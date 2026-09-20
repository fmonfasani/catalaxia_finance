import csv
import sys
from pathlib import Path

csv_path = Path(r"d:/Software Development/Porfolio/catalaxia-cedears-prod/data/contraste/contraste_argentinos_vs_investing.csv")
if not csv_path.exists():
    print(f"ERROR: file not found: {csv_path}")
    sys.exit(2)

total = 0
exact = 0
p1 = 0
p5 = 0
p10 = 0

with csv_path.open(encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        total += 1
        dr = row.get('desvio_rel','')
        try:
            val = float(dr)
        except:
            continue
        # treat very small values close to zero
        if abs(val) < 1e-12:
            exact += 1
        if abs(val) <= 0.01:
            p1 += 1
        if abs(val) <= 0.05:
            p5 += 1
        if abs(val) <= 0.10:
            p10 += 1

print(f"total_rows,{total}")
print(f"exact_matches,{exact},{(exact/total*100) if total else 0:.2f}%")
print(f"within_1%,{p1},{(p1/total*100) if total else 0:.2f}%")
print(f"within_5%,{p5},{(p5/total*100) if total else 0:.2f}%")
print(f"within_10%,{p10},{(p10/total*100) if total else 0:.2f}%")
