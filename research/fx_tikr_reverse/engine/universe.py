#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Universo trimestral — PRIORIDAD 5. Puro salvo lectura de RAW local (clase A).

Entradas: 00_DEFINIR/target_dates.csv + raw/bcra/a3500/*.json + parsed/bcra_oficial.csv.
Regla OBS-V1 (congelada, no redefinida aquí): última publicación con
observation_date <= target_date y lag <= 5 días calendario; si no existe ->
NULL + NO_PUBLICATION_IN_WINDOW. Prohibido forward-fill e interpolación.

Salida: universe.csv con target_date Y effective_market_date lado a lado:
  period | target_date | eff_a3500 | lag_a3500 | status_a3500 |
  eff_oficial | lag_oficial | status_oficial
No se reemplaza silenciosamente: target_date se conserva siempre.

Uso:
  python engine/universe.py
"""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import assert_in_sandbox  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TARGETS = ROOT / "00_DEFINIR" / "target_dates.csv"
RAW_A3500 = ROOT / "raw" / "bcra" / "a3500"
PARSED_OFICIAL = ROOT / "parsed" / "bcra_oficial.csv"
OUT = ROOT / "parsed" / "universe.csv"
UNIVERSE_VERSION = "universe@v1.0.0"
WINDOW = 5


def load_targets() -> list[dict]:
    with open(TARGETS, encoding="utf-8") as f:
        return [r for r in csv.DictReader(
            l for l in f if not l.lstrip().startswith("#") and l.strip())]


def load_a3500() -> dict[str, float]:
    """source_date -> usd (sólo valores > 0)."""
    out: dict[str, float] = {}
    if not RAW_A3500.exists():
        return out
    for p in RAW_A3500.glob("*.json"):
        try:
            env = json.loads(p.read_text(encoding="utf-8"))
            v = (env.get("parsed_hint") or {}).get("usd_tipoCotizacion")
            sd = (env.get("meta") or {}).get("source_date", p.stem)
            if v and float(v) > 0:
                out[sd] = float(v)
        except (ValueError, KeyError, OSError):
            continue
    return out


def load_oficial() -> dict[str, float]:
    out: dict[str, float] = {}
    if not PARSED_OFICIAL.exists():
        return out
    with open(PARSED_OFICIAL, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                v = float(r["venta"])
                if v > 0:
                    out[r["source_date"]] = v
            except (ValueError, TypeError, KeyError):
                continue
    return out


def resolve(target: date, series: dict[str, float]) -> tuple[str | None, int | None, str]:
    for lag in range(WINDOW + 1):
        cand = (target - timedelta(days=lag)).isoformat()
        if cand in series:
            return cand, lag, "OK"
    return None, None, "NO_PUBLICATION_IN_WINDOW"


def main() -> None:
    assert_in_sandbox(OUT)
    targets = load_targets()
    a3500 = load_a3500()
    oficial = load_oficial()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "period", "target_date", "eff_a3500", "lag_a3500", "status_a3500",
            "eff_oficial", "lag_oficial", "status_oficial", "universe_version"])
        w.writeheader()
        for t in targets:
            tgt = date.fromisoformat(t["target_date"])
            ea, la, sa = resolve(tgt, a3500)
            eo, lo, so = resolve(tgt, oficial)
            w.writerow({"period": t["period_id"], "target_date": t["target_date"],
                        "eff_a3500": ea or "", "lag_a3500": la if la is not None else "",
                        "status_a3500": sa, "eff_oficial": eo or "",
                        "lag_oficial": lo if lo is not None else "",
                        "status_oficial": so, "universe_version": UNIVERSE_VERSION})
    n_ok = sum(1 for _ in open(OUT, encoding="utf-8")) - 1
    print(f"[{UNIVERSE_VERSION}] periodos={n_ok} a3500_dias={len(a3500)} "
          f"oficial_dias={len(oficial)} -> parsed/universe.csv")


if __name__ == "__main__":
    main()
