"""Comparar 13 ratios CNV vs YFinance para ALUA"""
import sqlite3
import math
from datetime import datetime, date

db = sqlite3.connect('data/screener.db')

TICKER = 'ALUA'
print(f"=== Comparacion 13 ratios: {TICKER} ===")
print()

# ---- 1. PRECIO (misma fuente para ambos) ----
# Intentar desde yfinance API
import yfinance as yf
try:
    tk = yf.Ticker(TICKER + ".BA")  # BYMA ticker
    info = tk.info
    precio = info.get('currentPrice') or info.get('regularMarketPrice')
    max52 = info.get('fiftyTwoWeekHigh')
    min52 = info.get('fiftyTwoWeekLow')
    currency = info.get('currency', 'ARS')
    print(f"Precio: {precio} {currency}")
    print(f"Max 52 sem: {max52}")
    print(f"Min 52 sem: {min52}")
    print()
except Exception as e:
    print(f"No se pudo obtener precio YFinance: {e}")
    precio = max52 = min52 = currency = None

# ---- 2. DATOS CNV ----
cur = db.execute("""
    SELECT concepto, period_end, valor FROM cnv_estados 
    WHERE ticker=? AND fuente LIKE 'cnv-%'
    ORDER BY period_end
""", (TICKER,))

cnv_raw = {}
for r in cur.fetchall():
    conc, pe, val = r
    cnv_raw.setdefault(conc, []).append((pe, val))

# Get latest period
latest_period = max(cnv_raw.get('Revenue', []) + cnv_raw.get('NetIncome', []) + cnv_raw.get('EPS_basico', []), key=lambda x: x[0])[0]
print(f"CNV latest period: {latest_period}")

def latest(cnv_raw, concept, period=latest_period):
    vals = cnv_raw.get(concept, [])
    for pe, v in sorted(vals, reverse=True):
        if pe <= period:
            return v
    return None

def get_year(cnv_raw, concept, year):
    """Get value for a specific year (approximate - find closest to year-end)"""
    vals = [v for v in cnv_raw.get(concept, []) if v[0].startswith(str(year))]
    if vals:
        return max(vals, key=lambda x: x[0])[1]  # latest in that year
    return None

def cagr(start_val, end_val, years):
    if start_val and end_val and start_val > 0 and years > 0:
        return (end_val / start_val) ** (1/years) - 1
    return None

# Latest CNV values
cnv_netincome = latest(cnv_raw, 'NetIncome')
cnv_revenue = latest(cnv_raw, 'Revenue')
cnv_eps = latest(cnv_raw, 'EPS_basico')
cnv_ebitda = latest(cnv_raw, 'EBITDA')
cnv_debt_c = latest(cnv_raw, 'DebtCurrent')
cnv_debt_nc = latest(cnv_raw, 'DebtNonCurrent')
cnv_equity = latest(cnv_raw, 'Equity')
cnv_cf_op = latest(cnv_raw, 'CF_Operativo')
cnv_cf_inv = latest(cnv_raw, 'CF_Inversion')

# EPS 5 years ago for CAGR
latest_year = int(latest_period[:4])
cnv_eps_5y = get_year(cnv_raw, 'EPS_basico', latest_year - 5)
cnv_revenue_5y = get_year(cnv_raw, 'Revenue', latest_year - 5)
cnv_ni_5y = get_year(cnv_raw, 'NetIncome', latest_year - 5)
cnv_equity_5y = get_year(cnv_raw, 'Equity', latest_year - 5)

# Dividends - check if available in cnv_estados
cnv_dividends = latest(cnv_raw, 'Dividends') or latest(cnv_raw, 'CashDividendsPaid')

# Calculate CNV ratios
cnv_deuda_ebitda = (cnv_debt_c + cnv_debt_nc) / cnv_ebitda if all([cnv_debt_c, cnv_debt_nc, cnv_ebitda, cnv_ebitda != 0]) else None
cnv_margen_neto = cnv_netincome / cnv_revenue if all([cnv_netincome, cnv_revenue, cnv_revenue != 0]) else None
cnv_roe = cnv_netincome / cnv_equity if all([cnv_netincome, cnv_equity, cnv_equity != 0]) else None
cnv_eps_cagr = cagr(cnv_eps_5y, cnv_eps, 5)
cnv_fcf = (cnv_cf_op or 0) + (cnv_cf_inv or 0)  # CF_Operativo + CF_Inversion
cnv_ce = (cnv_equity or 0) + (cnv_debt_nc or 0)  # Equity + Deuda LP
cnv_fcf_ce = cnv_fcf / cnv_ce if cnv_ce and cnv_ce != 0 else None
cnv_payout = cnv_dividends / cnv_netincome if all([cnv_dividends, cnv_netincome, cnv_netincome != 0]) else None

