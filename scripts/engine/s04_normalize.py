#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S04_normalize — parsed.* -> derived.fact

Contrato completo: docs/architecture/S04_CONTRACT.md

Convierte los hechos XBRL crudos en UN hecho canonico por
(entidad, filing, concepto, periodo, unidad), con la procedencia de cada uno.
No calcula ratios ni arma series: eso es S05.

Las tres trampas del insumo, medidas antes de escribir esto:
  T1  5.982 contextos duplicados (todos identicos). El JOIN ingenuo infla
      67.084 hechos a 100.804.
  T2  18.853 grupos de hechos duplicados; 98 con VALOR DISTINTO, que no son
      errores sino la misma cifra con distinta precision (decimals).
  T3  22.617 hechos consolidados vs 78.187 dimensionales. Sumarlos juntos
      duplica ingresos.

Requisito F-009 (obligatorio, y la razon por la que esto NO copia a S03):
  * run_scope(): el cierre va en `finally`.
  * la transicion a CHECKPOINTED + el report + la fila de engine.checkpoints
    se escriben en UNA SOLA TRANSACCION. En S03 iban separadas y por esa
    grieta se colaron 2 corridas que llegaron a CHECKPOINTED sin report.
  * corridas_huerfanas() al arrancar.

S03 NO se modifica: S04 lee su checkpoint, que esta verificado.

Uso:
    python scripts/engine/s04_normalize.py            # ejecuta
    python scripts/engine/s04_normalize.py --dry-run  # no escribe, solo gate
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine import db as edb
from engine import hashout  # noqa: E402
from engine.config import load_settings # noqa: E402
from engine.report import StageReport # noqa: E402
from engine.states import GateStatus, StageState # noqa: E402

STAGE_ID = "S04_normalize"
PIPELINE_VERSION = "engine-v1"
CONTRACT_VERSION = "derived-v1"
NORMALIZER_VERSION = "s04_normalize_v1"
SCRIPT = "scripts/engine/s04_normalize.py"
INPUT_STAGE = "S03_parse"

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "docs" / "fase_s04"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


# =====================================================================
# Desempate por precision (T2). Funcion pura: se testea sin base.
# =====================================================================

def rango_precision(decimals) -> tuple[int, int]:
    """Ordena la precision declarada. Mas alto = mas preciso.

    Devuelve (categoria, valor) para comparar:
      INF        -> (2, 0)   maxima precision, gana a cualquier finito
      finito n   -> (1, n)   entre finitos gana el mayor
      ausente    -> (0, 0)   sin precision declarada, pierde
    """
    if decimals is None:
        return (0, 0)
    d = str(decimals).strip().upper()
    if d in ("INF", "+INF"):
        return (2, 0)
    try:
        return (1, int(d))
    except ValueError:
        return (0, 0)


def elegir_ganador(candidatos: list[dict]) -> tuple[dict, str]:
    """De un grupo de hechos duplicados, elige uno y explica por que.

    Orden: precision declarada -> longitud del texto (digitos significativos
    conservados) -> fact_id menor. Nunca el orden de insercion.
    """
    if len(candidatos) == 1:
        return candidatos[0], "UNICO"

    # La identidad del valor es el TEXTO DECLARADO, no su interpretacion
    # numerica. '0.30' y '0.3000' son declaraciones distintas con distinta
    # precision; comparadas como numero son iguales y el desempate por
    # precision se perderia en silencio. (En Postgres NUMERIC llegan como
    # Decimal y conservan la escala, pero un float las colapsa: el codigo no
    # debe depender de que tipo llegue.)
    valores = {
        ("<nil>" if c["is_nil"]
         else c["value_text"] if c["value_text"] is not None
         else str(c["value_numeric"]))
        for c in candidatos
    }
    if len(valores) == 1:
        return min(candidatos, key=lambda c: c["fact_id"]), "IDENTICO"

    orden = sorted(
        candidatos,
        key=lambda c: (rango_precision(c["decimals"]),
                       len(c["value_text"] or ""),
                       -c["fact_id"]),
        reverse=True)
    mejor, segundo = orden[0], orden[1]
    empatados = (rango_precision(mejor["decimals"]) == rango_precision(segundo["decimals"])
                 and len(mejor["value_text"] or "") == len(segundo["value_text"] or ""))
    if empatados:
        return min(candidatos, key=lambda c: c["fact_id"]), "POR_FACT_ID"
    return mejor, "POR_PRECISION"


