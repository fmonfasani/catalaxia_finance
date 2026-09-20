"""
Comparación real TIKR vs referencias.
No determina ganador.
No modifica datos.
"""
from pathlib import Path
import json, pandas as pd, numpy as np

cfg = json.loads(Path("00_DEFINIR/closeout_decision_config.json").read_text())

fixture_path = Path("fixtures/tikr_fx_12.csv")
if not fixture_path.exists():
    fixture_path = Path("research/fx_tikr_reverse/fixtures/tikr_fx_12.csv")

ref_path = Path("normalized/fx_reference.parquet")
if not ref_path.exists():
    ref_path = Path("research/fx_tikr_reverse/normalized/fx_reference.parquet")

if not fixture_path.exists():
    raise SystemExit("FAIL: TIKR fixture missing")
if not ref_path.exists():
    raise SystemExit("FAIL: fx_reference.parquet missing")

t = pd.read_csv(fixture_path)
r = pd.read_parquet(ref_path)

t["target_date"] = pd.to_datetime(t["target_date"])
r["date"] = pd.to_datetime(r["date"])

if t["period"].duplicated().any():
    raise SystemExit("FAIL: duplicate TIKR periods")

rows = []
for source in cfg["reference_sources"]:
    x = r[r["fx_type"].astype(str).str.upper() == source.upper()].copy()
    if x.empty:
        continue

    x = x[["period","date","fx_value","provenance_id"]].copy()
    x = x.rename(columns={
        "date":"reference_target_date",
        "fx_value":"reference_fx",
        "provenance_id":"reference_provenance"
    })

    m = t.merge(x, on="period", how="left")
    m["source"] = source
    m["absolute_error"] = (m["tikr_fx"] - m["reference_fx"]).abs()
    m["relative_error"] = m["absolute_error"] / m["tikr_fx"]
    m["within_0_1pct"] = m["relative_error"] <= .001
    m["within_0_25pct"] = m["relative_error"] <= .0025
    m["within_0_5pct"] = m["relative_error"] <= .005
    m["within_1pct"] = m["relative_error"] <= .01
    rows.append(m)

if not rows:
    raise SystemExit("FAIL: no reference series available")

detail = pd.concat(rows, ignore_index=True)

summary = (
    detail.groupby("source", dropna=False)
    .agg(
        n=("period","count"),
        valid=("reference_fx", lambda x: x.notna().sum()),
        MAE=("absolute_error","mean"),
        RMSE=("absolute_error", lambda x: np.sqrt(np.nanmean(x*x))),
        MEDIAN_ABS_ERROR=("absolute_error","median"),
        PCT_WITHIN_0_1=("within_0_1pct","mean"),
        PCT_WITHIN_0_25=("within_0_25pct","mean"),
        PCT_WITHIN_0_5=("within_0_5pct","mean"),
        PCT_WITHIN_1=("within_1pct","mean"),
    ).reset_index()
)

for c in ["PCT_WITHIN_0_1","PCT_WITHIN_0_25","PCT_WITHIN_0_5","PCT_WITHIN_1"]:
    summary[c] *= 100

detail.to_csv("outputs/tikr_fx_comparison_detail.csv", index=False)
summary.to_csv("outputs/tikr_fx_comparison_summary.csv", index=False)

result = {
    "status": "EXECUTED",
    "sources": cfg["reference_sources"],
    "rows": len(detail),
    "summary": summary.to_dict(orient="records"),
    "winner": None,
    "methodology_conclusion": "NOT_DETERMINABLE_FROM_ERROR_ALONE"
}
Path("outputs/tikr_fx_comparison.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
)

print(summary.to_string(index=False))
print("\nNO WINNER DECLARED.")
