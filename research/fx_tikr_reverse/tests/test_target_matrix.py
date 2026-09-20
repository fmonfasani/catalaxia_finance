"""Matriz objetivo — REQ-FX-001. Clase A, sin red."""
import csv
from pathlib import Path

DEFINIR = Path(__file__).resolve().parents[1] / "00_DEFINIR" / "target_dates.csv"
POC_EXPECTED = ["2023-Q3", "2023-Q4", "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
                "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]
Q_END = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}


def _load():
    # 00_DEFINIR/target_dates.csv lleva cabecera documental `#`; se filtra.
    # El artefacto canónico regenerable está en outputs/target_dates.csv.
    with DEFINIR.open(encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def test_matrix_exists_with_26_rows():
    rows = _load()
    assert len(rows) == 26, f"esperado 26 filas 2020-Q1..2026-Q2, hay {len(rows)}"


def test_poc_coverage_exact():
    rows = _load()
    poc = sorted(r["period_id"] for r in rows if r["priority"] == "POC")
    assert poc == sorted(POC_EXPECTED)


def test_quarter_ends_match_calendar():
    for r in _load():
        mmdd = r["target_date"][5:]
        assert mmdd == Q_END[r["quarter"]], r
        assert r["observation_rule_version"] == "OBS-V1"


def test_no_duplicate_periods():
    rows = _load()
    ids = [r["period_id"] for r in rows]
    assert len(ids) == len(set(ids))
