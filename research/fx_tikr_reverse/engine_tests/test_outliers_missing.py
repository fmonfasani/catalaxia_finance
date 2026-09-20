"""Ejes 8-9: outliers + missing data. Puro."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))
from stats_ext import describe_ext  # noqa: E402
from reconstruct import reconstruct_day  # noqa: E402


def test_mediana_robusta_a_outlier():
    d = describe_ext([100.0, 101.0, 102.0, 1000.0])
    assert d["median"] == 101.5
    assert d["mean"] > 300  # la media sí se contamina; por eso el primario usa median
    assert d["p90"] is not None and d["p10"] is not None
    assert d["p10"] <= d["p25"] <= d["median"] <= d["p75"] <= d["p90"]


def test_percentiles_vector_unitario_y_vacio():
    d1 = describe_ext([808.46])
    assert d1["n"] == 1 and d1["p10"] == d1["p90"] == 808.46
    assert d1["sd"] is None  # REQ-FX-007: N<2 -> NULL, no invento
    d0 = describe_ext([])
    assert d0["n"] == 0
    for k in ("mean", "median", "mode", "mad", "iqr", "sd", "cv",
              "p10", "p25", "p75", "p90"):
        assert d0[k] is None, k


def test_missing_data_jamas_imputa():
    out = reconstruct_day("2024-12-30", [], "CCL")
    assert out["fx_value"] is None and out["null_reason"] == "NO_PAIRS"
    d = describe_ext([None, float("nan")])
    assert d["n"] == 0 and d["median"] is None
