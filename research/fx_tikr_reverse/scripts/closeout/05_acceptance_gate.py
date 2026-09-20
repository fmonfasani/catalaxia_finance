"""
05_acceptance_gate.py

Gate objetivo. No declara ganador: certifica conformidad con el contrato.
"""
from pathlib import Path
import json, pandas as pd

contract=json.loads(Path("00_DEFINIR/fx_acceptance_contract.json").read_text(encoding="utf-8"))
s=Path("outputs/fx_tikr_backtest_summary.csv")
if not s.exists():
    raise SystemExit("FAIL: falta outputs/fx_tikr_backtest_summary.csv")

df=pd.read_csv(s)
results=[]
for _,r in df.iterrows():
    coverage = r["n"] / 12 if r["n"] <= 12 else 1
    results.append({
        "source":r["source"],
        "coverage":coverage,
        "coverage_pass":coverage>=contract["minimum_coverage"],
        "MAE":r["MAE"],
        "RMSE":r["RMSE"],
        "within_0_5_pct":r["PCT_WITHIN_0_5"],
        "within_1_pct":r["PCT_WITHIN_1"],
    })

out=pd.DataFrame(results)
Path("outputs/fx_acceptance_matrix.csv").write_text(out.to_csv(index=False),encoding="utf-8")

print(out.to_string(index=False))
print("\nSTATUS: BACKTEST EVIDENCE GENERATED")
print("NOTE: this gate does not certify TIKR's proprietary methodology.")
