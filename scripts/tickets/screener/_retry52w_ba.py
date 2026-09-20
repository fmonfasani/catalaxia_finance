# -*- coding: utf-8 -*-
"""Retry 52w para locales ARS con sufijo .BA (complementa _refresh_rangos_52w)."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
LOG = ROOT / "data" / "precert_refresh52w.json"

prev = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
fallidos = [tk for tk, d in prev.get("detalle_muestra", {}).items() if "error" in d]
# detalle_muestra es una muestra; releer fallos reales desde DB: tickers ARS sin refresh
con = sqlite3.connect(DB)
cur = con.cursor()
filas = cur.execute("""
    SELECT p.ticker, p.fecha, p.currency FROM precios p
    WHERE (p.ticker, p.fecha) IN (
        SELECT ticker, MAX(fecha) FROM precios GROUP BY ticker)
      AND p.currency = 'ARS'
""").fetchall()

import yfinance as yf

ok = fail = 0
detalle = {}
for tk, fe, cur_ in filas:
    try:
        fi = yf.Ticker(f"{tk}.BA").fast_info
        hi = getattr(fi, "year_high", None) or fi.get("year_high")
        lo = getattr(fi, "year_low", None) or fi.get("year_low")
        if not hi or not lo:
            raise ValueError("sin rangos .BA")
        cur.execute("UPDATE precios SET year_high=?, year_low=? WHERE ticker=? AND fecha=?",
                    (float(hi), float(lo), tk, fe))
        ok += 1
        detalle[tk] = {"yhigh": float(hi), "ylow": float(lo)}
    except Exception as e:
        fail += 1
        detalle[tk] = {"error": str(e)[:100]}
con.commit()

fuera = cur.execute("""
    SELECT COUNT(*) FROM precios p
    WHERE (ticker, fecha) IN (
        SELECT ticker, MAX(fecha) FROM precios GROUP BY ticker)
      AND precio IS NOT NULL AND year_high IS NOT NULL
      AND year_low IS NOT NULL AND year_low > 0
      AND (precio > year_high * 1.001 OR precio < year_low * 0.999)
""").fetchone()[0]

resumen = dict(prev)
resumen.update({
    "ts_retry_ba": datetime.now().isoformat(timespec="seconds"),
    "retry_ars_ok": ok, "retry_ars_fail": fail,
    "fuera_rango_post_retry": fuera,
})
LOG.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Retry .BA: {ok} ok / {fail} fallo | fuera de rango ahora: {fuera}")
con.close()
