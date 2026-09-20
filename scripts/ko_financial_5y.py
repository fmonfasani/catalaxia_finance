"""
KO — Financial 5Y desde SEC CompanyFacts
VERSIÓN CORREGIDA DE PERIODIZACIÓN

Períodos:
    2021 Q1
    2021 Q2
    2021 Q3
    2021 FY
    ...
    2025 Q1
    2025 Q2
    2025 Q3
    2025 FY

Reglas:

FLOW:
    Q1 = acumulado Q1
    Q2 = H1 - Q1
    Q3 = 9M - H1
    FY = FY

INSTANT:
    Assets / Cash se toman usando exactamente la fecha
    de cierre del período financiero correspondiente.

IMPORTANTE:
SEC CompanyFacts puede incluir períodos comparativos de ejercicios
anteriores dentro de filings posteriores.

Por eso NO alcanza con fy/fp:
también se selecciona el cierre correcto del ejercicio.
"""

import csv
from datetime import date
from pathlib import Path

import requests


# ============================================================
# CONFIG
# ============================================================

CIK = "0000021344"

YEARS = list(range(2021, 2026))

SEC_URL = (
    f"https://data.sec.gov/api/xbrl/companyfacts/"
    f"CIK{CIK}.json"
)

HEADERS = {
    "User-Agent": (
        "Catalaxia financial research "
        "contact@example.com"
    )
}

OUTPUT_FILE = Path("KO_SEC_financial_5y.csv")


# ============================================================
# SEC DOWNLOAD
# ============================================================

print()
print("=" * 100)
print("KO — SEC COMPANYFACTS")
print("=" * 100)
print()
print("Descargando SEC CompanyFacts...")
print(SEC_URL)

response = requests.get(
    SEC_URL,
    headers=HEADERS,
    timeout=60,
)

response.raise_for_status()

payload = response.json()

US_GAAP = payload["facts"]["us-gaap"]


# ============================================================
# HELPERS
# ============================================================

def days_between(start, end):
    if not start or not end:
        return None

    return (
        date.fromisoformat(end)
        - date.fromisoformat(start)
    ).days


def days(row):
    return days_between(
        row.get("start"),
        row.get("end"),
    )


def value(row):
    if row is None:
        return None

    return row.get("val")


def money(v):
    if v is None:
        return "N/D"

    return f"{v / 1_000_000_000:.3f} B"


def pct(v):
    if v is None:
        return "N/D"

    return f"{v:.4f}"


def margin(numerator, denominator):
    if numerator is None:
        return None

    if denominator in (None, 0):
        return None

    return numerator / denominator * 100


# ============================================================
# CONCEPTS
# ============================================================

def find_concept(*names):

    for name in names:

        if name in US_GAAP:
            return name

    return None


CONCEPTS = {

    "revenue": find_concept(
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ),

    "gross_profit": find_concept(
        "GrossProfit",
    ),

    "operating_income": find_concept(
        "OperatingIncomeLoss",
    ),

    "net_income": find_concept(
        "NetIncomeLoss",
        "ProfitLoss",
    ),

    "da": find_concept(
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
    ),

    "cfo": find_concept(
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),

    "capex": find_concept(
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),

    "assets": find_concept(
        "Assets",
    ),

    "cash": find_concept(
        "CashAndCashEquivalentsAtCarryingValue",
    ),
}


print()
print("=" * 100)
print("CONCEPTOS")
print("=" * 100)

for key, concept in CONCEPTS.items():
    print(
        f"{key:20} : "
        f"{concept if concept else 'NO ENCONTRADO'}"
    )


# ============================================================
# GET ROWS
# ============================================================

def get_rows(concept):

    if not concept:
        return []

    units = US_GAAP[concept].get("units", {})

    if "USD" in units:
        return units["USD"]

    if not units:
        return []

    first_unit = next(iter(units))

    return units[first_unit]


# ============================================================
# FORM FILTERS
# ============================================================

QUARTER_FORMS = (
    "10-Q",
    "10-Q/A",
)

ANNUAL_FORMS = (
    "10-K",
    "10-K/A",
)