def normalizar_unidad(unit_type, measure, numerator, denominator) -> tuple[str | None, str | None, str | None]:
    """Devuelve (unit_kind, unit_measure, currency).

    `iso4217:ARS` -> moneda ARS. `utr:MMBbls` -> unidad fisica, sin moneda.
    Una unidad dividida (p.ej. ARS/accion) conserva ambos lados.
    """
    if unit_type == "DIVIDED":
        num = (numerator or "").strip()
        den = (denominator or "").strip()
        med = f"{num}/{den}" if (num or den) else None
        cur = num.split(":", 1)[1] if num.startswith("iso4217:") else None
        return "DIVIDED", med, cur
    m = (measure or "").strip() or None
    if m is None:
        return None, None, None
    cur = m.split(":", 1)[1] if m.startswith("iso4217:") else None
    return "SIMPLE", m, cur


def fact_key(entity_key, accession, qname, context_id, unit_ref) -> str:
    return sha("|".join((entity_key, accession, qname, context_id, unit_ref or "")))


# =====================================================================
# Lectura del insumo y validaciones previas
# =====================================================================

def checkpoint_s03(conn) -> dict:
    # Decisión R4/E2E: en modo E2E las etapas NO escriben checkpoints
    # individuales (un run E2E que aborta no debe dejar checkpoints dangling,
    # F-031). El insumo de S04 es el S03 del MISMO run E2E: se resuelve directo
    # por stage_runs, sin depender de engine.checkpoints.
    e2e_run_id = os.environ.get("ENGINE_E2E_RUN_ID")
    if e2e_run_id:
        s03_row = conn.execute(text(
            """
            SELECT state, gate_status FROM engine.stage_runs
             WHERE run_id = :r AND stage_id = :s
             ORDER BY id DESC LIMIT 1
            """), {"r": e2e_run_id, "s": INPUT_STAGE}).mappings().first()
        if s03_row is None or s03_row["gate_status"] != "PASS":
            raise RuntimeError(
                f"S04 en modo E2E requiere S03 con gate PASS en el run {e2e_run_id}")
        return {
            "checkpoint_id": f"S03E2E:{e2e_run_id}",
            "run_id": e2e_run_id,
            "code_version": "engine-v1",
            "contract_version": "parsed-v1",
            "artifact_ref": "pg://parsed.* (E2E, sin checkpoint individual)",
            "status": "OK",
        }
    row = conn.execute(text(
        """
        SELECT c.checkpoint_id, c.run_id, c.code_version, c.contract_version,
               c.artifact_ref, r.status
          FROM engine.checkpoints c JOIN engine.runs r ON r.run_id = c.run_id
         WHERE c.stage_id = :s ORDER BY c.created_at DESC LIMIT 1
        """), {"s": INPUT_STAGE}).mappings().first()
    if row is None:
        raise RuntimeError(f"No hay checkpoint de {INPUT_STAGE}. S04 no puede arrancar.")
    return dict(row)


PARSED_TABLES = ["parsed.facts", "parsed.contexts", "parsed.units",
                 "parsed.concepts", "parsed.link_relations"]


def hash_out_s03(conn, run_id: str) -> tuple[str, str, str]:
    """(declarado, recalculado, spec) — se recalcula, no se confia en lo declarado.

    F-029: la spec paso de `hashout-v1` (cinco conteos de filas) a `hashout-v2`
    (digest de contenido). Se compara contra la que el reporte DECLARA, para no
    contrastar hashes calculados con especificaciones distintas.
    """
    fila = conn.execute(text(
        "SELECT report->'integrity'->>'hash_out', "
        "       COALESCE(report->'integrity'->>'hash_spec', 'hashout-v1') "
        "  FROM engine.stage_runs "
        " WHERE run_id=:r AND report IS NOT NULL ORDER BY id DESC LIMIT 1"),
        {"r": run_id}).first()
    declarado, spec = (fila[0], fila[1]) if fila else (None, None)
    if spec == hashout.HASH_SPEC:
        return declarado, hashout.hash_out(conn, PARSED_TABLES)["hash_out"], spec
    tot = dict(zip(("facts", "contexts", "units", "concepts", "relations"),
                   conn.execute(text(
                       "SELECT (SELECT count(*) FROM parsed.facts),"
                       "(SELECT count(*) FROM parsed.contexts),"
                       "(SELECT count(*) FROM parsed.units),"
                       "(SELECT count(*) FROM parsed.concepts),"
                       "(SELECT count(*) FROM parsed.link_relations)")).one()))
    return declarado, sha(json.dumps(tot, sort_keys=True)), spec


