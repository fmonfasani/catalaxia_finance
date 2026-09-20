#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estadísticos por período — REQ-FX-007. Puro, sin red, sin BD (clase A).

Implementa exactamente stats_spec.md §2. Ausencia => None (NULL) + reason;
jamás imputa (REQ-FX-006).
"""
from __future__ import annotations

import statistics
from collections import Counter
from math import isnan
from typing import Sequence

SCRIPT_VERSION = "stats@v1.0.0"
TRIM_PCT = 0.10
MAD_SCALE = 1.4826  # consistencia normal


def _clean(xs: Sequence[float]) -> list[float]:
    out = []
    for x in xs:
        if x is None:
            continue
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if isnan(v):
            continue
        out.append(v)
    return out


def trimmed_mean(xs: Sequence[float], pct: float = TRIM_PCT) -> float | None:
    xs = sorted(_clean(xs))
    n = len(xs)
    if n == 0:
        return None
    k = int(n * pct)
    core = xs[k:n - k] if k else xs
    if not core:
        return None
    return sum(core) / len(core)


def mode_strict(xs: Sequence[float]) -> tuple[float | None, str | None]:
    """Moda exacta. Sin repetición => (None, 'NO_MODE')."""
    xs = _clean(xs)
    if not xs:
        return None, "EMPTY_VECTOR"
    c = Counter(xs)
    val, cnt = c.most_common(1)[0]
    if cnt < 2:
        return None, "NO_MODE"
    return val, None


def describe(xs: Sequence[float]) -> dict:
    """Devuelve {n, mean, median, mode, trimmed_mean, mad, iqr, sd, cv, null_reasons}."""
    v = _clean(xs)
    n = len(v)
    reasons: list[str] = []
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "mode": None,
                "trimmed_mean": None, "mad": None, "iqr": None,
                "sd": None, "cv": None,
                "null_reasons": ["EMPTY_VECTOR"], "stats_version": SCRIPT_VERSION}
    mean = sum(v) / n
    median = statistics.median(v)
    mval, mreason = mode_strict(v)
    if mreason:
        reasons.append(mreason)
    tmean = trimmed_mean(v)
    mad_raw = statistics.median(sorted(abs(x - median) for x in v))
    mad = mad_raw * MAD_SCALE
    qs = statistics.quantiles(v, n=4, method="exclusive") if n >= 4 else []
    iqr = (qs[2] - qs[0]) if len(qs) == 3 else None
    if iqr is None:
        reasons.append("IQR_REQUIRES_N_GE_4")
    sd = statistics.stdev(v) if n >= 2 else None
    if sd is None:
        reasons.append("SD_REQUIRES_N_GE_2")
    cv = (sd / mean) if (sd is not None and mean != 0) else None
    if sd is not None and mean == 0:
        reasons.append("CV_MEAN_ZERO")
    return {"n": n, "mean": mean, "median": median, "mode": mval,
            "trimmed_mean": tmean, "mad": mad, "iqr": iqr,
            "sd": sd, "cv": cv,
            "null_reasons": reasons, "stats_version": SCRIPT_VERSION}


def rel_err(observed: float | None, candidate: float | None) -> float | None:
    if observed is None or candidate in (None, 0):
        return None
    try:
        return (float(observed) - float(candidate)) / float(candidate)
    except (TypeError, ValueError):
        return None