# ============================================================
# PERIOD SELECTION
# ============================================================

def select_period_candidate(
    candidates,
    target_year,
    expected_bucket,
):
    """
    Selección crítica.

    CompanyFacts puede contener:

        fy=2021 fp=Q1 end=2020-09-25

como dato comparativo dentro de un filing posterior.

Por eso:

1. filtramos fy/fp/form
2. exigimos end.year == target_year
3. entre los candidatos elegimos el cierre más reciente
4. luego filing más reciente

Esto evita tomar comparativos.
    """

    filtered = []

    for row in candidates:

        end = row.get("end")

        if not end:
            continue

        try:
            end_year = date.fromisoformat(end).year
        except ValueError:
            continue

        if end_year != target_year:
            continue

        filtered.append(row)

    if not filtered:
        return None

    # Primero el cierre fiscal más reciente.
    max_end = max(
        row["end"]
        for row in filtered
    )

    same_end = [
        row
        for row in filtered
        if row["end"] == max_end
    ]

    # Después el filing más reciente.
    same_end.sort(
        key=lambda row: (
            row.get("filed", ""),
            row.get("accn", ""),
        ),
        reverse=True,
    )

    return same_end[0]


# ============================================================
# FLOW — YTD
# ============================================================

def get_ytd(concept, year, bucket):

    rows = get_rows(concept)

    if not rows:
        return None

    target_fp = {
        "Q1": "Q1",
        "H1": "Q2",
        "9M": "Q3",
    }[bucket]

    duration_ranges = {

        "Q1": (70, 110),

        "H1": (160, 200),

        "9M": (240, 290),
    }

    min_days, max_days = duration_ranges[bucket]

    candidates = []

    for row in rows:

        if row.get("form") not in QUARTER_FORMS:
            continue

        if row.get("fy") != year:
            continue

        if row.get("fp") != target_fp:
            continue

        if not row.get("start") or not row.get("end"):
            continue

        d = days(row)

        if d is None:
            continue

        if not (
            min_days <= d <= max_days
        ):
            continue

        candidates.append(row)

    return select_period_candidate(
        candidates,
        year,
        bucket,
    )


# ============================================================
# FLOW — FY
# ============================================================

def get_fy(concept, year):

    rows = get_rows(concept)

    if not rows:
        return None

    candidates = []

    for row in rows:

        if row.get("form") not in ANNUAL_FORMS:
            continue

        if row.get("fy") != year:
            continue

        if row.get("fp") != "FY":
            continue

        if not row.get("start") or not row.get("end"):
            continue

        d = days(row)

        if d is None:
            continue

        if not (
            330 <= d <= 380
        ):
            continue

        candidates.append(row)

    return select_period_candidate(
        candidates,
        year,
        "FY",
    )


# ============================================================
# INSTANT FACT
# ============================================================

def get_instant(
    concept,
    end_date,
    target_year,
):

    rows = get_rows(concept)

    if not rows:
        return None

    candidates = []

    for row in rows:

        if row.get("form") not in (
            "10-Q",
            "10-Q/A",
            "10-K",
            "10-K/A",
        ):
            continue

        if row.get("end") != end_date:
            continue

        # Evitar valores que pertenezcan a otro ejercicio
        if row.get("fy") not in (
            None,
            target_year,
        ):
            continue

        candidates.append(row)

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: (
            row.get("filed", ""),
            row.get("accn", ""),
        ),
        reverse=True,
    )

    return candidates[0]


# ============================================================
# BUILD YEAR
# ============================================================

