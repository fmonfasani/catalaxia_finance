"""Explorar propiedades de navegacion y modeloDatos"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

for fid in ('1001', '1002'):
    for r in rows:
        if r['formTypeId'] == fid and r['ticker'] == 'ALUA':
            target = r
            break
    
    url = target['url']
    resp = requests.get(url, headers=H, timeout=25, verify=False)
    html = resp.text
    
    m = re.search(r'var formFile\s*=\s*(\{.*?\});\s*$', html, re.DOTALL | re.MULTILINE)
    if not m:
        m = re.search(r'var formFile\s*=\s*(\{.*\});', html, re.DOTALL)
    data = json.loads(m.group(1))
    
    print(f"\n=== formTypeId={fid} ticker={target['ticker']} PID={int(float(target['presentationId']))} ===")
    print(f"FormType en metadata: {data['metadata']['FormType']}")
    print(f"Ejercicio: {data['metadata']['Ejercicio']}, Periodo: {data['metadata']['Periodo']}, Periodicidad: {data['metadata']['Periodicidad']}")
    
    # ---- navegacion propiedades ----
    agrupador = data['navegacion']['agrupador'][0]
    if 'propiedades' in agrupador:
        props = agrupador['propiedades']
        print(f"\nnavegacion.agrupador[0].propiedades: {len(props)} items")
        for p in props:
            pid = p.get('id', '')
            nombre = p.get('nombre', '')
            titulo = p.get('titulo', '')
            valor = p.get('valor', '')
            print(f"  id={pid} nombre={nombre[:50]} titulo={titulo[:50]} valor={str(valor)[:50]}")
    elif 'seccion' in agrupador:
        secs = agrupador['seccion']
        print(f"\nnavegacion.agrupador[0].seccion: {len(secs)} items")
        for s in secs:
            print(f"  seccion id={s.get('id','')} titulo={s.get('titulo','')[:50]}")
            if 'propiedades' in s:
                for p in s['propiedades'][:20]:
                    print(f"    P: id={p.get('id','')} nombre={p.get('nombre','')[:50]} valor={str(p.get('valor',''))[:50]}")
            elif 'agrupador' in s:
                for a2 in s['agrupador']:
                    print(f"    subagrupador titulo={a2.get('titulo','')[:30]} props={len(a2.get('propiedades',[]))}")
    
    # ---- modeloDatos propiedades ----
    md = data['modeloDatos'][0]
    if 'propiedades' in md:
        props = md['propiedades']['propiedad']
        print(f"\nmodeloDatos[0].propiedades.propiedad: {len(props)} items")
        for p in props[:20]:
            print(f"  codigo={p.get('codigo','')} nombre={p.get('nombre','')[:60]} valor={p.get('valor','')}")
        print(f"  ... (showing 20/{len(props)})")
    
    break  # solo 1
