#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE de F-054 y F-055.

Independencia: no importa `engine.*` ni ninguno de los modulos que implementaron
las correcciones. Habla con PostgreSQL por `psql` via subprocess y reconstruye
cada invariante con su propio SQL. No lee logs, ni reportes de gate, ni los
documentos que declaran PASS.

Preguntas que responde:

  F-054  ¿Puede procesarse mas de una empresa sin que la provenance de una
         termine apuntando a hechos de otra?
  F-055  ¿Se sigue perdiendo algun hecho por contextos declarados
         contradictorios que no lo son?

SOLO LECTURA sobre la base homologada. Las pruebas mutacionales van aparte.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "auditoria"
CONT = "catalaxia-engine-dev"
DB = "catalaxia"

# Canonizacion de contextos, reescrita por el auditor a partir del CONTRATO
# ("una lista de dimensiones es un conjunto; el fragmento XML tipado no debe
# arrastrar los xmlns"), no copiada del implementador.
CTX_CANON = """
SELECT run_id, accession_number, context_id, start_date, end_date, instant_date,
       period_kind,
       CASE WHEN jsonb_typeof(dimensions)='array'
            THEN (SELECT jsonb_agg(x ORDER BY x::text)
                    FROM jsonb_array_elements(dimensions) x) ELSE dimensions END AS d1,
       CASE WHEN jsonb_typeof(typed_dimensions)='array'
            THEN (SELECT jsonb_agg(y ORDER BY y::text) FROM (
                    SELECT CASE WHEN x ? 'content'
                                THEN jsonb_set(x,'{content}', to_jsonb(regexp_replace(
                                       x->>'content','\\s+xmlns(:[-\\w.]+)?="[^"]*"','','g')))
                                ELSE x END AS y
                      FROM jsonb_array_elements(typed_dimensions) x) q)
            ELSE typed_dimensions END AS d2
  FROM parsed.contexts
"""


def sql(q: str, db: str = DB) -> list[list[str]]:
    p = subprocess.run(
        ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
         "-t", "-A", "-F", "\x1f", "-c", q],
        capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo:\n{p.stderr[:600]}")
    return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]


