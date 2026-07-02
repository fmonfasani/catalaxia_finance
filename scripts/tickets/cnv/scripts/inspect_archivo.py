from pathlib import Path
import re

text = Path('scripts/tickets/cnv/eeff/LONG/1304.html').read_text(encoding='utf-8', errors='ignore')
m = re.search(r'propiedad id="Archivo"[^>]*>(.*?)</propiedad>', text, re.S)
print('archivo-block found', bool(m))
if m:
    print(m.group(1)[:3000])
