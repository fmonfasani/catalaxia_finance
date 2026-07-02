"""Investigate formTypeId=339 filings and find dividend data"""
import csv, re, requests

# Check ALL form types in CSV
with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    by_type = {}
    for row in reader:
        by_type.setdefault(row['formTypeId'], []).append(row)

print(f"FormTypes found: {sorted(by_type.keys())}")
print(f"FT=339 exists: {'339' in by_type}")
if '339' in by_type:
    tickers = set(r['ticker'] for r in by_type['339'])
    print(f"  Tickers: {sorted(tickers)}")
    print(f"  Count: {len(by_type['339'])}")

# Get ALUA's AIF2 filings to find one with sub-items
with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    alua = sorted(
        [r for r in reader if r['ticker'] == 'ALUA' and r['formTypeId'] == '147'],
        key=lambda x: x.get('guid', '')
    )

# Get the last one (largest GUID typically = most recent)
recent = alua[-1]
print(f"\nLatest ALUA AIF2: GUID={recent['guid']}")

# Download it
resp = requests.get(recent['url'], timeout=30)
html = resp.text

# Extract period_end
m = re.search(r'FechaCierre[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
if m:
    print(f"Period end: {m.group(1)}")

# Parse ALL fila elements
codes = {}
for m in re.finditer(r'<fila[^>]*>.*?<propiedad id="Nro"[^>]*>(\d+)</propiedad>.*?<propiedad id="Rubro"[^>]*>(.*?)</propiedad>.*?<propiedad id="Monto"[^>]*>(.*?)</propiedad>.*?</fila>', html, re.DOTALL):
    code = int(m.group(1))
    label = m.group(2).strip()
    amount = m.group(3).strip()
    codes[code] = (label, amount)

print(f"Total codes: {len(codes)}")

# Show equity section in detail
print("\n=== EQUITY SECTION (221xxx) ===")
for c in sorted(codes):
    if str(c).startswith('221') or str(c) == '2299999':
        print(f"  {c}: {codes[c][0]:<50} {codes[c][1]}")

# Show cash flow sub-items
print("\n=== CASH FLOW (324xxx) ===")
for c in sorted(codes):
    if str(c).startswith('324'):
        print(f"  {c}: {codes[c][0]:<50} {codes[c][1]}")

# Show any codes with "DIVIDENDO" or "dividendo" in the label
print("\n=== ANY DIVIDEND-RELATED ===")
for c, (l, a) in sorted(codes.items()):
    if any(kw in l.lower() for kw in ['dividend', 'distrib', 'pago', 'honorari', 'retrib']):
        print(f"  {c}: {l:<50} {a}")

# Also search in raw HTML
for kw in ['dividendo', 'dividend', 'DIVIDENDO']:
    matches = list(re.finditer(kw, html, re.IGNORECASE))
    if matches:
        print(f"\n'{kw}' found {len(matches)}x in raw HTML")
        for m in matches[:3]:
            print(f"  at {m.start()}: ...{html[m.start()-50:m.end()+100]}")
