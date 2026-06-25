"""
PASO 3 — Calcular ratios fundamentales por empresa.

Algoritmo portado tal cual de _research/scripts/05_calcular_ratios.py (ya
validado contra Investing.com, ver docs/screener/RESUMEN_FINAL_HALLAZGOS.md)
-- no se reinventa el calculo de TTM ni el CAGR, solo cambia de donde se leen
los datos crudos (datos/financials_sec/{cik}.json en vez de financials_sec/
del research, mismo formato porque ambos vienen de la misma extraer_metricas()).

Regla dura (docs/screener/GUIA_RATIOS_EDGAR_vs_INVESTING.md): si falta un
componente, el ratio queda NULL. Nunca se estima.

Input : datos/tickets_con_cik.csv, datos/financials_sec/*.json, datos/precios_tickets.json
Output: datos/ratios_tickets.csv + datos/ratios_tickets.json
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

DATOS_DIR = Path(__file__).resolve().parent / "datos"
IN_CON_CIK = DATOS_DIR / "tickets_con_cik.csv"
FIN_DIR = DATOS_DIR / "financials_sec"
PRECIOS_F = DATOS_DIR / "precios_tickets.json"
CSV_OUT = DATOS_DIR / "ratios_tickets.csv"
JSON_OUT = DATOS_DIR / "ratios_tickets.json"


# ============================================================
# HELPERS de extraccion (idem _research/scripts/05_calcular_ratios.py)
# ============================================================

def cargar_financials(cik: str) -> dict | None:
    p = FIN_DIR / f"{cik}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_serie(fin: dict, metric: str) -> list[dict]:
    m = fin.get("metricas", {}).get(metric)
    if not m:
        return []
    return m.get("datos", [])


def get_serie_alt(fin: dict, *metrics: str) -> tuple[str, list[dict]]:
    """De las metricas candidatas, la que tenga el datapoint mas reciente."""
    mejor_metric, mejor_serie, mejor_end = "", [], ""
    for m in metrics:
        s = get_serie(fin, m)
        if not s:
            continue
        ultimo_end = max((dp.get("end") or "" for dp in s), default="")
        if ultimo_end > mejor_end:
            mejor_metric, mejor_serie, mejor_end = m, s, ultimo_end
    return mejor_metric, mejor_serie


def dias_periodo(dp: dict) -> int | None:
    if not dp.get("start") or not dp.get("end"):
        return None
    try:
        s = datetime.fromisoformat(dp["start"])
        e = datetime.fromisoformat(dp["end"])
        return (e - s).days + 1
    except Exception:
        return None


def ttm_flujo(serie: list[dict]) -> tuple[float | None, str | None, str | None]:
    """
    TTM para una metrica de flujo. Estrategias en orden de preferencia:
    A) 4 trimestres standalone (~90d) consecutivos -> sumar.
    B) Annual + YTD_actual - YTD_anterior (canonico para 10-Q acumulado).
    C) Ultimo anual solo (~365d).

    Devuelve (valor, end, estrategia). La estrategia 'C' NO es un TTM rodante
    real: es el ultimo anio fiscal cerrado. Si un trimestre reciente tuvo un
    item no recurrente, ese FY puede divergir fuerte del TTM que muestra
    Investing (caso MRK, ver docs/screener/DIAGNOSTICO_INVESTING_vs_EDGAR.md).
    Por eso se reporta la estrategia, para poder marcar la fila como FY.
    """
    if not serie:
        return None, None, None

    quarters, ytds, annuals = [], [], []
    for dp in serie:
        d = dias_periodo(dp)
        if d is None:
            continue
        if 85 <= d <= 100:
            quarters.append(dp)
        elif 355 <= d <= 380:
            annuals.append(dp)
        elif 170 <= d <= 290:
            ytds.append(dp)

    quarters.sort(key=lambda x: x["end"], reverse=True)
    ytds.sort(key=lambda x: x["end"], reverse=True)
    annuals.sort(key=lambda x: x["end"], reverse=True)

    # --- Estrategia A: 4 quarters consecutivos ---
    if len(quarters) >= 4:
        candidatos = quarters[:4]
        candidatos_asc = sorted(candidatos, key=lambda x: x["end"])
        consecutivo = True
        for i in range(1, 4):
            prev_end = datetime.fromisoformat(candidatos_asc[i - 1]["end"])
            curr_start = datetime.fromisoformat(candidatos_asc[i]["start"])
            gap = (curr_start - prev_end).days
            if gap < -5 or gap > 5:
                consecutivo = False
                break
        if consecutivo:
            return sum(q["val"] for q in candidatos), candidatos[0]["end"], "A"

    # --- Estrategia B: Annual + YTD_actual - YTD_anterior ---
    if annuals and ytds:
        anual = annuals[0]
        anual_end = datetime.fromisoformat(anual["end"])
        ytd_actual = None
        for y in ytds:
            if not y.get("start"):
                continue
            ystart = datetime.fromisoformat(y["start"])
            if abs((ystart - anual_end).days) <= 5:
                ytd_actual = y
                break

        if ytd_actual is not None:
            ytd_actual_end = datetime.fromisoformat(ytd_actual["end"])
            ytd_actual_dias = dias_periodo(ytd_actual)
            ytd_prior = None
            for y in ytds:
                if y is ytd_actual:
                    continue
                yend = datetime.fromisoformat(y["end"])
                delta_year = (ytd_actual_end - yend).days
                if 355 <= delta_year <= 380 and abs(dias_periodo(y) - ytd_actual_dias) <= 5:
                    ytd_prior = y
                    break

            if ytd_prior is not None:
                ttm = anual["val"] + ytd_actual["val"] - ytd_prior["val"]
                return ttm, ytd_actual["end"], "B"

    # --- Estrategia C: ultimo anual solo ---
    if annuals:
        return annuals[0]["val"], annuals[0]["end"], "C"

    return None, None, None


def ultimo_valor(serie: list[dict]) -> tuple[float | None, str | None]:
    if not serie:
        return None, None
    last = max(serie, key=lambda x: x.get("end") or "")
    return last.get("val"), last.get("end")


def serie_anual(serie: list[dict]) -> list[dict]:
    annuals = []
    for dp in serie:
        d = dias_periodo(dp)
        if d is not None and 355 <= d <= 380:
            annuals.append(dp)
        elif dp.get("start") is None and dp.get("form") in ("10-K", "20-F", "40-F"):
            annuals.append(dp)

    por_fy = {}
    for dp in annuals:
        fy = dp.get("fy") or (dp.get("end") or "")[:4]
        prev = por_fy.get(fy)
        if prev is None or (dp.get("filed") or "") > (prev.get("filed") or ""):
            por_fy[fy] = dp

    return sorted(por_fy.values(), key=lambda x: x.get("end") or "")


def cagr(serie_anual_data: list[dict], years: int = 5) -> float | None:
    if len(serie_anual_data) < years + 1:
        return None
    inicio = serie_anual_data[-(years + 1)]["val"]
    fin = serie_anual_data[-1]["val"]
    if inicio is None or fin is None or inicio <= 0 or fin <= 0:
        return None
    return (fin / inicio) ** (1 / years) - 1


# ============================================================
# HELPERS de los fixes (ver docs/screener/DIAGNOSTICO_INVESTING_vs_EDGAR.md)
# ============================================================

def serie_anual_eps_limpia(fin: dict) -> list[dict]:
    """Serie anual de EPS diluido, SOLO periodos de un anio fiscal completo
    (355-380 dias). Excluye los datapoints raros con start=None (a veces
    periodos parciales/transicion tageados como 10-K) que contaminan el anio
    base y hacen explotar el CAGR -- ej. CSCO con un EPS base de 0,02 que
    inflaba el crecimiento a +173%. Ver fix #7 del diagnostico."""
    out = []
    for dp in get_serie(fin, "EarningsPerShareDiluted"):
        d = dias_periodo(dp)
        if d is not None and 355 <= d <= 380 and dp.get("val") is not None:
            out.append(dp)
    por_fy = {}
    for dp in out:
        fy = dp.get("fy") or (dp.get("end") or "")[:4]
        prev = por_fy.get(fy)
        if prev is None or (dp.get("filed") or "") > (prev.get("filed") or ""):
            por_fy[fy] = dp
    return sorted(por_fy.values(), key=lambda x: x.get("end") or "")


