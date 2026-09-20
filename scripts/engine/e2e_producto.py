#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flujo E2E del producto sobre la muestra deliberada.

  EMPRESA -> IDENTITY -> SEC/XBRL -> MARKET -> METRICAS -> RATIOS -> SCREENER -> PROVENANCE

Para cada empresa se recorre la cadena entera y se registra EN QUE ESLABON se
corta. Un eslabon roto no se rellena ni se estima: la fila del screener queda
con NULL y el motivo.

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
MUESTRA = ["CEPU", "YPFD", "TGSU2", "GGAL", "BMA", "AAPL", "MSFT", "NVDA"]

# Construido desde `ratio_defs.py` (fuente unica de la cadena de fallback
# ifrs-full <-> us-gaap). Antes este dict tenia sus propias listas solo-IFRS:
# un emisor US-GAAP con los facts completos daba 0/9 porque ninguno de esos
# tags coincidia. No cubre el numerador compuesto (quick_ratio); eso queda en
# `ratios_inventario.py`, que es donde se declara la resta. Ver F-056.
FUNDAMENTALES = {
    rid: (CONCEPTOS[num_c], CONCEPTOS[den_c], unidad)
    for rid, (num_c, resta_c, den_c, unidad, _publicable) in RATIOS.items()
    if resta_c is None
}
EPS_TAGS = CONCEPTOS["eps_basico"]

ESLABONES = ["EMPRESA", "IDENTITY", "SEC_XBRL", "MARKET", "METRICAS", "RATIOS",
             "SCREENER", "PROVENANCE"]


def q(conn, sql, **kw):
    return conn.execute(text(sql), kw).mappings().all()


