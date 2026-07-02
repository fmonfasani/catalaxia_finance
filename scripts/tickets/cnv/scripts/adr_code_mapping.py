"""
ADR CNV Code Mapping — maps 7-digit NRO codes to standard concept names.

Two variants:
  - "nonbank": FT=147 (standard NIIF, same codes as BYMA)
  - "bank": FT=487 (NIIF bancos, slightly different codes/ratios)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / "debug"

# ================================================================
# NON-BANK (FT=147) → MAPPING TO STANDARD CONCEPTS
# ================================================================
NONBANK_MAP = {
    # -- Balance Sheet --
    "1122500": "CashAndEquivalents",           # EFECTIVO Y EQUIVALENTES A EFECTIVO
    "1122300": "FinancialAssetsCurrent",        # ACTIVOS FINANCIEROS CORRIENTES
    "1121999": "AccountsReceivable",            # CUENTAS POR COBRAR CORRIENTES
    "1122400": "OtherAssetsCurrent",            # OTROS ACTIVOS NO FINANCIEROS CORRIENTES
    "1120100": "Inventories",                   # INVENTARIOS CORRIENTES
    "1139999": "TotalCurrentAssets",            # ACTIVO CORRIENTE
    "1112400": "FinancialAssetsNonCurrent",     # ACTIVOS FINANCIEROS NO CORRIENTES
    "1111999": "AccountsReceivableNonCurrent",  # CUENTAS POR COBRAR NO CORRIENTES
    "1110100": "PropertyPlantEquipment",        # PROPIEDADES PLANTAS Y EQUIPOS
    "1112500": "OtherAssetsNonCurrent",         # OTROS ACTIVOS NO FINANCIEROS NO CORRIENTES
    "1110200": "IntangibleAssets",              # ACTIVOS INTANGIBLES
    "1119999": "TotalNonCurrentAssets",         # ACTIVO NO CORRIENTE
    "1999999": "TotalAssets",                   # TOTAL DEL ACTIVO
    # -- Equity --
    "2210999": "CapitalStock",                  # CAPITAL
    "2210300": "CapitalAdjustment",             # AJUSTE DE CAPITAL
    "2210500": "AdditionalPaidInCapital",       # APORTES NO CAPITALIZADOS
    "2210900": "OtherCapitalItems",             # OTROS CONCEPTOS DEL CAPITAL
    "2211100": "LegalReserve",                  # RESERVA LEGAL
    "2211200": "OtherReserves",                 # OTRAS RESERVAS
    "2211999": "RetainedEarnings",              # GANANCIAS RESERVADAS
    "2211300": "NonControllingInterests",       # INTERESES NO CONTROLANTES
    "2212999": "UnappropriatedResults",         # RESULTADOS NO ASIGNADOS
    "2213999": "OtherComprehensiveIncome",      # RESULTADOS INTEGRALES
    "2299999": "TotalEquity",                   # TOTAL PATRIMONIO NETO
    # -- Liabilities --
    "2322200": "FinancialDebtCurrent",          # PASIVOS FINANCIEROS CORRIENTES
    "2321999": "AccountsPayable",               # CUENTAS POR PAGAR CORRIENTES
    "2322100": "TaxPayableCurrent",             # PASIVOS POR IMPUESTOS CORRIENTES
    "2322300": "OtherLiabilitiesCurrent",       # OTROS PASIVOS NO FINANCIEROS CORRIENTES
    "2339999": "TotalCurrentLiabilities",       # PASIVO CORRIENTE
    "2312300": "FinancialDebtNonCurrent",       # PASIVOS FINANCIEROS NO CORRIENTES
    "2311999": "AccountsPayableNonCurrent",     # CUENTAS POR PAGAR NO CORRIENTES
    "2312200": "DeferredTaxLiabilities",        # PASIVOS POR IMPUESTOS NO CORRIENTES
    "2312400": "OtherLiabilitiesNonCurrent",    # OTROS PASIVOS NO FINANCIEROS NO CORRIENTES
    "2319999": "TotalNonCurrentLiabilities",    # PASIVO NO CORRIENTE
    "2399999": "TotalLiabilities",              # TOTAL DEL PASIVO
    "2999999": "TotalLiabilitiesEquity",        # TOTAL DEL PASIVO Y PATRIMONIO NETO
    # -- Income Statement --
    "3000100": "Revenue",                       # INGRESOS DE ACTIVIDADES ORDINARIAS
    "3000200": "CostOfRevenue",                 # COSTO DE VENTAS Y/O SERVICIOS
    "3009999": "GrossProfit",                   # GANANCIA (PERDIDA) BRUTA
    "3011301": "DirectorsFees",                 # HONORARIOS A DIRECTORES Y SINDICOS
    "3011300": "AdminExpenses",                 # OTROS GASTOS DE ADMINISTRACION
    "3011200": "SellingExpenses",               # GASTOS DE COMERCIALIZACION
    "3011400": "OtherOperatingExpenses",        # OTROS GASTOS OPERATIVOS
    "3011100": "OtherOperatingIncome",          # OTROS INGRESOS
    "3011600": "DepreciationAmortization",      # DEPRECIACIONES Y AMORTIZACIONES
    "3019999": "OperatingIncome",               # GANANCIA (PERDIDA) DE ACTIVIDADES OPERATIVAS
    "3021400": "FinancialIncome",               # INGRESOS FINANCIEROS
    "3021500": "FinancialCosts",                # COSTOS FINANCIEROS
    "3021800": "RECPAM",                        # RECPAM
    "3021900": "OtherResults",                  # OTROS RESULTADOS
    "3029999": "ProfitBeforeTax",               # GANANCIA ANTES DE IMPUESTOS
    "3031100": "IncomeTax",                     # INGRESO (GASTO) POR IMPUESTOS
    "3049999": "NetIncome",                     # GANANCIA DEL PERIODO
    "3061999": "OtherComprehensiveIncomeTotal", # OTRO RESULTADO INTEGRAL
    "3099999": "TotalComprehensiveIncome",      # RESULTADO INTEGRAL TOTAL
    # -- Cash Flow --
    "3241100": "CashFromOperations",            # CAMBIOS EN ACTIVOS Y PASIVOS OPERATIVOS
    "3241200": "CashFromInvesting",             # ACTIVIDADES DE INVERSION
    "3241300": "CashFromFinancing",             # ACTIVIDADES DE FINANCIACION
    "3240000": "NetCashChange",                 # INCREMENTO NETA DE EFECTIVO
    # -- Pre-calculated Ratios (CNV) --
    "8000000": "EPS_Basic",                     # GANANCIA BASICA POR ACCION
    "8000001": "EPS_Diluted",                   # GANANCIA DILUIDA POR ACCION
    "8000002": "TotalEquity_PriorYear",         # PATRIMONIO NETO EJERCICIO ANTERIOR
    "8000003": "EBIT",                          # EBIT
    "8000004": "EBITDA",                        # EBITDA
    "8000005": "WorkingCapital",                # CAPITAL DE TRABAJO
    "8000006": "Liquidity",                     # LIQUIDEZ
    "8000007": "Solvency",                      # SOLVENCIA
    "8000008": "CapitalImmobilization",         # INMOVILIZACION DEL CAPITAL
    "8000009": "ROE",                           # RENTABILIDAD PATRIMONIO NETO (ROE)
    "8000010": "ROA",                           # RENTABILIDAD DEL ACTIVO (ROA)
    "8000011": "DebtRatio",                     # ENDEUDAMIENTO
    "8000012": "ShortTermDebtRatio",            # ENDEUDAMIENTO A CORTO PLAZO
    "8000013": "Leverage",                      # APALANCAMIENTO
    "8000014": "NetMargin",                     # MARGEN NETO / VENTAS
    "8000015": "DebtToEBITDA",                  # DEUDA FINANCIERA / EBITDA
    "8000016": "EBITDA_Coverage",               # EBITDA / COSTOS FINANCIEROS
    "8000017": "DuPont_Analysis",               # ANALISIS DU-PONT
}

# ================================================================
# BANK (FT=487) → MAPPING TO STANDARD CONCEPTS
# ================================================================
BANK_MAP = {
    # -- Balance Sheet --
    "1122500": "CashAndEquivalents",           # EFECTIVO Y DEPOSITOS EN BANCOS
    "1122600": "DebtSecuritiesFVTPL",           # TITULOS DE DEUDA A VALOR RAZONABLE
    "1122700": "LoansAndAdvances",              # PRESTAMOS Y OTRAS FINANCIACIONES
    "1122800": "DerivativesAndRepos",           # OPERACIONES DE PASE, DERIVADOS
    "1122900": "DeferredTaxAssets",             # ACTIVO POR IMPUESTO DIFERIDO
    "1123100": "EquityInstruments",             # INVERSIONES EN INSTRUMENTOS DE PATRIMONIO
    "1123200": "FinancialAssetsAsCollateral",   # ACTIVOS FINANCIEROS ENTREGADOS EN GARANTIA
    "1110100": "PropertyPlantEquipment",        # PROPIEDAD PLANTA Y EQUIPO
    "1123300": "InvestmentsInSubsidiaries",     # INVERSIONES EN SUBSIDIARIAS
    "1110200": "IntangibleAssets",              # ACTIVOS INTANGIBLES
    "1122300": "OtherFinancialAssets",          # OTROS ACTIVOS FINANCIEROS
    "1122400": "OtherNonFinancialAssets",       # OTROS ACTIVOS NO FINANCIEROS
    "1999999": "TotalAssets",                   # TOTAL DEL ACTIVO
    # -- Equity --
    "2210999": "CapitalStock",                  # CAPITAL
    "2210300": "CapitalAdjustment",             # AJUSTE DE CAPITAL
    "2210500": "AdditionalPaidInCapital",       # APORTES NO CAPITALIZADOS
    "2210900": "OtherCapitalItems",             # OTROS CONCEPTOS DEL CAPITAL
    "2211100": "LegalReserve",                  # RESERVA LEGAL
    "2211200": "OtherReserves",                 # OTRAS RESERVAS
    "2211999": "RetainedEarnings",              # GANANCIAS RESERVADAS
    "2211300": "NonControllingInterests",       # INTERESES NO CONTROLANTES
    "2212999": "UnappropriatedResults",         # RESULTADOS NO ASIGNADOS
    "2213999": "OtherComprehensiveIncome",      # RESULTADOS INTEGRALES
    "2299999": "TotalEquity",                   # TOTAL PATRIMONIO NETO
    # -- Liabilities --
    "2311000": "Deposits",                      # DEPOSITOS
    "2311100": "LiabilitiesAtFVTPL",            # PASIVOS A VALOR DE REALIZACION
    "2311200": "DerivativeLiabilities",         # DERIVADOS, PASES Y OTROS PASIVOS
    "2311300": "Provisions",                    # PROVISIONES
    "2311400": "FinancingFromBCRA",             # FINANCIACIONES BCRA
    "2311500": "SubordinatedNotes",             # OBLIGACIONES NEGOCIABLES SUBORDINADAS
    "2311600": "NotesIssued",                   # OBLIGACIONES NEGOCIABLES EMITIDAS
    "2322100": "CurrentTaxPayable",             # PASIVOS POR IMPUESTO CORRIENTE
    "2312200": "DeferredTaxLiabilities",        # PASIVOS POR IMPUESTO DIFERIDO
    "2322300": "OtherNonFinancialLiabilities",  # OTROS PASIVOS NO FINANCIEROS
    "2399999": "TotalLiabilities",              # TOTAL DEL PASIVO
    "2999999": "TotalLiabilitiesEquity",        # TOTAL DEL PASIVO Y PATRIMONIO NETO
    # -- Income Statement --
    "3000100": "InterestIncome",                # INGRESOS POR INTERESES
    "3000200": "InterestExpense",               # EGRESOS POR INTERESES
    "3000102": "FeeIncome",                     # INGRESOS POR COMISIONES
    "3000201": "FeeExpense",                    # EGRESOS POR COMISIONES
    "3000101": "ImpairmentCharge",              # CARGO POR INCOBRABILIDAD
    "3000301": "NetFVAdjustment",               # RESULTADO NETO POR MEDICION A VR
    "3000302": "FXAndGoldDifference",           # DIFERENCIA DE COTIZACION ORO Y ME
    "3000303": "OtherOperatingIncome",          # OTROS INGRESOS OPERATIVOS
    "3000304": "DerecognitionResult",           # RESULTADO POR BAJA DE ACTIVOS
    "3009999": "NetOperatingIncome",            # INGRESO OPERATIVO NETO
    "3011301": "DirectorsFees",                 # HONORARIOS A DIRECTORES
    "3011300": "AdminExpenses",                 # OTROS GASTOS DE ADMINISTRACION
    "3011400": "EmployeeBenefits",              # BENEFICIOS AL PERSONAL
    "3011500": "OtherOperatingExpenses",        # OTROS GASTOS OPERATIVOS
    "3011600": "DepreciationAmortization",      # DEPRECIACIONES Y AMORTIZACIONES
    "3011700": "IncomeFromAssociates",          # RESULTADOS POR ASOCIADAS
    "3021800": "RECPAM",                        # RECPAM
    "3029999": "ProfitBeforeTax",               # GANANCIA ANTES DE IMPUESTOS
    "3031100": "IncomeTax",                     # INGRESO (GASTO) POR IMPUESTOS
    "3049999": "NetIncome",                     # GANANCIA DEL PERIODO
    "3061999": "OtherComprehensiveIncomeTotal", # OTRO RESULTADO INTEGRAL
    "3099999": "TotalComprehensiveIncome",      # RESULTADO INTEGRAL TOTAL
    # -- Cash Flow --
    "3241100": "CashFromOperations",            # FCO OPERATIVAS
    "3241200": "CashFromInvesting",             # FCO INVERSION
    "3241300": "CashFromFinancing",             # FCO FINANCIACION
    "3241400": "FXEffect",                      # EFECTO TIPO DE CAMBIO
    "3241500": "MonetaryEffectOnCash",          # EFECTO RESULTADO MONETARIO
    "3240000": "NetCashChange",                 # INCREMENTO NETA DE EFECTIVO
    # -- Pre-calculated Ratios (CNV) --
    "8000000": "EPS_Basic",                     # GANANCIA BASICA POR ACCION
    "8000001": "EPS_Diluted",                   # GANANCIA DILUIDA
    "8000002": "TotalEquity_PriorYear",         # PATRIMONIO NETO ANTERIOR
    "8000003": "EBIT",                          # EBIT
    "8000004": "EBITDA",                        # EBITDA
    "8000018": "Leverage",                      # C1 - APALANCAMIENTO
    "8000019": "ROE",                           # R1 - ROE
    "8000020": "ROA",                           # RG1 - ROA
    "8000021": "Liquidity_Coverage",            # L8_II - LIQUIDEZ
}

# ================================================================
# DIVIDEND (FT=339) → OUTPUT FIELDS
# ================================================================
DIVIDEND_FIELDS = {
    "MontoDelDividendo": "DividendAmount",
    "TipoDeDividendo": "DividendType",
    "MonedaDelDividendo": "DividendCurrency",
    "PorcentajeSobreElValorNonimal": "DividendPercent",
    "FechaEnQueSePoneADisposicion": "PaymentDate",
    "OrigenDeLosFondos": "FundSource",
}

# ================================================================
# HELPERS
# ================================================================
def get_mapping(form_type, nro_code):
    """Get the standard concept name for a given formType and NRO code."""
    if form_type in ("147", "154", "142"):
        return NONBANK_MAP.get(nro_code)
    elif form_type == "487":
        return BANK_MAP.get(nro_code)
    return None

def save_mapping():
    """Save mapping as JSON for use by the extractor."""
    out = {
        "nonbank": NONBANK_MAP,
        "bank": BANK_MAP,
        "dividend": DIVIDEND_FIELDS,
    }
    path = DEBUG / "adr_code_mapping.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Mapping saved to {path}")

# 13 ratios target concepts
TARGET_CONCEPTS = [
    "TotalAssets", "TotalLiabilities", "TotalEquity",
    "NetIncome", "Revenue", "EBIT", "EBITDA",
    "TotalCurrentAssets", "TotalCurrentLiabilities",
    "CashAndEquivalents", "FinancialDebtCurrent", "FinancialDebtNonCurrent",
    "Leverage", "ROE", "ROA", "Liquidity", "DebtToEBITDA",
    "NetMargin", "WorkingCapital",
    # Plus dividend
    "DividendAmount",
]

if __name__ == "__main__":
    save_mapping()
    print(f"Non-bank codes: {len(NONBANK_MAP)}")
    print(f"Bank codes: {len(BANK_MAP)}")
    print(f"Target concepts: {len(TARGET_CONCEPTS)}")
