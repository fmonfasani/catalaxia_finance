"""Contar datos CNV para los 56 BYMA"""
import sqlite3

db = sqlite3.connect('data/screener.db')

cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
byma = [r[0] for r in cur.fetchall()]
ph = ','.join('?' * len(byma))

print(f"BYMA: {len(byma)} tickers\n")

# CNV sources
fuentes_cnv = ['cnv-aif2', 'cnv-487', 'cnv-142', 'cnv-ir', 'cnv-6k']

print("=== Datos CNV por fuente ===")
total_cnv = 0
for ft in fuentes_cnv:
    cur = db.execute(f"SELECT COUNT(*) FROM cnv_estados WHERE fuente=? AND ticker IN ({ph})", (ft, *byma))
    cnt = cur.fetchone()[0]
    cur = db.execute(f"SELECT COUNT(DISTINCT concepto) FROM cnv_estados WHERE fuente=? AND ticker IN ({ph})", (ft, *byma))
    concepts = cur.fetchone()[0]
    cur = db.execute(f"SELECT COUNT(DISTINCT ticker) FROM cnv_estados WHERE fuente=? AND ticker IN ({ph})", (ft, *byma))
    tickers = cur.fetchone()[0]
    cur = db.execute(f"SELECT MIN(period_end), MAX(period_end) FROM cnv_estados WHERE fuente=? AND ticker IN ({ph})", (ft, *byma))
    mind, maxd = cur.fetchone()
    total_cnv += cnt
    print(f"  {ft:<12} {cnt:>7} filas | {concepts:>2} conceptos | {tickers:>2} tickers | {mind} - {maxd}")

print(f"\n  TOTAL CNV: {total_cnv} filas")

# Total conceptos CNV (distinct across all sources)
cur = db.execute(f"SELECT COUNT(DISTINCT concepto) FROM cnv_estados WHERE ticker IN ({ph})", (*byma,))
conc_total = cur.fetchone()[0]
print(f"  Conceptos unicos CNV: {conc_total}")

# List them
cur = db.execute(f"SELECT DISTINCT concepto FROM cnv_estados WHERE ticker IN ({ph}) ORDER BY concepto", (*byma,))
for r in cur.fetchall():
    print(f"    {r[0]}")

print()

# Compare with EDGAR for BYMA
print("=== YFinance en facts para BYMA ===")
cur = db.execute(f"""
    SELECT COUNT(*), COUNT(DISTINCT f.tag), COUNT(DISTINCT f.cik)
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.grupo = 'byma_yf' AND f.taxonomia = 'yfinance'
""")
cnt, tags, tickers = cur.fetchone()
print(f"  {cnt:>7} filas | {tags} tags | {tickers} tickers")

# Show top tags
cur = db.execute(f"""
    SELECT f.tag, COUNT(*) as cnt
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.grupo = 'byma_yf' AND f.taxonomia = 'yfinance'
    GROUP BY f.tag ORDER BY cnt DESC LIMIT 15
""")
print("  Top tags yfinance:")
for r in cur.fetchall():
    print(f"    {r[1]:>5}x {r[0]}")

print()
print("=== EDGAR (us-gaap + ifrs-full) para comparacion ===")
cur = db.execute("SELECT COUNT(*), COUNT(DISTINCT tag) FROM facts WHERE taxonomia IN ('us-gaap','ifrs-full')")
cnt, tags = cur.fetchone()
print(f"  {cnt:>7} filas | {tags} tags")

db.close()
