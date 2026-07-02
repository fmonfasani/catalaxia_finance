"""Explorar estructura HTML de IR (formTypeId=1001 y 1002)"""
import csv, re, requests, html as ihtml

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Tomar 1 filing de 1001 y 1 de 1002, de distintas empresas
for fid in ('1001', '1002'):
    for r in rows:
        if r['formTypeId'] == fid:
            url = r['url']
            ticker = r['ticker']
            pid = int(float(r['presentationId']))
            print(f"\n=== formTypeId={fid} ticker={ticker} PID={pid} ===")
            print(f"URL: {url[:80]}")
            
            try:
                resp = requests.get(url, headers=H, timeout=25, verify=False)
                html = resp.text
                print(f"HTML size: {len(html)} bytes")
                
                # Look for date patterns
                fechas = re.findall(r'(\d{4}-\d{2}-\d{2})', html)
                print(f"Fechas encontradas: {len(fechas)}")
                for f in fechas[:10]:
                    ctx = html[html.find(f)-40:html.find(f)+50]
                    clean = re.sub(r'<[^>]+>', ' ', ctx).strip()
                    clean = re.sub(r'\s+', ' ', clean)
                    print(f"  {clean[:120]}")
                
                # Look for all codes in this format (different from AIF2?)
                txt = ihtml.unescape(re.sub(r"<[^>]+>", " ", html))
                txt = re.sub(r"\s+", " ", txt)
                codes = set()
                for m in re.finditer(r"([1-8]\d{6})\s+[A-Za-zÁÉÍÓÚÑáéíóúñ()/.,\s]+?\s+(-?\d+\.\d{2})", txt):
                    codes.add(m.group(1))
                print(f"Codigos CNV encontrados: {len(codes)}")
                print(f"  {sorted(codes)[:20]}")
                
            except Exception as e:
                print(f"ERROR: {str(e)[:80]}")
            
            break  # solo 1 muestra
