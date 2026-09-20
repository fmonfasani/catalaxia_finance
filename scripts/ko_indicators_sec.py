import requests

CIK = "0000021344"
URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"

HEADERS = {
    "User-Agent": "BYMAStocks contacto@example.com"
}

data = requests.get(URL, headers=HEADERS, timeout=60).json()
facts = data["facts"]["us-gaap"]


def get_fact(*names):
    for name in names:
        if name in facts and "USD" in facts[name]["units"]:
            return facts[name]["units"]["USD"]
    return []


def get_period_fact(names, start, end, form="10-Q"):
    rows = get_fact(*names)

    matches = [
        x for x in rows
        if x.get("form") == form
        and x.get("start") == start
        and x.get("end") == end
    ]

    if not matches:
        return None

    # último filing disponible para ese período
    matches.sort(key=lambda x: x.get("filed", ""))
    return matches[-1]["val"]


def get_fy_fact(names, end):
    rows = get_fact(*names)

    matches = [
        x for x in rows
        if x.get("form") == "10-K"
        and x.get("end") == end
        and x.get("fp") == "FY"
    ]

    if not matches:
        return None

    matches.sort(key=lambda x: x.get("filed", ""))
    return matches[-1]["val"]


def div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def pct(a):
    return None if a is None else a * 100


REVENUE = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)

GROSS_PROFIT = (
    "GrossProfit",
)

OPERATING_INCOME = (
    "OperatingIncomeLoss",
)

NET_INCOME = (
    "NetIncomeLoss",
    "ProfitLoss",
)

ASSETS = (
    "Assets",
)

CFO = (
    "NetCashProvidedByUsedInOperatingActivities",
)

CAPEX = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
)

DA = (
    "DepreciationDepletionAndAmortization",
    "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    "DepreciationAndAmortization",
)


# ============================================================
# PERÍODOS 2025
# ============================================================

periods = [
    ("2025 Q1", "2025-01-01", "2025-03-28"),
    ("2025 Q2", "2025-03-29", "2025-06-27"),
    ("2025 Q3", "2025-06-28", "2025-09-26"),
]


results = []


for label, start, end in periods:

    revenue = get_period_fact(REVENUE, start, end)
    gross = get_period_fact(GROSS_PROFIT, start, end)
    operating = get_period_fact(OPERATING_INCOME, start, end)
    net = get_period_fact(NET_INCOME, start, end)
    cfo = get_period_fact(CFO, start, end)
    capex = get_period_fact(CAPEX, start, end)

    assets = get_period_fact(
        ASSETS,
        start,
        end
    )

    da = get_period_fact(
        DA,
        start,
        end
    )

    if capex is not None:
        capex = abs(capex)

    fcf = (
        cfo - capex
        if cfo is not None and capex is not None
        else None
    )

    ebitda = (
        operating + da
        if operating is not None and da is not None
        else None
    )

    results.append({
        "Periodo": label,
        "Revenue": revenue,
        "Gross Profit": gross,
        "Gross Margin": pct(div(gross, revenue)),
        "Operating Income": operating,
        "Operating Margin": pct(div(operating, revenue)),
        "Net Income": net,
        "Net Margin": pct(div(net, revenue)),
        "EBITDA": ebitda,
        "EBITDA Margin": pct(div(ebitda, revenue)),
        "CFO": cfo,
        "Capex": capex,
        "FCF": fcf,
        "FCF Margin": pct(div(fcf, revenue)),
        "Assets": assets,
        "Asset Turnover": div(revenue, assets),
    })


# ============================================================
# FY2025
# ============================================================

end = "2025-12-31"

revenue = get_fy_fact(REVENUE, end)
gross = get_fy_fact(GROSS_PROFIT, end)
operating = get_fy_fact(OPERATING_INCOME, end)
net = get_fy_fact(NET_INCOME, end)
cfo = get_fy_fact(CFO, end)
capex = get_fy_fact(CAPEX, end)
assets = get_fy_fact(ASSETS, end)
da = get_fy_fact(DA, end)

if capex is not None:
    capex = abs(capex)

fcf = (
    cfo - capex
    if cfo is not None and capex is not None
    else None
)

ebitda = (
    operating + da
    if operating is not None and da is not None
    else None
)

results.append({
    "Periodo": "2025 FY",
    "Revenue": revenue,
    "Gross Profit": gross,
    "Gross Margin": pct(div(gross, revenue)),
    "Operating Income": operating,
    "Operating Margin": pct(div(operating, revenue)),
    "Net Income": net,
    "Net Margin": pct(div(net, revenue)),
    "EBITDA": ebitda,
    "EBITDA Margin": pct(div(ebitda, revenue)),
    "CFO": cfo,
    "Capex": capex,
    "FCF": fcf,
    "FCF Margin": pct(div(fcf, revenue)),
    "Assets": assets,
    "Asset Turnover": div(revenue, assets),
})


# ============================================================
# RESULTADO
# ============================================================

print()
print("=" * 120)
print("COCA-COLA (KO) — 2025 — SEC EDGAR")
print("=" * 120)

for row in results:

    print()
    print(row["Periodo"])
    print("-" * 60)

    for key, value in row.items():

        if key == "Periodo":
            continue

        if isinstance(value, float):
            print(f"{key:22}: {value:.4f}")

        elif value is None:
            print(f"{key:22}: N/D")

        else:
            print(f"{key:22}: {value:,}")