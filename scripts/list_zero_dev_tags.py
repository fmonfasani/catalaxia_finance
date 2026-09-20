import csv
from pathlib import Path
csv_path = Path(r"d:/Software Development/Porfolio/catalaxia-cedars-prod/data/contraste/contraste_argentinos_vs_investing.csv")
# fallback correct path
csv_path = Path(r"d:/Software Development/Porfolio/catalaxia-cedears-prod/data/contraste/contraste_argentinos_vs_investing.csv")
if not csv_path.exists():
    print(f"ERROR: file not found: {csv_path}")
    raise SystemExit(2)

counts = {}
examples = {}
with csv_path.open(encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        dr = row.get('desvio_rel','')
        try:
            val = float(dr)
        except:
            continue
        if abs(val) < 1e-12:
            concept = row.get('concepto') or ''
            counts[concept] = counts.get(concept,0) + 1
            if concept not in examples:
                examples[concept] = []
            if len(examples[concept]) < 5:
                examples[concept].append((row.get('ticker',''), row.get('period_end','')))

# print sorted by count desc
for concept, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    ex = ";".join([f"{t}/{p}" for t,p in examples.get(concept,[])])
    print(f"{concept},{cnt},{ex}")

print(f"TOTAL_CONCEPTS_WITH_ZERO_DEV,{len(counts)}")
