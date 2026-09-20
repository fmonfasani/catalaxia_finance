#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstrucción FX_MEP / FX_CCL — PRIORIDAD 4. Funciones puras (clase A).

Fórmulas (congeladas en 00_DEFINIR/instrumental_spec.md):
  FX_MEP = ARS_PRICE / USD_LOCAL_PRICE   (ej. AL30 / AL30D, mismo settlement)
  FX_CCL = ARS_PRICE / USD_CABLE_PRICE   (ej. AL30 / AL30C) o ADR:
           CCL(adr) = P_ARS(local) × ratio / P_USD(adr)

Controles obligatorios (cada violación -> fx_value=None + null_reason;
jamás excepción silenciosa ni imputación):
  nominalidad  : ambas patas > 0 y en moneda esperada (ARS vs USD/USD_CABLE)
  ratio        : ADR exige ratio conocido (10/1/25); bono exige ratio=1
  settlement   : ambas patas con MISMO settlement declarado; UNDECLARED o
                 mismatch -> NO_DECIDE (flag, no voto primario)
  currency     : pata ARS currency=ARS; pata USD currency∈{USD,USD_CABLE} según tipo
  fecha        : ambas patas MISMO date (tolerancia 0); si no -> MISMATCHED_LEGS
  liquidez     : volume_min configurable; volume < mínimo -> LOW_LIQUIDITY (flag)
  precio cero  : price<=0 o None -> ZERO_OR_NEGATIVE_PRICE / MISSING_PRICE
  precio falt. : pata ausente -> MISSING_LEG
  stale price  : retrieved_at/quote_date difieren > max_stale_days -> STALE_PRICE

Agregación: mediana de instrumentos válidos del día (robusta); N = nº de
instrumentos con fx válido. Se conservan los parciales en `legs`.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from instruments import validate_quote  # noqa: E402

RECONSTRUCT_VERSION = "reconstruct@v1.0.0"


def _check_pair(ars: dict | None, usd: dict, fx_kind: str,
                ratio: float = 1.0, volume_min: float = 0.0,
                max_stale_days: int = 7) -> tuple[float | None, str | None, list[str]]:
    """Núcleo puro de validación+cálculo para un par. Retorna (fx, null_reason, flags)."""
    flags: list[str] = []
    if ars is None or usd is None:
        return None, "MISSING_LEG", flags
    for q, name in ((ars, "ARS"), (usd, "USD")):
        ok, reason = validate_quote(q)
        if not ok:
            return None, reason, flags
    if ars["date"] != usd["date"]:
        return None, "MISMATCHED_LEGS", flags
    if ars["currency"] != "ARS":
        return None, "CURRENCY_MISMATCH_ARS_LEG", flags
    want_usd = "USD" if fx_kind == "MEP" else "USD_CABLE"
    # ADR-CCL usa USD simple en pata exterior; se acepta USD o USD_CABLE para CCL.
    if fx_kind == "MEP" and usd["currency"] != "USD":
        return None, "CURRENCY_MISMATCH_USD_LEG", flags
    if fx_kind == "CCL" and usd["currency"] not in ("USD", "USD_CABLE"):
        return None, "CURRENCY_MISMATCH_USD_LEG", flags
    if ars["settlement"] != usd["settlement"]:
        return None, "SETTLEMENT_MISMATCH", flags
    if ars["settlement"] == "UNDECLARED" or usd["settlement"] == "UNDECLARED":
        flags.append("UNDECLARED_SETTLEMENT")
    if ratio is None or ratio <= 0:
        return None, "BAD_RATIO", flags
    for q in (ars, usd):
        try:
            if float(q.get("volume") or 0) < volume_min and volume_min > 0:
                flags.append("LOW_LIQUIDITY")
                break
        except (TypeError, ValueError):
            return None, "BAD_VOLUME", flags
    if max_stale_days is not None:
        try:
            from datetime import date
            qd = date.fromisoformat(ars["date"])
            rd = date.fromisoformat(str(ars["retrieved_at"])[:10])
            if abs((rd - qd).days) > max_stale_days:
                flags.append("STALE_PRICE")
        except (ValueError, TypeError):
            flags.append("UNPARSEABLE_DATES")
    px_ars, px_usd = float(ars["price"]), float(usd["price"])
    if px_usd == 0:
        return None, "DIVISION_BY_ZERO", flags
    fx = px_ars * ratio / px_usd
    if fx <= 0:
        return None, "NONPOSITIVE_FX", flags
    return fx, None, flags


def reconstruct_day(date_: str, pairs: list[dict], fx_kind: str,
                    volume_min: float = 0.0,
                    max_stale_days: int = 7) -> dict:
    """Reconstruye un día desde lista de pares {ars, usd, ratio, instrument}.

    Retorna {date, fx_type, fx_value(mediana o None), n, legs[], null_reason, flags,
    reconstruct_version}. Sin pares válidos -> fx_value=None (no imputa).
    """
    assert fx_kind in ("MEP", "CCL")
    legs = []
    for p in pairs:
        fx, reason, flags = _check_pair(p.get("ars"), p.get("usd"), fx_kind,
                                        p.get("ratio", 1.0), volume_min, max_stale_days)
        legs.append({"instrument": p.get("instrument"), "fx": fx,
                     "null_reason": reason, "flags": flags})
    valid = [l["fx"] for l in legs if l["fx"] is not None]
    day_flags = sorted({f for l in legs for f in l["flags"]})
    if not valid:
        reasons = sorted({l["null_reason"] for l in legs if l["null_reason"]})
        return {"date": date_, "fx_type": f"{fx_kind}_RECONSTRUCTED",
                "fx_value": None, "n": 0, "legs": legs,
                "null_reason": "|".join(reasons) if reasons else "NO_PAIRS",
                "flags": day_flags, "reconstruct_version": RECONSTRUCT_VERSION}
    return {"date": date_, "fx_type": f"{fx_kind}_RECONSTRUCTED",
            "fx_value": statistics.median(valid), "n": len(valid), "legs": legs,
            "null_reason": None, "flags": day_flags,
            "reconstruct_version": RECONSTRUCT_VERSION}