# ---- 3. DATOS YFINANCE ----
cik = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=?", (TICKER,)).fetchone()[0]

cur = db.execute("""
    SELECT tag, period_end, val FROM facts
    WHERE cik=? AND taxonomia='yfinance'
    ORDER BY period_end
""", (cik,))

yf_raw = {}
for r in cur.fetchall():
    tag, pe, val = r
    yf_raw.setdefault(tag, []).append((pe, val))

def yf_latest(yf_raw, tag):
    vals = yf_raw.get(tag, [])
    return max(vals, key=lambda x: x[0])[1] if vals else None

def yf_year(yf_raw, tag, year):
    vals = [v for v in yf_raw.get(tag, []) if v[0].startswith(str(year))]
    return max(vals, key=lambda x: x[0])[1] if vals else None

yf_revenue = yf_latest(yf_raw, 'Total Revenue')
yf_netincome = yf_latest(yf_raw, 'Net Income')
yf_eps = yf_latest(yf_raw, 'Basic EPS')
yf_ebitda = yf_latest(yf_raw, 'EBITDA')
yf_debt_c = yf_latest(yf_raw, 'Current Debt')
yf_debt_nc = yf_latest(yf_raw, 'Long Term Debt')
yf_equity = yf_latest(yf_raw, 'Total Equity Gross Minority Interest')
yf_cf_op = yf_latest(yf_raw, 'Operating Cash Flow')
yf_cf_inv = yf_latest(yf_raw, 'Investing Cash Flow')
yf_dividends = yf_latest(yf_raw, 'Cash Dividends Paid') or yf_latest(yf_raw, 'Common Stock Dividend Paid')

# 5 years ago
yf_years = sorted(set(pe[:4] for tag_vals in yf_raw.values() for pe, v in tag_vals))
yf_latest_year = max(yf_years) if yf_years else latest_year
yf_eps_5y = yf_year(yf_raw, 'Basic EPS', int(yf_latest_year) - 5)
yf_revenue_5y = yf_year(yf_raw, 'Total Revenue', int(yf_latest_year) - 5)
yf_ni_5y = yf_year(yf_raw, 'Net Income', int(yf_latest_year) - 5)
yf_equity_5y = yf_year(yf_raw, 'Total Equity Gross Minority Interest', int(yf_latest_year) - 5)

yf_period = max(max([pe for pe,v in yf_raw.get('Total Revenue', [])], default=''), 
                max([pe for pe,v in yf_raw.get('Net Income', [])], default=''))
print(f"YF latest period: {yf_period}")
print()

# Calculate YFinance ratios
yf_deuda_ebitda = (yf_debt_c + yf_debt_nc) / yf_ebitda if all([yf_debt_c, yf_debt_nc, yf_ebitda, yf_ebitda != 0]) else None
yf_margen_neto = yf_netincome / yf_revenue if all([yf_netincome, yf_revenue, yf_revenue != 0]) else None
yf_roe = yf_netincome / yf_equity if all([yf_netincome, yf_equity, yf_equity != 0]) else None
yf_eps_cagr = cagr(yf_eps_5y, yf_eps, 5)
yf_fcf = (yf_cf_op or 0) + (yf_cf_inv or 0)
yf_ce = (yf_equity or 0) + (yf_debt_nc or 0)
yf_fcf_ce = yf_fcf / yf_ce if yf_ce and yf_ce != 0 else None
yf_payout = yf_dividends / yf_netincome if all([yf_dividends, yf_netincome, yf_netincome != 0]) else None

# ---- 4. COMPARACION ----
# Ratios that need price (same for both)
per_cnv = precio / cnv_eps if all([precio, cnv_eps, cnv_eps != 0]) else None
per_yf = precio / yf_eps if all([precio, yf_eps, yf_eps != 0]) else None
dif_max = (precio / max52 - 1) if all([precio, max52, max52 != 0]) else None
dif_min = (precio / min52 - 1) if all([precio, min52, min52 != 0]) else None

def pct(v):
    if v is None: return '-'
    return f"{v*100:.2f}%"
def num(v):
    if v is None: return '-'
    return f"{v:.2f}"

print("=" * 90)
print(f"{'Ratio':<30} {'CNV':>20} {'YFinance':>20} {'Diferencia':>15}")
print("=" * 90)

# 1. Precio
print(f"{'1. Precio u$s':<30} {num(precio):>20} {num(precio):>20} {'0%':>15}")

