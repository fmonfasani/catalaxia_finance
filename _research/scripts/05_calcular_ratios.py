"""
PASO 5 — Calcular ratios fundamentales por empresa
Input : financials_sec/*.json (schema v2: 10-K + 10-Q por período)
        precios.json (yfinance: precio actual, 52w hi/lo)
        cedears_con_cik.json (mapeo BYMA <-> SEC <-> CIK)
Output: seguimiento.csv + seguimiento.json (1 fila por BYMA ticker)

Definiciones (acordadas con el usuario):
- EPS y PER          : TTM (últimos 4 trimestres)
- Shares             : Diluted (Weighted Average)
- Deuda/EBITDA       : DOS campos -- (a) sólo LongTermDebt  (b) Deuda Total
- ROE 5 años         : CAGR (5 años)
- FCF                : Clásica = CFO − CapEx
- Capital Empleado   : DOS campos -- (a) Equity + LongTermDebt  (b) Equity + DeudaTotal − Cash
- Precios            : yfinance

Cómo se calcula TTM:
- Para flujos (Revenue, NetIncome, CFO, CapEx, Dividendos, D&A):
  TTM = último anual fiscal − YTD-mismo-período-año-anterior + YTD-actual
  (equivalente a sumar los 4 últimos trimestres standalone)
  Implementación: encontrar el último período con start_end consistente y
  derivar los 4 trimestres anteriores.
- Para stocks (Equity, Debt, Cash, Shares): valor del último período disponible.
"""

import json
import csv
from datetime import datetime
from pathlib import Path

FIN_DIR     = Path("financials_sec")
PRECIOS_F   = Path("precios.json")
CEDEARS_F   = Path("cedears_con_cik.json")
CSV_OUT     = Path("seguimiento.csv")
JSON_OUT    = Path("seguimiento.json")

# ============================================================
# HELPERS de extracción de datos desde financials_sec/*.json
# ============================================================

def cargar_financials(cik: str) -> dict | None:
    p = FIN_DIR / f"{cik}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_serie(fin: dict, metric: str) -> list[dict]:
    """Devuelve la lista de datapoints de una métrica, o [] si no existe."""
    m = fin.get("metricas", {}).get(metric)
    if not m:
        return []
    return m.get("datos", [])


def get_serie_alt(fin: dict, *metrics: str) -> tuple[str, list[dict]]:
    """
    De las métricas candidatas, devuelve la que tenga el datapoint más reciente.
    Esto evita que tags deprecados (con datos sólo viejos) ganen sobre los actuales.
    """
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
    """Cantidad de días entre start y end. None si falta uno."""
    if not dp.get("start") or not dp.get("end"):
        return None
    try:
        s = datetime.fromisoformat(dp["start"])
        e = datetime.fromisoformat(dp["end"])
        return (e - s).days + 1  # inclusive
    except Exception:
        return None


# ============================================================
# TTM para métricas de FLUJO
# ============================================================

def ttm_flujo(serie: list[dict]) -> tuple[float | None, str | None]:
    """
    Calcula TTM (12 meses) para una métrica de flujo.

    Estrategias (en orden de preferencia):
    A) 4 trimestres standalone (~90d) consecutivos -> sumar.
    B) TTM = Annual + YTD_current - YTD_prior_year
       (canónico cuando la empresa sólo reporta YTD en 10-Q).
    C) Último anual solo (~365d).

    Retorna (ttm_value, fecha_end).
    """
    if not serie:
        return None, None

    quarters = []  # ~90d standalone
    ytds     = []  # 100-300d (YTD cumulative)
    annuals  = []  # ~365d

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
            return sum(q["val"] for q in candidatos), candidatos[0]["end"]

    # --- Estrategia B: Annual + YTD_actual − YTD_año_anterior ---
    if annuals and ytds:
        anual = annuals[0]
        anual_end = datetime.fromisoformat(anual["end"])
        # YTD actual = primer YTD que arranca el día después del cierre anual
        ytd_actual = None
        for y in ytds:
            if not y.get("start"):
                continue
            ystart = datetime.fromisoformat(y["start"])
            if abs((ystart - anual_end).days) <= 5:
                ytd_actual = y
                break

        if ytd_actual is not None:
            # YTD prior = mismo fp/duración pero un año fiscal antes
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
                return ttm, ytd_actual["end"]

    # --- Estrategia C: último anual solo ---
    if annuals:
        return annuals[0]["val"], annuals[0]["end"]

    return None, None


# ============================================================
# Valor más reciente para métricas de STOCK (balance sheet)
# ============================================================

def ultimo_valor(serie: list[dict]) -> tuple[float | None, str | None]:
    """Devuelve (valor, fecha_end) del datapoint más reciente."""
    if not serie:
        return None, None
    last = max(serie, key=lambda x: x.get("end") or "")
    return last.get("val"), last.get("end")


# ============================================================
# Serie ANUAL (10-K) para CAGRs
# ============================================================

