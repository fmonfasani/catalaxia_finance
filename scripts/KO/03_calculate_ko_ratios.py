#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

import numpy as np
import pandas as pd


# ============================================================
# CATALAXIA / KO
# 03_calculate_ko_ratios.py
#
# INPUTS
#   01 -> KO_FINANCIAL_INPUTS_2021_2025.csv
#   02 -> KO_YAHOO_MARKET_2021_2025.csv
#   Dictionary -> TIKR_CANONICAL_MAPPING_KO.xlsx
#   Reference -> KO_TIKR_REFERENCE_QUARTERLY_MASTER.xlsx
#
# OUTPUTS
#   KO_RATIOS_2021_2025.csv
#   KO_RATIOS_2021_2025.xlsx
#   KO_CATALAXIA_TIKR_OUTPUT_QUARTERLY.xlsx
#
# IMPORTANT
#   - Does not modify RAW/input files.
#   - TIKR is used as structural/reference benchmark only.
#   - Financial statement values in the TIKR-shaped output are represented
#     in USD millions, while the current Catalaxia input is USD billions.
#   - Ratios are not scaled.
#   - Missing data remains NULL; it is never silently converted to zero.
# ============================================================

BASE = Path(__file__).resolve().parent

EDGAR = BASE / "KO_FINANCIAL_INPUTS_2021_2025.csv"
YAHOO = BASE / "KO_YAHOO_MARKET_2021_2025.csv"

DICT_CANDIDATES = [
    BASE / "TIKR_CANONICAL_MAPPING_KO.xlsx",
    BASE / "TIKR_CANONICAL_MAPPING_KO.csv",
]

REF_CANDIDATES = [
    BASE / "KO_TIKR_REFERENCE_QUARTERLY_MASTER.xlsx",
    BASE / "KO_TIKR_REFERENCE_QUARTERLY.xlsx",
]

OUT_CSV = BASE / "KO_RATIOS_2021_2025.csv"
OUT_XLSX = BASE / "KO_RATIOS_2021_2025.xlsx"
OUT_TIKR = BASE / "KO_CATALAXIA_TIKR_OUTPUT_QUARTERLY.xlsx"

SEC_JSON = BASE / "data" / "raw" / "companyfacts" / "CIK0000021344.json"


def _load_historical_fy_eps() -> dict[int, float]:
    """Read FY diluted EPS from SEC CompanyFacts JSON for CAGR lookback."""
    if not SEC_JSON.exists():
        return {}
    data = json.loads(SEC_JSON.read_text(encoding="utf-8"))
    entries = (
        data.get("facts", {})
        .get("us-gaap", {})
        .get("EarningsPerShareDiluted", {})
        .get("units", {})
        .get("USD/shares", [])
    )
    seen: dict[int, float] = {}
    for e in entries:
        if e.get("fp") == "FY" and e.get("form") in ("10-K", "10-K/A"):
            seen[int(e["fy"])] = float(e["val"])
    return seen


RATIOS = [
    "ROA_%", "ROIC_%", "ROE_%", "Common_Equity_ROE_%",
    "Gross_Margin_%", "SGA_%", "EBITDA_Margin_%",
    "EBITA_Margin_%", "EBIT_Margin_%",
    "Continuing_Operations_Income_Margin_%",
    "Net_Margin_%", "Normalized_Net_Margin_%",
    "FCF_Levered_Margin_%", "FCF_Unlevered_Margin_%",
    "CFO_Current_Liabilities_%", "FCFonCE_%",
    "Asset_Turnover", "Fixed_Asset_Turnover", "AR_Turnover",
    "Inventory_Turnover", "Working_Capital_Turnover",
    "CCC", "DSO", "DIO", "DPO",
    "Current_Ratio", "Quick_Ratio",
    "Debt_Equity_%", "Debt_Total_Capital_%",
    "Liabilities_Assets_%",
    "Debt_EBITDA", "Net_Debt_EBITDA",
    "Net_Debt_EBITDA_Capex",
    "EBIT_Interest", "EBITDA_Interest",
    "EBITDA_Capex_Interest", "FFO_Interest", "FFO_Debt",
    "P_E", "Annual_EPS", "EPS_TTM", "EPS_Growth_5Y_%",
    "P_E_Growth_5Y_%",
    "Price", "52W_High", "Diff_vs_52W_High_%",
    "52W_Low", "Diff_vs_52W_Low_%",
    "Dividend_Yield_%", "Payout_Ratio_%",
]


