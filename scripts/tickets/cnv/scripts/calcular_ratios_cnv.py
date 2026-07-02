"""
Calculate CNV-based ratios for 56 BYMA + 9 ADR.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "screener.db"
con = sqlite3.connect(DB)
db = con.cursor()

ADR_9 = ('GGAL','BBAR','CEPU','CRESY','EDN','LOMA','PAM','SUPV','TEO')

def get_cnv(ticker, concepto, source):
    db.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto=? AND fuente=? ORDER BY period_end", (ticker, concepto, source))
    return {r[0]: r[1] for r in db.fetchall()}

def get_price(ticker):
    db.execute("SELECT precio, year_high, year_low, market_cap, currency FROM precios WHERE ticker=?", (ticker,))
    return db.fetchone()

def safe_div(a, b):
    return a / b if b and b != 0 else None

def fmt_n(v):
    return f"{v:>7.1%}" if v is not None else "  N/A"
def fmt_x(v):
    return f"{v:>8.1f}x" if v is not None else "   N/A"
def fmt_f(v, d=2):
    return f"{v:>6.2f}" if v is not None else "  N/A"

# ===== BYMA =====
db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
byma = [r[0] for r in db.fetchall()]
print(f"BYMA: {len(byma)} tickers")
print(f"{'Ticker':<8} {'Period':<12} {'ROE':>7} {'ROA':>7} {'D/Ebitda':>9} {'NetMarg':>8} {'Liq':>6} {'Solv':>6} {'Price':>10}")
print("-"*73)

for t in byma:
    ni_d = get_cnv(t, 'NetIncome', 'cnv-aif2')
    eq_d = get_cnv(t, 'Equity', 'cnv-aif2')
    as_d = get_cnv(t, 'Assets', 'cnv-aif2')
    rev_d = get_cnv(t, 'Revenue', 'cnv-aif2')
    eb_d = get_cnv(t, 'EBITDA', 'cnv-aif2')
    dc_d = get_cnv(t, 'DebtCurrent', 'cnv-aif2')
    dn_d = get_cnv(t, 'DebtNonCurrent', 'cnv-aif2')
    ca_d = get_cnv(t, 'AssetsCurrent', 'cnv-aif2')
    cl_d = get_cnv(t, 'LiabilitiesCurrent', 'cnv-aif2')

    pdata = get_price(t)
    periods = sorted(set(ni_d.keys()) & set(eq_d.keys()) & set(as_d.keys()))
    if not periods or not pdata:
        continue

    p = periods[-1]
    ni, eq, ass = ni_d[p], eq_d[p], as_d[p]
    rev = rev_d.get(p)
    eb = eb_d.get(p)
    dc = dc_d.get(p, 0) or 0
    dnc = dn_d.get(p, 0) or 0
    td = dc + dnc
    cur_a = ca_d.get(p)
    cur_l = cl_d.get(p)
    price, _, _, mcap, currency = pdata

    roe = safe_div(ni, eq)
    roa = safe_div(ni, ass)
    debt_ebitda = safe_div(td, eb)
    net_margin = safe_div(ni, rev)
    liq = safe_div(cur_a, cur_l)
    solv = safe_div(eq, ass)

    print(f"{t:<8} {p:<12} {fmt_n(roe)} {fmt_n(roa)} {fmt_x(debt_ebitda)} {fmt_n(net_margin)} {fmt_f(liq)} {fmt_n(solv)} {price:>10,.2f}")

# ===== ADR =====
print(f"\nADR: 9 tickers")
print(f"{'Ticker':<8} {'Period':<12} {'ROE':>7} {'ROA':>7} {'D/Ebitda':>9} {'NetMarg':>8} {'Liq':>6} {'Solv':>6} {'Price':>9}")
print("-"*73)

for t in ADR_9:
    ni_d = get_cnv(t, 'NetIncome', 'cnv-adr')
    eq_d = get_cnv(t, 'TotalEquity', 'cnv-adr')
    as_d = get_cnv(t, 'TotalAssets', 'cnv-adr')
    rev_d = get_cnv(t, 'Revenue', 'cnv-adr')
    eb_d = get_cnv(t, 'EBITDA', 'cnv-adr')
    dc_d = get_cnv(t, 'FinancialDebtCurrent', 'cnv-adr')
    dn_d = get_cnv(t, 'FinancialDebtNonCurrent', 'cnv-adr')
    ca_d = get_cnv(t, 'TotalCurrentAssets', 'cnv-adr')
    cl_d = get_cnv(t, 'TotalCurrentLiabilities', 'cnv-adr')

    pdata = get_price(t)
    periods = sorted(set(ni_d.keys()) & set(eq_d.keys()) & set(as_d.keys()))
    if not periods or not pdata:
        continue

    p = periods[-1]
    ni, eq, ass = ni_d[p], eq_d[p], as_d[p]
    rev = rev_d.get(p)
    eb = eb_d.get(p)
    dc = dc_d.get(p, 0) or 0
    dnc = dn_d.get(p, 0) or 0
    td = dc + dnc
    cur_a = ca_d.get(p)
    cur_l = cl_d.get(p)
    price, _, _, mcap, currency = pdata

    roe = safe_div(ni, eq)
    roa = safe_div(ni, ass)
    debt_ebitda = safe_div(td, eb)
    net_margin = safe_div(ni, rev)
    liq = safe_div(cur_a, cur_l)
    solv = safe_div(eq, ass)

    print(f"{t:<8} {p:<12} {fmt_n(roe)} {fmt_n(roa)} {fmt_x(debt_ebitda)} {fmt_n(net_margin)} {fmt_f(liq)} {fmt_n(solv)} {price:>9.2f}")

# ===== PAYOUT BYMA =====
print(f"\n{'='*60}")
print("PAYOUT RATIO")
print(f"{'='*60}\n")
print("--- BYMA (YFinance Cash Dividends Paid / CNV NetIncome) ---")
print(f"{'Ticker':<8} {'Year':>5} {'Dividends':>15} {'NetIncome':>15} {'Payout':>8}")
print("-"*55)

db.execute("SELECT e.ticker_ppal, f.period_end, f.val FROM facts f JOIN empresas e ON f.cik=e.cik WHERE f.taxonomia='yfinance' AND f.concepto='Dividends' AND f.val IS NOT NULL ORDER BY e.ticker_ppal, f.period_end")
for t, pe, val in db.fetchall():
    ni_d = get_cnv(t, 'NetIncome', 'cnv-aif2')
    div_year = pe[:4]
    ni = next((ni_d[p] for p in ni_d if p[:4] == div_year), None)
    payout = safe_div(abs(val), ni) if ni else None
    if payout:
        print(f"{t:<8} {div_year:>5} {abs(val):>15,.0f} {ni:>15,.0f} {payout:>7.1%}")

# ===== PAYOUT ADR =====
print(f"\n--- ADR (CNV FT-339 Dividends / CNV NetIncome x1000) ---")
print(f"{'Ticker':<8} {'Period':<12} {'Dividend':>15} {'NetInc*1000':>15} {'Payout':>8}")
print("-"*60)

for t in ADR_9:
    div_d = get_cnv(t, 'DividendAmount', 'cnv-adr')
    ni_d = get_cnv(t, 'NetIncome', 'cnv-adr')
    for pe in sorted(div_d.keys()):
        div_val = div_d[pe]
        # CNV NetIncome is in thousands ARS, dividends in actual ARS
        ni = ni_d.get(pe[:4] + '-12-31') or ni_d.get(pe[:4] + '-06-30') or next((ni_d[p] for p in ni_d if p[:4] == pe[:4]), None)
        payout = safe_div(div_val, ni * 1000) if ni else None
        if payout and payout < 2:  # reasonable payout range
            print(f"{t:<8} {pe:<12} {div_val:>15,.0f} {ni*1000:>15,.0f} {payout:>7.1%}")

con.close()
print("\nDone.")