def build_year(year):

    print()
    print("=" * 100)
    print(f"FY {year}")
    print("=" * 100)

    result = {}

    # --------------------------------------------------------
    # Obtener acumulados
    # --------------------------------------------------------

    raw = {}

    flow_keys = (
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "da",
        "cfo",
        "capex",
    )

    for key in flow_keys:

        concept = CONCEPTS[key]

        raw[key] = {

            "Q1": get_ytd(
                concept,
                year,
                "Q1",
            ),

            "H1": get_ytd(
                concept,
                year,
                "H1",
            ),

            "9M": get_ytd(
                concept,
                year,
                "9M",
            ),

            "FY": get_fy(
                concept,
                year,
            ),
        }

    # --------------------------------------------------------
    # Fecha de cierre usando Revenue
    # --------------------------------------------------------

    revenue_q1 = raw["revenue"]["Q1"]
    revenue_h1 = raw["revenue"]["H1"]
    revenue_9m = raw["revenue"]["9M"]
    revenue_fy = raw["revenue"]["FY"]

    period_end = {

        "Q1": (
            revenue_q1.get("end")
            if revenue_q1
            else None
        ),

        "Q2": (
            revenue_h1.get("end")
            if revenue_h1
            else None
        ),

        "Q3": (
            revenue_9m.get("end")
            if revenue_9m
            else None
        ),

        "FY": (
            revenue_fy.get("end")
            if revenue_fy
            else None
        ),
    }

    # --------------------------------------------------------
    # Inicializar
    # --------------------------------------------------------

    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    ):

        result[period] = {

            "year": year,

            "period": period,

            "period_end": period_end[period],

            "revenue": None,

            "gross_profit": None,

            "operating_income": None,

            "net_income": None,

            "da": None,

            "ebitda": None,

            "cfo": None,

            "capex": None,

            "fcf": None,

            "assets": None,

            "cash": None,
        }

    # --------------------------------------------------------
    # FLOW RECONSTRUCTION
    # --------------------------------------------------------

    for key in flow_keys:

        q1 = value(raw[key]["Q1"])

        h1 = value(raw[key]["H1"])

        m9 = value(raw[key]["9M"])

        fy = value(raw[key]["FY"])

        # Q1
        result["Q1"][key] = q1

        # Q2 = H1 - Q1
        if h1 is not None and q1 is not None:

            result["Q2"][key] = (
                h1 - q1
            )

        # Q3 = 9M - H1
        if m9 is not None and h1 is not None:

            result["Q3"][key] = (
                m9 - h1
            )

        # FY
        result["FY"][key] = fy

    # --------------------------------------------------------
    # CAPEX POSITIVO
    # --------------------------------------------------------

    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    ):

        capex = result[period]["capex"]

        if capex is not None:

            result[period]["capex"] = abs(
                capex
            )

    # --------------------------------------------------------
    # EBITDA
    # --------------------------------------------------------

    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    ):

        op = result[period][
            "operating_income"
        ]

        da = result[period]["da"]

        if op is not None and da is not None:

            result[period]["ebitda"] = (
                op + da
            )

    # --------------------------------------------------------
    # FCF
    # --------------------------------------------------------

    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    ):

        cfo = result[period]["cfo"]

        capex = result[period]["capex"]

        if (
            cfo is not None
            and capex is not None
        ):

            result[period]["fcf"] = (
                cfo - capex
            )

    # --------------------------------------------------------
    # INSTANTS
    # --------------------------------------------------------

    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    ):

        end_date = result[period][
            "period_end"
        ]

        if not end_date:
            continue

        assets_row = get_instant(
            CONCEPTS["assets"],
            end_date,
            year,
        )

        cash_row = get_instant(
            CONCEPTS["cash"],
            end_date,
            year,
        )

        result[period]["assets"] = value(
            assets_row
        )

        result[period]["cash"] = value(
            cash_row
        )

    return result


# ============================================================
# BUILD ALL YEARS
# ============================================================

all_data = []

for year in YEARS:

    year_data = build_year(year)

    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    ):

        row = year_data[period]

        revenue = row["revenue"]

        row["gross_margin"] = margin(
            row["gross_profit"],
            revenue,
        )

        row["operating_margin"] = margin(
            row["operating_income"],
            revenue,
        )

        row["net_margin"] = margin(
            row["net_income"],
            revenue,
        )

        row["ebitda_margin"] = margin(
            row["ebitda"],
            revenue,
        )

        row["fcf_margin"] = margin(
            row["fcf"],
            revenue,
        )

        if (
            revenue is not None
            and row["assets"] not in (
                None,
                0,
            )
        ):

            row["asset_turnover"] = (
                revenue / row["assets"]
            )

        else:

            row["asset_turnover"] = None

        all_data.append(row)


