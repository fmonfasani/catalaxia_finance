# -*- coding: utf-8 -*-
"""
JOB 5 v2 · E-EEFF — EXTRAER ESTADOS CONTABLES (UNIDAD NORMALIZADA)
===================================================================
Corrige el cambio de UnidadMedida (MILES DE $ → Millones de $) que
rompió la serie histórica en ~2021-2022.

Diferencias clave con v1:
  - factor_unidad(): normaliza todos los valores a pesos base.
  - Guarda HTML crudo en eeff/eeff_html/{guid}.html (nunca re-bajar).
  - Escribe cnv_estados_v2 (no toca cnv_estados).
  - Captura UnidadMedida + fecha_reexpresion como provenance.
  - Resume-safe: saltea GUIDs cuyo HTML ya está guardado.

Uso:
    python job5_v2_extract_eeff.py
    python job5_v2_extract_eeff.py --rango 0 500
    python job5_v2_extract_eeff.py --sleep 0.3
    python job5_v2_extract_eeff.py --max 800
    python job5_v2_extract_eeff.py --cuits empresas_subset.csv
"""
from __future__ import annotations
import csv, os, re, sys, time, sqlite3, html as ihtml
from pathlib import Path
from datetime import datetime
import requests
import urllib3
urllib3.disable_warnings()

BASE = Path(__file__).resolve().parent.parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
WHITELIST = BASE / "datos" / "whitelist_eeff_codigos.csv" if "--codigos" in sys.argv else BASE / "datos" / "whitelist_eeff.csv"
SUBSET = BASE / "datos" / "empresas_subset.csv"
HTML_DIR = BASE / "eeff" / "eeff_html"
DONE = ROOT / "data" / "log_job5_v2_done.txt"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Accept-Language": "es-AR"}

# --- FIX PERIMETRO -------------------------------------------------------
# La CNV declara el perimetro contable en un campo estructurado del HTML.
# Sin el, dos documentos del mismo cuit+periodo (individual y consolidado)
# colisionan en la PRIMARY KEY y el segundo se pierde en el INSERT OR IGNORE.
# Medido: 293 documentos quedaban mutilados y se descartaban 11.524 conceptos.
_RX_TB = re.compile(r'claveinformativa="TipoBalance"[^>]*>([^<]{0,40})', re.I)
_TB_NORM = {"individual": "INDIVIDUAL", "consolidado": "CONSOLIDADO"}


def tipo_balance(html):
    """'Individual'/'INDIVIDUAL' -> 'INDIVIDUAL'. Cadena vacia si no se declara."""
    m = _RX_TB.search(html)
    return _TB_NORM.get(m.group(1).strip().lower(), "") if m else ""


def _mark_done(guid):
    with open(DONE, "a", encoding="utf-8") as fh:
        fh.write(guid + "\n")

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

# CODIGOS que NO se multiplican por factor_unidad
# EPS_basico y EPS_diluido ya están en pesos por acción (no siguen la escala del documento)
NO_FACTOR = {"8000000", "8000001"}


def factor_unidad(html):
    """Lee UnidadMedida del HTML. Devuelve multiplicador a pesos base.

    Orden de chequeo: 'millon' antes que 'mil' (millon contiene 'mil').
    Si es None la unidad es desconocida → flag, no adivinar.
    """
    m = re.search(r'UnidadMedida[^>]*>\s*([^<]+)', html)
    u = (m.group(1) if m else "").strip().lower()
    # '$' a secas es el valor mas frecuente (1.030 de 2.350 documentos) y significa
    # pesos sin escalar. Antes caia en el return None y se contaba como "unidad
    # desconocida", aunque el llamador le asignaba 1 igual: el dato salia bien pero
    # el flag quedaba inservible, con 1.030 falsas alarmas tapando cualquier caso real.
    if not u or u in ("$", "$.") or "pesos" in u or "unidad" in u:
        return 1
    if "millon" in u:
        return 1_000_000
    if "mil" in u:
        return 1_000
    return None


def extraer_unidad_medida(html):
    m = re.search(r'UnidadMedida[^>]*>\s*([^<]+)', html)
    return m.group(1).strip() if m else ""


def extraer_moneda(html):
    m = re.search(r'Moneda[^>]*>\s*([^<]+)', html)
    return m.group(1).strip() if m else ""