# Un contexto XBRL puede llegar dos veces: SEC publica el documento inline
# (.htm) y la instancia extraida (_htm.xml) del MISMO filing, y ambos se
# parsean. Las dos representaciones son equivalentes pero serializan la lista de
# dimensiones en distinto ORDEN. Comparar `dimensions::text` las declaraba
# contradictorias, y `contextos_deduplicados` DESCARTA lo contradictorio: los
# hechos que usaban esos contextos se perdian en silencio (F-055).
#
# La lista de dimensiones es un conjunto, no una secuencia: se canoniza
# ordenando sus elementos antes de comparar. Es el mismo criterio que hashout-v2
# aplico a las filas.
#
# Las dimensiones TIPADAS guardan ademas el fragmento XML crudo, que arrastra
# los `xmlns` en alcance en ese punto del documento. El inline y la instancia
# declaran distintos prefijos, asi que el mismo valor tipado (p.ej. la fecha
# 2024-09-29 de AAPL) se serializaba distinto. Se comparan sin ese ruido.
SQL_CTX_CANONICO = """
SELECT ctx_id, run_id, accession_number, context_id, start_date, end_date,
       instant_date, period_kind, dim_count, dimensions,
       CASE WHEN jsonb_typeof(dimensions) = 'array'
            THEN (SELECT jsonb_agg(e ORDER BY e::text)
                    FROM jsonb_array_elements(dimensions) e)
            ELSE dimensions END AS dims_c,
       CASE WHEN jsonb_typeof(typed_dimensions) = 'array'
            THEN (SELECT jsonb_agg(n ORDER BY n::text) FROM (
                    SELECT CASE WHEN e ? 'content'
                                THEN jsonb_set(e, '{content}', to_jsonb(
                                       regexp_replace(e->>'content',
                                         '\\s+xmlns(:[A-Za-z0-9_.-]+)?="[^"]*"', '', 'g')))
                                ELSE e END AS n
                      FROM jsonb_array_elements(typed_dimensions) e) t)
            ELSE typed_dimensions END AS typed_c
  FROM parsed.contexts
"""


def contextos_deduplicados(conn, run_id: str) -> tuple[dict, list]:
    """T1 — un contexto por (accession, context_id). Reporta contradicciones."""
    filas = conn.execute(text(
        f"""
        SELECT accession_number, context_id,
               count(*) AS n,
               count(DISTINCT (start_date, end_date, instant_date, period_kind,
                               dims_c, typed_c)::text) AS variantes,
               min(start_date) AS start_date, min(end_date) AS end_date,
               min(instant_date) AS instant_date, min(period_kind) AS period_kind,
               min(dim_count) AS dim_count,
               (array_agg(dimensions ORDER BY ctx_id))[1] AS dimensions
          FROM ({SQL_CTX_CANONICO}) z
         WHERE run_id = :r
         GROUP BY accession_number, context_id
        """), {"r": run_id}).mappings().all()
    ctx = {}
    contradictorios = []
    for f in filas:
        if f["variantes"] > 1:
            contradictorios.append(dict(f))
            continue
        ctx[(f["accession_number"], f["context_id"])] = dict(f)
    return ctx, contradictorios


def resolver_entidad(conn, cik: str) -> str | None:
    return conn.execute(text(
        "SELECT entity_key FROM identity_v1.identifier "
        " WHERE id_type='CIK' AND id_namespace='SEC' AND id_value=:v "
        "   AND is_authoritative AND valid_to IS NULL"), {"v": cik}).scalar()


# =====================================================================
# Normalizacion
# =====================================================================

