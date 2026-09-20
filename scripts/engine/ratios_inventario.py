#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventario y calculo de ratios sobre datos REALES — fases B, C y E.

No inventa valores. Si un input falta, el ratio queda NO_CALCULABLE con el
motivo. Cada resultado conserva sus inputs y su provenance (accession, tag,
periodo, unidad).

SOLO LECTURA. No escribe en la base.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

sys.path.insert(0, str(REPO / "scripts" / "engine"))
from ratio_defs import CONCEPTOS, RATIOS  # noqa: E402
from ratio_inputs import sql_insumos  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_ratios"

# Muestra deliberada del encargo (ticker_canonico del legacy)
MUESTRA = ["CEPU", "YPFD", "TGSU2", "GGAL", "BMA", "AAPL", "MSFT", "NVDA"]

# Definicion de cada ratio: que facts necesita, por CONCEPTO (no por tag).
# Construido desde `ratio_defs.py`, la unica fuente de verdad de la cadena de
# fallback taxonomia-a-taxonomia (ifrs-full <-> us-gaap). Antes este dict
# declaraba sus propias listas de tags solo-IFRS, duplicadas y desincronizadas
# de `ratio_defs.py`: un emisor US-GAAP con los facts completos en la base
# (AssetsCurrent, StockholdersEquity, NetIncomeLoss...) daba 0/9 ratios
# calculados porque ninguno de esos tags estaba en la lista local. Ver F-056.
FUNDAMENTALES = {
    rid: {
        "formula": f"{num_c}{f' - {resta_c}' if resta_c else ''} / {den_c}",
        "num": CONCEPTOS[num_c],
        **({"num_resta": CONCEPTOS[resta_c]} if resta_c else {}),
        "den": CONCEPTOS[den_c],
        "unidad": unidad,
    }
    for rid, (num_c, resta_c, den_c, unidad, _publicable) in RATIOS.items()
}


def facts_del_periodo(conn, cik: str) -> dict:
    """Un fact por (tag, periodo): el del filing cuyo report_period == instant/end.

    Regla de seleccion declarada: cada 20-F trae 3 anios comparativos. Se toma
    el anio PRINCIPAL del filing (report_period == fecha del hecho), que es el
    auditado en ese documento. Los comparativos se descartan porque el mismo
    hecho aparece en 3 filings y hay que elegir uno de forma determinista.
    """
    # F-061: WHERE canonico en `ratio_inputs`, con la guarda de pertenencia.
    filas = conn.execute(text(
        sql_insumos(
            "d.tag, d.report_period, d.currency, d.value_numeric, d.accession_number, "
            "d.unit_measure, COALESCE(d.instant_date::text, d.end_date::text) AS fecha, "
            "d.period_kind, d.filing_date",
            extra=" ORDER BY d.report_period DESC, d.tag")), {"c": cik}).mappings().all()
    out = {}
    for f in filas:
        out.setdefault(f["report_period"], {})[f["tag"]] = dict(f)
    return out


def elegir(disponibles: dict, candidatos: list[str]):
    """Primer candidato presente. El orden de la lista ES la regla de fallback."""
    for tag in candidatos:
        if tag in disponibles:
            return tag, disponibles[tag]
    return None, None


def calcular(conn, cik: str, nombre: str) -> list[dict]:
    porper = facts_del_periodo(conn, cik)
    res = []
    for periodo, disp in sorted(porper.items(), reverse=True):
        for rid, d in FUNDAMENTALES.items():
            tn, fn = elegir(disp, d["num"])
            td, fd = elegir(disp, d["den"])
            r = {"entidad": nombre, "cik": cik, "periodo": str(periodo), "ratio": rid,
                 "formula": d["formula"], "unidad": d["unidad"]}
            if fn is None or fd is None:
                falta = d["num"] if fn is None else d["den"]
                r.update(estado="NO_CALCULABLE", valor=None,
                         motivo=f"falta {'numerador' if fn is None else 'denominador'}: "
                                f"ninguno de {falta} presente en {periodo}")
                res.append(r); continue
            if fn["currency"] != fd["currency"]:
                r.update(estado="NO_CALCULABLE", valor=None,
                         motivo=f"monedas distintas: {tn}={fn['currency']} vs "
                                f"{td}={fd['currency']}. Un ratio no mezcla monedas")
                res.append(r); continue
            if fd["value_numeric"] == 0:
                r.update(estado="NO_CALCULABLE", valor=None,
                         motivo=f"denominador {td} = 0")
                res.append(r); continue
            # numerador compuesto (p.ej. quick_ratio resta las existencias)
            num_valor, resta_tag = float(fn["value_numeric"]), None
            if d.get("num_resta"):
                tr, fr = elegir(disp, d["num_resta"])
                if fr is None:
                    r.update(estado="NO_CALCULABLE", valor=None,
                             motivo=f"falta el termino a restar: ninguno de "
                                    f"{d['num_resta']} presente en {periodo}")
                    res.append(r); continue
                if fr["currency"] != fn["currency"]:
                    r.update(estado="NO_CALCULABLE", valor=None,
                             motivo=f"monedas distintas dentro del numerador: "
                                    f"{tn}={fn['currency']} vs {tr}={fr['currency']}")
                    res.append(r); continue
                num_valor -= float(fr["value_numeric"])
                resta_tag = tr
            valor = num_valor / float(fd["value_numeric"])
            r.update(estado="CALCULADO", valor=round(valor, 6),
                     numerador={"tag": tn, "valor": float(fn["value_numeric"]),
                                "resta_tag": resta_tag, "valor_neto": num_valor,
                                "moneda": fn["currency"], "accession": fn["accession_number"]},
                     denominador={"tag": td, "valor": float(fd["value_numeric"]),
                                  "moneda": fd["currency"], "accession": fd["accession_number"]},
                     provenance={"fuente": "SEC XBRL via derived.fact",
                                 "accession_num": fn["accession_number"],
                                 "accession_den": fd["accession_number"],
                                 "filing_date": str(fn["filing_date"]),
                                 "moneda": fn["currency"]})
            res.append(r)
    return res


