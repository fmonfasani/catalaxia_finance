#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construye la matriz de fechas objetivo quarterly — REQ-FX-001.

Clase A: determinista, sin red, sin BD. Lee la regla OBS-V1 documentada en
00_DEFINIR/target_dates.csv (cabecera) y regenera el CSV bit a bit.

Uso:
    python build_target_matrix.py --out outputs/target_dates.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFINIR = HERE.parent / "00_DEFINIR"

OBS_VERSION = "OBS-V1"
# POC fijado por el encargo (congelado; cambiar = nueva versión de decision_criteria).
POC_IDS = {
    "2023-Q3", "2023-Q4",
    "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
    "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4",
    "2026-Q1", "2026-Q2",
}
Q_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
SCRIPT_VERSION = "build_target_matrix@v1.0.0"


def rows(year_from: int = 2020, year_to: int = 2026, q_to: int = 2):
    out = []
    for y in range(year_from, year_to + 1):
        for q in (1, 2, 3, 4):
            if y == year_to and q > q_to:
                break
            m, d = Q_END[q]
            pid = f"{y}-Q{q}"
            out.append({
                "period_id": pid,
                "year": str(y),
                "quarter": str(q),
                "target_date": f"{y:04d}-{m:02d}-{d:02d}",
                "priority": "POC" if pid in POC_IDS else "EXT",
                "observation_rule_version": OBS_VERSION,
            })
    return out


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=HERE.parent.parent.parent, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-year", type=int, default=2020)
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--to-quarter", type=int, default=2)
    a = ap.parse_args()

    out = Path(a.out)
    # Guardia anti-producción: sólo escribir dentro de research/fx_tikr_reverse/.
    root = (HERE.parent).resolve()
    if root not in out.resolve().parents and out.resolve() != root:
        raise SystemExit(f"REFUSADO: --out fuera del sandbox ({out}); sólo {root}")

    data = rows(a.from_year, a.to_year, a.to_quarter)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "period_id", "year", "quarter", "target_date",
            "priority", "observation_rule_version"])
        w.writeheader()
        w.writerows(data)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"[{SCRIPT_VERSION}] git={git_commit()} rows={len(data)} "
          f"poc={sum(1 for r in data if r['priority']=='POC')} sha256={sha} -> {out}")


if __name__ == "__main__":
    main()
