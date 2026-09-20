#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estadística extendida — PRIORIDAD 7. Extiende scripts/stats.py SIN modificarlo.

stats_spec.md (congelado, REQ-FX-007) exige: N, mean, median, mode, trimmed_mean,
MAD, IQR, std, CV. PRIORIDAD 7 agrega: P10, P25, P75, P90 (percentiles lineales).
Este módulo reutiliza describe() y añade los percentiles; los NULL siguen siendo
None + null_reason (REQ-FX-006). Si N==0 -> percentiles None + EMPTY_VECTOR.

Uso como librería (no CLI):
  from stats_ext import describe_ext
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stats import describe  # noqa: E402 (módulo congelado: sólo lectura)

STATS_EXT_VERSION = "stats_ext@v1.0.0"


def _quantile(sorted_v: list[float], p: float) -> float | None:
    """Percentil lineal (método 'exclusive' compatible con statistics.quantiles)."""
    n = len(sorted_v)
    if n == 0:
        return None
    if n == 1:
        return sorted_v[0]
    # interpolación lineal sobre posiciones (n+1)*p, estilo exclusive
    pos = (n + 1) * p
    if pos <= 1:
        return sorted_v[0]
    if pos >= n:
        return sorted_v[-1]
    k = int(pos) - 1
    d = pos - int(pos)
    return sorted_v[k] + d * (sorted_v[k + 1] - sorted_v[k])


def describe_ext(xs) -> dict:
    """describe() + p10/p25/p75/p90. Claves nuevas; las congeladas intactas."""
    base = describe(xs)
    v = sorted(x for x in (float(x) for x in (xs or []) if x is not None)
               if x == x)  # filtra None/NaN ya limpiados por describe
    # reconstruir vector limpio igual que stats._clean para percentiles exactos
    from stats import _clean
    v = sorted(_clean(xs))
    if not v:
        base.update({"p10": None, "p25": None, "p75": None, "p90": None})
        if "EMPTY_VECTOR" not in base["null_reasons"]:
            base["null_reasons"] = base["null_reasons"] + ["EMPTY_VECTOR"]
    else:
        base.update({"p10": _quantile(v, 0.10), "p25": _quantile(v, 0.25),
                     "p75": _quantile(v, 0.75), "p90": _quantile(v, 0.90)})
    base["stats_ext_version"] = STATS_EXT_VERSION
    return base
