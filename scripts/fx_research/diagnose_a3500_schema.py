#!/usr/bin/env python3
"""Capture a bounded, non-transforming A3500 API response for schema inspection.

Layer: 1 FUENTES. Diagnostic only; does not map FX definitions or compare TIKR.
Acceptance: write a timestamped JSON artifact containing HTTP metadata and
response structure/sample (bounded), even on request/HTTP/JSON failure.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "fx_44q" / "A3500_DIAGNOSTIC"
DATE = os.getenv("A3500_DIAGNOSTIC_DATE", "2025-06-30")
URL = f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones?fecha={DATE}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "source": "BCRA API (A3500 investigation)",
        "requested_date": DATE,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "raw schema diagnostic only; no FX mapping, equivalence, or certification",
        "url": URL,
    }
    try:
        response = requests.get(URL, timeout=(10, 35))
        result["http_status"] = response.status_code
        result["content_type"] = response.headers.get("Content-Type")
        result["response_bytes"] = len(response.content)
        result["body_excerpt"] = response.text[:2000]
        try:
            payload = response.json()
            result["root_type"] = type(payload).__name__
            if isinstance(payload, dict):
                result["root_keys"] = sorted(map(str, payload.keys()))
                nested = payload.get("results")
                result["results_type"] = type(nested).__name__
                if isinstance(nested, dict):
                    result["results_keys"] = sorted(map(str, nested.keys()))
                    rows = nested.get("detalle")
                    result["detalle_type"] = type(rows).__name__
                    if isinstance(rows, list):
                        result["detalle_count"] = len(rows)
                        result["detalle_sample"] = rows[:5]
                elif isinstance(nested, list):
                    result["results_count"] = len(nested)
                    result["results_sample"] = nested[:5]
            elif isinstance(payload, list):
                result["root_count"] = len(payload)
                result["root_sample"] = payload[:5]
            result["json_parse"] = "OK"
        except ValueError as exc:
            result["json_parse"] = "FAILED"
            result["json_error"] = str(exc)
        result["status"] = "CAPTURED" if response.ok else "HTTP_ERROR_CAPTURED"
        exit_code = 0 if response.ok else 1
    except requests.RequestException as exc:
        result.update(status="REQUEST_FAILED", error_type=type(exc).__name__, error=str(exc))
        exit_code = 1
    path = OUT / "a3500_schema_sample.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
