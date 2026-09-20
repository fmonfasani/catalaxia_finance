#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screener del universo de demostracion, con trazabilidad hasta la evidencia.

Produce, para cada empresa, la fila del screener y —para cada metrica— la
cadena completa:

    ratio -> formula -> insumos (concepto, tag, valor, moneda)
          -> derived.fact -> source_fact_ids -> parsed.facts
          -> source_file + source_hash -> filing en SEC

Ese drill-down es el entregable: permite responder "¿de donde sale este numero?"
sin salir del sistema.

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
from ratio_defs import (CONCEPTOS, RATIOS, elegir_concepto,  # noqa: E402
                        taxonomia_de)
from ratio_inputs import sql_insumos  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_producto"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

# ticker -> CIK declarado del universo de demostracion. Es una ENTRADA, no una
# resolucion: el script exige que la assertion del CIK este VERIFIED antes de
# usarlo, y lo deja registrado en `origen_identidad`.
UNIVERSO = {
    "YPFD": "0000904851", "CEPU": "0001717161", "TGSU2": "0000931427",
    "GGAL": "0001114700", "BMA": "0001347426", "AAPL": "0000320193",
    "MSFT": "0000789019", "NVDA": "0001045810",
}


def q(conn, sql, **kw):
    return conn.execute(text(sql), kw).mappings().all()


def url_filing(cik: str, acc: str) -> str:
    return f"{SEC_ARCHIVES}/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm"


def evidencia_de(conn, fact: dict) -> dict:
    """Cadena derived.fact -> parsed.facts -> archivo fuente.

    No se infiere: se sigue `source_fact_ids`, que S04 dejo escrito.
    """
    ids = fact.get("source_fact_ids") or []
    if not ids:
        return {"estado": "SIN_CADENA",
                "motivo": "el hecho derivado no cita source_fact_ids"}
    filas = q(conn, """
        SELECT fact_id, taxonomy, namespace, qname, context_id, unit_ref, measure,
               decimals, source_kind, source_file, source_path, source_hash
          FROM parsed.facts WHERE fact_id = ANY(:ids)""",
        ids=[int(i) for i in ids])
    if not filas:
        return {"estado": "ROTA", "motivo": f"source_fact_ids {ids} no existen en parsed.facts"}
    p = dict(filas[0])
    return {"estado": "COMPLETA",
            "n_fuentes": len(filas),
            "parsed_fact_id": p["fact_id"],
            "taxonomia": p["taxonomy"],
            "namespace": p["namespace"],
            "qname": p["qname"],
            "contexto": p["context_id"],
            "unidad_ref": p["unit_ref"],
            "medida": p["measure"],
            "decimales": p["decimals"],
            "archivo_fuente": p["source_file"],
            "ruta_raw": p["source_path"],
            "sha256_fuente": p["source_hash"]}


def facts_ultimo_ejercicio(conn, cik: str):
    # F-061: la seleccion la arma `ratio_inputs`, que agrega la guarda de
    # pertenencia. Aca solo se declaran las columnas.
    filas = q(conn, sql_insumos(
        "d.tag, d.report_period::text AS per, d.currency, d.value_numeric, "
        "d.accession_number, d.filing_date::text AS fdate, d.form, d.namespace, "
        "d.unit_measure, d.source_fact_ids, d.fact_key, d.period_kind"), c=cik)
    if not filas:
        return None, {}, []
    porper = {}
    for f in filas:
        porper.setdefault(f["per"], {})[f["tag"]] = dict(f)
    per = max(porper)
    ns = sorted({f["namespace"] for f in filas if f["namespace"]})
    return per, porper[per], ns


