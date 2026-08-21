"""
Extraccion masiva de EEFF NIIF (formTypeId=147) desde CNV AIF2
para las 56 empresas BYMA.
Carga a tabla cnv_estados con period_end real.
"""
import csv, re, sqlite3, time, html as ihtml
import os as _os
from pathlib import Path
from datetime import datetime
import requests

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
DB = BASE / "data" / _os.environ.get("SCREENER_DB", "screener.db")
LINKS_REFINED = BASE / 'scripts' / 'tickets' / 'cnv' / 'datos' / 'links_eeff_refined.csv'
LOG_FILE = BASE / 'data' / 'log_extract_masivo.txt'

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
     "Accept-Language": "es-AR"}
DELAY = 0.1  # seconds between requests (CNV response time is 2-5s anyway)

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

    cur.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-aif2',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")

    cur.execute("SELECT ticker_ppal, cik, nombre FROM empresas WHERE grupo = 'byma_yf'")
    byma = {r[0]: {'cik': r[1], 'nombre': r[2]} for r in cur.fetchall()}
    log(f"Empresas BYMA a procesar: {len(byma)}")

    niif_by_ticker = {}
    with open(LINKS_REFINED, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            t = row['ticker'].strip().upper()
            if row['formTypeId'] == '147':
                niif_by_ticker.setdefault(t, []).append(row)

    log(f"Empresas con NIIF en refined: {len(niif_by_ticker)}")
    log(f"Total presentaciones NIIF: {sum(len(v) for v in niif_by_ticker.values())}")

    stats = {
        'total_requests': 0, 'ok': 0, 'error': 0, 'skipped': 0,
        'annual': 0, 'partial': 0, 'datapoints': 0, 'ident_errors': 0,
    }

    for ticker in sorted(byma.keys()):
        info = byma[ticker]
        cik_byma = info['cik']
        nombre = info['nombre'][:30]

        if ticker not in niif_by_ticker:
            log(f"{ticker:<8} {nombre:<30} SIN PRESENTACIONES NIIF")
            continue

        rows = sorted(niif_by_ticker[ticker],
                     key=lambda r: int(float(r['presentationId'])))

        # Delete old data with period_end='latest' for this ticker
        cur.execute("DELETE FROM cnv_estados WHERE ticker = ? AND period_end = 'latest' AND fuente = 'cnv-aif2'", (ticker,))
        con.commit()

        empresa_ok = 0
        empresa_err = 0
        empresa_skip = 0

        for row in rows:
            pid = int(float(row['presentationId']))
            guid = row['guid']
            url = row['url']

            try:
                r = ses.get(url, timeout=25, verify=False)
                stats['total_requests'] += 1

                if r.status_code != 200:
                    empresa_err += 1
                    continue

                html = r.text
                period_end = extract_period_end(html)
                if not period_end:
                    empresa_err += 1
                    continue

                pares = parse(html)
                datos = {CODIGOS[c]: v for c, v in pares.items() if c in CODIGOS}

                if len(datos) < 5:
                    empresa_err += 1
                    continue

                revenue = datos.get('Revenue')
                tipo = classify_period(revenue, period_end)

                ident = validate(datos)
                if ident is not None and ident >= 5:
                    stats['ident_errors'] += 1

                cnv_ratios = {RATIOS_CNV[c]: v for c, v in pares.items() if c in RATIOS_CNV}

                # Insert all concepts (INSERT OR IGNORE skips existing)
                for concepto, valor in datos.items():
                    cur.execute("""INSERT OR IGNORE INTO cnv_estados
                        (ticker, cik, concepto, period_end, tipo, valor,
                         valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticker, cik_byma, concepto, period_end, tipo,
                         valor, None, "", "EEFF", 1, guid, "cnv-aif2"))
                    stats['datapoints'] += 1

                for concepto, valor in cnv_ratios.items():
                    cur.execute("""INSERT OR IGNORE INTO cnv_estados
                        (ticker, cik, concepto, period_end, tipo, valor,
                         valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticker, cik_byma, f"CNV_{concepto}", period_end, tipo,
                         valor, None, "", "EEFF", 1, guid, "cnv-aif2"))
                    stats['datapoints'] += 1

                con.commit()

                empresa_ok += 1
                if tipo == 'A':
                    stats['annual'] += 1
                else:
                    stats['partial'] += 1

                time.sleep(DELAY)

            except Exception as e:
                empresa_err += 1
                stats['error'] += 1
                time.sleep(DELAY)

        if empresa_ok > 0 or empresa_err > 0:
            total = empresa_ok + empresa_err + empresa_skip
            log(f"{ticker:<8} {nombre:<30} OK={empresa_ok:>3} "
                f"SKIP={empresa_skip:>3} ERR={empresa_err:>2} Total={total}")

    log(f"\n{'='*60}")
    log(f"RESUMEN FINAL")
    log(f"{'='*60}")
    log(f"Requests totales: {stats['total_requests']}")
    log(f"OK: {stats['annual'] + stats['partial']} "
        f"(A={stats['annual']} P={stats['partial']})")
    log(f"Datapoints cargados: {stats['datapoints']}")
    log(f"Errores: {stats['error']}")
    log(f"Identity errors (>5%): {stats['ident_errors']}")

    con.close()

if __name__ == '__main__':
    main()
