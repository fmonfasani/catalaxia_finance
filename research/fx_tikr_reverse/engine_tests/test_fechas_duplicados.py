"""Ejes 3-4: fechas + duplicados. Sin red."""
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _targets():
    with open(ROOT / "00_DEFINIR" / "target_dates.csv", encoding="utf-8") as f:
        return [r for r in csv.DictReader(
            l for l in f if not l.lstrip().startswith("#") and l.strip())]


def test_universe_no_forward_fill_y_lag_acotado():
    with open(ROOT / "parsed" / "universe.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 26
    for r in rows:
        tgt = date.fromisoformat(r["target_date"])
        for prefix in ("a3500", "oficial"):
            eff, lag, st = r[f"eff_{prefix}"], r[f"lag_{prefix}"], r[f"status_{prefix}"]
            if st == "OK":
                assert eff and date.fromisoformat(eff) <= tgt, r  # jamás futuro
                assert int(lag) <= 5, r
            else:
                assert st == "NO_PUBLICATION_IN_WINDOW" and not eff, r


def test_universe_cubre_targets_congelados():
    want = [r["target_date"] for r in _targets()]
    with open(ROOT / "parsed" / "universe.csv", encoding="utf-8") as f:
        got = [r["target_date"] for r in csv.DictReader(f)]
    assert got == want


def test_sin_duplicados_en_capas():
    with open(ROOT / "parsed" / "bcra_oficial.csv", encoding="utf-8") as f:
        ds = [r["source_date"] for r in csv.DictReader(f)]
    assert len(ds) == len(set(ds)) and len(ds) > 3000
    import pandas as pd
    uni = pd.read_csv(ROOT / "parsed" / "universe.csv", dtype=str)
    assert uni["period"].is_unique
    ref = pd.read_parquet(ROOT / "normalized" / "fx_reference.parquet")
    assert len(ref) == 52  # 26 períodos × 2 tipos
    assert ref[["period", "fx_type"]].drop_duplicates().shape[0] == 52
