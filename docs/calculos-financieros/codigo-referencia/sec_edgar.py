"""
Fetcher de financials SEC EDGAR — Backend B (Mateo).

extraer_metricas() viene CASI textual de 03_descargar_financials_sec.py
(script de investigación) — esa función ya implementa correctamente el
dedup por (start, end) conservando el `filed` más reciente. No reescribir
esta lógica, ver docs/02-jobs.md#por-que-insert-y-no-upsert.

Ver también docs/06-decisiones-tecnicas.md para el caso de empresas IFRS
(20-F) como Infosys.
"""

from __future__ import annotations

import requests

SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Forms aceptados: anuales (10-K, 20-F, 40-F) + trimestrales (10-Q) + enmiendas
FORMS_ACEPTADOS = ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A")

# Métricas clave — ver docs/03-base-de-datos.md y analizar_cobertura.py
# (script de investigación) para la cobertura real medida por métrica.
METRICAS_GAAP = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "GrossProfit",
    "OperatingIncomeLoss",
    "NetIncomeLoss",
    # Fallback de NetIncomeLoss: empresas que consolidan intereses
    # minoritarios (ej. CAT con Caterpillar Financial Services) tagean su
    # income statement con ProfitLoss y dejan NetIncomeLoss desactualizado o
    # sin tag en 10-K/10-Q. Ver docs/screener/GUIA_SEC_EDGAR_PARA_DEVS.md#9.
    "ProfitLoss",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "Depreciation",
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
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "CommonStockSharesOutstanding",
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfDividends",
]

PREFERENCIA_UNIDAD = ("USD", "USD/shares", "shares", "pure")


def extraer_metricas(facts: dict, esquema: str = "us-gaap") -> dict:
    """
    Del JSON completo de companyfacts, extrae las métricas clave incluyendo
    trimestrales (10-Q) para poder calcular TTM en app/calculators/ratios.py.

    Dedup por (start, end), conservando el `filed` más reciente — maneja
    restatements automáticamente.

    `esquema` permite pasar "ifrs-full" para empresas que no reportan en
    us-gaap (ver docs/02-jobs.md#empresas-extranjeras-caso-infy).
    """
    gaap = facts.get("facts", {}).get(esquema, {})
    resultado: dict = {}

    for metrica in METRICAS_GAAP:
        if metrica not in gaap:
            continue

        units = gaap[metrica].get("units", {})

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
                "end": v.get("end"),
                "val": v.get("val"),
                "fy": v.get("fy"),
                "fp": v.get("fp"),
                "form": v.get("form"),
                "filed": v.get("filed"),
                "frame": v.get("frame"),
            }
            for v in valores
            if v.get("form") in FORMS_ACEPTADOS and v.get("val") is not None
        ]

        por_periodo: dict = {}
        for v in registros:
            key = (v["start"], v["end"])
            prev = por_periodo.get(key)
            if prev is None or (v.get("filed") or "") > (prev.get("filed") or ""):
                por_periodo[key] = v

        if por_periodo:
            resultado[metrica] = {
                "unit": unidad,
                "datos": sorted(
                    por_periodo.values(),
                    key=lambda x: (x.get("end") or "", x.get("start") or ""),
                ),
            }

    return resultado


def descargar_empresa(cik: str, sec_user_agent: str = "Mozilla/5.0") -> dict:
    """
    Descarga el JSON completo de companyfacts para un CIK y extrae métricas.

    Maneja el caso IFRS: si us-gaap está vacío, intenta ifrs-full
    automáticamente (empresas como Infosys que reportan 20-F).
    """
    url = SEC_FACTS_URL.format(cik=cik)
    headers = {"User-Agent": sec_user_agent}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        facts = r.json()
    except requests.exceptions.HTTPError:
        return {"cik": cik, "error": f"HTTP {r.status_code}"}
    except Exception as e:  # noqa: BLE001
        return {"cik": cik, "error": str(e)}

    metricas = extraer_metricas(facts, esquema="us-gaap")
    esquema_usado = "us-gaap"

    if not metricas:
        metricas = extraer_metricas(facts, esquema="ifrs-full")
        esquema_usado = "ifrs-full"

    if not metricas:
        return {"cik": cik, "error": "sin_datos_xbrl"}

    return {
        "cik": cik,
        "esquema": esquema_usado,
        "entity_name": facts.get("entityName", ""),
        "metricas": metricas,
    }
