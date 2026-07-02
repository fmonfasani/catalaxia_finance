"""Find what CNV data exists for ADR companies"""
import sqlite3
db = sqlite3.connect('data/screener.db')

# 1. All CNV tickers
cur = db.execute("SELECT DISTINCT ticker FROM cnv_estados WHERE fuente LIKE 'cnv-%' ORDER BY ticker")
all_cnv = [r[0] for r in cur]
print(f"All CNV tickers ({len(all_cnv)}):")
print(f"  {', '.join(all_cnv)}")

# 2. ADR companies' CNV data
cur = db.execute("SELECT DISTINCT ticker_ppal FROM empresas WHERE grupo='adr_arg' ORDER BY ticker_ppal")
adr_tickers = [r[0] for r in cur]
print(f"\nADR tickers: {adr_tickers}")

# Check each ADR ticker in CNV
for tk in adr_tickers:
    cur = db.execute("SELECT COUNT(*) FROM cnv_estados WHERE ticker=?", (tk,))
    cnt = cur.fetchone()[0]
    cur = db.execute("SELECT COUNT(DISTINCT concepto) FROM cnv_estados WHERE ticker=? AND concepto='NetIncome'", (tk,))
    has_ni = cur.fetchone()[0]
    if cnt > 0:
        cur = db.execute("SELECT COUNT(DISTINCT concepto) FROM cnv_estados WHERE ticker=?", (tk,))
        n_concepts = cur.fetchone()[0]
        cur = db.execute("SELECT MIN(period_end), MAX(period_end) FROM cnv_estados WHERE ticker=?", (tk,))
        rng = cur.fetchone()
        print(f"  {tk:<6}: {cnt:>5} filas, {n_concepts:>2} conceptos, NetIncome={has_ni}, range={rng[0]} -> {rng[1]}")
    else:
        print(f"  {tk:<6}: NO CNV data")

# 3. For comparison: BYMA-only companies  
cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf' ORDER BY ticker_ppal")
byma_only = [r[0] for r in cur]
print(f"\nBYMA-only companies: {len(byma_only)}")
print(f"  First 10: {byma_only[:10]}")

# Check how many have NetIncome
cur = db.execute("SELECT COUNT(DISTINCT ticker) FROM cnv_estados WHERE concepto='NetIncome'")
print(f"Tickers with NetIncome in CNV: {cur.fetchone()[0]}")

# 4. For ALL tickers, show what's available
print(f"\n=== Best ADR candidates for cross-reference ===")
for tk in adr_tickers:
    cik = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg'", (tk,)).fetchone()
    if not cik:
        continue
    cik = cik[0]
    
    # EDGAR ProfitLoss
    cur = db.execute("""
        SELECT COUNT(*) FROM facts WHERE cik=? AND tag='ProfitLoss'
          AND taxonomia NOT LIKE 'yfinance'
    """, (cik,))
    edgar_ni = cur.fetchone()[0]
    
    # YFinance
    cur = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND taxonomia='yfinance'", (cik,))
    yf_total = cur.fetchone()[0]
    
    # CNV NetIncome  
    cur = db.execute("SELECT COUNT(*) FROM cnv_estados WHERE ticker=? AND concepto='NetIncome'", (tk,))
    cnv_ni = cur.fetchone()[0]
    
    # CNV total
    cur = db.execute("SELECT COUNT(*) FROM cnv_estados WHERE ticker=?", (tk,))
    cnv_total = cur.fetchone()[0]
    
    print(f"  {tk:<6}: EDGAR_NI={edgar_ni}  YF_total={yf_total}  CNV_ni={cnv_ni}  CNV_total={cnv_total}")

db.close()
