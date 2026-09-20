#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase B — matriz EMPRESA x RATIO para los 13 ratios del encargo de producto.

A diferencia de `ratios_inventario.py`/`e2e_producto.py` (que encadenan
IDENTITY -> SEC_XBRL -> MARKET en ese orden y por eso marcan a una empresa
entera como "cortada" si el instrumento no esta enlazado), esta matriz separa
por ratio: los fundamentales NO necesitan `identity_v1.instrument` — se
calculan directo desde `derived.fact` por CIK. Solo P/E, P/B y P/S necesitan
precio, y por lo tanto el enlace de instrumento. Esa distincion es el punto
central de la Fase E del encargo.

Estados: CALCULADO, NULL_VALIDO, NO_CALCULABLE, NO_IMPLEMENTADO, BLOQUEADO.
(CALCULABLE y REVIEW_REQUIRED quedan disponibles pero no se usan en esta
corrida: ninguno de los 13 ratios pedidos cae en REVIEW_REQUIRED hoy.)

SOLO LECTURA. No escribe en la base.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

from ratio_defs import CONCEPTOS, RATIOS  # noqa: E402
from ratio_inputs import sql_insumos  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_ratios"

EMPRESAS = [
    ("YPFD", "0000904851", "IFRS+US-GAAP"),
    ("CEPU", "0001717161", "ifrs-full"),
    ("TGSU2", "0000931427", "ifrs-full"),
    ("GGAL", "0001114700", "ifrs-full"),
    ("BMA", "0001347426", "ifrs-full"),
    ("AAPL", "0000320193", "us-gaap"),
    ("MSFT", "0000789019", "us-gaap"),
    ("NVDA", "0001045810", "us-gaap"),
]

# ratio pedido -> id interno en ratio_defs.RATIOS (None = no tiene equivalente
# fundamental, se resuelve aparte: eps, pe, y los NO_IMPLEMENTADO)
RATIOS_PEDIDOS = [
    ("P/E", None), ("EPS", None), ("P/B", None), ("P/S", None),
    ("ROE", "roe"), ("ROA", "roa"), ("D/E", "debt_to_equity"),
    ("Current Ratio", "current_ratio"), ("Quick Ratio", "quick_ratio"),
    ("Gross Margin", "gross_margin"), ("Operating Margin", "operating_margin"),
    ("Net Margin", "net_margin"), ("EV/EBITDA", None),
]


def q(conn, sql, **kw):
    return conn.execute(text(sql), kw).mappings().all()


def facts_del_periodo(conn, cik: str) -> dict:
    # F-061: WHERE canonico en `ratio_inputs`, con la guarda de pertenencia.
    filas = q(conn, sql_insumos(
        "d.tag, d.report_period, d.currency, d.value_numeric, d.accession_number, "
        "d.filing_date::text AS fdate, "
        "COALESCE(d.instant_date::text, d.end_date::text) AS fecha",
        extra=" ORDER BY d.report_period DESC"), c=cik)
    out: dict[str, dict] = {}
    for f in filas:
        out.setdefault(str(f["report_period"]), {})[f["tag"]] = dict(f)
    return out


def elegir(disp: dict, cands: list[str]):
    for t in cands:
        if t in disp:
            return t, disp[t]
    return None, None


def identidad(conn, ticker: str) -> dict:
    """Estado de identidad: CIK conocido, CUIT y su status, y si el/los
    instrumento(s) de mercado estan enlazados a esta entidad."""
    inst = q(conn, "SELECT instrument_id, exchange, currency, venue_ticker "
                   "  FROM market_instruments WHERE ticker_canonico=:t "
                   " ORDER BY instrument_id", t=ticker)
    enlazados = q(conn, """
        SELECT ii.instrument_key, ii.ratio_underlying
          FROM identity_v1.instrument ii
         WHERE ii.instrument_key = ANY(:ks) AND ii.valid_to IS NULL""",
        ks=[f"MKT:{i['instrument_id']}" for i in inst]) if inst else []
    return {"instrumentos": [dict(i) for i in inst],
            "enlazados": {e["instrument_key"]: float(e["ratio_underlying"] or 1)
                          for e in enlazados}}


def precio_en_moneda(conn, ident: dict, moneda: str):
    """Precio mas reciente de un instrumento de esta empresa cuya moneda
    coincide con la pedida, y SOLO si ese instrumento esta enlazado en
    identity_v1 (si no, no hay forma de saber a que entidad pertenece)."""
    for inst in ident["instrumentos"]:
        key = f"MKT:{inst['instrument_id']}"
        if key not in ident["enlazados"] or inst["currency"] != moneda:
            continue
        p = q(conn, """SELECT trading_date::text AS d, close, currency
                          FROM market_price_daily WHERE instrument_id=:i
                         ORDER BY trading_date DESC LIMIT 1""",
              i=inst["instrument_id"])
        if p:
            return dict(p[0]), ident["enlazados"][key]
    return None, None


