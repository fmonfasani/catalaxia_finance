import requests, re

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36'}

# Get a FT=147 filing for a non-bank ADR (CEPU)
url_147 = 'https://aif2.cnv.gov.ar/presentations/publicview/ef29a051-d818-4463-b214-0faa9d328d97'

# Get a FT=339 dividend filing for GGAL
url_339 = 'https://aif2.cnv.gov.ar/presentations/publicview/13280c13-2796-470b-9734-0753478b9604'

def inspect_filing(url, label):
    print(f"{'='*80}")
    print(f"{label}")
    print(f"{'='*80}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    html = r.text
    print(f"HTML length: {len(html)}")
    
    # Find formTypeId
    m = re.search(r'formTypeId\s*=\s*["\']([^"\']+)["\']', html, re.I)
    if m: print(f"formTypeId: {m.group(1)}")
    m = re.search(r'formTypeName\s*=\s*["\']([^"\']+)["\']', html, re.I)
    if m: print(f"formTypeName: {m.group(1)}")
    m = re.search(r'periodoANIO\s*=\s*["\']([^"\']+)["\']', html, re.I)
    if m: print(f"periodoANIO: {m.group(1)}")
    m = re.search(r'periodoMES\s*=\s*["\']([^"\']+)["\']', html, re.I)
    if m: print(f"periodoMES: {m.group(1)}")
    
    # Find entities
    entities = re.findall(r'<entidad[^>]*>.*?</entidad>', html, re.IGNORECASE | re.DOTALL)
    print(f"Entities: {len(entities)}")
    
    for i, ent in enumerate(entities):
        ent_tag = re.search(r'<entidad\s+([^>]*)>', ent, re.IGNORECASE)
        if not ent_tag: continue
        attrs = ent_tag.group(1)
        eid = re.search(r'id=["\']([^"\']+)["\']', attrs)
        clave = re.search(r'clave=["\']([^"\']+)["\']', attrs)
        nelem = re.search(r'numeroelementos=["\']([^"\']+)["\']', attrs)
        eid_val = eid.group(1) if eid else "?"
        clave_val = clave.group(1) if clave else "?"
        nelem_val = nelem.group(1) if nelem else "?"
        
        filas = re.findall(r'<fila[^>]*>.*?</fila>', ent, re.IGNORECASE | re.DOTALL)
        nf = len(filas)
        
        print(f"  Entity #{i}: id={eid_val} clave='{clave_val}' filas={nf}")
        
        if nf > 0 and i < 8:
            for j, fila in enumerate(filas[:3]):
                codes = re.findall(r'<propiedad\s+id=["\']([^"\']+)["\'][^>]*>([^<]*)</propiedad>', fila, re.IGNORECASE)
                code_dict = {c[0]: c[1].strip() for c in codes}
                code_str = "; ".join([f"{k}={v[:40]}" for k, v in code_dict.items()])
                print(f"    [{j+1}] {code_str}")
            if nf > 3:
                print(f"    ... + {nf-3} more")

inspect_filing(url_147, "CEPU - FT=147 (Estados Contables NIIF)")
inspect_filing(url_339, "GGAL - FT=339 (Pago de Dividendos)")