def normalizar(conn, s03: dict, run_id: str) -> tuple[list[dict], list[dict], dict]:
    ctx, contradictorios = contextos_deduplicados(conn, s03["run_id"])
    conflictos = [{"kind": "CONTEXTO_CONTRADICTORIO",
                   "accession_number": c["accession_number"],
                   "context_id": c["context_id"], "qname": None,
                   "detalle": {"variantes": c["variantes"]}} for c in contradictorios]

    concepto_custom = dict(conn.execute(text(
        "SELECT qname, bool_or(is_custom) FROM parsed.concepts WHERE run_id=:r "
        " GROUP BY qname"), {"r": s03["run_id"]}).all())

    filas = conn.execute(text(
        """
        SELECT fact_id, cik, accession_number, form, filing_date, report_period,
               qname, namespace, tag, context_id, unit_ref, unit_type, measure,
               numerator, denominator, value_numeric, value_text, is_numeric,
               is_nil, decimals
          FROM parsed.facts WHERE run_id = :r
         ORDER BY accession_number, qname, context_id, COALESCE(unit_ref,''), fact_id
        """), {"r": s03["run_id"]}).mappings().all()

    entidades: dict[str, str | None] = {}
    grupos: dict[tuple, list[dict]] = {}
    for f in filas:
        grupos.setdefault(
            (f["accession_number"], f["qname"], f["context_id"], f["unit_ref"] or ""),
            []).append(dict(f))

    hechos = []
    stats = {"grupos": len(grupos), "filas_entrada": len(filas), "desempates": {},
             "sin_contexto": 0, "sin_entidad": 0, "sin_unidad": 0,
             "unidad_no_resuelta": 0}

    for clave, cands in grupos.items():
        accession, qname, context_id, unit_ref = clave
        c = ctx.get((accession, context_id))
        if c is None:
            stats["sin_contexto"] += len(cands)
            conflictos.append({"kind": "CONTEXTO_CONTRADICTORIO",
                               "accession_number": accession, "context_id": context_id,
                               "qname": qname,
                               "detalle": {"motivo": "el contexto no quedo deduplicado"}})
            continue

        cik = cands[0]["cik"]
        if cik not in entidades:
            entidades[cik] = resolver_entidad(conn, cik)
        ek = entidades[cik]
        if ek is None:
            stats["sin_entidad"] += len(cands)
            conflictos.append({"kind": "IDENTIDAD_SIN_RESOLVER",
                               "accession_number": accession, "qname": qname,
                               "context_id": context_id,
                               "detalle": {"cik": cik,
                                           "motivo": "identity_v1 no lo resuelve autoritativamente"}})
            continue

        ganador, motivo = elegir_ganador(cands)
        stats["desempates"][motivo] = stats["desempates"].get(motivo, 0) + 1
        if motivo == "POR_FACT_ID":
            conflictos.append({"kind": "VALOR_SIN_DESEMPATE",
                               "accession_number": accession, "qname": qname,
                               "context_id": context_id,
                               "detalle": {"candidatos": len(cands),
                                           "valores": sorted({
                                               (x["value_text"] or str(x["value_numeric"]))[:60]
                                               for x in cands})}})

        kind, measure, currency = normalizar_unidad(
            ganador["unit_type"], ganador["measure"],
            ganador["numerator"], ganador["denominator"])
        # F-026: S03 no extrae numerator/denominator de las unidades DIVIDED,
        # ni en parsed.facts ni en parsed.units. El unico dato es el NOMBRE del
        # unit_ref ('Unit_USD_per_Share'), y derivar la moneda de ahi seria
        # inferir por nombre. No se descarta el hecho ni se le inventa la
        # unidad: se emite marcado y el conflicto dice por que.
        unidad_resuelta = True
        if ganador["is_numeric"] and not ganador["is_nil"] and measure is None:
            if not unit_ref:
                stats["sin_unidad"] = stats.get("sin_unidad", 0) + len(cands)
                conflictos.append({"kind": "UNIDAD_DESCONOCIDA",
                                   "accession_number": accession, "qname": qname,
                                   "context_id": context_id,
                                   "detalle": {"unit_ref": None,
                                               "motivo": "el hecho no declara unidad"}})
                continue
            unidad_resuelta = False
            stats["unidad_no_resuelta"] = stats.get("unidad_no_resuelta", 0) + 1
            conflictos.append({"kind": "UNIDAD_DESCONOCIDA",
                               "accession_number": accession, "qname": qname,
                               "context_id": context_id,
                               "detalle": {"unit_ref": unit_ref,
                                           "unit_type": ganador["unit_type"],
                                           "motivo": "S03 no extrajo numerator/denominator "
                                                     "(F-026); no se infiere del nombre"}})

        dim_count = c["dim_count"] or 0
        hechos.append({
            "fact_key": fact_key(ek, accession, qname, context_id, unit_ref),
            "entity_key": ek, "cik": cik, "accession_number": accession,
            "form": ganador["form"], "filing_date": ganador["filing_date"],
            "report_period": ganador["report_period"],
            "qname": qname, "namespace": ganador["namespace"], "tag": ganador["tag"],
            "is_custom": concepto_custom.get(qname),
            "context_id": context_id, "period_kind": c["period_kind"],
            "start_date": c["start_date"], "end_date": c["end_date"],
            "instant_date": c["instant_date"],
            "is_dimensional": dim_count > 0, "dim_count": dim_count,
            "dimensions": json.dumps(c["dimensions"]) if c["dimensions"] is not None else None,
            "unit_ref": unit_ref or None, "unit_kind": kind,
            "unit_measure": measure, "currency": currency,
            "unidad_resuelta": unidad_resuelta,
            "value_numeric": ganador["value_numeric"], "value_text": ganador["value_text"],
            "is_nil": ganador["is_nil"], "is_numeric": ganador["is_numeric"],
            "decimals": ganador["decimals"],
            "n_fuentes": len(cands),
            "source_fact_ids": sorted(x["fact_id"] for x in cands),
            "desempate": motivo,
            "input_checkpoint_id": s03["checkpoint_id"], "run_id": run_id,
        })

    return hechos, conflictos, stats


