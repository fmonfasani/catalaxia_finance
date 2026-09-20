"""Ejes 10-11: reproducibilidad + provenance. Sin red (re-ejecuta pasos clase A)."""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"


def _run(mod: str):
    return subprocess.run([sys.executable, str(ENGINE / mod)], capture_output=True,
                          text=True, cwd=str(ROOT))


def test_pipeline_clase_a_determinista():
    uni = ROOT / "parsed" / "universe.csv"
    pq = ROOT / "normalized" / "fx_reference.parquet"
    h_uni = hashlib.sha256(uni.read_bytes()).hexdigest()
    h_pq = hashlib.sha256(pq.read_bytes()).hexdigest()
    assert _run("universe.py").returncode == 0
    assert _run("normalize.py").returncode == 0
    assert hashlib.sha256(uni.read_bytes()).hexdigest() == h_uni
    assert hashlib.sha256(pq.read_bytes()).hexdigest() == h_pq


def test_provenance_completa_raw_y_normalized():
    a3500 = sorted((ROOT / "raw" / "bcra" / "a3500").glob("*.json"))
    assert a3500, "sin RAW A3500"
    for p in a3500[:3]:
        m = json.loads(p.read_text(encoding="utf-8"))["meta"]
        assert m["source_url"].startswith("https://api.bcra.gob.ar/")
        assert m["retrieved_at"] and m["source_date"] == p.stem and m["sha256"]
    ref = pd.read_parquet(ROOT / "normalized" / "fx_reference.parquet")
    assert ref["provenance_id"].notna().all() and (ref["provenance_id"] != "").all()
    assert set(ref["fx_type"]) == {"A3500", "OFICIAL"}
    assert ref["fx_value"].notna().all()  # 26/26 OK en ambas series (ver RUN_REPORT)


def test_fixture_tikr_intacto_y_byma_status():
    with open(ROOT / "fixtures" / "tikr_fx_12.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 12
    assert rows[0] == {"period": "2023-Q3", "target_date": "2023-09-30",
                       "tikr_fx": "349.97", "fixture_version": "tikr_fixture@v1.0.0",
                       "provenance": "encargo-AGENTE02-P8 (fixture externo, no medido aquí)"}
    for prod in ("mep", "ccl", "dollar_index", "ccl_index"):
        st = json.loads((ROOT / "raw" / "byma" / f"{prod}.status.json").read_text(encoding="utf-8"))
        assert st["status"] in ("AUTH_REQUIRED", "NOT_AVAILABLE"), prod
