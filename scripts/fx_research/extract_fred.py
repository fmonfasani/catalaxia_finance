"""Acquire a FRED series as raw observations; no FX equivalence is asserted."""
from __future__ import annotations
import csv, io, json, os
from datetime import datetime, timezone
from pathlib import Path
import requests

SERIES_ID = os.getenv("FRED_SERIES_ID", "DEXARUS")
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
OUT = Path("artifacts/fx_44q/FRED")

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    diag = {"source":"FRED", "series_id":SERIES_ID, "status":"STARTED", "checked_at_utc":datetime.now(timezone.utc).isoformat(), "claim":"RAW_SERIES_ONLY; FX definition/equivalence not certified"}
    try:
        r = requests.get(URL, params={"id": SERIES_ID}, timeout=45, headers={"User-Agent":"Catalaxia-FX-research/1.0"})
        diag["http_status"] = r.status_code
        r.raise_for_status()
        text = r.text
        (OUT / "fred_raw.csv").write_text(text, encoding="utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        diag.update({"status":"ACQUIRED" if rows else "EMPTY_RESPONSE", "columns":reader.fieldnames, "row_count":len(rows), "first_row":rows[0] if rows else None, "last_row":rows[-1] if rows else None, "raw_file":"fred_raw.csv"})
        # Preserve observations without aggregation or interpretation.
        (OUT / "fred_observations.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception as e:
        diag.update({"status":"FAILED", "error_type":type(e).__name__, "error":str(e)})
    (OUT / "diagnostics.json").write_text(json.dumps(diag, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(diag, indent=2))
    return 0 if diag["status"] == "ACQUIRED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
