# -*- coding: utf-8 -*-
"""
Capa de ratios: lee data/screener.db (tabla facts, conceptos canonicos) y
calcula los ratios EDGAR-only (sin precio) para todas las empresas con facts.

Reusa la logica robusta de TTM (estrategia B generalizada al caso Q1) y de
CAGR ya validada en 03_calcular_ratios.py. Unifica GAAP e IFRS porque opera
sobre los conceptos canonicos (NetIncome, Revenue, Equity...), no sobre los
tags crudos.

Ratios con PRECIO (PER, P/B, P/S, EV/EBITDA, yields) quedan para la capa de FX
+ precios (yfinance), que es el proximo paso.

Salida: tabla `ratios` en la misma base.
"""
from __future__ import annotations
import sqlite3, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "screener.db"

# Prioridad de tags por concepto (para desambiguar cuando varios tags mapean al
# mismo concepto canonico, ej. NetIncome <- ProfitLossAttributableToOwnersOfParent
# antes que ProfitLoss). Orden = preferencia.
PRIORIDAD = {
 "Revenue": ["Revenues","Revenue","RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","RevenueFromSaleOfGoods"],
 "NetIncome": ["NetIncomeLoss","ProfitLossAttributableToOwnersOfParent","ProfitLoss"],
 "OperatingIncome": ["OperatingIncomeLoss","ProfitLossFromOperatingActivities"],
 "GrossProfit": ["GrossProfit"],
 "DA": ["DepreciationDepletionAndAmortization","DepreciationAndAmortisationExpense","DepreciationAndAmortization","AdjustmentsForDepreciationAndAmortisationExpense","Depreciation"],
 "Equity": ["StockholdersEquity","EquityAttributableToOwnersOfParent","Equity"],
 "Assets": ["Assets"],
 "AssetsCurrent": ["AssetsCurrent","CurrentAssets"],
 "Liabilities": ["Liabilities"],
 "LiabilitiesCurrent": ["LiabilitiesCurrent","CurrentLiabilities"],
 "Cash": ["CashAndCashEquivalentsAtCarryingValue","CashAndCashEquivalents"],
 "Inventory": ["InventoryNet","Inventories"],
 "Receivables": ["AccountsReceivableNetCurrent","TradeAndOtherCurrentReceivables","CurrentTradeReceivables"],
 "Debt": ["LongTermDebt","LongTermDebtNoncurrent","Borrowings","LongtermBorrowings"],
 "CFO": ["NetCashProvidedByUsedInOperatingActivities","CashFlowsFromUsedInOperatingActivities"],
 "CapEx": ["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireProductiveAssets","PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
 "Dividends": ["PaymentsOfDividendsCommonStock","DividendsPaidClassifiedAsFinancingActivities","PaymentsOfDividends","DividendsPaid"],
 "EPS_diluted": ["EarningsPerShareDiluted","DilutedEarningsLossPerShare"],
 "Shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding","AdjustedWeightedAverageShares","WeightedAverageShares"],
 "SharesOutstanding": ["CommonStockSharesOutstanding","EntityCommonStockSharesOutstanding","NumberOfSharesOutstanding"],
}
CUTOFF_CAGR = (datetime.now(timezone.utc) - timedelta(days=365*7)).date().isoformat()


# ---------- helpers de series (operan sobre dicts {start,end,val,fy,fp,form,filed}) ----------
def dias(dp):
    if not dp["start"] or not dp["end"]: return None
    try: return (datetime.fromisoformat(dp["end"]) - datetime.fromisoformat(dp["start"])).days + 1
    except: return None


def ttm_flujo(serie):
    """TTM rodante: A) 4 Q consecutivos; B) Anual + parcial_FY_nuevo - mismo_parcial_anterior
    (acepta Q1); C) ultimo anual. Devuelve (valor, estrategia)."""
    if not serie: return None, None
    quarters = [d for d in serie if dias(d) and 85 <= dias(d) <= 100]
    annuals = [d for d in serie if dias(d) and 355 <= dias(d) <= 380]
    quarters.sort(key=lambda x: x["end"], reverse=True)
    annuals.sort(key=lambda x: x["end"], reverse=True)
    # A
    if len(quarters) >= 4:
        c = quarters[:4]; asc = sorted(c, key=lambda x: x["end"]); ok = True
        for i in range(1,4):
            gap = (datetime.fromisoformat(asc[i]["start"]) - datetime.fromisoformat(asc[i-1]["end"])).days
            if gap < -5 or gap > 5: ok = False; break
        if ok: return sum(q["val"] for q in c), "A"
    # B generalizada
    if annuals:
        an = annuals[0]; an_end = datetime.fromisoformat(an["end"])
        parciales = []
        for d in serie:
            if not d["start"]: continue
            dd = dias(d)
            if dd is None or dd > 300: continue
            if abs((datetime.fromisoformat(d["start"]) - an_end).days) <= 7:
                parciales.append(d)
        if parciales:
            pa = max(parciales, key=lambda x: x["end"]); pa_end = datetime.fromisoformat(pa["end"]); pa_d = dias(pa)
            prior = None
            for d in serie:
                if d is pa or not d["start"]: continue
                dd = dias(d)
                if dd is None: continue
                dy = (pa_end - datetime.fromisoformat(d["end"])).days
                if 350 <= dy <= 380 and abs(dd - pa_d) <= 7: prior = d; break
            if prior is not None:
                return an["val"] + pa["val"] - prior["val"], "B"
    # C
    if annuals: return annuals[0]["val"], "C"
    return None, None


