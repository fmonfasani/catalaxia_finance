"""Explorar estructura HTML de FT=349 y FT=488"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Buscar varios samples de 349 y 488 - que NO sean los mismos para descartar 147
targets = {'349': [], '488': []}
seen_ticker = {'349': set(), '488': set()}

for r in rows:
    for ft in ('349', '488'):
        if r['formTypeId'] == ft and r['ticker'] not in seen_ticker[ft] and len(targets[ft]) < 4:
            seen_ticker[ft].add(r['ticker'])
            targets[ft].append(r)

for ft in ('349', '488'):
    for s in targets[ft]:
        fid = s['formTypeId']
        ticker = s['ticker']
        pid = int(float(s['presentationId']))
        url = s['url']
        
        resp = requests.get(url, headers=H, timeout=20, verify=False)
        html = resp.text
        
        # Get formFile
        m = re.search(r'var formFile\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not m:
            m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)
        
        if not m:
            print(f"{ft:<5} {ticker:<6} PID={pid:<8} NO formFile")
            continue
        
        data = json.loads(m.group(1))
        md = data.get('metadata', {})
        ft_real = md.get('FormType', '?')
        ej = md.get('Ejercicio', '?')
        per = md.get('Periodo', '?')
        perid = md.get('Periodicidad', '?')
        form_name = md.get('DescripcionFormulario', '')
        
        print(f"\n{ft:<5} {ticker:<6} PID={pid:<8} FT={ft_real:<4} Ejer={ej:<5} Per={per:<4} Perid={perid:<4}")
        print(f"      FormName: {form_name}")
        
        # Look at modeloDatos[0].propiedades.propiedad for the actual data items
        if 'modeloDatos' in data and len(data['modeloDatos']) > 0:
            md0 = data['modeloDatos'][0]
            if 'propiedades' in md0:
                props = md0['propiedades'].get('propiedad', [])
                print(f"      Propiedades en modeloDatos: {len(props)}")
                for p in props[:30]:
                    cod = p.get('codigo', '').strip()
                    nom = p.get('nombre', '').strip()
                    valor = str(p.get('valor', '')).strip()
                    print(f"        [{cod}] {nom[:50]:50s} = {valor[:30]}")
                if len(props) > 30:
                    print(f"        ... y {len(props)-30} mas")

        # Also check navigation for properties
        nav = data.get('navegacion', {})
        if 'agrupador' in nav:
            for a in nav['agrupador']:
                if 'propiedades' in a:
                    print(f"      Props en navegacion.agrupador: {len(a['propiedades'])}")