def escribir(conn, hechos: list[dict], conflictos: list[dict], run_id: str) -> None:
    LOTE = 2000
    for i in range(0, len(hechos), LOTE):
        conn.execute(text(
            """
            INSERT INTO derived.fact (
                fact_key, entity_key, cik, accession_number, form, filing_date,
                report_period, qname, namespace, tag, is_custom, context_id,
                period_kind, start_date, end_date, instant_date, is_dimensional,
                dim_count, dimensions, unit_ref, unit_kind, unit_measure, currency,
                unidad_resuelta,
                value_numeric, value_text, is_nil, is_numeric, decimals,
                n_fuentes, source_fact_ids, desempate, input_checkpoint_id, run_id)
            VALUES (
                :fact_key, :entity_key, :cik, :accession_number, :form, :filing_date,
                :report_period, :qname, :namespace, :tag, :is_custom, :context_id,
                :period_kind, :start_date, :end_date, :instant_date, :is_dimensional,
                :dim_count, CAST(:dimensions AS JSONB), :unit_ref, :unit_kind,
                :unit_measure, :currency, :unidad_resuelta, :value_numeric, :value_text, :is_nil,
                :is_numeric, :decimals, :n_fuentes, :source_fact_ids, :desempate,
                :input_checkpoint_id, :run_id)
            ON CONFLICT (fact_key) DO UPDATE SET
                value_numeric = EXCLUDED.value_numeric,
                value_text    = EXCLUDED.value_text,
                decimals      = EXCLUDED.decimals,
                n_fuentes     = EXCLUDED.n_fuentes,
                source_fact_ids = EXCLUDED.source_fact_ids,
                desempate     = EXCLUDED.desempate,
                -- la unidad TAMBIEN se refresca: si una correccion aguas
                -- arriba la resuelve (F-026), el hecho tiene que dejar de
                -- estar marcado como no resuelto. Sin esto el upsert dejaba
                -- 295 filas diciendo 'unidad no resuelta' cuando ya lo estaba.
                unit_kind       = EXCLUDED.unit_kind,
                unit_measure    = EXCLUDED.unit_measure,
                currency        = EXCLUDED.currency,
                unidad_resuelta = EXCLUDED.unidad_resuelta,
                -- y los atributos del filing y del periodo, por el mismo motivo
                form          = EXCLUDED.form,
                filing_date   = EXCLUDED.filing_date,
                report_period = EXCLUDED.report_period,
                is_custom     = EXCLUDED.is_custom,
                period_kind   = EXCLUDED.period_kind,
                start_date    = EXCLUDED.start_date,
                end_date      = EXCLUDED.end_date,
                instant_date  = EXCLUDED.instant_date,
                is_dimensional = EXCLUDED.is_dimensional,
                dim_count     = EXCLUDED.dim_count,
                dimensions    = EXCLUDED.dimensions,
                is_nil        = EXCLUDED.is_nil,
                is_numeric    = EXCLUDED.is_numeric,
                input_checkpoint_id = EXCLUDED.input_checkpoint_id,
                run_id        = EXCLUDED.run_id,
                valid_to      = NULL,
                updated_at    = now()
            """), hechos[i:i + LOTE])
    for c in conflictos:
        conn.execute(text(
            "INSERT INTO derived.normalize_conflict "
            "(run_id, kind, accession_number, qname, context_id, detalle) "
            "VALUES (:r, :k, :a, :q, :c, CAST(:d AS JSONB))"),
            {"r": run_id, "k": c["kind"], "a": c.get("accession_number"),
             "q": c.get("qname"), "c": c.get("context_id"),
             "d": json.dumps(c["detalle"])})


# =====================================================================
# Gate — 9 checks contra la base, no contra contadores internos
# =====================================================================