def recorrer(conn, ticker: str) -> dict:
    r = {"ticker": ticker, "cadena": {}, "ratios": {}, "corte": None}

    def marca(eslabon, ok, detalle):
        r["cadena"][eslabon] = {"ok": ok, "detalle": detalle}
        if not ok and r["corte"] is None:
            r["corte"] = eslabon
        return ok

    # 1 EMPRESA ------------------------------------------------------------
    inst = q(conn, """
        SELECT instrument_id, exchange, currency, instrument_type, venue_ticker
          FROM market_instruments WHERE ticker_canonico=:t ORDER BY instrument_id""", t=ticker)
    if not marca("EMPRESA", bool(inst),
                 f"{len(inst)} instrumento(s): "
                 + ", ".join(f"{i['instrument_id']}@{i['exchange'] or '?'}" for i in inst)):
        return r

    # 2 IDENTITY -----------------------------------------------------------
    ident = q(conn, """
        SELECT DISTINCT e.entity_key, e.preferred_name,
               (SELECT i.id_value FROM identity_v1.identifier i
                 WHERE i.entity_key=e.entity_key AND i.id_type='CIK' AND i.valid_to IS NULL
                 LIMIT 1) AS cik,
               (SELECT i.id_value FROM identity_v1.identifier i
                 WHERE i.entity_key=e.entity_key AND i.id_type='CUIT' AND i.valid_to IS NULL
                 LIMIT 1) AS cuit,
               (SELECT a.status::text FROM identity_v1.identifier i
                  JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
                 WHERE i.entity_key=e.entity_key AND i.id_type='CUIT' AND i.valid_to IS NULL
                 LIMIT 1) AS cuit_status
          FROM identity_v1.instrument ii
          JOIN identity_v1.entity e ON e.entity_key=ii.entity_key
         WHERE ii.instrument_key = ANY(:ks) AND ii.valid_to IS NULL""",
        ks=[f"MKT:{i['instrument_id']}" for i in inst])
    if not marca("IDENTITY", len(ident) == 1,
                 (f"{ident[0]['preferred_name']} · {ident[0]['entity_key']} · "
                  f"CIK={ident[0]['cik']} CUIT={ident[0]['cuit']}({ident[0]['cuit_status']})")
                 if len(ident) == 1 else
                 (f"{len(ident)} entidades para los instrumentos "
                  f"{[i['instrument_id'] for i in inst]}: sin enlace en identity_v1.instrument"
                  if not ident else f"AMBIGUO: {len(ident)} entidades")):
        return r
    ent = dict(ident[0])
    r["entidad"] = ent

    # 3 SEC / XBRL ---------------------------------------------------------
    cik = ent["cik"]
    # F-061: WHERE canonico en `ratio_inputs`, con la guarda de pertenencia.
    facts = q(conn, sql_insumos(
        "d.tag, d.report_period::text AS per, d.currency, d.value_numeric, "
        "d.accession_number, d.filing_date::text AS fdate"),
        c=cik) if cik else []
    if not marca("SEC_XBRL", bool(facts),
                 f"{len(facts)} facts normalizados"
                 + (f" para CIK {cik}" if cik else " (la entidad no tiene CIK)")
                 + ("" if facts else
                    " — la entidad existe y el CIK esta en identity_v1, pero S02/S03/S04 "
                    "nunca ingirieron sus filings")):
        return r

    porper = {}
    for f in facts:
        porper.setdefault(f["per"], {})[f["tag"]] = dict(f)
    ultimo = max(porper)
    disp = porper[ultimo]
    r["ejercicio"] = ultimo

    # 4 MARKET -------------------------------------------------------------
    precios = q(conn, """
        SELECT p.instrument_id, p.trading_date::text AS d, p.close, p.currency, p.exchange
          FROM market_price_daily p
          JOIN (SELECT instrument_id, max(trading_date) md FROM market_price_daily
                 WHERE instrument_id = ANY(:ids) GROUP BY 1) u
            ON u.instrument_id=p.instrument_id AND u.md=p.trading_date
         WHERE p.instrument_id = ANY(:ids)""",
        ids=[str(i["instrument_id"]) for i in inst])
    if not marca("MARKET", bool(precios),
                 ", ".join(f"{p['instrument_id']}@{p['exchange']}={p['close']} "
                           f"{p['currency']} ({p['d']})" for p in precios) or "sin precios"):
        return r
    r["precios"] = [dict(p) for p in precios]

    # 5 METRICAS -----------------------------------------------------------
    necesarios = {t for n, d, _ in FUNDAMENTALES.values() for t in (n + d)}
    presentes = necesarios & set(disp)
    marca("METRICAS", bool(presentes),
          f"ejercicio {ultimo}: {len(presentes)}/{len(necesarios)} tags requeridos presentes")

    # 6 RATIOS -------------------------------------------------------------
    def elegir(cands):
        for t in cands:
            if t in disp:
                return t, disp[t]
        return None, None

    calc = 0
    for rid, (num, den, uni) in FUNDAMENTALES.items():
        tn, fn = elegir(num)
        td, fd = elegir(den)
        if fn is None or fd is None:
            falta = num if fn is None else den
            r["ratios"][rid] = {"estado": "NO_CALCULABLE", "valor": None,
                                "motivo": f"ninguno de {falta} en {ultimo}"}
            continue
        if fn["currency"] != fd["currency"]:
            r["ratios"][rid] = {"estado": "NO_CALCULABLE", "valor": None,
                                "motivo": f"monedas {fn['currency']}/{fd['currency']}"}
            continue
        if float(fd["value_numeric"]) == 0:
            r["ratios"][rid] = {"estado": "NO_CALCULABLE", "valor": None,
                                "motivo": f"denominador {td}=0"}
            continue
        r["ratios"][rid] = {
            "estado": "CALCULADO", "unidad": uni,
            "valor": round(float(fn["value_numeric"]) / float(fd["value_numeric"]), 6),
            "formula": f"{tn}/{td}", "moneda": fn["currency"],
            "accession": fn["accession_number"], "filing_date": fn["fdate"]}
        calc += 1

    # P/E: precio del instrumento cuya MONEDA coincide con la del EPS
    te, fe = elegir(EPS_TAGS)
    if fe is None:
        r["ratios"]["pe"] = {"estado": "NO_CALCULABLE", "valor": None,
                             "motivo": f"sin EPS: ninguno de {EPS_TAGS} en {ultimo}"}
    else:
        p = next((x for x in precios if x["currency"] == fe["currency"]), None)
        if p is None:
            r["ratios"]["pe"] = {"estado": "NO_CALCULABLE", "valor": None,
                                 "motivo": f"EPS en {fe['currency']} y no hay precio en esa "
                                           f"moneda ({[x['currency'] for x in precios]}); "
                                           f"convertir exigiria un FX que no esta declarado"}
        elif float(fe["value_numeric"]) <= 0:
            r["ratios"]["pe"] = {"estado": "NO_CALCULABLE", "valor": None,
                                 "motivo": f"EPS={float(fe['value_numeric'])} <= 0 "
                                           f"(ejercicio con perdida)"}
        else:
            ratio_adr = q(conn, "SELECT ratio_underlying FROM identity_v1.instrument "
                                " WHERE instrument_key=:k AND valid_to IS NULL",
                          k=f"MKT:{p['instrument_id']}")
            ru = float(ratio_adr[0]["ratio_underlying"]) if ratio_adr and \
                ratio_adr[0]["ratio_underlying"] else 1.0
            # el precio es por ADR; el EPS es por accion subyacente
            r["ratios"]["pe"] = {
                "estado": "CALCULADO", "unidad": "veces",
                "valor": round(float(p["close"]) / ru / float(fe["value_numeric"]), 4),
                "formula": f"close/ratio_adr/{te}", "moneda": fe["currency"],
                "precio": float(p["close"]), "ratio_adr": ru,
                "eps": float(fe["value_numeric"]), "fecha_precio": p["d"],
                "accession": fe["accession_number"]}
            calc += 1
    marca("RATIOS", calc > 0, f"{calc}/{len(FUNDAMENTALES)+1} calculados en {ultimo}")

    # 7 SCREENER + 8 PROVENANCE -------------------------------------------
    marca("SCREENER", calc > 0, f"fila publicable con {calc} metricas")
    acc = {v.get("accession") for v in r["ratios"].values() if v.get("accession")}
    marca("PROVENANCE", bool(acc),
          f"accessions citadas: {sorted(acc)} · precio {precios[0]['d']}")
    return r


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)
    filas = []

    with eng.connect() as conn:
        print("FLUJO E2E DEL PRODUCTO — muestra deliberada\n")
        for t in MUESTRA:
            filas.append(recorrer(conn, t))

    # --- cadena ------------------------------------------------------------
    print(f"  {'ticker':<7} " + " ".join(f"{e[:9]:<10}" for e in ESLABONES))
    for f in filas:
        linea = f"  {f['ticker']:<7} "
        for e in ESLABONES:
            c = f["cadena"].get(e)
            linea += f"{('OK' if c['ok'] else 'CORTE') if c else '-':<10} "
        print(linea)

    print("\n  donde se corta cada una")
    for f in filas:
        if f["corte"]:
            print(f"  {f['ticker']:<7} {f['corte']:<10} {f['cadena'][f['corte']]['detalle'][:120]}")
        else:
            print(f"  {f['ticker']:<7} {'completa':<10} "
                  f"{sum(1 for v in f['ratios'].values() if v['estado']=='CALCULADO')} metricas")

    # --- screener ----------------------------------------------------------
    cols = list(FUNDAMENTALES) + ["pe"]
    print(f"\n  SCREENER v1 — ejercicio mas reciente por empresa\n")
    print(f"  {'ticker':<7} {'ejercicio':<11} " + " ".join(f"{c[:9]:>10}" for c in cols))
    for f in filas:
        if not f["ratios"]:
            print(f"  {f['ticker']:<7} {'-':<11} " +
                  " ".join(f"{'NULL':>10}" for _ in cols) + f"   <- {f['corte']}")
            continue
        linea = f"  {f['ticker']:<7} {f.get('ejercicio','-')[:10]:<11} "
        for c in cols:
            v = f["ratios"].get(c, {})
            linea += (f"{v['valor']:>10.4f} " if v.get("estado") == "CALCULADO"
                      else f"{'NULL':>10} ")
        print(linea)

    # --- resumen -----------------------------------------------------------
    completas = [f for f in filas if not f["corte"]]
    print(f"\n  empresas con cadena completa: {len(completas)}/{len(filas)}")
    cortes = {}
    for f in filas:
        if f["corte"]:
            cortes.setdefault(f["corte"], []).append(f["ticker"])
    for e, ts in cortes.items():
        print(f"    corte en {e:<10} {ts}")

    (OUT / "e2e_producto.json").write_text(
        json.dumps(filas, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\n  -> outputs/docs/fase_ratios/e2e_producto.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