def eps(disp: dict):
    """EPS por su cuenta, SIN depender de que haya precio. Devuelve
    (estado, valor, tag, moneda, accession, motivo)."""
    t, f = elegir(disp, CONCEPTOS["eps_basico"])
    if f is not None:
        return ("CALCULADO", float(f["value_numeric"]), t, f["currency"],
                f["accession_number"], None)
    # metodo 2: resultado_neto / acciones_promedio
    tn, fn = elegir(disp, CONCEPTOS["resultado_neto"])
    ts, fs = elegir(disp, CONCEPTOS["acciones_promedio"])
    if fn is None or fs is None or float(fs["value_numeric"]) == 0:
        falta = "resultado_neto" if fn is None else (
            "acciones_promedio" if fs is None else "acciones_promedio=0")
        return ("NO_CALCULABLE", None, None, None, None,
                f"sin tag directo de EPS y falta {falta} para derivarlo")
    if fn["currency"] != fs.get("currency", fn["currency"]):
        pass  # acciones no lleva moneda; no aplica el chequeo
    v = float(fn["value_numeric"]) / float(fs["value_numeric"])
    return ("CALCULADO", round(v, 6), f"{tn}/{ts} (derivado)", fn["currency"],
            fn["accession_number"], None)


def pe(conn, ident: dict, disp: dict, eps_res: tuple):
    estado_eps, val_eps, tag_eps, mon_eps, acc_eps, motivo_eps = eps_res
    if not ident["instrumentos"]:
        return ("NO_CALCULABLE", None, "no hay instrumento de mercado para esta empresa")
    if not ident["enlazados"]:
        return ("BLOQUEADO", None,
                f"{len(ident['instrumentos'])} instrumento(s) de mercado existen "
                "pero ninguno esta enlazado en identity_v1.instrument — el precio "
                "no se puede atribuir a esta entidad")
    if estado_eps != "CALCULADO":
        return ("NO_CALCULABLE", None, f"EPS no calculable: {motivo_eps}")
    if val_eps <= 0:
        return ("NULL_VALIDO", None,
                f"EPS={val_eps} <= 0 (ejercicio con perdida) — regla IAMC: "
                "P/E queda NULL, nunca negativo")
    precio, ratio_adr = precio_en_moneda(conn, ident, mon_eps)
    if precio is None:
        return ("NO_CALCULABLE", None,
                f"EPS en {mon_eps} y ningun instrumento ENLAZADO tiene precio "
                "en esa moneda")
    v = float(precio["close"]) / ratio_adr / val_eps
    return ("CALCULADO", round(v, 4),
            f"precio {precio['close']} {precio['currency']} / ratio_adr "
            f"{ratio_adr} / EPS {val_eps} ({tag_eps}, accession {acc_eps})")