def find_existing(candidates: list[Path], description: str) -> Path:
    for path in candidates:
        if path.exists():
            return path
    names = "\n".join(f"  - {p}" for p in candidates)
    raise FileNotFoundError(f"Falta {description}. Buscado:\n{names}")


def num(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[name], errors="coerce")


def div(a, b) -> pd.Series:
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    return a.div(b).where(b.notna() & b.ne(0))


def pct(a, b) -> pd.Series:
    return div(a, b) * 100.0


def avg_previous(df: pd.DataFrame, column: str) -> pd.Series:
    cur = num(df, column)
    prev = cur.shift(1)
    return (cur + prev) / 2.0


def normalize_label(value) -> str:
    s = "" if pd.isna(value) else str(value)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[*_]", "", s)
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def period_key(value) -> str | None:
    if pd.isna(value):
        return None

    # ISO date / datetime / Timestamp.
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")

    # TIKR strings such as 29/9/23, 31/12/25, etc.
    parsed = pd.to_datetime(str(value), errors="coerce", dayfirst=True)
    if not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")

    return None


def period_type_for_key(df: pd.DataFrame) -> pd.Series:
    if "period" in df.columns:
        return df["period"].astype(str)
    return pd.Series("", index=df.index)


def load_dictionary() -> pd.DataFrame:
    path = find_existing(DICT_CANDIDATES, "TIKR canonical dictionary")
    if path.suffix.lower() == ".csv":
        d = pd.read_csv(path)
    else:
        d = pd.read_excel(path, sheet_name="TIKR_MAPPING")

    required = {"tikr_label", "econ_key"}
    missing = required - set(d.columns)
    if missing:
        raise AssertionError(
            f"Diccionario incompleto. Faltan columnas: {sorted(missing)}"
        )

    d = d.copy()
    d["tikr_label_norm"] = d["tikr_label"].map(normalize_label)
    d["econ_key"] = d["econ_key"].astype(str).str.strip()
    d = d.drop_duplicates(subset=["tikr_label_norm"], keep="first")

    return d


def load_reference() -> tuple[Path, pd.ExcelFile]:
    path = find_existing(REF_CANDIDATES, "TIKR reference workbook")
    return path, pd.ExcelFile(path)