def parse(html):
    """Parser idéntico a v1. Retorna {codigo: valor_raw} (pre-normalización)."""
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


# El documento declara su periodicidad en `PeriodoBalance`. Medido sobre los
# 2.457 documentos de la whitelist: esta en el 100%, ninguno lo trae vacio.
#   1 = anual        670 docs, cierres concentrados en diciembre (442) y junio (122)
#   2 = semestral     23 docs, casi todos en junio (21)
#   3 = trimestral  1753 docs, repartidos en septiembre, marzo, junio y diciembre
#   4 / 5           11 docs en total, sin patron claro -> se tratan como parciales
PERIODO_BALANCE = re.compile(
    r'claveinformativa="PeriodoBalance"[^>]*>\s*([0-9]{1,2})', re.I)


def tipo_periodo(html, pe=None):
    """'A' si el documento declara ser anual, 'P' si no. None si no lo declara.

    ANTES ESTO ADIVINABA, y por eso hay que mirarlo con cuidado al releer datos
    viejos. La regla anterior era:

        if rev > 100_000_000_000: return "A"      # "si factura mucho, es anual"
        if mes in (12, 5, 6):     return "A"
        return "P"

    Consecuencia medida: Aluar quedaba con SEIS cierres marcados "A" separados
    TRES MESES entre si (2026-03, 2025-12, 2025-09, 2025-06...), porque factura
    por encima del umbral. Con ese campo, 23 de las 56 empresas BYMA parecian
    apoyar sus ratios en un periodo parcial; con la periodicidad real son 37.

    No se cae a la adivinanza si el campo falta: devuelve None y el periodo
    queda sin declarar. Un dato ausente se puede detectar; uno inventado, no.
    """
    m = PERIODO_BALANCE.search(html or "")
    if not m:
        return None
    return "A" if m.group(1).strip() == "1" else "P"


def validar(d):
    if all(k in d for k in ("Assets", "Liabilities", "Equity")) and d["Assets"]:
        return abs((d["Liabilities"] + d["Equity"]) - d["Assets"]) / abs(d["Assets"]) * 100
    return None


