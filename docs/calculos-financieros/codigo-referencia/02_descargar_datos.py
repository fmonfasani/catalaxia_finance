"""
PASO 2 — Descargar financials (SEC EDGAR) y precios (yfinance) crudos.

Reusa los fetchers puros que ya existen en el repo, sin tocarlos:
  backend/fetchers/sec_edgar.py  -> descargar_empresa()  (User-Agent + fallback ifrs-full)
  backend/fetchers/precios.py    -> descargar_ticker()

Input : datos/tickets_con_cik.csv
Output: datos/financials_sec/{cik}.json   (uno por empresa, resume-safe)
        datos/precios_tickets.json
        datos/financials_errores.json
        datos/precios_errores.json
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.fetchers.precios import descargar_ticker  # noqa: E402
from backend.fetchers.sec_edgar import descargar_empresa  # noqa: E402

SEC_USER_AGENT = "Federico Monfasani fmonfasani@gmail.com"
SEC_DELAY = 0.15  # rate limit SEC: 10 req/s
YF_DELAY = 0.2

DATOS_DIR = Path(__file__).resolve().parent / "datos"
IN_CON_CIK = DATOS_DIR / "tickets_con_cik.csv"
FIN_DIR = DATOS_DIR / "financials_sec"
PRECIOS_OUT = DATOS_DIR / "precios_tickets.json"
FIN_ERRORES_OUT = DATOS_DIR / "financials_errores.json"
PRECIOS_ERRORES_OUT = DATOS_DIR / "precios_errores.json"

# Si esta en False, no vuelve a descargar un CIK cuyo JSON ya existe en disco
# (permite resumir si el script se corta a mitad de camino).
FORCE_REDOWNLOAD = False


def leer_con_cik() -> list[dict]:
    with open(IN_CON_CIK, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def descargar_financials(filas: list[dict]) -> tuple[int, list[dict]]:
    """Descarga companyfacts por CIK unico. Devuelve (ok_count, errores)."""
    FIN_DIR.mkdir(parents=True, exist_ok=True)

    ciks_unicos: dict[str, dict] = {}
    for fila in filas:
        ciks_unicos.setdefault(fila["cik"], fila)

    print(f"\n  CIKs unicos a descargar: {len(ciks_unicos)}")
    print(f"  Tiempo estimado: ~{len(ciks_unicos) * SEC_DELAY:.0f}s")

    ok, errores = 0, []
    for i, (cik, fila) in enumerate(ciks_unicos.items(), 1):
        out_path = FIN_DIR / f"{cik}.json"
        ticker = fila["ticker"]

        if out_path.exists() and not FORCE_REDOWNLOAD:
            print(f"  [{i:3}/{len(ciks_unicos)}] SKIP {ticker:<8} (ya en cache)")
            ok += 1
            continue

        resultado = descargar_empresa(cik, sec_user_agent=SEC_USER_AGENT)

        if "error" in resultado:
            print(f"  [{i:3}/{len(ciks_unicos)}] {ticker:<8} -> ERROR: {resultado['error']}")
            errores.append({"cik": cik, "ticker": ticker, "error": resultado["error"]})
        else:
            n_metricas = len(resultado.get("metricas", {}))
            esquema = resultado.get("esquema", "?")
            print(f"  [{i:3}/{len(ciks_unicos)}] {ticker:<8} -> OK "
                  f"({n_metricas} metricas, {esquema})")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
            ok += 1

        time.sleep(SEC_DELAY)

    return ok, errores


def descargar_precios(filas: list[dict]) -> tuple[dict, list[dict]]:
    print(f"\n  Tickers a descargar (yfinance): {len(filas)}")
    print(f"  Tiempo estimado: ~{len(filas) * YF_DELAY:.0f}s")

    precios, errores = {}, []
    for i, fila in enumerate(filas, 1):
        ticker = fila["ticker"]
        resultado = descargar_ticker(ticker)

        if "error" in resultado:
            print(f"  [{i:3}/{len(filas)}] {ticker:<8} -> ERROR: {resultado['error']}")
            errores.append({"ticker": ticker, "error": resultado["error"]})
        else:
            precio = resultado.get("last_price")
            print(f"  [{i:3}/{len(filas)}] {ticker:<8} -> OK (precio={precio})")
            precios[ticker] = resultado

        time.sleep(YF_DELAY)

    return precios, errores


def main() -> None:
    print("=" * 60)
    print("  PASO 2 -- Descargar financials EDGAR + precios yfinance")
    print("=" * 60)

    filas = leer_con_cik()
    print(f"\n  Tickers con CIK: {len(filas)}")

    print("\n-- Financials (SEC EDGAR) --")
    fin_ok, fin_errores = descargar_financials(filas)

    print("\n-- Precios (yfinance) --")
    precios, precios_errores = descargar_precios(filas)

    with open(PRECIOS_OUT, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "precios": precios,
        }, f, ensure_ascii=False, indent=2, default=str)

    if fin_errores:
        with open(FIN_ERRORES_OUT, "w", encoding="utf-8") as f:
            json.dump(fin_errores, f, ensure_ascii=False, indent=2)
    if precios_errores:
        with open(PRECIOS_ERRORES_OUT, "w", encoding="utf-8") as f:
            json.dump(precios_errores, f, ensure_ascii=False, indent=2)

    print("\n" + "-" * 60)
    print(f"  Financials OK    : {fin_ok}/{len(set(f['cik'] for f in filas))} CIKs")
    print(f"  Financials error : {len(fin_errores)}")
    print(f"  Precios OK       : {len(precios)}/{len(filas)}")
    print(f"  Precios error    : {len(precios_errores)}")
    print(f"\n  OK {PRECIOS_OUT}")
    print("\nPaso 2 completo. Proximo paso -> 03_calcular_ratios.py")


if __name__ == "__main__":
    main()
