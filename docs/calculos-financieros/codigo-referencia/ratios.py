"""
Calculador de ratios — Job 2 (Mateo, con apoyo de Valentino).

Este módulo NUNCA hace requests a internet. Solo recibe datos ya
descargados (de financials_raw vía SQL, no de archivos) y devuelve ratios
calculados. Ver docs/02-jobs.md#job-2--calculo-de-ratios para el contrato
completo y docs/06-decisiones-tecnicas.md para el detalle de TTM y EBITDA.

TODO (Mateo): portar la lógica completa de 05_calcular_ratios.py
(script de investigación) a este módulo. Lo que sigue es el esqueleto de
funciones puras que ese script ya resolvió — no reinventar el cálculo de
TTM, solo adaptarlo a leer desde rows de SQL en vez de JSON en disco.
"""

from __future__ import annotations

from datetime import date

# Fallback de métricas equivalentes — ver docs/06-decisiones-tecnicas.md
FALLBACK_REVENUE = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
)
FALLBACK_DA = (
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "Depreciation",
)
FALLBACK_CAPEX = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
)
FALLBACK_DIVIDENDOS = (
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfDividends",
)


def dias_periodo(periodo_start: date | None, periodo_end: date | None) -> int | None:
    """Duración en días de un período — clave para distinguir Q vs YTD."""
    if periodo_start is None or periodo_end is None:
        return None
    return (periodo_end - periodo_start).days + 1


def clasificar_periodo(dias: int | None) -> str:
    """
    Ver docs/02-jobs.md tabla de clasificación:
    ~90d = trimestre, ~180d = semianual, ~270d = nueve meses, ~365d = anual.
    """
    if dias is None:
        return "desconocido"
    if dias <= 120:
        return "trimestre"
    if dias <= 210:
        return "semianual"
    if dias <= 300:
        return "nueve_meses"
    return "anual"


def resolver_metrica(datapoints_por_metrica: dict, candidatos: tuple[str, ...]) -> list | None:
    """
    Itera la lista de nombres XBRL candidatos para un concepto contable y
    devuelve la primera serie de datos que exista. Ver docs/06-decisiones-
    tecnicas.md tabla de fallback.
    """
    for nombre in candidatos:
        serie = datapoints_por_metrica.get(nombre)
        if serie:
            return serie
    return None


def calcular_ttm_flujo(serie: list) -> float | None:
    """
    TTM para una métrica de flujo (Revenue, NetIncome, CFO, CapEx, etc).

    TODO (Mateo): portar la lógica completa de ttm_flujo() en
    05_calcular_ratios.py — estrategias A) 4 trimestres standalone,
    B) Annual + YTD_actual - YTD_anterior, C) último anual solo.
    """
    raise NotImplementedError("Portar desde 05_calcular_ratios.py — ver docs/02-jobs.md")


def calcular_cagr(serie_anual: list, years: int = 5) -> float | None:
    """CAGR = (valor_fin / valor_ini)^(1/years) - 1. Ver docs/06-decisiones-tecnicas.md."""
    raise NotImplementedError("Portar desde 05_calcular_ratios.py")


def calcular_ebitda(net_income: float | None, da: float | None,
                     interest: float | None, tax: float | None) -> float | None:
    """
    EBITDA no existe en XBRL — se construye sumando 4 componentes.
    Si alguno es None, el resultado es None (nunca se estima).
    Ver docs/06-decisiones-tecnicas.md#ebitda-no-existe-en-xbrl.
    """
    componentes = (net_income, da, interest, tax)
    if any(c is None for c in componentes):
        return None
    return sum(componentes)  # type: ignore[arg-type]


def calcular_ratios_ticker(precios_row: dict, financials_rows: list[dict]) -> dict:
    """
    Punto de entrada del Job 2 para un ticker individual.

    precios_row: una fila de precios_raw.
    financials_rows: todas las filas de financials_raw para ese CIK.

    Devuelve un dict listo para UPSERT en `ratios` (ver docs/03-base-de-datos.md).

    TODO (Mateo): implementar usando las funciones de arriba + la lógica de
    05_calcular_ratios.py para PER, EPS, margen, ROE, FCFonCE, payout y
    Deuda/EBITDA.
    """
    raise NotImplementedError("Implementar siguiendo docs/02-jobs.md#paso-5")
