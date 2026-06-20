"""
Fetcher de precios — Backend A (Valentino).

Adaptado de 04_descargar_precios.py (script de investigación). La lógica de
descarga se conserva igual; lo que cambia es que esta función NO escribe a
disco ni hace loop — recibe un ticker y devuelve un dict. El loop y la
persistencia viven en app/jobs/precio_job.py.

Ver docs/02-jobs.md#job-1a y docs/06-decisiones-tecnicas.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

import yfinance as yf


class PrecioResult(TypedDict, total=False):
    last_price: float | None
    year_high: float | None
    year_low: float | None
    market_cap: float | None
    shares: float | None
    currency: str | None
    exchange: str | None
    previous_close: float | None
    fetched_at: str
    error: str


def normalizar_ticker_yf(ticker: str) -> str:
    """yfinance usa '-' donde SEC/BYMA usan '.' (ej. BRK.B -> BRK-B)."""
    return ticker.replace(".", "-")


def descargar_ticker(ticker: str) -> PrecioResult:
    """
    Descarga precio + 52w hi/lo + market cap para un único ticker.

    Importante (ver docs/02-jobs.md): validar cada campo INDIVIDUALMENTE.
    fast_info puede devolver last_price válido pero year_high/year_low en
    None — no asumir que si uno está, todos están.
    """
    tk = yf.Ticker(normalizar_ticker_yf(ticker))
    try:
        fi = tk.fast_info

        if fi.last_price is None:
            return {"error": "no_data"}

        return {
            "last_price": fi.last_price,
            "year_high": fi.year_high,
            "year_low": fi.year_low,
            "market_cap": fi.market_cap,
            "shares": fi.shares,
            "currency": fi.currency,
            "exchange": fi.exchange,
            "previous_close": fi.previous_close,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:  # noqa: BLE001 — se loguea en el job, no aquí
        return {"error": str(e)[:200]}
