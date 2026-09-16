"""Acquire a FRED series as raw observations; no FX equivalence is asserted."""
from __future__ import annotations

import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

SERIES_ID = os.getenv("FRED_SERIES_ID", "DEXARUS")
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
OUT = Path("artifacts/fx_44q/FRED")
CONNECT_TIMEOUT = float(os.getenv("FRED_CONNECT_TIMEOUT", "10"))
READ_TIMEOUT = float(os.getenv("FRED_READ_TIMEOUT", "45"))
MAX_ATTEMPTS = int(os.getenv("FRED_MAX_ATTEMPTS", "4"))
BACKOFF_SECONDS = float(os.getenv("FRED_BACKOFF_SECONDS", "3"))
MAX_BACKOFF_SECONDS = float(os.getenv("FRED_MAX_BACKOFF_SECONDS", "12"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    diag = {
        "source": "FRED",
        "series_id": SERIES_ID,
        "status": "STARTED",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim": "RAW_SERIES_ONLY; FX definition/equivalence not certified",
        "endpoint": URL,
        "connect_timeout_seconds": CONNECT_TIMEOUT,
        "read_timeout_seconds": READ_TIMEOUT,
        "max_attempts": MAX_ATTEMPTS,
        "backoff_seconds": BACKOFF_SECONDS,
        "max_backoff_seconds": MAX_BACKOFF_SECONDS,
        "attempts": [],
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_info = {"attempt": attempt}
        started = time.monotonic()
        try:
            response = requests.get(
                URL,
                params={"id": SERIES_ID},
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                headers={"User-Agent": "Catalaxia-FX-research/1.0"},
            )
            attempt_info["elapsed_seconds"] = round(time.monotonic() - started, 3)
            attempt_info["http_status"] = response.status_code
            response.raise_for_status()
            text = response.text
            (OUT / "fred_raw.csv").write_text(text, encoding="utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            diag.update({
                "status": "ACQUIRED" if rows else "EMPTY_RESPONSE",
                "columns": reader.fieldnames,
                "row_count": len(rows),
                "first_row": rows[0] if rows else None,
                "last_row": rows[-1] if rows else None,
                "raw_file": "fred_raw.csv",
            })
            attempt_info["result"] = diag["status"]
            diag["attempts"].append(attempt_info)
            break
        except Exception as exc:
            attempt_info.update({
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "result": "FAILED",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            diag["attempts"].append(attempt_info)
            if attempt < MAX_ATTEMPTS:
                delay = min(BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
                attempt_info["backoff_before_next_attempt_seconds"] = delay
                time.sleep(delay)
            else:
                diag.update({
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })

    if diag["status"] == "STARTED":
        diag["status"] = "FAILED"
        diag["error_type"] = "UnknownFailure"
        diag["error"] = "Acquisition loop ended without a terminal result"

    if diag["status"] == "ACQUIRED":
        (OUT / "fred_observations.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    diag["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (OUT / "diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(diag, ensure_ascii=False, indent=2))
    return 0 if diag["status"] == "ACQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
