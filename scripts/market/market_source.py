# -*- coding: utf-8 -*-
"""
MARKET SOURCE -- abstraccion de fuente externa
===============================================
El motor de fetch no habla con yfinance: habla con una `Source`. Eso permite

  * produccion  -> YahooSource   (red real)
  * matriz test -> FixtureSource (replay determinista de RAW, fallas
                   programadas, payload corrupto, duplicados)

sin ramas `if testing` dentro del motor.

Contrato de Source:
    fetch(ticker, params) -> FetchResult
    name / version         identifican la fuente en provenance
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

DEFAULT_PARAMS = {"period": "max", "interval": "1d",
                  "auto_adjust": False, "actions": True}

COLUMNAS_ESPERADAS = ["Open", "High", "Low", "Close", "Adj Close",
                      "Volume", "Dividends", "Stock Splits"]


@dataclass
class FetchResult:
    ok: bool
    df: Optional[pd.DataFrame] = None
    metadata: dict = field(default_factory=dict)   # history_metadata de la fuente
    raw_bytes: Optional[bytes] = None              # payload exacto que se archiva
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 0
    elapsed_s: float = 0.0

    @property
    def rows(self) -> int:
        return 0 if self.df is None else int(len(self.df))


class SourceError(Exception):
    pass


class RawCorruptError(SourceError):
    """El payload recibido no se puede parsear como serie OHLC."""


def validar_payload(df) -> None:
    """Rechaza un DataFrame que no cumple la forma minima del contrato."""
    if df is None:
        raise RawCorruptError("payload None")
    if not isinstance(df, pd.DataFrame):
        raise RawCorruptError(f"payload no es DataFrame: {type(df).__name__}")
    faltantes = [c for c in ("Open", "High", "Low", "Close", "Volume")
                 if c not in df.columns]
    if faltantes:
        raise RawCorruptError(f"columnas ausentes: {faltantes}")
    if len(df) and not hasattr(df.index, "date") and not hasattr(df.index[0], "date"):
        raise RawCorruptError("indice no temporal")


class YahooSource:
    """Fuente de produccion. period=max, interval=1d, auto_adjust=False."""

    name = "yahoo"

    def __init__(self, retries: int = 2, backoff_s: float = 2.0):
        import yfinance as yf
        self._yf = yf
        self.version = f"yfinance@{yf.__version__}"
        self.retries = retries
        self.backoff_s = backoff_s

    def fetch(self, ticker: str, params: dict = None) -> FetchResult:
        params = dict(params or DEFAULT_PARAMS)
        t0 = time.time()
        err_type = err_msg = None
        for intento in range(self.retries + 1):
            try:
                tk = self._yf.Ticker(ticker)
                df = tk.history(**params)
                meta = dict(getattr(tk, "history_metadata", {}) or {})
                validar_payload(df)
                if len(df) == 0:
                    err_type, err_msg = "EMPTY", "la fuente devolvio 0 filas"
                    break
                return FetchResult(
                    ok=True, df=df, metadata=_meta_serializable(meta),
                    raw_bytes=df.to_csv(index=True).encode("utf-8"),
                    attempts=intento + 1, elapsed_s=round(time.time() - t0, 2))
            except Exception as e:                       # noqa: BLE001
                err_type, err_msg = type(e).__name__, str(e)[:300]
                if intento < self.retries:
                    time.sleep(self.backoff_s * (intento + 1))
        return FetchResult(ok=False, error_type=err_type or "EMPTY",
                           error_message=err_msg or "sin filas",
                           attempts=self.retries + 1,
                           elapsed_s=round(time.time() - t0, 2))

    def snapshot(self, ticker: str) -> dict:
        fi = self._yf.Ticker(ticker).fast_info
        campos = ("last_price", "previous_close", "open", "day_high", "day_low",
                  "year_high", "year_low", "fifty_day_average",
                  "two_hundred_day_average", "currency", "exchange", "timezone")
        out = {}
        for k in campos:
            try:
                out[k] = fi[k] if hasattr(fi, "__getitem__") else getattr(fi, k, None)
            except Exception:                            # noqa: BLE001
                out[k] = None
        try:
            out["volume"] = fi["last_volume"]
        except Exception:                                # noqa: BLE001
            out["volume"] = None
        return out


class FixtureSource:
    """Replay determinista para la matriz de tests.

    guion: lista de FetchResult (o excepciones) a devolver en orden; el ultimo
    elemento se repite si se piden mas fetches que los programados.
    """

    name = "fixture"

    def __init__(self, guion, version="fixture@1", snapshot_payload=None):
        self.version = version
        self._guion = list(guion)
        self._i = 0
        self._snapshot = snapshot_payload or {}
        self.llamadas = []

    def fetch(self, ticker: str, params: dict = None) -> FetchResult:
        self.llamadas.append(ticker)
        item = self._guion[min(self._i, len(self._guion) - 1)]
        self._i += 1
        if isinstance(item, Exception):
            return FetchResult(ok=False, error_type=type(item).__name__,
                               error_message=str(item)[:300], attempts=1)
        if callable(item):
            item = item()
        return item

    def snapshot(self, ticker: str) -> dict:
        return dict(self._snapshot)


# ------------------------------------------------------------- utilidades

def _meta_serializable(meta: dict) -> dict:
    """history_metadata trae objetos no JSON-serializables; deja solo lo util."""
    claves = ("currency", "exchangeName", "fullExchangeName", "instrumentType",
              "firstTradeDate", "regularMarketTime", "timezone",
              "exchangeTimezoneName", "gmtoffset", "gmtOffSetMilliseconds",
              "timeZoneShortName", "symbol", "longName", "shortName",
              "regularMarketPrice", "chartPreviousClose", "priceHint")
    out = {}
    for k in claves:
        v = meta.get(k)
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    tp = meta.get("currentTradingPeriod")
    if isinstance(tp, dict):
        try:
            reg = tp.get("regular") or {}
            out["regular_start"] = reg.get("start")
            out["regular_end"] = reg.get("end")
        except Exception:                                # noqa: BLE001
            pass
    return out


def df_desde_csv(raw_bytes: bytes, tz: str = None) -> pd.DataFrame:
    """Reconstruye el DataFrame desde bytes RAW archivados (replay de fixtures
    y verificacion de fidelidad de parseo)."""
    df = pd.read_csv(io.BytesIO(raw_bytes), index_col=0)
    df.index = pd.to_datetime(df.index, utc=False, format="mixed")
    if tz and df.index.tz is None:
        df.index = df.index.tz_localize(tz)
    return df


def resultado_desde_csv(path, tz=None, metadata=None) -> FetchResult:
    """FetchResult a partir de un history.csv archivado (fixture de replay)."""
    raw = open(path, "rb").read()
    df = df_desde_csv(raw, tz)
    return FetchResult(ok=True, df=df, metadata=dict(metadata or {}),
                       raw_bytes=df.to_csv(index=True).encode("utf-8"),
                       attempts=1)