def ultimo(serie):
    s = [d for d in serie if d["val"] is not None and d["end"]]
    return max(s, key=lambda x: x["end"])["val"] if s else None


def equity_prom(serie):
    s = sorted([d for d in serie if d["val"] is not None and d["end"]], key=lambda x: x["end"])
    if not s: return None
    act = s[-1]; act_end = datetime.fromisoformat(act["end"]); prev = None
    for d in reversed(s[:-1]):
        if 300 <= (act_end - datetime.fromisoformat(d["end"])).days <= 430: prev = d; break
    return (act["val"] + prev["val"])/2 if prev else act["val"]


def serie_anual(serie):
    an = [d for d in serie if dias(d) and 355 <= dias(d) <= 380 and d["val"] is not None]
    por_end = {}
    for d in an:
        k = d["end"]
        if k not in por_end or (d.get("filed") or "") > (por_end[k].get("filed") or ""): por_end[k] = d
    return sorted(por_end.values(), key=lambda x: x["end"])


def cagr(serie_an, years=5):
    if len(serie_an) < years+1: return None
    ini = serie_an[-(years+1)]["val"]; fin = serie_an[-1]["val"]
    if ini is None or fin is None or ini <= 0 or fin <= 0: return None
    vals = [d["val"] for d in serie_an]
    med = sorted(vals)[len(vals)//2]
    if med > 0 and ini < 0.10*med: return None
    return (fin/ini)**(1/years) - 1


def div(a, b):
    return a/b if (a is not None and b not in (None,0)) else None


# ---------- por empresa ----------
def conceptos_de(cur, cik):
    """Devuelve {concepto: serie} eligiendo el tag de mayor prioridad por concepto."""
    rows = cur.execute("""SELECT concepto, tag, period_start, period_end, val, fy, fp, form, filed
                          FROM facts WHERE cik=? AND concepto IS NOT NULL""", (cik,)).fetchall()
    por_concepto_tag = {}
    for c, tag, s, e, v, fy, fp, form, filed in rows:
        por_concepto_tag.setdefault((c, tag), []).append(
            {"start": s, "end": e, "val": v, "fy": fy, "fp": fp, "form": form, "filed": filed})
    out = {}
    for concepto, prio in PRIORIDAD.items():
        tags_presentes = {tag for (c, tag) in por_concepto_tag if c == concepto}
        elegido = next((t for t in prio if t in tags_presentes), None)
        if elegido is None and tags_presentes:
            elegido = next(iter(tags_presentes))
        out[concepto] = por_concepto_tag.get((concepto, elegido), []) if elegido else []
    return out


def calcular(cur, cik):
    C = conceptos_de(cur, cik)
    rev, estr = ttm_flujo(C["Revenue"])
    ni, ni_estr = ttm_flujo(C["NetIncome"])
    opinc, _ = ttm_flujo(C["OperatingIncome"])
    gp, _ = ttm_flujo(C["GrossProfit"])
    da, _ = ttm_flujo(C["DA"])
    cfo, _ = ttm_flujo(C["CFO"])
    capex, _ = ttm_flujo(C["CapEx"])
    divs, _ = ttm_flujo(C["Dividends"])

    equity = equity_prom(C["Equity"]); assets = ultimo(C["Assets"]); cash = ultimo(C["Cash"])
    debt = ultimo(C["Debt"]); inv = ultimo(C["Inventory"]); recv = ultimo(C["Receivables"])
    ac = ultimo(C["AssetsCurrent"]); lc = ultimo(C["LiabilitiesCurrent"])
    shares = ultimo(C["Shares_diluted"]); sh_out = ultimo(C["SharesOutstanding"])
    eps_rep_an = serie_anual(C["EPS_diluted"])
    eps_anual = eps_rep_an[-1]["val"] if eps_rep_an else None

    ebitda = (opinc + da) if (opinc is not None and da is not None) else None
    fcf = (cfo - capex) if (cfo is not None and capex is not None) else None
    cogs = (rev - gp) if (rev is not None and gp is not None) else None
    deuda_neta = (debt - cash) if (debt is not None and cash is not None) else None
    eps_ttm = div(ni, shares)

    r = {
        "_revenue_ttm": rev, "_netincome_ttm": ni, "_ebitda_ttm": ebitda, "_fcf_ttm": fcf,
        "_equity": equity, "_assets": assets, "_deuda": debt,
        "margen_bruto": div(gp, rev), "margen_operativo": div(opinc, rev),
        "margen_ebitda": div(ebitda, rev), "margen_neto": div(ni, rev),
        "roe": div(ni, equity), "roa": div(ni, assets),
        "roce": div(opinc, (equity + debt)) if (equity is not None and debt is not None) else None,
        "deuda_equity": div(debt, equity), "deuda_ebitda": div(debt, ebitda) if (ebitda and ebitda > 0) else None,
        "deuda_neta_ebitda": div(deuda_neta, ebitda) if (ebitda and ebitda > 0) else None,
        "current_ratio": div(ac, lc), "quick_ratio": div((ac - inv) if (ac is not None and inv is not None) else None, lc),
        "asset_turnover": div(rev, assets), "inventory_turnover": div(cogs, inv) if (cogs and inv) else None,
        "dso": div(recv * 365, rev) if (recv is not None and rev) else None,
        "fcf_margin": div(fcf, rev), "capex_revenue": div(capex, rev),
        "earnings_quality": div(cfo, ni) if (ni and ni > 0) else None,
        "payout": div(divs, ni) if (ni and ni > 0) else None,
        "fcf_payout": div(divs, fcf) if (fcf and fcf > 0) else None,
        "eps_ttm": eps_ttm, "eps_anual": eps_anual, "bvps": div(equity, sh_out),
        "cagr_revenue_5y": cagr(serie_anual(C["Revenue"])),
        "cagr_eps_5y": cagr(eps_rep_an),
        "cagr_ni_5y": cagr(serie_anual(C["NetIncome"])),
        "cagr_equity_5y": cagr(serie_anual(C["Equity"])),
        "_ni_estrategia": ni_estr,
    }
    return r


def main():
    con = sqlite3.connect(DB, timeout=60); con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    ciks = [r[0] for r in cur.execute("SELECT cik FROM empresas WHERE fecha_facts IS NOT NULL")]
    print(f"Calculando ratios para {len(ciks)} empresas con facts...")

    # tabla ratios
    cols_ratio = ["margen_bruto","margen_operativo","margen_ebitda","margen_neto","roe","roa","roce",
        "deuda_equity","deuda_ebitda","deuda_neta_ebitda","current_ratio","quick_ratio",
        "asset_turnover","inventory_turnover","dso","fcf_margin","capex_revenue","earnings_quality",
        "payout","fcf_payout","eps_ttm","eps_anual","bvps","cagr_revenue_5y","cagr_eps_5y","cagr_ni_5y","cagr_equity_5y"]
    cols_dbg = ["_revenue_ttm","_netincome_ttm","_ebitda_ttm","_fcf_ttm","_equity","_assets","_deuda","_ni_estrategia"]
    con.execute("DROP TABLE IF EXISTS ratios")
    defcols = ", ".join(f'"{c}" REAL' for c in cols_ratio + [c for c in cols_dbg if c != "_ni_estrategia"])
    con.execute(f"""CREATE TABLE ratios (cik TEXT PRIMARY KEY, ticker TEXT, nombre TEXT, esquema TEXT,
        moneda TEXT, sector_gics TEXT, grupo TEXT, {defcols}, ni_estrategia TEXT, fecha TEXT)""")

    meta = {r[0]: r[1:] for r in cur.execute("SELECT cik,ticker_ppal,nombre,esquema,moneda,sector_gics,grupo FROM empresas")}
    n_ok = 0
    fecha = datetime.now(timezone.utc).isoformat()
    for cik in ciks:
        try:
            r = calcular(cur, cik)
        except Exception as e:
            print(f"  {cik}: error {e}"); continue
        m = meta.get(cik, (None,)*6)
        vals = [cik, m[0], m[1], m[2], m[3], m[4], m[5]]
        vals += [r.get(c) for c in cols_ratio]
        vals += [r.get(c) for c in cols_dbg if c != "_ni_estrategia"]
        vals += [r.get("_ni_estrategia"), fecha]
        ph = ",".join("?"*len(vals))
        con.execute(f"INSERT OR REPLACE INTO ratios VALUES ({ph})", vals)
        n_ok += 1
        if n_ok % 100 == 0: con.commit()
    con.commit()
    print(f"OK: {n_ok} empresas con ratios calculados en tabla `ratios`")
    # cobertura por ratio clave
    print("\nCobertura (no-NULL) de ratios clave:")
    for c in ["margen_neto","roe","roa","deuda_ebitda","current_ratio","fcf_margin","payout","cagr_eps_5y"]:
        n = con.execute(f"SELECT COUNT(*) FROM ratios WHERE \"{c}\" IS NOT NULL").fetchone()[0]
        print(f"  {c:<20} {n}/{n_ok}")
    con.close()


if __name__ == "__main__":
    main()
