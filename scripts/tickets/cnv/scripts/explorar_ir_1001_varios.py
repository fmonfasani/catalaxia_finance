"""Check several 1001/1002 filings for different companies - look for varied structures"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Group by formTypeId and ticker
seen = set()
samples = []
for r in rows:
    key = (r['formTypeId'], r['ticker'])
    if key not in seen and len(samples) < 16:
        seen.add(key)
        samples.append(r)

for s in samples:
    fid = s['formTypeId']
    ticker = s['ticker']
    pid = int(float(s['presentationId']))
    url = s['url']
    
    try:
        resp = requests.get(url, headers=H, timeout=20, verify=False)
        html = resp.text
        m = re.search(r'var formFile\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not m:
            m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)
        
        if m:
            data = json.loads(m.group(1))
            md = data.get('metadata', {})
            ft = md.get('FormType', '?')
            ej = md.get('Ejercicio', '?')
            per = md.get('Periodo', '?')
            perid = md.get('Periodicidad', '?')
            
            # Count properties in navigation
            props_count = 0
            nav = data.get('navegacion', {})
            if 'agrupador' in nav:
                for a in nav['agrupador']:
                    if 'propiedades' in a:
                        props_count += len(a['propiedades'])
                    if 'seccion' in a:
                        for sec in a['seccion']:
                            if 'propiedades' in sec:
                                props_count += len(sec['propiedades'])
                            if 'agrupador' in sec:
                                for a2 in sec['agrupador']:
                                    if 'propiedades' in a2:
                                        props_count += len(a2['propiedades'])
            
            # Check modeloDatos
            md_props = 0
            if 'modeloDatos' in data and len(data['modeloDatos']) > 0:
                md0 = data['modeloDatos'][0]
                if 'propiedades' in md0:
                    md_props = len(md0['propiedades'].get('propiedad', []))
            
            print(f"{fid:<5} {ticker:<6} PID={pid:<7} FT={ft:<4} Ejer={ej:<5} Per={per:<4} Perid={perid:<4} Props(nav={props_count}, md={md_props})")
        else:
            print(f"{fid:<5} {ticker:<6} PID={pid:<7} NO formFile found (raw HTML {len(html)} bytes)")
    except Exception as e:
        print(f"{fid:<5} {ticker:<6} PID={pid:<7} ERROR: {str(e)[:60]}")
