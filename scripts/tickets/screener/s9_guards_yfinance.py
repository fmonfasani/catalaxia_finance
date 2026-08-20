#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FASE 9 · GUARDS DE FUENTE UNICA (yfinance) + PRECIO EN USD VIA MEP
===================================================================
Politica: **yfinance es la unica fuente de precios**. Nada de IAMC ni de
ninguna otra fuente escribiendo valores. Cuando el dato no es confiable se
pone NULL; nunca se parcha con otra fuente.

Aplica tres guards, todos con datos de yfinance o internos:

  1. GUARD DE MONEDA
     Una empresa byma_only cotiza en pesos. Si `Currency <> 'ARS'`, el ticker
     se resolvio contra otro papel (colision con un simbolo de EEUU: COUR ->
     Coursera, CELU -> Celularity, AGRO -> Adecoagro, ...). Precio y rango a NULL.

  2. GUARD DE LIQUIDEZ
     Un papel que no opera no tiene precio de mercado. Si opero menos de
     MIN_PCT_RUEDAS del ultimo anio, el rango 52w va a NULL. Si ademas
     `fast_info` y `history` se contradicen mas de MAX_DIF_APIS, tampoco se
     publica el precio.

  3. RANGO 52w: ABSOLUTO Y PORCENTUAL
     Se guardan los dos. Los absolutos ya venian de yfinance pero se perdian
     en s4 (solo sobrevivia el %).
        max_52w_ars_yfinance          1170.00   (maximo absoluto, ARS)
        max_52w_usd_calc_mep_dolarito    0.7649
        dif_max_52w_pct                -17.24   (negativo = abajo del maximo)
     Convencion de signo: `precio/maximo - 1`, la de finviz/investing.

  4. PRECIO EN USD VIA MEP
        precio_usd_calc_mep_dolarito = precio_ars_yfinance / valor_mep_dolarito
     Reemplaza al `precio_usd` que salia de un CCL derivado de precios IAMC.
     El MEP sale de `dolarito_cotizaciones` (ver fetch_dolarito_historico.py),
     tomando la rueda mas cercana <= fecha del precio.

Orden en el pipeline:  s4 -> s6 -> s7 -> s8 -> **s9** -> s5
Uso:  python scripts/tickets/screener/s9_guards_yfinance.py [--no-fetch]
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion:
#   SCREENER_DB=screener.db.test python scripts/tickets/screener/run_all.py
# Debe estar en TODOS los scripts del pipeline: si uno solo no lo respeta,
# escribe en la base real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
from _precondiciones import requiere_columnas, requiere_filas

MIN_PCT_RUEDAS = 50.0   # % minimo de ruedas con volumen en 1 anio
MAX_DIF_APIS = 10.0     # % max de discrepancia fast_info vs history

COLS = [
    ("max_52w_ars_yfinance", "REAL"),
    ("min_52w_ars_yfinance", "REAL"),
    ("max_52w_usd_calc_mep_dolarito", "REAL"),
    ("min_52w_usd_calc_mep_dolarito", "REAL"),
    ("dif_max_52w_pct", "REAL"),
    ("dif_min_52w_pct", "REAL"),
    ("precio_usd_calc_mep_dolarito", "REAL"),
    ("valor_mep_dolarito", "REAL"),
    ("fecha_mep_dolarito", "TEXT"),
    ("pct_ruedas_operadas", "REAL"),
    ("guard_motivo", "TEXT"),
]


def asegurar_columnas(cur):
    existentes = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for nombre, tipo in COLS:
        if nombre not in existentes:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {nombre} {tipo}")


def medir_liquidez(tickers, log):
    """{ticker: (pct_ruedas, dif_apis_pct)} consultando yfinance."""
    import yfinance as yf
    out = {}
    for i, tk in enumerate(tickers, 1):
        sym = f"{tk}.BA"
        try:
            t = yf.Ticker(sym)
            h = t.history(period="1y")
            if not len(h):
                out[tk] = (0.0, None)
                continue
            pct = 100.0 * float((h["Volume"] > 0).sum()) / len(h)
            hist_high = float(h["High"].max())
            try:
                fi_high = t.fast_info.year_high
            except Exception:
                fi_high = None
            dif = (100.0 * (fi_high / hist_high - 1)
                   if (fi_high and hist_high) else None)
            out[tk] = (pct, dif)
        except Exception as e:
            log(f"    {tk}: error {type(e).__name__}")
            out[tk] = (None, None)
        if i % 15 == 0:
            log(f"    ... {i}/{len(tickers)}")
    return out


def mep_para(cur, fecha):
    """MEP de dolarito de la rueda mas cercana <= fecha."""
    r = cur.execute(
        "SELECT fecha, venta FROM dolarito_cotizaciones "
        "WHERE tipo='MEP' AND venta IS NOT NULL AND fecha <= ? "
        "ORDER BY fecha DESC LIMIT 1", (fecha,)).fetchone()
    return (r[0], r[1]) if r else (None, None)


