# -*- coding: utf-8 -*-
"""
FASE 3 -- Precios yfinance + FX para el subset
================================================
Baja precios de yfinance para los tickers del subset CNV que aun no estan
en la tabla precios.

BYMA tickers: usan sufijo ".BA" en yfinance (ej. ALUA.BA).
ADR tickers: usan su simbolo NYSE (ej. PAM, GGAL, TGS).

Escribe en tabla precios (INSERT OR REPLACE).
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"

# ADR: CUIT -> yfinance ticker
# Los _ADR_XXXX generados necesitan mapping manual a ticker yfinance real
ADR_YF = {
    "30500001735": "GGAL",     # Banco Galicia
    "30500003193": "BBAR",     # BBVA Argentina
    "30500010084": "BMA",      # Banco Macro
    "30500530851": "LOMA",     # Loma Negra
    "30509300700": "CRESY",    # Cresud
    "30525322749": "IRS",      # IRSA
    "30526552659": "PAM",      # Pampa Energia
    "30546689979": "YPF",      # YPF (mismo simbolo BYMA y NYSE)
    "30639453738": "TEO",      # Telecom Argentina
    "30657862068": "TGS",      # Transportadora Gas del Sur
    "30617442937": "SUPV",     # Grupo Supervielle
    "33500005179": "SUPV",     # Grupo Supervielle
    "33515950899": "VIST",     # Vista Energy
    "33650305499": "CEPU",     # Central Puerto
    "30704962807": "GGAL",     # Grupo Financiero Galicia
    "30696170580": "CAAP",     # Aeropuertos Argentina 2000 (Corp. America)
    "30714128309": "YPFD",     # YPF Energia Electrica -> YPPPF OTC o similar
}


def yf_precio(ticker_yf, retries=3):
    """Obtener precio + market cap + high/low de yfinance."""
    for attempt in range(retries):
        try:
            fi = yf.Ticker(ticker_yf).fast_info
            if fi is not None and fi.market_cap is not None:
                return {
                    "precio": fi.last_price,
                    "mcap": fi.market_cap,
                    "yhigh": fi.year_high,
                    "ylow": fi.year_low,
                    "cur": fi.currency,
                }
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return None
    return None


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    print("FASE 3 -- Precios yfinance")
    print("=" * 60)

    fecha = datetime.now(timezone.utc).isoformat()

    # --- Leer entidades primarias sin precio ---
    cur.execute("""
        SELECT m.cuit, m.ticker, m.grupo
        FROM mapa_entidades m
        WHERE m.es_primario = 1
          AND NOT EXISTS (SELECT 1 FROM precios p WHERE p.ticker = m.ticker)
        ORDER BY m.ticker
    """)
    pendientes = cur.fetchall()
    print(f"Entidades primarias sin precio: {len(pendientes)}")

    ok = 0
    sin_precio = 0

    for cuit, ticker, grupo in pendientes:
        # Determinar ticker yfinance
        if grupo == "adr":
            yf_tk = ADR_YF.get(cuit)
            if yf_tk is None:
                sin_precio += 1
                print(f"    [SIN ADR] {ticker:20s} cuit={cuit} no tiene ADR mapping")
                continue
        else:
            # BYMA: usar ".BA" suffix
            yf_tk = f"{ticker}.BA"

        # Obtener precio
        d = yf_precio(yf_tk)
        if d is None:
            sin_precio += 1
            print(f"    [SIN PRECIO] {ticker:20s} yf={yf_tk}")
            continue

        # Escribir en precios
        cur.execute("""
            INSERT OR REPLACE INTO precios (cik, ticker, precio, market_cap, year_high, year_low, currency, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cuit, ticker, d["precio"], d["mcap"], d.get("yhigh"), d.get("ylow"), d.get("cur"), fecha))
        ok += 1
        print(f"    OK {ticker:20s} yf={yf_tk:8s} precio={d['precio']:.2f} mcap={d['mcap']:.0f} cur={d.get('cur','?')}")

        time.sleep(0.3)

    con.commit()
    con.close()

    n_total = ok + sin_precio
    print(f"\n  Resultados:")
    print(f"    Nuevos descargados:   {ok}/{n_total}")
    print(f"    Sin precio:           {sin_precio}/{n_total}")
    print("\nFASE 3 -- OK")


if __name__ == "__main__":
    main()
