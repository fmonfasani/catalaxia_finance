# -*- coding: utf-8 -*-
"""
JOB 5 · E-EEFF — EXTRAER ESTADOS CONTABLES
==========================================
Consume whitelist_eeff.csv (JOB 4). Para cada GUID abre el publicview aif2, parsea
la plantilla estandarizada por CODIGO (7 digitos) -> conceptos + ratios pre-calculados
de la CNV, valida la identidad contable (Activo = Pasivo + PN) y carga a la tabla
cnv_estados de data/screener.db.

Este es un job RATE-LIMITED (1 request por GUID a CNV). Es SEGMENTABLE con --rango
para dividir el trabajo en varias corridas / dias.

Resume-safe: saltea los GUIDs ya cargados (registrados en data/log_job5_done.txt).

Uso:
    python job5_extract_eeff.py                    # toda la whitelist que falte
    python job5_extract_eeff.py --rango 0 500      # solo filas [0,500)
    python job5_extract_eeff.py --sleep 0.3        # segundos entre requests
    python job5_extract_eeff.py --max 800          # corta tras 800 requests (tope por corrida)
    python job5_extract_eeff.py --cuits empresas_subset.csv  # SOLO extrae los CUIT de ese CSV (palanca de scope)

Parser IDENTICO al validado en extract_aif2_masivo.py (identidad 0.000% en Ledesma).
"""
from __future__ import annotations
import csv, re, sys, time, sqlite3, html as ihtml
from pathlib import Path
from datetime import datetime
import requests
import urllib3
urllib3.disable_warnings()

BASE = Path(__file__).resolve().parent.parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
WHITELIST = BASE / "datos" / "whitelist_eeff.csv"
DONE = ROOT / "data" / "log_job5_done.txt"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Accept-Language": "es-AR"}

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
    txt = re.sub(r"\s+", " ", ihtml.unescape(re.sub(r"<[^>]+>", " ", html)))
    pares = {}
    for m in re.finditer(r"([1-8]\d{6})\s+[A-Za-zÁÉÍÓÚÑáéíóúñ()/.,\s]+?\s+(-?\d+\.\d{2})", txt):
        pares.setdefault(m.group(1), float(m.group(2)))
    return pares


def period_end(html):
    for pat in (r'FechaCierre[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', r'FechaHasta[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def tipo_periodo(rev, pe):
    if rev and rev > 100_000_000_000:
        return "A"
    if pe and int(pe.split("-")[1]) in (12, 5, 6):
        return "A"
    return "P"


def validar(d):
    if all(k in d for k in ("Assets", "Liabilities", "Equity")) and d["Assets"]:
        return abs((d["Liabilities"] + d["Equity"]) - d["Assets"]) / abs(d["Assets"]) * 100
    return None


def main():
    args = sys.argv[1:]
    sleep = float(args[args.index("--sleep") + 1]) if "--sleep" in args else 0.3
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 10**9
    r0, r1 = 0, 10**9
    if "--rango" in args:
        i = args.index("--rango"); r0, r1 = int(args[i + 1]), int(args[i + 2])
    cuits_ok = None
    if "--cuits" in args:
        cp = Path(args[args.index("--cuits") + 1])
        cp = cp if cp.exists() else BASE / "datos" / cp.name
        cuits_ok = {r["cuit"].strip() for r in csv.DictReader(open(cp, encoding="utf-8-sig")) if r.get("cuit")}

    hechos = set(DONE.read_text(encoding="utf-8").split()) if DONE.exists() else set()
    filas = list(csv.DictReader(open(WHITELIST, encoding="utf-8-sig")))
    if cuits_ok is not None:
        filas = [f for f in filas if f["cuit"].strip() in cuits_ok]
    filas = filas[r0:r1]

    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-aif2',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")
    ses = requests.Session(); ses.headers.update(H)

    print(f"JOB5 · E-EEFF — Extraer estados [{r0}:{r1}] = {len(filas)} GUIDs (sleep {sleep}s, max {mx}, ya hechos {len(hechos)})")
    ok = err = skip = ident_bad = dp = reqs = 0
    for i, row in enumerate(filas):
        guid = row["guid"]
        if guid in hechos:
            skip += 1; continue
        if reqs >= mx:
            print(f"  Tope --max {mx} alcanzado; corté (resume-safe, volvé a correr para seguir)."); break
        reqs += 1
        try:
            html = ses.get(row["url"], timeout=30, verify=False).text
            pe = period_end(html)
            datos = {CODIGOS[c]: v for c, v in parse(html).items() if c in CODIGOS}
            ratios = {RATIOS_CNV[c]: v for c, v in parse(html).items() if c in RATIOS_CNV}
            if not pe or len(datos) < 5:
                err += 1; time.sleep(sleep); continue
            iv = validar(datos)
            if iv is not None and iv >= 5:
                ident_bad += 1
            tp = tipo_periodo(datos.get("Revenue"), pe)
            cuit = row["cuit"]
            for concepto, valor in datos.items():
                cur.execute("""INSERT OR IGNORE INTO cnv_estados VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (row.get("empresa", ""), cuit, concepto, pe, tp, valor, None, "", "EEFF", 1, guid, "cnv-aif2"))
                dp += 1
            for concepto, valor in ratios.items():
                cur.execute("""INSERT OR IGNORE INTO cnv_estados VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (row.get("empresa", ""), cuit, f"CNV_{concepto}", pe, tp, valor, None, "", "EEFF", 1, guid, "cnv-aif2"))
                dp += 1
            con.commit()
            ok += 1
            with open(DONE, "a", encoding="utf-8") as fh:
                fh.write(guid + "\n")
        except Exception as ex:
            err += 1
            print(f"  ! {guid[:8]}: {type(ex).__name__}")
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(filas)}] ok={ok} skip={skip} err={err} datapoints={dp}")
        time.sleep(sleep)
    con.close()
    print(f"\n  Listo: ok={ok} skip={skip} err={err} | datapoints={dp} | identidad>5%={ident_bad}")


if __name__ == "__main__":
    main()
