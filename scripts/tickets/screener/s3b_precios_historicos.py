# -*- coding: utf-8 -*-
"""
FASE 3B -- Serie diaria de precios (OHLC) para todo el universo
================================================================
Baja de yfinance la serie **diaria** de cada papel entre una fecha de inicio y
hoy, y la guarda con una fila por (ticker, dia): apertura, maximo, minimo,
cierre, cierre ajustado y volumen.

POR QUE UNA TABLA APARTE
  `precios` guarda UNA fila por ticker: la ultima foto. Sus consumidores (s4,
  s7, s9) la leen asi, y meterle historia los romperia. Ademas, guardar solo la
  foto tiene el problema de fondo que ya conocemos: cada corrida pisa la
  anterior y no queda historia con la que reconstruir nada.

  Aca se guardan los HECHOS (la serie diaria) y `precios` sigue siendo la foto
  derivada. Es la misma idea que aplicamos al vintage: guardar el dato crudo y
  derivar lo demas.

QUE RESUELVE
  - Cada valor dice a que dia pertenece y si es open/high/low/close.
  - Se puede reconstruir el precio de cualquier fecha pasada -> PER historico,
    series, backtests sin sesgo de anticipacion.
  - El precio en USD via MEP se puede calcular por dia, con el MEP de ESE dia,
    en vez de con uno solo para toda la tabla.

INCREMENTAL
  Por cada ticker arranca desde el dia siguiente al ultimo que ya tenga. Si no
  tiene nada, desde --desde. Correrlo dos veces no vuelve a bajar lo mismo.

UNIVERSO
  byma_only -> TICKER.BA        (yfinance usa sufijo .BA para BYMA)
  adr       -> simbolo del ADR  (mapeo ADR_YF, reutilizado de s3_precios)
  sp500     -> el simbolo tal cual

USO
  python s3b_precios_historicos.py --desde 2026-07-09
  python s3b_precios_historicos.py --desde 2026-01-01 --grupo byma_only
  SCREENER_DB=screener.db.test python s3b_precios_historicos.py --desde 2026-07-09
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance no instalado. Correr: pip install yfinance")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s3_precios import ADR_YF          # noqa: E402  (mapeo CUIT -> simbolo ADR)

DDL = """
CREATE TABLE IF NOT EXISTS precios_diarios (
    ticker      TEXT NOT NULL,      -- simbolo canonico del screener
    fecha       TEXT NOT NULL,      -- AAAA-MM-DD, dia de la rueda
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    adj_close   REAL,               -- ajustado por splits y dividendos
    volume      REAL,
    currency    TEXT,               -- moneda de cotizacion (ARS / USD)
    ticker_yf   TEXT,               -- simbolo consultado en yfinance
    fuente      TEXT DEFAULT 'yfinance',
    ingested_at TEXT,               -- cuando lo bajamos nosotros
    PRIMARY KEY (ticker, fecha)
);
CREATE INDEX IF NOT EXISTS ix_precios_diarios_fecha ON precios_diarios(fecha);
"""


def simbolo_yf(cur, ticker, grupo, cuit):
    """Simbolo de yfinance para un papel del screener."""
    if grupo == "byma_only":
        return f"{ticker}.BA"
    if grupo == "adr":
        return ADR_YF.get(str(cuit)) or ticker
    return ticker                      # sp500: el simbolo tal cual


def ultimo_dia(cur, ticker):
    cur.execute("SELECT MAX(fecha) FROM precios_diarios WHERE ticker=?", (ticker,))
    r = cur.fetchone()
    return r[0] if r and r[0] else None


def bajar(sym, desde, hasta, reintentos=3):
    """DataFrame diario de yfinance, o None."""
    for i in range(reintentos):
        try:
            df = yf.Ticker(sym).history(start=desde, end=hasta,
                                        interval="1d", auto_adjust=False)
            if df is not None and not df.empty:
                return df
            return None
        except Exception:
            if i < reintentos - 1:
                time.sleep(1.5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-07-09",
                    help="fecha inicial si el ticker no tiene historia (AAAA-MM-DD)")
    ap.add_argument("--hasta", default=None, help="por defecto, hoy")
    ap.add_argument("--grupo", default=None,
                    choices=["byma_only", "adr", "sp500"],
                    help="limitar a un grupo")
    ap.add_argument("--sleep", type=float, default=0.35)
    ap.add_argument("--limite", type=int, default=0, help="cortar tras N tickers")
    a = ap.parse_args()

    hasta = a.hasta or (date.today() + timedelta(days=1)).isoformat()
    print("FASE 3B -- serie diaria de precios (OHLC)")
    print("=" * 62)
    print(f"Base   : {DB}")
    print(f"Rango  : {a.desde} .. {hasta}" + (f"   grupo={a.grupo}" if a.grupo else ""))

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    for stmt in DDL.strip().split(";"):
        if stmt.strip():
            cur.execute(stmt)
    con.commit()

    sql = "SELECT ticker, grupo, cuit FROM screener WHERE ticker IS NOT NULL"
    params = []
    if a.grupo:
        sql += " AND grupo=?"
        params.append(a.grupo)
    sql += " ORDER BY grupo, ticker"
    papeles = cur.execute(sql, params).fetchall()
    if a.limite:
        papeles = papeles[:a.limite]
    print(f"Papeles: {len(papeles)}\n")

    ahora = datetime.now().isoformat(timespec="seconds")
    ok = vacios = errores = 0
    filas_nuevas = 0
    for i, (ticker, grupo, cuit) in enumerate(papeles, 1):
        sym = simbolo_yf(cur, ticker, grupo, cuit)
        ult = ultimo_dia(cur, ticker)
        desde = a.desde
        if ult:
            # incremental: arrancar el dia siguiente al ultimo que ya tenemos
            desde = (date.fromisoformat(ult) + timedelta(days=1)).isoformat()
            if desde >= hasta:
                continue                       # al dia, nada que bajar

        df = bajar(sym, desde, hasta)
        if df is None:
            vacios += 1
            if vacios <= 10:
                print(f"  [SIN DATOS] {ticker:<9} yf={sym}")
            time.sleep(a.sleep)
            continue

        cur_moneda = None
        try:
            cur_moneda = yf.Ticker(sym).fast_info.currency
        except Exception:
            pass

        n = 0
        for idx, row in df.iterrows():
            f = idx.date().isoformat()
            cur.execute("""
                INSERT OR REPLACE INTO precios_diarios
                  (ticker, fecha, open, high, low, close, adj_close, volume,
                   currency, ticker_yf, fuente, ingested_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,'yfinance',?)
            """, (ticker, f,
                  float(row.get("Open")) if row.get("Open") == row.get("Open") else None,
                  float(row.get("High")) if row.get("High") == row.get("High") else None,
                  float(row.get("Low")) if row.get("Low") == row.get("Low") else None,
                  float(row.get("Close")) if row.get("Close") == row.get("Close") else None,
                  float(row.get("Adj Close")) if "Adj Close" in row and row.get("Adj Close") == row.get("Adj Close") else None,
                  float(row.get("Volume")) if row.get("Volume") == row.get("Volume") else None,
                  cur_moneda, sym, ahora))
            n += 1
        con.commit()
        ok += 1
        filas_nuevas += n
        if i % 25 == 0 or n:
            print(f"  [{i}/{len(papeles)}] {ticker:<9} {sym:<10} +{n} ruedas")
        time.sleep(a.sleep)

    print(f"\n  con datos: {ok} | sin datos: {vacios} | ruedas nuevas: {filas_nuevas}")
    tot = cur.execute("SELECT COUNT(*) FROM precios_diarios").fetchone()[0]
    tk = cur.execute("SELECT COUNT(DISTINCT ticker) FROM precios_diarios").fetchone()[0]
    rng = cur.execute("SELECT MIN(fecha), MAX(fecha) FROM precios_diarios").fetchone()
    print(f"  precios_diarios: {tot} filas | {tk} tickers | {rng[0]} .. {rng[1]}")
    con.close()
    print("\nFASE 3B -- OK")


if __name__ == "__main__":
    main()