def uno(q: str, db: str = DB):
    r = sql(q, db)
    return r[0][0] if r else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total = [], True

    def chk(nombre, cond, detalle="", critico=True):
        nonlocal ok_total
        marca = "OK   " if cond else ("FALLA" if critico else "AVISO")
        print(f"  {marca} {nombre:<58} {detalle}")
        res.append({"control": nombre, "ok": bool(cond), "critico": critico,
                    "detalle": str(detalle)[:500]})
        if not cond and critico:
            ok_total = False

    print("AUDITORIA INDEPENDIENTE — F-054 / F-055")
    print("  psql directo · SQL propio · sin importar codigo del implementador\n")

    # ───────────────────────── BASELINE ─────────────────────────
    print("0. BASELINE")
    universo = sql("SELECT cik, count(*) FROM parsed.facts GROUP BY cik ORDER BY cik")
    derived = dict((r[0], int(r[1])) for r in
                   sql("SELECT cik, count(*) FROM derived.fact WHERE valid_to IS NULL "
                       " GROUP BY cik"))
    print(f"   emisores en parsed.facts : {len(universo)}")
    for cik, n in universo:
        print(f"     {cik}  parsed={int(n):>7,}  derived={derived.get(cik, 0):>7,}")
    corriendo = uno("SELECT count(*) FROM engine.runs WHERE status='RUNNING'")
    chk("0.1 · ningun pipeline en vuelo durante la auditoria", corriendo == "0",
        f"{corriendo} corridas RUNNING")
    chk("0.2 · el universo tiene mas de un emisor (si no, F-054 no se prueba)",
        len(universo) > 1, f"{len(universo)} emisores")

    # ═══════════════════════ F-054 ═══════════════════════
    print("\nF-054 · AISLAMIENTO DE LA PROVENANCE ENTRE EMISORES")

    # 1 · TODOS los elementos de source_fact_ids, no solo el primero
    filas = sql("""
        SELECT d.cik,
               count(*) AS punteros,
               count(*) FILTER (WHERE p.fact_id IS NULL) AS colgados,
               count(*) FILTER (WHERE p.cik IS NOT NULL AND p.cik <> d.cik) AS ajenos
          FROM derived.fact d
          CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          LEFT JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL
         GROUP BY d.cik ORDER BY d.cik""")
    tot_p = sum(int(r[1]) for r in filas)
    tot_c = sum(int(r[2]) for r in filas)
    tot_a = sum(int(r[3]) for r in filas)
    print(f"   {'cik':<12} {'punteros':>10} {'colgados':>10} {'de otra empresa':>17}")
    for r in filas:
        print(f"   {r[0]:<12} {int(r[1]):>10,} {int(r[2]):>10,} {int(r[3]):>17,}")
    chk("1.1 · ningun puntero resuelve a un hecho de OTRA empresa", tot_a == 0,
        f"{tot_a} de {tot_p:,} punteros")
    chk("1.2 · ningun puntero queda colgado", tot_c == 0,
        f"{tot_c} de {tot_p:,} punteros")

    # 2 · los rangos de fact_id no se solapan entre emisores
    rangos = sql("SELECT cik, min(fact_id), max(fact_id), count(*) "
                 "  FROM parsed.facts GROUP BY cik ORDER BY min(fact_id)")
    solapes = []
    for i in range(len(rangos)):
        for j in range(i + 1, len(rangos)):
            a, b = rangos[i], rangos[j]
            if int(a[1]) <= int(b[2]) and int(b[1]) <= int(a[2]):
                solapes.append(f"{a[0]}[{a[1]}-{a[2]}] x {b[0]}[{b[1]}-{b[2]}]")
    chk("2.1 · los rangos de fact_id no se solapan entre emisores", not solapes,
        f"{len(rangos)} emisores, {len(solapes)} solapes " + (str(solapes[:2]) if solapes else ""))

    # 3 · la secuencia nunca vuelve atras
    seq = uno("SELECT last_value FROM parsed.facts_fact_id_seq")
    maxid = uno("SELECT max(fact_id) FROM parsed.facts")
    chk("2.2 · la secuencia de fact_id no fue reiniciada",
        seq is not None and maxid is not None and int(seq) >= int(maxid),
        f"secuencia={seq} max(fact_id)={maxid}")

    # 4 · un fact_id nunca designa dos hechos
    dupid = uno("SELECT count(*) FROM (SELECT fact_id FROM parsed.facts "
                " GROUP BY fact_id HAVING count(*)>1) x")
    chk("2.3 · fact_id es unico en toda la tabla", dupid == "0", f"{dupid} repetidos")

    # 5 · cada hecho derivado cita hechos de SU MISMO accession
    cruce_acc = uno("""
        SELECT count(*) FROM derived.fact d
         CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND p.accession_number <> d.accession_number""")
    chk("3.1 · ningun hecho derivado cita un filing distinto del suyo",
        cruce_acc == "0", f"{cruce_acc} punteros cruzan accession")

    # 6 · el qname citado coincide
    cruce_q = uno("""
        SELECT count(*) FROM derived.fact d
         CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND p.qname <> d.qname""")
    chk("3.2 · el concepto citado coincide con el del hecho derivado",
        cruce_q == "0", f"{cruce_q} punteros cambian de concepto")

    # 7 · seleccion del insumo de S02 por CIK
    print("\n   seleccion del insumo de S02 (atribucion cruzada de entrada)")
    malas = []
    for cik, _ in universo:
        run = uno(f"""
            SELECT r.run_id FROM engine.runs r
             WHERE EXISTS (SELECT 1 FROM engine.stage_runs s WHERE s.run_id=r.run_id
                            AND s.stage_id='S02_fetch' AND s.gate_status='PASS')
               AND EXISTS (SELECT 1 FROM fetch_raw.download_log d WHERE d.run_id=r.run_id
                            AND d.cik='{cik}')
             ORDER BY r.started_at DESC LIMIT 1""")
        if not run:
            malas.append(f"{cik}: sin corrida S02")
            continue
        otros = uno(f"SELECT count(DISTINCT cik) FROM fetch_raw.download_log "
                    f" WHERE run_id='{run}' AND cik <> '{cik}'")
        if otros != "0":
            malas.append(f"{cik}: su corrida S02 {run[:8]} trae {otros} CIK ajenos")
    chk("4.1 · la corrida S02 elegida por CIK no contiene otro emisor", not malas,
        f"{len(universo)} emisores verificados " + (str(malas[:2]) if malas else ""))

    # ═══════════════════════ F-055 ═══════════════════════
    print("\nF-055 · CONTEXTOS CONTRADICTORIOS Y PERDIDA DE HECHOS")

    # 8 · comparacion ingenua vs canonica: cuanto absorbio la correccion
    ingenuos = uno("""
        SELECT count(*) FROM (SELECT accession_number, context_id FROM parsed.contexts
          GROUP BY 1,2 HAVING count(DISTINCT (start_date,end_date,instant_date,
            period_kind,dimensions,typed_dimensions)::text) > 1) x""")
    canonicos = uno(f"""
        SELECT count(*) FROM (SELECT accession_number, context_id FROM ({CTX_CANON}) z
          GROUP BY 1,2 HAVING count(DISTINCT (start_date,end_date,instant_date,
            period_kind,d1,d2)::text) > 1) x""")
    print(f"   contradictorios con comparacion INGENUA  : {ingenuos}")
    print(f"   contradictorios con comparacion CANONICA : {canonicos}")
    chk("5.1 · no quedan contextos contradictorios bajo la regla canonica",
        canonicos == "0", f"{canonicos} contextos")
    chk("5.2 · la correccion absorbio falsos positivos reales",
        int(ingenuos) > 0, f"{ingenuos} eran falsos contradictorios", critico=False)

    # 9 · hechos en riesgo de ser descartados por contexto contradictorio
    en_riesgo = uno(f"""
        SELECT count(*) FROM parsed.facts f
         WHERE (f.accession_number, f.context_id) IN (
           SELECT accession_number, context_id FROM ({CTX_CANON}) z GROUP BY 1,2
            HAVING count(DISTINCT (start_date,end_date,instant_date,period_kind,d1,d2)::text)>1)""")
    chk("6.1 · ningun hecho depende de un contexto descartable", en_riesgo == "0",
        f"{en_riesgo} hechos")

    # 10 · CONTROL CENTRAL: derived == grupos canonicos de parsed, sin perdida
    print("\n   conservacion: grupos de parsed que deben producir un hecho derivado")
    grupos = dict((r[0], int(r[1])) for r in sql("""
        SELECT cik, count(*) FROM (
          SELECT cik, accession_number, qname, context_id, coalesce(unit_ref,'') u
            FROM parsed.facts GROUP BY 1,2,3,4,5) x GROUP BY cik"""))
    print(f"   {'cik':<12} {'grupos parsed':>14} {'derived':>10} {'diferencia':>12}")
    perdidas = []
    for cik in sorted(grupos):
        g, d = grupos[cik], derived.get(cik, 0)
        dif = d - g
        print(f"   {cik:<12} {g:>14,} {d:>10,} {dif:>12,}")
        if dif != 0:
            perdidas.append(f"{cik}: grupos={g} derived={d} dif={dif}")
    chk("6.2 · derived tiene exactamente un hecho por grupo canonico de parsed",
        not perdidas, (str(perdidas[:3]) if perdidas else "todos coinciden"))

    # 11 · los hechos duplicados por doble representacion se colapsan, no se pierden
    dobles = sql("""
        SELECT cik, count(DISTINCT source_kind) FROM parsed.facts
         GROUP BY cik HAVING count(DISTINCT source_kind) > 1 ORDER BY cik""")
    chk("6.3 · hay emisores con doble representacion (inline + instancia)",
        len(dobles) > 0, f"{[d[0] for d in dobles]}", critico=False)

    # 12 · n_fuentes refleja la deduplicacion
    nf = sql("SELECT n_fuentes, count(*) FROM derived.fact WHERE valid_to IS NULL "
             " GROUP BY 1 ORDER BY 1")
    chk("6.4 · derived declara cuantas fuentes colapso en cada hecho",
        all(int(r[0]) >= 1 for r in nf),
        ", ".join(f"n_fuentes={r[0]}:{int(r[1]):,}" for r in nf))

    n_ok = sum(1 for r in res if r["ok"])
    n_cri = sum(1 for r in res if not r["ok"] and r["critico"])
    print(f"\n  {n_ok}/{len(res)} controles OK · {n_cri} criticos en rojo")
    (OUT / "f054_f055_auditoria.json").write_text(
        json.dumps({"ok": ok_total, "controles": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/auditoria/f054_f055_auditoria.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