def correr_gate(conn, s03: dict, run_id: str, stats: dict, dry: bool) -> list[dict]:
    checks: list[dict] = []

    def chk(cid, ok, detalle=""):
        checks.append({"id": cid, "result": "PASS" if ok else "FAIL", "detail": detalle})

    decl, recalc, spec = hash_out_s03(conn, s03["run_id"])
    chk("C-S04-001", decl == recalc and s03["status"] == "OK" and spec == hashout.HASH_SPEC,
        f"spec={spec} declarado={decl} recalculado={recalc} corrida={s03['status']}")

    # F-054: `parsed` acumula un emisor por corrida. La invariante ya no es
    # "una sola corrida en la tabla" —eso era cierto cuando habia un unico
    # golden case— sino "ningun CIK mezcla corridas".
    n_runs = conn.execute(text("SELECT count(DISTINCT run_id) FROM parsed.facts")).scalar()
    ciks_mezclados = conn.execute(text(
        "SELECT count(*) FROM (SELECT cik FROM parsed.facts GROUP BY cik "
        "  HAVING count(DISTINCT run_id) > 1) x")).scalar()
    chk("C-S04-002", ciks_mezclados == 0,
        f"CIK con hechos de mas de una corrida: {ciks_mezclados} "
        f"(corridas en parsed.facts: {n_runs}, una por emisor)")

    contradictorios = conn.execute(text(
        f"SELECT count(*) FROM (SELECT accession_number, context_id "
        f"  FROM ({SQL_CTX_CANONICO}) z WHERE run_id=:r GROUP BY 1,2 "
        f" HAVING count(DISTINCT (start_date,end_date,instant_date,period_kind,"
        f"dims_c,typed_c)::text) > 1) x"), {"r": s03["run_id"]}).scalar()
    chk("C-S04-003", contradictorios == 0, f"contextos contradictorios: {contradictorios}")

    ciks = [r[0] for r in conn.execute(text(
        "SELECT DISTINCT cik FROM parsed.facts WHERE run_id=:r"), {"r": s03["run_id"]})]
    sin_resolver = [c for c in ciks if resolver_entidad(conn, c) is None]
    chk("C-S04-004", not sin_resolver, f"CIK sin entidad en identity_v1: {sin_resolver}")

    if dry:
        for cid in ("C-S04-005", "C-S04-006", "C-S04-007", "C-S04-008", "C-S04-009"):
            checks.append({"id": cid, "result": "SKIP", "detail": "dry-run"})
        return checks

    # SIN PERDIDA: todo fact_id de parsed aparece en algun source_fact_ids
    # SIN PERDIDA. El anti-join en SQL (con `@>` o con CTE) agota el
    # statement_timeout: son 67k facts contra 47k arrays. Se comparan los dos
    # conjuntos en memoria — son enteros, entran de sobra— pero AMBOS se leen
    # DE LA BASE: se verifica lo persistido, no un contador del proceso.
    cubiertos = {r[0] for r in conn.execute(text(
        "SELECT DISTINCT unnest(source_fact_ids) FROM derived.fact WHERE run_id = :run"),
        {"run": run_id})}
    entrada = {r[0] for r in conn.execute(text(
        "SELECT fact_id FROM parsed.facts WHERE run_id = :r"), {"r": s03["run_id"]})}
    perdidos = len(entrada - cubiertos)
    invasores = len(cubiertos - entrada)
    esperados_fuera = (stats["sin_contexto"] + stats["sin_entidad"]
                       + stats["sin_unidad"])
    chk("C-S04-005", perdidos == esperados_fuera and invasores == 0,
        f"facts sin representar: {perdidos} (excluidos por conflicto: {esperados_fuera}) "
        f"· fact_ids citados que no existen en el insumo: {invasores}")

    sin_origen = conn.execute(text(
        "SELECT count(*) FROM derived.fact WHERE run_id=:r AND n_fuentes < 1"),
        {"r": run_id}).scalar()
    chk("C-S04-006", sin_origen == 0, f"hechos sin fila de origen: {sin_origen}")

    sin_unidad = conn.execute(text(
        "SELECT count(*) FROM derived.fact WHERE run_id=:r AND is_numeric "
        "  AND NOT is_nil AND unidad_resuelta AND unit_measure IS NULL"),
        {"r": run_id}).scalar()
    no_resueltas = conn.execute(text(
        "SELECT count(*) FROM derived.fact WHERE run_id=:r AND NOT unidad_resuelta"),
        {"r": run_id}).scalar()
    chk("C-S04-007", sin_unidad == 0,
        f"numericos con unidad resuelta pero sin medida: {sin_unidad} "
        f"· con unidad declarada y no resuelta (F-026): {no_resueltas}")

    # IDEMPOTENCIA: recalcular las claves y comparar con lo persistido
    total = conn.execute(text("SELECT count(*) FROM derived.fact WHERE run_id=:r"),
                         {"r": run_id}).scalar()
    huella = conn.execute(text(
        "SELECT md5(string_agg(fact_key, ',' ORDER BY fact_key)) FROM derived.fact "
        " WHERE run_id=:r"), {"r": run_id}).scalar()
    hechos2, _, _ = normalizar(conn, s03, run_id)
    huella2 = hashlib.md5(",".join(sorted(h["fact_key"] for h in hechos2)).encode()).hexdigest()
    chk("C-S04-008", total == len(hechos2) and huella == huella2,
        f"persistidos={total} recomputados={len(hechos2)} huella_igual={huella == huella2}")

    sin_dim = conn.execute(text(
        "SELECT count(*) FROM derived.fact WHERE run_id=:r AND is_dimensional IS NULL"),
        {"r": run_id}).scalar()
    chk("C-S04-009", sin_dim == 0, f"is_dimensional nulo: {sin_dim}")
    return checks


