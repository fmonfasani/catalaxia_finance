"""
Calcular Payout Ratio — todas las fuentes para BYMA (56) y ADR (9).

BYMA:
  Primario: YF CashDividendsPaid / CNV NetIncome anual (suma 4 trimestres)
  Fallback: 18 tickers sin YF Dividends → solo reporte

ADR:
  Primario (ground truth): EDGAR IFRS Dividends / ProfitLoss
  Secundario: CNV FT-339 DividendAmount / (CNV NetIncome × escala)
  Validación cruzada entre ambas fuentes
"""
import sqlite3
from pathlib import Path
from collections import defaultdict

DB = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "screener.db"
con = sqlite3.connect(DB)
cur = con.cursor()

ADR_9 = ('GGAL','BBAR','CEPU','CRESY','EDN','LOMA','PAM','SUPV','TEO')

# EDGAR IFRS tag priority for each ADR (best tag known to have data)
ADR_DIV_TAG = {
    'GGAL': 'DividendsPaidOrdinaryShares',
    'BBAR': 'DividendsPaid',
    'CEPU': 'DividendsPaidClassifiedAsFinancingActivities',
    'CRESY': 'DividendsPaid',         # pre-2022; post-2022 uses DividendsPaidClassifiedAsFinancingActivities
    'EDN': None,                      # NO dividend tags found
    'LOMA': 'DividendsPaid',
    'PAM': 'DividendsPaid',
    'SUPV': 'DividendsPaid',
    'TEO': 'DividendsRecognisedAsDistributionsToOwnersOfParent',
}

ADR_FYE = {'CRESY':'06-30'}  # default 12-31

# ── helpers ──────────────────────────────────────────────────────────
def safe_div(a, b):
    return a / b if b and b != 0 else None

def parse_year(pe):
    if not pe: return None
    return str(pe)[:4]

def is_fye(pe, ticker):
    """Check if period_end is fiscal year end for this ticker"""
    s = str(pe)
    fye = ADR_FYE.get(ticker, '12-31')
    return s.endswith(f'-{fye}') or s.endswith('-12-31') or s.endswith('-06-30')

def sum_quarterly_to_annual(data):
    """Sum quarterly NI values into annual totals.
    data: dict {period_end: valor}
    returns: dict {year: annual_total}
    """
    annual = defaultdict(float)
    for pe, val in data.items():
        yr = parse_year(pe)
        if yr:
            annual[yr] += val
    return dict(annual)

# ═══════════════════════════════════════════════════════════════════════
# 1. BYMA Payout
# ═══════════════════════════════════════════════════════════════════════
print("=" * 90)
print("PAYOUT BYMA (56)")
print("=" * 90)

# Pre-load all BYMA tickers
cur.execute("SELECT ticker_ppal FROM empresas WHERE grupo='byma_yf'")
all_byma = [r[0] for r in cur.fetchall()]

# Pre-load CNV NetIncome for all BYMA: {ticker: {period_end: valor}}
cnv_ni_byma = {}
for t in all_byma:
    cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto='NetIncome' AND fuente='cnv-aif2' ORDER BY period_end", (t,))
    cnv_ni_byma[t] = {r[0]: r[1] for r in cur.fetchall()}

# Pre-load YF Dividends for all BYMA: {ticker: {year: val}}
yf_div_byma = {}
cur.execute("""
    SELECT e.ticker_ppal, f.period_end, f.val
    FROM facts f
    JOIN empresas e ON f.cik = e.cik
    WHERE f.taxonomia = 'yfinance' AND f.concepto = 'Dividends' AND f.val IS NOT NULL
    ORDER BY e.ticker_ppal, f.period_end
""")
for t, pe, val in cur.fetchall():
    yr = parse_year(pe)
    if yr:
        yf_div_byma.setdefault(t, {})[yr] = abs(val)

# Pre-load CNV ResultadosNoAsignados for RE-derived method
cnv_re_byma = {}
for t in all_byma:
    cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto='ResultadosNoAsignados' AND fuente='cnv-aif2' ORDER BY period_end", (t,))
    cnv_re_byma[t] = {r[0]: r[1] for r in cur.fetchall()}

