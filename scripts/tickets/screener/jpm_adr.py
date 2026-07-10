# -*- coding: utf-8 -*-
"""
DATOS DE ADR desde J.P. Morgan (adr.com) — API pública
=======================================================
Fuente: **J.P. Morgan Depositary Receipts** (adr.com), servida por MarkitDigital.
API pública (sin login): https://api.markitdigital.com/jpmadr-public/v1/

Para cada ADR argentino (ticker NYSE de la tabla `adr_ratios`) trae:
  - **CUSIP** (identificador del ADR)  -> search?q={ticker}
  - **DR Level** (I / II / III)         -> dr/level/{cusip}
  - **Dividendos del ADR** (ratePerDr USD + fechas) -> dr/dividends/{cusip}

Guarda:
  - columnas en `screener`: `cusip`, `dr_level`, `div_adr_12m` (USD/ADR últimos 12m),
    `last_div_date`
  - tabla `adr_dividendos` (historial completo, auditable, con source)

Nota: el **ratio DR:ORD no está en la API pública** de JPMorgan (se sirve por la privada,
con login) — ese dato sale de SEC EDGAR (ver `sec_adr_ratios.py`). Los **fees** vienen
vacíos en la API pública. CUSIP es dato con copyright (CUSIP Global Services): lo usamos
como identificador puntual, no redistribuimos la base.

Uso:  python jpm_adr.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
import urllib3
urllib3.disable_warnings()

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
B = "https://api.markitdigital.com/jpmadr-public/v1/"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
     "Origin": "https://www.adr.com", "Referer": "https://www.adr.com/"}
SOURCE = "https://www.adr.com (J.P. Morgan / MarkitDigital jpmadr-public API)"


def _get(ep):
    try:
        r = requests.get(B + ep, headers=H, timeout=15, verify=False)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_adr(ticker):
    """Devuelve dict con cusip, level, dividends (lista) para un ticker NYSE, o None."""
    s = _get(f"search?q={ticker}")
    items = (s or {}).get("data", {}).get("items", [])
    it = next((x for x in items if x.get("symbol") == ticker), items[0] if items else None)
    if not it or not it.get("cusip"):
        return None
    cusip = it["cusip"]
    level = (_get(f"dr/level/{cusip}") or {}).get("data", {}).get("level")
    divs = (_get(f"dr/dividends/{cusip}") or {}).get("data", {}).get("items", [])
    return {"cusip": cusip, "level": level, "dividends": divs}


def build():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("DATOS DE ADR desde J.P. Morgan (adr.com)")
    print("=" * 60)

    # columnas nuevas
    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for c, t in [("cusip", "TEXT"), ("dr_level", "TEXT"),
                 ("div_adr_12m", "REAL"), ("last_div_date", "TEXT")]:
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {t}")

    # tabla de dividendos ADR
    cur.execute("""CREATE TABLE IF NOT EXISTS adr_dividendos (
        cuit TEXT, ticker TEXT, cusip TEXT, announcement_date TEXT, record_date TEXT,
        payment_date TEXT, rate_per_dr REAL, source TEXT)""")

    adrs = cur.execute("SELECT cuit, edgar_ticker FROM adr_ratios ORDER BY edgar_ticker").fetchall()
    hoy = datetime.now(timezone.utc)
    corte12 = hoy - timedelta(days=365)

    n_ok = n_div = 0
    for row in adrs:
        cuit, tk = row["cuit"], row["edgar_ticker"]
        data = fetch_adr(tk)
        if not data:
            print(f"  {tk:6} sin datos en JPM")
            continue
        cusip, level, divs = data["cusip"], data["level"], data["dividends"]

        # resolver la fila del screener: por cuit, o por ticker si el cuit no coincide
        # (BMA tiene cuit=None en adr_ratios y usa el CIK en el screener)
        scr = cur.execute("SELECT cuit FROM screener WHERE grupo='adr' AND (cuit=? OR ticker=?) LIMIT 1",
                          (cuit or "", tk)).fetchone()
        target = scr[0] if scr else cuit

        # guardar historial de dividendos (reemplaza los de este cusip)
        cur.execute("DELETE FROM adr_dividendos WHERE cusip=?", (cusip,))
        div_12m, last_date = 0.0, None
        for d in divs:
            rate = d.get("ratePerDr")
            pay = (d.get("paymentDate") or "")[:10]
            cur.execute("INSERT INTO adr_dividendos VALUES (?,?,?,?,?,?,?,?)",
                        (target, tk, cusip, (d.get("announcementDate") or "")[:10],
                         (d.get("recordDate") or "")[:10], pay, rate, SOURCE))
            if rate and pay:
                if last_date is None or pay > last_date:
                    last_date = pay
                try:
                    if datetime.fromisoformat(pay).replace(tzinfo=timezone.utc) >= corte12:
                        div_12m += rate
                except ValueError:
                    pass
        if divs:
            n_div += 1

        # escribir en screener (match por cuit resuelto)
        cur.execute("""UPDATE screener SET cusip=?, dr_level=?, div_adr_12m=?, last_div_date=?
                       WHERE cuit=?""",
                    (cusip, level, round(div_12m, 6) if div_12m else None, last_date, target))
        n_ok += 1
        print(f"  {tk:6} cusip={cusip:11} level={str(level):10} divs={len(divs):>2} "
              f"12m=${div_12m:.4f} ult={last_date}")

    con.commit()
    print(f"\n  {n_ok} ADR con CUSIP+level · {n_div} con historial de dividendos")

    # ── Dividend yield del ADR (limpio: USD dividendo / USD precio del ADR) ──
    # NO calculamos payout desde acá: el dividendo es USD/ADR y el EPS viene en la moneda
    # del balance (ARS para varios) → mezclarlos sin CCL da error. El payout correcto sale
    # de EDGAR (div/NI del mismo 20-F, misma moneda). Acá damos yield + corregimos quién paga.
    if "div_yield_adr" not in {r[1] for r in cur.execute("PRAGMA table_info(screener)")}:
        cur.execute("ALTER TABLE screener ADD COLUMN div_yield_adr REAL")
    n_yield = n_fix = 0
    for row in cur.execute("""SELECT cuit, ticker, precio_usd, div_adr_12m, payout_status
                              FROM screener WHERE grupo='adr'""").fetchall():
        div12, precio = row["div_adr_12m"], row["precio_usd"]
        if div12 and div12 > 0 and precio and precio > 0:
            dy = div12 / precio
            cur.execute("UPDATE screener SET div_yield_adr=? WHERE cuit=?", (round(dy, 5), row["cuit"]))
            n_yield += 1
            # si figuraba 'no_paga' pero pagó en los últimos 12m, corregir: SÍ paga
            if row["payout_status"] == "no_paga":
                cur.execute("UPDATE screener SET payout_status='falta_dato' WHERE cuit=?", (row["cuit"],))
                n_fix += 1
            print(f"    {row['ticker']:6} div_yield={dy*100:.1f}%  (${div12:.4f}/ADR sobre ${precio:.2f})")
    con.commit()
    print(f"  {n_yield} ADR con dividend yield · {n_fix} corregidos de 'no_paga' a 'paga' (falta ratio)")
    print(f"  FUENTE: {SOURCE}")
    con.close()
    print("\nJPM ADR -- OK")


if __name__ == "__main__":
    build()
