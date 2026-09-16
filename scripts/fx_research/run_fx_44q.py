#!/usr/bin/env python3
"""FX 44Q research runner.

Layer: 1 FUENTES. Acquisition/orchestration only.
It does not certify the TIKR method.
"""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "fx_44q"
TIKR_CANDIDATES = [ROOT / "research" / "fx_tikr_reverse" / "tikr_fx_fixture_44q.csv", ROOT / "data" / "TIKR_FX_FIXTURE_44Q.csv", ROOT / "TIKR_FX_FIXTURE_44Q.csv"]
URL = "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones?fecha={date}"


def get_json(url, **kwargs):
    r = requests.get(url, timeout=30, **kwargs); r.raise_for_status(); return r.json()


def find_fixture():
    for p in TIKR_CANDIDATES:
        if p.exists(): return p
    return None


def load_tikr(path):
    df = pd.read_csv(path)
    required = {"period", "tikr_fx"}
    if not required.issubset(df.columns): raise ValueError(f"Fixture must contain {sorted(required)}")
    return df[["period", "tikr_fx"]].copy()


def quarter_targets(periods):
    q = pd.PeriodIndex(periods, freq="Q")
    return pd.DataFrame({"period": periods, "target_date": q.to_timestamp(how="end").date.astype(str)})


def a3500(period):
    d = period.to_timestamp(how="end")
    for i in range(7):
        date = (d - pd.Timedelta(days=i)).date().isoformat()
        data = get_json(URL.format(date=date))
        rows = data.get("results", data.get("data", []))
        if isinstance(rows, dict): rows = rows.get("results", rows.get("data", []))
        if rows:
            for row in rows:
                if str(row.get("codigoMoneda", row.get("moneda", ""))).upper() in {"USD","DOLAR"}:
                    for k in ("tipoCambio", "valor", "venta", "cotizacion"):
                        if row.get(k) is not None:
                            return float(str(row[k]).replace(",", ".")), date
    return None, None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fixture", default=None); args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = Path(args.fixture) if args.fixture else find_fixture()
    if fixture is None: raise SystemExit("NO_DETERMINABLE: TIKR 44Q fixture not found in repository")
    tikr = load_tikr(fixture)
    if len(tikr) != 44: raise SystemExit(f"BLOCKER: expected 44 TIKR quarters, found {len(tikr)}")
    targets = quarter_targets(tikr.period)
    a_rows=[]
    for _, r in targets.iterrows():
        p=pd.Period(r.period, freq="Q"); value, effective=a3500(p)
        a_rows.append({"period":r.period,"target_date":r.target_date,"effective_date":effective,"a3500":value})
    a=pd.DataFrame(a_rows); out=tikr.merge(a,on=["period"],how="left")
    out["error_ars"] = out.tikr_fx-out.a3500
    out["error_pct"] = out.error_ars/out.a3500*100
    out.to_csv(OUT/"tikr_vs_a3500_44q.csv",index=False)
    summary={"run_at":datetime.now(timezone.utc).isoformat(),"fixture":str(fixture),"quarters":len(out),"a3500_coverage":int(out.a3500.notna().sum()),"mae_ars":float(out.error_ars.abs().mean()) if out.a3500.notna().any() else None,"max_abs_pct":float(out.error_pct.abs().max()) if out.a3500.notna().any() else None}
    (OUT/"run_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__ == "__main__": main()
