"""Check where BYMA price data lives"""
import sqlite3

db = sqlite3.connect('data/screener.db')

# Get BYMA tickers
cur = db.execute("SELECT ticker_ppal, cik FROM empresas WHERE grupo='byma_yf'")
byma = cur.fetchall()
print(f"BYMA tickers: {len(byma)}")
print(f"CIK samples: {[r[1] for r in byma[:5]]}")

# Check precios table
print("\n--- Precios table (all tickers with data) ---")
cur = db.execute("SELECT ticker, precio, market_cap, year_high, year_low FROM precios ORDER BY ticker")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
byma_in_precios = [r for r in rows if r[0] in [b[0] for b in byma]]
print(f"BYMA in precios: {len(byma_in_precios)}")
if byma_in_precios:
    for r in byma_in_precios[:5]:
        print(f"  {r}")

# Check facts (yfinance) for BYMA - what yfinance tags exist?
print("\n--- Facts yfinance for BYMA ---")
for tk, cik in byma[:3]:
    cur = db.execute("SELECT COUNT(*), COUNT(DISTINCT tag) FROM facts WHERE cik=? AND taxonomia='yfinance'", (cik,))
    cnt, tags = cur.fetchone()
    print(f"  {tk} (cik={cik}): {cnt} datapoints, {tags} tags")
    if cnt > 0:
        cur2 = db.execute("SELECT DISTINCT tag FROM facts WHERE cik=? AND taxonomia='yfinance' LIMIT 10", (cik,))
        print(f"    tags: {[r[0] for r in cur2.fetchall()]}")
        cur2 = db.execute("SELECT MIN(period_end), MAX(period_end) FROM facts WHERE cik=? AND taxonomia='yfinance'", (cik,))
        md, xd = cur2.fetchone()
        print(f"    dates: {md} - {xd}")

# Check facts for price-like yfinance data across ALL BYMA
print("\n--- All BYMA with yfinance data ---")
ph = ','.join('?' * len(byma))
ciks = tuple(b[1] for b in byma)
cur = db.execute(f"SELECT f.cik, e.ticker_ppal, COUNT(*) as cnt FROM facts f JOIN empresas e ON f.cik=e.cik WHERE f.cik IN ({ph}) AND f.taxonomia='yfinance' GROUP BY f.cik ORDER BY cnt DESC", ciks)
rows = cur.fetchall()
print(f"BYMA with yfinance data: {len(rows)}/{len(byma)}")
for r in rows[:10]:
    print(f"  {r[1]:<8} {r[2]:>6} datapoints")

# List yfinance tags
cur = db.execute(f"SELECT DISTINCT tag FROM facts WHERE taxonomia='yfinance' AND cik IN ({ph}) ORDER BY tag", ciks)
yf_tags = [r[0] for r in cur.fetchall()]
print(f"\nYFinance tags for BYMA: {yf_tags}")

# Check for price (close, adjclose, etc.)
price_tags = ['close', 'adjclose', 'price', 'regularMarketPrice', 'currentPrice']
for pt in price_tags:
    cur = db.execute(f"SELECT COUNT(DISTINCT cik) FROM facts WHERE tag LIKE '%{pt}%' AND cik IN ({ph})", ciks)
    cnt = cur.fetchone()[0]
    print(f"  Tag containing '{pt}': {cnt} tickers")

db.close()
