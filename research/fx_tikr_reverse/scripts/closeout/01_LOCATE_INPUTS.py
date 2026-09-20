from pathlib import Path
import json

ROOT = Path(".")
candidates = {
    "tikr_fixture": [
        "fixtures/tikr_fx_12.csv",
        "research/fx_tikr_reverse/fixtures/tikr_fx_12.csv",
    ],
    "fx_reference": [
        "normalized/fx_reference.parquet",
        "research/fx_tikr_reverse/normalized/fx_reference.parquet",
    ],
    "run_report": [
        "RUN_REPORT.md",
        "research/fx_tikr_reverse/RUN_REPORT.md",
    ],
    "provenance": [
        "PROVENANCE.md",
        "research/fx_tikr_reverse/PROVENANCE.md",
    ],
}

found = {}
for key, paths in candidates.items():
    found[key] = next((str(Path(p)) for p in paths if Path(p).exists()), None)

print(json.dumps(found, indent=2))
Path("outputs/input_manifest.json").write_text(
    json.dumps(found, indent=2), encoding="utf-8"
)

missing = [k for k,v in found.items() if v is None]
if missing:
    print("MISSING:", ", ".join(missing))
