import sqlite3
db = sqlite3.connect('data/screener.db')
tickers = ['ALUA','ARCA','YPFD','GGAL','PAMP','TECO2','BMA','CRES','LOMA','IRSA','EDN','CEPU','TGSU4']
cur = db.execute(f"""
    SELECT cik, ticker_ppal, nombre, grupo FROM empresas 
    WHERE ticker_ppal IN ({','.join('?'*len(tickers))})
    ORDER BY grupo, ticker_ppal
""", tickers)
for r in cur:
    print(f"CIK={r[0]:<10} {r[1]:<8} {r[2][:40]:<42} {r[3]}")

print()

# For ALUA specifically, check what EDGAR/ADR data exists
cik_alua = db.execute("SELECT cik FROM empresas WHERE ticker_ppal='ALUA'").fetchone()
if cik_alua:
    cur = db.execute("""
        SELECT tag, taxonomia, COUNT(*) as n, MIN(period_end), MAX(period_end)
        FROM facts WHERE cik=? AND tag IN ('CashDividendsPaid', 'NetIncome', 'Revenue', 'EarningsPerShareBasic')
        GROUP BY tag, taxonomia ORDER BY taxonomia, tag
    """, (cik_alua[0],))
    for r in cur:
        print(f"ALUA: tag={r[0]:<25} tax={r[1]:<10} count={r[2]:>5} range={r[3]} -> {r[4]}")

# Show all ARCA references
cur = db.execute("SELECT cik, ticker_ppal, nombre, grupo FROM empresas WHERE ticker_ppal='ARCA' OR nombre LIKE '%Aluar%' OR nombre LIKE '%ARCA%'")
for r in cur:
    print(f"  empresa: CIK={r[0]} ticker={r[1]} name={r[2][:50]} group={r[3]}")

db.close()
