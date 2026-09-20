from pathlib import Path
import json, pandas as pd

cfg=json.loads(Path("00_DEFINIR/closeout_decision_config.json").read_text())
results=[]

# 1 comparison exists
comparison=Path("outputs/tikr_fx_comparison_detail.csv")
results.append(("comparison_executed", comparison.exists()))

# 2 summary exists
summary=Path("outputs/tikr_fx_comparison_summary.csv")
results.append(("comparison_summary", summary.exists()))

# 3 provenance audit exists
prov=Path("outputs/tikr_provenance_audit.json")
results.append(("provenance_audit", prov.exists()))

# 4 reference coverage
if summary.exists():
    s=pd.read_csv(summary)
    for _,r in s.iterrows():
        results.append((f"coverage_{r['source']}", int(r["valid"]) >= int(len(pd.read_csv(
            Path("fixtures/tikr_fx_12.csv") if Path("fixtures/tikr_fx_12.csv").exists()
            else Path("research/fx_tikr_reverse/fixtures/tikr_fx_12.csv")
        ))*cfg["acceptance"]["minimum_reference_coverage"])))

# 5 no winner
if Path("outputs/tikr_fx_comparison.json").exists():
    j=json.loads(Path("outputs/tikr_fx_comparison.json").read_text())
    results.append(("no_winner", j.get("winner") is None))
    results.append(("no_proprietary_method_claim", j.get("methodology_conclusion")=="NOT_DETERMINABLE_FROM_ERROR_ALONE"))

# 6 provenance
if prov.exists():
    j=json.loads(prov.read_text())
    results.append(("tikr_primary_source_found", j.get("provenance_status")=="SOURCE_FOUND_CANDIDATE"))

df=pd.DataFrame(results,columns=["requirement","pass"])
df.to_csv("outputs/validation_matrix.csv",index=False)

print(df.to_string(index=False))
print("\nPASS:", int(df["pass"].sum()), "/", len(df))

# Validation itself does NOT certify. It reports whether required evidence exists.
