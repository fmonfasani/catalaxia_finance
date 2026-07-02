"""Cross-reference CNV vs YFinance data for 56 BYMA tickers"""
import sqlite3

db = sqlite3.connect('data/screener.db')

cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
byma = [r[0] for r in cur.fetchall()]
ph = ','.join('?' * len(byma))

print("=== Cobertura CNV vs YFinance ===")
print(f"{'Ticker':<8} {'CNV filas':>10} {'CNV conceptos':>15} {'YF filas':>10} {'YF tags':>10}")
print("-" * 55)

for tk in sorted(byma):
    cur = db.execute(f"SELECT COUNT(*), COUNT(DISTINCT concepto) FROM cnv_estados WHERE ticker=?", (tk,))
    cnv_f, cnv_c = cur.fetchone()
    
    cik = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=?", (tk,)).fetchone()
    if cik:
        cur = db.execute("SELECT COUNT(*), COUNT(DISTINCT tag) FROM facts WHERE cik=? AND taxonomia='yfinance'", (cik[0],))
        yf_f, yf_t = cur.fetchone()
    else:
        yf_f, yf_t = 0, 0
    
    print(f"{tk:<8} {cnv_f:>10} {cnv_c:>15} {yf_f:>10} {yf_t:>10}")

print()

# Show matching concepts
print("=== Mapeo CNV -> YFinance ===")
cnv_concepts = [
    'Revenue', 'NetIncome', 'EBITDA', 'Assets', 'Equity',
    'Cash', 'DebtCurrent', 'DebtNonCurrent', 'EPS_basico',
    'CF_Operativo', 'CF_Inversion', 'CF_Financiacion', 'CashFlowNeto'
]
yf_map = {
    'Revenue': 'TotalRevenue',
    'NetIncome': 'NetIncome',
    'EBITDA': 'EBITDA',
    'Assets': 'TotalAssets',
    'Equity': 'TotalEquityGrossMinorityInterest',
    'Cash': 'CashAndCashEquivalents',
    'DebtCurrent': 'CurrentDebt',
    'DebtNonCurrent': 'LongTermDebt',
    'EPS_basico': 'BasicEPS',
    'CF_Operativo': 'OperatingCashFlow',
    'CF_Inversion': 'InvestingCashFlow',
    'CF_Financiacion': 'FinancingCashFlow',
    'CashFlowNeto': 'ChangesInCash',
}

print(f"{'Concepto CNV':<20} {'Tag YFinance':<45} {'CNV':>8} {'YF':>8}")
print("-" * 83)
for cnv, yf in yf_map.items():
    # Count how many tickers have it in CNV
    cur = db.execute(f"SELECT COUNT(DISTINCT ticker), MIN(period_end), MAX(period_end) FROM cnv_estados WHERE concepto=? AND ticker IN ({ph})", (cnv, *byma))
    cnt_c, min_c, max_c = cur.fetchone()
    
    # Count in YFinance
    cur = db.execute(f"""
        SELECT COUNT(DISTINCT e.ticker_ppal), MIN(f.period_end), MAX(f.period_end)
        FROM facts f
        JOIN empresas e ON f.cik = e.cik
        WHERE e.grupo='byma_yf' AND f.tag=? AND f.taxonomia='yfinance'
    """, (yf,))
    cnt_y, min_y, max_y = cur.fetchone() or (0, None, None)
    
    print(f"{cnv:<20} {yf:<45} {cnt_c:>3} tickers {cnt_y:>3} tickers")
    print(f"{'':20} {'':45} {str(min_c or '-'):>10} {str(min_y or '-'):>10}")
    print(f"{'':20} {'':45} {str(max_c or '-'):>10} {str(max_y or '-'):>10}")
    print()

db.close()
