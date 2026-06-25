"""
PASO 3 — Descargar financials de SEC EDGAR para cada empresa
Input : cedears_con_cik.json (422 tickers, 295 CIKs únicos)
Output: financials_sec/  (1 JSON por empresa)
        financials_index.json (índice de lo descargado)

Fuente: data.sec.gov/api/xbrl/companyfacts/{CIK}.json
- Gratis, sin auth, sin API key
- Rate limit SEC: 10 req/seg -> usamos 0.15s entre requests
- Cada JSON contiene TODO el historial financiero de la empresa
- Campos clave: us-gaap -> Revenues, NetIncome, Assets, Liabilities, etc.

Tiempo estimado: 295 empresas x 0.15s = ~45 segundos
"""

import json
import time
import os
import requests
from datetime import datetime

INPUT_FILE    = "cedears_con_cik.json"
OUTPUT_DIR    = "financials_sec"
INDEX_FILE    = "financials_index.json"
ERROR_FILE    = "financials_errores.json"

SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_HEADERS   = {"User-Agent": "valuarty-research contacto@valuarty.com"}
DELAY         = 0.15  # seg entre requests (respetar rate limit SEC 10 req/s)

# Si True, re-descarga aunque exista el archivo (cambió el schema → necesario).
FORCE_REDOWNLOAD = True

# Schema version: si cambia la estructura del JSON, bump y re-descargar
SCHEMA_VERSION = 3

# Forms aceptados: anuales (10-K, 20-F, 40-F) + trimestrales (10-Q) + enmiendas
FORMS_ACEPTADOS = ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A")

# Métricas clave que vamos a extraer (us-gaap)
METRICAS_GAAP = [
    # Income Statement
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "GrossProfit",
    "OperatingIncomeLoss",
    "NetIncomeLoss",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
    # D&A para EBITDA
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "Depreciation",
    # Balance Sheet
    "Assets",
    "AssetsCurrent",
    "Liabilities",
    "LiabilitiesCurrent",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "LongTermDebt",
    "LongTermDebtNoncurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "DebtCurrent",
    "RetainedEarningsAccumulatedDeficit",
    # Cash Flow
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    # Shares (point in time)
    "CommonStockSharesOutstanding",
    "CommonStockSharesIssued",
    # Dividends
    "CommonStockDividendsPerShareDeclared",
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfDividends",
]

# Orden de preferencia para la unidad de cada métrica
PREFERENCIA_UNIDAD = ("USD", "USD/shares", "shares", "pure")


def cargar_ciks(input_file: str) -> list[dict]:
    """Carga CIKs únicos desde el JSON de paso 2."""
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    vistos = {}
    for d in data["cedears"]:
        cik = d.get("cik")
        if cik and cik not in vistos:
            vistos[cik] = {
                "cik":        cik,
                "ticker_sec": d.get("ticker_sec"),
                "nombre_sec": d.get("nombre_sec"),
                "byma_tickers": [d["byma_ticker"]],
            }
        elif cik:
            vistos[cik]["byma_tickers"].append(d["byma_ticker"])

    return list(vistos.values())


def extraer_metricas(facts: dict) -> dict:
    """
    Del JSON completo de companyfacts, extrae las métricas clave incluyendo
    trimestrales (10-Q) para poder calcular TTM en el paso 5.

    Por cada datapoint conserva: start, end, val, fy, fp, form, filed, frame.
    - `start`/`end`     : permiten medir longitud del período (Q vs YTD vs FY)
    - `fp`              : Q1/Q2/Q3/FY
    - `filed`           : usado para dedup (queda la versión más reciente)
    - `frame`           : marco fiscal estandarizado SEC (ej. "CY2024Q3I")

    Dedup por (start, end), conservando el `filed` más reciente.
    """
    gaap = facts.get("facts", {}).get("us-gaap", {})
    resultado = {}

    for metrica in METRICAS_GAAP:
        if metrica not in gaap:
            continue

        units = gaap[metrica].get("units", {})

        # Elegir unidad según preferencia (USD > USD/shares > shares > pure)
        unidad, valores = None, []
        for u in PREFERENCIA_UNIDAD:
            if u in units and units[u]:
                unidad, valores = u, units[u]
                break
        if not valores:
            continue

        registros = [
            {
                "start": v.get("start"),
                "end":   v.get("end"),
                "val":   v.get("val"),
                "fy":    v.get("fy"),
                "fp":    v.get("fp"),
                "form":  v.get("form"),
                "filed": v.get("filed"),
                "frame": v.get("frame"),
            }
            for v in valores
            if v.get("form") in FORMS_ACEPTADOS and v.get("val") is not None
        ]

        # Dedup por (start, end) — mantener el filed más reciente
        por_periodo = {}
        for v in registros:
            key = (v["start"], v["end"])
            prev = por_periodo.get(key)
            if prev is None or (v.get("filed") or "") > (prev.get("filed") or ""):
                por_periodo[key] = v

        if por_periodo:
            resultado[metrica] = {
                "unit":  unidad,
                "datos": sorted(
                    por_periodo.values(),
                    key=lambda x: (x.get("end") or "", x.get("start") or ""),
                ),
            }

    return resultado


