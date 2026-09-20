"""Build mini-whitelist of parseable GUIDs from v1 and add --codigos to job5_v2."""
import csv, re, sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
BASE = Path(__file__).resolve().parent
DB = ROOT / "data" / "screener.db"
WHITELIST_ORIG = BASE / "datos" / "whitelist_eeff.csv"
WHITELIST_CODIGOS = BASE / "datos" / "whitelist_eeff_codigos.csv"
SUBSET = BASE / "datos" / "empresas_subset.csv"

# 1. Get parseable GUIDs from v1 cnv_estados
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("SELECT DISTINCT accn FROM cnv_estados WHERE fuente='cnv-aif2' AND accn != ''")
v1_guids = {r[0] for r in cur.fetchall()}
con.close()
print(f"v1 parseable GUIDs: {len(v1_guids)}")

# 2. Get 72 CUITs from subset
with open(SUBSET, encoding='utf-8-sig') as f:
    cuits_72 = {r['cuit'].strip() for r in csv.DictReader(f) if r.get('cuit')}

# 3. Filter whitelist to only parseable GUIDs for 72 entities
filtered = []
total_in_72 = 0
with open(WHITELIST_ORIG, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cu = row['cuit'].strip()
        if cu not in cuits_72:
            continue
        total_in_72 += 1
        if row['guid'].strip() in v1_guids:
            filtered.append(row)

# 4. Write mini-whitelist
with open(WHITELIST_CODIGOS, 'w', newline='', encoding='utf-8-sig') as f:
    if filtered:
        w = csv.DictWriter(f, fieldnames=filtered[0].keys())
        w.writeheader()
        w.writerows(filtered)

print(f"GUIDs for 72 entities in whitelist: {total_in_72}")
print(f"Parseable (in v1): {len(filtered)}")
print(f"Saved to: {WHITELIST_CODIGOS}")

# 5. Add --codigos flag to job5_v2
job5_path = BASE / "jobs" / "job5_v2_extract_eeff.py"
content = job5_path.read_text(encoding='utf-8')

# Check if --codigos already added
if '--codigos' not in content:
    # Add --codigos arg parsing before the WHITELIST usage
    content = content.replace(
        'WHITELIST = BASE / "datos" / "whitelist_eeff.csv"',
        'WHITELIST = BASE / "datos" / "whitelist_eeff_codigos.csv" if "--codigos" in sys.argv else BASE / "datos" / "whitelist_eeff.csv"'
    )
    job5_path.write_text(content, encoding='utf-8')
    print("Added --codigos flag to job5_v2")
else:
    print("--codigos flag already present")
