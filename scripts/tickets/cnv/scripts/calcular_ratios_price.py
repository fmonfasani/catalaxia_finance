"""
Calcular ratios price-based: PER, P/B, EV/EBITDA, Dividend Yield.

BYMA (56): todos los datos en ARS, consistentes.
ADR (9): precio en USD, datos contables en ARS → requiere FX.
"""
import sqlite3
from pathlib import Path
from collections import defaultdict

DB = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "screener.db"
con = sqlite3.connect(DB)
cur = con.cursor()

ADR_9 = ('GGAL','BBAR','CEPU','CRESY','EDN','LOMA','PAM','SUPV','TEO')

def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b

def sum_quarterly_to_annual(data):
    annual = defaultdict(float)
    for pe, val in data.items():
        yr = str(pe)[:4]
        if yr:
            annual[yr] += val
    return dict(annual)

# ═══════════════════════════════════════════════════════════════════════
# Pre-carga datos BYMA
# ═══════════════════════════════════════════════════════════════════════
cur.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
all_byma = [r[0] for r in cur.fetchall()]

# Prices: {ticker: {precio, market_cap, year_high, year_low, currency}}
prices = {}
for t in all_byma + list(ADR_9):
    cur.execute("SELECT precio, market_cap, currency, year_high, year_low FROM precios WHERE ticker=?", (t,))
    r = cur.fetchone()
    if r:
        prices[t] = {'price': r[0], 'mcap': r[1], 'cur': r[2], 'hi': r[3], 'lo': r[4]}

# EPS: {ticker: {year: eps_diluted}}
eps = {}
for t in all_byma:
    cur.execute("SELECT period_end, val FROM facts f JOIN empresas e ON f.cik=e.cik WHERE e.ticker_ppal=? AND f.taxonomia='yfinance' AND f.concepto='EPS_diluted' ORDER BY period_end", (t,))
    eps[t] = {str(r[0])[:4]: r[1] for r in cur.fetchall()}

# SharesOutstanding: {ticker: {year: shares}}
shares = {}
for t in all_byma:
    cur.execute("SELECT period_end, val FROM facts f JOIN empresas e ON f.cik=e.cik WHERE e.ticker_ppal=? AND f.taxonomia='yfinance' AND f.concepto='SharesOutstanding' ORDER BY period_end", (t,))
    shares[t] = {str(r[0])[:4]: r[1] for r in cur.fetchall()}

# CNV Equity, EBITDA, Debt, Cash: {ticker: {year: annual_sum}}
cnv_data = {}
for conc in ['Equity', 'EBITDA', 'DebtCurrent', 'DebtNonCurrent', 'Cash']:
    cnv_data[conc] = {}
    for t in all_byma:
        cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto=? AND fuente='cnv-aif2' ORDER BY period_end", (t, conc))
        vals = {r[0]: r[1] for r in cur.fetchall()}
        cnv_data[conc][t] = sum_quarterly_to_annual(vals) if conc != 'Equity' else {str(pe)[:4]: val for pe, val in vals.items()}

# YF Dividends
yf_div = {}
cur.execute("""
    SELECT e.ticker_ppal, f.period_end, f.val FROM facts f JOIN empresas e ON f.cik=e.cik
    WHERE f.taxonomia='yfinance' AND f.concepto='Dividends' AND f.val IS NOT NULL
""")
for t, pe, val in cur.fetchall():
    yr = str(pe)[:4]
    yf_div.setdefault(t, {})[yr] = abs(val)

# Precio y EPS ADR (CNV)
adr_eps = {}
adr_equity = {}
for t in ADR_9:
    cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto='EPS_Basic' AND fuente='cnv-adr' ORDER BY period_end", (t,))
    adr_eps[t] = {str(r[0])[:4]: r[1] for r in cur.fetchall()}
    cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto='TotalEquity' AND fuente='cnv-adr' ORDER BY period_end", (t,))
    adr_equity[t] = {str(r[0])[:4]: r[1] for r in cur.fetchall()}

