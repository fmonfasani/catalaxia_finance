"""Deep search for fecha_presentacion, fecha_reexpresion in HTML metadata."""
import re
from pathlib import Path

HTML_DIR = Path("scripts/tickets/cnv/eeff/eeff_html")

# Search ALL JS variables AND properties in the presentation data
for html_file in sorted(HTML_DIR.glob("*.html"))[:20]:
    html = html_file.read_text(encoding="utf-8")
    
    # Find the presentation JS variable (contains the XML data)
    # Look for all var/const assignments before the blob
    pres_start = html.find("var presentation ='")
    if pres_start < 0:
        continue
    
    # Check metadata section in the JS model
    meta = html[pres_start:pres_start + 10000]
    
    # Search for all property IDs and values
    props = re.findall(r'propiedad id="([^"]+)"[^>]*>(.*?)<', meta)
    interesting = [(p, v.strip()) for p, v in props if v.strip() and p not in ("Nro", "Rubro", "Monto", "AMEMoneda", "AMEActivoInversiones")]
    
    if interesting:
        print(f"\n--- {html_file.stem} ---")
        for p, v in interesting[:15]:
            print(f"  {p}: {v}")
    
    # Also check JS variables
    js_vars = re.findall(r'var\s+(\w+)\s*=\s*[\'\"]([^\'\"]+)[\'\"]', html)
    for name, val in js_vars:
        if name in ("presentationDate", "formTypeName", "currency", "formTypeId"):
            print(f"  JS var {name} = '{val}'")
