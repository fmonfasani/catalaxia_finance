"""Find period_end pattern for FT=142 and FT=487"""
import csv, re, requests

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

for ft_target, ticker in [('142', 'BOLT'), ('487', 'BPAT'), ('487', 'PATA'), ('487', 'VALO')]:
    for r in rows:
        if r['formTypeId'] == ft_target and r['ticker'] == ticker:
            url = r['url']
            pid = int(float(r['presentationId']))
            break
    
    resp = requests.get(url, headers=H, timeout=20, verify=False)
    html = resp.text
    
    print(f"\n=== formTypeId={ft_target} ticker={ticker} PID={pid} ===")
    
    # Search for standard AIF2 patterns
    fch = re.search(r'FechaCierre[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
    fh = re.search(r'FechaHasta[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
    fd = re.search(r'FechaDesde[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
    fc = re.search(r'Fecha[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
    
    print(f"  FechaCierre: {fch.group(1) if fch else 'NO'}")
    print(f"  FechaHasta:  {fh.group(1) if fh else 'NO'}")
    print(f"  FechaDesde:  {fd.group(1) if fd else 'NO'}")
    
    # Also check formFile metadata for dates
    import json
    m = re.search(r'var formFile\s*=\s*(\{.*?\});', html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            md = data.get('metadata', {})
            # Check for period-related fields
            pe = md.get('Periodo', '')
            ej = md.get('Ejercicio', '')
            print(f"  metadata - Periodo: {pe}, Ejercicio: {ej}")
            
            # Check modeloDatos properties for dates
            props = data['modeloDatos'][0]['propiedades'].get('propiedad', [])
            for p in props:
                nom = p.get('nombre','')
                val = p.get('valor','')
                if 'fecha' in nom.lower() or 'periodo' in nom.lower() or 'cierre' in nom.lower() or 'balance' in nom.lower():
                    print(f"  md prop [{nom}] = {val}")
        except:
            pass
    
    # Look for any date-like patterns near "Cierre" or "Hasta"
    all_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', html)
    if all_dates:
        unique = sorted(set(all_dates))
        print(f"  All dates in HTML: {unique[:10]}")
