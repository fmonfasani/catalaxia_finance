"""Audit cnv_estados_v2: check all 5 critical points from the plan."""
import sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
con = sqlite3.connect(ROOT / "data" / "screener.db")
cur = con.cursor()

# Schema
cur.execute("SELECT sql FROM sqlite_master WHERE name='cnv_estados_v2'")
print("=== SCHEMA ===")
print(cur.fetchone()[0])

# Sample rows for TXAR
print("\n=== Sample rows TXAR ===")
cur.execute("SELECT * FROM cnv_estados_v2 WHERE cuit='30516888241' LIMIT 3")
cols = [d[0] for d in cur.description]
print("Cols:", cols)
for r in cur.fetchall():
    print(r)

# Check all conceptos for TXAR
print("\n=== TXAR distinct conceptos ===")
cur.execute("SELECT DISTINCT concepto FROM cnv_estados_v2 WHERE cuit='30516888241' ORDER BY concepto")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Point: CNV_* ratios
print("\n=== CNV_ ratios ===")
cur.execute("SELECT concepto FROM cnv_estados_v2 WHERE cuit='30516888241' AND concepto LIKE 'CNV_%' LIMIT 10")
for r in cur.fetchall():
    print(f"  {r[0]}")
print("CNV_ ratio count:", cur.execute("SELECT COUNT(*) FROM cnv_estados_v2 WHERE cuit='30516888241' AND concepto LIKE 'CNV_%'").fetchone()[0])

# Point: valor_comparativo (should be NULL for CNV aif2)
print("\n=== valor_comparativo check ===")
cur.execute("SELECT concepto, period_end, valor, valor_comparativo FROM cnv_estados_v2 WHERE cuit='30516888241' AND concepto='NetIncome' ORDER BY period_end DESC LIMIT 5")
for r in cur.fetchall():
    print(f"  {r}")

# Point: fecha_reexpresion
print("\n=== fecha_reexpresion check ===")
cur.execute("SELECT concepto, period_end, valor, fecha_reexpresion FROM cnv_estados_v2 WHERE cuit='30516888241' AND concepto='Assets' ORDER BY period_end DESC LIMIT 3")
for r in cur.fetchall():
    print(f"  {r}")

# Point: unidad_factor + unidad_medida
print("\n=== unidad metadata ===")
cur.execute("SELECT DISTINCT unidad_factor, unidad_medida FROM cnv_estados_v2 WHERE cuit='30516888241'")
for r in cur.fetchall():
    print(f"  factor={r[0]}  unidad='{r[1]}'")

# Now check the HTML for fecha_reexpresion and fecha_presentacion
import csv, re
# Check multiple HTMLs for these fields
html_dir = Path("scripts/tickets/cnv/eeff/eeff_html")
print("\n=== Searching HTMLs for FechaReexpresion ===")
founds = 0
for html_file in list(html_dir.glob("*.html"))[:50]:
    html = html_file.read_text(encoding="utf-8")
    m = re.search(r'propiedad id="(?:FechaReexpresion|FechaPresentacion|Reexpresion)".*?>(.*?)<', html)
    if m:
        if founds == 0:
            print(f"  Found in {html_file.stem}: {m.group(0)[:100]}")
        founds += 1
print(f"  HTMLs with reexpression metadata: {founds}/50")

# Also search for FechaPresentacion
print("\n=== Searching HTMLs for FechaPresentacion ===")
founds2 = 0
for html_file in list(html_dir.glob("*.html"))[:50]:
    html = html_file.read_text(encoding="utf-8")
    for m in re.finditer(r'FechaPresentacion.*?[<>\s]*(\d{4}-\d{2}-\d{2})', html):
        if founds2 == 0:
            print(f"  Found in {html_file.stem}: {m.group(1)}")
        founds2 += 1
print(f"  HTMLs with FechaPresentacion: {founds2}/50")

# PeriodoBalance
print("\n=== PeriodoBalance ===")
founds3 = 0
for html_file in list(html_dir.glob("*.html"))[:50]:
    html = html_file.read_text(encoding="utf-8")
    for m in re.finditer(r'PeriodoBalance[^>]*>\s*(\d+)', html):
        if founds3 == 0:
            print(f"  Found in {html_file.stem}: PeriodoBalance={m.group(1)}")
        founds3 += 1
print(f"  HTMLs with PeriodoBalance: {founds3}/50")
