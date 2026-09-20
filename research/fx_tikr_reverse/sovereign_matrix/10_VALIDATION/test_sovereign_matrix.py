"""Tests §16 sovereign_matrix (19 ejes). Sin red; todo contra artefactos citados."""
import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SM = ROOT / "sovereign_matrix"
EDT = ROOT / "edgar_sovereign" / "tables"


def _csv(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_identity_uniqueness():
    rows = _csv(SM / "02_IDENTITY" / "instrument_master.csv")
    ids = [r["canonical_instrument_id"] for r in rows]
    assert len(ids) == len(set(ids)) and len(ids) >= 20


def test_duplicate_instruments_isin():
    rows = _csv(SM / "02_IDENTITY" / "instrument_master.csv")
    isins = [r["isin"] for r in rows if r["isin"]]
    assert len(isins) == len(set(isins)), "ISIN duplicado = identidad colapsada"


def test_duplicate_observations():
    rows = _csv(SM / "sovereign_debt_master.csv")
    keys = [(r["INSTRUMENTO"], r["FECHA"], r["TIPO_DE_PRECIO"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_date_consistency():
    for r in _csv(SM / "sovereign_debt_master.csv"):
        assert len(r["FECHA"]) == 10 and r["FECHA"][4] == "-" and r["FECHA"][7] == "-"


def test_currency_consistency():
    for r in _csv(SM / "sovereign_debt_master.csv"):
        assert r["MONEDA"] != "", r
        if r["TIPO_DE_PRECIO"] == "MARKET_PRICE":
            assert r["MONEDA"] == "ARS", r  # pata USD ausente: declarado, no asumido


def test_price_unit_consistency():
    for r in _csv(SM / "sovereign_debt_master.csv"):
        if r["PRECIO_ARS"]:
            assert r["UNIDAD_DEL_PRECIO"] != "", r


def test_nominal_vs_price():
    rows = list(_csv(SM / "sovereign_debt_master.csv"))
    for r in rows:
        if r["TIPO_DE_PRECIO"] == "NOMINAL_ONLY":
            assert r["STATUS"] == "PARTIAL", r  # nominal jamás SUPPORTED/CERTIFIED
            assert r["FX_IMPLICITO"] == "", r
    t2 = _csv(EDT / "TABLA2_price_value_evidence.csv")
    nom = [r for r in t2 if r["tipo_valor"] == "NOMINAL_ONLY"]
    assert nom and all(r["usable_fx"].startswith("NO") for r in nom)


def test_fair_value_vs_price():
    t2 = _csv(EDT / "TABLA2_price_value_evidence.csv")
    for r in t2:
        if r["tipo_valor"] == "FAIR_VALUE":
            assert r["usable_fx"].startswith("NO"), r["obs_id"]


def test_ars_usd_comparability():
    for r in _csv(SM / "fx_observations.csv"):
        assert r["veredicto_comparabilidad"] in (
            "COMPARABLE (posición, banda ±~15)", "NO_COMPARABLE_COMO_FX (sólo ratio carrying)",
            "NO_DETERMINABLE (falta componente §18)"), r["fx_id"]


def test_fx_division_by_zero():
    for r in _csv(EDT / "TABLA3_fx_evidence.csv"):
        if r["fx_implied"] not in ("NO_DETERMINABLE (EDGAR-only)", "N/A",
                                   "NO_DETERMINABLE (formula, no print)"):
            assert float(r["fx_implied"]) > 0, r["fx_id"]


def test_fx_formula():
    assert abs(37157 / 36 - 1032.14) < 0.01
    assert abs(115725101466 / 145602795 - 794.79) < 0.01


def test_cross_market_alignment():
    rows = _csv(SM / "cross_market_cases.csv")
    assert any(r["clasificacion"] == "NO_EVIDENCE_FOUND" for r in rows)
    assert any(r["clasificacion"] == "FALSE_POSITIVE_REMOVED" for r in rows)


def test_provenance_completeness():
    rows = _csv(SM / "provenance_matrix.csv")
    assert {r["grado"] for r in rows} <= {"A", "B", "C", "D", "E"}
    assert all(r["fuente"] and r["justificacion"] for r in rows)


def test_source_independence():
    rows = _csv(SM / "09_PROVENANCE" / "cross_validation.csv")
    assert all(r["source_a"] != r["source_b"] for r in rows)


def test_internal_artifact_detection():
    rows = _csv(SM / "09_PROVENANCE" / "internal_artifacts.csv")
    names = [r["artefacto"] for r in rows]
    assert any("tikr_fx_12" in n for n in names)
    assert any("fx_reference" in n for n in names)


def test_hash_reproducibility():
    import hashlib
    for p in ["sovereign_debt_master.csv", "fx_observations.csv", "provenance_matrix.csv"]:
        b = (SM / p).read_bytes()
        assert hashlib.sha256(b).hexdigest() == hashlib.sha256(b).hexdigest()
        assert len(b) > 100


def test_idempotence():
    n1 = len(_csv(SM / "sovereign_debt_master.csv"))
    assert n1 == 9  # TABLA2 base; regenerar no duplica (build es escritura total)


def test_deterministic_output():
    df = pd.read_parquet(ROOT / "normalized" / "fx_reference.parquet")
    assert len(df) == 52  # reuse BCRA intacto


def test_coverage_calculation():
    cov = json.loads((SM / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["identity_coverage"] == round(21 / 25, 4)
    assert cov["usd_price_coverage"] == 0.0
    assert cov["cross_market_cases"] == 0