def canonical_fact_series(
    econ_key: str,
    facts: pd.DataFrame,
    ratios: pd.DataFrame,
) -> pd.Series:
    """
    Maps the dictionary's canonical ECON_KEY to the actual fields produced
    by 01/02/03.

    This is deliberately centralized here rather than scattered through
    the workbook builder.
    """
    fact_map = {
        # Income statement
        "revenue": "revenue",
        "cost_of_goods_sold": "cost_of_revenue",
        "gross_profit": "gross_profit",
        "sga_expense": "sga",
        "operating_income": "operating_income",
        "interest_expense": "interest_expense",
        "income_before_tax": "income_before_tax",
        "ebt_excl_unusual_items": "income_before_tax",
        "ebt_incl_unusual_items": "income_before_tax",
        "income_tax_expense": "income_tax_expense",
        "continuing_operations_income": "continuing_operations_income",
        "net_income": "net_income",
        "net_income_to_company": "net_income_to_company",
        "minority_interest": "minority_interest",
        "eps_diluted": "eps_diluted",
        "net_income_to_common": "net_income",
        "normalized_net_income": "net_income",
        "diluted_eps_excl_extra": "eps_diluted",
        "weighted_avg_diluted_shares": "diluted_shares",
        "weighted_avg_basic_shares": "diluted_shares",
        "dividends_per_share": "dps",
        "basic_eps": "eps_basic",
        "ebitda": "ebitda",
        "selling_marketing_expense": "selling_marketing_expense",

        # Balance sheet
        "cash_and_equivalents": "cash",
        "short_term_investments": "short_term_investments",
        "cash_and_short_term_investments": "__cash_plus_sti",
        "accounts_receivable": "accounts_receivable",
        "inventory": "inventory",
        "current_assets": "current_assets",
        "gross_ppe": "ppe_gross",
        "accumulated_depreciation": "accumulated_depreciation",
        "net_ppe": "ppe_net",
        "long_term_investments": "long_term_investments",
        "goodwill": "goodwill",
        "other_intangibles": "other_intangibles",
        "deferred_tax_assets_long_term": "deferred_tax_assets_long_term",
        "other_long_term_assets": "other_long_term_assets",
        "total_assets": "assets",
        "assets": "assets",
        "accounts_payable": "accounts_payable",
        "accrued_expenses": "accrued_expenses",
        "short_term_borrowings": "short_term_borrowings",
        "current_portion_long_term_debt": "debt_current",
        "current_liabilities": "current_liabilities",
        "long_term_debt": "debt_long_term",
        "capital_leases": "capital_leases",
        "pension_other_post_retirement": "pension_other_post_retirement",
        "deferred_tax_liability_noncurrent": "deferred_tax_liability_noncurrent",
        "other_noncurrent_liabilities": "other_noncurrent_liabilities",
        "liabilities": "liabilities",
        "total_liabilities": "liabilities",
        "common_stock": "common_stock",
        "additional_paid_in_capital": "additional_paid_in_capital",
        "retained_earnings": "retained_earnings",
        "treasury_stock": "treasury_stock",
        "comprehensive_income_other": "comprehensive_income_other",
        "common_equity": "common_equity",
        "minority_interest_balance": "minority_interest_balance",
        "equity": "equity",
        "total_equity": "equity",
        "total_liabilities_and_equity": "__liabilities_plus_equity",
        "shares_out_filing_date": "shares_out_filing_date",
        "tangible_book_value": "tangible_book_value",
        "total_debt": "total_debt",
        "net_debt": "__net_debt",
        "equity_method_investments": "equity_method_investments",

        # Cash flow
        "depreciation_amortization": "da",
        "total_depreciation_amortization": "total_da",
        "stock_based_compensation": "stock_based_compensation",
        "cfo": "cfo",
        "capex": "capex",
        "cash_from_investing": "cash_from_investing",
        "debt_issued": "debt_issued",
        "debt_repaid": "debt_repaid",
        "issuance_common_stock": "issuance_common_stock",
        "repurchase_common_stock": "repurchase_common_stock",
        "common_dividends_paid": "common_dividends_paid",
        "common_preferred_dividends_paid": "common_preferred_dividends_paid",
        "cash_from_financing": "cash_from_financing",
        "fx_rate_adjustments": "fx_rate_adjustments",
        "net_change_cash": "net_change_cash",
        "cash_beginning_period": "cash_beginning_period",
        "cash_end_period": "cash_end_period",
        "cash_interest_paid": "cash_interest_paid",
        "cash_taxes_paid": "cash_taxes_paid",
    }

    ratio_map = {
        "roa": "ROA_%",
        "roic": "ROIC_%",
        "roe": "ROE_%",
        "common_equity_roe": "Common_Equity_ROE_%",
        "gross_margin": "Gross_Margin_%",
        "sga_margin": "SGA_%",
        "ebitda_margin": "EBITDA_Margin_%",
        "ebita_margin": "EBITA_Margin_%",
        "ebit_margin": "EBIT_Margin_%",
        "continuing_operations_income_margin": "Continuing_Operations_Income_Margin_%",
        "net_margin": "Net_Margin_%",
        "normalized_net_margin": "Normalized_Net_Margin_%",
        "net_available_common_margin": "Net_Margin_%",
        "fcf_levered_margin": "FCF_Levered_Margin_%",
        "fcf_unlevered_margin": "FCF_Unlevered_Margin_%",
        "asset_turnover": "Asset_Turnover",
        "fixed_asset_turnover": "Fixed_Asset_Turnover",
        "ar_turnover": "AR_Turnover",
        "inventory_turnover": "Inventory_Turnover",
        "working_capital_turnover": "Working_Capital_Turnover",
        "current_ratio": "Current_Ratio",
        "quick_ratio": "Quick_Ratio",
        "cfo_current_liabilities": "CFO_Current_Liabilities_%",
        "cash_conversion_cycle": "CCC",
        "dso": "DSO",
        "dio": "DIO",
        "dpo": "DPO",
        "debt_equity": "Debt_Equity_%",
        "debt_total_capital": "Debt_Total_Capital_%",
        "liabilities_assets": "Liabilities_Assets_%",
        "ebit_interest": "EBIT_Interest",
        "ebitda_interest": "EBITDA_Interest",
        "ebitda_capex_interest": "EBITDA_Capex_Interest",
        "ffo_interest": "FFO_Interest",
        "ffo_debt": "FFO_Debt",
        "debt_ebitda": "Debt_EBITDA",
        "net_debt_ebitda": "Net_Debt_EBITDA",
        "net_debt_ebitda_capex": "Net_Debt_EBITDA_Capex",
        "payout_ratio": "Payout_Ratio_%",
        "effective_tax_rate": "__effective_tax_rate",
        "market_cap": "__market_cap",
        "price_close": "Price",
        "tev": "__tev",
        "free_cash_flow": "__fcf",
        "cash_flow_per_share": "__cfps",
        "diluted_eps_excl_extra": "Annual_EPS",
        "book_value_per_share": "__bvps",
        "tangible_book_value_per_share": "__tbvps",
    }

    ratio_col = ratio_map.get(econ_key)
    if ratio_col and ratio_col in ratios.columns:
        return ratios[ratio_col]

    if ratio_col == "__effective_tax_rate":
        ibt = num(facts, "income_before_tax")
        tax = num(facts, "income_tax_expense")
        return (tax / ibt * 100).where(ibt.notna() & ibt.ne(0))

    if ratio_col == "__fcf":
        return num(facts, "cfo") - num(facts, "capex")

    if ratio_col == "__cfps":
        return num(facts, "cfo") / num(facts, "diluted_shares")

    if ratio_col == "__bvps":
        return num(facts, "common_equity") / num(facts, "diluted_shares") * 1e9

    if ratio_col == "__tbvps":
        return pd.Series(np.nan, index=facts.index, dtype="float64")

    if ratio_col == "__market_cap":
        return pd.Series(np.nan, index=facts.index, dtype="float64")

    if ratio_col == "__tev":
        return pd.Series(np.nan, index=facts.index, dtype="float64")

    col = fact_map.get(econ_key)
    if not col:
        return pd.Series(np.nan, index=facts.index, dtype="float64")

    if col == "__cash_plus_sti":
        return num(facts, "cash") + num(facts, "short_term_investments").fillna(0)

    if col == "__net_debt":
        return (
            num(facts, "total_debt")
            - num(facts, "cash")
            - num(facts, "short_term_investments").fillna(0)
        )

    if col == "__liabilities_plus_equity":
        return num(facts, "liabilities") + num(facts, "equity")

    return num(facts, col)


