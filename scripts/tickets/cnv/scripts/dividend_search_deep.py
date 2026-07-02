"""Thorough search for dividend data in a recent ALUA AIF2 annual filing"""
import csv, re, requests, sqlite3

# Find ALUA's most recent ANNUAL filing (tipo='A' in cnv_estados)
db = sqlite3.connect('data/screener.db')
cur = db.execute("""
    SELECT period_end, form, accn FROM cnv_estados 
    WHERE ticker='ALUA' AND concepto='NetIncome' AND tipo='A'
    ORDER BY period_end DESC LIMIT 1
""")
latest = cur.fetchone()
print(f"Latest annual period: {latest[0]} | filing: {latest[2]}")
db.close()

# Find the filing with that GUID
with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    target = None
    for row in reader:
        if row['ticker'] == 'ALUA' and row['formTypeId'] == '147' and row['guid'] == latest[2]:
            target = row
            break

if not target:
    # Try first 500 rows for ALUA
    with open('scripts/tickets/cnv/datos/links_eeff_refined.csv', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if row['ticker'] == 'ALUA' and row['formTypeId'] == '147':
                target = row
                if i > 400:
                    break
                break

print(f"Target GUID: {target['guid']}")
print(f"URL: {target['url']}")

resp = requests.get(target['url'], timeout=30)
html = resp.text
print(f"HTML size: {len(html)} bytes")

# Search ALL XML-like tags in the HTML
all_tags = set()
for m in re.finditer(r'<(\w+)[>\s]', html):
    all_tags.add(m.group(1))
print(f"\nAll XML tags: {sorted(all_tags)}")

# Check for section/division markers
print("\n=== Section/division markers ===")
for marker in ['cuadro', 'seccion', 'tabla', 'capitulo', 'rubro', 'ESTADO', 'CAMBIO', 
               'PATRIMONIO', 'DIVIDEND', 'RESULTADO', 'INTEGRAL', 'FLUJO', 'EFECTIVO',
               'BALANCE', 'SITUACION', 'EQUITY', 'INCOME']:
    matches = list(re.finditer(marker, html, re.IGNORECASE))
    if 0 < len(matches) < 20:
        print(f"  '{marker}': {len(matches)} matches")

# Extract ALL <fila> elements and ALL <propiedad> structures
all_filas = re.findall(r'<fila[^>]*>.*?</fila>', html, re.DOTALL)
print(f"\nTotal <fila> elements: {len(all_filas)}")

# Try different XML pattern variations
print("\n=== Trying all data patterns ===")
# Pattern: any <tag>code</tag> where code is 7-8 digits
code_patterns = set()
for m in re.finditer(r'>([1-8]\d{6})<', html):
    code_patterns.add(int(m.group(1)))
print(f"Total unique codes in HTML: {len(code_patterns)}")

# Labels for codes not in our current extraction
known = {1122500,1121999,1120100,1139999,1110100,1110200,1119999,1999999,
         2210999,2211999,2212999,2299999,2322200,2321999,2339999,2312300,2319999,2399999,
         3000100,3000200,3009999,3011600,3019999,3021400,3021500,3021800,3029999,3031100,3049999,3099999,
         3240000,3241100,3241200,3241300,
         8000000,8000001,8000003,8000004,8000005,8000006,8000007,8000008,8000009,8000010,8000011,8000012,8000013,8000014,8000015,8000016,8000017,
         2210300,2210500,2210900,2211100,2211200,2211300,2213999,
         1111999,1112400,1112500,1122300,1122400,
         2311999,2312200,2312400,2322100,2322300,
         3011100,3011200,3011300,3011301,3011400,3021900,3061999,
         2999999}

unknown = sorted(int(c) for c in code_patterns if int(c) not in known)
print(f"Unknown codes: {len(unknown)}")

# Get labels for all codes (both known and unknown)
for code in sorted(code_patterns):
    m = re.search(rf'<propiedad id="Nro"[^>]*>{code}</propiedad>.*?<propiedad id="Rubro"[^>]*>(.*?)</propiedad>.*?<propiedad id="Monto"[^>]*>(.*?)</propiedad>', html, re.DOTALL)
    if m:
        label = m.group(1).strip()
        amount = m.group(2).strip()
        if code in unknown:
            print(f"  UNKNOWN {code}: {label:<60} {amount}")
    else:
        if code in unknown:
            print(f"  UNKNOWN {code}: (no label found)")

# Search for dividend words in raw HTML
print("\n=== RAW SEARCH for dividend/distribution words ===")
for word in ['dividend', 'DIVIDEND', 'Dividend', 'pago', 'PAGO', 'distrib', 'DISTRIB']:
    matches = list(re.finditer(word, html))
    if matches:
        print(f"  '{word}': {len(matches)} matches")
        for m in matches[:5]:
            ctx = html[max(0,m.start()-80):m.end()+80]
            ctx = ctx.replace('\n',' ').replace('\r',' ')
            ctx = re.sub(r'\s+', ' ', ctx)
            print(f"    offset {m.start()}: ...{ctx}...")

# Check for "Cambios en el Patrimonio" section
print("\n=== CAMBIOS / CHANGES section ===")
for m in re.finditer(r'(CAMBIO|CAMBIOS|MOVIMIENTO|MOVIMIENTOS).{0,30}(PATRIMONIO|PN|EQUITY)', html, re.IGNORECASE):
    ctx = html[max(0,m.start()-100):m.end()+200]
    ctx = ctx.replace('\n',' ').replace('\r',' ')
    ctx = re.sub(r'\s+', ' ', ctx)
    print(f"  offset {m.start()}: ...{ctx[:300]}...")

# Check if there's a second table (the changes in equity would be a separate <table>)
tables = re.findall(r'<(?:table|cuadro)[^>]*>.*?</(?:table|cuadro)>', html, re.DOTALL|re.IGNORECASE)
print(f"\nHTML <table>/<cuadro> sections: {len(tables)}")

# Look for ANY other table structure
all_sections = re.findall(r'<(?:div|section|tbody)[^>]*>', html)
print(f"Other structural tags: {len(all_sections)}")

# Check for <propiedad> with id='...' that is NOT Nro/Rubro/Monto
other_props = set()
for m in re.finditer(r'<propiedad id="([^"]+)"', html):
    other_props.add(m.group(1))
print(f"Unique propiedad ids: {sorted(other_props)}")

# Check for 'EjercicioAnterior' (previous year comparative)
for m in re.finditer(r'EjercicioAnterior', html):
    ctx = html[max(0,m.start()-100):m.end()+200]
    ctx = ctx.replace('\n',' ').replace('\r',' ')
    ctx = re.sub(r'\s+', ' ', ctx)
    print(f"  '{'EjercicioAnterior'}' at {m.start()}: {ctx[:200]}...")

# Look at first 5000 chars for structure
print("\n=== FIRST 3000 CHARS (structure) ===")
print(html[:3000][:2000])
