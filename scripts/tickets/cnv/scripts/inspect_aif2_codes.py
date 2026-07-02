"""Parse ALL codes from ALUA AIF2 HTML using XML structure"""
import csv, re, requests

with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['ticker'] == 'ALUA' and row['formTypeId'] == '147':
            recent = row
            break

resp = requests.get(recent['url'], timeout=30)
html = resp.text

# Parse ALL <fila> elements
codes = {}
for m in re.finditer(r'<fila[^>]*>.*?<propiedad id="Nro"[^>]*>(\d+)</propiedad>.*?<propiedad id="Rubro"[^>]*>(.*?)</propiedad>.*?<propiedad id="Monto"[^>]*>(.*?)</propiedad>.*?</fila>', html, re.DOTALL):
    code = int(m.group(1))
    label = m.group(2).strip()
    amount = m.group(3).strip()
    codes[code] = (label, amount)

print(f"Total <fila> elements found: {len(codes)}")
print()

# Current mapped codes
current = {1122500, 1121999, 1120100, 1139999, 1110100, 1110200, 1119999, 1999999,
           2210999, 2211999, 2212999, 2299999,
           2322200, 2321999, 2339999, 2312300, 2319999, 2399999,
           3000100, 3000200, 3009999, 3011600, 3019999, 3021400, 3021500, 3021800, 3029999, 3031100, 3049999, 3099999,
           3240000, 3241100, 3241200, 3241300,
           8000000, 8000001, 8000003, 8000004, 8000005}

new_codes = {c for c in codes if c not in current}

# Group by prefix
def group_by_prefix(codes_dict, prefix_len):
    groups = {}
    for c in sorted(codes_dict if isinstance(codes_dict, set) else codes_dict.keys()):
        if isinstance(codes_dict, set):
            label = codes.get(c, ('',''))[0]
        else:
            label = codes_dict[c][0]
        prefix = str(c)[:prefix_len]
        groups.setdefault(prefix, []).append((c, label))
    return groups

print("=== ALL CODES (organized by prefix) ===")
for prefix in sorted(set(str(c)[:2] for c in codes)):
    group = sorted([(c, codes[c]) for c in codes if str(c).startswith(prefix)])
    print(f"\n--- PREFIX {prefix}xx ---")
    for c, (label, amt) in group:
        is_new = "NEW" if c in new_codes else "   "
        print(f"  {is_new} {c:>7}  {label:<50}  {amt}")

print()
print("=== SEARCH FOR DIVIDENDOS, DISTRIBUCION in ALL text ===")
for term in ['dividend', 'dividen', 'distrib', 'pago', 'retrib']:
    matches = list(re.finditer(term, html, re.IGNORECASE))
    if matches:
        print(f"\n'{term}': {len(matches)} matches")
        for m in matches[:5]:
            start = max(0, m.start() - 100)
            end = min(len(html), m.end() + 100)
            print(f"  ...{html[start:end].replace(chr(10),' ').strip()[:200]}...")

# Also check: what's in 3061999?
print("\n\n=== Context for 3061999 ===")
for code in [3061999, 3011100, 3011200, 3011300, 3011301, 3011400, 3021900]:
    if code in codes:
        print(f"  {code}: {codes[code][0]:<40} -> {codes[code][1]}")
    else:
        print(f"  {code}: NOT FOUND in this filing")
