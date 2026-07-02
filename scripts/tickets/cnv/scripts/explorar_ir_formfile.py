"""Extraer y analizar formFile de IR"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

for fid in ('1001', '1002'):
    for r in rows:
        if r['formTypeId'] == fid:
            pid = int(float(r['presentationId']))
            target = r
            break
    
    url = target['url']
    resp = requests.get(url, headers=H, timeout=25, verify=False)
    html = resp.text
    
    # Extract formFile JSON
    m = re.search(r'var formFile\s*=\s*(\{.*?\});\s*$', html, re.DOTALL | re.MULTILINE)
    # Try different patterns
    if not m:
        m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)
    
    if m:
        raw = m.group(1)
        print(f"\n=== formTypeId={fid} ticker={target['ticker']} PID={pid} ===")
        print(f"JSON raw length: {len(raw)}")
        
        try:
            data = json.loads(raw)
            print(f"Top-level keys: {list(data.keys())}")
            
            if 'navegacion' in data:
                nav = data['navegacion']
                if 'agrupador' in nav:
                    print(f"agrupador count: {len(nav['agrupador'])}")
                    for a in nav['agrupador'][:5]:
                        print(f"  Agrupador id={a.get('id','')} titulo={a.get('titulo','')[:50]}")
                        if 'propiedades' in a:
                            print(f"    propiedades count: {len(a['propiedades'])}")
                            for p in a['propiedades'][:3]:
                                print(f"    P: id={p.get('id','')} nombre={p.get('nombre','')[:40]} valor={str(p.get('valor',''))[:40]}")
            
            # Also check for other structures
            if 'modeloDatos' in data:
                print(f"modeloDatos: {type(data['modeloDatos'])} {len(data['modeloDatos']) if isinstance(data['modeloDatos'], list) else 'N/A'}")
            
        except json.JSONDecodeError as e:
            print(f"JSON error: {e}")
            # Show last 200 chars
            print(f"Last 200: ...{raw[-200:]}")
    else:
        print(f"\n=== formTypeId={fid} ticker={target['ticker']} PID={pid} ===")
        print("formFile NOT FOUND")
        # Look for any JSON-like content
        for m in re.finditer(r'(\{.*\})', html):
            try:
                j = json.loads(m.group(0))
                if isinstance(j, dict) and len(j) > 2:
                    print(f"Potential JSON: keys={list(j.keys())}")
            except:
                pass
    
    break  # solo 1 por tipo
