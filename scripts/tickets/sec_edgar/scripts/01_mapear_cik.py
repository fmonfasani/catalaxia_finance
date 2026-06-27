"""
PASO 1 — Mapear los tickers de Tickets.xlsx a su CIK en SEC EDGAR.

Ver docs/screener/GUIA_SEC_EDGAR_PARA_DEVS.md#64-el-cik para el porque de
cada decision (User-Agent obligatorio, CIK con 10 digitos, etc).

Input : ../../Tickets.xlsx (columna unica "Ticker")
Output: datos/tickets_con_cik.csv   (ticker, cik, nombre_sec, exchange_hint)
        datos/tickets_sin_cik.csv   (ticker) - revision manual, NUNCA inventar CIK

Cachea datos/company_tickers.json para no volver a pegarle a SEC en cada
corrida (ese archivo cambia poco y SEC pide no abusar de las requests).
"""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import requests

HEADERS = {
    "User-Agent": "Federico Monfasani fmonfasani@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir())
TICKETS_XLSX = ROOT / "Tickets.xlsx"
DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
CACHE_FILE = DATOS_DIR / "company_tickers.json"
OUT_CON_CIK = DATOS_DIR / "tickets_con_cik.csv"
OUT_SIN_CIK = DATOS_DIR / "tickets_sin_cik.csv"

# Tickers reciclados: la SEC los reasigno a una empresa nueva sin relacion con
# la que originalmente representaban. Verificado a mano contra
# data.sec.gov/submissions/ el 24-jun-2026 (ver conversacion). Confirmado con
# el usuario: excluir y mandar a revision manual en vez de usar el CIK actual.
TICKERS_RECICLADOS = {
    "GOLD": "Hoy es Gold.com Inc (ex A-Mark Precious Metals), no Barrick "
            "Gold -- Barrick paso a cotizar como 'B' en 2025.",
    "CHA": "Hoy es Chagee Holdings Ltd (cadena de te china, IPO 2025), no "
           "China Telecom -- deslistada de NYSE en 2021.",
}


def leer_tickets() -> list[str]:
    wb = openpyxl.load_workbook(TICKETS_XLSX, data_only=True)
    ws = wb["Tickets"]
    return [r[0].strip().upper() for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]


def cargar_company_tickers() -> dict:
    """Descarga (una vez) y cachea el mapeo oficial ticker -> CIK de la SEC."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)

    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def armar_mapeo(company_tickers: dict) -> dict[str, dict]:
    """{ticker: {cik, nombre}} con CIK ya rellenado a 10 digitos."""
    mapeo = {}
    for entry in company_tickers.values():
        ticker = (entry.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        mapeo[ticker] = {
            "cik": str(entry["cik_str"]).zfill(10),
            "nombre": entry.get("title", ""),
        }
    return mapeo


def variantes(ticker: str) -> list[str]:
    """Variantes simples a probar antes de declarar 'no encontrado'."""
    v = [ticker]
    if "." in ticker:
        v.append(ticker.replace(".", "-"))
        v.append(ticker.split(".")[0])
    if "-" in ticker:
        v.append(ticker.replace("-", "."))
    return list(dict.fromkeys(v))  # dedup preservando orden


def main() -> None:
    print("=" * 60)
    print("  PASO 1 -- Mapear tickers de Tickets.xlsx a CIK (SEC EDGAR)")
    print("=" * 60)

    tickers = leer_tickets()
    print(f"\n  Tickers en Tickets.xlsx: {len(tickers)}")

    company_tickers = cargar_company_tickers()
    mapeo = armar_mapeo(company_tickers)
    print(f"  Empresas en mapeo oficial SEC: {len(mapeo)}")

    con_cik, sin_cik = [], []
    for ticker in tickers:
        if ticker in TICKERS_RECICLADOS:
            sin_cik.append({"ticker": ticker, "motivo": TICKERS_RECICLADOS[ticker]})
            print(f"  SKIP {ticker:<8} -> ticker reciclado: {TICKERS_RECICLADOS[ticker]}")
            continue

        encontrado = None
        for v in variantes(ticker):
            if v in mapeo:
                encontrado = v
                break

        if encontrado:
            info = mapeo[encontrado]
            con_cik.append({
                "ticker": ticker,
                "cik": info["cik"],
                "nombre_sec": info["nombre"],
                "matched_as": encontrado,
            })
            print(f"  OK   {ticker:<8} -> CIK {info['cik']}  ({info['nombre']})")
        else:
            sin_cik.append({"ticker": ticker, "motivo": "no encontrado en SEC"})
            print(f"  MISS {ticker:<8} -> no encontrado en SEC (revisar manualmente)")

    DATOS_DIR.mkdir(parents=True, exist_ok=True)

    import csv

    with open(OUT_CON_CIK, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "cik", "nombre_sec", "matched_as"])
        w.writeheader()
        w.writerows(con_cik)

    with open(OUT_SIN_CIK, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "motivo"])
        w.writeheader()
        w.writerows(sin_cik)

    print("\n" + "-" * 60)
    print(f"  Con CIK     : {len(con_cik)}/{len(tickers)}")
    print(f"  Sin CIK     : {len(sin_cik)}/{len(tickers)}")
    print(f"  CIKs unicos : {len({c['cik'] for c in con_cik})}")
    print(f"\n  OK {OUT_CON_CIK}")
    print(f"  OK {OUT_SIN_CIK}")
    print("\nPaso 1 completo. Proximo paso -> 02_descargar_datos.py")


if __name__ == "__main__":
    main()
