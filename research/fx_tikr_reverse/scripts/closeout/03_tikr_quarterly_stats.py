"""
03_tikr_quarterly_stats.py

Calcula moda y mediana del FX implícito de TIKR.
Busca un dataset TIKR existente bajo tikr/, data/, normalized/, raw/.
Si existe una tabla ARS/USD alineada por Concept y período, calcula ARS/USD.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from collections import Counter

ROOTS = [Path("tikr"), Path("data"), Path("normalized"), Path("raw"), Path("outputs")]
files = []
for r in ROOTS:
    if r.exists():
        files += [p for p in r.rglob("*") if p.suffix.lower() in [".csv",".xlsx",".xls"]]

records = []
for p in files:
    try:
        sheets = pd.read_excel(p, sheet_name=None) if p.suffix.lower() in [".xlsx",".xls"] else {"_":pd.read_csv(p)}
    except Exception:
        continue
    for sheet, df in sheets.items():
        cols = {str(c).lower():c for c in df.columns}
        concept = next((c for k,c in cols.items() if "concept" in k or "metric" in k), None)
        if concept is None:
            continue

        # Detect quarter columns such as 2024-Q1, 2024 Q1, etc.
        qcols = [c for c in df.columns if pd.Series([str(c)]).str.contains(r"20\d{2}[- _]?Q[1-4]", case=False, regex=True).iloc[0]]
        if not qcols:
            continue

        # Handle files with explicit ARS/USD records.
        currency_c = next((c for k,c in cols.items() if "currency" in k or "moneda" in k), None)
        if currency_c:
            currencies = df[currency_c].astype(str).str.upper()
            for q in qcols:
                vals = pd.to_numeric(df[q], errors="coerce")
                ars = vals[currencies.str.contains("ARS")]
                usd = vals[currencies.str.contains("USD")]
                if len(ars) and len(usd):
                    records.append((p,sheet,q,"currency_rows",ars.sum()/usd.sum()))
        # Handle explicit ARS/USD columns on same row.
        for q in qcols:
            s = df[q].astype(str)
            # If values look like "ARS / USD" is not supported; preserve file for manual adapter.
            pass

# Prefer the already generated Catalaxia quarterly inference if present.
candidate = Path("outputs/tikr_quarterly_fx.csv")
if candidate.exists():
    out = pd.read_csv(candidate)
    print(out.to_string(index=False))
    raise SystemExit(0)

if not records:
    print("NO_DETERMINABLE: no generic TIKR ARS/USD quarterly table detected.")
    print("Use the project adapter for the exact TIKR workbook.")
    raise SystemExit(2)

out = pd.DataFrame(records, columns=["file","sheet","quarter","method","fx"])
out["fx_rounded"] = out["fx"].round(2)
stats = []
for q,g in out.groupby("quarter"):
    vals = g["fx_rounded"].dropna().tolist()
    counts = Counter(vals)
    mode, freq = counts.most_common(1)[0]
    stats.append([q,len(vals),np.mean(vals),np.median(vals),mode,freq])
res = pd.DataFrame(stats, columns=["quarter","n","mean","median","mode","mode_freq"])
Path("outputs").mkdir(exist_ok=True)
res.to_csv("outputs/tikr_quarterly_fx_stats.csv", index=False)
print(res.to_string(index=False))
