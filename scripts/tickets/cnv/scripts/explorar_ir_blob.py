"""Encontrar datos reales de IR - buscar llamadas AJAX y JSON embebido"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Tomar un 1001 de ALUA o GRIM para probar
target = None
for r in rows:
    if r['formTypeId'] == '1001' and r['ticker'] in ('ALUA', 'GRIM', 'TRAN'):
        target = r
        break

print(f"Ticker: {target['ticker']}")
print(f"PID: {int(float(target['presentationId']))}")
print(f"URL: {target['url']}")

resp = requests.get(target['url'], headers=H, timeout=25, verify=False)
html = resp.text

# Buscar referencias a blob service
for m in re.finditer(r'(https?://[^"\']+?blob[^"\']+)', html):
    print(f"\nBlob URL: {m.group(1)[:120]}")

# Buscar var formFile 
for m in re.finditer(r'(formFile|dataFile|json|\.json|PresentationData|GetPresentation)', html, re.IGNORECASE):
    ctx = html[max(0,m.start()-50):m.end()+80]
    clean = re.sub(r'<[^>]+>', ' ', ctx).strip()
    clean = re.sub(r'\s+', ' ', clean)
    print(f"Ref: ...{clean[:150]}...")

# Buscar llamadas AJAX / fetch
for m in re.finditer(r'(\.get\(|\.post\(|fetch\(|ajax\()', html):
    ctx = html[max(0,m.start()-80):m.end()+120]
    clean = re.sub(r'<[^>]+>', ' ', ctx).strip()
    clean = re.sub(r'\s+', ' ', clean)
    print(f"AJAX: ...{clean[:200]}...")

# Buscar cualquier JSON {}
# Look for large JSON blocks
for m in re.finditer(r'(\{.*"modeloDatos".*\})', html, re.DOTALL):
    try:
        data = json.loads(m.group(1))
        print(f"\nJSON encontrado! Keys: {list(data.keys())}")
        if 'modeloDatos' in data:
            print(f"  modeloDatos items: {len(data['modeloDatos'])}")
            for item in data['modeloDatos'][:3]:
                print(f"    {item}")
    except:
        pass

# Check if data is in a <script> tag
for m in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
    script = m.group(1)
    if 'modeloDatos' in script or 'datos' in script.lower() or 'json' in script.lower():
        print(f"\nScript tag ({len(script)} chars): {script[:200]}")

# Try fetching blob service directly
blob_base = "https://blob.cnv.gov.ar/BlobWebService.svc"
pid = int(float(target['presentationId']))
for method in [f'/PresentationData/{pid}', f'/GetPresentation/{pid}', f'/{pid}', f'?id={pid}']:
    try:
        u = blob_base + method
        r = requests.get(u, headers=H, timeout=10, verify=False)
        print(f"\nBlob GET {method}: HTTP {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200 and len(r.text) > 50:
            print(f"  Content: {r.text[:200]}")
    except Exception as e:
        print(f"Blob GET {method}: ERROR {str(e)[:50]}")