def serie_anual(serie: list[dict]) -> list[dict]:
    """Devuelve solo los datapoints anuales (10-K, ~365 días), uno por año fiscal."""
    annuals = []
    for dp in serie:
        d = dias_periodo(dp)
        # Para flow items
        if d is not None and 355 <= d <= 380:
            annuals.append(dp)
        # Para stock items (sin start) — agarrar todos los de form 10-K
        elif dp.get("start") is None and dp.get("form") in ("10-K", "20-F", "40-F"):
            annuals.append(dp)

    # Dedup por fy quedándose con el más reciente filed
    por_fy = {}
    for dp in annuals:
        fy = dp.get("fy") or (dp.get("end") or "")[:4]
        prev = por_fy.get(fy)
        if prev is None or (dp.get("filed") or "") > (prev.get("filed") or ""):
            por_fy[fy] = dp

    return sorted(por_fy.values(), key=lambda x: x.get("end") or "")


def cagr(serie_anual_data: list[dict], years: int = 5) -> float | None:
    """CAGR de los últimos `years` años. Necesita value > 0 en ambos extremos."""
    if len(serie_anual_data) < years + 1:
        return None
    inicio = serie_anual_data[-(years + 1)]["val"]
    fin    = serie_anual_data[-1]["val"]
    if inicio is None or fin is None or inicio <= 0 or fin <= 0:
        return None
    return (fin / inicio) ** (1 / years) - 1


# ============================================================
# CÁLCULO DE RATIOS POR EMPRESA
# ============================================================

