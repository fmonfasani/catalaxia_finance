"""Analizar potencial maximo de cada fuente"""
import csv, sqlite3

db = sqlite3.connect('data/screener.db')
cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
byma = set(r[0] for r in cur.fetchall())
print(f"BYMA tickers: {len(byma)}\n")

# ---- 1. links_eeff_refined.csv ----
with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    links = list(csv.DictReader(f))

info_ft = {
    '147': 'AIF2 NIIF estandar',
    '487': 'AIF2 alternativo (bancos)',
    '142': 'AIF2 complementario',
    '349': 'Controladas (solo metadata)',
    '488': 'Wrapper balance (solo metadata)',
    '1001': 'Wrapper migracion (PDF blob)',
    '1002': 'Wrapper migracion (PDF blob)',
}

t147_by_ticker = {}
for r in links:
    t = r['ticker'].strip().upper()
    ft = r['formTypeId']
    if t in byma:
        t147_by_ticker.setdefault(ft, set()).add(t)

cobertura_147 = t147_by_ticker.get('147', set())

print("=== Fuentes CNV AIF2 (links_eeff_refined.csv) ===")
for ft in ['147', '487', '142', '349', '488', '1001', '1002']:
    tickers = sorted(t147_by_ticker.get(ft, set()))
    records = sum(1 for r in links if r['formTypeId'] == ft and r['ticker'].strip().upper() in byma)
    sin_147 = [t for t in tickers if t not in cobertura_147]
    print(f"  {ft:<6} {info_ft[ft]:30s} Tickers: {len(tickers):>2}/{len(byma)} Records: {records}")
    if sin_147:
        print(f"         *** EXCLUSIVOS (sin 147): {sin_147}")

print()

# ---- 2. CNV-IR (PDF pipeline) ----
import importlib.util, sys
spec = importlib.util.spec_from_file_location("catalogo_ir", 
    r"scripts/tickets/cnv/scripts/cnv_ir/catalogo_ir.py")
cat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cat)
CATALOGO = cat.CATALOGO

con_url = sum(1 for v in CATALOGO.values() if v[3] and v[3][0])
sin_url = sum(1 for v in CATALOGO.values() if not v[3] or not v[3][0])

print("=== CNV-IR (Pipeline PDF desde sitios IR) ===")
print(f"  Tickers con URL en catalogo: {con_url}/{len(CATALOGO)}")
print(f"  Tickers SIN URL: {sin_url}/{len(CATALOGO)}")
for tk, v in sorted(CATALOGO.items()):
    estado = "TIENE URL" if v[3] and v[3][0] else "SIN URL"
    print(f"    {tk:<7} {estado}")

print()

# ---- 3. YFinance ----
cur = db.execute("""
    SELECT COUNT(DISTINCT e.ticker_ppal)
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.grupo = 'byma_yf' AND f.taxonomia = 'yfinance'
""")
yf_tickers = cur.fetchone()[0]
cur = db.execute("""
    SELECT COUNT(DISTINCT f.tag)
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.grupo = 'byma_yf' AND f.taxonomia = 'yfinance'
""")
yf_tags = cur.fetchone()[0]
print(f"=== YFinance (facts table) ===")
print(f"  Tickers BYMA: {yf_tickers}/{len(byma)}")
print(f"  Tags unicos: {yf_tags}")

print()

# ---- 4. SEC EDGAR ----
cur = db.execute("""
    SELECT COUNT(DISTINCT e.ticker_ppal)
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE e.ticker_ppal IS NOT NULL AND f.taxonomia IN ('us-gaap','ifrs-full')
""")
edgar_tickers = cur.fetchone()[0]
print(f"=== SEC EDGAR ===")
print(f"  Tickers con datos: {edgar_tickers} (SP500 + ADR + Latam)")

# ---- 5. CNV-6K ----
cur = db.execute("SELECT COUNT(DISTINCT ticker) FROM cnv_estados WHERE fuente='cnv-6k'")
k6 = cur.fetchone()[0]
print()
print(f"=== CNV-6K ===")
print(f"  Tickers: {k6}/56 BYMA")

db.close()
