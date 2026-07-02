"""Check formtypes_global.csv for ADR companies"""
import csv
f = open('scripts/tickets/cnv/debug/formtypes_global.csv', 'r', encoding='utf-8-sig')
r = csv.DictReader(f)
cols = r.fieldnames
print(f"Columns: {cols}")
tickers = set()
for i, row in enumerate(r):
    t = row.get('ticker', '').strip().upper()
    tickers.add(t)
f.close()

print(f"Total tickers in formtypes_global: {len(tickers)}")
for tk in ['GGAL','BMA','CEPU','CRESY','EDN','LOMA','PAM','SUPV','TEO','BBAR']:
    print(f"  {tk}: {tk in tickers}")

# Show all tickers
print(f"\nAll tickers: {sorted(tickers)}")
