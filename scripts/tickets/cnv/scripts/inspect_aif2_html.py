"""Inspect ALUA AIF2 HTML to find dividend codes"""
import csv, re, requests

with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['ticker'] == 'ALUA' and row['formTypeId'] == '147':
            recent = row
            break

resp = requests.get(recent['url'], timeout=30)
html = resp.text

# Find the equity section (codes around 221xxxx)
# Look for patterns in raw HTML around equity codes
print("=== Looking at raw HTML around 221xxxx codes ===")
for code in [2210300, 2210500, 2210900, 2211100, 2211200, 2211300, 2210999, 2211999, 2212999, 2213999, 2299999]:
    idx = html.find(str(code))
    if idx >= 0:
        start = max(0, idx - 200)
        end = min(len(html), idx + 300)
        snippet = html[start:end]
        # Clean for display
        snippet = snippet.replace('\n', ' ').replace('\r', ' ')
        snippet = re.sub(r'\s+', ' ', snippet)
        print(f"\n--- Code {code} at offset {idx} ---")
        print(snippet[:500])

# Also look for "Resultados No Asignados" and "Dividend" mentions
print("\n\n=== Searching for dividend/resultados mentions ===")
for term in ['Dividend', 'dividend', 'Resultados No Asignados', 'resultados no asignados', 'Distribución', 'distribucion']:
    for m in re.finditer(term, html):
        start = max(0, m.start() - 150)
        end = min(len(html), m.end() + 200)
        snippet = html[start:end].replace('\n', ' ').replace('\r', ' ')
        snippet = re.sub(r'\s+', ' ', snippet)
        print(f"\n'{term}' at {m.start()}: {snippet[:400]}")

# Check structure: how many columns in the HTML table for equity section?
print("\n\n=== Table structure near equity ===")
# Find sections with <th> or table headers
th_sections = re.finditer(r'<th[^>]*>(.*?)</th>', html, re.DOTALL)
for i, m in enumerate(th_sections):
    if i < 20:
        print(f"  TH[{i}]: {m.group(1).strip()[:60]}")
