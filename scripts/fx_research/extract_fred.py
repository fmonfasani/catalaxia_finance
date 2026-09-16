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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SERIES_ID = os.getenv("FRED_SERIES_ID", "DEXARUS")
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
OUT = Path("artifacts/fx_44q/FRED")
CONNECT_TIMEOUT = float(os.getenv("FRED_CONNECT_TIMEOUT", "10"))
READ_TIMEOUT = float(os.getenv("FRED_READ_TIMEOUT", "45"))
MAX_ATTEMPTS = int(os.getenv("FRED_MAX_ATTEMPTS", "4"))
BACKOFF_FACTOR = float(os.getenv("FRED_BACKOFF_FACTOR", "2"))


def build_session() -> requests.Session:
    retry = Retry(
        total=MAX_ATTEMPTS - 1,
        connect=MAX_ATTEMPTS - 1,
        read=MAX_ATTEMPTS - 1,
        status=MAX_ATTEMPTS - 1,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "Catalaxia-FX-research/1.0"})
    return session


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
        "retry_backoff_factor": BACKOFF_FACTOR,
    }
    try:
        started = time.monotonic()
        response = build_session().get(
            URL,
            params={"id": SERIES_ID},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        diag["elapsed_seconds"] = round(time.monotonic() - started, 3)
        diag["http_status"] = response.status_code
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
        (OUT / "fred_observations.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        diag.update({
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
    diag["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (OUT / "diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(diag, ensure_ascii=False, indent=2))
    return 0 if diag["status"] == "ACQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
