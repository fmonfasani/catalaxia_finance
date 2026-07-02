"""Analizar el potencial máximo de cada fuente de datos EEFF"""
import csv, sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
LINKS = BASE / 'scripts' / 'tickets' / 'cnv' / 'datos' / 'links_eeff_refined.csv'

db = sqlite3.connect(BASE / 'data' / 'screener.db')

# Get 56 BYMA tickers
cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
byma = set(r[0] for r in cur.fetchall())
print(f"BYMA tickers: {len(byma)}")
print()

# ---- 1. ANALISIS DE links_eeff_refined.csv ----
with open(LINKS, encoding='utf-8-sig') as f:
    links = list(csv.DictReader(f))

from collections import Counter

by_tkr_form = {}
for r in links:
    t = r['ticker'].strip().upper()
    if t in byma:
        by_tkr_form.setdefault(r['formTypeId'], set()).add(t)

print("=== Fuentes desde CNV AIF2 (links_eeff_refined.csv) ===")
print()

# Check each formTypeId for BYMA-only coverage
formtype_info = {
    '147': 'AIF2 NIIF estándar (ya extraído)',
    '487': 'AIF2 bancario/alternativo (ya extraído)',
    '142': 'AIF2 complementario (ya extraído)',
    '349': 'Controladas/Vinculadas (solo metadata)',
    '488': 'Wrapper balance (solo metadata)',
    '1001': 'IR Migration wrapper (PDF blob)',
    '1002': 'IR Migration wrapper (PDF blob)',
}

for ft in ['147', '487', '142', '349', '488', '1001', '1002']:
    tickers = sorted(by_tkr_form.get(ft, set()))
    # How many of these DON'T have 147 (the primary source)?
    sin_147 = [t for t in tickers if t not in by_tkr_form.get('147', set())]
    max_potencial = len(tickers)
    info = formtype_info.get(ft, '?')
    records = sum(1 for r in links if r['formTypeId'] == ft and r['ticker'].strip().upper() in byma)
    print(f"  {ft:<6} {info}")
    print(f"         Tickers BYMA: {max_potencial}/{len(byma)} | Records: {records}")
    if sin_147:
        print(f"         *** SIN 147: {sin_147}")
    print()

# ---- 2. CNV-IR (PDF pipeline) ----
from pathlib import Path as P
syspath = str(BASE / 'scripts' / 'tickets' / 'cnv' / 'scripts' / 'cnv_ir')
import sys
sys.path.insert(0, syspath)

from catalogo_ir import CATALOGO
print("=== CNV-IR (Pipeline PDF desde Relación con Inversores) ===")
print()
con_url = sum(1 for v in CATALOGO.values() if len(v[3]) > 0 and v[3][0])
sin_url = sum(1 for v in CATALOGO.values() if not v[3] or not v[3][0])
print(f"  Tickers con URL en catálogo: {con_url}/{len(CATALOGO)}")
print(f"  Tickers SIN URL en catálogo: {sin_url}/{len(CATALOGO)}")
print()

# ---- 3. YFINANCE en facts ----
cur = db.execute("""
    SELECT COUNT(DISTINCT e.ticker_ppal) 
    FROM facts f 
    JOIN empresas e ON f.cik = e.cik 
    WHERE e.grupo = 'byma_yf' AND f.taxonomia = 'yfinance'
""")
yf_tickers = cur.fetchone()[0]
print("=== YFinance (facts table, taxonomy=yfinance) ===")
print(f"  Tickers BYMA con datos yfinance: {yf_tickers}/{len(byma)}")
# Check what yfinance tags are available
cur = db.execute("""
    SELECT COUNT(DISTINCT f.tag) 
    FROM facts f 
    JOIN empresas e ON f.cik = e.cik 
    WHERE e.grupo = 'byma_yf' AND f.taxonomia = 'yfinance'
""")
yf_tags = cur.fetchone()[0]
print(f"  Tags únicos yfinance: {yf_tags}")
print()

# ---- 4. EDGAR para ADR/CEDEAR argentinos ----
cur = db.execute("""
    SELECT COUNT(DISTINCT e.ticker_ppal) 
    FROM facts f 
    JOIN empresas e ON f.cik = e.cik 
    WHERE e.grupo IN ('adr_arg', 'adr_bra', 'sp500') AND f.taxonomia = 'us-gaap'
""")
edgar_tickers = cur.fetchone()[0]
print("=== SEC EDGAR para ADR + SP500 ===")
print(f"  Tickers con datos EDGAR: {edgar_tickers}")

# ---- 5. CNV-6K ----
cur = db.execute("""
    SELECT COUNT(DISTINCT ticker) FROM cnv_estados WHERE fuente = 'cnv-6k'
""")
k6_tickers = cur.fetchone()[0]
print()
print("=== CNV-6K ===")
print(f"  Tickers con 6-K: {k6_tickers}/56 BYMA")

db.close()