def build(fetch_liquidez=True):
    log = print
    log("FASE 9 -- GUARDS yfinance + precio USD via MEP")
    log("=" * 66)

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    # s9 recalcula precios sobre el universo completo (s7) y necesita el sector
    # que asigna s6.
    requiere_columnas(cur, "screener", ["sector"], "s6_ajustes")
    requiere_filas(cur, "screener", 100, "s7_unificar")
    asegurar_columnas(cur)

    # rango 52w absoluto desde `precios` (se habia perdido en s4)
    rangos = {}
    for tk, pr, yh, yl, moneda, fecha in cur.execute(
            "SELECT ticker, precio, year_high, year_low, currency, fecha FROM precios"):
        rangos[tk] = {"precio": pr, "yhigh": yh, "ylow": yl,
                      "cur": moneda, "fecha": (fecha or "")[:10]}

    byma = [r[0] for r in cur.execute(
        "SELECT ticker FROM screener WHERE grupo='byma_only' ORDER BY ticker")]

    liq = {}
    if fetch_liquidez:
        log(f"\nMidiendo liquidez de {len(byma)} BYMA en yfinance...")
        liq = medir_liquidez(byma, log)

    n_moneda = n_iliquido = n_incons = n_usd = n_rango = 0
    hoy = datetime.now().strftime("%Y-%m-%d")

    for tk in byma:
        info = rangos.get(tk, {})
        precio = info.get("precio")
        yhigh, ylow = info.get("yhigh"), info.get("ylow")
        moneda = info.get("cur")
        fecha_px = info.get("fecha") or hoy
        pct, dif = liq.get(tk, (None, None))
        motivos = []

        # --- GUARD 1: moneda ---
        if moneda is not None and moneda != "ARS":
            motivos.append(f"moneda={moneda}(colision_ticker)")
            precio = yhigh = ylow = None

        # --- GUARD 2: liquidez ---
        if pct is not None and pct < MIN_PCT_RUEDAS:
            motivos.append(f"iliquido({pct:.0f}%_ruedas)")
            yhigh = ylow = None
            n_iliquido += 1
        if dif is not None and abs(dif) > MAX_DIF_APIS:
            motivos.append(f"apis_inconsistentes({dif:+.0f}%)")
            yhigh = ylow = None
            precio = None
            n_incons += 1
        if motivos and "moneda" in motivos[0]:
            n_moneda += 1

        # --- MEP de la fecha del precio ---
        f_mep, v_mep = mep_para(cur, fecha_px)

        # --- derivados ---
        precio_usd = (precio / v_mep) if (precio and v_mep) else None
        max_usd = (yhigh / v_mep) if (yhigh and v_mep) else None
        min_usd = (ylow / v_mep) if (ylow and v_mep) else None
        # signo estandar de screener: negativo = por debajo del maximo
        dif_max = ((precio / yhigh - 1) * 100) if (precio and yhigh) else None
        dif_min = ((precio / ylow - 1) * 100) if (precio and ylow) else None

        if precio_usd is not None:
            n_usd += 1
        if yhigh is not None:
            n_rango += 1

        cur.execute("""UPDATE screener SET
            max_52w_ars_yfinance=?, min_52w_ars_yfinance=?,
            max_52w_usd_calc_mep_dolarito=?, min_52w_usd_calc_mep_dolarito=?,
            dif_max_52w_pct=?, dif_min_52w_pct=?,
            precio_usd_calc_mep_dolarito=?, valor_mep_dolarito=?, fecha_mep_dolarito=?,
            pct_ruedas_operadas=?, guard_motivo=?
            WHERE ticker=? AND grupo='byma_only'""",
            (yhigh, ylow, max_usd, min_usd, dif_max, dif_min,
             precio_usd, v_mep, f_mep, pct,
             "; ".join(motivos) if motivos else None, tk))

    con.commit()

    log(f"\n  BYMA procesadas          : {len(byma)}")
    log(f"  descartadas por moneda   : {n_moneda}")
    log(f"  rango 52w NULL x iliquido: {n_iliquido}")
    log(f"  NULL x APIs inconsistentes: {n_incons}")
    log(f"  con precio_usd via MEP   : {n_usd}/{len(byma)}")
    log(f"  con rango 52w publicable : {n_rango}/{len(byma)}")

    log("\n  Papeles con guard activo:")
    for tk, m, p in cur.execute(
            "SELECT ticker, guard_motivo, pct_ruedas_operadas FROM screener "
            "WHERE grupo='byma_only' AND guard_motivo IS NOT NULL ORDER BY ticker"):
        log(f"    {tk:<8} {m}")

    con.close()
    log("\nFASE 9 -- OK")


if __name__ == "__main__":
    build(fetch_liquidez="--no-fetch" not in sys.argv)
