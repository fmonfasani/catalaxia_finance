import requests, re, html as html_mod

url = 'https://aif2.cnv.gov.ar/presentations/publicview/00b2561d-2c21-48b9-89a8-373f74aafe8b'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36'}
r = requests.get(url, headers=headers, timeout=30)
html_content = r.text

# Find all entity blocks in the XML
entities = re.findall(r'<entidad[^>]*>.*?</entidad>', html_content, re.IGNORECASE | re.DOTALL)
print(f"Total entities found: {len(entities)}")

for i, ent in enumerate(entities):
    # Get entity attributes
    ent_tag = re.search(r'<entidad\s+([^>]*)>', ent, re.IGNORECASE)
    if not ent_tag:
        continue
    attrs = ent_tag.group(1)
    eid = re.search(r'id=["\']([^"\']+)["\']', attrs)
    clave = re.search(r'clave=["\']([^"\']+)["\']', attrs)
    nelem = re.search(r'numeroelementos=["\']([^"\']+)["\']', attrs)
    vis = re.search(r'visibilidad=["\']([^"\']+)["\']', attrs)
    
    eid_val = eid.group(1) if eid else "?"
    clave_val = clave.group(1) if clave else "?"
    nelem_val = nelem.group(1) if nelem else "?"
    vis_val = vis.group(1) if vis else "?"
    
    print(f"\nEntity #{i}: id={eid_val} clave='{clave_val}' elementos={nelem_val} visibilidad={vis_val}")
    
    # Extract all fila elements
    filas = re.findall(r'<fila[^>]*>.*?</fila>', ent, re.IGNORECASE | re.DOTALL)
    print(f"  Filas: {len(filas)}")
    
    if len(filas) > 0:
        if i == 5:
            # Show all 73 accounts summarized
            for j, fila in enumerate(filas):
                codes = re.findall(r'<propiedad\s+id=["\']([^"\']+)["\'][^>]*>([^<]*)</propiedad>', fila, re.IGNORECASE)
                code_dict = {c[0]: c[1].strip() for c in codes}
                nro = code_dict.get('Nro', '?')
                rubro = code_dict.get('Rubro', '?')
                monto = code_dict.get('Monto', '?')
                if j < 3 or j >= len(filas) - 3:
                    print(f"  [{j+1}] Nro={nro} Rubro={rubro[:40]} Monto={monto}")
                elif j == 3:
                    print(f"  ... {len(filas)-6} more items ...")
        else:
            for j, fila in enumerate(filas[:3]):
                codes = re.findall(r'<propiedad\s+id=["\']([^"\']+)["\'][^>]*>([^<]*)</propiedad>', fila, re.IGNORECASE)
                code_dict = {c[0]: c[1].strip() for c in codes}
                code_str = ", ".join([f"{k}={v[:20]}" for k, v in code_dict.items()])
                print(f"  [{j+1}] {code_str}")
            if len(filas) > 3:
                print(f"  ... + {len(filas)-3} more")