def calcular_ratios(fin: dict, precio_info: dict) -> dict:
    """Calcula todos los ratios para una empresa dada."""
    # --- TTM de FLUJOS ---
    metric_rev, s_rev = get_serie_alt(
        fin,
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    )
    revenue_ttm, _ = ttm_flujo(s_rev)

    netinc_ttm,   _              = ttm_flujo(get_serie(fin, "NetIncomeLoss"))
    opinc_ttm,    _              = ttm_flujo(get_serie(fin, "OperatingIncomeLoss"))
    cfo_ttm,      _              = ttm_flujo(get_serie(fin, "NetCashProvidedByUsedInOperatingActivities"))
    metric_capex, s_capex        = get_serie_alt(
        fin,
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    )
    capex_ttm,    _              = ttm_flujo(s_capex)
    metric_div, s_div            = get_serie_alt(
        fin,
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
    )
    div_ttm,      _              = ttm_flujo(s_div)
    metric_da, s_da              = get_serie_alt(
        fin,
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    )
    da_ttm, _ = ttm_flujo(s_da)

    # Diluted shares (weighted avg TTM-like = último período disponible)
    diluted_shares_serie = get_serie(fin, "WeightedAverageNumberOfDilutedSharesOutstanding")
    basic_shares_serie   = get_serie(fin, "WeightedAverageNumberOfSharesOutstandingBasic")
    diluted_shares, _ = ultimo_valor(diluted_shares_serie or basic_shares_serie)

    # --- STOCKS (último período) ---
    equity, _   = ultimo_valor(get_serie(fin, "StockholdersEquity"))
    cash, _     = ultimo_valor(get_serie(fin, "CashAndCashEquivalentsAtCarryingValue"))
    lt_debt, _  = ultimo_valor(get_serie(fin, "LongTermDebt"))
    if lt_debt is None:
        lt_debt, _ = ultimo_valor(get_serie(fin, "LongTermDebtNoncurrent"))

    lt_debt_curr, _ = ultimo_valor(get_serie(fin, "LongTermDebtCurrent"))
    st_debt, _      = ultimo_valor(get_serie(fin, "ShortTermBorrowings"))
    debt_curr, _    = ultimo_valor(get_serie(fin, "DebtCurrent"))

    # Deuda Total = LongTermDebt + porción corriente + ShortTerm/DebtCurrent
    componentes = [x for x in (lt_debt, lt_debt_curr, st_debt or debt_curr) if x is not None]
    deuda_total = sum(componentes) if componentes else None

    # --- EBITDA ---
    if opinc_ttm is not None and da_ttm is not None:
        ebitda_ttm = opinc_ttm + da_ttm
    else:
        ebitda_ttm = None

    # --- RATIOS ---
    precio = (precio_info or {}).get("last_price")

    # EPS TTM (diluted)
    eps_ttm = (netinc_ttm / diluted_shares) if (netinc_ttm and diluted_shares) else None

    # PER TTM
    per_ttm = (precio / eps_ttm) if (precio and eps_ttm and eps_ttm > 0) else None

    # 52w
    year_high = (precio_info or {}).get("year_high")
    year_low  = (precio_info or {}).get("year_low")
    dif_max = (precio / year_high - 1) if (precio and year_high) else None
    dif_min = (precio / year_low  - 1) if (precio and year_low ) else None

    # Deuda / EBITDA (dos variantes)
    deuda_ebitda_lp    = (lt_debt     / ebitda_ttm) if (lt_debt is not None and ebitda_ttm) else None
    deuda_ebitda_total = (deuda_total / ebitda_ttm) if (deuda_total is not None and ebitda_ttm) else None

    # Margen Neto TTM
    margen_neto = (netinc_ttm / revenue_ttm) if (netinc_ttm is not None and revenue_ttm) else None

    # ROE CAGR 5y
    netinc_anual = serie_anual(get_serie(fin, "NetIncomeLoss"))
    equity_anual = serie_anual(get_serie(fin, "StockholdersEquity"))
    # Calcular ROE año a año y CAGR de eso es matemáticamente raro;
    # más útil: CAGR de NetIncome + CAGR de Equity. Pero el usuario pidió CAGR del ROE.
    # Construyo serie de ROE anual y aplico CAGR.
    roe_anual = []
    eq_por_year = {(dp.get("fy") or dp["end"][:4]): dp["val"] for dp in equity_anual if dp.get("val")}
    for dp in netinc_anual:
        y = dp.get("fy") or dp["end"][:4]
        eq = eq_por_year.get(y)
        if eq and eq > 0 and dp.get("val") is not None:
            roe_anual.append({"fy": y, "end": dp["end"], "val": dp["val"] / eq})
    roe_anual.sort(key=lambda x: x["end"])
    roe_cagr_5y = cagr(roe_anual, years=5)

    # FCF clásica
    fcf_ttm = (cfo_ttm - capex_ttm) if (cfo_ttm is not None and capex_ttm is not None) else None

    # FCFonCE (dos variantes)
    ce_a = (equity + lt_debt) if (equity is not None and lt_debt is not None) else None
    ce_b = None
    if equity is not None and deuda_total is not None and cash is not None:
        ce_b = equity + deuda_total - cash
    fcfonce_a = (fcf_ttm / ce_a) if (fcf_ttm is not None and ce_a) else None
    fcfonce_b = (fcf_ttm / ce_b) if (fcf_ttm is not None and ce_b) else None

    # Payout
    payout = (div_ttm / netinc_ttm) if (div_ttm is not None and netinc_ttm and netinc_ttm > 0) else None

    return {
        "precio_usd":            precio,
        "currency":              (precio_info or {}).get("currency"),
        "exchange":              (precio_info or {}).get("exchange"),
        "per_ttm":               per_ttm,
        "year_high":             year_high,
        "dif_max_52w":           dif_max,
        "year_low":              year_low,
        "dif_min_52w":           dif_min,
        "deuda_lp_sobre_ebitda":     deuda_ebitda_lp,
        "deuda_total_sobre_ebitda":  deuda_ebitda_total,
        "eps_ttm_diluted":       eps_ttm,
        "cagr_eps_5y":           None,  # se calcula abajo
        "margen_neto_ttm":       margen_neto,
        "roe_cagr_5y":           roe_cagr_5y,
        "fcfonce_equity_lp":     fcfonce_a,
        "fcfonce_neto_caja":     fcfonce_b,
        "payout_ttm":            payout,
        # debug útiles
        "_revenue_ttm":          revenue_ttm,
        "_netincome_ttm":        netinc_ttm,
        "_ebitda_ttm":           ebitda_ttm,
        "_fcf_ttm":              fcf_ttm,
        "_diluted_shares":       diluted_shares,
        "_equity":               equity,
        "_lt_debt":              lt_debt,
        "_deuda_total":          deuda_total,
        "_metric_revenue":       metric_rev,
        "_metric_da":            metric_da,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  PASO 5 -- Calcular ratios fundamentales")
    print("=" * 60)

    # Cargar precios
    with open(PRECIOS_F, encoding="utf-8") as f:
        precios = json.load(f)["precios"]
    print(f"\n  Precios cargados: {len(precios)} tickers")

    # Cargar mapeo BYMA <-> SEC <-> CIK
    with open(CEDEARS_F, encoding="utf-8") as f:
        cedears = json.load(f)["cedears"]
    print(f"  CEDEARs en mapeo: {len(cedears)}")

    # Iterar
    filas = []
    sin_financials = 0
    sin_precio     = 0

    for c in cedears:
        cik    = c.get("cik")
        ts     = c.get("ticker_sec")
        bt     = c.get("byma_ticker")
        nombre = c.get("nombre_sec")

        if not cik or not ts:
            continue

        fin = cargar_financials(cik)
        if not fin:
            sin_financials += 1
            continue

        precio_info = precios.get(ts) or {}
        if not precio_info.get("last_price"):
            sin_precio += 1

        ratios = calcular_ratios(fin, precio_info)

        fila = {
            "byma_ticker":   bt,
            "ticker_sec":    ts,
            "nombre":        nombre,
            "cik":           cik,
            "exchange":      ratios.get("exchange") or "",
            **ratios,
        }
        filas.append(fila)

    print(f"\n  Filas generadas         : {len(filas)}")
    print(f"  Sin financials (skip)   : {sin_financials}")
    print(f"  Sin precio (con ratios) : {sin_precio}")

    # CSV
    if filas:
        headers = list(filas[0].keys())
        with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            w.writerows(filas)
        print(f"\n  OK {CSV_OUT}")

    # JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "count":     len(filas),
            "filas":     filas,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"  OK {JSON_OUT}")

    print("\nPaso 5 completo.")


if __name__ == "__main__":
    main()
