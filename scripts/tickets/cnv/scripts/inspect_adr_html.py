import requests, re

url = 'https://aif2.cnv.gov.ar/presentations/publicview/00b2561d-2c21-48b9-89a8-373f74aafe8b'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36'}
r = requests.get(url, headers=headers, timeout=30)
html = r.text

print(f"Status: {r.status_code}")
print(f"HTML length: {len(html)}")
print()

# Check for data-related patterns
patterns = ['fila', 'codigo', 'datatable', 'cuenta', 'concepto', 'json', 'xml', 'report', 'periodo', 'balance']
for p in patterns:
    matches = re.findall(p, html, re.I)
    if matches:
        print(f"'{p}': {len(matches)} occurrences")

# Show metadata variables
for pattern_name, rx in [
    ("presentationIdGlobal", r"presentationIdGlobal\s*=\s*['\"]([^'\"]+)['\"]"),
    ("formTypeName", r"formTypeName\s*=\s*['\"]([^'\"]+)['\"]"),
    ("formTypeId", r"formTypeId\s*=\s*['\"]([^'\"]+)['\"]"),
    ("periodoANIO", r"periodoANIO\s*=\s*['\"]([^'\"]+)['\"]"),
]:
    m = re.search(rx, html, re.I)
    if m:
        print(f"{pattern_name}: {m.group(1)}")

# Show sections of interest around 3000-4000 chars
print(f"\nHTML around offset 3000:")
print(html[3000:4000])
print(f"\nHTML around offset 10000:")
print(html[10000:11000])
print(f"\nHTML around offset 50000:")
print(html[50000:51000])

# Look for API endpoints
for m in re.finditer(r"(url|src|href|action)\s*[:=]\s*[\"']([^\"']+)[\"']", html, re.I):
    u = m.group(2)
    if any(k in u.lower() for k in ['data', 'table', 'report', 'load', 'get']):
        print(f"Endpoint: {u}")
