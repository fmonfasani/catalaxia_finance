"""Check data coverage for 13 BYMA ratios"""
import sqlite3

db = sqlite3.connect('data/screener.db')

cur = db.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
byma = [r[0] for r in cur.fetchall()]
by = tuple(byma)
ph = ','.join('?' * len(by))

print(f"BYMA tickers: {len(byma)}")
print()

conceptos = {
    'EPS_basico': 'PER, EPS Anual, Crecimiento EPS 5y',
    'Revenue': 'Margen Neto',
    'NetIncome': 'Margen Neto, ROE 5y',
    'EBITDA': 'Deuda/EBITDA',
    'DebtCurrent': 'Deuda/EBITDA',
    'DebtNonCurrent': 'Deuda/EBITDA',
    'Equity': 'ROE 5y',
    'CF_Operativo': 'FCF/CE',
    'CF_Inversion': 'FCF/CE',
    'CashFlowNeto': 'FCF/CE (alt)',
}

print(f"{'Concepto':<25} {'Tickers':>8} {'Min date':>12} {'Max date':>12}")
print("-" * 60)
for conc, uso in conceptos.items():
    cur = db.execute(f"SELECT COUNT(DISTINCT ticker), MIN(period_end), MAX(period_end) FROM cnv_estados WHERE concepto=? AND ticker IN ({ph})", (conc, *by))
    cnt, mind, maxd = cur.fetchone()
    print(f"{conc:<25} {cnt:>8} {str(mind or '-'):>12} {str(maxd or '-'):>12}")

print()
print("--- Precios ---")
cur = db.execute(f"SELECT COUNT(*), MIN(precio), MIN(year_high), MIN(year_low) FROM precios WHERE ticker IN ({ph})", (*by,))
cnt, pmin, yh, yl = cur.fetchone()
cur2 = db.execute(f"SELECT MAX(precio), MAX(year_high), MAX(year_low) FROM precios WHERE ticker IN ({ph})", (*by,))
pmax, yh2, yl2 = cur2.fetchone()
print(f"BYMA con precios: {cnt}/{len(byma)}")
print(f"Precio: {pmin} - {pmax}")
print(f"Year High: {yh} - {yh2}")
print(f"Year Low:  {yl} - {yl2}")

print()
print("--- FX rates (ratios table) ---")
cur = db.execute(f"SELECT COUNT(*), MIN(fx_a_usd), MAX(fx_a_usd) FROM ratios WHERE ticker IN ({ph})", (*by,))
cnt, fxmin, fxmax = cur.fetchone()
print(f"BYMA con FX: {cnt}/{len(byma)}")
print(f"FX range: {fxmin:.4f} - {fxmax:.4f}")

print()
print("--- Dividendos ---")
cur = db.execute("SELECT DISTINCT tag FROM facts WHERE tag LIKE '%Dividend%' AND tag NOT LIKE '%Interest%' LIMIT 15")
for r in cur.fetchall():
    print(f"  facts: {r[0]}")
# Check if any BYMA company has dividend data in facts
cur = db.execute(f"SELECT DISTINCT f.tag FROM facts f JOIN empresas e ON f.cik=e.cik WHERE e.grupo='byma_yf' AND (f.tag LIKE '%DividendCash%' OR f.tag LIKE '%DividendsPaid%' OR f.tag LIKE '%CommonStockDividends%')")
for r in cur.fetchall():
    print(f"  facts (BYMA): {r[0]}")

# Check payout in ratios table
cur = db.execute(f"SELECT ticker, payout FROM ratios WHERE ticker IN ({ph}) AND payout IS NOT NULL LIMIT 5", (*by,))
pr = cur.fetchall()
print(f"  Payout en ratios (BYMA): {len(pr)} tickers")
for r in pr[:5]:
    print(f"    {r[0]}: {r[1]}")

db.close()
