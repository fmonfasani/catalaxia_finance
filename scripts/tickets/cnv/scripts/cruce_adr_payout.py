"""Cross-reference NetIncome + Dividends for an ADR: EDGAR vs YFinance vs CNV"""
import sqlite3
from collections import defaultdict

db = sqlite3.connect('data/screener.db')

# Find ADR companies and map to their CNV BYMA ticker
# BYMA tickers may differ from ADR tickers
cur = db.execute("""
    SELECT DISTINCT c.ticker FROM cnv_estados c
    WHERE c.fuente LIKE 'cnv-%'
    ORDER BY c.ticker
""")
byma_tickers = [r[0] for r in cur]
print(f"BYMA tickers in cnv_estados: {len(byma_tickers)}")

# For each ADR company, find the matching BYMA ticker
# ADR companies
cur = db.execute("SELECT ticker_ppal, cik, nombre FROM empresas WHERE grupo='adr_arg' ORDER BY ticker_ppal")
adrs = cur.fetchall()

adr_byma_map = {}
for at, cik, name in adrs:
    # Try exact match first
    if at in byma_tickers:
        adr_byma_map[at] = at
        print(f"  ADR {at:<6} -> BYMA {at:<6} (exact match)")
    else:
        # Try partial match (e.g., PAM -> PAMP)
        candidates = [b for b in byma_tickers if b.startswith(at[:3])]
        if candidates:
            adr_byma_map[at] = candidates[0]
            print(f"  ADR {at:<6} -> BYMA {candidates[0]:<6} (partial)")
        else:
            print(f"  ADR {at:<6} -> NO BYMA match found")

# Choose which test case
# First, check GGAL data availability
for test in ['GGAL', 'BMA', 'CEPU', 'EDN', 'LOMA']:
    byma_tk = adr_byma_map.get(test)
    if byma_tk:
        cnt_edgar = db.execute("SELECT COUNT(*) FROM facts WHERE cik=(SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg') AND taxonomia NOT LIKE 'yfinance' AND tag='NetIncome'", (test,)).fetchone()[0]
        cnt_cnv = db.execute("SELECT COUNT(*) FROM cnv_estados WHERE ticker=? AND concepto='NetIncome' AND fuente LIKE 'cnv-%'", (byma_tk,)).fetchone()[0]
        cnt_yf = db.execute("SELECT COUNT(*) FROM facts WHERE cik=(SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg') AND taxonomia='yfinance' AND tag='Net Income'", (test,)).fetchone()[0]
        print(f"  {test:<6} (BYMA={byma_tk:<6}): EDGAR_NI={cnt_edgar}  YF_NI={cnt_yf}  CNV_NI={cnt_cnv}")

# Pick best test case
TICKER = 'GGAL'
BYMA_TICKER = adr_byma_map.get(TICKER, TICKER)
print(f"\n=== TEST CASE: ADR={TICKER}  BYMA={BYMA_TICKER} ===")

CIK = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg'", (TICKER,)).fetchone()[0]
print(f"CIK (EDGAR): {CIK}")

# ---- 1. EDGAR DATA ----
print(f"\n--- EDGAR (SEC) ---")
cur = db.execute("""
    SELECT tag, period_end, val FROM facts
    WHERE cik=? AND taxonomia NOT LIKE 'yfinance'
      AND tag IN ('NetIncome', 'NetIncomeAvailableToCommonStockholders',
                  'CashDividendsPaid', 'CommonStockDividendsPerShareDeclared',
                  'Revenue', 'EarningsPerShareBasic')
    ORDER BY period_end, tag
""", (CIK,))
edgar = defaultdict(dict)
for r in cur:
    edgar[r[1]][r[0]] = r[2]

print(f"{'Period':<15} {'Revenue':>18} {'NetIncome':>18} {'DivPaid':>18}")
for pe in sorted(edgar):
    d = edgar[pe]
    ni = d.get('NetIncome', d.get('NetIncomeAvailableToCommonStockholders', ''))
    rev = d.get('Revenue', '')
    div = d.get('CashDividendsPaid', '')
    if ni:
        print(f"{pe:<15} {rev:>18,.0f} {ni:>18,.0f} {div:>18,.0f}" if isinstance(div, float) else f"{pe:<15} {rev:>18,.0f} {ni:>18,.0f} {'N/A':>18}")

