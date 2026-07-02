"""Find ADR companies in existing links_eeff_refined by company name"""
import csv
f = open('scripts/tickets/cnv/datos/links_eeff_refined.csv','r',encoding='utf-8-sig')
r = csv.DictReader(f)
for row in r:
    name = row['empresa'].lower()
    if any(k in name for k in ['macro', 'galicia', 'central puerto', 'cresud', 'edenor', 'loma negra', 'pampa energ', 'supervielle', 'telecom', 'bbva', 'banco']):
        print(f"ticker={row['ticker']:8} empresa={row['empresa'][:50]:50} cuit={row['cuit']}")
f.close()