def cagr_eps_robusto(serie_eps: list[dict], years: int = 5) -> float | None:
    """CAGR de EPS con guarda de anio base. Ademas del requisito de signo
    (base y fin > 0), descarta el calculo si el anio base es un outlier chico
    (< 10% de la mediana de la serie): eso delata un dato corrupto/parcial que
    haria estallar el CAGR. Si pasa, devuelve None en vez de un numero falso."""
    if len(serie_eps) < years + 1:
        return None
    vals = [dp["val"] for dp in serie_eps if dp.get("val") is not None]
    if len(vals) < years + 1:
        return None
    inicio = serie_eps[-(years + 1)]["val"]
    fin = serie_eps[-1]["val"]
    if inicio is None or fin is None or inicio <= 0 or fin <= 0:
        return None
    mediana = sorted(vals)[len(vals) // 2]
    if mediana > 0 and inicio < 0.10 * mediana:
        return None  # anio base sospechoso -> no inventar un crecimiento
    return (fin / inicio) ** (1 / years) - 1


def equity_promedio_ttm(fin: dict) -> tuple[float | None, str | None]:
    """Equity PROMEDIO para el denominador del ROE (no el puntual). Promedia el
    equity del ultimo balance con el de ~1 anio antes, que es como lo hace
    Investing.com (ver docs/.../FORMULAS_RATIOS.md: 'ROE = NI_TTM / Equity_prom').
    Reduce el ruido en empresas con recompras donde el equity se mueve fuerte
    trimestre a trimestre. Si no hay un punto ~1 anio atras, usa el ultimo."""
    serie = get_serie(fin, "StockholdersEquity")
    if not serie:
        return None, None
    serie_ok = sorted((dp for dp in serie if dp.get("end") and dp.get("val") is not None),
                      key=lambda x: x["end"])
    if not serie_ok:
        return None, None
    actual = serie_ok[-1]
    end_actual = datetime.fromisoformat(actual["end"])
    previo = None
    for dp in reversed(serie_ok[:-1]):
        delta = (end_actual - datetime.fromisoformat(dp["end"])).days
        if 300 <= delta <= 430:  # ~1 anio antes
            previo = dp
            break
    if previo is None:
        return actual["val"], actual["end"]
    return (actual["val"] + previo["val"]) / 2, actual["end"]


def fecha_mas_reciente(*series: list[dict]) -> str | None:
    """Maximo 'end' entre varias series -- para detectar datos stale."""
    ends = [dp.get("end") for s in series for dp in s if dp.get("end")]
    return max(ends) if ends else None


def anios_desde(fecha_iso: str | None, hoy: datetime | None = None) -> float | None:
    if not fecha_iso:
        return None
    hoy = hoy or datetime.now()
    try:
        return (hoy - datetime.fromisoformat(fecha_iso)).days / 365.25
    except Exception:
        return None


# ============================================================
# CALCULO DE RATIOS POR EMPRESA (idem _research, sin cambios de formula)
# ============================================================

def calcular_ratios(fin: dict, precio_info: dict) -> dict:
    flags: list[str] = []  # banderas de calidad de datos (fix #2/#3/#5/#6)

    metric_rev, s_rev = get_serie_alt(
        fin, "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
    )
    revenue_ttm, _, _ = ttm_flujo(s_rev)

    # Fallback NetIncomeLoss -> ProfitLoss: documentado en
    # docs/screener/GUIA_SEC_EDGAR_PARA_DEVS.md#9 (ProfitLoss es el tag
    # ifrs-full equivalente, pero algunas empresas us-gaap con intereses
    # minoritarios -- ej. CAT, que consolida Caterpillar Financial Services --
    # tambien usan ProfitLoss como tag primario del income statement y dejan
    # NetIncomeLoss desactualizado o solo tageado en proxy statements (DEF 14A,
    # tabla Pay vs Performance) que no se ingestan aca a proposito.
    metric_ni, s_ni = get_serie_alt(fin, "NetIncomeLoss", "ProfitLoss")
    netinc_ttm, ni_end, ni_estrategia = ttm_flujo(s_ni)
    opinc_ttm, _, _ = ttm_flujo(get_serie(fin, "OperatingIncomeLoss"))
    cfo_ttm, _, _ = ttm_flujo(get_serie(fin, "NetCashProvidedByUsedInOperatingActivities"))

    metric_capex, s_capex = get_serie_alt(
        fin, "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
    )
    capex_ttm, _, _ = ttm_flujo(s_capex)

    metric_div, s_div = get_serie_alt(
        fin, "PaymentsOfDividendsCommonStock", "PaymentsOfDividends",
    )
    div_ttm, _, _ = ttm_flujo(s_div)

    # Fix #4 -- eleccion del tag de D&A para EBITDA. La regla NO puede ser "el
    # mas reciente" (rompia GE: elegia Depreciation estrecho 4,25B en vez del
    # comprensivo 9,29B) ni "prioridad estricta" (rompia INTC: elegia un
    # DepreciationAndAmortization mal tageado de 0,2B sobre el Depreciation real
    # de 9,43B). Regla robusta:
    #   1) si existe DepreciationDepletionAndAmortization (el mas comprensivo,
    #      incluye depletion + amortizacion de intangibles) -> usarlo.
    #   2) si no, elegir entre DepreciationAndAmortization y Depreciation el de
    #      MAYOR TTM (un tag diminuto es un mis-tag, no el D&A real).
    #   3) si el elegido es 'Depreciation' (solo PP&E), sumarle la
    #      AmortizationOfIntangibleAssets para no subestimar el EBITDA de
    #      empresas adquisitivas (ORCL/Cerner, IBM).
    da_dda, _, _ = ttm_flujo(get_serie(fin, "DepreciationDepletionAndAmortization"))
    da_da, _, _ = ttm_flujo(get_serie(fin, "DepreciationAndAmortization"))
    da_dep, _, _ = ttm_flujo(get_serie(fin, "Depreciation"))
    if da_dda is not None:
        metric_da, da_ttm, da_incluye_intangibles = "DepreciationDepletionAndAmortization", da_dda, True
    else:
        candidatos_da = [(m, v) for m, v in (("DepreciationAndAmortization", da_da),
                                             ("Depreciation", da_dep)) if v is not None]
        if candidatos_da:
            metric_da, da_ttm = max(candidatos_da, key=lambda x: x[1])
        else:
            metric_da, da_ttm = "", None
        da_incluye_intangibles = metric_da == "DepreciationAndAmortization"
    if metric_da == "Depreciation":
        amort_ttm, _, _ = ttm_flujo(get_serie(fin, "AmortizationOfIntangibleAssets"))
        if amort_ttm is not None:
            da_ttm = (da_ttm or 0) + amort_ttm
            da_incluye_intangibles = True
            flags.append("ebitda_da_mas_intangibles")

    diluted_shares_serie = get_serie(fin, "WeightedAverageNumberOfDilutedSharesOutstanding")
    basic_shares_serie = get_serie(fin, "WeightedAverageNumberOfSharesOutstandingBasic")
    diluted_shares, _ = ultimo_valor(diluted_shares_serie or basic_shares_serie)

    # Fix #2 -- validacion de ESCALA de shares. NMR tagea el weighted-avg de
    # acciones en una unidad equivocada (3,04e15, ~1e6 veces de mas) y SID con
    # un valor de 2009 fuera de escala -> EPS/PER quedan absurdos. Si el conteo
    # difiere >100x del CommonStockSharesOutstanding (control independiente del
    # balance), se descarta en vez de inventar un EPS roto.
    shares_outstanding, _ = ultimo_valor(get_serie(fin, "CommonStockSharesOutstanding"))
    if diluted_shares and shares_outstanding and shares_outstanding > 0:
        ratio = diluted_shares / shares_outstanding
        if ratio > 100 or ratio < 0.01:
            flags.append("shares_descartadas_escala")
            diluted_shares = None

    equity, _ = ultimo_valor(get_serie(fin, "StockholdersEquity"))
    cash, _ = ultimo_valor(get_serie(fin, "CashAndCashEquivalentsAtCarryingValue"))
    lt_debt, _ = ultimo_valor(get_serie(fin, "LongTermDebt"))
    if lt_debt is None:
        lt_debt, _ = ultimo_valor(get_serie(fin, "LongTermDebtNoncurrent"))

    lt_debt_curr, _ = ultimo_valor(get_serie(fin, "LongTermDebtCurrent"))
    st_debt, _ = ultimo_valor(get_serie(fin, "ShortTermBorrowings"))
    debt_curr, _ = ultimo_valor(get_serie(fin, "DebtCurrent"))

    componentes = [x for x in (lt_debt, lt_debt_curr, st_debt or debt_curr) if x is not None]
    deuda_total = sum(componentes) if componentes else None

    # Fix #3 -- deteccion de datos STALE. Foreign private issuers como TM
    # (Toyota) y VALE dejaron de filear us-gaap detallado: su ultimo
    # income statement es de 2012, pero el pipeline lo toma como si fuera el
    # "TTM" actual. Si el dato de NI/revenue tiene > 2 anios, se anulan los
    # ratios derivados (mejor NULL honesto que un ratio de hace una decada).
    # Se mide sobre el net income REALMENTE usado (ni_end): es lo que alimenta
    # PER/EPS/margen/ROE/payout. NMR, por ejemplo, tiene revenue reciente pero
    # su ultimo net income es de 2010 -> debe contar como stale igual.
    end_datos = ni_end or fecha_mas_reciente(s_ni, s_rev)
    antiguedad = anios_desde(end_datos)
    es_stale = antiguedad is not None and antiguedad > 2.0
    if es_stale:
        flags.append(f"stale_{end_datos}")
        netinc_ttm = revenue_ttm = opinc_ttm = cfo_ttm = None
        capex_ttm = div_ttm = da_ttm = None
        diluted_shares = equity = None

    ebitda_ttm = opinc_ttm + da_ttm if (opinc_ttm is not None and da_ttm is not None) else None

    precio = (precio_info or {}).get("last_price")

    eps_ttm = (netinc_ttm / diluted_shares) if (netinc_ttm and diluted_shares) else None
    per_ttm = (precio / eps_ttm) if (precio and eps_ttm and eps_ttm > 0) else None

    # Fix #6 -- si el "TTM" de net income salio de la estrategia C (ultimo anio
    # fiscal cerrado, no un TTM rodante), se marca: PER/EPS/margen/ROE/payout de
    # esa fila son FY, no TTM, y pueden divergir de Investing por items no
    # recurrentes en un trimestre reciente (caso MRK).
    ni_es_fy = (ni_estrategia == "C") and not es_stale
    if ni_es_fy:
        flags.append("ni_es_fy_no_ttm")

    year_high = (precio_info or {}).get("year_high")
    year_low = (precio_info or {}).get("year_low")
    dif_max = (precio / year_high - 1) if (precio and year_high) else None
    dif_min = (precio / year_low - 1) if (precio and year_low) else None

    deuda_ebitda_lp = (lt_debt / ebitda_ttm) if (lt_debt is not None and ebitda_ttm and ebitda_ttm > 0) else None
    deuda_ebitda_total = (deuda_total / ebitda_ttm) if (deuda_total is not None and ebitda_ttm and ebitda_ttm > 0) else None

    margen_neto = (netinc_ttm / revenue_ttm) if (netinc_ttm is not None and revenue_ttm) else None

    netinc_anual = serie_anual(s_ni)
    equity_anual = serie_anual(get_serie(fin, "StockholdersEquity"))
    roe_anual = []
    eq_por_year = {(dp.get("fy") or dp["end"][:4]): dp["val"] for dp in equity_anual if dp.get("val")}
    for dp in netinc_anual:
        y = dp.get("fy") or dp["end"][:4]
        eq = eq_por_year.get(y)
        if eq and eq > 0 and dp.get("val") is not None:
            roe_anual.append({"fy": y, "end": dp["end"], "val": dp["val"] / eq})
    roe_anual.sort(key=lambda x: x["end"])
    roe_cagr_5y = cagr(roe_anual, years=5)

    # Fix #5 -- ROE TTM con EQUITY PROMEDIO (no puntual), que es lo que usa
    # Investing.com (docs/.../FORMULAS_RATIOS.md). Reduce el ruido en empresas
    # con recompras. Ademas se marca 'roe_no_significativo' cuando el equity es
    # < 5% de los activos (ej. CL con equity casi cero por treasury stock): ahi
    # el ROE puede ser tecnicamente correcto pero no interpretable.
    equity_prom, _ = (None, None) if es_stale else equity_promedio_ttm(fin)
    roe_ttm = (netinc_ttm / equity_prom) if (netinc_ttm is not None and equity_prom and equity_prom > 0) else None
    assets, _ = ultimo_valor(get_serie(fin, "Assets"))
    if roe_ttm is not None and equity_prom is not None and assets and assets > 0:
        if equity_prom < 0.05 * assets:
            flags.append("roe_no_significativo")

    # Fix #7 -- crecimiento EPS con serie anual LIMPIA (solo anios fiscales
    # completos) y guarda de anio base, para no inflar el CAGR con un dato
    # base corrupto (ej. CSCO base 0,02 -> +173% falso).
    cagr_eps_5y = None if es_stale else cagr_eps_robusto(serie_anual_eps_limpia(fin), years=5)

    fcf_ttm = (cfo_ttm - capex_ttm) if (cfo_ttm is not None and capex_ttm is not None) else None

    ce_a = (equity + lt_debt) if (equity is not None and lt_debt is not None) else None
    ce_b = (equity + deuda_total - cash) if (equity is not None and deuda_total is not None and cash is not None) else None
    fcfonce_a = (fcf_ttm / ce_a) if (fcf_ttm is not None and ce_a) else None
    fcfonce_b = (fcf_ttm / ce_b) if (fcf_ttm is not None and ce_b) else None

    payout = (div_ttm / netinc_ttm) if (div_ttm is not None and netinc_ttm and netinc_ttm > 0) else None

    return {
        "precio_usd": precio,
        "currency": (precio_info or {}).get("currency"),
        "exchange": (precio_info or {}).get("exchange"),
        "per_ttm": per_ttm,
        "year_high": year_high,
        "dif_max_52w": dif_max,
        "year_low": year_low,
        "dif_min_52w": dif_min,
        "deuda_lp_sobre_ebitda": deuda_ebitda_lp,
        "deuda_total_sobre_ebitda": deuda_ebitda_total,
        "eps_ttm_diluted": eps_ttm,
        "cagr_eps_5y": cagr_eps_5y,
        "margen_neto_ttm": margen_neto,
        "roe_cagr_5y": roe_cagr_5y,
        "roe_ttm": roe_ttm,
        "fcfonce_equity_lp": fcfonce_a,
        "fcfonce_neto_caja": fcfonce_b,
        "payout_ttm": payout,
        # debug / calidad de datos
        "_esquema": fin.get("esquema"),
        "_revenue_ttm": revenue_ttm,
        "_netincome_ttm": netinc_ttm,
        "_ebitda_ttm": ebitda_ttm,
        "_fcf_ttm": fcf_ttm,
        "_diluted_shares": diluted_shares,
        "_equity": equity,
        "_equity_prom": equity_prom,
        "_lt_debt": lt_debt,
        "_deuda_total": deuda_total,
        "_metric_revenue": metric_rev,
        "_metric_da": metric_da,
        "_da_incluye_intangibles": da_incluye_intangibles,
        "_ni_estrategia": ni_estrategia,
        "_ni_es_fy": ni_es_fy,
        "_stale": es_stale,
        "_end_datos": end_datos,
        "_flags": ";".join(flags),
    }


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 60)
    print("  PASO 3 -- Calcular ratios fundamentales")
    print("=" * 60)

    with open(PRECIOS_F, encoding="utf-8") as f:
        precios = json.load(f)["precios"]
    print(f"\n  Precios cargados: {len(precios)} tickers")

    with open(IN_CON_CIK, encoding="utf-8") as f:
        tickers_cik = list(csv.DictReader(f))
    print(f"  Tickers con CIK: {len(tickers_cik)}")

    filas = []
    sin_financials = 0
    sin_precio = 0

    for row in tickers_cik:
        ticker = row["ticker"]
        cik = row["cik"]
        nombre = row["nombre_sec"]

        fin = cargar_financials(cik)
        if not fin or "error" in fin:
            sin_financials += 1
            filas.append({
                "ticker": ticker, "cik": cik, "nombre": nombre,
                "_error": (fin or {}).get("error", "sin_datos_descargados"),
            })
            continue

        precio_info = precios.get(ticker) or {}
        if not precio_info.get("last_price"):
            sin_precio += 1

        ratios = calcular_ratios(fin, precio_info)

        filas.append({
            "ticker": ticker,
            "cik": cik,
            "nombre": nombre,
            **ratios,
        })

    print(f"\n  Filas generadas         : {len(filas)}")
    print(f"  Sin financials (error)  : {sin_financials}")
    print(f"  Sin precio (con ratios) : {sin_precio}")

    if filas:
        headers = sorted({k for fila in filas for k in fila.keys()})
        # ticker/cik/nombre primero, el resto alfabetico
        headers = ["ticker", "cik", "nombre"] + [h for h in headers if h not in ("ticker", "cik", "nombre")]
        with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers, restval="")
            w.writeheader()
            w.writerows(filas)
        print(f"\n  OK {CSV_OUT}")

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "count": len(filas),
            "filas": filas,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"  OK {JSON_OUT}")

    print("\nPaso 3 completo. Proximo paso -> 04_generar_reporte.py")


if __name__ == "__main__":
    main()
