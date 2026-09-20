#!/usr/bin/env python3
"""
Catalaxia / YPF — Yahoo Finance market data extractor

Extracts price, 52-week high/low, dividends, and market data
for the YPF NYSE ADR. Only 5 FY rows (annual, no quarterly).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

BASE = Path(__file__).resolve().parent
INPUT = BASE / "YPF_FINANCIAL_INPUTS_2021_2025.csv"
OUTPUT_CSV = BASE / "YPF_YAHOO_MARKET_2021_2025.csv"
OUTPUT_XLSX = BASE / "YPF_YAHOO_MARKET_2021_2025.xlsx"

TICKER = "YPF"
EXPECTED_ROWS = 5


def get_price_history():
    tk = yf.Ticker(TICKER)
    hist = tk.history(
        start="2020-01-01", end="2026-07-01",
        auto_adjust=False, actions=True,
    )
    if hist is None or hist.empty:
        raise RuntimeError("Yahoo returned no history for YPF.")
    hist = hist.reset_index()
    hist["Date"] = pd.to_datetime(
        hist["Date"], errors="coerce"
    ).dt.tz_localize(None)
    return hist


def trailing_dividend(hist, end_date):
    start = end_date - timedelta(days=365)
    x = hist[(hist["Date"] > start) & (hist["Date"] <= end_date)]
    if "Dividends" not in x:
        return math.nan
    v = pd.to_numeric(x["Dividends"], errors="coerce").fillna(0).sum()
    return float(v) if pd.notna(v) else math.nan


def get_ticker_info():
    tk = yf.Ticker(TICKER)
    try:
        info = tk.info
    except Exception:
        info = {}
    return info


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing {INPUT}")

    fin = pd.read_csv(INPUT)
    if len(fin) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} rows; found {len(fin)}"
        )

    fin["period_end"] = pd.to_datetime(fin["period_end"], errors="raise")
    hist = get_price_history()
    info = get_ticker_info()

    rows = []
    for _, r in fin.iterrows():
        end = r["period_end"]
        eligible = hist[hist["Date"] <= end]
        if eligible.empty:
            raise RuntimeError(f"No Yahoo price for {end.date()}")

        day = eligible.iloc[-1]
        price = float(day["Close"]) if pd.notna(day["Close"]) else math.nan

        window = hist[
            (hist["Date"] <= end) &
            (hist["Date"] > end - timedelta(days=365))
        ]
        hi = pd.to_numeric(window["High"], errors="coerce").max()
        lo = pd.to_numeric(window["Low"], errors="coerce").min()

        div = trailing_dividend(hist, end)
        dy = (
            (div / price * 100)
            if pd.notna(div) and pd.notna(price) and price != 0
            else math.nan
        )

        rows.append({
            "fiscal_year": int(r["fiscal_year"]),
            "period": str(r["period"]),
            "period_end": end.strftime("%Y-%m-%d"),
            "price_usd": price,
            "52w_high_usd": float(hi) if pd.notna(hi) else math.nan,
            "52w_low_usd": float(lo) if pd.notna(lo) else math.nan,
            "dividend_per_share_ttm_usd": div,
            "dividend_yield_ttm_pct": dy,
            "trading_date_used": pd.Timestamp(day["Date"]).strftime("%Y-%m-%d"),
            "source": "Yahoo Finance",
            "ticker": TICKER,
            "yfinance_version": importlib.metadata.version("yfinance"),
        })

    out = pd.DataFrame(rows)

    checks = {
        c: int(out[c].notna().sum())
        for c in [
            "price_usd", "52w_high_usd", "52w_low_usd",
        ]
    }

    if checks["price_usd"] != EXPECTED_ROWS:
        raise AssertionError(
            f"YAHOO FAIL: price_usd {checks['price_usd']}/{EXPECTED_ROWS}"
        )

    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    out.to_excel(OUTPUT_XLSX, index=False)

    print("=" * 46)
    print("YPF YAHOO EXTRACTION")
    print("=" * 46)
    print(f"Rows: {len(out)}")
    for k, v in checks.items():
        print(f"  {k}: {v}/{EXPECTED_ROWS}")
    print()
    for _, row in out.iterrows():
        print(
            f"  {int(row['fiscal_year'])} {row['period']} "
            f"price={row['price_usd']:.2f}  "
            f"div_ttm={row['dividend_per_share_ttm_usd']:.4f}"
        )
    print()
    print("YAHOO EXTRACTION: PASS")
    print("=" * 46)


if __name__ == "__main__":
    main()
