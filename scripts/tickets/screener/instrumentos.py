# -*- coding: utf-8 -*-
"""
TABLA `instrumentos` — modelo de 2 niveles (empresa 1 : N instrumentos)
=======================================================================
El screener es 1 fila por EMPRESA (fundamentales). Esta tabla es 1 fila por
INSTRUMENTO negociable (la acción local, el ADR, el CEDEAR), cada uno con su
ISIN, mercado, moneda, precio y ratio. Se une a la empresa por `company_id`
(= screener.cuit: CIK para US, CUIT para AR).

Instrumentos por universo:
  - S&P 500  -> acción ordinaria US (USD) + CEDEAR en BYMA (ARS) si cotiza como tal
  - ADR AR   -> ADR en NYSE (USD) + acción ordinaria local en BYMA (ARS)
  - BYMA-only-> acción ordinaria local en BYMA (ARS)

Fundamentales NO se duplican acá (viven una sola vez en el screener). Acá va
solo lo del instrumento: precio/moneda/mercado/ISIN/ratio.

Salida: tabla `instrumentos` + data/instrumentos.csv + data/instrumentos.json
Uso:  python instrumentos.py
"""
from __future__ import annotations
import sqlite3, csv, json
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
OUT_CSV = ROOT / "data" / "instrumentos.csv"
OUT_JSON = ROOT / "data" / "instrumentos.json"

# ticker local (screener) -> ticker del ADR en NYSE
NYSE_TK = {"YPFD": "YPF", "PAMP": "PAM", "TECO2": "TEO", "TGSU2": "TGS", "CRES": "CRESY",
           "IRSA": "IRS", "BBAR": "BBAR", "CEPU": "CEPU", "GGAL": "GGAL", "LOMA": "LOMA",
           "SUPV": "SUPV", "VIST": "VIST", "BMA": "BMA"}

COLS = ["company_id", "ticker_empresa", "nombre", "tipo", "ticker", "mercado", "moneda",
        "isin", "cusip", "ratio", "precio", "fuente_precio"]


def isin_check_digit(body11: str) -> str:
    """Dígito verificador ISIN (ISO 6166) para las 11 primeras posiciones (país+NSIN).
    Letras -> A=10..Z=35, luego Luhn desde la derecha."""
    conv = "".join(str(int(c, 36)) for c in body11)     # '0'-'9'->0-9, 'A'-'Z'->10-35
    total = 0
    for i, ch in enumerate(reversed(conv)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - (total % 10)) % 10)


def isin_desde_cusip(cusip: str) -> str | None:
    """ISIN de un valor US a partir del CUSIP (9 chars): 'US' + cusip + check."""
    if not cusip or len(cusip) != 9:
        return None
    body = "US" + cusip
    return body + isin_check_digit(body)


def build():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("TABLA instrumentos (empresa 1:N instrumentos)")
    print("=" * 60)

    # cedear_ratios: ISIN cedear + ISIN subyacente por ticker
    ced = {}
    for r in cur.execute("SELECT ticker, isin_cedear, isin_subyacente, ratio, cedears_por_accion FROM cedear_ratios"):
        ced[r["ticker"].upper()] = r

    # nombres (para referencia): ratios (por cik) para US/ADR; null para BYMA
    def nombre(cuit):
        try:
            r = cur.execute("SELECT nombre FROM ratios WHERE cik=? LIMIT 1", (cuit,)).fetchone()
            return r[0] if r and r[0] else None
        except Exception:
            return None

    filas = []

    def add(company_id, tk_emp, nom, tipo, ticker, mercado, moneda, isin, cusip, ratio, precio, fuente):
        filas.append({"company_id": company_id, "ticker_empresa": tk_emp, "nombre": nom,
                      "tipo": tipo, "ticker": ticker, "mercado": mercado, "moneda": moneda,
                      "isin": isin, "cusip": cusip, "ratio": ratio,
                      "precio": round(precio, 4) if precio is not None else None,
                      "fuente_precio": fuente})

    rows = cur.execute("""SELECT cuit, ticker, grupo, precio_usd, precio_ars, ccl,
        cusip, adr_ratio, cedear_ratio, cedear_x FROM screener""").fetchall()

    for s in rows:
        cid, tk, grupo = s["cuit"], s["ticker"], s["grupo"]
        nom = nombre(cid)
        p_usd, p_ars, ccl = s["precio_usd"], s["precio_ars"], s["ccl"]

        if grupo == "sp500":
            c = ced.get((tk or "").upper())
            us_isin = c["isin_subyacente"] if c and c["isin_subyacente"] else None
            us_cusip = us_isin[2:11] if (us_isin and us_isin[:2] == "US" and len(us_isin) == 12) else None
            add(cid, tk, nom, "ordinaria", tk, "US", "USD", us_isin, us_cusip, None, p_usd, "yfinance")
            if s["cedear_ratio"] and c:
                cx = s["cedear_x"] or (c["cedears_por_accion"])
                precio_cedear = (p_ars / cx) if (p_ars and cx) else None
                add(cid, tk, nom, "cedear", tk, "BYMA", "ARS", c["isin_cedear"], None,
                    s["cedear_ratio"], precio_cedear, "derivado (usd*ccl/ratio)")

        elif grupo == "adr":
            nyse = NYSE_TK.get(tk, tk)
            adr_isin = isin_desde_cusip(s["cusip"]) if s["cusip"] else None
            add(cid, tk, nom, "adr", nyse, "NYSE", "USD", adr_isin, s["cusip"], s["adr_ratio"], p_usd, "yfinance")
            # acción ordinaria local (BYMA, ARS)
            add(cid, tk, nom, "ordinaria_ar", tk, "BYMA", "ARS", None, None, None, p_ars, "iamc")

        else:  # byma_only
            add(cid, tk, nom, "ordinaria_ar", tk, "BYMA", "ARS", None, None, None, p_ars, "iamc/yfinance")

    # crear tabla
    cur.execute("DROP TABLE IF EXISTS instrumentos")
    cur.execute(f"""CREATE TABLE instrumentos (
        instrumento_id INTEGER PRIMARY KEY AUTOINCREMENT,
        {', '.join(c + ' TEXT' for c in COLS if c not in ('precio',))}, precio REAL)""")
    cur.executemany(
        f"INSERT INTO instrumentos ({','.join(COLS)}) VALUES ({','.join(':' + c for c in COLS)})", filas)
    con.commit()

    # export CSV + JSON
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(filas)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(filas, f, ensure_ascii=False)

    # reporte
    from collections import Counter
    tipos = Counter(r["tipo"] for r in filas)
    print(f"  {len(filas)} instrumentos para {len(rows)} empresas")
    print("  por tipo:", dict(tipos))
    con_isin = sum(1 for r in filas if r["isin"])
    print(f"  con ISIN: {con_isin}/{len(filas)}  (falta: ISIN local AR + los S&P sin CEDEAR)")
    print(f"  -> {OUT_CSV.name} · {OUT_JSON.name}")
    # ejemplos
    print("\n  ejemplo YPF y AAPL:")
    for r in filas:
        if r["ticker_empresa"] in ("YPFD", "AAPL"):
            print(f"    {r['ticker_empresa']:6} {r['tipo']:13} {r['ticker']:6} {r['mercado']:6} "
                  f"{r['moneda']} {str(r['isin']):14} ratio={str(r['ratio']):6} precio={r['precio']}")
    con.close()
    print("\nINSTRUMENTOS -- OK")


if __name__ == "__main__":
    build()
