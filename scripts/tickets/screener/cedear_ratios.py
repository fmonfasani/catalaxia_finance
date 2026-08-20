# -*- coding: utf-8 -*-
"""
RATIOS CEDEAR — dato OFICIAL del emisor (Banco Comafi)
======================================================
Fuente: **Banco Comafi**, emisor de CEDEARs autorizado por la CNV (custodia del subyacente
en The Bank of New York Mellon). Comafi publica el "Listado Total Programas de CEDEARs" que
su web carga desde un endpoint JSON:

    https://www.comafi.com.ar/custodiaglobal/json/apps/getproducts.aspx

Cada producto trae el ratio en el campo `character` (ej. "20 : 1" = 20 CEDEARs por 1 acción
del subyacente), el ticker (`name`), el ISIN del CEDEAR (`tip`), el ISIN del subyacente
(`tech`) y el país (`categories[].category`).

Guarda:
  - tabla `cedear_ratios` (ticker, empresa, ratio, cedears_por_accion, isin_cedear,
    isin_subyacente, pais, source_url, fecha)
  - CSV data/cedear_ratios.csv (auditable, versionable)
  - columna `cedear_ratio` en `screener` (los S&P que cotizan como CEDEAR)

Uso:  python cedear_ratios.py
Cadencia sugerida: mensual/trimestral (los ratios cambian de vez en cuando — Comafi los
reajusta; ver campo `fecha`).
"""
from __future__ import annotations
import re, csv, json, sqlite3, time
from pathlib import Path
from datetime import datetime

import requests
import urllib3
urllib3.disable_warnings()

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
OUT_CSV = ROOT / "data" / "cedear_ratios.csv"
COMAFI_URL = "https://www.comafi.com.ar/custodiaglobal/json/apps/getproducts.aspx"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
     "X-Requested-With": "XMLHttpRequest",
     "Referer": "https://www.comafi.com.ar/custodiaglobal/programas.aspx"}
RATIO = re.compile(r"(\d+)\s*:\s*(\d+)")


def fetch_comafi(log):
    url = f"{COMAFI_URL}?ts={int(time.time())}"
    r = requests.get(url, headers=H, timeout=40, verify=False)
    r.raise_for_status()
    data = r.json()
    prods = data.get("products", [])
    log(f"cedear: Comafi devolvió {len(prods)} programas")
    out = []
    for p in prods:
        name = (p.get("name") or "").strip().upper()
        m = RATIO.search((p.get("character") or "").strip())
        if not name or not m:
            continue
        n, mm = int(m.group(1)), int(m.group(2))
        pais = ""
        cats = p.get("categories") or []
        if cats:
            pais = cats[0].get("category", "")
        out.append({
            "ticker": name,
            "empresa": (p.get("summary") or "").strip(),
            "ratio": f"{n}:{mm}",
            "cedears_por_accion": n / mm,     # cuántos CEDEARs equivalen a 1 acción
            "isin_cedear": (p.get("tip") or "").strip(),
            "isin_subyacente": (p.get("tech") or "").strip(),
            "pais": pais,
            "source_url": COMAFI_URL,
            "fecha": datetime.now().strftime("%Y-%m-%d"),
        })
    return out


def build():
    log = lambda m: print(m)
    print("RATIOS CEDEAR (fuente oficial: Banco Comafi)")
    print("=" * 60)

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    # Resiliente: si Comafi responde, reconstruye tabla+CSV; si no, reusa lo cacheado.
    rows = None
    try:
        rows = fetch_comafi(log)
        print(f"  {len(rows)} CEDEARs con ratio parseado")
    except Exception as e:
        print(f"  [!] Comafi no responde ({type(e).__name__}) — reuso la tabla cedear_ratios cacheada")

    if rows:
        cur.execute("DROP TABLE IF EXISTS cedear_ratios")
        cur.execute("""CREATE TABLE cedear_ratios (
            ticker TEXT PRIMARY KEY, empresa TEXT, ratio TEXT, cedears_por_accion REAL,
            isin_cedear TEXT, isin_subyacente TEXT, pais TEXT, source_url TEXT, fecha TEXT)""")
        cur.executemany("""INSERT OR REPLACE INTO cedear_ratios
            (ticker, empresa, ratio, cedears_por_accion, isin_cedear, isin_subyacente, pais, source_url, fecha)
            VALUES (:ticker,:empresa,:ratio,:cedears_por_accion,:isin_cedear,:isin_subyacente,:pais,:source_url,:fecha)""",
            rows)
        con.commit()
        with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["ticker", "empresa", "ratio", "cedears_por_accion",
                                              "isin_cedear", "isin_subyacente", "pais", "source_url", "fecha"])
            w.writeheader(); w.writerows(rows)
        print(f"  -> {OUT_CSV.name} ({len(rows)} filas, con source_url)")
    else:
        if not cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cedear_ratios'").fetchone():
            print("  [!] Sin tabla cacheada y Comafi caído — no hay ratios CEDEAR este run.")
            con.close(); return
        rows = [dict(zip(["ticker", "ratio", "cedears_por_accion"], r)) for r in
                cur.execute("SELECT ticker, ratio, cedears_por_accion FROM cedear_ratios").fetchall()]
        print(f"  reusando {len(rows)} ratios de la tabla cacheada")

    # columna cedear_ratio en screener (para los que matchean por ticker)
    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for c, t in [("cedear_ratio", "TEXT"), ("cedear_x", "REAL")]:
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {t}")
    cur.execute("UPDATE screener SET cedear_ratio=NULL, cedear_x=NULL")
    n_match = 0
    by = {r["ticker"]: r for r in rows}
    for (tk,) in cur.execute("SELECT ticker FROM screener").fetchall():
        r = by.get((tk or "").upper())
        if r:
            cur.execute("UPDATE screener SET cedear_ratio=?, cedear_x=? WHERE ticker=?",
                        (r["ratio"], r["cedears_por_accion"], tk))
            n_match += 1
    con.commit()

    # reporte por universo
    print(f"\n  cedear_ratio poblado en screener: {n_match} tickers")
    for g in ("sp500", "adr", "byma_only"):
        tot = cur.execute("SELECT COUNT(*) FROM screener WHERE grupo=?", (g,)).fetchone()[0]
        c = cur.execute("SELECT COUNT(*) FROM screener WHERE grupo=? AND cedear_ratio IS NOT NULL", (g,)).fetchone()[0]
        print(f"    {g:10} {c}/{tot} con CEDEAR")
    print("\n  ejemplos:", dict(cur.execute(
        "SELECT ticker, cedear_ratio FROM screener WHERE cedear_ratio IS NOT NULL AND ticker IN ('AAPL','MSFT','NVDA','AMZN','KO','TSLA') ").fetchall()))
    print(f"\n  FUENTE: {COMAFI_URL}")
    print("  (Banco Comafi — emisor de CEDEARs autorizado por CNV, custodia en BNY Mellon)")
    con.close()
    print("\nRATIOS CEDEAR -- OK")


if __name__ == "__main__":
    build()
