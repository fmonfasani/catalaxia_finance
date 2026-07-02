"""Find dividend codes in ALUA AIF2 HTML"""
import csv, re, requests

with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    alua_aif2 = []
    for row in reader:
        if row['ticker'] == 'ALUA' and row['formTypeId'] == '147':
            alua_aif2.append(row)
    print(f"ALUA AIF2 filings: {len(alua_aif2)}")

recent = sorted(alua_aif2, key=lambda x: x.get('guid', ''), reverse=True)[0]
print(f"GUID: {recent['guid']} | URL: {recent['url']}")

resp = requests.get(recent['url'], timeout=30)
html = resp.text
print(f"HTML size: {len(html)} bytes")

all_codes = set()
for m in re.finditer(r'\b([1-8]\d{6})\b', html):
    all_codes.add(int(m.group(1)))
all_codes = sorted(all_codes)

current_codes = {
    1122500, 1121999, 1120100, 1139999, 1110100, 1110200, 1119999, 1999999,
    2210999, 2211999, 2212999, 2299999,
    2322200, 2321999, 2339999, 2312300, 2319999, 2399999,
    3000100, 3000200, 3009999, 3011600, 3019999, 3021400, 3021500, 3021800, 3029999, 3031100, 3049999, 3099999,
    3240000, 3241100, 3241200, 3241300,
    8000000, 8000001, 8000003, 8000004, 8000005,
    8000006, 8000007, 8000009, 8000010, 8000011, 8000013, 8000014, 8000015, 8000016, 8000027, 8000028, 8000029,
}

new_codes = [c for c in all_codes if c not in current_codes]
print(f"Total codes in HTML: {len(all_codes)}")
print(f"New (unmapped): {len(new_codes)}")

# Group
equity_new = sorted([c for c in new_codes if str(c)[0:3] == '221'])
income_new = sorted([c for c in new_codes if str(c)[0:2] == '30'])
liab_new = sorted([c for c in new_codes if str(c)[0:2] in ('23',) and c not in equity_new])
assets_new = sorted([c for c in new_codes if str(c)[0] == '1'])
cf_new = sorted([c for c in new_codes if str(c)[0:3] == '324'])
ratio_new = sorted([c for c in new_codes if str(c)[0] == '8'])
rest_new = sorted([c for c in new_codes if c not in equity_new+income_new+liab_new+assets_new+cf_new+ratio_new])

def get_label(html, code):
    pattern = rf'{code}\s+([A-Za-zÁÉÍÓÚÑáéíóúñ().,/ \s-]+?)\s+-?\d'
    m = re.search(pattern, html)
    return m.group(1).strip()[:70] if m else '(no label)'

for name, codes in [('EQUITY (dividend proxy)', equity_new), ('INCOME', income_new), 
                     ('LIABILITIES', liab_new), ('ASSETS', assets_new), 
                     ('CASH FLOW', cf_new), ('RATIOS', ratio_new), ('OTHER', rest_new)]:
    if codes:
        print(f"\n--- {name} ---")
        for c in codes:
            print(f"  {c} : {get_label(html, c)}")
