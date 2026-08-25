# -*- coding: utf-8 -*-
"""
M0 -- Discovery / contrato Yahoo Finance
=========================================
Sondeos controlados sobre el Golden Case (YPF ADR NYSE + YPFD.BA local)
para documentar comportamiento REAL de yfinance antes de construir el
pipeline. Ninguna descarga masiva. Evidencia -> JSON + consola.

Clasificacion de campos pedida por el contrato:
STATIC | SNAPSHOT | HISTORICAL | DERIVED | UNSTABLE | UNKNOWN
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
OUT = ROOT / "outputs" / "docs" / "fase_market"
OUT.mkdir(parents=True, exist_ok=True)

TICKERS = {"YPF": "ADR NYSE (golden case)", "YPFD.BA": "accion local BYMA"}
ev: dict = {"ts_utc": datetime.now(timezone.utc).isoformat(),
            "yfinance": yf.__version__, "tickers": {}}


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe(tk: str) -> dict:
    t = yf.Ticker(tk)
    r: dict = {}

    # --- H3: historia maxima, auto_adjust=False, acciones incluidas
    h = t.history(period="max", interval="1d", auto_adjust=False, actions=True)
    r["history_max"] = {
        "rows": int(len(h)),
        "min_date": str(h.index.min()) if len(h) else None,
        "max_date": str(h.index.max()) if len(h) else None,
        "columns": list(h.columns),
        "index_tz": str(h.index.tz) if len(h) else None,
        "index_dtype": str(h.index.dtype) if len(h) else None,
        "dividends_rows": int((h["Dividends"] != 0).sum()) if "Dividends" in h else None,
        "splits_rows": int((h["Stock Splits"] != 0).sum()) if "Stock Splits" in h else None,
    }

    # --- auto_adjust=True: que pasa con Close/Adj Close
    ha = t.history(period="5d", interval="1d", auto_adjust=True, actions=False)
    r["auto_adjust_true"] = {
        "columns": list(ha.columns),
        "close_es_ajustado": bool(len(h)),
    }
    # comparacion closes misma ventana
    hf = t.history(period="5d", interval="1d", auto_adjust=False, actions=False)
    if len(ha) and len(hf):
        r["auto_adjust_true"]["diff_close_vs_sin_adj"] = float(
            (ha["Close"].iloc[-1] - hf["Close"].iloc[-1]).round(6))

    # --- fast_info (SNAPSHOT movil)
    fi = t.fast_info
    keys = {}
    for k in ("currency", "exchange", "fullExchangeName", "timezone",
              "shares", "last_price", "previous_close", "open", "day_high",
              "day_low", "year_high", "year_low", "fifty_day_average",
              "two_hundred_day_average", "ten_day_average",
              "three_month_average", "market_cap", "quote_type"):
        try:
            v = getattr(fi, k, None)
            keys[k] = None if v is None else (str(v)[:40])
        except Exception as e:
            keys[k] = f"ERR:{type(e).__name__}"
    r["fast_info"] = keys

    # --- history_metadata (SNAPSHOT de la ultima respuesta)
    hm = getattr(t, "history_metadata", {}) or {}
    r["history_metadata_keys"] = sorted(map(str, hm.keys()))
    r["history_metadata_sample"] = {k: str(hm.get(k))[:60] for k in
                                    ("currency", "exchangeName", "instrumentType",
                                     "firstTradeDate", "regularMarketTime",
                                     "gmtOffSetMilliseconds", "timeZoneShortName")}
    # fullExchangeName vive aca?
    r["history_metadata_sample"]["fullExchangeName"] = str(hm.get("fullExchangeName"))

    # --- info: inventario de claves (SNAPSHOT/PROFILE; NUNCA historico)
    try:
        info = t.info or {}
        r["info_key_count"] = len(info)
        r["info_keys"] = sorted(map(str, info.keys()))
        r["info_sample"] = {k: str(info.get(k))[:50] for k in
                            ("currency", "exchange", "fullExchangeName",
                             "instrumentType" if "instrumentType" in info else "quoteType",
                             "firstTradeDate", "regularMarketPrice",
                             "regularMarketPreviousClose", "fiftyTwoWeekHigh",
                             "fiftyTwoWeekLow", "timeZoneFullName")}
    except Exception as e:
        r["info_error"] = f"{type(e).__name__}: {str(e)[:100]}"

    # --- intervalos disponibles (sondeo minimo)
    iv = {}
    for interval, params in (("1wk", {"period": "max"}),
                             ("1mo", {"period": "max"}),
                             ("1h", {"period": "730d"}),
                             ("15m", {"period": "60d"}),
                             ("1m", {"period": "7d"})):
        try:
            hh = t.history(interval=interval, auto_adjust=False, **params)
            iv[interval] = {"ok": True, "rows": int(len(hh)),
                            "min": str(hh.index.min()), "max": str(hh.index.max())}
        except Exception as e:
            iv[interval] = {"ok": False, "error": str(e)[:80]}
    r["intervals"] = iv

    # --- pre/post market disponible?
    try:
        pp = t.history(period="2d", interval="15m", prepost=True)
        ppn = t.history(period="2d", interval="15m", prepost=False)
        r["prepost"] = {"rows_prepost": int(len(pp)),
                        "rows_regular": int(len(ppn)),
                        "extra_rows": int(len(pp) - len(ppn))}
    except Exception as e:
        r["prepost"] = {"error": str(e)[:80]}

    return r


for tk, nota in TICKERS.items():
    print(f"[{utcnow()}] probing {tk} ({nota}) ...")
    try:
        ev["tickers"][tk] = probe(tk)
    except Exception as e:
        ev["tickers"][tk] = {"FATAL": f"{type(e).__name__}: {str(e)[:200]}"}

out_json = OUT / "M0_discovery_evidence.json"
out_json.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")

# resumen consola
for tk, d in ev["tickers"].items():
    if "FATAL" in d:
        print(f"\n== {tk}: FATAL {d['FATAL']}")
        continue
    hm = d.get("history_max", {})
    print(f"\n== {tk}")
    print(f"  history max : {hm.get('rows')} filas  {hm.get('min_date')} -> {hm.get('max_date')}")
    print(f"  columnas    : {hm.get('columns')}")
    print(f"  tz index    : {hm.get('index_tz')}  ({hm.get('index_dtype')})")
    print(f"  dividends   : {hm.get('dividends_rows')} eventos | splits: {hm.get('splits_rows')} eventos")
    aa = d.get("auto_adjust_true", {})
    print(f"  autoadj True cols: {aa.get('columns')} | diff close vs sin-ajuste: {aa.get('diff_close_vs_sin_adj')}")
    print(f"  fast_info   : currency={d['fast_info'].get('currency')} exchange={d['fast_info'].get('exchange')} "
          f"full={d['fast_info'].get('fullExchangeName')} quote_type={d['fast_info'].get('quote_type')}")
    print(f"  meta sample : {d['history_metadata_sample']}")
    print(f"  info        : {d.get('info_key_count')} claves | sample: {d.get('info_sample')}")
    print("  intervalos  : " + ", ".join(
        f"{k}:{'OK' if v.get('ok') else 'ERR'}({v.get('rows', '-')})" for k, v in d.get("intervals", {}).items()))
    print(f"  prepost     : {d.get('prepost')}")
print(f"\nEvidencia -> {out_json}")
