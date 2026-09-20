#!/usr/bin/env python3
"""
Catalaxia / YPF — Ratio calculator + TIKR-shaped output (USD)

INPUTS
  01 -> YPF_FINANCIAL_INPUTS_2021_2025.csv
  02 -> YPF_YAHOO_MARKET_2021_2025.csv
  Reference -> YPF_TIKR_REFERENCE_MASTER_USD.xlsx

OUTPUTS
  YPF_RATIOS_2021_2025.csv/.xlsx
  YPF_CATALAXIA_TIKR_OUTPUT_ANNUAL.xlsx (4 sheets: TIKR_IS/BS/CF/RATIOS)

All periods are annual (FY). No annualization factor needed.
Both TIKR reference and Catalaxia output are in USD millions.
Internal data is USD billions; TIKR output multiplies by 1000.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent

EDGAR = BASE / "YPF_FINANCIAL_INPUTS_2021_2025.csv"
YAHOO = BASE / "YPF_YAHOO_MARKET_2021_2025.csv"

REF_CANDIDATES = [
    BASE / "YPF_TIKR_REFERENCE_MASTER_USD.xlsx",
]

OUT_CSV = BASE / "YPF_RATIOS_2021_2025.csv"
OUT_XLSX = BASE / "YPF_RATIOS_2021_2025.xlsx"
OUT_TIKR = BASE / "YPF_CATALAXIA_TIKR_OUTPUT_ANNUAL.xlsx"

EXPECTED_ROWS = 5


RATIOS = [
    "ROA_%", "ROIC_%", "ROE_%", "Common_Equity_ROE_%",
    "Gross_Margin_%", "SGA_%", "EBITDA_Margin_%",
    "EBITA_Margin_%", "EBIT_Margin_%",
    "Continuing_Operations_Income_Margin_%",
    "Net_Margin_%", "Normalized_Net_Margin_%",
    "FCF_Levered_Margin_%", "FCF_Unlevered_Margin_%",
    "CFO_Current_Liabilities_%",
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
    "Price", "52W_High", "52W_Low",
    "Payout_Ratio_%",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_existing(candidates: list[Path], description: str) -> Path:
    for path in candidates:
        if path.exists():
            return path
    names = "\n".join(f"  - {p}" for p in candidates)
    raise FileNotFoundError(f"Missing {description}:\n{names}")


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
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")
    parsed = pd.to_datetime(str(value), errors="coerce", dayfirst=True)
    if not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")
    return None


# ---------------------------------------------------------------------------
# TIKR canonical mapping
# ---------------------------------------------------------------------------

# Maps normalized TIKR label -> econ_key (internal column or computed field)
TIKR_MAPPING = {
    # ── IS ──
    "revenues": "revenue",
    "total revenues": "revenue",
    "cost of goods sold": "cost_of_sales",
    "gross profit": "gross_profit",
    "selling general & admin expenses": "sga",
    "exploration / drilling costs": "exploration_expense",
    "amortization of goodwill and intangible assets": "da_amortization",
    "impairment of oil gas & mineral properties": "impairment",
    "other operating expenses": "__other_op_expenses",
    "total operating expenses": "__total_op_expenses",
    "operating income": "operating_income",
    "interest expense": "interest_paid",
    "interest and investment income": "finance_income",
    "income (loss) on equity invest.": "share_of_associates",
    "currency exchange gains (loss)": "__currency_fx",
    "other non operating income (expenses)": "__other_non_op",
    "ebt excl. unusual items": "income_before_tax",
    "merger & restructuring charges": "__merger_restruct",
    "gain (loss) on sale of investments": "__gain_loss_investments",
    "gain (loss) on sale of assets": "__gain_loss_assets",
    "asset writedown": "__asset_writedown",
    "insurance settlements": "__insurance",
    "legal settlements": "__legal",
    "other unusual items": "__other_unusual",
    "ebt incl. unusual items": "income_before_tax",
    "income tax expense": "income_tax_expense",
    "earnings from continuing operations": "__continuing_ops",
    "net income to company": "net_income_to_company",
    "minority interest": "minority_interest_is",
    "net income": "net_income",
    "net income to common incl extra items": "net_income",
    "net income to common excl. extra items": "net_income",
    "diluted eps excl extra items": "eps_diluted",
    "weighted average diluted shares outstanding": "diluted_shares",
    "weighted average basic shares outstanding": "diluted_shares",
    "dividends per share": "__dps",
    "payout ratio %": "__payout",
    "basic eps": "eps_basic",
    "ebitda": "ebitda",
    "ebitdar": "__ebitdar",
    "r&d expense": "r_and_d",
    "selling and marketing expense": "__selling_marketing",
    "general and administrative expense": "admin_expense",
    "effective tax rate %": "__effective_tax_rate",
    "market cap": "__market_cap_mm",
    "price close": "__price_close",
    "tev": "__tev_mm",

    # ── BS ──
    "cash and equivalents": "cash",
    "short term investments": "short_term_investments",
    "trading asset securities": "__trading_assets",
    "total cash and short term investments": "__cash_plus_sti",
    "accounts receivable": "current_trade_receivables",
    "other receivables": "__other_receivables",
    "notes receivable": "__notes_receivable",
    "total receivables": "__total_receivables",
    "inventory": "inventories",
    "prepaid expenses": "__prepaid",
    "other current assets": "__other_current_assets",
    "total current assets": "current_assets",
    "gross property plant and equipment": "__gross_ppe",
    "accumulated depreciation": "__accum_dep",
    "net property plant and equipment": "ppe_net",
    "long-term investments": "noncurrent_financial_assets",
    "goodwill": "goodwill",
    "other intangibles": "intangibles",
    "accounts receivable long-term": "__ar_lt",
    "loans receivable long-term": "__loans_receivable_lt",
    "deferred tax assets long-term": "deferred_tax_assets",
    "deferred charges long-term": "__deferred_charges_lt",
    "other long-term assets": "__other_lt_assets",
    "total assets": "assets",
    "accounts payable": "accounts_payable",
    "accrued expenses": "__accrued",
    "short-term borrowings": "st_borrowings",
    "current portion of long-term debt": "__current_portion_lt_debt",
    "current portion of capital lease obligations": "current_lease_liabilities",
    "current income taxes payable": "__current_taxes_payable",
    "unearned revenue current": "__unearned_revenue_current",
    "other current liabilities": "__other_current_liabilities",
    "total current liabilities": "current_liabilities",
    "long-term debt": "lt_borrowings",
    "capital leases": "noncurrent_lease_liabilities",
    "unearned revenue non current": "__unearned_revenue_nc",
    "pension & other post retirement benefits": "noncurrent_provisions",
    "deferred tax liability non current": "deferred_tax_liabilities",
    "other non current liabilities": "__other_nc_liabilities",
    "total liabilities": "liabilities",
    "common stock": "issued_capital",
    "additional paid in capital": "__apic",
    "retained earnings": "retained_earnings",
    "treasury stock": "treasury_stock",
    "comprehensive income and other": "comprehensive_income_other",
    "total common equity": "common_equity",
    "total equity": "equity",
    "total liabilities and equity": "__liabilities_plus_equity",
    "total shares out. on filing date": "shares_outstanding",
    "book value / share": "__bvps",
    "tangible book value": "__tbv",
    "tangible book value / share": "__tbvps",
    "total debt": "total_debt",
    "net debt": "net_debt",
    "total minority interest": "minority_interest_bs",
    "equity method investments": "__equity_method_inv",
    "land": "__land",
    "construction in progress": "__construction_wip",
    "full time employees": "__fte",

    # ── CF ──
    "depreciation & amortization": "da_depreciation",
    "total depreciation & amortization": "total_da",
    "(gain) loss from sale of asset": "__gain_loss_asset_cf",
    "(gain) loss on sale of investments": "__gain_loss_inv_cf",
    "asset writedown & restructuring costs": "__writedown_cf",
    "(income) loss on equity investments": "share_of_associates",
    "stock-based compensation": "stock_comp",
    "net cash from discontinued operations": "__net_cash_disc",
    "other operating activities": "__other_operating",
    "change in accounts receivable": "change_ar",
    "change in inventories": "change_inventory",
    "change in accounts payable": "change_ap",
    "change in unearned revenues": "__change_unearned",
    "change in income taxes": "__change_income_taxes",
    "change in other net operating assets": "__change_other_noa",
    "cash from operations": "cfo",
    "memo: change in net working capital": "__memo_nwc",
    "capital expenditure": "capex",
    "sale of property, plant, and equipment": "__sale_ppe",
    "cash acquisitions": "__cash_acquisitions",
    "divestitures": "__divestitures",
    "sale (purchase) of intangible assets": "__sale_purchase_intangible",
    "investment in marketable and equity securities": "__inv_marketable",
    "other investing activities": "__other_investing",
    "cash from investing": "cash_from_investing",
    "total debt issued": "debt_issued",
    "total debt repaid": "debt_repaid",
    "repurchase of common stock": "__repurchase_stock",
    "common dividends paid": "__dividends_paid",
    "other financing activities": "__other_financing",
    "cash from financing": "cash_from_financing",
    "foreign exchange rate adjustments": "fx_effect",
    "miscellaneous cash flow adjustments": "__misc_cf_adj",
    "net change in cash": "net_change_cash",
    "free cash flow": "__fcf",
    "cash and cash equivalents, beginning of period": "__cash_beginning",
    "cash and cash equivalents, end of period": "__cash_end",
    "cash interest paid": "interest_paid",
    "cash taxes paid": "taxes_paid",
    "cash flow per share": "__cfps",

    # ── Ratios ──
    "return on assets %": "ROA_%",
    "return on capital %": "ROIC_%",
    "return on equity %": "ROE_%",
    "return on common equity %": "Common_Equity_ROE_%",
    "gross profit margin %": "Gross_Margin_%",
    "sg&a margin %": "SGA_%",
    "ebitda margin %": "EBITDA_Margin_%",
    "ebita margin %": "EBITA_Margin_%",
    "ebit margin %": "EBIT_Margin_%",
    "income from continuing operations margin %": "Continuing_Operations_Income_Margin_%",
    "net income margin %": "Net_Margin_%",
    "normalized net income margin %": "Normalized_Net_Margin_%",
    "net avail. for common margin %": "Net_Margin_%",
    "levered free cash flow margin %": "FCF_Levered_Margin_%",
    "unlevered free cash flow margin %": "FCF_Unlevered_Margin_%",
    "asset turnover": "Asset_Turnover",
    "fixed assets turnover": "Fixed_Asset_Turnover",
    "receivables turnover": "AR_Turnover",
    "inventory turnover": "Inventory_Turnover",
    "working capital turnover": "Working_Capital_Turnover",
    "current ratio": "Current_Ratio",
    "quick ratio": "Quick_Ratio",
    "op cash flow to current liab": "CFO_Current_Liabilities_%",
    "avg. cash conversion cycle": "CCC",
    "avg. days sales outstanding": "DSO",
    "avg. days outstanding inventory": "DIO",
    "avg. days payable outstanding": "DPO",
    "total debt / equity": "Debt_Equity_%",
    "total debt / capital": "Debt_Total_Capital_%",
    "total liabilities / total assets": "Liabilities_Assets_%",
    "ebit / interest expense": "EBIT_Interest",
    "ebitda / interest expense": "EBITDA_Interest",
    "(ebitda - capex) / interest expense": "EBITDA_Capex_Interest",
    "ffo interest coverage": "FFO_Interest",
    "ffo to total debt (x)": "FFO_Debt",
    "total debt / ebitda": "Debt_EBITDA",
    "net debt / ebitda": "Net_Debt_EBITDA",
    "net debt / (ebitda - capex)": "Net_Debt_EBITDA_Capex",
}


def canonical_fact_series(
    econ_key: str,
    facts: pd.DataFrame,
    ratios: pd.DataFrame,
    is_ratio_sheet: bool = False,
) -> pd.Series:
    """Maps econ_key to the actual data series (USD billions internally)."""

    ratio_keys = {
        "ROA_%", "ROIC_%", "ROE_%", "Common_Equity_ROE_%",
        "Gross_Margin_%", "SGA_%", "EBITDA_Margin_%",
        "EBITA_Margin_%", "EBIT_Margin_%",
        "Continuing_Operations_Income_Margin_%",
        "Net_Margin_%", "Normalized_Net_Margin_%",
        "FCF_Levered_Margin_%", "FCF_Unlevered_Margin_%",
        "CFO_Current_Liabilities_%",
        "Asset_Turnover", "Fixed_Asset_Turnover", "AR_Turnover",
        "Inventory_Turnover", "Working_Capital_Turnover",
        "CCC", "DSO", "DIO", "DPO",
        "Current_Ratio", "Quick_Ratio",
        "Debt_Equity_%", "Debt_Total_Capital_%",
        "Liabilities_Assets_%",
        "Debt_EBITDA", "Net_Debt_EBITDA", "Net_Debt_EBITDA_Capex",
        "EBIT_Interest", "EBITDA_Interest",
        "EBITDA_Capex_Interest", "FFO_Interest", "FFO_Debt",
        "Payout_Ratio_%",
    }

    if econ_key in ratio_keys and econ_key in ratios.columns:
        return ratios[econ_key]

    if econ_key == "__effective_tax_rate":
        ibt = num(facts, "income_before_tax")
        tax = num(facts, "income_tax_expense")
        return (tax / ibt * 100).where(ibt.notna() & ibt.ne(0))

    if econ_key == "__fcf":
        return num(facts, "cfo") - num(facts, "capex")

    if econ_key == "__cash_plus_sti":
        return num(facts, "cash") + num(facts, "short_term_investments").fillna(0)

    if econ_key == "__liabilities_plus_equity":
        return num(facts, "liabilities") + num(facts, "equity")

    if econ_key == "__continuing_ops":
        return num(facts, "income_before_tax") - num(facts, "income_tax_expense")

    if econ_key == "__total_op_expenses":
        return (
            num(facts, "cost_of_sales")
            + num(facts, "sga")
            + num(facts, "exploration_expense").fillna(0)
        )

    if econ_key == "__equity_method_inv":
        return (
            num(facts, "investments_associates").fillna(0)
            + num(facts, "investments_jv").fillna(0)
        )

    if econ_key == "__price_close":
        return num(facts, "price_usd")

    if econ_key == "__market_cap_mm":
        price = num(facts, "price_usd")
        shares = num(facts, "diluted_shares")
        return price * shares / 1e6

    if econ_key == "__tev_mm":
        mcap = canonical_fact_series("__market_cap_mm", facts, ratios)
        net_d = num(facts, "net_debt")
        return mcap + net_d * 1000.0

    if econ_key == "__writedown_cf":
        return (
            num(facts, "impairment").fillna(0)
            + num(facts, "impairment_reversal").fillna(0)
        )

    if econ_key == "__bvps":
        eq = num(facts, "common_equity")
        shares = num(facts, "diluted_shares")
        return eq / shares * 1e9

    if econ_key == "__tbv":
        return (
            num(facts, "common_equity")
            - num(facts, "intangibles").fillna(0)
            - num(facts, "goodwill").fillna(0)
        )

    if econ_key.startswith("__"):
        return pd.Series(np.nan, index=facts.index, dtype="float64")

    if econ_key in facts.columns:
        return num(facts, econ_key)

    return pd.Series(np.nan, index=facts.index, dtype="float64")


# ---------------------------------------------------------------------------
# TIKR output builder
# ---------------------------------------------------------------------------

def build_tikr_output(
    facts: pd.DataFrame,
    ratios: pd.DataFrame,
    reference: pd.ExcelFile,
) -> None:
    """Build TIKR-shaped XLSX in USD millions."""
    facts = facts.copy()
    ratios = ratios.copy()

    facts["__key"] = facts["period_end"].map(period_key)
    ratios["__key"] = ratios["period_end"].map(period_key)

    _NO_SCALE = {
        "eps_diluted", "eps_basic", "__dps", "__payout",
        "__price_close", "__bvps", "__tbvps",
        "__effective_tax_rate",
    }

    _SHARES_TO_MILLIONS = {
        "diluted_shares", "shares_outstanding",
    }

    _NEGATE = {
        "cost_of_sales", "sga", "admin_expense",
        "distribution_costs", "exploration_expense",
        "finance_costs", "income_tax_expense",
        "capex", "debt_repaid", "__total_op_expenses",
    }
    _NEGATE_IS_ONLY = {"interest_paid", "taxes_paid"}

    section_headers = {
        "[return]", "[margin]", "[turnover]",
        "[liquidity]", "[leverage]", "[coverage]",
    }

    _SHEET_OVERRIDES = {
        "BS": {
            "inventory": "inventories",
            "minority interest": "minority_interest_bs",
        },
        "Ratios": {"inventory": "Inventory_Turnover"},
    }

    sheet_map = {
        "IS": "TIKR_IS",
        "BS": "TIKR_BS",
        "CF": "TIKR_CF",
        "Ratios": "TIKR_RATIOS",
    }

    with pd.ExcelWriter(OUT_TIKR, engine="openpyxl") as writer:
        for ref_sheet, out_sheet in sheet_map.items():
            ref = pd.read_excel(reference, sheet_name=ref_sheet)
            if "Metric" not in ref.columns:
                raise AssertionError(f"{ref_sheet}: missing 'Metric' column")

            period_columns = [c for c in ref.columns if c != "Metric"]
            result = pd.DataFrame({"Metric": ref["Metric"]})
            is_ratio = (ref_sheet == "Ratios")

            for pcol in period_columns:
                key = period_key(pcol)
                is_ltm = str(pcol).strip().upper() == "LTM"
                if is_ltm:
                    key = "2025-12-31"

                values = []

                for metric in ref["Metric"]:
                    label_norm = normalize_label(metric)

                    if label_norm in section_headers or pd.isna(metric) or str(metric).strip() == "":
                        values.append(np.nan)
                        continue

                    skip_labels = {
                        "yoy %", "gross margin %", "operating margin %",
                        "net margin %", "eps yoy %", "fcf yoy %", "fcf margin %",
                    }
                    if label_norm in skip_labels:
                        values.append(np.nan)
                        continue

                    overrides = _SHEET_OVERRIDES.get(ref_sheet, {})
                    econ_key = overrides.get(label_norm, TIKR_MAPPING.get(label_norm))
                    value = np.nan

                    if econ_key and key:
                        source = ratios if is_ratio else facts
                        source_rows = source[source["__key"].eq(key)]

                        if not source_rows.empty:
                            selected = source_rows.index[0]
                            s = canonical_fact_series(
                                econ_key, facts, ratios,
                                is_ratio_sheet=is_ratio,
                            )
                            value = s.loc[selected]

                    if (
                        not pd.isna(value)
                        and not is_ratio
                        and isinstance(econ_key, str)
                    ):
                        if econ_key in _SHARES_TO_MILLIONS:
                            value = float(value) / 1e6
                        elif econ_key == "__price_close":
                            pass
                        elif econ_key == "__market_cap_mm":
                            pass
                        elif econ_key == "__tev_mm":
                            pass
                        elif econ_key not in _NO_SCALE:
                            value = float(value) * 1000.0

                        should_negate = econ_key in _NEGATE or (
                            econ_key in _NEGATE_IS_ONLY and ref_sheet == "IS"
                        )
                        if should_negate:
                            value = -abs(float(value))

                    values.append(value)

                result[pcol] = values

            result.to_excel(writer, index=False, sheet_name=out_sheet)

            ws = writer.book[out_sheet]
            ws.freeze_panes = "B2"
            ws.column_dimensions["A"].width = 45
            from openpyxl.utils import get_column_letter
            for col_idx in range(2, len(result.columns) + 1):
                ws.column_dimensions[get_column_letter(col_idx)].width = 16

    print(f"  TIKR-shaped XLSX: {OUT_TIKR}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    if not EDGAR.exists():
        raise FileNotFoundError(f"Missing {EDGAR}")
    if not YAHOO.exists():
        raise FileNotFoundError(f"Missing {YAHOO}")

    reference_path = find_existing(REF_CANDIDATES, "TIKR reference")
    reference = pd.ExcelFile(reference_path)

    e = pd.read_csv(EDGAR)
    y = pd.read_csv(YAHOO)

    if len(e) != EXPECTED_ROWS or len(y) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} rows: EDGAR={len(e)}, YAHOO={len(y)}"
        )

    keys = ["fiscal_year", "period", "period_end"]
    for k in keys:
        if k not in e.columns or k not in y.columns:
            raise AssertionError(f"Missing key: {k}")

    e["period_end"] = pd.to_datetime(
        e["period_end"], errors="raise"
    ).dt.strftime("%Y-%m-%d")
    y["period_end"] = pd.to_datetime(
        y["period_end"], errors="raise"
    ).dt.strftime("%Y-%m-%d")

    df = e.merge(y, on=keys, how="left", validate="one_to_one",
                 suffixes=("_edgar", "_yahoo"))

    if len(df) != EXPECTED_ROWS:
        raise AssertionError(f"Merge produced {len(df)} rows, expected {EXPECTED_ROWS}")

    # USD-to-USD comparison: no rate conversion needed

    # ------------------------------------------------------------------
    # Economic facts
    # ------------------------------------------------------------------
    revenue = num(df, "revenue")
    cost_of_sales = num(df, "cost_of_sales")
    gross_profit = num(df, "gross_profit")
    sga = num(df, "sga")
    operating_income = num(df, "operating_income")
    finance_costs = num(df, "finance_costs")
    income_before_tax = num(df, "income_before_tax")
    income_tax = num(df, "income_tax_expense")
    net_income = num(df, "net_income")
    total_da = num(df, "total_da")
    ebitda = num(df, "ebitda")
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
    ar = num(df, "current_trade_receivables")
    inventory = num(df, "inventories")
    ppe = num(df, "ppe_net")
    ap = num(df, "accounts_payable")
    debt = num(df, "total_debt")
    eps = num(df, "eps_diluted")
    fcf = cfo - capex
    ffo = cfo

    out = df[keys].copy()

    # ------------------------------------------------------------------
    # Ratios (all annual, no annualization needed)
    # ------------------------------------------------------------------

    # Margins
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
    out["FCF_Unlevered_Margin_%"] = pct(fcf + finance_costs, revenue)

    # Averages for return/activity ratios
    avg_assets = avg_previous(df, "assets")
    avg_equity = avg_previous(df, "equity")
    avg_common_equity = avg_previous(df, "common_equity")
    avg_ppe = avg_previous(df, "ppe_net")
    avg_ar = avg_previous(df, "current_trade_receivables")
    avg_inventory = avg_previous(df, "inventories")
    avg_ap = avg_previous(df, "accounts_payable")

    # Returns
    out["ROA_%"] = pct(net_income, avg_assets)
    out["ROE_%"] = pct(net_income, avg_equity)
    out["Common_Equity_ROE_%"] = pct(net_income, avg_common_equity)

    tax_rate = div(income_tax, income_before_tax).clip(lower=0, upper=1)
    nopat = operating_income * (1 - tax_rate)
    invested_capital = debt + equity - cash - sti.fillna(0)
    avg_ic = (invested_capital + invested_capital.shift(1)) / 2.0
    out["ROIC_%"] = pct(nopat, avg_ic)

    # Turnover
    out["Asset_Turnover"] = div(revenue, avg_assets)
    out["Fixed_Asset_Turnover"] = div(revenue, avg_ppe)
    out["AR_Turnover"] = div(revenue, avg_ar)
    out["Inventory_Turnover"] = div(cost_of_sales, avg_inventory)
    working_capital = current_assets - current_liabilities
    out["Working_Capital_Turnover"] = div(revenue, working_capital)

    out["DSO"] = div(avg_ar, revenue) * 365.0
    out["DIO"] = div(avg_inventory, cost_of_sales) * 365.0
    out["DPO"] = div(avg_ap, cost_of_sales) * 365.0
    out["CCC"] = out["DSO"] + out["DIO"] - out["DPO"]

    # Liquidity
    out["Current_Ratio"] = div(current_assets, current_liabilities)
    out["Quick_Ratio"] = div(cash + sti.fillna(0) + ar, current_liabilities)
    out["CFO_Current_Liabilities_%"] = div(cfo, current_liabilities)

    # Leverage
    out["Debt_Equity_%"] = pct(debt, equity)
    out["Debt_Total_Capital_%"] = pct(debt, debt + equity)
    out["Liabilities_Assets_%"] = pct(liabilities, assets)

    net_debt = debt - cash - sti.fillna(0)
    out["Debt_EBITDA"] = div(debt, ebitda)
    out["Net_Debt_EBITDA"] = div(net_debt, ebitda)
    out["Net_Debt_EBITDA_Capex"] = div(net_debt, ebitda - capex)

    # Coverage — use interest_paid (CF-based) which matches TIKR's narrower Interest concept
    interest_paid = num(df, "interest_paid")
    out["EBIT_Interest"] = div(operating_income, interest_paid)
    out["EBITDA_Interest"] = div(ebitda, interest_paid)
    out["EBITDA_Capex_Interest"] = div(ebitda - capex, interest_paid)
    out["FFO_Interest"] = div(ffo, interest_paid)
    out["FFO_Debt"] = div(ffo, debt)

    # Market / valuation
    out["Price"] = num(df, "price_usd")
    out["52W_High"] = num(df, "52w_high_usd")
    out["52W_Low"] = num(df, "52w_low_usd")

    # YPF paid no dividends
    out["Payout_Ratio_%"] = np.nan

    for ratio in RATIOS:
        if ratio not in out.columns:
            out[ratio] = np.nan

    out = out[keys + RATIOS]

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    out.to_excel(OUT_XLSX, index=False)

    build_tikr_output(
        facts=df,
        ratios=out,
        reference=reference,
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if len(out) != EXPECTED_ROWS:
        raise AssertionError(f"Output: {len(out)} rows; expected {EXPECTED_ROWS}")

    missing_ratios = [r for r in RATIOS if r not in out.columns]
    if missing_ratios:
        raise AssertionError(f"Missing ratios: {missing_ratios}")

    expected_sheets = {"TIKR_IS", "TIKR_BS", "TIKR_CF", "TIKR_RATIOS"}
    produced = set(pd.ExcelFile(OUT_TIKR).sheet_names)
    if not expected_sheets.issubset(produced):
        raise AssertionError(f"Missing TIKR sheets: {expected_sheets - produced}")

    print("=" * 68)
    print("YPF CATALAXIA RATIOS + TIKR STRUCTURE: PASS")
    print(f"  Rows: {len(out)}")
    print(f"  Ratios: {len(RATIOS)}")
    print(f"  TIKR reference: {reference_path.name}")
    print(f"  Ratios CSV: {OUT_CSV}")
    print(f"  Ratios XLSX: {OUT_XLSX}")
    print(f"  TIKR-shaped XLSX: {OUT_TIKR}")
    print("=" * 68)


if __name__ == "__main__":
    main()
