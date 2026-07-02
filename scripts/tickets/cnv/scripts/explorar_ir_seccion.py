"""Ir a fondo en la seccion del IR y probar descarga Blob"""
import csv, re, requests, json, math

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Probar varias empresas con 1001
targets = []
for r in rows:
    if r['formTypeId'] in ('1001', '1002') and r['ticker'] in ('ALUA', 'TRAN', 'GGAL', 'YPFD', 'PAMP'):
        targets.append(r)

for t in targets[:4]:
    url = t['url']
    resp = requests.get(url, headers=H, timeout=25, verify=False)
    html = resp.text
    
    m = re.search(r'var formFile\s*=\s*(\{.*?\});\s*$', html, re.DOTALL | re.MULTILINE)
    if not m:
        m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)
    data = json.loads(m.group(1))
    
    pid = int(float(t['presentationId']))
    fid = t['formTypeId']
    print(f"\n=== {t['ticker']} formTypeId={fid} PID={pid} ===")
    print(f"metadata: FormType={data['metadata'].get('FormType')}, Ejercicio={data['metadata'].get('Ejercicio')}, Periodo={data['metadata'].get('Periodo')}, Periodicidad={data['metadata'].get('Periodicidad')}")
    
    # Blob URL
    blob_url = data['metadata'].get('UriArchivo', '')
    print(f"BlobUri: {blob_url[:100]}")
    
    # Try blob download
    if blob_url:
        try:
            br = requests.get(blob_url, headers=H, timeout=15, verify=False)
            print(f"  Blob download: HTTP {br.status_code} ({len(br.text)} bytes)")
            if len(br.text) > 0:
                # Check content type
                ct = br.headers.get('Content-Type', '')
                print(f"  Content-Type: {ct}")
                if 'json' in ct or br.text.strip().startswith('{') or br.text.strip().startswith('['):
                    try:
                        bdata = json.loads(br.text)
                        print(f"  JSON parsed: {type(bdata).__name__}")
                        if isinstance(bdata, dict):
                            print(f"    keys: {list(bdata.keys())[:10]}")
                        elif isinstance(bdata, list):
                            print(f"    len: {len(bdata)}")
                            if bdata and isinstance(bdata[0], dict):
                                print(f"    first keys: {list(bdata[0].keys())[:10]}")
                    except:
                        # Might be CSV or other format
                        print(f"  Not JSON. First 200 chars: {br.text[:200]}")
        except Exception as e:
            print(f"  Blob error: {e}")
    
    # Navigate through sections recursively
    def explore(obj, depth=0, max_depth=3):
        prefix = "  " * (depth + 1)
        if depth > max_depth:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ('propiedades', 'propiedad') and isinstance(v, list) and len(v) > 0:
                    print(f"{prefix}{k}: {len(v)} items")
                    for item in v[:15]:
                        if isinstance(item, dict):
                            val_str = str(item.get('valor', ''))[:30]
                            cod = item.get('codigo', item.get('id', ''))
                            nom = item.get('nombre', '')[:30]
                            print(f"{prefix}  [{cod}] {nom} = {val_str}")
                elif k in ('propiedades', 'propiedad') and isinstance(v, dict):
                    print(f"{prefix}{k}: dict {list(v.keys())}")
                    explore(v, depth+1, max_depth)
                elif isinstance(v, str) and len(v) < 80 and v.strip():
                    pass  # skip short strings
                elif isinstance(v, (list, dict)):
                    if isinstance(v, list) and len(v) <= 20:
                        explore({f"[{i}]": item for i, item in enumerate(v)}, depth, max_depth)
                    elif isinstance(v, list):
                        print(f"{prefix}{k}: list[{len(v)}] (skipping large)")
                    elif isinstance(v, dict):
                        explore(v, depth+1, max_depth)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                explore({f"[{i}]": item}, depth, max_depth)
    
    explore(data.get('navegacion', {}), max_depth=5)
