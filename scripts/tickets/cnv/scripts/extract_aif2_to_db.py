"""Extract latest EEFF from CNV AIF2 for only-byma tickers and load to cnv_estados"""
import csv, re, sqlite3, time, html as ihtml
import os as _os
from pathlib import Path
import requests

BASE = Path(r'D:\Software Development\Porfolio\catalaxia-cedears-prod')
DB = BASE / "data" / _os.environ.get("SCREENER_DB", "screener.db")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
     "Accept-Language": "es-AR"}

CODIGOS = {
    "1122500": "Cash", "1121999": "Receivables", "1120100": "Inventory",
    "1139999": "AssetsCurrent", "1110100": "PPE", "1110200": "Intangibles",
    "1119999": "AssetsNonCurrent", "1999999": "Assets",
    "2210999": "Capital", "2211999": "Reservas", "2212999": "ResultadosNoAsignados",
    "2299999": "Equity",
    "2322200": "DebtCurrent", "2321999": "Payables", "2339999": "LiabilitiesCurrent",
    "2312300": "DebtNonCurrent", "2319999": "LiabilitiesNonCurrent", "2399999": "Liabilities",
    "3000100": "Revenue", "3000200": "COGS", "3009999": "GrossProfit",
    "3011600": "DA", "3019999": "OperatingIncome", "3021400": "IngresosFinancieros",
    "3021500": "InterestExpense", "3021800": "RECPAM", "3029999": "PretaxIncome",
    "3031100": "IncomeTax", "3049999": "NetIncome", "3099999": "ResultadoIntegral",
    "3240000": "CashFlowNeto",
    "8000000": "EPS_basico", "8000001": "EPS_diluido", "8000003": "EBIT",
    "8000004": "EBITDA", "8000005": "WorkingCapital",
}

def parse(html):
    txt = ihtml.unescape(re.sub("<[^>]+>", " ", html))
    txt = re.sub(r"\s+", " ", txt)
    pares = {}
    for m in re.finditer(r"([1-8]\d{6})\s+[A-ZÁÉÍÓÚÑ()/.,\s]+?\s+(-?\d+\.\d{2})", txt):
        pares.setdefault(m.group(1), float(m.group(2)))
    return pares

def validate(d):
    if all(k in d for k in ("Assets", "Liabilities", "Equity")):
        s = d["Liabilities"] + d["Equity"]
        return abs(s - d["Assets"]) / abs(d["Assets"]) * 100 if d["Assets"] else None
    return None

def load(con, ticker, datos, fuente="cnv-aif2"):
    cik = f"BYMA-{ticker}"
    n = 0
    for concepto, valor in datos.items():
        con.execute("""INSERT OR REPLACE INTO cnv_estados
            (ticker,cik,concepto,period_end,tipo,valor,valor_comparativo,fecha_reexpresion,form,escala,accn,fuente)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ticker, cik, concepto, "latest", "A", valor, None, "latest", "EEFF", 1, None, fuente))
        n += 1
    con.commit()
    return n

def ratios(d):
    def d2(a, b): return a / b if (a is not None and b not in (None, 0)) else None
    return {
        "margen_neto": d2(d.get("NetIncome"), d.get("Revenue")),
        "margen_bruto": d2(d.get("GrossProfit"), d.get("Revenue")),
        "roe": d2(d.get("NetIncome"), d.get("Equity")),
        "roa": d2(d.get("NetIncome"), d.get("Assets")),
        "deuda_total": (d.get("DebtCurrent", 0) or 0) + (d.get("DebtNonCurrent", 0) or 0),
        "EBITDA": d.get("EBITDA"),
        "EPS": d.get("EPS_basico"),
        "working_capital": d.get("WorkingCapital"),
    }

# Load tickers
solo = {}
with open(BASE / 'scripts' / 'screener' / 'datos' / 'acciones_solo_byma.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        tk = row['ticker_byma'].rstrip('m')
        solo[tk] = row['empresa']

# Load links
links = {}
for row in csv.DictReader(open(BASE / 'scripts' / 'tickets' / 'cnv' / 'datos' / 'links_eeff.csv', encoding='utf-8-sig')):
    tk = row['ticker'].upper()
    if tk in solo:
        pid = int(float(row['presentationId']))
        if tk not in links or pid > links[tk]['pid']:
            links[tk] = {'pid': pid, 'guid': row['guid'], 'url': row['url'],
                         'formTypeName': row['formTypeName'].strip()}

con = sqlite3.connect(DB)
con.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
    ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
    valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
    form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-6k',
    PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")

print("=" * 80)
print("Extracción EEFF vía CNV AIF2 para only-byma tickers")
print("=" * 80)
print(f"{'Ticker':<8} {'Empresa':<30} {'Items':<7} {'Identity':<12} {'Ratios':<40}")
print("-" * 97)

total = 0
for tk in sorted(solo):
    emp = solo[tk]
    if tk not in links:
        print(f"{tk:<8} {emp:<30} {'SIN ENLACE CNV':<19}")
        continue
    info = links[tk]
    try:
        r = requests.get(info['url'], headers=H, timeout=25, verify=False)
        pares = parse(r.text)
        datos = {CODIGOS[c]: v for c, v in pares.items() if c in CODIGOS}
        if len(datos) < 10:
            print(f"{tk:<8} {emp:<30} {'SIN DATA':<19} (form: {info['formTypeName'][:30]})")
            continue
        ident_pct = validate(datos)
        ident_str = f"{ident_pct:.2f}%" if ident_pct is not None else "N/A"
        n = load(con, tk, datos)
        total += n
        r2 = ratios(datos)
        ratio_str = f"NetMarg={r2['margen_neto']:.2%} ROE={r2['roe']:.2%} D/EBITDA={r2['deuda_total']/(r2['EBITDA'] or 1):.2f}"
        status = "OK" if ident_pct is not None and ident_pct < 1 else "CHK"
        print(f"{tk:<8} {emp:<30} {n:<7} {ident_str:<12} {status:<4} {ratio_str}")
    except Exception as e:
        print(f"{tk:<8} {emp:<30} ERROR   {str(e)[:40]}")

print(f"\nTotal datapoints cargados: {total}")
con.close()
