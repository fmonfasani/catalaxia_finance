# -*- coding: utf-8 -*-
"""
O2 -- Refresh de rangos 52 semanas en tabla precios
====================================================
Los year_high/year_low de `precios` son estaticos (snapshot de descarga):
si el precio actual salio del rango historico, Max52w/Min52w quedan
inconsistentes. Este script:

  1. mide el baseline de filas fuera de rango,
  2. refresca year_high/year_low via yfinance (fast_info) SOLO en la fila
     mas reciente de cada ticker (nunca inserta ni toca precio/mcap),
  3. vuelve a medir y deja un log JSON en data/.

Degradacion honesta: si no hay red, registra el fallo por ticker y
conserva el baseline. Idempotente.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"


def fuera_de_rango(cur):
    row = cur.execute("""
        SELECT COUNT(*) FROM precios p
        WHERE (ticker, fecha) IN (
            SELECT ticker, MAX(fecha) FROM precios GROUP BY ticker)
          AND precio IS NOT NULL AND year_high IS NOT NULL
          AND year_low IS NOT NULL AND year_low > 0
          AND (precio > year_high * 1.001 OR precio < year_low * 0.999)
    """).fetchone()
    return row[0]


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    ts = datetime.now().isoformat(timespec="seconds")

    base = fuera_de_rango(cur)
    filas = cur.execute("""
        SELECT ticker, MAX(fecha) FROM precios GROUP BY ticker
    """).fetchall()
    print(f"Baseline: {base} tickers fuera de rango | {len(filas)} tickers en precios")

    ok = fail = skipped = 0
    detalle = {}
    try:
        import yfinance as yf
    except ImportError:
        yf = None
        print("yfinance no disponible -> modo solo-lectura")

    if yf is not None:
        for tk, fe in filas:
            try:
                fi = yf.Ticker(tk).fast_info
                hi = getattr(fi, "year_high", None) or fi.get("year_high")
                lo = getattr(fi, "year_low", None) or fi.get("year_low")
                if not hi or not lo:
                    raise ValueError("fast_info sin rangos")
                cur.execute(
                    "UPDATE precios SET year_high=?, year_low=? "
                    "WHERE ticker=? AND fecha=?",
                    (float(hi), float(lo), tk, fe),
                )
                ok += 1
                detalle[tk] = {"yhigh": float(hi), "ylow": float(lo)}
            except Exception as e:
                fail += 1
                detalle[tk] = {"error": str(e)[:120]}
            if (ok + fail) % 25 == 0:
                print(f"  ... {ok + fail}/{len(filas)} procesados")
        con.commit()

    despues = fuera_de_rango(cur)
    resumen = {
        "ts": ts, "baseline_fuera_rango": base,
        "tickers": len(filas), "refrescados": ok, "fallos": fail,
        "fuera_rango_post": despues, "detalle_muestra": dict(
            list(detalle.items())[:10]),
    }
    out = ROOT / "data" / "precert_refresh52w.json"
    out.write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"Refrescados: {ok} | Fallos: {fail}")
    print(f"Fuera de rango: {base} -> {despues}")
    print(f"Log -> {out}")
    con.close()


if __name__ == "__main__":
    main()