# ---- 2. YFINANCE DATA (via same CIK) ----
print(f"\n--- YFINANCE ---")
cur = db.execute("""
    SELECT tag, period_end, val FROM facts
    WHERE cik=? AND taxonomia='yfinance'
      AND tag IN ('Total Revenue', 'Net Income', 'Cash Dividends Paid', 'Common Stock Dividend Paid', 'Basic EPS')
    ORDER BY period_end, tag
""", (CIK,))
yf = defaultdict(dict)
for r in cur:
    yf[r[1]][r[0]] = r[2]

print(f"{'Period':<15} {'Revenue':>18} {'NetIncome':>18} {'DivPaid':>18} {'EPS':>12}")
for pe in sorted(yf):
    d = yf[pe]
    rev = d.get('Total Revenue', '-')
    ni = d.get('Net Income', '-')
    div = d.get('Cash Dividends Paid', d.get('Common Stock Dividend Paid', '-'))
    eps = d.get('Basic EPS', '-')
    rev_s = f"{rev:>18,.0f}" if isinstance(rev, float) else str(rev)
    ni_s = f"{ni:>18,.0f}" if isinstance(ni, float) else str(ni)
    div_s = f"{div:>18,.0f}" if isinstance(div, float) else str(div)
    eps_s = f"{eps:>12,.2f}" if isinstance(eps, float) else str(eps)
    print(f"{pe:<15} {rev_s:>18} {ni_s:>18} {div_s:>18} {eps_s:>12}")

# ---- 3. CNV DATA ----
print(f"\n--- CNV (AIF2) ---")
cur = db.execute("""
    SELECT concepto, period_end, valor FROM cnv_estados
    WHERE ticker=? AND concepto IN ('NetIncome', 'Revenue', 'EPS_basico')
      AND fuente LIKE 'cnv-%'
    ORDER BY period_end, concepto
""", (BYMA_TICKER,))
cnv = defaultdict(dict)
for r in cur:
    cnv[r[1]][r[0]] = r[2]

print(f"{'Period':<15} {'Revenue':>22} {'NetIncome':>22} {'EPS':>12}")
for pe in sorted(cnv):
    d = cnv[pe]
    rev = d.get('Revenue', '-')
    ni = d.get('NetIncome', '-')
    eps = d.get('EPS_basico', '-')
    rev_s = f"{rev:>22,.0f}" if isinstance(rev, float) else str(rev)
    ni_s = f"{ni:>22,.0f}" if isinstance(ni, float) else str(ni)
    eps_s = f"{eps:>12,.2f}" if isinstance(eps, float) else str(eps)
    print(f"{pe:<15} {rev_s:>22} {ni_s:>22} {eps_s:>12}")

# ---- 4. CROSS-COMPARISON: Payout ----
print(f"\n=== PAYOUT RATIO CROSS-COMPARISON ===")
print(f"{'Period':<12} {'NI_EDGAR':>18} {'NI_YF':>16} {'NI_CNV':>16} {'DIV_EDGAR':>14} {'DIV_YF':>12} {'YF/CNV':>14} {'EDG/CNV':>16}")
print('-' * 120)

# Align by fiscal year
years = set()
for pe in list(edgar.keys()) + list(yf.keys()) + list(cnv.keys()):
    if pe and len(pe) >= 7:
        years.add(pe[:4])

for yr in sorted(years):
    def best(data_dict, target_yr):
        cands = [p for p in data_dict if p.startswith(target_yr)]
        return max(cands) if cands else None
    
    pe_e = best(edgar, yr)
    pe_y = best(yf, yr)
    pe_c = best(cnv, yr)
    
    ni_e = edgar.get(pe_e, {}).get('NetIncome', edgar.get(pe_e, {}).get('NetIncomeAvailableToCommonStockholders'))
    ni_y = yf.get(pe_y, {}).get('Net Income')
    ni_c = cnv.get(pe_c, {}).get('NetIncome')
    div_e = edgar.get(pe_e, {}).get('CashDividendsPaid')
    div_y = yf.get(pe_y, {}).get('Cash Dividends Paid') or yf.get(pe_y, {}).get('Common Stock Dividend Paid')
    
    py_cnv = div_y / ni_c if all([div_y, ni_c, ni_c != 0]) else None
    pe_cnv = div_e / ni_c if all([div_e, ni_c, ni_c != 0]) else None
    
    def f(v):
        if v is None: return '-'
        return f"{v/1e9:>16.2f}B" if abs(v) >= 1e9 else f"{v:>16,.0f}"
    def p(v):
        return '-' if v is None else f"{v*100:>13.1f}%"
    
    print(f"{yr:<12} {f(ni_e):>18} {f(ni_y):>16} {f(ni_c):>16} {f(div_e):>14} {f(div_y):>12} {p(py_cnv):>14} {p(pe_cnv):>16}")

db.close()
