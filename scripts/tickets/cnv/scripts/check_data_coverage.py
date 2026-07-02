"""Investigate what data we actually have for ADR vs BYMA tickers"""
import sqlite3
from collections import defaultdict

db = sqlite3.connect('data/screener.db')

# 1. What tickers are in cnv_estados?
cur = db.execute("""
    SELECT ticker, COUNT(*) as n, COUNT(DISTINCT concepto) as concepts, 
           COUNT(DISTINCT CASE WHEN concepto='NetIncome' THEN 1 END) as has_ni
    FROM cnv_estados WHERE fuente LIKE 'cnv-%'
    GROUP BY ticker ORDER BY ticker
""")
cnv_tickers = {r[0]: r for r in cur.fetchall()}
print(f"CNV tickers: {len(cnv_tickers)}")

# 2. What ADR companies do we have?
cur = db.execute("SELECT ticker_ppal, cik, nombre FROM empresas WHERE grupo='adr_arg' ORDER BY ticker_ppal")
adrs = cur.fetchall()
print(f"\nADR companies: {len(adrs)}")
for t, cik, name in adrs:
    in_cnv = t in cnv_tickers
    cnv_info = cnv_tickers.get(t, (0,0,0))
    # Check facts
    cur2 = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND tag='NetIncome'", (cik,))
    f_ni = cur2.fetchone()[0]
    cur2 = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND tag='CashDividendsPaid'", (cik,))
    f_div = cur2.fetchone()[0]
    # Also check by ticker_ppal directly in facts 
    cur2 = db.execute("SELECT COUNT(*) FROM facts WHERE cik=?", (cik,))
    f_total = cur2.fetchone()[0]
    print(f"  {t:<8} CIK={cik:<15} CNV={in_cnv:<5} f_total={f_total:<5} f_NI={f_ni:<3} f_Div={f_div:<3} {name[:40]}")

# 3. Check yfinance data - which CIKs have yfinance facts?
print(f"\n--- YFinance data coverage ---")
cur = db.execute("""
    SELECT cik, COUNT(*) as n FROM facts 
    WHERE taxonomia='yfinance' GROUP BY cik ORDER BY n DESC LIMIT 10
""")
for r in cur:
    tk = db.execute("SELECT ticker_ppal FROM empresas WHERE cik=?", (r[0],)).fetchone()
    tk_name = tk[0] if tk else 'UNKNOWN'
    print(f"  CIK={r[0]:<15} {tk_name:<8} n_facts={r[1]}")

# 4. Check all CIKs in facts
cur = db.execute("SELECT COUNT(DISTINCT cik) FROM facts")
print(f"\nUnique CIKs in facts: {cur.fetchone()[0]}")

# 5. Check GGAL specifically
print(f"\n--- GGAL deep check ---")
for tk in ['GGAL', 'GGAL.BA', 'GGAL']:
    cur = db.execute("SELECT cik, ticker_ppal, nombre, grupo FROM empresas WHERE ticker_ppal=?", (tk,))
    for r in cur:
        print(f"  empresas: CIK={r[0]} ticker={r[1]} name={r[2][:40]} grupo={r[3]}")
        cur2 = db.execute("SELECT taxonomia, tag, COUNT(*) FROM facts WHERE cik=? GROUP BY taxonomia, tag ORDER BY COUNT(*) DESC LIMIT 10", (r[0],))
        for r2 in cur2:
            print(f"    facts: tax={r2[0]:<15} tag={r2[1]:<40} count={r2[2]}")

# 6. Check what yfinance data exists for BYMA companies
print(f"\n--- BYMA tickers with yfinance ---")
cur = db.execute("SELECT ticker_ppal, cik FROM empresas WHERE grupo='byma_yf' ORDER BY ticker_ppal")
byma = cur.fetchall()
print(f"Total byma_yf: {len(byma)}")
for tk, cik in byma[:10]:
    cur2 = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND taxonomia='yfinance'", (cik,))
    n = cur2.fetchone()[0]
    print(f"  {tk:<8} CIK={cik:<15} yf_facts={n}")

# 7. Check the original byma_yf CIK format
print(f"\n--- BYMA CIK pattern ---")
cur = db.execute("SELECT ticker_ppal, cik FROM empresas WHERE grupo='byma_yf' LIMIT 5")
for r in cur:
    print(f"  {r[0]}: {r[1]}")

db.close()