# ═══════════════════════════════════════════════════════════════════════
# 1. BYMA Price Ratios
# ═══════════════════════════════════════════════════════════════════════
print("=" * 120)
print("BYMA PRICE RATIOS")
print("=" * 120)
print(f"{'Ticker':<8} {'Price':>10} {'EPS':>10} {'PER':>8} {'BVPS':>12} {'P/B':>8} {'EV/EBITDA':>11} {'DivYld':>8}")
print("-" * 85)

for t in sorted(all_byma):
    p = prices.get(t)
    if not p:
        continue

    price = p['price']
    # Use most recent year's data
    years = sorted(eps.get(t, {}).keys())
    if not years:
        continue
    yr = years[-1]

    eps_val = eps.get(t, {}).get(yr)
    sh = shares.get(t, {}).get(yr)
    equity = cnv_data['Equity'].get(t, {}).get(yr)
    ebitda = cnv_data['EBITDA'].get(t, {}).get(yr)
    dc = cnv_data['DebtCurrent'].get(t, {}).get(yr, 0) or 0
    dnc = cnv_data['DebtNonCurrent'].get(t, {}).get(yr, 0) or 0
    cash = cnv_data['Cash'].get(t, {}).get(yr, 0) or 0
    divs = yf_div.get(t, {}).get(yr)

    td = dc + dnc
    mcap = p['mcap']

    per = safe_div(price, eps_val)
    bvps = safe_div(equity, sh)
    pb = safe_div(price, bvps)
    ev = mcap + td - cash if mcap else None
    ev_ebitda = safe_div(ev, ebitda)
    div_yield = safe_div(divs, mcap) if divs else None

    per_s = f"{per:>7.1f}x" if per and per > 0 else "  N/A"
    pb_s = f"{pb:>7.2f}x" if pb and pb > 0 else "  N/A"
    ev_s = f"{ev_ebitda:>10.1f}x" if ev_ebitda and ev_ebitda > 0 else "   N/A"
    dy_s = f"{div_yield:>7.1%}" if div_yield else "   N/A"

    print(f"{t:<8} {price:>10,.2f} {eps_val if eps_val else 0:>10,.2f} {per_s:>8} {bvps if bvps else 0:>12,.2f} {pb_s:>8} {ev_s:>11} {dy_s:>8}")

# ═══════════════════════════════════════════════════════════════════════
# 2. ADR Price Ratios (CNV data in ARS, price in USD)
# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 120)
print("ADR PRICE RATIOS (9) - CNV ARS data, USD price => FX conversion needed")
print("=" * 120)
print(f"{'Ticker':<8} {'Price':>10} {'Cur':>5} {'EPS_ARS':>10} {'PER_USD':>9} {'BVPS':>12} {'P/B':>8} {'Note':<30}")
print("-" * 85)

for t in sorted(ADR_9):
    p = prices.get(t)
    if not p:
        continue

    price = p['price']
    cur = p['cur']

    # Use most recent year with EPS data
    years = sorted(adr_eps.get(t, {}).keys())
    if not years:
        print(f"{t:<8} {price:>10,.2f} {cur:>5} {'N/A':>10} {'N/A':>9} {'N/A':>12} {'N/A':>8} {'No EPS data':<30}")
        continue
    yr = years[-1]

    eps_val = adr_eps[t].get(yr)
    equity = adr_equity.get(t, {}).get(yr)

    # PER would need FX rate: PER = Price / (EPS_ARS / FX)
    # Without FX, we show EPS_ARS and note
    bvps = safe_div(equity, 1)  # Can't compute BVPS without shares outstanding
    pb = safe_div(price, bvps) if bvps else None

    print(f"{t:<8} {price:>10,.2f} {cur:>5} {eps_val if eps_val else 0:>10,.2f} {'FX needed':>9} {bvps if bvps else 0:>12,.2f} {'N/A':>8} {'EPS in ARS, price USD':<30}")

con.close()
print("\nDone.")
