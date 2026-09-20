"""
02_build_quarterly_panel.py

Construye el panel trimestral desde CSV/XLSX disponibles bajo raw/parsed/normalized.
No inventa ni rellena datos.
Espera columnas semánticas equivalentes a:
date, source, fx/value o ars_price/usd_price, instrument.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import re

ROOTS = [Path("raw"), Path("parsed"), Path("normalized"), Path("data")]
OUT = Path("normalized")
OUT.mkdir(exist_ok=True)

def find_col(cols, patterns):
    for c in cols:
        s = str(c).lower().strip()
        if any(re.search(p, s) for p in patterns):
            return c
    return None

frames = []
for root in ROOTS:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if p.suffix.lower() not in [".csv", ".xlsx", ".xls"]:
            continue
        try:
            sheets = pd.read_excel(p, sheet_name=None) if p.suffix.lower() in [".xlsx",".xls"] else {"_": pd.read_csv(p)}
        except Exception as e:
            print(f"SKIP {p}: {e}")
            continue

        for sheet, df in sheets.items():
            if df.empty:
                continue
            date_c = find_col(df.columns, [r"^date$", r"fecha", r"datetime", r"effective_date"])
            source_c = find_col(df.columns, [r"source", r"fuente", r"provider"])
            fx_c = find_col(df.columns, [r"^fx$", r"exchange.?rate", r"tipo.?cambio", r"usd.*ars"])
            ars_c = find_col(df.columns, [r"ars.*price", r"price.*ars", r"precio.*ars"])
            usd_c = find_col(df.columns, [r"usd.*price", r"price.*usd", r"precio.*usd"])
            if not date_c:
                continue

            x = df.copy()
            x["date"] = pd.to_datetime(x[date_c], errors="coerce")
            x = x[x["date"].notna()].copy()
            if x.empty:
                continue

            if fx_c:
                x["fx"] = pd.to_numeric(x[fx_c], errors="coerce")
            elif ars_c and usd_c:
                x["fx"] = pd.to_numeric(x[ars_c], errors="coerce") / pd.to_numeric(x[usd_c], errors="coerce")
            else:
                continue

            x["source"] = x[source_c].astype(str) if source_c else p.stem.upper()
            x["instrument"] = x.get("instrument", p.stem)
            x["file"] = str(p)
            x["sheet"] = sheet
            frames.append(x[["date","source","instrument","fx","file","sheet"]])

if not frames:
    raise SystemExit("FAIL: no se encontraron datasets con date + fx o ars_price/usd_price")

panel = pd.concat(frames, ignore_index=True)
panel["fx"] = pd.to_numeric(panel["fx"], errors="coerce")
panel = panel.replace([np.inf, -np.inf], np.nan).dropna(subset=["fx"])
panel = panel[(panel["fx"] > 0) & (panel["fx"] < 1_000_000)]

panel["target_year"] = panel["date"].dt.year
panel["quarter"] = panel["date"].dt.quarter
panel["target_date"] = pd.PeriodIndex(panel["date"], freq="Q").end_time.dt.normalize()
panel["effective_date"] = panel["date"]

panel = panel.sort_values(["date","source","instrument"])
panel.to_csv(OUT / "fx_panel_normalized.csv", index=False)

print(f"PASS: {len(panel):,} observations -> {OUT/'fx_panel_normalized.csv'}")
