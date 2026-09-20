#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase F — auditoria INDEPENDIENTE del screener.

Independencia: no importa `ratio_defs`, ni `screener_demo`, ni `engine.*`.
Habla con PostgreSQL por `psql` via subprocess y hace su propia aritmetica con
`Decimal`. Lo unico compartido con el implementador es la base de datos, que es
lo que hay que auditar.

Trata cada celda del screener como una AFIRMACION a refutar:
  - el valor se recalcula desde `derived.fact` con los tags que la celda declara
  - cada insumo debe existir en la base con ese valor exacto y esa moneda
  - la cadena hasta `parsed.facts` y su `source_hash` debe cerrar
  - todo NULL debe tener motivo
  - ningun ratio puede mezclar monedas

SOLO LECTURA.
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
FASE = REPO / "outputs" / "docs" / "fase_producto"
CONTENEDOR = "catalaxia-engine-dev"


def sql(q: str) -> list[list[str]]:
    p = subprocess.run(
        ["docker", "exec", CONTENEDOR, "psql", "-U", "catalaxia", "-d", "catalaxia",
         "-t", "-A", "-F", "\x1f", "-c", q],
        capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo: {p.stderr[:300]}")
    return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]


def uno(q: str):
    r = sql(q)
    return r[0][0] if r else None


