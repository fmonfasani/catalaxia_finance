"""
04_backtest.py

Compara FX TIKR trimestral contra A3500/OFFICIAL/MEP/CCL y cualquier fuente
presente en normalized/fx_panel_normalized.csv.
NO selecciona retrospectivamente la fuente.
"""
from pathlib import Path
import pandas as pd
import numpy as np

panel = Path("normalized/fx_panel_normalized.csv")
tikr = Path("outputs/tikr_quarterly_fx_stats.csv")
if not panel.exists() or not tikr.exists():
    raise SystemExit("FAIL: ejecutar 02_build_quarterly_panel.py y 03_tikr_quarterly_stats.py primero")

p = pd.read_csv(panel, parse_dates=["date","target_date"])
t = pd.read_csv(tikr)

t["year"] = t["quarter"].str.extract(r"(20\d{2})").astype(int)
t["q"] = t["quarter"].str.extract(r"Q([1-4])").astype(int)
t["target_date"] = pd.to_datetime(
    t["year"].astype(str) + "-" + (t["q"]*3).astype(str) + "-01"
) + pd.offsets.MonthEnd(0)

# Use the last valid observation <= quarter-end for each source/instrument.
rows=[]
for (source, target), g in p.groupby(["source","target_date"]):
    g=g[g["date"]<=target]
    if g.empty: continue
    latest=g["date"].max()
    vals=g.loc[g["date"]==latest,"fx"].dropna()
    if not vals.empty:
        rows.append([source,target,latest,vals.median(),len(vals)])

ref=pd.DataFrame(rows,columns=["source","target_date","effective_date","fx","n"])
merged=ref.merge(t[["target_date","mode"]],on="target_date",how="inner")
merged["abs_error"]=(merged["fx"]-merged["mode"]).abs()
merged["rel_error"]=merged["abs_error"]/merged["mode"]
merged["within_0_1"]=merged["rel_error"]<=0.001
merged["within_0_25"]=merged["rel_error"]<=0.0025
merged["within_0_5"]=merged["rel_error"]<=0.005
merged["within_1"]=merged["rel_error"]<=0.01

summary=(merged.groupby("source")
    .agg(n=("rel_error","size"),
         MAE=("abs_error","mean"),
         RMSE=("abs_error",lambda x: np.sqrt(np.mean(x*x))),
         MEDIAN_ABS_ERROR=("abs_error","median"),
         PCT_WITHIN_0_1=("within_0_1","mean"),
         PCT_WITHIN_0_25=("within_0_25","mean"),
         PCT_WITHIN_0_5=("within_0_5","mean"),
         PCT_WITHIN_1=("within_1","mean"))
    .reset_index())

for c in summary.columns[4:]:
    summary[c]*=100

Path("outputs").mkdir(exist_ok=True)
merged.to_csv("outputs/fx_tikr_backtest_detail.csv",index=False)
summary.to_csv("outputs/fx_tikr_backtest_summary.csv",index=False)

print("\n=== BACKTEST ===")
print(summary.to_string(index=False))
