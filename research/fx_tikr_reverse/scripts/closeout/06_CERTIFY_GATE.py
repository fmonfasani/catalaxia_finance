from pathlib import Path
import json, pandas as pd

v=Path("outputs/validation_matrix.csv")
p=Path("outputs/tikr_provenance_audit.json")
if not v.exists():
    raise SystemExit("FAIL: validation not executed")

df=pd.read_csv(v)
failed=df[~df["pass"].astype(bool)]

prov=json.loads(p.read_text()) if p.exists() else {}
primary=prov.get("provenance_status")=="SOURCE_FOUND_CANDIDATE"

if len(failed):
    status="BLOCKED"
    reason="mandatory evidence/tests missing"
elif not primary:
    status="BLOCKED"
    reason="TIKR fixture primary provenance not established"
else:
    status="READY_FOR_INDEPENDENT_CERTIFICATION"
    reason="engineering gate passed; proprietary methodology remains unproven"

report={
    "status":status,
    "reason":reason,
    "failed_requirements":failed.to_dict(orient="records"),
    "tikr_fx_method":"UNKNOWN",
    "confidence":0.0,
    "important_limit":"A statistical match does not establish TIKR proprietary methodology."
}

Path("outputs/CERTIFICATION_GATE.json").write_text(
    json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8"
)

print(json.dumps(report,indent=2,ensure_ascii=False))
