"""
Extraccion masiva de EEFF NIIF (FT=147, 487) y dividendos (FT=339) desde CNV
AIF2 para las 9 ADR argentinos con CUIT propio.
Carga a tabla cnv_estados con fuente='cnv-adr'.
"""
import csv, re, sqlite3, time, json
from pathlib import Path
from datetime import datetime
import requests, html as html_mod

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = BASE / "data" / _os.environ.get("SCREENER_DB", "screener.db")
EEFF_CSV = BASE / "scripts" / "tickets" / "cnv" / "debug" / "adr_links_eeff.csv"
DIV_CSV = BASE / "scripts" / "tickets" / "cnv" / "debug" / "adr_links_dividendos.csv"
MAPPING_JSON = BASE / "scripts" / "tickets" / "cnv" / "debug" / "adr_code_mapping.json"
LOG_FILE = BASE / "data" / "log_extract_adr.txt"

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
     "Accept-Language": "es-AR"}
DELAY = 0.15

# Load mapping
with open(MAPPING_JSON, encoding="utf-8") as f:
    MAPPING = json.load(f)

NONBANK_MAP = MAPPING["nonbank"]  # for FT=147,154,142
BANK_MAP = MAPPING["bank"]        # for FT=487
DIV_FIELDS = MAPPING["dividend"]


def get_map(form_type: str) -> dict:
    """Return the code->concept mapping for a given formTypeId."""
    ft = form_type.split(".")[0]  # handles "487.0" -> "487"
    if ft in ("147", "154", "142"):
        return NONBANK_MAP
    elif ft == "487":
        return BANK_MAP
    return {}


def parse_codes(html_text: str, code_map: dict) -> dict:
    """Parse NNNNNNN Rubro Monto pairs from HTML and map to concepts."""
    txt = html_mod.unescape(re.sub(r"<[^>]+>", " ", html_text))
    txt = re.sub(r"\s+", " ", txt)
    result = {}
    for m in re.finditer(r"([1-8]\d{6})\s+[A-Za-zÁÉÍÓÚÑáéíóúñ()/.,\s]+?\s+(-?\d+\.\d{2})", txt):
        code = m.group(1)
        if code in code_map:
            result[code_map[code]] = float(m.group(2))
    return result


