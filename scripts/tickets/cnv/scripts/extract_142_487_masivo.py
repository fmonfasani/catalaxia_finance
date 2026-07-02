"""
Extraccion masiva de EEFF desde CNV AIF2 para formTypeId=142 y 487.
Carga a tabla cnv_estados.

formTypeId=142: 9 tickers (BOLT, COUR, FIPL, GAMI, GARO, GCLA, LONG, REGE, SEMI)
formTypeId=487: 5 tickers (BHIP, BPAT, PATA, VALO, MOLI) - CRITICO: BPAT y PATA no tienen 147
"""
import csv, re, sqlite3, time, html as ihtml
from pathlib import Path
from datetime import datetime
import requests

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
DB = BASE / 'data' / 'screener.db'
LINKS_REFINED = BASE / 'scripts' / 'tickets' / 'cnv' / 'datos' / 'links_eeff_refined.csv'
LOG_FILE = BASE / 'data' / 'log_extract_142_487.txt'

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
     "Accept-Language": "es-AR"}
DELAY = 0.1

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
    "3241100": "CF_Operativo", "3241200": "CF_Inversion", "3241300": "CF_Financiacion",
    "8000000": "EPS_basico", "8000001": "EPS_diluido", "8000003": "EBIT",
    "8000004": "EBITDA", "8000005": "WorkingCapital",
}

RATIOS_CNV = {
    "8000006": "liquidez", "8000007": "solvencia", "8000009": "roe", "8000010": "roa",
    "8000011": "endeudamiento", "8000013": "apalancamiento", "8000014": "margen_neto",
    "8000015": "deuda_fin_ebitda", "8000016": "ebitda_costos_fin", "8000027": "prueba_acida",
    "8000028": "cobertura_intereses", "8000029": "rotacion_activos",
}


def parse(html):
    txt = ihtml.unescape(re.sub(r"<[^>]+>", " ", html))
    txt = re.sub(r"\s+", " ", txt)
    pares = {}
    for m in re.finditer(r"([1-8]\d{6})\s+[A-Za-zÁÉÍÓÚÑáéíóúñ()/.,\s]+?\s+(-?\d+\.\d{2})", txt):
        pares.setdefault(m.group(1), float(m.group(2)))
    return pares


def extract_period_end(html):
    m = re.search(r'FechaCierre[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
    if m:
        return m.group(1)
    m = re.search(r'FechaHasta[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html)
    return m.group(1) if m else None


def classify_period(revenue, period_end):
    if revenue and revenue > 100_000_000_000:
        return 'A'
    if period_end:
        month = int(period_end.split('-')[1])
        if month in (12, 5, 6):
            return 'A'
    return 'P'


def validate(datos):
    if all(k in datos for k in ("Assets", "Liabilities", "Equity")):
        s = datos["Liabilities"] + datos["Equity"]
        return abs(s - datos["Assets"]) / abs(datos["Assets"]) * 100 if datos["Assets"] else None
    return None


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    ses = requests.Session()
    ses.headers.update(H)

    cur.execute("SELECT ticker_ppal, cik, nombre FROM empresas WHERE grupo = 'byma_yf'")
    byma = {r[0]: {'cik': r[1], 'nombre': r[2]} for r in cur.fetchall()}
    log(f"Empresas BYMA: {len(byma)}")

    # Group links_eeff_refined by ticker and formTypeId
    links_by_tkr = {}
    with open(LINKS_REFINED, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            t = row['ticker'].strip().upper()
            ft = row['formTypeId']
            if ft in ('142', '487'):
                links_by_tkr.setdefault(t, []).append(row)

    log(f"Tickers con 142/487: {len(links_by_tkr)}")
    log(f"Total presentaciones: {sum(len(v) for v in links_by_tkr.values())}")

    stats = {'total': 0, 'ok': 0, 'error': 0, 'datapoints': 0, 'annual': 0, 'partial': 0}

    for ticker in sorted(byma.keys()):
        info = byma[ticker]
        cik_byma = info['cik']
        nombre = info['nombre'][:30]

        if ticker not in links_by_tkr:
            continue

        rows = sorted(links_by_tkr[ticker], key=lambda r: int(float(r['presentationId'])))

        emp_ok = emp_err = 0

        for row in rows:
            pid = int(float(row['presentationId']))
            ft = row['formTypeId']
            guid = row['guid']
            url = row['url']

            try:
                r = ses.get(url, timeout=25, verify=False)
                stats['total'] += 1
                if r.status_code != 200:
                    emp_err += 1
                    continue

                html = r.text
                period_end = extract_period_end(html)
                if not period_end:
                    emp_err += 1
                    continue

                pares = parse(html)
                datos = {CODIGOS[c]: v for c, v in pares.items() if c in CODIGOS}

                if len(datos) < 5:
                    emp_err += 1
                    continue

                revenue = datos.get('Revenue')
                tipo = classify_period(revenue, period_end)

                ident_err = validate(datos)
                if ident_err is not None and ident_err >= 5:
                    pass

                cnv_ratios = {RATIOS_CNV[c]: v for c, v in pares.items() if c in RATIOS_CNV}
                fuente = f"cnv-{ft}"

                for concepto, valor in datos.items():
                    cur.execute("""INSERT OR IGNORE INTO cnv_estados
                        (ticker, cik, concepto, period_end, tipo, valor,
                         valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticker, cik_byma, concepto, period_end, tipo,
                         valor, None, "", "EEFF", 1, guid, fuente))
                    stats['datapoints'] += 1

                for concepto, valor in cnv_ratios.items():
                    cur.execute("""INSERT OR IGNORE INTO cnv_estados
                        (ticker, cik, concepto, period_end, tipo, valor,
                         valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticker, cik_byma, f"CNV_{concepto}", period_end, tipo,
                         valor, None, "", "EEFF", 1, guid, fuente))
                    stats['datapoints'] += 1

                con.commit()
                emp_ok += 1
                if tipo == 'A':
                    stats['annual'] += 1
                else:
                    stats['partial'] += 1
                time.sleep(DELAY)

            except Exception as e:
                emp_err += 1
                stats['error'] += 1
                time.sleep(DELAY)

        if emp_ok > 0 or emp_err > 0:
            total = emp_ok + emp_err
            log(f"{ticker:<8} {nombre:<30} OK={emp_ok:>3} ERR={emp_err:>2} Total={total}")

    log(f"\n{'='*60}")
    log(f"RESUMEN FINAL")
    log(f"{'='*60}")
    log(f"Requests: {stats['total']} | OK: {stats['annual']+stats['partial']} (A={stats['annual']} P={stats['partial']})")
    log(f"Datapoints: {stats['datapoints']} | Errors: {stats['error']}")
    con.close()


if __name__ == '__main__':
    main()
