"""Estadísticos REQ-FX-007 + no-imputación REQ-FX-006."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stats import describe, rel_err, trimmed_mean  # noqa: E402


def test_known_vector():
    d = describe([100.0, 102.0, 101.0, 103.0, 102.0])
    assert d["n"] == 5
    assert abs(d["mean"] - 101.6) < 1e-9
    assert d["median"] == 102.0
    assert d["mode"] == 102.0
    assert d["iqr"] is not None and d["sd"] is not None
    assert d["cv"] is not None


def test_empty_vector_returns_nulls_not_zeros():
    d = describe([])
    assert d["n"] == 0
    for k in ("mean", "median", "mode", "trimmed_mean", "mad", "iqr", "sd", "cv"):
        assert d[k] is None, k
    assert "EMPTY_VECTOR" in d["null_reasons"]


def test_single_value_sd_null():
    d = describe([808.46])
    assert d["n"] == 1
    assert d["sd"] is None and "SD_REQUIRES_N_GE_2" in d["null_reasons"]
    assert d["median"] == 808.46


def test_mode_without_repetition_is_null():
    d = describe([1.0, 2.0, 3.0])
    assert d["mode"] is None and "NO_MODE" in d["null_reasons"]


def test_no_imputation_none_and_nan_skipped():
    d = describe([100.0, None, float("nan"), 100.0])
    assert d["n"] == 2
    assert d["mean"] == 100.0


def test_trimmed_mean_10pct():
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100.0]
    assert abs(trimmed_mean(xs) - 5.5) < 1e-9


def test_rel_err_null_safe():
    assert rel_err(None, 100) is None
    assert rel_err(100, 0) is None
    assert rel_err(101, 100) == 0.01
