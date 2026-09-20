from pathlib import Path
import json

# ============================================================
# DECISION POINTS — FREEZE THESE BEFORE RUNNING THE BACKTEST
# ============================================================
CONFIG = {
    "version": "FX-CLOSEOUT-1.0",
    "quarter_selection": "fixture_12",  # DECIDE: fixture_12 | all_available
    "reference_sources": ["A3500", "OFICIAL"],  # DECIDE before run
    "include_mep_ccl": True,              # if data exists, include it; no invented values
    "tikr_statistic": "fixture_value",    # FIXED for this POC: values supplied by fixture
    "comparison_date_policy": "effective_market_date",  # DECIDE: effective_market_date
    "missing_policy": "NO_FILL",           # MUST remain NO_FILL
    "winner_policy": "NO_WINNER",         # MUST remain NO_WINNER
    "provenance_policy": "SOURCE_REQUIRED",
    "acceptance": {
        "minimum_tikr_provenance": True,
        "minimum_reference_coverage": 1.0,
        "comparison_must_execute": True,
        "no_proprietary_method_claim_from_error_alone": True,
    }
}

Path("outputs").mkdir(exist_ok=True)
Path("00_DEFINIR").mkdir(exist_ok=True)
Path("00_DEFINIR/closeout_decision_config.json").write_text(
    json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("CONFIG FROZEN")
print(json.dumps(CONFIG, indent=2, ensure_ascii=False))