def cobertura_mercado(conn) -> list[dict]:
    filas = conn.execute(text("""
        SELECT i.ticker_canonico, i.instrument_id, i.venue_ticker, i.exchange,
               count(p.*) AS n, max(p.trading_date)::text AS ultimo,
               min(p.trading_date)::text AS primero
          FROM market_instruments i
          LEFT JOIN market_price_daily p ON p.instrument_id = i.instrument_id
         WHERE i.ticker_canonico = ANY(:m)
         GROUP BY 1,2,3,4 ORDER BY 1, 4"""), {"m": MUESTRA}).mappings().all()
    return [dict(f) for f in filas]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)

    with eng.connect() as conn:
        # --- universo con fundamentals -----------------------------------
        emisores = conn.execute(text(
            "SELECT DISTINCT d.cik, (SELECT preferred_name FROM identity_v1.v_entity_resolution v "
            "  WHERE v.cik=d.cik) n FROM derived.fact d WHERE d.valid_to IS NULL")).all()
        print("INVENTARIO DE RATIOS — datos reales\n")
        print(f"  emisores con fundamentals en derived.fact: {len(emisores)}")
        for cik, n in emisores:
            print(f"    {cik}  {n}")

        todos = []
        for cik, nombre in emisores:
            todos += calcular(conn, cik, nombre or cik)

        # --- resultados ----------------------------------------------------
        calc = [r for r in todos if r["estado"] == "CALCULADO"]
        noc = [r for r in todos if r["estado"] == "NO_CALCULABLE"]
        print(f"\n  ratios evaluados: {len(todos)}  ·  CALCULADO {len(calc)}  ·  NO_CALCULABLE {len(noc)}")

        print("\n  cobertura por ratio (sobre los emisores con fundamentals)")
        print(f"    {'ratio':<18} {'calc':>5} {'n/c':>5}  periodos con valor")
        for rid in FUNDAMENTALES:
            c = [r for r in calc if r["ratio"] == rid]
            n = [r for r in noc if r["ratio"] == rid]
            per = sorted({r["periodo"][:4] for r in c}, reverse=True)
            print(f"    {rid:<18} {len(c):>5} {len(n):>5}  {','.join(per[:9]) or '-'}")

        print("\n  ultimo periodo con valor, por ratio (YPF 2025)")
        for r in sorted([x for x in calc if x["periodo"].startswith("2025")],
                        key=lambda x: x["ratio"]):
            num = r["numerador"]["tag"]
            if r["numerador"].get("resta_tag"):
                num = f"({num}-{r['numerador']['resta_tag']})"
            print(f"    {r['ratio']:<20} {r['valor']:>10.4f} {r['unidad']:<9} "
                  f"{num}/{r['denominador']['tag']} "
                  f"[{r['numerador']['moneda']}] {r['provenance']['accession_num']}")

        if noc:
            print("\n  motivos de NO_CALCULABLE (primeros 5)")
            vistos = set()
            for r in noc:
                k = r["motivo"][:60]
                if k in vistos:
                    continue
                vistos.add(k)
                print(f"    {r['ratio']:<18} {r['periodo']}  {r['motivo'][:95]}")
                if len(vistos) >= 5:
                    break

        # --- mercado --------------------------------------------------------
        mk = cobertura_mercado(conn)
        print(f"\n  cobertura de MERCADO en la muestra deliberada")
        print(f"    {'ticker':<8} {'iid':<5} {'venue':<7} {'exch':<6} {'precios':>8}  rango")
        for f in mk:
            print(f"    {f['ticker_canonico']:<8} {f['instrument_id']:<5} "
                  f"{str(f['venue_ticker']):<7} {str(f['exchange'] or '-'):<6} {f['n']:>8}  "
                  f"{f['primero']} .. {f['ultimo']}")
        faltan = [t for t in MUESTRA if t not in {f["ticker_canonico"] for f in mk}]
        if faltan:
            print(f"    sin instrumento: {faltan}")

    (OUT / "ratios_calculados.json").write_text(
        json.dumps({"ratios": todos, "mercado": mk}, indent=2, ensure_ascii=False,
                   default=str), encoding="utf-8")
    print(f"\n  -> outputs/docs/fase_ratios/ratios_calculados.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
