#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Homologacion INDEPENDIENTE del vertical slice. Solo lectura.

    python scripts/engine/homologacion_slice.py

INDEPENDENCIA
No importa `ratio_engine`, ni `ratio_api`, ni `ratio_defs`, ni `ratio_inputs`,
ni `engine.*`. Habla con PostgreSQL por `psql` dentro del contenedor y rehace
cada cuenta con `Decimal` a partir de los insumos que la fila persistio.

Si el motor y este auditor comparten una funcion, comparten tambien su error.
Por eso las formulas estan escritas de nuevo aca, desde el contrato, y las
consultas son propias.

QUE VERIFICA
  A  EPS      el valor publicado es exactamente el fact reportado
  B  P/B      (close / ratio_adr) / (patrimonio / acciones)
  C  EV/Sales (market_cap + deuda - caja) / ingresos
  D  provenance: cada source_fact_id existe, es del mismo emisor y su hash
     figura en la fila
  E  cross-entity: ningun insumo pertenece a otro emisor
  F  contrato de la celda: ventana, moneda, version de formula, estado
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 40

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "fase_ratios"
CONT = "catalaxia-engine-dev"
SEP = "\x1f"

# Tolerancia declarada. El motor redondea a 6 decimales al persistir; el
# auditor no redondea. La diferencia esperada es de ese orden.
TOL_RELATIVA = Decimal("1e-6")


def psql(sql: str) -> list[list[str]]:
    p = subprocess.run(
        ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "catalaxia",
         "-t", "-A", "-F", SEP, "-c", sql],
        capture_output=True, text=True, encoding="utf-8", timeout=90)
    if p.returncode != 0:
        raise SystemExit(f"psql fallo: {(p.stderr or '')[:300]}")
    return [ln.split(SEP) for ln in p.stdout.splitlines() if ln.strip()]


def d(x) -> Decimal | None:
    return None if x in (None, "", "\\N") else Decimal(str(x))


def cerca(a: Decimal, b: Decimal) -> tuple[bool, Decimal]:
    if a is None or b is None:
        return False, Decimal(0)
    if b == 0:
        return a == 0, abs(a)
    rel = abs(a - b) / abs(b)
    return rel <= TOL_RELATIVA, rel