def build_tikr_output(
    facts: pd.DataFrame,
    ratios: pd.DataFrame,
    dictionary: pd.DataFrame,
    reference: pd.ExcelFile,
) -> None:
    """
    Builds four sheets with EXACTLY the row labels and period columns of
    the TIKR reference.

    The dictionary supplies:
        TIKR label -> ECON_KEY

    The canonical field resolver supplies:
        ECON_KEY -> Catalaxia field / calculated ratio

    Financial values are converted from Catalaxia USD billions to TIKR
    USD millions in this presentation layer only.
    """
    facts = facts.copy()
    ratios = ratios.copy()

    facts["__key"] = facts["period_end"].map(period_key)
    ratios["__key"] = ratios["period_end"].map(period_key)

    # Do NOT index only by period_end: Q4 and FY share the same date
    # (31/12/YYYY). TIKR's 31/12 column is standalone Q4, so the
    # selector below must preserve the period type.

    # Mapping index.
    mapping = dictionary.set_index("tikr_label_norm")["econ_key"].to_dict()

    with pd.ExcelWriter(OUT_TIKR, engine="openpyxl") as writer:
        for sheet in ["TIKR_IS", "TIKR_BS", "TIKR_CF", "TIKR_RATIOS"]:
            ref = pd.read_excel(reference, sheet_name=sheet)

            if "Metric" not in ref.columns:
                raise AssertionError(
                    f"{sheet}: la referencia debe tener columna 'Metric'."
                )

            period_columns = [c for c in ref.columns if c != "Metric"]

            result = pd.DataFrame({"Metric": ref["Metric"]})

            for pcol in period_columns:
                key = period_key(pcol)
                values = []

                for metric in ref["Metric"]:
                    label_norm = normalize_label(metric)
                    econ_key = mapping.get(label_norm)

                    value = np.nan

                    if econ_key and key:
                        # TIKR quarterly reference uses standalone Q1/Q2/Q3/Q4.
                        # For 31/12/YYYY, select Q4 rather than FY.
                        source = ratios if sheet == "TIKR_RATIOS" else facts
                        source_rows = source[source["__key"].eq(key)]

                        if not source_rows.empty:
                            # For TIKR quarterly columns, prefer Q4 on 31/12;
                            # otherwise prefer the matching quarter.
                            if key.endswith("-12-31"):
                                candidates = source_rows[
                                    source_rows["period"].astype(str).str.upper().eq("Q4")
                                ]
                            else:
                                candidates = source_rows

                            if candidates.empty:
                                candidates = source_rows

                            # There must be exactly one selected source row.
                            if len(candidates) == 1:
                                selected = candidates.index[0]
                                s = canonical_fact_series(
                                    econ_key, facts, ratios
                                )
                                value = s.loc[selected]

                    # Presentation normalization:
                    # Catalaxia financial statement values are USD billions;
                    # TIKR reference is USD millions.
                    if (
                        not pd.isna(value)
                        and sheet != "TIKR_RATIOS"
                        and isinstance(econ_key, str)
                    ):
                        _NO_SCALE = {
                            "diluted_eps_excl_extra", "basic_eps",
                            "dividends_per_share", "price_close",
                            "book_value_per_share",
                            "tangible_book_value_per_share",
                            "cash_flow_per_share",
                            "effective_tax_rate", "payout_ratio",
                        }
                        _SHARES_TO_MILLIONS = {
                            "weighted_avg_diluted_shares",
                            "weighted_avg_basic_shares",
                            "shares_out_filing_date",
                        }
                        _NEGATE = {
                            "cost_of_goods_sold", "sga_expense",
                            "interest_expense", "income_tax_expense",
                            "capex", "common_dividends_paid",
                            "common_preferred_dividends_paid",
                            "cash_interest_paid", "cash_taxes_paid",
                        }
                        if econ_key in _SHARES_TO_MILLIONS:
                            value = float(value) / 1e6
                        elif econ_key not in _NO_SCALE:
                            value = float(value) * 1000.0
                        if econ_key in _NEGATE:
                            value = -float(value)

                    values.append(value)

                result[pcol] = values

            result.to_excel(writer, index=False, sheet_name=sheet)

            ws = writer.book[sheet]
            ws.freeze_panes = "B2"
            ws.column_dimensions["A"].width = 55
            for col_idx in range(2, len(result.columns) + 1):
                from openpyxl.utils import get_column_letter
                ws.column_dimensions[get_column_letter(col_idx)].width = 14

    print(f"TIKR-shaped XLSX: {OUT_TIKR}")