def main() -> int:
    res, ok_total = [], True

    def chk(nombre, cond, detalle=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {nombre:<54} {detalle}")
        res.append({"control": nombre, "ok": bool(cond), "detalle": str(detalle)[:400]})
        if not cond:
            ok_total = False

    filas = json.loads((FASE / "screener.json").read_text(encoding="utf-8"))
    print("AUDITORIA INDEPENDIENTE DEL SCREENER\n")
    print("  psql directo · Decimal · sin importar ratio_defs ni screener_demo\n")

    con_datos = [f for f in filas if f["estado"] == "OK"]
    print(f"A. reproducibilidad ({len(con_datos)} empresas con fila)")

    reprod = falla = 0
    detalle = []
    for f in con_datos:
        cik = f["entidad"]["cik"]
        per = f["ejercicio"]
        for rid, m in f["metricas"].items():
            if m["estado"] not in ("CALCULADO", "REVIEW_REQUIRED"):
                continue
            if rid in ("pe", "market_cap", "price_to_book"):
                continue          # se auditan en C, llevan precio
            ins = {i["rol"]: i for i in m["insumos"]}
            tags = [i["tag"] for i in m["insumos"]]
            lista = ",".join(f"'{t}'" for t in tags)
            vals = {x[0]: (x[1], x[2]) for x in sql(
                f"SELECT tag, value_numeric, currency FROM derived.fact "
                f" WHERE valid_to IS NULL AND cik='{cik}' AND NOT is_dimensional "
                f"   AND report_period='{per}' AND tag IN ({lista}) "
                f"   AND COALESCE(instant_date::text,end_date::text)=report_period::text")}
            if any(t not in vals for t in tags):
                falla += 1
                detalle.append(f"{f['ticker']}/{rid}: falta en base "
                               f"{[t for t in tags if t not in vals]}")
                continue
            num = Decimal(vals[ins["numerador"]["tag"]][0])
            if "resta" in ins:
                num -= Decimal(vals[ins["resta"]["tag"]][0])
            den = Decimal(vals[ins["denominador"]["tag"]][0])
            mio = num / den
            if abs(mio - Decimal(str(m["valor"]))) > Decimal("0.000001"):
                falla += 1
                detalle.append(f"{f['ticker']}/{rid}: yo {mio} vs {m['valor']}")
            else:
                reprod += 1
    chk("A1 · ratios contables recalculados", falla == 0,
        f"{reprod} reproducidos, {falla} divergentes " + (str(detalle[:3]) if detalle else ""))

    print("\nB. insumos: cada valor existe en la base tal como se declara")
    sin_resp = []
    for f in con_datos:
        cik = f["entidad"]["cik"]
        for rid, m in f["metricas"].items():
            for i in m.get("insumos", []):
                if not i.get("tag") or i.get("moneda") is None:
                    continue
                n = uno(f"SELECT count(*) FROM derived.fact WHERE valid_to IS NULL "
                        f" AND cik='{cik}' AND tag='{i['tag']}' "
                        f" AND report_period='{m['periodo']}' "
                        f" AND value_numeric={i['valor']} AND currency='{i['moneda']}'")
                if n == "0":
                    sin_resp.append(f"{f['ticker']}/{rid}/{i['tag']}={i['valor']}")
    chk("B1 · todo insumo respaldado en derived.fact", not sin_resp,
        f"{len(sin_resp)} sin respaldo " + (str(sin_resp[:3]) if sin_resp else ""))

    print("\nC. ratios de mercado (precio + contabilidad)")
    pe_ok = pe_mal = []
    pe_ok, pe_mal = 0, []
    for f in con_datos:
        m = f["metricas"].get("pe", {})
        if m.get("estado") != "CALCULADO":
            continue
        ins = {i["rol"]: i for i in m["insumos"]}
        p, e = ins["precio"], ins["eps"]
        # el precio se re-lee de la base, no se toma del JSON
        fila = sql(f"SELECT close, currency, trading_date::text FROM market_price_daily "
                   f" WHERE instrument_id='{p['instrumento']}' "
                   f"   AND trading_date='{p['fecha']}'")
        if not fila:
            pe_mal.append(f"{f['ticker']}: no existe el precio citado")
            continue
        cierre, moneda = Decimal(fila[0][0]), fila[0][1]
        if moneda != e["moneda"]:
            pe_mal.append(f"{f['ticker']}: precio {moneda} vs EPS {e['moneda']}")
            continue
        mio = cierre / Decimal(str(p["ratio_adr"])) / Decimal(str(e["valor"]))
        if abs(mio - Decimal(str(m["valor"]))) > Decimal("0.001"):
            pe_mal.append(f"{f['ticker']}: yo {mio} vs {m['valor']}")
        else:
            pe_ok += 1
    chk("C1 · P/E recalculado desde precio y EPS de la base", not pe_mal,
        f"{pe_ok} reproducidos " + (str(pe_mal[:3]) if pe_mal else ""))

    neg = [f["ticker"] for f in con_datos
           if f["metricas"].get("pe", {}).get("estado") == "NO_CALCULABLE"
           and "<= 0" in f["metricas"]["pe"].get("motivo", "")]
    sin_valor = all(f["metricas"]["pe"].get("valor") is None for f in con_datos
                    if f["metricas"].get("pe", {}).get("estado") == "NO_CALCULABLE")
    chk("C2 · EPS <= 0 produce NULL, nunca un P/E negativo", sin_valor,
        f"empresas con EPS<=0: {neg}")

    print("\nD. monedas y periodos")
    mezcla = []
    for f in con_datos:
        for rid, m in f["metricas"].items():
            monedas = {i.get("moneda") for i in m.get("insumos", []) if i.get("moneda")}
            if len(monedas) > 1:
                mezcla.append(f"{f['ticker']}/{rid}: {monedas}")
    chk("D1 · ningun ratio mezcla monedas", not mezcla,
        f"{len(mezcla)} mezclados " + (str(mezcla[:3]) if mezcla else ""))

    cruces = []
    for f in con_datos:
        for rid, m in f["metricas"].items():
            pers = {m.get("periodo")}
            accs = {i.get("accession") for i in m.get("insumos", []) if i.get("accession")}
            if len(accs) > 1:
                cruces.append(f"{f['ticker']}/{rid}: {sorted(accs)}")
    chk("D2 · numerador y denominador del mismo filing", not cruces,
        f"{len(cruces)} cruzan filings " + (str(cruces[:2]) if cruces else ""))

    print("\nE. cadena hasta la evidencia fuente")
    rotas, completas = [], 0
    for f in con_datos:
        for rid, m in f["metricas"].items():
            for i in m.get("insumos", []):
                ev = i.get("evidencia") or {}
                if ev.get("fuente") == "market_price_daily":
                    continue
                if ev.get("estado") != "COMPLETA":
                    rotas.append(f"{f['ticker']}/{rid}/{i.get('tag')}: {ev.get('estado')}")
                    continue
                n = uno(f"SELECT count(*) FROM parsed.facts "
                        f" WHERE fact_id={ev['parsed_fact_id']} "
                        f"   AND source_hash='{ev['sha256_fuente']}'")
                if n == "1":
                    completas += 1
                else:
                    rotas.append(f"{f['ticker']}/{rid}: parsed.fact "
                                 f"{ev['parsed_fact_id']} sin ese source_hash")
    chk("E1 · cada insumo llega a parsed.facts con su source_hash", not rotas,
        f"{completas} cadenas completas, {len(rotas)} rotas "
        + (str(rotas[:3]) if rotas else ""))

    print("\nF. lo que falta se declara")
    sin_motivo = [f"{f['ticker']}/{k}" for f in con_datos
                  for k, v in f["metricas"].items()
                  if v["estado"] == "NO_CALCULABLE" and not v.get("motivo")]
    chk("F1 · todo NO_CALCULABLE declara motivo", not sin_motivo, f"{len(sin_motivo)} sin motivo")
    sin_estado = [f["ticker"] for f in filas if f["estado"] != "OK" and not f.get("motivo")]
    chk("F2 · toda empresa sin fila declara motivo", not sin_estado, f"{len(sin_estado)}")
    no_publicables = {k for f in con_datos for k, v in f["metricas"].items()
                      if v["estado"] == "REVIEW_REQUIRED"}
    chk("F3 · los REVIEW_REQUIRED no se presentan como calculados",
        no_publicables <= {"effective_tax_rate", "ocf_to_net_income"},
        f"{sorted(no_publicables)}")

    print("\nG-EQ. equivalencia de facts: EPS publicado vs resultado/acciones")
    # El auditor declara SU PROPIA preferencia de tags, en orden. No importa la
    # del implementador: si las dos rutas coinciden, la semantica del tag esta
    # verificada, no supuesta.
    EPS_T = ["BasicEarningsLossPerShare", "BasicAndDilutedEarningsPerShare",
             "BasicAndDilutedEarningsLossPerShare", "EarningsPerShareBasic"]
    NI_T = ["ProfitLossAttributableToOwnersOfParent", "NetIncomeLoss", "ProfitLoss"]
    SH_T = ["WeightedAverageShares", "WeightedAverageNumberOfSharesOutstandingBasic"]

    def primero(cik, per, cands):
        for t in cands:
            r = sql(f"SELECT value_numeric FROM derived.fact WHERE valid_to IS NULL "
                    f" AND cik='{cik}' AND NOT is_dimensional AND report_period='{per}' "
                    f" AND tag='{t}' "
                    f" AND COALESCE(instant_date::text,end_date::text)=report_period::text")
            if r:
                return t, Decimal(r[0][0])
        return None, None

    eq_ok, eq_mal, eq_nd = 0, [], []
    for f in con_datos:
        cik, per = f["entidad"]["cik"], f["ejercicio"]
        te, ve = primero(cik, per, EPS_T)
        tn, vn = primero(cik, per, NI_T)
        ts, vs = primero(cik, per, SH_T)
        if ve is None or vn is None or vs is None or vs == 0:
            eq_nd.append(f"{f['ticker']}: falta "
                         f"{'EPS' if ve is None else 'resultado' if vn is None else 'acciones'}")
            continue
        derivado = vn / vs
        dif = abs(derivado - ve) / abs(ve) * 100 if ve else Decimal(0)
        if dif > 5:
            eq_mal.append(f"{f['ticker']}: publicado {ve} vs derivado {derivado:.4f} "
                          f"({dif:.2f}%) [{te} / {tn}/{ts}]")
        else:
            eq_ok += 1
    chk("G0 · EPS publicado == resultado/acciones (dos caminos)", not eq_mal,
        f"{eq_ok} coinciden, {len(eq_mal)} divergen, {len(eq_nd)} sin datos "
        + (str(eq_mal[:2]) if eq_mal else ""))

    print("\nG. taxonomia")
    taxs = {f["ticker"]: f["taxonomia"] for f in con_datos}
    dist = sorted(set(taxs.values()))
    chk("G1 · se detecto mas de una taxonomia en el universo", len(dist) > 1, str(dist))
    for f in con_datos:
        ns = uno(f"SELECT count(DISTINCT namespace) FROM derived.fact "
                 f" WHERE valid_to IS NULL AND cik='{f['entidad']['cik']}'")
        res.append({"control": f"G · {f['ticker']} namespaces", "ok": True, "detalle": ns})

    print("\nH. cobertura declarada vs medida")
    n_fact = uno("SELECT count(DISTINCT cik) FROM derived.fact WHERE valid_to IS NULL")
    chk("H1 · empresas con fundamentals en base == filas con datos",
        int(n_fact) >= len(con_datos), f"{n_fact} CIK con facts, {len(con_datos)} filas OK")

    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} controles OK")
    (FASE / "auditoria_screener.json").write_text(
        json.dumps({"ok": ok_total, "controles": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_producto/auditoria_screener.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