def calcular(conn, disp: dict, per: str, cik: str) -> dict:
    """Los 14 ratios por concepto. Cada resultado lleva su cadena de evidencia."""
    out = {}
    for rid, (c_num, c_resta, c_den, unidad, publicable) in RATIOS.items():
        tn, fn = elegir_concepto(disp, c_num)
        td, fd = elegir_concepto(disp, c_den)
        base = {"unidad": unidad, "periodo": per, "publicable": publicable,
                "concepto_num": c_num, "concepto_den": c_den}
        if fn is None or fd is None:
            falta, cand = ((c_num, CONCEPTOS[c_num]) if fn is None
                           else (c_den, CONCEPTOS[c_den]))
            out[rid] = {**base, "estado": "NO_CALCULABLE", "valor": None,
                        "motivo": f"sin fact para el concepto '{falta}' en {per}; "
                                  f"ninguno de {cand} presente"}
            continue
        if fn["currency"] != fd["currency"]:
            out[rid] = {**base, "estado": "NO_CALCULABLE", "valor": None,
                        "motivo": f"monedas distintas: {tn}={fn['currency']} vs "
                                  f"{td}={fd['currency']}"}
            continue
        num, tr, fr = float(fn["value_numeric"]), None, None
        if c_resta:
            tr, fr = elegir_concepto(disp, c_resta)
            if fr is None:
                out[rid] = {**base, "estado": "NO_CALCULABLE", "valor": None,
                            "motivo": f"sin fact para el concepto '{c_resta}' en {per}"}
                continue
            if fr["currency"] != fn["currency"]:
                out[rid] = {**base, "estado": "NO_CALCULABLE", "valor": None,
                            "motivo": f"monedas distintas dentro del numerador"}
                continue
            num -= float(fr["value_numeric"])
        if float(fd["value_numeric"]) == 0:
            out[rid] = {**base, "estado": "NO_CALCULABLE", "valor": None,
                        "motivo": f"denominador {td} = 0"}
            continue
        formula = (f"({tn} - {tr}) / {td}" if tr else f"{tn} / {td}")
        insumos = [{"rol": "numerador", "concepto": c_num, "tag": tn,
                    "valor": float(fn["value_numeric"]), "moneda": fn["currency"],
                    "accession": fn["accession_number"], "filing_date": fn["fdate"],
                    "form": fn["form"], "namespace": fn["namespace"],
                    "url_filing": url_filing(cik, fn["accession_number"]),
                    "evidencia": evidencia_de(conn, fn)}]
        if fr is not None:
            insumos.append({"rol": "resta", "concepto": c_resta, "tag": tr,
                            "valor": float(fr["value_numeric"]), "moneda": fr["currency"],
                            "accession": fr["accession_number"], "filing_date": fr["fdate"],
                            "form": fr["form"], "namespace": fr["namespace"],
                            "url_filing": url_filing(cik, fr["accession_number"]),
                            "evidencia": evidencia_de(conn, fr)})
        insumos.append({"rol": "denominador", "concepto": c_den, "tag": td,
                        "valor": float(fd["value_numeric"]), "moneda": fd["currency"],
                        "accession": fd["accession_number"], "filing_date": fd["fdate"],
                        "form": fd["form"], "namespace": fd["namespace"],
                        "url_filing": url_filing(cik, fd["accession_number"]),
                        "evidencia": evidencia_de(conn, fd)})
        out[rid] = {**base, "estado": "CALCULADO" if publicable else "REVIEW_REQUIRED",
                    "valor": round(num / float(fd["value_numeric"]), 6),
                    "moneda_insumos": fn["currency"], "formula": formula,
                    "insumos": insumos}
    return out