def main():
    args = sys.argv[1:]
    whitelist_path = WHITELIST  # module default
    if "--whitelist" in args:
        i = args.index("--whitelist")
        wp = Path(args[i + 1])
        if wp.exists():
            whitelist_path = wp
        else:
            print(f"  --whitelist {wp} not found, using default")
    sleep = float(args[args.index("--sleep") + 1]) if "--sleep" in args else 0.3
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 10 ** 9
    # --offline: re-procesa SOLO los HTML ya guardados en disco y no toca la red.
    # Es lo que hace falta para re-extraer tras cambiar el parser o la PK.
    offline = "--offline" in args
    r0, r1 = 0, 10 ** 9
    if "--rango" in args:
        i = args.index("--rango")
        r0, r1 = int(args[i + 1]), int(args[i + 2])
    cuits_ok = None
    if "--cuits" in args:
        cp = Path(args[args.index("--cuits") + 1])
        cp = cp if cp.exists() else BASE / "datos" / cp.name
        cuits_ok = {r["cuit"].strip() for r in csv.DictReader(open(cp, encoding="utf-8-sig")) if r.get("cuit")}

    # Build cuit → ticker mapping from SUBSET (autoritativo)
    cuit_a_ticker = {}
    with open(SUBSET, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cu = r["cuit"].strip()
            tk = r["ticker"].strip().upper()
            if cu and tk:
                cuit_a_ticker[cu] = tk

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    hechos = set(DONE.read_text(encoding="utf-8").split()) if DONE.exists() else set()
    filas = list(csv.DictReader(open(whitelist_path, encoding="utf-8-sig")))
    if cuits_ok is not None:
        filas = [f for f in filas if f["cuit"].strip() in cuits_ok]
    filas = filas[r0:r1]

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS cnv_estados_v2 (
        ticker TEXT,
        cuit TEXT,
        concepto TEXT,
        period_end TEXT,
        tipo TEXT,
        valor REAL,
        valor_comparativo REAL,
        fecha_reexpresion TEXT,
        form TEXT,
        unidad_factor INTEGER,
        accn TEXT,
        fuente TEXT DEFAULT 'cnv-aif2',
        moneda TEXT,
        unidad_medida TEXT,
        tipo_balance TEXT DEFAULT '',
        PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
    )""")
    ses = requests.Session()
    ses.headers.update(H)

    print(f"JOB5 V2 · E-EEFF — Extraer [{r0}:{r1}] = {len(filas)} GUIDs (sleep {sleep}s, max {mx})")
    ok = err = skip = cache = ident_bad = dp = reqs = desconocidas = 0

    for i, row in enumerate(filas):
        guid = row["guid"]
        html_path = HTML_DIR / f"{guid}.html"

        if guid in hechos:
            skip += 1
            continue

        if offline and not html_path.exists():
            skip += 1
            continue

        if reqs >= mx:
            print(f"  Tope --max {mx} alcanzado; resume-safe (re-correr para seguir).")
            break

        # Si el HTML ya está guardado pero NO en DONE, re-procesar desde el archivo
        if html_path.exists():
            html = html_path.read_text(encoding="utf-8")
            cache += 1
        else:
            reqs += 1
            html = ses.get(row["url"], timeout=15, verify=False).text
            html_path.write_text(html, encoding="utf-8")

        try:
            pe = period_end(html)
            if not pe:
                err += 1
                _mark_done(guid)
                time.sleep(sleep)
                continue

            factor = factor_unidad(html)
            if factor is None:
                desconocidas += 1
                factor = 1

            unidad_medida = extraer_unidad_medida(html)
            moneda = extraer_moneda(html)
            pares = parse(html)

            datos = {}
            for code, raw_val in pares.items():
                if code in CODIGOS:
                    f = factor if code not in NO_FACTOR else 1
                    datos[CODIGOS[code]] = raw_val * f

            ratios = {}
            for code, raw_val in pares.items():
                if code in RATIOS_CNV:
                    ratios[RATIOS_CNV[code]] = raw_val

            if len(datos) < 5:
                err += 1
                _mark_done(guid)
                time.sleep(sleep)
                continue

            iv = validar(datos)
            if iv is not None and iv >= 5:
                ident_bad += 1

            # Se lee del documento (PeriodoBalance), no se deduce del monto.
            tp = tipo_periodo(html, pe)
            cuit = row["cuit"].strip()
            ticker = cuit_a_ticker.get(cuit, row.get("empresa", ""))

            tb = tipo_balance(html)
            for concepto, valor in datos.items():
                cur.execute("""INSERT OR IGNORE INTO cnv_estados_v2
                    (ticker, cuit, concepto, period_end, tipo, valor,
                     valor_comparativo, fecha_reexpresion, form,
                     unidad_factor, accn, fuente, moneda, unidad_medida, tipo_balance)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ticker, cuit, concepto, pe, tp, valor,
                             None, "", "EEFF", factor, guid, "cnv-aif2",
                             moneda, unidad_medida, tb))
                dp += 1
            for concepto, valor in ratios.items():
                cur.execute("""INSERT OR IGNORE INTO cnv_estados_v2
                    (ticker, cuit, concepto, period_end, tipo, valor,
                     valor_comparativo, fecha_reexpresion, form,
                     unidad_factor, accn, fuente, moneda, unidad_medida, tipo_balance)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ticker, cuit, f"CNV_{concepto}", pe, tp, valor,
                             None, "", "EEFF", factor, guid, "cnv-aif2",
                             moneda, unidad_medida, tb))
                dp += 1
            con.commit()
            ok += 1
            with open(DONE, "a", encoding="utf-8") as fh:
                fh.write(guid + "\n")
        except Exception as ex:
            err += 1
            _mark_done(guid)
            print(f"  ! {guid[:8]}: {type(ex).__name__}")
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(filas)}] ok={ok} skip={skip} cache={cache} err={err} dp={dp}")
        if not html_path.exists():  # solo sleep si hubo fetch real
            time.sleep(sleep)

    con.close()
    tk = ok + skip + err
    total_fetch = ok + err
    print(f"\n  Listo: ok={ok} skip={skip} cache={cache} err={err} | dp={dp} | fetch={total_fetch}/{reqs}")
    print(f"  Identidad>5%: {ident_bad} | Unidad desconocida: {desconocidas}")


if __name__ == "__main__":
    main()