# ============================================================
# PRINT
# ============================================================

print()
print()
print("=" * 140)
print("KO — DATASET FINANCIERO 2021-2025")
print("=" * 140)

for row in all_data:

    print()
    print(
        f"{row['year']} {row['period']}"
        f" | cierre={row['period_end']}"
    )

    print(
        f"Revenue            : "
        f"{money(row['revenue'])}"
    )

    print(
        f"Gross Profit       : "
        f"{money(row['gross_profit'])}"
    )

    print(
        f"Gross Margin       : "
        f"{pct(row['gross_margin'])}%"
    )

    print(
        f"Operating Income   : "
        f"{money(row['operating_income'])}"
    )

    print(
        f"Operating Margin   : "
        f"{pct(row['operating_margin'])}%"
    )

    print(
        f"Net Income         : "
        f"{money(row['net_income'])}"
    )

    print(
        f"Net Margin         : "
        f"{pct(row['net_margin'])}%"
    )

    print(
        f"D&A                : "
        f"{money(row['da'])}"
    )

    print(
        f"EBITDA             : "
        f"{money(row['ebitda'])}"
    )

    print(
        f"EBITDA Margin      : "
        f"{pct(row['ebitda_margin'])}%"
    )

    print(
        f"CFO                : "
        f"{money(row['cfo'])}"
    )

    print(
        f"Capex              : "
        f"{money(row['capex'])}"
    )

    print(
        f"FCF                : "
        f"{money(row['fcf'])}"
    )

    print(
        f"FCF Margin         : "
        f"{pct(row['fcf_margin'])}%"
    )

    print(
        f"Assets             : "
        f"{money(row['assets'])}"
    )

    print(
        f"Cash               : "
        f"{money(row['cash'])}"
    )

    print(
        f"Asset Turnover     : "
        f"{pct(row['asset_turnover'])}"
    )


# ============================================================
# CSV
# ============================================================

CSV_COLUMNS = [

    "year",
    "period",
    "period_end",

    "revenue",
    "gross_profit",
    "gross_margin",

    "operating_income",
    "operating_margin",

    "net_income",
    "net_margin",

    "da",
    "ebitda",
    "ebitda_margin",

    "cfo",
    "capex",
    "fcf",
    "fcf_margin",

    "assets",
    "cash",
    "asset_turnover",
]


with OUTPUT_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=CSV_COLUMNS,
    )

    writer.writeheader()

    for row in all_data:

        writer.writerow(row)


# ============================================================
# VALIDACIÓN
# ============================================================

expected_rows = 20
actual_rows = len(all_data)

expected_periods = {
    (year, period)
    for year in YEARS
    for period in (
        "Q1",
        "Q2",
        "Q3",
        "FY",
    )
}

actual_periods = {
    (
        row["year"],
        row["period"],
    )
    for row in all_data
}


periods_ok = (
    expected_periods
    == actual_periods
)


dates_ok = True

for row in all_data:

    end = row["period_end"]

    if not end:
        dates_ok = False
        continue

    end_year = date.fromisoformat(end).year

    if end_year != row["year"]:
        dates_ok = False

        print(
            "ERROR PERIODIZACIÓN:",
            row["year"],
            row["period"],
            end,
        )


print()
print("=" * 100)
print("VALIDACIÓN FINAL")
print("=" * 100)

print(
    f"Filas esperadas : {expected_rows}"
)

print(
    f"Filas obtenidas : {actual_rows}"
)

print(
    f"Períodos        : "
    f"{'PASS' if periods_ok else 'FAIL'}"
)

print(
    f"Fechas fiscales : "
    f"{'PASS' if dates_ok else 'FAIL'}"
)

if (
    actual_rows == expected_rows
    and periods_ok
    and dates_ok
):

    print()
    print("RESULTADO       : PASS")

else:

    print()
    print("RESULTADO       : FAIL")


print()
print(
    f"CSV generado: "
    f"{OUTPUT_FILE.resolve()}"
)
print()