def descargar_empresa(empresa: dict, session: requests.Session) -> dict:
    cik = empresa["cik"]
    url = SEC_FACTS_URL.format(cik=cik)

    try:
        r = session.get(url, headers=SEC_HEADERS, timeout=30)
        r.raise_for_status()
        facts = r.json()
    except requests.exceptions.HTTPError as e:
        return {"cik": cik, "error": f"HTTP {r.status_code}", "url": url}
    except Exception as e:
        return {"cik": cik, "error": str(e), "url": url}

    # Metadata básica
    entity = facts.get("entityType", "")
    nombre = facts.get("entityName", empresa["nombre_sec"])

    # Extraer métricas
    metricas = extraer_metricas(facts)

    return {
        "schema_version": SCHEMA_VERSION,
        "cik":          cik,
        "ticker_sec":   empresa["ticker_sec"],
        "byma_tickers": empresa["byma_tickers"],
        "nombre":       nombre,
        "entity_type":  entity,
        "metricas_disponibles": list(metricas.keys()),
        "metricas":     metricas,
        "descargado_en": datetime.now().isoformat(),
    }


def main():
    print("=" * 60)
    print("  PASO 3 -- Descargar financials desde SEC EDGAR")
    print("=" * 60)

    # Crear directorio output
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Cargar CIKs únicos
    empresas = cargar_ciks(INPUT_FILE)
    print(f"\n  CIKs únicos a descargar: {len(empresas)}")
    print(f"  Output dir: {OUTPUT_DIR}/")
    print(f"  Tiempo estimado: ~{len(empresas) * DELAY:.0f} segundos")
    print(f"\n  Iniciando descarga...\n")

    session  = requests.Session()
    index    = []
    errores  = []
    ok_count = 0

    for i, empresa in enumerate(empresas, 1):
        cik    = empresa["cik"]
        ticker = empresa["ticker_sec"] or cik
        nombre = (empresa["nombre_sec"] or "")[:35]

        # Check si ya existe (resume si se interrumpe).
        # Si el schema cambió o FORCE_REDOWNLOAD=True, re-descargar.
        out_path = os.path.join(OUTPUT_DIR, f"{cik}.json")
        if os.path.exists(out_path) and not FORCE_REDOWNLOAD:
            try:
                with open(out_path, encoding="utf-8") as fp:
                    cached = json.load(fp)
                if cached.get("schema_version") == SCHEMA_VERSION:
                    print(f"  [{i:3}/{len(empresas)}] SKIP {ticker:<8} (ya existe, schema v{SCHEMA_VERSION})")
                    index.append({"cik": cik, "ticker": ticker, "estado": "cached"})
                    ok_count += 1
                    continue
            except Exception:
                pass  # cache corrupto → re-descargar

        print(f"  [{i:3}/{len(empresas)}] {ticker:<8} {nombre}", end=" ", flush=True)

        resultado = descargar_empresa(empresa, session)

        if "error" in resultado:
            print(f"-> ERROR: {resultado['error']}")
            errores.append(resultado)
            index.append({"cik": cik, "ticker": ticker, "estado": "error",
                          "error": resultado["error"]})
        else:
            n_metricas = len(resultado["metricas_disponibles"])
            print(f"-> OK ({n_metricas} métricas)")

            # Guardar JSON individual
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)

            index.append({
                "cik":      cik,
                "ticker":   ticker,
                "nombre":   resultado["nombre"],
                "byma_tickers": resultado["byma_tickers"],
                "metricas": resultado["metricas_disponibles"],
                "estado":   "ok",
            })
            ok_count += 1

        time.sleep(DELAY)

    # Guardar índice
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp":  datetime.now().isoformat(),
            "total":      len(empresas),
            "ok":         ok_count,
            "errores":    len(errores),
            "empresas":   index,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  OK {INDEX_FILE}")

    # Guardar errores
    if errores:
        with open(ERROR_FILE, "w", encoding="utf-8") as f:
            json.dump(errores, f, ensure_ascii=False, indent=2)
        print(f"  OK {ERROR_FILE} ({len(errores)} errores)")

    print("\n── RESUMEN ──────────────────────────────────────────────────")
    print(f"  Empresas procesadas : {len(empresas)}")
    print(f"  Descargadas OK      : {ok_count}")
    print(f"  Errores             : {len(errores)}")
    print(f"  Archivos en         : {OUTPUT_DIR}/")
    print("─────────────────────────────────────────────────────────────")
    print("\nPaso 3 completo.")
    print("Proximo paso -> 04_calcular_ratios.py")
    print(f"Input        -> {OUTPUT_DIR}/ + {INDEX_FILE}\n")


if __name__ == "__main__":
    main()