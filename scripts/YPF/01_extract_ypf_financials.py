#!/usr/bin/env python3
"""
Catalaxia / YPF — SEC financial extractor (IFRS)

Extracts financial facts from SEC CompanyFacts JSON for YPF S.A.
YPF reports under IFRS (namespace ifrs-full) via 20-F (annual only).
No quarterly data exists in CompanyFacts — only FY periods.

Fiscal year-end: always December 31.
Currency: SEC data is in ARS for FY2017-2021, USD for FY2022-2025.
We extract exclusively from USD rows (available FY2020-2025 via
comparative restatements in 20-F filings).

FY2020 is exported to Calculation_Buffer for 5Y lookback calculations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


CIK = "0000904851"
TICKER = "YPF"
NAMESPACE = "ifrs-full"

START_YEAR = 2020
END_YEAR = 2025

SEC_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"

BASE = Path(__file__).resolve().parent
RAW_DIR = BASE / "data" / "raw" / "companyfacts"
RAW_FILE = RAW_DIR / f"CIK{CIK}.json"

OUT_CSV = BASE / "YPF_FINANCIAL_INPUTS_2021_2025.csv"
OUT_XLSX = BASE / "YPF_FINANCIAL_INPUTS_2021_2025.xlsx"

USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Catalaxia Research contact@example.com",
)


# ---------------------------------------------------------------------------
# IFRS FLOW CONCEPTS (Income Statement + Cash Flow)
# ---------------------------------------------------------------------------

FLOW_CONCEPTS = {
    "revenue": [
        "Revenue",
        "RevenueFromContractsWithCustomers",
    ],
    "cost_of_sales": [
        "CostOfSales",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "admin_expense": [
        "AdministrativeExpense",
    ],
    "distribution_costs": [
        "DistributionCosts",
    ],
    "exploration_expense": [
        "ExpenseArisingFromExplorationForAndEvaluationOfMineralResources",
    ],
    "operating_income": [
        "ProfitLossFromOperatingActivities",
    ],
    "finance_costs": [
        "FinanceCosts",
    ],
    "finance_income": [
        "FinanceIncome",
    ],
    "share_of_associates": [
        "ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod",
    ],
    "income_before_tax": [
        "ProfitLossBeforeTax",
    ],
    "income_tax_expense": [
        "IncomeTaxExpenseContinuingOperations",
    ],
    "net_income_to_company": [
        "ProfitLoss",
    ],
    "minority_interest_is": [
        "ProfitLossAttributableToNoncontrollingInterests",
    ],
    "net_income": [
        "ProfitLossAttributableToOwnersOfParent",
    ],
    "eps_diluted": [
        "DilutedEarningsLossPerShare",
    ],
    "eps_basic": [
        "BasicEarningsLossPerShare",
    ],
    "diluted_shares": [
        "WeightedAverageShares",
    ],
    "da_depreciation": [
        "AdjustmentsForDepreciationExpense",
    ],
    "da_amortization": [
        "AdjustmentsForAmortisationExpense",
    ],
    "cfo": [
        "CashFlowsFromUsedInOperatingActivities",
    ],
    "capex": [
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
        "PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets",
    ],
    "cash_from_investing": [
        "CashFlowsFromUsedInInvestingActivities",
    ],
    "cash_from_financing": [
        "CashFlowsFromUsedInFinancingActivities",
    ],
    "debt_issued": [
        "ProceedsFromBorrowingsClassifiedAsFinancingActivities",
    ],
    "debt_repaid": [
        "RepaymentsOfBorrowingsClassifiedAsFinancingActivities",
    ],
    "dividends_paid": [
        "DividendsPaidClassifiedAsFinancingActivities",
    ],
    "interest_paid": [
        "InterestPaidClassifiedAsFinancingActivities",
    ],
    "taxes_paid": [
        "IncomeTaxesPaidClassifiedAsOperatingActivities",
    ],
    "fx_effect": [
        "EffectOfExchangeRateChangesOnCashAndCashEquivalents",
    ],
    "net_change_cash": [
        "IncreaseDecreaseInCashAndCashEquivalents",
    ],
    "impairment": [
        "ImpairmentLossRecognisedInProfitOrLoss",
    ],
    "impairment_reversal": [
        "ImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss",
    ],
    "stock_comp": [
        "AdjustmentsForSharebasedPayments",
        "SharebasedPaymentArrangementsExpense",
    ],
    "gains_losses_monetary": [
        "GainsLossesOnNetMonetaryPosition",
    ],
    "change_ar": [
        "AdjustmentsForDecreaseIncreaseInTradeAccountReceivable",
    ],
    "change_inventory": [
        "AdjustmentsForDecreaseIncreaseInInventories",
    ],
    "change_ap": [
        "AdjustmentsForIncreaseDecreaseInTradeAccountPayable",
    ],
    "r_and_d": [
        "ResearchAndDevelopmentExpense",
    ],
}


# ---------------------------------------------------------------------------
# IFRS STOCK CONCEPTS (Balance Sheet — instant values)
# ---------------------------------------------------------------------------

STOCK_CONCEPTS = {
    "assets": [
        "Assets",
    ],
    "current_assets": [
        "CurrentAssets",
    ],
    "noncurrent_assets": [
        "NoncurrentAssets",
    ],
    "cash": [
        "CashAndCashEquivalents",
    ],
    "short_term_investments": [
        "CurrentFinancialAssets",
    ],
    "current_trade_receivables": [
        "CurrentTradeReceivables",
    ],
    "inventories": [
        "Inventories",
    ],
    "ppe_net": [
        "PropertyPlantAndEquipment",
    ],
    "intangibles": [
        "IntangibleAssetsOtherThanGoodwill",
    ],
    "goodwill": [
        "Goodwill",
    ],
    "current_liabilities": [
        "CurrentLiabilities",
    ],
    "noncurrent_liabilities": [
        "NoncurrentLiabilities",
    ],
    "liabilities": [
        "Liabilities",
    ],
    "accounts_payable": [
        "TradeAndOtherCurrentPayablesToTradeSuppliers",
        "TradeAndOtherCurrentPayables",
    ],
    "borrowings": [
        "Borrowings",
    ],
    "lt_borrowings": [
        "NoncurrentBorrowings",
        "LongtermBorrowings",
    ],
    "st_borrowings": [
        "CurrentBorrowings",
        "ShorttermBorrowings",
    ],
    "lease_liabilities": [
        "LeaseLiabilities",
    ],
    "current_lease_liabilities": [
        "CurrentLeaseLiabilities",
    ],
    "noncurrent_lease_liabilities": [
        "NoncurrentLeaseLiabilities",
    ],
    "equity": [
        "Equity",
    ],
    "common_equity": [
        "EquityAttributableToOwnersOfParent",
    ],
    "minority_interest_bs": [
        "NoncontrollingInterests",
    ],
    "issued_capital": [
        "IssuedCapital",
    ],
    "retained_earnings": [
        "RetainedEarnings",
    ],
    "treasury_stock": [
        "TreasuryShares",
    ],
    "comprehensive_income_other": [
        "AccumulatedOtherComprehensiveIncome",
    ],
    "deferred_tax_liabilities": [
        "DeferredTaxLiabilities",
    ],
    "deferred_tax_assets": [
        "DeferredTaxAssets",
    ],
    "investments_associates": [
        "InvestmentsInAssociates",
    ],
    "investments_jv": [
        "InvestmentsInJointVentures",
    ],
    "noncurrent_provisions": [
        "NoncurrentProvisions",
    ],
    "current_provisions": [
        "CurrentProvisions",
    ],
    "noncurrent_financial_assets": [
        "NoncurrentFinancialAssets",
    ],
    "shares_outstanding": [
        "NumberOfSharesIssued",
    ],
}


# ---------------------------------------------------------------------------
# SEC data loading
# ---------------------------------------------------------------------------

def load_companyfacts() -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_FILE.exists():
        return json.loads(RAW_FILE.read_text(encoding="utf-8"))

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }

    response = requests.get(SEC_URL, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    RAW_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    return data


def concept_rows(data: dict, concept: str) -> list[dict]:
    node = (
        data
        .get("facts", {})
        .get(NAMESPACE, {})
        .get(concept)
    )

    if not node:
        return []

    result = []
    for unit, rows in node.get("units", {}).items():
        for row in rows:
            item = dict(row)
            item["_concept"] = concept
            item["_unit"] = unit
            result.append(item)

    return result


def value(row: Optional[dict]):
    if row is None:
        return None
    try:
        return float(row["val"])
    except (KeyError, TypeError, ValueError):
        return None


def duration_days(row: dict) -> Optional[int]:
    start = row.get("start")
    end = row.get("end")
    if not start or not end:
        return None
    return (pd.Timestamp(end) - pd.Timestamp(start)).days + 1


# ---------------------------------------------------------------------------
# PERIOD SELECTORS — simplified for annual-only 20-F filings
# ---------------------------------------------------------------------------

def select_fy_fact(
    rows: list[dict],
    year: int,
    unit_filter: str = "USD",
) -> Optional[dict]:
    expected_end = f"{year}-12-31"

    candidates = []
    for row in rows:
        if row.get("end") != expected_end:
            continue
        if row.get("form") not in {"20-F", "20-F/A"}:
            continue
        if row.get("_unit") != unit_filter:
            continue

        d = duration_days(row)
        if d is not None and d < 300:
            continue

        candidates.append((
            str(row.get("filed", "")),
            row,
        ))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


def select_stock_fact(
    rows: list[dict],
    year: int,
    unit_filter: str = "USD",
) -> Optional[dict]:
    expected_end = f"{year}-12-31"

    candidates = []
    for row in rows:
        if row.get("end") != expected_end:
            continue
        if row.get("form") not in {"20-F", "20-F/A"}:
            continue
        if row.get("_unit") != unit_filter:
            continue

        candidates.append((
            str(row.get("filed", "")),
            row,
        ))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


# ---------------------------------------------------------------------------
# FACT HELPERS
# ---------------------------------------------------------------------------

def select_flow(
    data: dict,
    concepts: list[str],
    year: int,
) -> Optional[dict]:
    for concept in concepts:
        rows = concept_rows(data, concept)
        row = select_fy_fact(rows, year, "USD")
        if row is not None:
            return row
    return None


def select_flow_eps(
    data: dict,
    concepts: list[str],
    year: int,
) -> Optional[dict]:
    for concept in concepts:
        rows = concept_rows(data, concept)
        row = select_fy_fact(rows, year, "USD/shares")
        if row is not None:
            return row
    return None


def select_flow_shares(
    data: dict,
    concepts: list[str],
    year: int,
) -> Optional[dict]:
    for concept in concepts:
        rows = concept_rows(data, concept)
        row = select_fy_fact(rows, year, "shares")
        if row is not None:
            return row
    return None


def select_stock(
    data: dict,
    concepts: list[str],
    year: int,
) -> Optional[dict]:
    for concept in concepts:
        rows = concept_rows(data, concept)
        row = select_stock_fact(rows, year, "USD")
        if row is not None:
            return row
    return None


def select_stock_shares(
    data: dict,
    concepts: list[str],
    year: int,
) -> Optional[dict]:
    for concept in concepts:
        rows = concept_rows(data, concept)
        row = select_stock_fact(rows, year, "shares")
        if row is not None:
            return row
    return None


def fact_meta(row: Optional[dict]) -> dict:
    if row is None:
        return {}
    return {
        "concept": row.get("_concept"),
        "unit": row.get("_unit"),
        "start": row.get("start"),
        "end": row.get("end"),
        "fy": row.get("fy"),
        "fp": row.get("fp"),
        "form": row.get("form"),
        "filed": row.get("filed"),
        "accn": row.get("accn"),
    }


def usd_billions(x: Optional[float]):
    if x is None:
        return None
    return x / 1_000_000_000


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------

def add_source_columns(record: dict, name: str, row: Optional[dict]):
    meta = fact_meta(row)
    record[f"{name}_source_concept"] = meta.get("concept")
    record[f"{name}_source_unit"] = meta.get("unit")
    record[f"{name}_source_start"] = meta.get("start")
    record[f"{name}_source_end"] = meta.get("end")
    record[f"{name}_source_fy"] = meta.get("fy")
    record[f"{name}_source_fp"] = meta.get("fp")
    record[f"{name}_source_form"] = meta.get("form")
    record[f"{name}_source_filed"] = meta.get("filed")


def build_record(data: dict, year: int) -> dict:
    record = {
        "ticker": TICKER,
        "cik": CIK,
        "fiscal_year": year,
        "period": "FY",
        "period_end": f"{year}-12-31",
        "source": "SEC_EDGAR_COMPANYFACTS",
    }

    # --- Flow concepts ---
    for name, concepts in FLOW_CONCEPTS.items():
        if name in {"eps_diluted", "eps_basic"}:
            row = select_flow_eps(data, concepts, year)
            v = value(row)
            record[name] = v
        elif name == "diluted_shares":
            row = select_flow_shares(data, concepts, year)
            v = value(row)
            record[name] = v
        else:
            row = select_flow(data, concepts, year)
            v = value(row)
            record[name] = usd_billions(v)

        add_source_columns(record, name, row)

    # --- Stock concepts ---
    for name, concepts in STOCK_CONCEPTS.items():
        if name == "shares_outstanding":
            row = select_stock_shares(data, concepts, year)
            v = value(row)
            record[name] = v
        else:
            row = select_stock(data, concepts, year)
            v = value(row)
            record[name] = usd_billions(v)

        add_source_columns(record, name, row)

    # --- Derived fields ---
    # SG&A = AdminExpense + DistributionCosts
    admin = record.get("admin_expense")
    dist = record.get("distribution_costs")
    if admin is not None or dist is not None:
        record["sga"] = (admin or 0) + (dist or 0)
    else:
        record["sga"] = None

    # Total D&A
    dep = record.get("da_depreciation")
    amort = record.get("da_amortization")
    if dep is not None or amort is not None:
        record["total_da"] = (dep or 0) + (amort or 0)
    else:
        record["total_da"] = None

    # EBITDA
    op = record.get("operating_income")
    da = record.get("total_da")
    if op is not None and da is not None:
        record["ebitda"] = op + da
    else:
        record["ebitda"] = None

    # Total debt
    borr = record.get("borrowings")
    lt = record.get("lt_borrowings")
    st = record.get("st_borrowings")
    if borr is not None:
        record["total_debt"] = borr
    elif lt is not None or st is not None:
        record["total_debt"] = (lt or 0) + (st or 0)
    else:
        record["total_debt"] = None

    # FCF
    cfo_val = record.get("cfo")
    capex_val = record.get("capex")
    if cfo_val is not None and capex_val is not None:
        record["fcf"] = cfo_val - capex_val
    else:
        record["fcf"] = None

    # Net debt
    total_debt = record.get("total_debt")
    cash_val = record.get("cash")
    sti = record.get("short_term_investments")
    if total_debt is not None and cash_val is not None:
        record["net_debt"] = total_debt - cash_val - (sti or 0)
    else:
        record["net_debt"] = None

    # Liabilities fallback
    if record.get("liabilities") is None:
        a = record.get("assets")
        eq = record.get("equity")
        if a is not None and eq is not None:
            record["liabilities"] = a - eq
            record["liabilities_source_concept"] = "DERIVED:Assets-Equity"

    return record


# ---------------------------------------------------------------------------
# EXCHANGE RATE EXTRACTION
# ---------------------------------------------------------------------------

def extract_exchange_rates(data: dict) -> dict:
    """Extract closing ARS/USD exchange rates from SEC filings."""
    rows = concept_rows(data, "ClosingForeignExchangeRate")
    rates = {}
    for row in rows:
        if row.get("_unit") != "Rate":
            continue
        end = row.get("end", "")
        if not end.endswith("-12-31"):
            continue
        year = int(end[:4])
        filed = str(row.get("filed", ""))
        if year not in rates or filed > rates[year][0]:
            rates[year] = (filed, float(row["val"]))
    return {y: v[1] for y, v in rates.items()}


def derive_implied_rates(data: dict) -> dict:
    """Derive ARS/USD rates from overlapping ARS/USD Revenue values."""
    rates = {}
    for unit_label in ["ARS", "USD"]:
        for concept in ["Revenue"]:
            node = (
                data.get("facts", {})
                .get(NAMESPACE, {})
                .get(concept, {})
                .get("units", {})
                .get(unit_label, [])
            )
            for row in node:
                end = row.get("end", "")
                if not end.endswith("-12-31"):
                    continue
                year = int(end[:4])
                d = duration_days(row)
                if d is not None and d < 300:
                    continue
                key = (year, unit_label)
                filed = str(row.get("filed", ""))
                if key not in rates or filed > rates[key][0]:
                    rates[key] = (filed, float(row["val"]))

    implied = {}
    for year in range(2017, 2026):
        ars_key = (year, "ARS")
        usd_key = (year, "USD")
        if ars_key in rates and usd_key in rates:
            ars_val = rates[ars_key][1]
            usd_val = rates[usd_key][1]
            if usd_val != 0:
                implied[year] = ars_val / usd_val

    return implied


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate(records: list[dict]):
    expected = {(year, "FY") for year in range(2021, 2026)}
    actual = {(int(r["fiscal_year"]), r["period"]) for r in records}

    if actual != expected:
        raise AssertionError(
            f"Period set incorrect. Missing/extra: {expected ^ actual}"
        )

    for r in records:
        if r.get("revenue") is None:
            raise AssertionError(
                f"FY{r['fiscal_year']}: Revenue is NULL"
            )

    if len(records) != 5:
        raise AssertionError(f"Expected 5 rows, got {len(records)}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    data = load_companyfacts()

    buffer_2020 = build_record(data, 2020)

    records = []
    for year in range(2021, END_YEAR + 1):
        records.append(build_record(data, year))

    validate(records)

    # Exchange rates for downstream ARS conversion
    closing_rates = extract_exchange_rates(data)
    implied_rates = derive_implied_rates(data)
    all_rates = {**implied_rates, **closing_rates}

    df = pd.DataFrame(records)
    df = df.sort_values("fiscal_year")

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="YPF_Financials", index=False)

        pd.DataFrame([buffer_2020]).to_excel(
            writer, sheet_name="Calculation_Buffer", index=False
        )

        rates_df = pd.DataFrame([
            {"year": y, "ars_per_usd": r, "source": "SEC"}
            for y, r in sorted(all_rates.items())
        ])
        rates_df.to_excel(
            writer, sheet_name="Exchange_Rates", index=False
        )

    print()
    print("=" * 46)
    print("YPF SEC EXTRACTION (IFRS)")
    print("=" * 46)
    print(f"Rows: {len(df)}")
    print(f"CSV:  {OUT_CSV.resolve()}")
    print(f"XLSX: {OUT_XLSX.resolve()}")
    print()
    print("PERIODS:")
    for row in df.itertuples():
        print(
            f"  {int(row.fiscal_year)} {row.period} "
            f"{row.period_end}  Revenue={row.revenue}"
        )

    print()
    if all_rates:
        print("EXCHANGE RATES (ARS/USD):")
        for y in sorted(all_rates):
            print(f"  {y}: {all_rates[y]:.2f}")

    print()
    print("PERIOD VALIDATION: PASS")
    print("=" * 46)


if __name__ == "__main__":
    main()
