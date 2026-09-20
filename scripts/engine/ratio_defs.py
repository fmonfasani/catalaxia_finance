#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Definicion de ratios por CONCEPTO, no por tag.

Por que por concepto: un emisor extranjero presenta bajo `ifrs-full` y uno
domestico de EE.UU. bajo `us-gaap`. El mismo concepto economico —"activo
corriente"— se llama `CurrentAssets` en uno y `AssetsCurrent` en el otro. Si el
ratio se define por tag, funciona para una taxonomia y devuelve NULL para la
otra sin que nada avise.

Regla que se mantiene: **el orden de la lista ES la regla de fallback**, y la
pertenencia de un tag a un concepto es una DECLARACION explicita, no una
inferencia por parecido de nombre. Donde hay un segundo camino para el mismo
numero, se verifica (ver `ratios_multipath.py`).
"""
from __future__ import annotations

# concepto -> tags candidatos, en orden de preferencia.
# La primera tanda de cada lista es IFRS, la segunda US-GAAP; el orden entre
# taxonomias no importa porque un emisor sólo publica en una.
CONCEPTOS: dict[str, list[str]] = {
    "activo_total": ["Assets"],
    "activo_corriente": ["CurrentAssets", "AssetsCurrent"],
    "pasivo_total": ["Liabilities"],
    "pasivo_corriente": ["CurrentLiabilities", "LiabilitiesCurrent"],
    "patrimonio": [
        "Equity", "EquityAttributableToOwnersOfParent",
        "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "patrimonio_controladora": [
        "EquityAttributableToOwnersOfParent", "Equity", "StockholdersEquity"],
    "efectivo": [
        "CashAndCashEquivalents",
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "existencias": ["Inventories", "InventoryNet"],
    "resultado_neto": [
        "ProfitLossAttributableToOwnersOfParent", "ProfitLoss",
        "NetIncomeLoss", "ProfitLossAttributableToOwnersOfParentDiluted"],
    "ingresos": [
        "Revenue", "RevenueFromContractsWithCustomers",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenues"],
    "resultado_bruto": ["GrossProfit"],
    "resultado_operativo": [
        "ProfitLossFromOperatingActivities", "OperatingIncomeLoss"],
    "resultado_antes_impuestos": [
        "ProfitLossBeforeTax",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "impuesto": [
        "IncomeTaxExpenseContinuingOperations", "IncomeTaxExpenseBenefit"],
    "costo_financiero": ["FinanceCosts", "InterestExpense", "InterestExpenseNonoperating"],
    # CUIDADO con la equivalencia: `Borrowings` (IFRS) abarca deuda financiera
    # corriente y no corriente; `LongTermDebt` (US-GAAP) es la deuda de largo
    # plazo incluida su porcion corriente, y NO incluye papel comercial de
    # corto plazo. No son el mismo perimetro. Se usa igual porque es el
    # equivalente mas cercano, y el tag empleado queda en la provenance de cada
    # celda para que la diferencia sea visible, no tapada.
    "deuda_financiera": ["Borrowings", "DebtLongtermAndShorttermCombinedAmount",
                         "LongTermDebt"],
    "flujo_operativo": [
        "CashFlowsFromUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivities"],
    # --- por accion -------------------------------------------------------
    # El tag del EPS cambia de nombre entre ejercicios dentro de IFRS y ademas
    # difiere en US-GAAP. Verificado contra resultado_neto/acciones_promedio.
    "eps_basico": [
        "BasicEarningsLossPerShare",
        "BasicAndDilutedEarningsPerShare",
        "BasicAndDilutedEarningsLossPerShare",
        "EarningsPerShareBasic",
        "IncomeLossFromContinuingOperationsPerBasicShare"],
    "acciones_promedio": [
        "WeightedAverageShares",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted"],
    # `dei` es comun a las dos taxonomias: lleva la fecha de CARATULA, no la
    # del cierre. No es intercambiable con el promedio ponderado.
    "acciones_circulacion": [
        "EntityCommonStockSharesOutstanding",
        "NumberOfSharesOutstanding",
        "CommonStockSharesOutstanding"],
}

# ratio -> (concepto numerador, concepto a restar | None, concepto denominador,
#           unidad, publicable_en_screener)
#
# `publicable` en False = el calculo es correcto pero el numero no es una
# metrica de screener sin banda de sanidad (ver SCREENER_CONTRACT_V1 §6).
RATIOS: dict[str, tuple[str, str | None, str, str, bool]] = {
    "current_ratio":        ("activo_corriente", None, "pasivo_corriente", "veces", True),
    "quick_ratio":          ("activo_corriente", "existencias", "pasivo_corriente", "veces", True),
    "cash_ratio":           ("efectivo", None, "pasivo_corriente", "veces", True),
    "debt_to_equity":       ("pasivo_total", None, "patrimonio", "veces", True),
    "borrowings_to_equity": ("deuda_financiera", None, "patrimonio_controladora", "veces", True),
    "equity_ratio":         ("patrimonio", None, "activo_total", "fraccion", True),
    "roe":                  ("resultado_neto", None, "patrimonio", "fraccion", True),
    "roa":                  ("resultado_neto", None, "activo_total", "fraccion", True),
    "net_margin":           ("resultado_neto", None, "ingresos", "fraccion", True),
    "gross_margin":         ("resultado_bruto", None, "ingresos", "fraccion", True),
    "operating_margin":     ("resultado_operativo", None, "ingresos", "fraccion", True),
    "interest_coverage":    ("resultado_operativo", None, "costo_financiero", "veces", True),
    "effective_tax_rate":   ("impuesto", None, "resultado_antes_impuestos", "fraccion", False),
    "ocf_to_net_income":    ("flujo_operativo", None, "resultado_neto", "veces", False),
}

# Ratios que combinan mercado con contabilidad. Se resuelven aparte porque
# necesitan precio, moneda e instrumento, no sólo facts.
RATIOS_MERCADO = ("pe", "market_cap", "price_to_book")


def elegir_concepto(disponibles: dict, concepto: str) -> tuple[str | None, dict | None]:
    """Primer tag del concepto presente en `disponibles`.

    Devuelve `(tag, fact)`. El tag elegido queda registrado en la provenance:
    saber CUAL de los candidatos se uso es parte del resultado.
    """
    for tag in CONCEPTOS[concepto]:
        if tag in disponibles:
            return tag, disponibles[tag]
    return None, None


def taxonomia_de(namespaces: list[str]) -> str:
    """Clasifica la taxonomia contable a partir de los namespaces observados.

    No se deduce del pais ni del formulario: se mira lo que el filing declara.
    """
    ns = " ".join(namespaces or []).lower()
    ifrs = "ifrs-full" in ns or "ifrs.org" in ns
    gaap = "us-gaap" in ns or "fasb.org/us-gaap" in ns
    if ifrs and gaap:
        return "IFRS+US-GAAP"      # YPF: IFRS de fondo con srt/us-gaap accesorios
    if ifrs:
        return "ifrs-full"
    if gaap:
        return "us-gaap"
    return "DESCONOCIDA"
