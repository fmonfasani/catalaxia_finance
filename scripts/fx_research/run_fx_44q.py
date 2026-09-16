#!/usr/bin/env python3
"""FX 44Q research runner.

Layer: 1 FUENTES. Acquisition/orchestration only.
It does not certify the TIKR method.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "fx_44q"
TIKR_CANDIDATES = [ROOT / "research" / "fx_tikr_reverse" / "tikr_fx_fixture_44q.csv", ROOT / "data" / "TIKR_FX_FIXTURE_44Q.csv", ROOT / "TIKR_FX_FIXTURE_44Q.csv"]
URL = "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones?fecha={date}"


def get_json(url, **kwargs):
    response = requests.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def find_fixture():
    for path in TIKR_CANDIDATES:
        if path.exists():
            return path
    return None


def load_tikr(path):
    df = pd.read_csv(path)
    required = {"period", "tikr_fx"}
    if not required.issubset(df.columns):
        raise ValueError(f"Fixture must contain {sorted(required)}")
    df = df[["period", "tikr_fx"]].copy()
    df["period"] = df["period"].astype(str)
    df["tikr_fx"] = pd.to_numeric(df["tikr_fx"], errors="coerce")
    if df["period"].duplicated().any():
        raise ValueError("Fixture contains duplicate period keys")
    return df


def quarter_targets(periods):
    q = pd.PeriodIndex(periods, freq="Q")
    return pd.DataFrame({"period": [str(p) for p in periods], "target_date": q.to_timestamp(how="end").date.astype(str)})


def _rows_from_payload(payload):
    """Extract common documented/container shapes without silently hiding unknown schemas."""
    if isinstance(payload, list):
        return payload, "root:list"
    if not isinstance(payload, dict):
        return [], f"unsupported_root:{type(payload).__name__}"
    for key in ("results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value, f"root.{key}"
        if isinstance(value, dict):
            for nested in ("results", "data", "detalle", "cotizaciones"):
                if isinstance(value.get(nested), list):
                    return value[nested], f"root.{key}.{nested}"
    return [], "no_recognized_rows;root_keys=" + ",".join(sorted(map(str, payload.keys())))


def _usd_value(row):
    if not isinstance(row, dict):
        return None, "row_not_object"
    currency = str(row.get("codigoMoneda", row.get("moneda", ""))).strip().upper()
    if currency not in {"USD", "DOLAR", "DÓLAR"}:
        return None, f"currency_not_usd:{currency or 'missing'}"
    for key in ("tipoCambio", "valor", "venta", "cotizacion"):
        raw = row.get(key)
        if raw is not None:
            try:
                return float(str(raw).replace(",", ".")), f"value_field:{key}"
            except (TypeError, ValueError):
                return None, f"invalid_numeric_value:{key}"
    return None, "usd_row_without_supported_value_field"


def a3500(period):
    quarter_end = period.to_timestamp(how="end").date()
    attempts = []
    for offset in range(7):
        date = (quarter_end - pd.Timedelta(days=offset)).isoformat()
        url = URL.format(date=date)
        try:
            response = requests.get(url, timeout=30)
            status = response.status_code
            if not response.ok:
                attempts.append({"date": date, "http_status": status, "reason": "http_error", "body_excerpt": response.text[:500]})
                continue
            try:
                payload = response.json()
            except ValueError:
                attempts.append({"date": date, "http_status": status, "reason": "invalid_json", "body_excerpt": response.text[:500]})
                continue
            rows, shape = _rows_from_payload(payload)
            for row in rows:
                value, reason = _usd_value(row)
                if value is not None:
                    return value, date, {"http_status": status, "payload_shape": shape, "row_count": len(rows), "selection": reason, "attempts": attempts}
            attempts.append({"date": date, "http_status": status, "reason": "no_matching_usd_value", "payload_shape": shape, "row_count": len(rows), "root_keys": sorted(payload.keys()) if isinstance(payload, dict) else None})
        except requests.RequestException as exc:
            attempts.append({"date": date, "reason": "request_exception", "error": str(exc)})
    return None, None, {"attempts": attempts, "failure": "no_a3500_value_found_in_7_day_window"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=None)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = Path(args.fixture) if args.fixture else find_fixture()
    if fixture is None:
        raise SystemExit("NO_DETERMINABLE: TIKR 44Q fixture not found in repository")
    tikr = load_tikr(fixture)
    if len(tikr) != 44:
        raise SystemExit(f"BLOCKER: expected 44 TIKR quarters, found {len(tikr)}")
    targets = quarter_targets(tikr.period)
    a_rows, diagnostics = [], []
    for _, target in targets.iterrows():
        period = pd.Period(target.period, freq="Q")
        value, effective, diagnostic = a3500(period)
        a_rows.append({"period": target.period, "target_date": target.target_date, "effective_date": effective, "a3500": value})
        diagnostics.append({"period": target.period, **diagnostic})
    a = pd.DataFrame(a_rows)
    out = tikr.merge(a, on="period", how="left", validate="one_to_one")
    valid_pair = out["tikr_fx"].notna() & out["a3500"].notna()
    out["error_ars"] = (out.tikr_fx - out.a3500).where(valid_pair)
    out["error_pct"] = (out.error_ars / out.a3500 * 100).where(valid_pair)
    out.to_csv(OUT / "tikr_vs_a3500_44q.csv", index=False)
    pd.DataFrame(diagnostics).to_json(OUT / "a3500_acquisition_diagnostics.json", orient="records", indent=2)
    valid_count = int(valid_pair.sum())
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(), "fixture": str(fixture),
        "quarters": len(out), "tikr_values_present": int(out.tikr_fx.notna().sum()),
        "a3500_coverage": int(out.a3500.notna().sum()), "valid_comparison_pairs": valid_count,
        "mae_ars": float(out.loc[valid_pair, "error_ars"].abs().mean()) if valid_count else None,
        "max_abs_pct": float(out.loc[valid_pair, "error_pct"].abs().max()) if valid_count else None,
        "status": "COMPARISON_AVAILABLE" if valid_count else "NO_VALID_COMPARISON_PAIRS",
        "certification_claim": "NONE"
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not out.a3500.notna().any():
        raise SystemExit("ACQUISITION_FAILED: zero A3500 coverage; inspect a3500_acquisition_diagnostics.json")

if __name__ == "__main__":
    main()
