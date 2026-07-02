"""Find correct IFRS tags for ADR companies and compare with CNV+YF"""
import sqlite3
from collections import defaultdict

db = sqlite3.connect('data/screener.db')

TICKER = 'GGAL'
CIK = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg'", (TICKER,)).fetchone()[0]
print(f"{TICKER}: CIK={CIK}")

# 1. See ALL tags available for GGAL in EDGAR IFRS
print("\n=== IFRS tags for GGAL (sample) ===")
cur = db.execute("""
    SELECT tag, taxonomia, COUNT(*) as n, MIN(period_end), MAX(period_end)
    FROM facts WHERE cik=?
    GROUP BY tag, taxonomia
    ORDER BY n DESC
""", (CIK,))
all_tags = cur.fetchall()
print(f"Total distinct tags: {len(all_tags)}")

# Find income/profit tags
print("\n--- Profit/Loss related tags ---")
for t, tax, n, mn, mx in all_tags:
    if any(k in t for k in ['Profit', 'Loss', 'Income', 'Earnings', 'Dividend', 'Revenue', 'Sales']):
        print(f"  {t:<55} {tax:<12} n={n:<4} {mn} -> {mx}")

# 2. Get the actual IFRS data for NetIncome equivalent  
print(f"\n=== IFRS raw data: ProfitLoss and DividendsPaid ===")
ni_tag = None
for t_name in ['ProfitLoss', 'ProfitLossForThePeriod', 'NetIncome', 'ProfitLossAttributableToEquityHoldersOfParent']:
    cur = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND tag=?", (CIK, t_name))
    if cur.fetchone()[0] > 0:
        ni_tag = t_name
        break

div_tag = None
for d_name in ['DividendsPaidOrdinaryShares', 'DividendsPaidClassifiedAsFinancingActivities', 'DividendsPaid']:
    cur = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND tag=?", (CIK, d_name))
    if cur.fetchone()[0] > 0:
        div_tag = d_name
        break

print(f"NetIncome tag: {ni_tag}")
print(f"Dividends tag: {div_tag}")

# 3. Get EDGAR data with correct tags
if ni_tag and div_tag:
    cur = db.execute("""
        SELECT tag, period_end, val FROM facts
        WHERE cik=? AND tag IN (?, ?)
        ORDER BY period_end, tag
    """, (CIK, ni_tag, div_tag))
    edgar_data = defaultdict(dict)
    for r in cur:
        edgar_data[r[1]][r[0]] = r[2]
    
    print(f"\nEDGAR periods: {len(edgar_data)}")
    print(f"{'Period':<15} {'NetIncome':>22} {'Dividends':>22} {'Payout':>12}")
    for pe in sorted(edgar_data):
        d = edgar_data[pe]
        ni = d.get(ni_tag)
        div = d.get(div_tag)
        if ni and div:
            payout = div / ni * 100
            print(f"{pe:<15} {ni:>22,.0f} {div:>22,.0f} {payout:>11.1f}%")
        elif ni:
            print(f"{pe:<15} {ni:>22,.0f} {'N/A':>22}")

# 4. Compare with YFinance (for GGAL, check if yfinance data exists under this CIK)
print(f"\n=== YFinance for GGAL ===")
cur = db.execute("""
    SELECT tag, COUNT(*) FROM facts WHERE cik=? AND taxonomia='yfinance'
    GROUP BY tag ORDER BY tag
""", (CIK,))
yf_tags = cur.fetchall()
print(f"YFinance tags: {len(yf_tags)}")
if yf_tags:
    for t, n in yf_tags[:5]:
        print(f"  {t}: {n}")
    # Get actual data
    cur = db.execute("""
        SELECT tag, period_end, val FROM facts
        WHERE cik=? AND taxonomia='yfinance' 
        ORDER BY period_end, tag
    """, (CIK,))
    yf_data = defaultdict(dict)
    for r in cur:
        yf_data[r[1]][r[0]] = r[2]
    print(f"YF periods: {len(yf_data)}")
    for pe in sorted(yf_data):
        d = yf_data[pe]
        ni = d.get('Net Income', '-')
        div = d.get('Cash Dividends Paid', d.get('Common Stock Dividend Paid', '-'))
        ni_s = f"{ni:>22,.0f}" if isinstance(ni, float) else str(ni)
        div_s = f"{div:>22,.0f}" if isinstance(div, float) else str(div)
        print(f"  {pe:<15} NI={ni_s}  Div={div_s}")
else:
    print("  No yfinance data for GGAL under this CIK")

# 5. CNV data for GGAL
print(f"\n=== CNV for GGAL ===")
cur = db.execute("""
    SELECT concepto, period_end, valor FROM cnv_estados
    WHERE ticker=? AND concepto IN ('NetIncome', 'Revenue', 'EPS_basico')
    ORDER BY period_end, concepto
""", (TICKER,))
cnv_data = defaultdict(dict)
for r in cur:
    cnv_data[r[1]][r[0]] = r[2]
print(f"CNV periods: {len(cnv_data)}")
for pe in sorted(cnv_data):
    d = cnv_data[pe]
    ni = d.get('NetIncome', '-')
    rev = d.get('Revenue', '-')
    eps = d.get('EPS_basico', '-')
    ni_s = f"{ni:>22,.0f}" if isinstance(ni, float) else str(ni)
    rev_s = f"{rev:>22,.0f}" if isinstance(rev, float) else str(rev)
    eps_s = f"{eps:>12,.2f}" if isinstance(eps, float) else str(eps)
    print(f"  {pe:<15} NI={ni_s}  Rev={rev_s}  EPS={eps_s}")

db.close()