def insumo(fila_json: dict, rol: str, campo: str = "valor"):
    for i in fila_json:
        if i.get("rol") == rol:
            return i.get(campo)
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total, ev = [], True, {}
    peor = Decimal(0)

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {n:<62} {det}")
        res.append({"control": n, "ok": bool(cond), "detalle": str(det)[:300]})
        if not cond:
            ok_total = False

    print("HOMOLOGACION INDEPENDIENTE — vertical slice\n")
    print("  psql directo · Decimal propio · sin importar ratio_engine\n")

    # ── el universo persistido ──────────────────────────────────────────
    filas = psql("""
        SELECT r.cik, r.canonical_id, coalesce(r.value::text,''), r.status,
               r.period_end::text, r.period_window, coalesce(r.currency,''),
               r.formula_version, r.entity_key, r.inputs::text
          FROM derived.ratio r WHERE r.valid_to IS NULL
         ORDER BY r.cik, r.canonical_id""")
    print(f"  filas vigentes en derived.ratio: {len(filas)}\n")
    ev["filas"] = len(filas)

    # ══ A/B/C · las tres cuentas, rehechas ═════════════════════════════
    print("A-C. recalculo manual de cada valor publicado")
    comparados, coinciden = 0, 0
    detalle_num = []
    for cik, cid, val, status, per, win, cur, fv, ek, inp_txt in filas:
        if status != "CALCULADO":
            continue
        inp = json.loads(inp_txt)
        publicado = d(val)
        manual = None
        if cid == "eps":
            manual = d(insumo(inp, "eps"))
        elif cid == "pb":
            close = d(insumo(inp, "precio"))
            radr = d(insumo(inp, "precio", "ratio_adr")) or Decimal(1)
            pat = d(insumo(inp, "patrimonio"))
            acc = d(insumo(inp, "acciones"))
            if None not in (close, pat, acc) and acc != 0:
                manual = (close / radr) / (pat / acc)
        elif cid == "pe":
            close = d(insumo(inp, "precio"))
            radr = d(insumo(inp, "precio", "ratio_adr")) or Decimal(1)
            eps = d(insumo(inp, "eps"))
            if None not in (close, eps) and eps != 0:
                manual = (close / radr) / eps
        elif cid == "ev_sales":
            close = d(insumo(inp, "precio"))
            radr = d(insumo(inp, "precio", "ratio_adr")) or Decimal(1)
            acc = d(insumo(inp, "acciones"))
            deuda = d(insumo(inp, "deuda"))
            caja = d(insumo(inp, "efectivo"))
            ing = d(insumo(inp, "ingresos"))
            if None not in (close, acc, deuda, caja, ing) and ing != 0:
                mcap = (close / radr) * acc
                manual = (mcap + deuda - caja) / ing
        if manual is None:
            chk(f"{cik} {cid}: se pudo rehacer la cuenta", False,
                "faltan insumos en la fila persistida")
            continue
        comparados += 1
        ok, rel = cerca(publicado, manual)
        coinciden += ok
        peor = max(peor, rel)
        detalle_num.append({"cik": cik, "ratio": cid, "publicado": str(publicado),
                            "manual": str(manual.quantize(Decimal("1.000000000000"))),
                            "dif_relativa": str(rel), "ok": ok})
        if not ok:
            chk(f"{cik} {cid}", False, f"publicado={publicado} manual={manual} rel={rel}")
    chk(f"A-C · los {comparados} valores publicados se reproducen a mano",
        comparados > 0 and coinciden == comparados,
        f"{coinciden}/{comparados} · peor desvio relativo {peor:.2e} "
        f"(tolerancia {TOL_RELATIVA})")
    ev["recalculo"] = detalle_num
    ev["peor_desvio_relativo"] = str(peor)

    # ══ D · provenance ═════════════════════════════════════════════════
    print("\nD. provenance de cada insumo contable")
    rotos = psql("""
        SELECT count(*) FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
         WHERE r.valid_to IS NULL AND r.status='CALCULADO'
           AND i->>'rol' NOT IN ('precio','derivado')
           AND (i->'evidencia'->>'estado' <> 'COMPLETA'
             OR i->'evidencia'->'source_hashes' IS NULL
             OR jsonb_array_length(i->'evidencia'->'source_fact_ids') = 0)""")
    chk("D1 · todo insumo contable de un CALCULADO cita RAW con hash",
        rotos[0][0] == "0", f"{rotos[0][0]} sin cadena")

    huerf = psql("""
        SELECT count(*) FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
          CROSS JOIN LATERAL jsonb_array_elements_text(i->'evidencia'->'source_fact_ids') s
          LEFT JOIN parsed.facts p ON p.fact_id = s::bigint
         WHERE r.valid_to IS NULL AND p.fact_id IS NULL""")
    chk("D2 · todo source_fact_id existe en parsed.facts", huerf[0][0] == "0",
        f"{huerf[0][0]} huerfanos")

    hash_malo = psql("""
        SELECT count(*) FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
          CROSS JOIN LATERAL jsonb_array_elements_text(i->'evidencia'->'source_fact_ids') s
          JOIN parsed.facts p ON p.fact_id = s::bigint
         WHERE r.valid_to IS NULL
           AND NOT (i->'evidencia'->'source_hashes') ? p.source_hash""")
    chk("D3 · el hash citado es el que parsed.facts guarda", hash_malo[0][0] == "0",
        f"{hash_malo[0][0]} discrepan")

    # ══ E · cross-entity ═══════════════════════════════════════════════
    print("\nE. aislamiento entre emisores")
    ajeno = psql("""
        SELECT count(*) FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
          CROSS JOIN LATERAL jsonb_array_elements_text(i->'evidencia'->'source_fact_ids') s
          JOIN parsed.facts p ON p.fact_id = s::bigint
         WHERE r.valid_to IS NULL AND p.cik <> r.cik""")
    chk("E1 · ningun insumo proviene de otro emisor", ajeno[0][0] == "0",
        f"{ajeno[0][0]} ajenos")
    ek_malo = psql("""
        SELECT count(*) FROM derived.ratio r
          JOIN identity_v1.identifier i
            ON i.id_type='CIK' AND i.id_value=r.cik AND i.valid_to IS NULL
         WHERE r.valid_to IS NULL AND r.entity_key <> i.entity_key""")
    chk("E2 · el entity_key de cada fila es el que da identity_v1",
        ek_malo[0][0] == "0", f"{ek_malo[0][0]} discrepan")
    f061 = psql("""SELECT count(*) FROM derived.v_fact_pertenencia
                    WHERE puntero_huerfano OR cik_ajeno OR filing_ajeno OR concepto_ajeno""")
    chk("E3 · F-061 sobre los punteros de derived.fact", f061[0][0] == "0",
        f"{f061[0][0]} violaciones")

    # ══ F · contrato de la celda ═══════════════════════════════════════
    print("\nF. contrato de la celda")
    for etq, sql in (
        ("F1 · ninguna ventana dice TTM (el motor no lo soporta)",
         "SELECT count(*) FROM derived.ratio WHERE valid_to IS NULL AND period_window='TTM'"),
        ("F2 · ningun CALCULADO sin moneda ni sin insumos",
         "SELECT count(*) FROM derived.ratio WHERE valid_to IS NULL AND status='CALCULADO' "
         " AND (currency IS NULL OR jsonb_array_length(inputs)=0)"),
        ("F3 · ningun NOT_CALCULABLE con valor o sin motivo",
         "SELECT count(*) FROM derived.ratio WHERE valid_to IS NULL "
         " AND status<>'CALCULADO' AND (value IS NOT NULL OR motivo IS NULL)"),
        ("F4 · ninguna identidad vigente duplicada",
         "SELECT count(*) FROM (SELECT entity_key, canonical_id, period_end, "
         " period_window, denominator_basis, coalesce(currency,'-') FROM derived.ratio "
         " WHERE valid_to IS NULL GROUP BY 1,2,3,4,5,6 HAVING count(*)>1) x"),
        ("F5 · ninguna corrida colgada",
         "SELECT count(*) FROM engine.runs WHERE status='RUNNING'"),
        ("F6 · toda fila cita una corrida real",
         "SELECT count(*) FROM derived.ratio r WHERE NOT EXISTS "
         " (SELECT 1 FROM engine.runs g WHERE g.run_id=r.run_id)"),
    ):
        n = psql(sql)[0][0]
        chk(etq, n == "0", n)

    versiones = psql("""SELECT canonical_id||'='||formula_version||' ('||period_window||')'
                          FROM derived.ratio WHERE valid_to IS NULL
                         GROUP BY 1 ORDER BY 1""")
    print("\n  versiones de formula vigentes:")
    for v in versiones:
        print(f"    {v[0]}")
    ev["formula_versions"] = [v[0] for v in versiones]

    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} controles OK · peor desvio {peor:.2e}")
    ev["controles"] = res
    ev["ok"] = ok_total
    (OUT / "HOMOLOGACION_SLICE.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_ratios/HOMOLOGACION_SLICE.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
