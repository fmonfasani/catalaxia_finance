"""
PASO 4 — Descargar precios de mercado desde yfinance
Input : cedears_con_cik.json (295 tickers SEC únicos)
Output: precios.json (precio actual, 52w hi/lo, market cap, shares)

Fuente: yfinance (Yahoo Finance, gratis, sin auth)
- Usa fast_info que es 1 request por ticker (no descarga histórico completo)
- Sin rate limit duro pero ponemos delay para ser amables
- Tickers con punto (BRK.B) se convierten a guión (BRK-B) para yfinance

Tiempo estimado: 295 tickers * 0.2s ~ 60 segundos
"""

import json
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf

INPUT_FILE  = "cedears_con_cik.json"
OUTPUT_FILE = "precios.json"
ERROR_FILE  = "precios_errores.json"
DELAY       = 0.2  # seg entre tickers


def normalizar_ticker_yf(ticker: str) -> str:
    """yfinance usa '-' donde SEC/BYMA usan '.' (ej. BRK.B -> BRK-B)."""
    return ticker.replace(".", "-")


def descargar_ticker(ticker: str) -> dict:
    """Descarga precio + 52w hi/lo + market cap. Retorna dict o {error: ...}."""
    tk = yf.Ticker(normalizar_ticker_yf(ticker))
    try:
        fi = tk.fast_info
        # fast_info puede tener todos None si el ticker es inválido
        if fi.last_price is None:
            return {"error": "no_data", "ticker_yf": normalizar_ticker_yf(ticker)}

        return {
            "last_price":    fi.last_price,
            "year_high":     fi.year_high,
            "year_low":      fi.year_low,
            "market_cap":    fi.market_cap,
            "shares":        fi.shares,
            "currency":      fi.currency,
            "exchange":      fi.exchange,
            "previous_close": fi.previous_close,
            "fetched_at":    datetime.now().isoformat(),
        }
    except Exception as e:
        return {"error": str(e)[:200], "ticker_yf": normalizar_ticker_yf(ticker)}


def cargar_tickers_unicos(input_file: str) -> list[dict]:
    """Devuelve lista de {ticker_sec, byma_ticker, nombre_sec} únicos por ticker_sec."""
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    vistos = {}
    for c in data["cedears"]:
        ts = c.get("ticker_sec")
        if not ts or ts in vistos:
            if ts:
                vistos[ts]["byma_tickers"].append(c["byma_ticker"])
            continue
        vistos[ts] = {
            "ticker_sec":   ts,
            "byma_tickers": [c["byma_ticker"]],
            "nombre_sec":   c.get("nombre_sec"),
            "cik":          c.get("cik"),
        }
    return list(vistos.values())


def main():
    print("=" * 60)
    print("  PASO 4 -- Descargar precios desde yfinance")
    print("=" * 60)

    tickers = cargar_tickers_unicos(INPUT_FILE)
    print(f"\n  Tickers SEC únicos: {len(tickers)}")
    print(f"  Tiempo estimado: ~{len(tickers) * DELAY:.0f} segundos\n")

    precios = {}
    errores = []

    for i, t in enumerate(tickers, 1):
        ts = t["ticker_sec"]
        print(f"  [{i:3}/{len(tickers)}] {ts:<8}", end=" ", flush=True)

        resultado = descargar_ticker(ts)

        if "error" in resultado:
            print(f"-> ERROR: {resultado['error']}")
            errores.append({**t, **resultado})
        else:
            precio = resultado["last_price"]
            print(f"-> {resultado['currency']} {precio:.2f}")
            precios[ts] = {**t, **resultado}

        time.sleep(DELAY)

    # Guardar precios
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total":     len(tickers),
            "ok":        len(precios),
            "errores":   len(errores),
            "precios":   precios,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  OK {OUTPUT_FILE}")

    # Guardar errores
    if errores:
        with open(ERROR_FILE, "w", encoding="utf-8") as f:
            json.dump(errores, f, ensure_ascii=False, indent=2)
        print(f"  OK {ERROR_FILE} ({len(errores)} errores)")

    print(f"\n  Tickers procesados : {len(tickers)}")
    print(f"  Descargados OK     : {len(precios)}")
    print(f"  Errores            : {len(errores)}")
    print("\nPaso 4 completo.")
    print(f"Proximo paso -> 05_calcular_ratios.py\n")


if __name__ == "__main__":
    main()