def build_s04_report(*, stage, run_id, mode, started_at, finished_at,
                     script, normalizer_version, git_commit,
                     input_stage, s03, stats, hechos, resumen, h2,
                     gate, checks, fallidos):
    """Construye el reporte S04 sobre engine.report.StageReport (M7, FASE 1).

    Mapeo C10: expected = filas de entrada (parsed), parsed = hechos
    canonicos emitidos, rejected = expected - parsed (caidos en
    normalizacion; numero honesto por construccion). El desglose por causa
    vive en coverage_detail porque las categorias de caida se solapan
    (un hecho puede ser sin_contexto y sin_entidad a la vez) y no admiten
    particion exacta: no se inventa un by_reason que no cuadre.
    Todo el contenido legacy se preserva como extras (code.normalizer_version,
    input.stage/run_id, coverage_detail, integrity extendida, nulls por causa
    exacta). validate() impone el contrato C10; unico cambio de conducta
    posible vs legacy: gate PASS con cero checks ahora falla en validate()
    (norma del proyecto: 'termino sin excepcion' nunca es PASS).
    """
    emitidos = len(hechos)
    sr = StageReport(
        stage=stage, run_id=run_id, mode=mode,
        started_at=started_at, finished_at=finished_at,
        gate=gate,
        input_checkpoint_id=s03["checkpoint_id"],
        input_rows=stats["filas_entrada"],
        expected=stats["filas_entrada"],
        parsed=emitidos,
        rejected=stats["filas_entrada"] - emitidos,
        hash_in=sha(s03["checkpoint_id"]),
        hash_out=h2["hash_out"],
        gate_reasons=[c["detail"] for c in fallidos],
        checks=[{"id": c["id"], "result": c["result"]} for c in checks],
        nulls_count=stats["sin_contexto"] + stats["sin_entidad"],
        nulls_by_reason={"sin_contexto": stats["sin_contexto"],
                         "sin_entidad": stats["sin_entidad"]},
        parser_version=normalizer_version,
        script=script,
        git_commit=git_commit,
    )
    sr.validate()
    report = sr.to_dict()
    report["code"]["normalizer_version"] = normalizer_version
    report["input"]["stage"] = input_stage
    report["input"]["run_id"] = s03["run_id"]
    report["coverage_detail"] = {
        "grupos": stats["grupos"], "emitidos": emitidos,
        "sin_contexto": stats["sin_contexto"],
        "sin_entidad": stats["sin_entidad"],
        "sin_unidad": stats["sin_unidad"],
        "unidad_no_resuelta": stats["unidad_no_resuelta"],
        "desempates": stats["desempates"],
    }
    report["integrity"]["hash_out_v1"] = sha(json.dumps(resumen, sort_keys=True))
    report["integrity"]["hash_spec"] = h2["hash_spec"]
    report["integrity"]["por_tabla"] = h2["por_tabla"]
    return report