print(f"{'Ticker':<8} {'Method':<12} {'Year':>5} {'Dividends':>18} {'NetIncome':>18} {'Payout':>8} {'Source':<20}")
print("-" * 95)

for t in sorted(all_byma):
    yf_div = yf_div_byma.get(t, {})
    cnv_ni = cnv_ni_byma.get(t, {})
    cnv_re = cnv_re_byma.get(t, {})

    # Annual NI from CNV (sum of 4 quarters)
    cnv_ni_annual = sum_quarterly_to_annual(cnv_ni)

    if yf_div:
        # Method 1: YF Dividends / CNV NetIncome
        for yr in sorted(yf_div.keys()):
            div_val = yf_div[yr]
            ni = cnv_ni_annual.get(yr)

            if ni:
                payout_raw = safe_div(div_val, ni)
                # Auto-detect CNV NI units
                if payout_raw and 0.01 < payout_raw < 5:
                    method = 'YF/CNV-ARS'
                    source_detail = f'YF Div / CNV NI'
                    payout = payout_raw
                elif payout_raw and payout_raw >= 50:
                    method = 'YF/CNV-thou'
                    payout = safe_div(div_val, ni * 1000)
                    source_detail = f'YF Div / CNV NI×1000'
                else:
                    method = 'YF/CNV'
                    payout = payout_raw
                    source_detail = f'YF Div / CNV NI'

                if payout and payout < 5:
                    print(f"{t:<8} {method:<12} {yr:>5} {div_val:>18,.0f} {ni:>18,.0f} {payout:>7.1%} {source_detail:<20}")
    else:
        # Method 2 (fallback): RE-derived
        # Note: RE-derived doesn't work well in hyperinflation. Report only.
        print(f"{t:<8} {'NO-DATA':<12} {'':5} {'':>18} {'':>18} {'  N/A':>8} {'No YF Dividends, RE unreliable':<20}")

print()

# ═══════════════════════════════════════════════════════════════════════
# 2. ADR Payout — EDGAR IFRS (ground truth)
# ═══════════════════════════════════════════════════════════════════════
print("=" * 90)
print("PAYOUT ADR (9) — EDGAR IFRS")
print("=" * 90)

ADR_CIKS = {
    'GGAL': '0001114700', 'BBAR': '0000913059', 'CEPU': '0001717161',
    'CRESY': '0001034957', 'EDN': '0001395213', 'LOMA': '0001711375',
    'PAM': '0001469395', 'SUPV': '0001517399', 'TEO': '0000932470'
}

# Also try alternative tags for each ADR
ALT_DIV_TAGS = [
    'DividendsPaid',
    'DividendsPaidOrdinaryShares',
    'DividendsRecognisedAsDistributionsToOwnersOfParent',
    'DividendsPaidClassifiedAsFinancingActivities',
    'DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities',
]

print(f"{'Ticker':<8} {'Tag':<50} {'Year':>5} {'Dividends':>18} {'ProfitLoss':>18} {'Payout':>8}")
print("-" * 115)