# 2. PER (precio compartido, difiere EPS)
diff_per = (per_cnv - per_yf) / per_yf * 100 if all([per_cnv, per_yf, per_yf != 0]) else None
print(f"{'2. PER':<30} {num(per_cnv):>20} {num(per_yf):>20} {pct(diff_per/100) if diff_per else '-':>15}")

# 3-6 Precios (iguales para ambos)
print(f"{'3. Max 52 sem':<30} {num(max52):>20} {num(max52):>20} {'0%':>15}")
print(f"{'4. Dif Max 52 sem':<30} {pct(dif_max):>20} {pct(dif_max):>20} {'0%':>15}")
print(f"{'5. Min 52 sem':<30} {num(min52):>20} {num(min52):>20} {'0%':>15}")
print(f"{'6. Dif Min 52 sem':<30} {pct(dif_min):>20} {pct(dif_min):>20} {'0%':>15}")

# 7. Deuda/EBITDA
diff_d_e = (cnv_deuda_ebitda - yf_deuda_ebitda)/yf_deuda_ebitda*100 if all([cnv_deuda_ebitda, yf_deuda_ebitda, yf_deuda_ebitda != 0]) else None
print(f"{'7. Deuda/EBITDA':<30} {num(cnv_deuda_ebitda):>20}x {num(yf_deuda_ebitda):>20}x {pct(diff_d_e/100) if diff_d_e else '-':>15}")

# 8. EPS Anual
diff_eps = (cnv_eps - yf_eps)/yf_eps*100 if all([cnv_eps, yf_eps, yf_eps != 0]) else None
print(f"{'8. EPS Anual':<30} {num(cnv_eps):>20} {num(yf_eps):>20} {pct(diff_eps/100) if diff_eps else '-':>15}")

# 9. Crecimiento EPS 5y
diff_eps_cagr = (cnv_eps_cagr - yf_eps_cagr) if all([cnv_eps_cagr, yf_eps_cagr]) else None
print(f"{'9. Crec. EPS 5y':<30} {pct(cnv_eps_cagr):>20} {pct(yf_eps_cagr):>20} {pct(diff_eps_cagr) if diff_eps_cagr else '-':>15}")

# 10. Margen Neto
diff_mn = cnv_margen_neto - yf_margen_neto if all([cnv_margen_neto, yf_margen_neto]) else None
print(f"{'10. Margen Neto':<30} {pct(cnv_margen_neto):>20} {pct(yf_margen_neto):>20} {pct(diff_mn) if diff_mn else '-':>15}")

# 11. ROE
diff_roe = cnv_roe - yf_roe if all([cnv_roe, yf_roe]) else None
print(f"{'11. ROE':<30} {pct(cnv_roe):>20} {pct(yf_roe):>20} {pct(diff_roe) if diff_roe else '-':>15}")

# 12. FCF/CE
diff_fcf = (cnv_fcf_ce - yf_fcf_ce) if all([cnv_fcf_ce, yf_fcf_ce]) else None
print(f"{'12. FCF/CE':<30} {pct(cnv_fcf_ce):>20} {pct(yf_fcf_ce):>20} {pct(diff_fcf) if diff_fcf else '-':>15}")

# 13. Payout
diff_payout = (cnv_payout - yf_payout) if all([cnv_payout, yf_payout]) else None
print(f"{'13. Payout':<30} {pct(cnv_payout):>20} {pct(yf_payout):>20} {pct(diff_payout) if diff_payout else '-':>15}")

print()
print("--- Inputs crudos ---")
print(f"{'Revenue':<30} {num(cnv_revenue):>20} {num(yf_revenue):>20}")
print(f"{'NetIncome':<30} {num(cnv_netincome):>20} {num(yf_netincome):>20}")
print(f"{'EPS':<30} {num(cnv_eps):>20} {num(yf_eps):>20}")
print(f"{'EBITDA':<30} {num(cnv_ebitda):>20} {num(yf_ebitda):>20}")
print(f"{'Deuda CP+LP':<30} {num((cnv_debt_c or 0)+(cnv_debt_nc or 0)):>20} {num((yf_debt_c or 0)+(yf_debt_nc or 0)):>20}")
print(f"{'Equity':<30} {num(cnv_equity):>20} {num(yf_equity):>20}")
print(f"{'CF_Operativo':<30} {num(cnv_cf_op):>20} {num(yf_cf_op):>20}")
print(f"{'CF_Inversion':<30} {num(cnv_cf_inv):>20} {num(yf_cf_inv):>20}")

db.close()