def ratios_mercado(conn, disp, per, cik, precios) -> dict:
    """P/E, market cap y price/book. Exigen precio, moneda e instrumento."""
    out = {}
    te, fe = elegir_concepto(disp, "eps_basico")
    ts, fs = elegir_concepto(disp, "acciones_circulacion")
    tb, fb = elegir_concepto(disp, "patrimonio_controladora")

    def sin(rid, motivo, **extra):
        out[rid] = {"estado": "NO_CALCULABLE", "valor": None, "periodo": per,
                    "motivo": motivo, "publicable": True, **extra}

    # --- P/E ---------------------------------------------------------------
    if fe is None:
        sin("pe", f"sin EPS: ningun tag de {CONCEPTOS['eps_basico']} en {per}")
    else:
        p = next((x for x in precios if x["currency"] == fe["currency"]), None)
        if p is None:
            sin("pe", f"EPS en {fe['currency']} y no hay precio en esa moneda "
                      f"({[x['currency'] for x in precios]}); convertir exigiria "
                      f"un FX que no esta declarado")
        elif float(fe["value_numeric"]) <= 0:
            sin("pe", f"EPS = {float(fe['value_numeric'])} <= 0 (ejercicio con perdida); "
                      f"el PER no tiene interpretacion")
        else:
            ru = float(p["ratio_underlying"] or 1)
            out["pe"] = {
                "estado": "CALCULADO", "unidad": "veces", "periodo": per,
                "publicable": True,
                "valor": round(float(p["close"]) / ru / float(fe["value_numeric"]), 4),
                "formula": f"(close / ratio_adr) / {te}",
                "insumos": [
                    {"rol": "precio", "concepto": "precio_cierre",
                     "valor": float(p["close"]), "moneda": p["currency"],
                     "instrumento": p["instrument_id"], "mercado": p["exchange"],
                     "fecha": p["d"], "ratio_adr": ru,
                     "evidencia": {"estado": "COMPLETA", "fuente": "market_price_daily",
                                   "instrument_key": f"MKT:{p['instrument_id']}"}},
                    {"rol": "eps", "concepto": "eps_basico", "tag": te,
                     "valor": float(fe["value_numeric"]), "moneda": fe["currency"],
                     "accession": fe["accession_number"], "filing_date": fe["fdate"],
                     "namespace": fe["namespace"],
                     "url_filing": url_filing(cik, fe["accession_number"]),
                     "evidencia": evidencia_de(conn, fe)}]}

    # --- market cap --------------------------------------------------------
    if fs is None:
        sin("market_cap", f"sin conteo de acciones: ninguno de "
                          f"{CONCEPTOS['acciones_circulacion']} en {per}")
    else:
        p = next((x for x in precios if x["currency"] == "USD"), precios[0] if precios else None)
        if p is None:
            sin("market_cap", "sin precio")
        else:
            ru = float(p["ratio_underlying"] or 1)
            out["market_cap"] = {
                "estado": "CALCULADO", "unidad": p["currency"], "periodo": per,
                "publicable": True,
                "valor": round(float(p["close"]) / ru * float(fs["value_numeric"]), 2),
                "formula": f"(close / ratio_adr) * {ts}",
                "insumos": [
                    {"rol": "precio", "valor": float(p["close"]), "moneda": p["currency"],
                     "instrumento": p["instrument_id"], "mercado": p["exchange"],
                     "fecha": p["d"], "ratio_adr": ru,
                     "evidencia": {"estado": "COMPLETA", "fuente": "market_price_daily"}},
                    {"rol": "acciones", "concepto": "acciones_circulacion", "tag": ts,
                     "valor": float(fs["value_numeric"]),
                     "accession": fs["accession_number"], "filing_date": fs["fdate"],
                     "url_filing": url_filing(cik, fs["accession_number"]),
                     "evidencia": evidencia_de(conn, fs)}]}

    # --- price / book ------------------------------------------------------
    if fb is None or fs is None:
        sin("price_to_book", "falta patrimonio o conteo de acciones")
    else:
        p = next((x for x in precios if x["currency"] == fb["currency"]), None)
        if p is None:
            sin("price_to_book", f"patrimonio en {fb['currency']} y no hay precio "
                                 f"en esa moneda")
        elif float(fs["value_numeric"]) == 0:
            sin("price_to_book", "acciones = 0")
        else:
            ru = float(p["ratio_underlying"] or 1)
            bvps = float(fb["value_numeric"]) / float(fs["value_numeric"])
            if bvps <= 0:
                sin("price_to_book", f"valor libro por accion = {bvps:.4f} <= 0")
            else:
                out["price_to_book"] = {
                    "estado": "CALCULADO", "unidad": "veces", "periodo": per,
                    "publicable": True,
                    "valor": round(float(p["close"]) / ru / bvps, 4),
                    "formula": f"(close / ratio_adr) / ({tb} / {ts})",
                    "insumos": [
                        {"rol": "precio", "valor": float(p["close"]), "moneda": p["currency"],
                         "instrumento": p["instrument_id"], "fecha": p["d"], "ratio_adr": ru,
                         "evidencia": {"estado": "COMPLETA", "fuente": "market_price_daily"}},
                        {"rol": "patrimonio", "concepto": "patrimonio_controladora",
                         "tag": tb, "valor": float(fb["value_numeric"]),
                         "moneda": fb["currency"], "accession": fb["accession_number"],
                         "url_filing": url_filing(cik, fb["accession_number"]),
                         "evidencia": evidencia_de(conn, fb)},
                        {"rol": "acciones", "concepto": "acciones_circulacion", "tag": ts,
                         "valor": float(fs["value_numeric"]),
                         "accession": fs["accession_number"],
                         "evidencia": evidencia_de(conn, fs)}]}
    return out