def extract_period_end(html_text: str) -> str | None:
    m = re.search(r'FechaCierre[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html_text)
    if m:
        return m.group(1)
    m = re.search(r'FechaHasta[^>]*?>[^<]*?(\d{4}-\d{2}-\d{2})', html_text)
    return m.group(1) if m else None


def extract_dividend(html_text: str) -> dict:
    """Extract dividend fields from XML-style propiedad tags."""
    result = {}
    for key, concept in DIV_FIELDS.items():
        m = re.search(rf'<propiedad id="{key}"[^>]*>([^<]+)</propiedad>', html_text)
        if m:
            val = m.group(1).strip()
            if concept == "DividendAmount":
                try:
                    result[concept] = float(val)
                except ValueError:
                    result[concept] = val
            else:
                result[concept] = val
    # Also get payment date for period_end
    m = re.search(r'<propiedad id="FechaEnQueSePoneADisposicion"[^>]*>([^<]+)</propiedad>', html_text)
    if m:
        date_str = m.group(1).strip()[:10]
        result["_payment_date"] = date_str
    return result


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    ses = requests.Session()
    ses.headers.update(H)

    # Ensure table exists
    cur.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-adr',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")

    stats = {
        "eeff_ok": 0, "eeff_err": 0, "div_ok": 0, "div_err": 0,
        "datapoints": 0, "no_period_end": 0, "no_codes": 0,
    }

    # ---- Process EEFF ----
    with open(EEFF_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    log(f"EEFF to process: {len(rows)}")

    for i, row in enumerate(rows):
        ticker = row["ticker"].strip()
        guid = row["guid"].strip()
        form_type = row["formTypeId"].strip()
        cuit = row["cuit"].strip()
        url = f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"

        code_map = get_map(form_type)

        try:
            r = ses.get(url, timeout=25, verify=False)
            if r.status_code != 200:
                stats["eeff_err"] += 1
                continue

            html_text = r.text
            period_end = extract_period_end(html_text)
            if not period_end:
                stats["no_period_end"] += 1
                stats["eeff_err"] += 1
                continue

            datos = parse_codes(html_text, code_map)
            if len(datos) < 3:
                stats["no_codes"] += 1
                stats["eeff_err"] += 1
                continue

            for concepto, valor in datos.items():
                cur.execute("""INSERT OR IGNORE INTO cnv_estados
                    (ticker, cik, concepto, period_end, tipo, valor,
                     valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ticker, cuit, concepto, period_end, "A",
                     valor, None, "", "EEFF", 1, guid, "cnv-adr"))
                stats["datapoints"] += 1

            con.commit()
            stats["eeff_ok"] += 1

            if (i + 1) % 50 == 0:
                log(f"  EEFF progress: {i+1}/{len(rows)} OK={stats['eeff_ok']} ERR={stats['eeff_err']}")

            time.sleep(DELAY)

        except Exception as e:
            stats["eeff_err"] += 1
            time.sleep(DELAY)

    log(f"EEFF done: OK={stats['eeff_ok']} ERR={stats['eeff_err']} datapoints={stats['datapoints']}")

    # ---- Process Dividends ----
    with open(DIV_CSV, encoding="utf-8-sig") as f:
        div_rows = list(csv.DictReader(f))

    log(f"Dividends to process: {len(div_rows)}")
    div_ok = 0
    div_err = 0

    for i, row in enumerate(div_rows):
        ticker = row["ticker"].strip()
        guid = row["guid"].strip()
        cuit = row["cuit"].strip()
        url = f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"

        try:
            r = ses.get(url, timeout=25, verify=False)
            if r.status_code != 200:
                div_err += 1
                continue

            div_data = extract_dividend(r.text)
            if "DividendAmount" not in div_data:
                div_err += 1
                continue

            payment_date = div_data.pop("_payment_date", None)
            period = payment_date[:10] if payment_date else "unknown"

            for concepto, valor in div_data.items():
                if isinstance(valor, (int, float)):
                    cur.execute("""INSERT OR IGNORE INTO cnv_estados
                        (ticker, cik, concepto, period_end, tipo, valor,
                         valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticker, cuit, concepto, period, "A",
                         valor, None, "", "Dividend", 1, guid, "cnv-adr"))
                    stats["datapoints"] += 1
                else:
                    meta_concept = f"Dividend_{concepto}"
                    cur.execute("""INSERT OR IGNORE INTO cnv_estados
                        (ticker, cik, concepto, period_end, tipo, valor,
                         valor_comparativo, fecha_reexpresion, form, escala, accn, fuente)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticker, cuit, meta_concept, period, "A",
                         None, None, valor, "Dividend", 1, guid, "cnv-adr"))
                    stats["datapoints"] += 1

            con.commit()
            div_ok += 1
            time.sleep(DELAY)

        except Exception as e:
            div_err += 1
            time.sleep(DELAY)

    stats["div_ok"] = div_ok
    stats["div_err"] = div_err

    log(f"Dividends done: OK={div_ok} ERR={div_err}")

    log(f"\n{'='*60}")
    log(f"RESUMEN FINAL")
    log(f"{'='*60}")
    log(f"EEFF OK: {stats['eeff_ok']}  ERR: {stats['eeff_err']}  "
        f"(sin period_end: {stats['no_period_end']}, sin codes: {stats['no_codes']})")
    log(f"Dividends OK: {stats['div_ok']}  ERR: {stats['div_err']}")
    log(f"Datapoints cargados: {stats['datapoints']}")

    con.close()


if __name__ == "__main__":
    main()
