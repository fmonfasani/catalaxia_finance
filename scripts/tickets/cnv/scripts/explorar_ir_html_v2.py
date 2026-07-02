"""Ver contenido real de HTML de IR"""
import csv, re, requests

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

for fid in ('1001', '1002'):
    for r in rows:
        if r['formTypeId'] == fid:
            url = r['url']
            break
    
    resp = requests.get(url, headers=H, timeout=25, verify=False)
    html = resp.text
    
    print(f"\n=== formTypeId={fid} ({len(html)} bytes) ===")
    
    # Find all non-trivial text content
    txt = re.sub(r'<[^>]+>', '\n', html)
    lines = [l.strip() for l in txt.split('\n') if l.strip() and len(l.strip()) > 3]
    
    # Show unique meaningful lines
    seen = set()
    for line in lines[:100]:
        clean = re.sub(r'\s+', ' ', line)
        if clean not in seen and '2004' not in clean and '2018' not in clean and '2013' not in clean:
            seen.add(clean)
            print(f"  {clean[:120]}")
    
    # Any numbers with decimals?
    nums = re.findall(r'\b\d+\.\d{2}\b', html)
    if nums:
        print(f"  Numeros decimales encontrados: {len(nums)} (primeros 5: {nums[:5]})")
    else:
        print(f"  NO hay numeros decimales (sin datos financieros)")
    
    break  # solo 1 muestra por tipo
