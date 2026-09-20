#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Outputs §18 + manifiesto + capas. Reutiliza CSVs (no duplica datos fuente).
Genera: sovereign_debt_master.{xlsx,parquet} (+csv ya existe),
evidence_matrix.xlsx, cross_market_cases.xlsx, fx_observations.xlsx,
research_manifest.json (SHA256 de cada artefacto + comando + git).
Uso: python sovereign_matrix/scripts/make_outputs.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import assert_in_sandbox, git_commit, utcnow_iso  # noqa: E402

SM = ROOT / "sovereign_matrix"
EDT = ROOT / "edgar_sovereign" / "tables"
V = "make_outputs@v1.0.0"

LAYERS = ["01_DISCOVERY", "02_IDENTITY", "03_RAW", "04_PARSED", "05_NORMALIZED",
          "06_ECONOMIC_FACTS", "07_FINANCIAL_MODEL", "09_PROVENANCE",
          "10_VALIDATION", "11_CERTIFICATION"]
STORE = {  # capa -> artefactos reales (reuse, sin duplicar)
    "01_DISCOVERY": ["../edgar_sovereign/raw/fts/*.json (40+41 ventanas FTS)"],
    "02_IDENTITY": ["02_IDENTITY/instrument_master.csv (26)", "02_IDENTITY/equivalences.csv"],
    "03_RAW": ["../edgar_sovereign/raw/filings/*.htm (16 docs)", "../raw/bcra/* (BCRA)"],
    "04_PARSED": ["../edgar_sovereign/parsed/evidence.jsonl (555 ventanas)"],
    "05_NORMALIZED": ["sovereign_debt_master.csv (9)", "../edgar_sovereign/tables/TABLA*.csv"],
    "06_ECONOMIC_FACTS": ["fx_observations.csv (3)", "../edgar_sovereign/tables/TABLA5_explicit_fx.csv"],
    "07_FINANCIAL_MODEL": ["fx_observations.csv", "cross_market_cases.csv (3)"],
    "09_PROVENANCE": ["provenance_matrix.csv (14)", "09_PROVENANCE/cross_validation.csv",
                      "09_PROVENANCE/internal_artifacts.csv"],
    "10_VALIDATION": ["10_VALIDATION/test_sovereign_matrix.py (19 ejes)"],
    "11_CERTIFICATION": ["11_CERTIFICATION/certification_report.md"],
}


def main():
    import pandas as pd
    for layer in LAYERS:
        d = SM / layer
        d.mkdir(parents=True, exist_ok=True)
        (d / "LAYER_MANIFEST.md").write_text(
            "# Capa %s\n\nPrimaria: %s\n\nArtefactos (reuse, no duplicados):\n%s\n" % (
                layer.split("_")[0], layer.split("_", 1)[1],
                "\n".join(f"- `{a}`" for a in STORE[layer])), encoding="utf-8")
    master = pd.read_csv(SM / "sovereign_debt_master.csv")
    master.to_excel(SM / "sovereign_debt_master.xlsx", index=False)
    master.to_parquet(SM / "sovereign_debt_master.parquet", index=False)
    ev = pd.read_csv(EDT / "TABLA2_price_value_evidence.csv")
    ev.to_excel(SM / "evidence_matrix.xlsx", index=False)
    pd.read_csv(SM / "cross_market_cases.csv").to_excel(SM / "cross_market_cases.xlsx", index=False)
    pd.read_csv(SM / "fx_observations.csv").to_excel(SM / "fx_observations.xlsx", index=False)
    manifest = {"generated_at": utcnow_iso(), "git_commit": git_commit(),
                "generator": V, "branch": "feature/fx-research-engine", "artifacts": []}
    for p in sorted(SM.rglob("*")):
        if p.is_file() and p.suffix not in (".pyc",) and "__pycache__" not in str(p):
            rel = str(p.relative_to(ROOT))
            manifest["artifacts"].append(
                {"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                 "bytes": p.stat().st_size})
    (SM / "research_manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"[{V}] artefactos={len(manifest['artifacts'])} xlsx+parquet ok")


if __name__ == "__main__":
    main()
