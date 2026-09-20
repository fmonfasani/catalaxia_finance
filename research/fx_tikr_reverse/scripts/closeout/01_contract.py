"""
01_contract.py
Congela el contrato de aceptación antes del backtest.
"""
from pathlib import Path
import json

CONTRACT = {
    "version": "FX-RE-001",
    "status": "FROZEN",
    "target_dates": ["03-31", "06-30", "09-30", "12-31"],
    "quarter_rule": "last valid market/publication date <= target date",
    "tikr_estimator": {
        "primary": "mode",
        "secondary": "median",
        "mode_round_decimals": 2,
    },
    "candidate_sources": ["A3500", "OFFICIAL", "MEP", "CCL", "MEP_RECONSTRUCTED", "CCL_RECONSTRUCTED"],
    "metrics": ["MAE", "RMSE", "MEDIAN_ABS_ERROR", "PCT_WITHIN_0.1", "PCT_WITHIN_0.25", "PCT_WITHIN_0.5", "PCT_WITHIN_1.0"],
    "minimum_coverage": 0.90,
    "no_retrospective_rule_selection": True,
    "missing_data": "NO_FILL",
}

Path("00_DEFINIR").mkdir(exist_ok=True)
Path("00_DEFINIR/fx_acceptance_contract.json").write_text(
    json.dumps(CONTRACT, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("PASS: contract frozen -> 00_DEFINIR/fx_acceptance_contract.json")
