"""Derive dividends from ResultadosNoAsignados difference between consecutive periods"""
import sqlite3
from collections import defaultdict

db = sqlite3.connect('data/screener.db')
TICKER = 'ALUA'

# 1. Get ResultadosNoAsignados and NetIncome for ALUA, ordered by period
cur = db.execute("""
    SELECT concepto, period_end, valor FROM cnv_estados 
    WHERE ticker=? AND concepto IN ('ResultadosNoAsignados', 'NetIncome', 'Reservas', 'Capital', 'Equity')
      AND fuente LIKE 'cnv-%'
    ORDER BY period_end, concepto
""", (TICKER,))

data = defaultdict(dict)
for r in cur:
    data[r[1]][r[0]] = r[2]

periods = sorted(data.keys())
print(f"ALUA: {len(periods)} periods with RE/NetIncome data")
print(f"Range: {periods[0]} to {periods[-1]}")
print()

print(f"{'Period':<15} {'RE_prev':>15} {'NetIncome':>15} {'RE':>15} {'Div_derived':>15} {'Reservas':>15} {'Equity':>15}")
print("-" * 105)

# Derive dividends for each consecutive pair
dividends_derived = []
prev_re = None
for pe in periods:
    d = data[pe]
    re = d.get('ResultadosNoAsignados')
    ni = d.get('NetIncome')
    reservas = d.get('Reservas')
    equity = d.get('Equity')
    
    if re is None or ni is None:
        prev_re = re
        continue
    
    if prev_re is not None:
        # Dividends = Previous_RE + NetIncome - Current_RE
        div = prev_re + ni - re
        dividends_derived.append((pe, div))
        print(f"{pe:<15} {prev_re:>15.0f} {ni:>15.0f} {re:>15.0f} {div:>15.2f} {reservas or 0:>15.0f} {equity or 0:>15.0f}")
    else:
        print(f"{pe:<15} {'-':>15} {ni:>15.0f} {re:>15.0f} {'-':>15} {reservas or 0:>15.0f} {equity or 0:>15.0f}")
    
    prev_re = re

print()
print("=== Dividends derived from RE difference ===")
for pe, div in dividends_derived:
    if abs(div) > 0:
        print(f"  {pe}: Dividends = {div:,.2f}")

# 2. Compare with YFinance dividends
cik = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=?", (TICKER,)).fetchone()[0]
cur = db.execute("""
    SELECT tag, period_end, val FROM facts
    WHERE cik=? AND taxonomia='yfinance' AND tag IN ('Cash Dividends Paid', 'Common Stock Dividend Paid', 'Net Income')
    ORDER BY period_end, tag
""", (cik,))

yf_data = defaultdict(dict)
for r in cur:
    yf_data[r[1]][r[0]] = r[2]

print(f"\n=== YFinance dividends for {TICKER} ===")
for pe in sorted(yf_data.keys()):
    d = yf_data[pe]
    div = d.get('Cash Dividends Paid') or d.get('Common Stock Dividend Paid')
    ni = d.get('Net Income')
    if div is not None:
        payout = div / ni * 100 if ni and ni != 0 else None
        print(f"  {pe}: Dividends={div:>15,.2f}  NetIncome={ni:>15,.2f}  Payout={payout:.1f}%" if payout else f"  {pe}: Dividends={div:>15,.2f}")

# 3. Try to align by fiscal year
print()
print("=== Comparison: Derived vs YFinance (annual periods only) ===")
# Group derived by year-end periods (June for ALUA)
derived_annual = {}
for pe, div in dividends_derived:
    year = pe[:4]
    month = pe[5:7]
    if month == '06':  # ALUA FYE = June
        derived_annual[year] = div

yf_annual = {}
for pe in sorted(yf_data.keys()):
    d = yf_data[pe]
    year = pe[:4]
    month = pe[5:7]
    if month == '06':
        div = d.get('Cash Dividends Paid') or d.get('Common Stock Dividend Paid')
        ni = d.get('Net Income')
        if div is not None:
            yf_annual[year] = (div, ni)

for year in sorted(set(list(derived_annual.keys()) + list(yf_annual.keys()))):
    d_derived = derived_annual.get(year)
    d_yf = yf_annual.get(year)
    d_yf_val = d_yf[0] if d_yf else None
    d_yf_ni = d_yf[1] if d_yf else None
    
    line = f"FY {year}: "
    if d_derived is not None:
        line += f"Derived={d_derived:>15,.2f}"
    else:
        line += f"{'Derived= N/A':>15}"
    if d_yf_val is not None:
        line += f"  YF={d_yf_val:>15,.2f}"
        if d_derived is not None and d_yf_val != 0:
            diff_pct = (d_derived - d_yf_val) / abs(d_yf_val) * 100
            line += f"  diff={diff_pct:+.1f}%"
    else:
        line += f"  {'YF=N/A':>15}"
    print(line)

db.close()