def main() -> None:
    # ------------------------------------------------------------
    # 1. Validate inputs
    # ------------------------------------------------------------
    if not EDGAR.exists():
        raise FileNotFoundError(f"Falta {EDGAR}")
    if not YAHOO.exists():
        raise FileNotFoundError(f"Falta {YAHOO}")

    dictionary = load_dictionary()
    reference_path, reference = load_reference()

    e = pd.read_csv(EDGAR)
    y = pd.read_csv(YAHOO)

    if len(e) != 25 or len(y) != 25:
        raise AssertionError(
            f"Se requieren 25 filas: EDGAR={len(e)}, YAHOO={len(y)}"
        )

    keys = ["fiscal_year", "period", "period_end"]
    for k in keys:
        if k not in e.columns or k not in y.columns:
            raise AssertionError(f"Falta clave {k}")

    e["period_end"] = pd.to_datetime(
        e["period_end"], errors="raise"
    ).dt.strftime("%Y-%m-%d")
    y["period_end"] = pd.to_datetime(
        y["period_end"], errors="raise"
    ).dt.strftime("%Y-%m-%d")

    if e.duplicated(keys).any() or y.duplicated(keys).any():
        raise AssertionError("Hay claves duplicadas en las tablas de entrada")

    df = e.merge(
        y,
        on=keys,
        how="left",
        validate="one_to_one",
        suffixes=("_edgar", "_yahoo"),
    )

    if len(df) != 25:
        raise AssertionError(f"Merge produjo {len(df)} filas, esperado 25")

    # ------------------------------------------------------------
    # 2. Economic facts from 01
    # ------------------------------------------------------------
    revenue = num(df, "revenue")
    cost_of_revenue = num(df, "cost_of_revenue")
    gross_profit = num(df, "gross_profit")
    sga = num(df, "sga")
    # Methodology: Operating Income adjusted (TIKR criterion).
    # GAAP OperatingIncomeLoss includes non-recurring impairment charges.
    # Adjusted OpInc adds them back to reflect recurring operations.
    # EBITDA recomputed from adjusted OpInc + D&A.
    operating_income_gaap = num(df, "operating_income")
    imp_intang = num(df, "impairment_intangibles").fillna(0)
    imp_assets = num(df, "impairment_assets").fillna(0)
    imp_goodwill = num(df, "goodwill_impairment").fillna(0)
    operating_income = operating_income_gaap + imp_intang + imp_assets + imp_goodwill

    interest = num(df, "interest_expense")
    income_before_tax = num(df, "income_before_tax")
    income_tax = num(df, "income_tax_expense")
    net_income = num(df, "net_income")
    da = num(df, "da")
    ebitda = operating_income + da
    cfo = num(df, "cfo")
    capex = num(df, "capex")

    assets = num(df, "assets")
    common_equity = num(df, "common_equity")
    equity = num(df, "equity")
    liabilities = num(df, "liabilities")
    current_assets = num(df, "current_assets")
    current_liabilities = num(df, "current_liabilities")
    cash = num(df, "cash")
    sti = num(df, "short_term_investments")
    ar = num(df, "accounts_receivable")
    inventory = num(df, "inventory")
    ppe = num(df, "ppe_net")
    ap = num(df, "accounts_payable")
    debt = num(df, "total_debt")
    eps = num(df, "eps_diluted")
    fcf = cfo - capex
    ffo = cfo

    out = df[keys].copy()

    # ------------------------------------------------------------
    # 3. 49 contractual ratios
    # ------------------------------------------------------------

    # --- Margin ratios (flow/flow, no annualization needed) ---
    out["Gross_Margin_%"] = pct(gross_profit, revenue)
    out["SGA_%"] = pct(sga, revenue)
    out["EBITDA_Margin_%"] = pct(ebitda, revenue)
    out["EBITA_Margin_%"] = pct(operating_income, revenue)
    out["EBIT_Margin_%"] = pct(operating_income, revenue)
    out["Continuing_Operations_Income_Margin_%"] = pct(
        income_before_tax - income_tax, revenue
    )
    out["Net_Margin_%"] = pct(net_income, revenue)
    out["Normalized_Net_Margin_%"] = np.nan
    out["FCF_Levered_Margin_%"] = pct(fcf, revenue)
    out["FCF_Unlevered_Margin_%"] = pct(fcf + interest, revenue)

    # --- Averages (previous row in sorted order: Q1→Q2→…→FY) ---
    avg_assets = avg_previous(df, "assets")
    avg_equity = avg_previous(df, "equity")
    avg_common_equity = avg_previous(df, "common_equity")
    avg_ppe = avg_previous(df, "ppe_net")
    avg_ar = avg_previous(df, "accounts_receivable")
    avg_inventory = avg_previous(df, "inventory")
    avg_ap = avg_previous(df, "accounts_payable")

    # --- Annualization factor: quarterly periods need *4 for flow items ---
    is_fy = df["period"].eq("FY")
    ann = pd.Series(np.where(is_fy, 1.0, 4.0), index=df.index)

    # --- Return ratios (annualized flow / avg stock) ---
    out["ROA_%"] = pct(net_income * ann, avg_assets)
    out["ROE_%"] = pct(net_income * ann, avg_equity)
    out["Common_Equity_ROE_%"] = pct(net_income * ann, avg_common_equity)

    tax_rate = div(income_tax, income_before_tax).clip(lower=0, upper=1)
    nopat = operating_income * (1 - tax_rate)
    invested_capital = debt + equity - cash - sti.fillna(0)
    avg_ic = (invested_capital + invested_capital.shift(1)) / 2.0
    out["ROIC_%"] = pct(nopat * ann, avg_ic)

    # --- Activity / turnover (annualized flow / avg stock) ---
    ann_revenue = revenue * ann
    ann_cogs = cost_of_revenue * ann
    out["Asset_Turnover"] = div(ann_revenue, avg_assets)
    out["Fixed_Asset_Turnover"] = div(ann_revenue, avg_ppe)
    out["AR_Turnover"] = div(ann_revenue, avg_ar)
    out["Inventory_Turnover"] = div(ann_cogs, avg_inventory)
    working_capital = current_assets - current_liabilities
    out["Working_Capital_Turnover"] = div(ann_revenue, working_capital)

    out["DSO"] = div(avg_ar, ann_revenue) * 365.0
    out["DIO"] = div(avg_inventory, ann_cogs) * 365.0
    out["DPO"] = div(avg_ap, ann_cogs) * 365.0
    out["CCC"] = out["DSO"] + out["DIO"] - out["DPO"]

    # --- Liquidity (stock / stock ratios, no annualization) ---
    out["Current_Ratio"] = div(current_assets, current_liabilities)
    out["Quick_Ratio"] = div(cash + sti.fillna(0) + ar, current_liabilities)
    out["CFO_Current_Liabilities_%"] = div(cfo * ann, current_liabilities)
    out["FCFonCE_%"] = pct(fcf * ann, equity)

    # --- Leverage ---
    out["Debt_Equity_%"] = pct(debt, equity)
    out["Debt_Total_Capital_%"] = pct(debt, debt + equity)
    out["Liabilities_Assets_%"] = pct(liabilities, assets)

    net_debt = debt - cash - sti.fillna(0)
    ann_ebitda = ebitda * ann
    out["Debt_EBITDA"] = div(debt, ann_ebitda)
    out["Net_Debt_EBITDA"] = div(net_debt, ann_ebitda)
    out["Net_Debt_EBITDA_Capex"] = div(net_debt, ann_ebitda - capex * ann)

    # --- Coverage (flow/flow same-period, no annualization needed) ---
    out["EBIT_Interest"] = div(operating_income, interest)
    out["EBITDA_Interest"] = div(ebitda, interest)
    out["EBITDA_Capex_Interest"] = div(ebitda - capex, interest)
    out["FFO_Interest"] = div(ffo, interest)
    out["FFO_Debt"] = div(ffo * ann, debt)

    # --- Market / valuation ---
    out["Price"] = num(df, "price_usd")
    out["52W_High"] = num(df, "52w_high_usd")
    out["52W_Low"] = num(df, "52w_low_usd")
    out["Diff_vs_52W_High_%"] = pct(out["Price"], out["52W_High"]) - 100.0
    out["Diff_vs_52W_Low_%"] = pct(out["Price"], out["52W_Low"]) - 100.0
    out["Dividend_Yield_%"] = num(df, "dividend_yield_ttm_pct")

    out["Annual_EPS"] = eps
    fy = out["period"].eq("FY")

    # TTM EPS: for quarters, rolling sum of last 4 quarterly EPS;
    # for FY, use annual EPS directly.
    eps_ttm = pd.Series(np.nan, index=out.index)
    eps_ttm[fy] = eps[fy]
    q_mask = out["period"].isin(["Q1", "Q2", "Q3", "Q4"])
    q_idx = out.index[q_mask]
    eps_ttm.loc[q_idx] = eps.loc[q_idx].rolling(4, min_periods=4).sum()
    out["EPS_TTM"] = eps_ttm

    # EPS Growth 5Y CAGR: (EPS_current / EPS_5y_ago)^(1/5) - 1
    hist_eps = _load_historical_fy_eps()
    eps_g5 = pd.Series(np.nan, index=out.index)
    for i, row in out.iterrows():
        yr = int(row["fiscal_year"])
        base_yr = yr - 5
        eps_now = eps_ttm.loc[i]
        eps_base = hist_eps.get(base_yr)
        if (
            eps_base is not None
            and eps_base > 0
            and pd.notna(eps_now)
            and eps_now > 0
        ):
            eps_g5.loc[i] = ((eps_now / eps_base) ** 0.2 - 1) * 100
    out["EPS_Growth_5Y_%"] = eps_g5

    pe = div(out["Price"], eps_ttm)
    out["P_E"] = pe

    # P/E Growth 5Y CAGR: (PE_current / PE_5y_ago)^(1/5) - 1
    # Build historical FY P/E from SEC EPS + Yahoo year-end price.
    pe_g5 = pd.Series(np.nan, index=out.index)
    hist_pe: dict[int, float] = {}
    try:
        import yfinance as yf

        min_base_yr = int(out["fiscal_year"].min()) - 5
        tk = yf.Ticker("KO")
        hist_price = tk.history(
            start=f"{min_base_yr}-01-01",
            end=f"{min_base_yr + 5}-01-05",
            auto_adjust=False,
        )
        if hist_price is not None and not hist_price.empty:
            hist_price = hist_price.reset_index()
            hist_price["Date"] = pd.to_datetime(
                hist_price["Date"]
            ).dt.tz_localize(None)
            for yr in range(min_base_yr, min_base_yr + 5):
                fy_eps = hist_eps.get(yr)
                if fy_eps and fy_eps > 0:
                    yr_end = hist_price[
                        hist_price["Date"].dt.year == yr
                    ]
                    if not yr_end.empty:
                        price_yr = float(yr_end.iloc[-1]["Close"])
                        hist_pe[yr] = price_yr / fy_eps
    except Exception:
        pass

    pe_lookup: dict[tuple[int, str], float] = {}
    for i, row in out.iterrows():
        pe_lookup[(int(row["fiscal_year"]), row["period"])] = pe.loc[i]
    for yr_h, pe_h in hist_pe.items():
        pe_lookup[(yr_h, "FY")] = pe_h

    for i, row in out.iterrows():
        yr = int(row["fiscal_year"])
        pe_now = pe.loc[i]
        pe_base = pe_lookup.get((yr - 5, row["period"]))
        if (
            pe_base is not None
            and pd.notna(pe_base)
            and pe_base > 0
            and pd.notna(pe_now)
            and pe_now > 0
        ):
            pe_g5.loc[i] = ((pe_now / pe_base) ** 0.2 - 1) * 100
    out["P_E_Growth_5Y_%"] = pe_g5

    # Payout Ratio: per-period (TIKR criterion).
    # Q: quarterly DPS / quarterly EPS. FY: annual DPS / annual EPS.
    # Both GAAP — the dividend is paid from real earnings.
    dps_q = num(df, "dps")
    out["Payout_Ratio_%"] = np.where(
        eps.ne(0) & eps.notna() & dps_q.notna(),
        pct(dps_q, eps), np.nan
    )

    for ratio in RATIOS:
        if ratio not in out.columns:
            out[ratio] = np.nan

    # ------------------------------------------------------------
    # 4. Null reasons / execution evidence
    # ------------------------------------------------------------
    reasons = []

    for _, row in out.iterrows():
        rr = []

        if pd.isna(row["DPO"]):
            rr.append("accounts_payable_missing_or_insufficient")

        if pd.isna(row["EBIT_Interest"]):
            rr.append("interest_expense_missing")

        if pd.isna(row["FFO_Interest"]) or pd.isna(row["FFO_Debt"]):
            rr.append("ffo_missing")

        if pd.isna(row["Annual_EPS"]) and row["period"] != "FY":
            rr.append("annual_eps_fy_only")

        reasons.append(";".join(rr))

    out["null_reason"] = reasons

    out = out[keys + RATIOS + ["null_reason"]]

    # ------------------------------------------------------------
    # 5. Outputs
    # ------------------------------------------------------------
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    out.to_excel(OUT_XLSX, index=False)

    # Inject adjusted values into facts for TIKR output layer.
    df_adj = df.copy()
    df_adj["operating_income"] = operating_income
    df_adj["ebitda"] = ebitda

    build_tikr_output(
        facts=df_adj,
        ratios=out,
        dictionary=dictionary,
        reference=reference,
    )

    # ------------------------------------------------------------
    # 6. Explicit validation
    # ------------------------------------------------------------
    if len(out) != 25:
        raise AssertionError(f"Output ratios: {len(out)} filas; esperado 25")

    missing_ratios = [r for r in RATIOS if r not in out.columns]
    if missing_ratios:
        raise AssertionError(
            f"Faltan ratios contractuales: {missing_ratios}"
        )

    expected_sheets = {"TIKR_IS", "TIKR_BS", "TIKR_CF", "TIKR_RATIOS"}
    produced = set(pd.ExcelFile(OUT_TIKR).sheet_names)
    if produced != expected_sheets:
        raise AssertionError(
            f"Sheets TIKR incorrectas: {sorted(produced)}"
        )

    print("=" * 68)
    print("KO CATALAXIA RATIOS + TIKR STRUCTURE: PASS")
    print("Rows:", len(out))
    print("Ratios:", len(RATIOS))
    print("Dictionary rows:", len(dictionary))
    print("TIKR reference:", reference_path.name)
    print("Ratios CSV:", OUT_CSV)
    print("Ratios XLSX:", OUT_XLSX)
    print("TIKR-shaped XLSX:", OUT_TIKR)
    print("=" * 68)


if __name__ == "__main__":
    main()
