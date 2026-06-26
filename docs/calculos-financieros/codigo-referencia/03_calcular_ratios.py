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


def ttm_flujo(serie: list[dict]) -> tuple[float | None, str | None]:
    """
    TTM para una metrica de flujo. Estrategias en orden de preferencia:
    A) 4 trimestres standalone (~90d) consecutivos -> sumar.
    B) Annual + YTD_actual - YTD_anterior (canonico para 10-Q acumulado).
    C) Ultimo anual solo (~365d).
    """
    if not serie:
        return None, None

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
            return sum(q["val"] for q in candidatos), candidatos[0]["end"]

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
                return ttm, ytd_actual["end"]

    # --- Estrategia C: ultimo anual solo ---
    if annuals:
        return annuals[0]["val"], annuals[0]["end"]

    return None, None


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
# CALCULO DE RATIOS POR EMPRESA (idem _research, sin cambios de formula)
# ============================================================

def calcular_ratios(fin: dict, precio_info: dict) -> dict:
    metric_rev, s_rev = get_serie_alt(
        fin, "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
    )
    revenue_ttm, _ = ttm_flujo(s_rev)

    # Fallback NetIncomeLoss -> ProfitLoss: documentado en
    # docs/screener/GUIA_SEC_EDGAR_PARA_DEVS.md#9 (ProfitLoss es el tag
    # ifrs-full equivalente, pero algunas empresas us-gaap con intereses
    # minoritarios -- ej. CAT, que consolida Caterpillar Financial Services --
    # tambien usan ProfitLoss como tag primario del income statement y dejan
    # NetIncomeLoss desactualizado o solo tageado en proxy statements (DEF 14A,
    # tabla Pay vs Performance) que no se ingestan aca a proposito.
    metric_ni, s_ni = get_serie_alt(fin, "NetIncomeLoss", "ProfitLoss")
    netinc_ttm, _ = ttm_flujo(s_ni)
    opinc_ttm, _ = ttm_flujo(get_serie(fin, "OperatingIncomeLoss"))
    cfo_ttm, _ = ttm_flujo(get_serie(fin, "NetCashProvidedByUsedInOperatingActivities"))

    metric_capex, s_capex = get_serie_alt(
        fin, "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
    )
    capex_ttm, _ = ttm_flujo(s_capex)

    metric_div, s_div = get_serie_alt(
        fin, "PaymentsOfDividendsCommonStock", "PaymentsOfDividends",
    )
    div_ttm, _ = ttm_flujo(s_div)

    metric_da, s_da = get_serie_alt(
        fin, "DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation",
    )
    da_ttm, _ = ttm_flujo(s_da)

    diluted_shares_serie = get_serie(fin, "WeightedAverageNumberOfDilutedSharesOutstanding")
    basic_shares_serie = get_serie(fin, "WeightedAverageNumberOfSharesOutstandingBasic")
    diluted_shares, _ = ultimo_valor(diluted_shares_serie or basic_shares_serie)

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

    ebitda_ttm = opinc_ttm + da_ttm if (opinc_ttm is not None and da_ttm is not None) else None

    precio = (precio_info or {}).get("last_price")

    eps_ttm = (netinc_ttm / diluted_shares) if (netinc_ttm and diluted_shares) else None
    per_ttm = (precio / eps_ttm) if (precio and eps_ttm and eps_ttm > 0) else None

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

    # ROE TTM simple (NetIncome_TTM / Equity) -- esto es lo que Investing.com
    # muestra como "Return on Equity TTM". NO confundir con roe_cagr_5y (que
    # es la tasa de crecimiento del ROE en 5 anios, una magnitud distinta).
    # Formula documentada en docs/screener/GUIA_RATIOS_EDGAR_vs_INVESTING.md.
    roe_ttm = (netinc_ttm / equity) if (netinc_ttm is not None and equity and equity > 0) else None

    eps_anual = []
    eps_serie = get_serie(fin, "EarningsPerShareDiluted")
    for dp in serie_anual(eps_serie):
        if dp.get("val") is not None:
            eps_anual.append(dp)
    cagr_eps_5y = cagr(eps_anual, years=5)

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
        "_lt_debt": lt_debt,
        "_deuda_total": deuda_total,
        "_metric_revenue": metric_rev,
        "_metric_da": metric_da,
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
