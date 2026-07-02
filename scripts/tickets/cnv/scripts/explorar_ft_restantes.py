"""Check if FT=142 and FT=487 have structured financial data"""
import csv, re, requests, json

H = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'es-AR'}

with open(r'scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Pick one entry each for formTypeId 142 and 487
for ft_target in ('142', '487'):
    for r in rows:
        if r['formTypeId'] == ft_target:
            url = r['url']
            ticker = r['ticker']
            pid = int(float(r['presentationId']))
            break
    
    print(f"\n{'='*60}")
    print(f"formTypeId={ft_target} ticker={ticker} PID={pid}")
    print(f"{'='*60}")
    
    resp = requests.get(url, headers=H, timeout=20, verify=False)
    html = resp.text
    print(f"HTML size: {len(html)} bytes")
    
    # Check for financial data pattern (code + amount)
    txt = json.dumps if 'json' in resp.headers.get('Content-Type','') else None
    
    txt = html
    # Unescape HTML
    import html as ihtml
    txt = ihtml.unescape(re.sub(r"<[^>]+>", " ", html))
    txt = re.sub(r"\s+", " ", txt)
    
    # Find code+amount patterns (like AIF2)
    matches = re.findall(r"([1-8]\d{6})\s+[A-Za-zÁÉÍÓÚÑáéíóúñ()/.,\s]+?\s+(-?\d+\.\d{2})", txt)
    print(f"Code+amount patterns: {len(matches)}")
    for code, amount in matches[:15]:
        # Find the label
        ctx = txt[txt.find(code):txt.find(code)+80]
        label = re.search(rf"{code}\s+(.+?)\s+-?\d+\.\d{{2}}", ctx)
        label_txt = label.group(1).strip()[:40] if label else "?"
        print(f"  [{code}] {label_txt} = {amount}")
    if len(matches) > 15:
        print(f"  ... y {len(matches)-15} mas")
    
    # Check for metadata
    m = re.search(r'var formFile\s*=\s*(\{.*?\});', html, re.DOTALL)
    if m:
        data = json.loads(m.group(1))
        md = data.get('metadata', {})
        ft = md.get('FormType', '?')
        desc = md.get('DescripcionFormulario', '')
        print(f"\nFormType: {ft} | Desc: {desc}")
        
        props = data.get('modeloDatos', [{}])[0].get('propiedades', {}).get('propiedad', [])
        print(f"modeloDatos props: {len(props)}")
        for p in props[:8]:
            print(f"  [{p.get('codigo','')}] {p.get('nombre','')[:40]} = {str(p.get('valor',''))[:30]}")
