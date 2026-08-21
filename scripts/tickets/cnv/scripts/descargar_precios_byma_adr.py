"""
Download current prices via YFinance for 56 BYMA + 9 ADR tickers.
Stores in `precios` table.
"""
import sqlite3, time, json
from pathlib import Path
from datetime import datetime
import yfinance as yf

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = BASE / "data" / _os.environ.get("SCREENER_DB", "screener.db")
LOG_FILE = BASE / "data" / "log_precios_byma_adr.txt"

DELAY = 1.0  # seconds between tickers to avoid rate limiting

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Ensure precios table exists
    cur.execute("""CREATE TABLE IF NOT EXISTS precios (
        cik TEXT PRIMARY KEY,
        ticker TEXT,
        precio REAL,
        market_cap REAL,
        year_high REAL,
        year_low REAL,
        currency TEXT,
        fecha TEXT
    )""")

    # Get BYMA tickers (grupo='byma_yf')
    cur.execute("SELECT ticker_ppal, cik, nombre FROM empresas WHERE grupo = 'byma_yf'")
    byma = {r[0]: {'cik': r[1], 'nombre': r[2]} for r in cur.fetchall()}

    # Get ADR tickers (grupo='adr_arg') - only our 9
    adr_9 = {'GGAL','BBAR','CEPU','CRESY','EDN','LOMA','PAM','SUPV','TEO'}
    cur.execute("SELECT ticker_ppal, cik, nombre FROM empresas WHERE grupo = 'adr_arg'")
    adr = {r[0]: {'cik': r[1], 'nombre': r[2]} for r in cur.fetchall() if r[0] in adr_9}

    stats = {'byma_ok': 0, 'byma_err': 0, 'adr_ok': 0, 'adr_err': 0}
    now = datetime.now().isoformat()

    # --- BYMA (need .BA suffix) ---
    log(f"BYMA tickers: {len(byma)}")
    for ticker in sorted(byma.keys()):
        info = byma[ticker]
        yf_ticker = f"{ticker}.BA"
        cik = info['cik']
        nombre = info['nombre'][:30]

        try:
            fi = yf.Ticker(yf_ticker).fast_info
            price = getattr(fi, 'last_price', None)
            year_high = getattr(fi, 'year_high', None)
            year_low = getattr(fi, 'year_low', None)
            market_cap = getattr(fi, 'market_cap', None)
            currency = getattr(fi, 'currency', 'ARS')

            if price is not None:
                cur.execute("""INSERT OR REPLACE INTO precios
                    (cik, ticker, precio, market_cap, year_high, year_low, currency, fecha)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (cik, ticker, price, market_cap, year_high, year_low, currency, now))
                stats['byma_ok'] += 1
            else:
                stats['byma_err'] += 1
                log(f"  {ticker:<8} {nombre:<30} NO PRICE")
        except Exception as e:
            stats['byma_err'] += 1

        if (stats['byma_ok'] + stats['byma_err']) % 20 == 0:
            con.commit()

        time.sleep(DELAY)

    con.commit()

    # --- ADR (direct ticker, USD) ---
    log(f"ADR tickers: {len(adr)}")
    for ticker in sorted(adr.keys()):
        info = adr[ticker]
        cik = info['cik']
        nombre = info['nombre'][:30]

        try:
            fi = yf.Ticker(ticker).fast_info
            price = getattr(fi, 'last_price', None)
            year_high = getattr(fi, 'year_high', None)
            year_low = getattr(fi, 'year_low', None)
            market_cap = getattr(fi, 'market_cap', None)
            currency = getattr(fi, 'currency', 'USD')

            if price is not None:
                cur.execute("""INSERT OR REPLACE INTO precios
                    (cik, ticker, precio, market_cap, year_high, year_low, currency, fecha)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (cik, ticker, price, market_cap, year_high, year_low, currency, now))
                stats['adr_ok'] += 1
            else:
                stats['adr_err'] += 1
                log(f"  {ticker:<8} {nombre:<30} NO PRICE")
        except Exception as e:
            stats['adr_err'] += 1
            log(f"  {ticker:<8} {nombre:<30} ERROR {e}")

        time.sleep(DELAY)

    con.commit()

    log(f"\nBYMA: OK={stats['byma_ok']} ERR={stats['byma_err']}")
    log(f"ADR:  OK={stats['adr_ok']} ERR={stats['adr_err']}")
    log(f"Total nuevos precios: {stats['byma_ok'] + stats['adr_ok']}")
    con.close()

if __name__ == '__main__':
    main()
