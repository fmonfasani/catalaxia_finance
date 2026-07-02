"""Verificar resultados de la carga de FT=142 y FT=487"""
import sqlite3

db = sqlite3.connect('data/screener.db')

# Check BPAT, PATA, VALO - tickers that didn't have data before
for tk in ('BPAT', 'PATA', 'VALO'):
    cur = db.execute("SELECT COUNT(*), COUNT(DISTINCT concepto), COUNT(DISTINCT period_end) FROM cnv_estados WHERE ticker=?", (tk,))
    cnt, concepts, periods = cur.fetchone()
    print(f"{tk:<6} {cnt:>6} filas, {concepts:>3} conceptos, {periods:>3} periodos")
    cur = db.execute("SELECT DISTINCT period_end FROM cnv_estados WHERE ticker=? ORDER BY period_end", (tk,))
    dates = [r[0] for r in cur.fetchall()]
    print(f"        periodos ({len(dates)}): {dates[:8]}")
    cur = db.execute("SELECT DISTINCT concepto FROM cnv_estados WHERE ticker=? ORDER BY concepto", (tk,))
    print(f"        conceptos ({len(cur.fetchall())})")
    cur = db.execute("SELECT DISTINCT fuente FROM cnv_estados WHERE ticker=?", (tk,))
    print(f"        fuentes: {[r[0] for r in cur.fetchall()]}")
    print()

# Also check new 142/487 additions to existing tickers
for tk in ('LONG', 'BHIP', 'BOLT', 'GAMI'):
    cur = db.execute("SELECT COUNT(*), COUNT(DISTINCT fuente) FROM cnv_estados WHERE ticker=?", (tk,))
    cnt, fuentes = cur.fetchone()
    cur2 = db.execute("SELECT DISTINCT fuente FROM cnv_estados WHERE ticker=?", (tk,))
    fsrc = [r[0] for r in cur2.fetchall()]
    print(f"{tk:<6} {cnt:>6} filas, fuentes={fsrc}")

print()
# Total DB count
cur = db.execute("SELECT COUNT(*) FROM cnv_estados")
print(f"Total filas en cnv_estados: {cur.fetchone()[0]}")

# Tickers count
cur = db.execute("SELECT COUNT(DISTINCT ticker) FROM cnv_estados")
print(f"Tickers con datos: {cur.fetchone()[0]}")

# Tickers without any data
cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
all_tickers = set(r[0] for r in cur.fetchall())
cur = db.execute("SELECT DISTINCT ticker FROM cnv_estados")
with_data = set(r[0] for r in cur.fetchall())
missing = all_tickers - with_data
print(f"Tickers SIN datos: {sorted(missing) if missing else 'NINGUNO!'}")

db.close()