# =====================================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no escribe; corre el gate previo")
    args = ap.parse_args()

    settings = load_settings()
    if settings.is_prod:
        print("EXT-010: S04 no corre contra 5432.")
        return 2
    engine = edb.get_engine(settings)

    huerfanas = edb.corridas_huerfanas(engine)
    if huerfanas:
        print(f"BLOCK · F-009: hay {len(huerfanas)} corrida(s) huerfana(s). "
              "Cerrarlas antes de generar mas.")
        for h in huerfanas:
            print(f"   {h['run_id']} {h['pipeline_version']} {h['horas']} h")
        return 1

    started_at = utc_now_iso()
    with engine.connect() as c:
        s03 = checkpoint_s03(c)
    print(f"S04_normalize · {settings.describe()}")
    print(f"insumo: checkpoint {s03['checkpoint_id']} (corrida {s03['run_id']}, "
          f"status {s03['status']})\n")

    # ---- run_scope: el cierre va en finally (F-009) --------------------
    with edb.run_scope(engine, settings, PIPELINE_VERSION,
                       run_id=os.environ.get("ENGINE_E2E_RUN_ID"),
                       stage_id=STAGE_ID) as run:
        prev = None
        for st in (StageState.READY, StageState.RUNNING):
            edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev, st)
            prev = st

        with engine.begin() as conn:
            hechos, conflictos, stats = normalizar(conn, s03, run.run_id)
            if not args.dry_run:
                escribir(conn, hechos, conflictos, run.run_id)

        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev, StageState.VALIDATING)
        prev = StageState.VALIDATING

        with engine.connect() as conn:
            checks = correr_gate(conn, s03, run.run_id, stats, args.dry_run)
        fallidos = [c for c in checks if c["result"] == "FAIL"]
        gate = GateStatus.BLOCK if fallidos else GateStatus.PASS

        resumen = {
            "facts": len(hechos),
            "entidades": len({h["entity_key"] for h in hechos}),
            "filings": len({h["accession_number"] for h in hechos}),
            "dimensionales": sum(1 for h in hechos if h["is_dimensional"]),
            "conflictos": len(conflictos),
            "unidad_no_resuelta": stats["unidad_no_resuelta"],
        }
        with engine.connect() as conn:
            h2 = hashout.hash_out(conn, ["derived.fact"], "run_id = :r",
                                  {"r": run.run_id})
        report = build_s04_report(
            stage=STAGE_ID, run_id=run.run_id, mode=settings.mode,
            started_at=started_at, finished_at=utc_now_iso(),
            script=SCRIPT, normalizer_version=NORMALIZER_VERSION,
            git_commit=run.git_commit, input_stage=INPUT_STAGE,
            s03=s03, stats=stats, hechos=hechos, resumen=resumen, h2=h2,
            gate=gate, checks=checks, fallidos=fallidos,
        )

        # ---- OPERACION CONSISTENTE (F-009): transicion + report +
        #      checkpoint en UNA transaccion. En S03 iban separadas.
        camino = [StageState.FAILED] if gate is GateStatus.BLOCK else [StageState.PASSED,
                                                                       StageState.CHECKPOINTED]
        with engine.begin() as conn:
            cursor = prev
            for nxt in camino:
                conn.execute(text(
                    "INSERT INTO engine.stage_runs (run_id, stage_id, state, prev_state, "
                    " gate_status, gate_reasons) VALUES (:r,:s,:st,:pv,:g,CAST(:gr AS JSONB))"),
                    {"r": run.run_id, "s": STAGE_ID, "st": nxt.value,
                     "pv": cursor.value if cursor else None,
                     "g": gate.value if nxt == camino[-1] else None,
                     "gr": json.dumps([c["detail"] for c in fallidos])})
                cursor = nxt
            conn.execute(text(
                "UPDATE engine.stage_runs SET report = CAST(:rep AS JSONB), finished_at = now() "
                " WHERE id = (SELECT max(id) FROM engine.stage_runs "
                "             WHERE run_id=:r AND stage_id=:s)"),
                {"rep": json.dumps(report), "r": run.run_id, "s": STAGE_ID})
            if gate is GateStatus.PASS and not args.dry_run:
                conn.execute(text(
                    "INSERT INTO engine.checkpoints (checkpoint_id, stage_id, run_id, "
                    " input_hash, code_version, contract_version, artifact_ref) "
                    "VALUES (:cid,:s,:r,:ih,:cv,:ctv,:ref) "
                    "ON CONFLICT (stage_id, input_hash, code_version, contract_version) "
                    "DO UPDATE SET checkpoint_id=EXCLUDED.checkpoint_id, "
                    " run_id=EXCLUDED.run_id, artifact_ref=EXCLUDED.artifact_ref, "
                    " created_at=now()"),
                    {"cid": run.run_id[:16] + "-s04", "s": STAGE_ID, "r": run.run_id,
                     "ih": report["integrity"]["hash_in"], "cv": PIPELINE_VERSION,
                     "ctv": CONTRACT_VERSION,
                     "ref": "pg://derived.fact + fs://outputs/docs/fase_s04"})

        run.status = "OK" if gate is GateStatus.PASS else "BLOCKED"

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"s04_report_{run.run_id[:16]}.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"grupos {stats['grupos']} -> hechos canonicos {len(hechos)}")
        print(f"desempates: {stats['desempates']}")
        print(f"dimensionales {resumen['dimensionales']} / consolidados "
              f"{resumen['facts'] - resumen['dimensionales']}")
        print(f"conflictos registrados: {len(conflictos)}")
        print(f"\nGATE {gate.value}")
        for c in checks:
            print(f"   [{c['result']:<4}] {c['id']}  {c['detail']}")
        print(f"\nhash_in  {report['integrity']['hash_in']}")
        print(f"hash_out {report['integrity']['hash_out']}")
        if gate is GateStatus.PASS and not args.dry_run:
            print(f"checkpoint {run.run_id[:16]}-s04")
        return 0 if gate is GateStatus.PASS else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
