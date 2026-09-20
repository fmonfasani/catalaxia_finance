#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixture TIKR 12 FX — PRIORIDAD 8. Materializa los valores dados, sin inferir nada.

Los 12 FX "ya inferidos" provistos en el encargo se tratan como FIXTURE de
entrada para agentes posteriores (comparación), NO como evidencia ni como
conclusión de este agente. Este script sólo los escribe a fixtures/tikr_fx_12.csv
con provenance del encargo. AGENTE 02 NO emite conclusión sobre qué FX usa TIKR.

Uso:
  python engine/tikr_fixture.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import assert_in_sandbox  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "fixtures" / "tikr_fx_12.csv"
FIXTURE_VERSION = "tikr_fixture@v1.0.0"

# Valores VERBATIM del encargo P8 (fixture, no medición de este agente).
ROWS = [
    ("2023-Q3", "2023-09-30", "349.97"),
    ("2023-Q4", "2023-12-31", "808.46"),
    ("2024-Q1", "2024-03-31", "857.22"),
    ("2024-Q2", "2024-06-30", "911.50"),
    ("2024-Q3", "2024-09-30", "968.50"),
    ("2024-Q4", "2024-12-31", "1030.50"),
    ("2025-Q1", "2025-03-31", "1073.10"),
    ("2025-Q2", "2025-06-30", "1204.50"),
    ("2025-Q3", "2025-09-30", "1379.70"),
    ("2025-Q4", "2025-12-31", "1451.00"),
    ("2026-Q1", "2026-03-31", "1382.00"),
    ("2026-Q2", "2026-06-30", "1483.70"),
]


def main() -> None:
    assert_in_sandbox(OUT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["period", "target_date", "tikr_fx",
                                          "fixture_version", "provenance"])
        w.writeheader()
        for period, tgt, fx in ROWS:
            w.writerow({"period": period, "target_date": tgt, "tikr_fx": fx,
                        "fixture_version": FIXTURE_VERSION,
                        "provenance": "encargo-AGENTE02-P8 (fixture externo, no medido aquí)"})
    print(f"[{FIXTURE_VERSION}] filas={len(ROWS)} -> fixtures/tikr_fx_12.csv")


if __name__ == "__main__":
    main()