for t in sorted(ADR_9):
    cik = ADR_CIKS[t]
    fye = ADR_FYE.get(t, '12-31')

    # Get ProfitLoss annual values
    cur.execute("""
        SELECT period_end, val FROM facts
        WHERE cik=? AND taxonomia='ifrs-full' AND tag='ProfitLoss'
        ORDER BY period_end
    """, (cik,))
    pl_rows = cur.fetchall()

    # Group ProfitLoss by fiscal year (take last/cumulative value)
    pl_annual = {}
    for pe, val in pl_rows:
        yr = parse_year(pe)
        if yr and is_fye(pe, t):
            if yr not in pl_annual or str(pe) > str(pl_annual[yr][0]):
                pl_annual[yr] = (pe, val)

    # Strategy: find the best tag with the most valid payout years
    best_tag = None
    best_years = {}
    for tag in ([ADR_DIV_TAG[t]] + ALT_DIV_TAGS if ADR_DIV_TAG[t] else ALT_DIV_TAGS):
        cur.execute("""
            SELECT period_end, val FROM facts
            WHERE cik=? AND taxonomia='ifrs-full' AND tag=?
            ORDER BY period_end
        """, (cik, tag))
        div_rows = cur.fetchall()
        if not div_rows:
            continue

        div_by_fy = defaultdict(float)
        for pe, val in div_rows:
            yr = parse_year(pe)
            if yr:
                div_by_fy[yr] += val

        valid = {}
        for yr in sorted(div_by_fy.keys()):
            pl_info = pl_annual.get(yr)
            if pl_info:
                _, pl_val = pl_info
                payout = safe_div(abs(div_by_fy[yr]), pl_val)
                if payout and payout < 5:
                    valid[yr] = payout
        if len(valid) > len(best_years):
            best_years = valid
            best_tag = tag
            best_div_data = div_by_fy

    any_printed = False
    if best_tag:
        for yr in sorted(best_years.keys()):
            div_val = best_div_data[yr]
            _, pl_val = pl_annual[yr]
            payout = best_years[yr]
            print(f"{t:<8} {best_tag:<50} {yr:>5} {abs(div_val):>18,.0f} {pl_val:>18,.0f} {payout:>7.1%}")
            any_printed = True
    if not any_printed and t == 'EDN':
        print(f"{t:<8} {'NO DIVIDEND TAGS IN EDGAR':<50} {'':>5} {'NO DATA':>18} {'':>18} {'N/A':>8}")
    elif not any_printed:
        print(f"{t:<8} {'NO VALID DIV/PL COMBINATION':<50} {'':>5} {'':>18} {'':>18} {'N/A':>8}")

print()

# ═══════════════════════════════════════════════════════════════════════
# 3. ADR Payout — CNV FT-339 (cross-validation)
# ═══════════════════════════════════════════════════════════════════════
print("=" * 90)
print("ADR PAYOUT — CNV FT-339 DividendAmount / NetIncome")
print("=" * 90)

print(f"{'Ticker':<8} {'Year':>5} {'Dividend':>18} {'NetIncome':>18} {'Scale':>8} {'Payout':>8} {'Note':<20}")
print("-" * 90)

for t in sorted(ADR_9):
    cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto='DividendAmount' AND fuente='cnv-adr' ORDER BY period_end", (t,))
    div_rows = cur.fetchall()

    if not div_rows:
        print(f"{t:<8} {'':>5} {'NO FT-339 DATA':>18} {'':>18} {'':>8} {'N/A':>8} {'CNV no tiene DividendAmount':<20}")
        continue

    cur.execute("SELECT period_end, valor FROM cnv_estados WHERE ticker=? AND concepto='NetIncome' AND fuente='cnv-adr' ORDER BY period_end", (t,))
    ni_rows = cur.fetchall()
    cnv_ni = {r[0]: r[1] for r in ni_rows}
    cnv_ni_annual = sum_quarterly_to_annual(cnv_ni)

    # Group dividends by year
    div_by_year = defaultdict(list)
    for pe, val in div_rows:
        yr = parse_year(pe)
        if yr:
            div_by_year[yr].append((pe, val))

    for yr in sorted(div_by_year.keys()):
        div_total = sum(abs(v) for _, v in div_by_year[yr])
        ni = cnv_ni_annual.get(yr)

        if not ni:
            continue

        # Auto-detect scale
        for scale in [1, 1000, 1_000_000]:
            payout = safe_div(div_total, ni * scale)
            if payout and 0.001 < payout < 5:
                scale_note = f'×{scale:,}' if scale > 1 else 'raw'
                print(f"{t:<8} {yr:>5} {div_total:>18,.0f} {ni:>18,.0f} {scale:>8} {payout:>7.1%} {'NI ' + scale_note:<20}")
                break
        else:
            print(f"{t:<8} {yr:>5} {div_total:>18,.0f} {ni:>18,.0f} {'':>8} {'??':>8} {'scale not found':<20}")

con.close()
print("\nDone.")
