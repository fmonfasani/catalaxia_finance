"""Analizar estructura completa de formFile IR"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Probar con ALUA (PID 1799) que tiene datos mas reales que A3
for r in rows:
    if r['formTypeId'] == '1001' and r['ticker'] == 'ALUA':
        target = r
        break

url = target['url']
resp = requests.get(url, headers=H, timeout=25, verify=False)
html = resp.text

m = re.search(r'var formFile\s*=\s*(\{.*?\});\s*$', html, re.DOTALL | re.MULTILINE)
if not m:
    m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)

data = json.loads(m.group(1))

print(f"=== formTypeId=1001 ticker={target['ticker']} PID={int(float(target['presentationId']))} ===")

# ---- modeloDatos ----
print(f"\n--- modeloDatos ({len(data['modeloDatos'])} items) ---")
for i, md in enumerate(data['modeloDatos']):
    print(f"  [{i}] tipo: {type(md).__name__}")
    if isinstance(md, dict):
        print(f"      keys: {list(md.keys())}")
        # Print first item
        for k, v in md.items():
            if isinstance(v, str) and len(v) > 100:
                print(f"      {k}: (str {len(v)} chars) {v[:80]}...")
            elif isinstance(v, list):
                print(f"      {k}: list[{len(v)}]")
                if v and isinstance(v[0], dict):
                    print(f"        first item keys: {list(v[0].keys())}")
                elif v and len(v) > 0:
                    print(f"        first item: {v[0]}")
            elif isinstance(v, dict):
                print(f"      {k}: dict[{len(v)}] keys={list(v.keys())}")
            else:
                print(f"      {k}: {v}")

# ---- navegacion ----
print(f"\n--- navegacion ---")
nav = data['navegacion']
for k, v in nav.items():
    print(f"  {k}: {type(v).__name__}", end="")
    if isinstance(v, list):
        print(f" [{len(v)}]", end="")
        if v and isinstance(v[0], dict):
            v0 = v[0]
            print(f" keys={list(v0.keys())}", end="")
            if 'propiedades' in v0:
                props = v0['propiedades']
                print(f" props[{len(props)}]", end="")
                for p in props[:5]:
                    print(f"\n    [{p.get('orden','')}] id={p.get('id','')} nombre={p.get('nombre','')[:60]} valor={str(p.get('valor',''))[:60]}")
    print()

# ---- metadata ----
print(f"\n--- metadata ---")
for k, v in data['metadata'].items():
    print(f"  {k}: {v}")