def fila(conn, ticker: str) -> dict:
    r = {"ticker": ticker, "estado": "OK", "metricas": {}}

    inst = q(conn, """
        SELECT instrument_id, exchange, currency FROM market_instruments
         WHERE ticker_canonico=:t ORDER BY instrument_id""", t=ticker)
    if not inst:
        return {**r, "estado": "REVIEW_REQUIRED", "motivo": "sin instrumento en Market"}

    # --- camino fuerte: el instrumento declara a que entidad pertenece -----
    ents = q(conn, """
        SELECT DISTINCT e.entity_key, e.preferred_name,
               (SELECT id_value FROM identity_v1.identifier
                 WHERE entity_key=e.entity_key AND id_type='CIK' AND valid_to IS NULL
                 LIMIT 1) AS cik
          FROM identity_v1.instrument ii
          JOIN identity_v1.entity e ON e.entity_key=ii.entity_key
         WHERE ii.instrument_key = ANY(:ks) AND ii.valid_to IS NULL""",
        ks=[f"MKT:{i['instrument_id']}" for i in inst])

    if len(ents) == 1:
        ent = dict(ents[0])
        r["origen_identidad"] = "identity_v1.instrument"
        r["enlace_instrumento"] = "OK"
    else:
        # --- sin enlace: la entidad se resuelve por el CIK declarado, y SOLO
        # si su assertion esta VERIFIED. El precio NO se puede atribuir: eso es
        # justamente lo que el enlace faltante no demuestra.
        cik_decl = UNIVERSO.get(ticker)
        cand = q(conn, """
            SELECT e.entity_key, e.preferred_name, i.id_value AS cik, a.status::text AS st,
                   a.method::text AS metodo, left(a.evidence::text, 160) AS evidencia
              FROM identity_v1.identifier i
              JOIN identity_v1.entity e ON e.entity_key=i.entity_key
              JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
             WHERE i.id_type='CIK' AND i.id_value=:c AND i.valid_to IS NULL""", c=cik_decl)
        if len(cand) != 1 or cand[0]["st"] != "VERIFIED":
            return {**r, "estado": "REVIEW_REQUIRED",
                    "motivo": (f"identidad no demostrable: los instrumentos "
                               f"{[i['instrument_id'] for i in inst]} no tienen fila en "
                               f"identity_v1.instrument y el CIK declarado {cik_decl} "
                               f"no resuelve a una entidad con assertion VERIFIED"),
                    "instrumentos": [dict(i) for i in inst]}
        ent = {"entity_key": cand[0]["entity_key"], "preferred_name": cand[0]["preferred_name"],
               "cik": cand[0]["cik"]}
        r["origen_identidad"] = f"assertion CIK {cand[0]['st']} ({cand[0]['metodo']})"
        r["evidencia_identidad"] = cand[0]["evidencia"]
        r["enlace_instrumento"] = "REVIEW_REQUIRED"
        r["enlace_instrumento_motivo"] = (
            f"los instrumentos {[i['instrument_id'] for i in inst]} no tienen fila en "
            f"identity_v1.instrument. El CIK esta demostrado (SEC), pero nada demuestra "
            f"que ESTA especie cotizante sea de esa entidad: sin eso, atribuirle el "
            f"precio seria un join por ticker. Los ratios de mercado quedan NULL.")

    r["entidad"] = ent
    if not ent["cik"]:
        return {**r, "estado": "REVIEW_REQUIRED", "motivo": "la entidad no tiene CIK vigente"}

    precios = q(conn, """
        SELECT p.instrument_id, p.trading_date::text AS d, p.close, p.currency, p.exchange,
               (SELECT ratio_underlying FROM identity_v1.instrument
                 WHERE instrument_key='MKT:'||p.instrument_id AND valid_to IS NULL)
                 AS ratio_underlying
          FROM market_price_daily p
          JOIN (SELECT instrument_id, max(trading_date) md FROM market_price_daily
                 WHERE instrument_id = ANY(:ids) GROUP BY 1) u
            ON u.instrument_id=p.instrument_id AND u.md=p.trading_date
         WHERE p.instrument_id = ANY(:ids) ORDER BY p.currency""",
        ids=[str(i["instrument_id"]) for i in inst])
    r["precios"] = [dict(p) for p in precios]

    per, disp, ns = facts_ultimo_ejercicio(conn, ent["cik"])
    if per is None:
        return {**r, "estado": "SIN_FUNDAMENTALS",
                "motivo": f"CIK {ent['cik']} sin facts en derived.fact: "
                          f"S02/S03/S04 no ingirieron sus filings"}
    r["ejercicio"] = per
    r["taxonomia"] = taxonomia_de(ns)
    r["metricas"] = calcular(conn, disp, per, ent["cik"])
    if r["enlace_instrumento"] == "OK":
        r["metricas"].update(ratios_mercado(conn, disp, per, ent["cik"], r["precios"]))
    else:
        for rid in ("pe", "market_cap", "price_to_book"):
            r["metricas"][rid] = {
                "estado": "NO_CALCULABLE", "valor": None, "periodo": per,
                "publicable": True, "motivo": r["enlace_instrumento_motivo"]}

    # La moneda de la fila es la de los insumos EFECTIVAMENTE usados, no un
    # elemento cualquiera del conjunto de monedas del ejercicio: un 20-F puede
    # traer importes en dos monedas y elegir al azar mentia sobre la fila.
    usadas = [m["moneda_insumos"] for m in r["metricas"].values()
              if m.get("moneda_insumos")]
    r["moneda_reporte"] = max(set(usadas), key=usadas.count) if usadas else None
    otras = sorted(set(usadas) - {r["moneda_reporte"]})
    if otras:
        r["monedas_secundarias"] = otras
    return r


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)

    with eng.connect() as conn:
        filas = [fila(conn, t) for t in UNIVERSO]

    cols = ["pe", "market_cap", "price_to_book", "roe", "debt_to_equity",
            "current_ratio", "net_margin", "gross_margin"]
    print("SCREENER — universo de demostracion\n")
    print(f"  {'ticker':<7} {'ejercicio':<11} {'tax':<13} {'mon':<4} " +
          " ".join(f"{c[:11]:>13}" for c in cols))
    for f in filas:
        if f["estado"] != "OK":
            print(f"  {f['ticker']:<7} {f['estado']:<11} {'-':<13} {'-':<4} " +
                  " ".join(f"{'NULL':>13}" for _ in cols))
            continue
        linea = (f"  {f['ticker']:<7} {f['ejercicio'][:10]:<11} "
                 f"{f['taxonomia'][:12]:<13} {str(f['moneda_reporte'])[:3]:<4} ")
        for c in cols:
            m = f["metricas"].get(c, {})
            if m.get("estado") == "CALCULADO":
                v = m["valor"]
                linea += (f"{v/1e9:>12.2f}B " if c == "market_cap" else f"{v:>13.4f} ")
            else:
                linea += f"{'NULL':>13} "
        print(linea)

    print("\n  motivos de NULL por empresa")
    for f in filas:
        if f["estado"] != "OK":
            print(f"  {f['ticker']:<7} {f['estado']}: {f.get('motivo','')[:110]}")
            continue
        nulos = [(k, v["motivo"]) for k, v in f["metricas"].items()
                 if v["estado"] == "NO_CALCULABLE"]
        rev = [k for k, v in f["metricas"].items() if v["estado"] == "REVIEW_REQUIRED"]
        calc = sum(1 for v in f["metricas"].values() if v["estado"] == "CALCULADO")
        print(f"  {f['ticker']:<7} calculados={calc} review={len(rev)} nulos={len(nulos)}")
        for k, mot in nulos[:3]:
            print(f"          {k}: {mot[:100]}")

    (OUT / "screener.json").write_text(
        json.dumps(filas, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n  -> outputs/docs/fase_producto/screener.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
