from pathlib import Path
import pandas as pd
import numpy as np

p = Path("outputs/tikr_fx_comparison_detail.csv")
if not p.exists():
    raise SystemExit("Run 03_COMPARE_TIKR.py first")

df = pd.read_csv(p)

out=[]
for source,g in df.groupby("source"):
    e = g["relative_error"].dropna()
    if e.empty:
        continue
    q1,q3=e.quantile([.25,.75])
    iqr=q3-q1
    clean=e[(e>=q1-1.5*iqr)&(e<=q3+1.5*iqr)]
    out.append({
        "source":source,
        "n":len(e),
        "raw_mean_rel_error":e.mean(),
        "raw_median_rel_error":e.median(),
        "trimmed_10pct_mean":e.sort_values().iloc[int(len(e)*.1):max(int(len(e)*.9), int(len(e)*.1)+1)].mean() if len(e)>=3 else e.mean(),
        "iqr_filtered_mean":clean.mean(),
        "max_rel_error":e.max(),
    })

res=pd.DataFrame(out)
res.to_csv("outputs/tikr_fx_robustness.csv",index=False)
print(res.to_string(index=False))
