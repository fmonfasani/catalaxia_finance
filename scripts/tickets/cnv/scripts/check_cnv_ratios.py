import sqlite3
db = sqlite3.connect('data/screener.db')

# Check CNV_ prefixed concepts
cur = db.execute("SELECT DISTINCT concepto FROM cnv_estados WHERE concepto LIKE 'CNV_%' ORDER BY concepto")
ratios = [r[0] for r in cur]
print(f"CNV ratios in DB ({len(ratios)}):")
for r in ratios:
    print(f"  {r}")

# Check ALUA's CNV ratios
print()
cur = db.execute("""
    SELECT concepto, period_end, valor FROM cnv_estados 
    WHERE ticker='ALUA' AND concepto LIKE 'CNV_%' 
    ORDER BY concepto, period_end
""")
for r in cur:
    print(f"  ALUA: {r[0]} = {r[2]} ({r[1]})")

# Check count of CNV ratios per ticker
print()
cur = db.execute("""
    SELECT COUNT(DISTINCT concepto) as n_conceptos, COUNT(DISTINCT ticker) as n_tickers
    FROM cnv_estados WHERE concepto LIKE 'CNV_%'
""")
r = cur.fetchone()
print(f"Total CNV_ concepts: {r[0]}, covering {r[1]} tickers")

# Show which tickers have CNV ratios
cur = db.execute("""
    SELECT ticker, COUNT(DISTINCT concepto) FROM cnv_estados 
    WHERE concepto LIKE 'CNV_%' GROUP BY ticker ORDER BY ticker
""")
for r in cur:
    print(f"  {r[0]}: {r[1]} CNV ratios")
    
db.close()
