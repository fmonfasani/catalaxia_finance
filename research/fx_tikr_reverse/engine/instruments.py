#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registro de instrumentos + validador de quotes — PRIORIDAD 3.

Contiene el universo (bonos AL30/GD30 con patas ARS/USD-local/USD-cable y los
3 pares ADR de _dolar.py) con ISIN NOT_VERIFIED (no inventado) y el validador
de filas instrument_quote según schema P3. La descarga histórica de precios
vive en BYMA EOD (AUTH_REQUIRED) o yfinance (UNDECLARED); aquí NO se descarga
nada: sólo registry + validación pura (clase A, testeable sin red).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

SETTLEMENTS = {"CI", "24hs", "48hs", "T+1", "T+2", "UNDECLARED"}
CURRENCIES = {"ARS", "USD", "USD_CABLE"}
MARKETS = {"BYMA", "NYSE", "NASDAQ", "EXTERIOR"}

REGISTRY: list[dict] = [
    {"instrument": "BONAR 2030", "ticker": "AL30", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "48hs",
     "currency": "ARS", "rol": "ARS_LEG_MEP_CCL"},
    {"instrument": "BONAR 2030", "ticker": "AL30D", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "48hs",
     "currency": "USD", "rol": "USD_LOCAL_LEG_MEP"},
    {"instrument": "BONAR 2030", "ticker": "AL30C", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "48hs",
     "currency": "USD_CABLE", "rol": "USD_CABLE_LEG_CCL"},
    {"instrument": "GLOBAL 2030", "ticker": "GD30", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "48hs",
     "currency": "ARS", "rol": "ARS_LEG_MEP_CCL"},
    {"instrument": "GLOBAL 2030", "ticker": "GD30D", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "48hs",
     "currency": "USD", "rol": "USD_LOCAL_LEG_MEP"},
    {"instrument": "GLOBAL 2030", "ticker": "GD30C", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "48hs",
     "currency": "USD_CABLE", "rol": "USD_CABLE_LEG_CCL"},
    {"instrument": "GGAL ADR", "ticker": "GGAL.BA", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "UNDECLARED",
     "currency": "ARS", "rol": "ARS_LEG_CCL", "ratio": 10, "par": "GGAL"},
    {"instrument": "GGAL ADR", "ticker": "GGAL", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "NASDAQ", "settlement": "UNDECLARED",
     "currency": "USD", "rol": "USD_LEG_CCL", "ratio": 10, "par": "GGAL.BA"},
    {"instrument": "YPF ADR", "ticker": "YPFD.BA", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "UNDECLARED",
     "currency": "ARS", "rol": "ARS_LEG_CCL", "ratio": 1, "par": "YPF"},
    {"instrument": "YPF ADR", "ticker": "YPF", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "NYSE", "settlement": "UNDECLARED",
     "currency": "USD", "rol": "USD_LEG_CCL", "ratio": 1, "par": "YPFD.BA"},
    {"instrument": "PAMP ADR", "ticker": "PAMP.BA", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "BYMA", "settlement": "UNDECLARED",
     "currency": "ARS", "rol": "ARS_LEG_CCL", "ratio": 25, "par": "PAM"},
    {"instrument": "PAMP ADR", "ticker": "PAM", "isin": None,
     "isin_status": "NOT_VERIFIED", "market": "NYSE", "settlement": "UNDECLARED",
     "currency": "USD", "rol": "USD_LEG_CCL", "ratio": 25, "par": "PAMP.BA"},
]

QUOTE_FIELDS = ["instrument", "ticker", "isin", "date", "market", "settlement",
                "currency", "price", "volume", "source", "source_url",
                "retrieved_at", "sha256"]


def validate_quote(q: dict) -> tuple[bool, str | None]:
    """Valida una fila instrument_quote. Retorna (ok, null_reason). Puro."""
    for f in QUOTE_FIELDS:
        if f not in q:
            return False, f"MISSING_FIELD_{f}"
    if q["market"] not in MARKETS:
        return False, "BAD_MARKET"
    if q["settlement"] not in SETTLEMENTS:
        return False, "BAD_SETTLEMENT"
    if q["currency"] not in CURRENCIES:
        return False, "BAD_CURRENCY"
    try:
        p = float(q["price"])
    except (TypeError, ValueError):
        return False, "MISSING_PRICE"
    if p <= 0:
        return False, "ZERO_OR_NEGATIVE_PRICE"
    try:
        float(q["volume"]) if q["volume"] is not None else 0.0
    except (TypeError, ValueError):
        return False, "BAD_VOLUME"
    for f in ("source", "source_url", "retrieved_at", "sha256", "date", "ticker", "instrument"):
        if not q.get(f):
            return False, f"MISSING_{f.upper()}"
    return True, None