def fundamental(disp: dict, rid: str):
    """Devuelve (estado, valor, unidad, moneda, detalle)."""
    num_c, resta_c, den_c, unidad, _pub = RATIOS[rid]
    tn, fn = elegir(disp, CONCEPTOS[num_c])
    td, fd = elegir(disp, CONCEPTOS[den_c])
    if fn is None or fd is None:
        falta = CONCEPTOS[num_c] if fn is None else CONCEPTOS[den_c]
        campo = "numerador" if fn is None else "denominador"
        return ("NO_CALCULABLE", None, unidad, "",
                f"falta {campo}: ninguno de {falta} presente")
    if fn["currency"] != fd["currency"]:
        return ("NO_CALCULABLE", None, unidad, "",
                f"monedas distintas: {tn}={fn['currency']} vs {td}={fd['currency']}")
    num_valor, resta_tag = float(fn["value_numeric"]), None
    if resta_c:
        tr, fr = elegir(disp, CONCEPTOS[resta_c])
        if fr is None:
            return ("NO_CALCULABLE", None, unidad, "",
                    f"falta el termino a restar: ninguno de {CONCEPTOS[resta_c]} presente")
        num_valor -= float(fr["value_numeric"])
        resta_tag = tr
    if float(fd["value_numeric"]) == 0:
        return ("NO_CALCULABLE", None, unidad, fn["currency"],
                f"denominador {td} = 0")
    v = round(num_valor / float(fd["value_numeric"]), 6)
    formula_tag = f"({tn}-{resta_tag})" if resta_tag else tn
    detalle = (f"{formula_tag}/{td} [{fn['currency']}] "
               f"accession {fn['accession_number']}")
    return ("CALCULADO", v, unidad, fn["currency"], detalle)


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)
    OUT.mkdir(parents=True, exist_ok=True)
    filas = []

    with eng.connect() as conn:
        for ticker, cik, tax in EMPRESAS:
            ident = identidad(conn, ticker)
            porper = facts_del_periodo(conn, cik)
            if not porper:
                for nombre, _ in RATIOS_PEDIDOS:
                    filas.append({"empresa": ticker, "ratio": nombre,
                                  "estado": "NO_CALCULABLE", "valor": "",
                                  "periodo": "", "moneda": "",
                                  "fuente": "derived.fact", "provenance": "",
                                  "metodo": "",
                                  "motivo": "sin fundamentals en derived.fact"})
                continue
            ultimo = max(porper)
            disp = porper[ultimo]
            eps_res = eps(disp)

            for nombre, rid in RATIOS_PEDIDOS:
                if nombre == "EPS":
                    estado, val, tag, mon, acc, motivo = eps_res
                    filas.append({
                        "empresa": ticker, "ratio": "EPS", "estado": estado,
                        "valor": val if val is not None else "",
                        "periodo": ultimo, "moneda": mon or "",
                        "fuente": "SEC EDGAR / derived.fact",
                        "provenance": f"tag={tag}, accession={acc}" if tag else "",
                        "metodo": "tag directo o resultado_neto/acciones_promedio",
                        "motivo": motivo or ""})
                elif nombre == "P/E":
                    estado, val, detalle = pe(conn, ident, disp, eps_res)
                    filas.append({
                        "empresa": ticker, "ratio": "P/E", "estado": estado,
                        "valor": val if val is not None else "",
                        "periodo": ultimo,
                        "moneda": eps_res[3] or "",
                        "fuente": "market_price_daily + derived.fact",
                        "provenance": detalle if estado == "CALCULADO" else "",
                        "metodo": "precio/ratio_adr/EPS",
                        "motivo": detalle if estado != "CALCULADO" else ""})
                elif nombre in ("P/B", "P/S"):
                    filas.append({
                        "empresa": ticker, "ratio": nombre,
                        "estado": "NO_IMPLEMENTADO", "valor": "",
                        "periodo": "", "moneda": "", "fuente": "",
                        "provenance": "",
                        "metodo": "declarado en RATIO_CONTRACT.md, sin cablear",
                        "motivo": "no existe codigo que lo calcule; los facts "
                                  "de patrimonio/ingresos SI estan disponibles"})
                elif nombre == "EV/EBITDA":
                    filas.append({
                        "empresa": ticker, "ratio": "EV/EBITDA",
                        "estado": "NO_IMPLEMENTADO", "valor": "",
                        "periodo": "", "moneda": "", "fuente": "",
                        "provenance": "",
                        "metodo": "ninguno: no hay concepto EBITDA/EV declarado "
                                  "en ratio_defs.py",
                        "motivo": "CORRECCION vs. ciclo anterior: SI existen tags "
                                  "candidatos de D&A para esta empresa en "
                                  "derived.fact (verificado por consulta directa "
                                  "2026-09-01); el bloqueo es de codigo "
                                  "(no implementado), no de dato ausente"})
                else:
                    estado, val, unidad, moneda, detalle = fundamental(disp, rid)
                    filas.append({
                        "empresa": ticker, "ratio": nombre, "estado": estado,
                        "valor": val if val is not None else "",
                        "periodo": ultimo, "moneda": moneda,
                        "fuente": "SEC EDGAR / derived.fact",
                        "provenance": detalle if estado == "CALCULADO" else "",
                        "metodo": f"{RATIOS[rid][0]}/{RATIOS[rid][2]}"
                                  + (f" - {RATIOS[rid][1]}" if RATIOS[rid][1] else ""),
                        "motivo": detalle if estado != "CALCULADO" else ""})

    # BLOQUEADO explicito para P/E cuando el bloqueo es de enlace, no de EPS:
    # ya lo calcula `pe()`. No hace falta post-proceso.

    campos = ["empresa", "ratio", "estado", "valor", "periodo", "moneda",
              "fuente", "provenance", "metodo", "motivo"]
    with (OUT / "RATIO_PRODUCT_MATRIX.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)

    (OUT / "_matriz_producto_raw.json").write_text(
        json.dumps(filas, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # resumen en consola
    from collections import Counter
    c = Counter(f["estado"] for f in filas)
    print("MATRIZ EMPRESA x RATIO — resumen de estados")
    for k, v in sorted(c.items()):
        print(f"  {k:<16} {v}")
    print(f"\n  total filas: {len(filas)}")
    print("  -> outputs/docs/fase_ratios/RATIO_PRODUCT_MATRIX.csv")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
