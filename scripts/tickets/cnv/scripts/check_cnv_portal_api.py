import requests, re

r = requests.get('https://aif2.cnv.gov.ar/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
html = r.text
print('Status:', r.status_code, 'Length:', len(html))

# Extract all script tags
for m in re.finditer(r'<script[^>]*src=["\']([^"\']+)["\']', html, re.I):
    u = m.group(1)
    print('SCRIPT:', u)

# Extract forms
for m in re.finditer(r'<form[^>]*action=["\']([^"\']*)["\']', html, re.I):
    print('FORM action:', m.group(1))

# Print all <input> types
for m in re.finditer(r'<input[^>]*>', html, re.I):
    inp = m.group(0)
    inp_type = re.search(r'type=["\']([^"\']*)["\']', inp, re.I)
    inp_name = re.search(r'name=["\']([^"\']*)["\']', inp, re.I)
    inp_id = re.search(r'id=["\']([^"\']*)["\']', inp, re.I)
    print(f'INPUT type={inp_type.group(1) if inp_type else "?"} name={inp_name.group(1) if inp_name else "?"} id={inp_id.group(1) if inp_id else "?"}')

# Print first 3000 chars
print()
print('=== FIRST 3000 CHARS ===')
print(html[:3000])
