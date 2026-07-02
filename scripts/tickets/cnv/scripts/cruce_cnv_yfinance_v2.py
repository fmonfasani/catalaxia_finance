"""Cross-reference CNV vs YFinance - con nombres reales de tags"""
import sqlite3

db = sqlite3.connect('data/screener.db')

# First, discover actual yfinance tag names for BYMA
cur = db.execute("""
    SELECT DISTINCT f.tag
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.grupo='byma_yf' AND f.taxonomia='yfinance'
    ORDER BY f.tag
""")
yf_tags = [r[0] for r in cur.fetchall()]
print(f"YFinance tags disponibles: {len(yf_tags)}")
print(f"Muestras: {yf_tags[:20]}")
print()

# Find relevant tags for our CNV concepts
cnv_concepts = [
    ('Revenue', ['TotalRevenue', 'Total Revenue', 'OperatingRevenue', 'Revenue']),
    ('NetIncome', ['NetIncome', 'Net Income', 'NetIncomeCommonStockholders']),
    ('EBITDA', ['EBITDA', 'NormalizedEBITDA']),
    ('Assets', ['TotalAssets', 'Total Assets']),
    ('Equity', ['TotalEquityGrossMinorityInterest', 'StockholdersEquity', 'Total Equity Gross Minority Interest']),
    ('Cash', ['CashAndCashEquivalents', 'Cash And Cash Equivalents', 'CashFinancial']),
    ('DebtCurrent', ['CurrentDebt', 'Current Debt', 'CurrentDebtAndCapitalLeaseObligation']),
    ('DebtNonCurrent', ['LongTermDebt', 'Long Term Debt', 'LongTermDebtAndCapitalLeaseObligation']),
    ('EPS_basico', ['BasicEPS', 'Basic EPS']),
    ('CF_Operativo', ['OperatingCashFlow', 'Operating Cash Flow', 'CashFlowsfromusedinOperatingActivitiesDirect']),
    ('CF_Inversion', ['InvestingCashFlow', 'Investing Cash Flow']),
    ('CF_Financiacion', ['FinancingCashFlow', 'Financing Cash Flow']),
    ('CashFlowNeto', ['ChangesInCash', 'Changes In Cash', 'EndCashPosition']),
]

cur = db.execute("SELECT ticker_ppal, cik FROM empresas WHERE grupo='byma_yf'")
byma = {r[0]: r[1] for r in cur.fetchall()}
ph = ','.join('?' * len(byma))

print(f"{'Concepto CNV':<20} {'Tag YF encontrado':<45} {'CNV tickers':>12} {'YF tickers':>12} {'Rango YF':>15}")
print("-" * 105)

for cnv, posibles in cnv_concepts:
    # CNV coverage
    cur = db.execute(f"SELECT COUNT(DISTINCT ticker) FROM cnv_estados WHERE concepto=? AND ticker IN ({ph})", (cnv, *byma))
    cnt_cnv = cur.fetchone()[0]
    
    # Find which yfinance tag actually exists
    real_tag = None
    for tag in posibles:
        cur = db.execute(f"""
            SELECT COUNT(DISTINCT e.ticker_ppal), MIN(f.period_end), MAX(f.period_end)
            FROM facts f
            JOIN empresas e ON f.cik = e.cik
            WHERE e.grupo='byma_yf' AND f.tag=? AND f.taxonomia='yfinance'
        """, (tag,))
        cnt_yf, min_yf, max_yf = cur.fetchone()
        if cnt_yf > 0:
            real_tag = tag
            break
    
    if real_tag:
        print(f"{cnv:<20} {real_tag:<45} {cnt_cnv:>5} tkrs    {cnt_yf:>5} tkrs    {str(min_yf):>10} - {str(max_yf):>10}")
    else:
        print(f"{cnv:<20} {'[NO ENCONTRADO]':<45} {cnt_cnv:>5} tkrs        -")

# Also show which BYMA tickers DON'T have yfinance data
print()
print("=== BYMA tickers SIN yfinance ===")
for tk, cik in sorted(byma.items()):
    cur = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND taxonomia='yfinance'", (cik,))
    cnt = cur.fetchone()[0]
    if cnt == 0:
        print(f"  {tk:<8} CIK={cik}")

# Count total yfinance facts per BYMA
print()
print("=== Datos totales ===")
cur = db.execute(f"SELECT COUNT(*) FROM cnv_estados WHERE ticker IN ({ph})", (*byma,))
total_cnv = cur.fetchone()[0]
cur = db.execute(f"""
    SELECT COUNT(*) FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.grupo='byma_yf' AND f.taxonomia='yfinance'
""")
total_yf = cur.fetchone()[0]
print(f"  CNV total: {total_cnv} filas")
print(f"  YFinance total: {total_yf} filas")

db.close()
