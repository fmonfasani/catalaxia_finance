# -*- coding: utf-8 -*-
"""
Ratios ADR OFICIALES desde SEC EDGAR (F-6 / 20-F)
=================================================
Para cada ADR argentino: busca su último 20-F en EDGAR, extrae la frase oficial
"Each ADS represents N shares" y guarda el ratio + la URL del filing (auditable).

NO es un dato estimado — es el dato oficial del documento presentado ante la SEC.

Salida: datos/adr_ratios.csv (edgar_ticker, cuit, empresa, ratio, clase, source_url, fecha)
        + tabla adr_ratios en data/screener.db

Uso: python sec_adr_ratios.py
"""
from __future__ import annotations
import sqlite3, requests, re, csv, time, html as ihtml
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
OUT = Path(__file__).resolve().parent.parent.parent / "cnv" / "datos" / "adr_ratios.csv"
H = {"User-Agent": "catalaxia-research fmonfasani@gmail.com"}

# ADR argentinos del screener: edgar_ticker -> cuit (link a la data local; la razon social confirma)
ADR_CUIT = {
    "YPF": "30546689979", "GGAL": "30704962807", "PAM": "30526552659",
    "TEO": "30639453738", "BBAR": "30500003193", "CEPU": "33650305499",
    "LOMA": "30500530851", "IRS": "30525322749", "SUPV": "30617442937",
    "CRESY": "30509300700", "BMA": None, "VIST": "33515950899",
    "TGS": "30657862068",
}
NUM = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten".split())}
NUM.update({"twenty-five": 25, "twenty five": 25, "twenty": 20, "fifteen": 15})

# Dos fraseos oficiales: "Each ADS represents N ..." y "ADSs, each representing N ..."
_DEP = r"(?:ADS|ADR|GDS|American [Dd]epositary [Ss]hare|Global [Dd]epositary [Ss]hare)"
PATS = [
    re.compile(r"[Ee]ach\s+" + _DEP + r"\s+represent\w*\s+(?:the right to receive\s+)?([\w-]+)\s+([\w ]{0,20}?shares?)", re.I),
    re.compile(_DEP + r"s?,?\s+each\s+(?:of which\s+)?represent\w*\s+(?:the right to receive\s+)?([\w-]+)\s+([\w ]{0,20}?shares?)", re.I),
]
# Fallback: agregado "N ADSs, representing M ... shares" -> ratio = M/N
RX_AGG = re.compile(r"([\d,]+)\s+ADSs?,?\s+represent\w*\s+([\d,]+)\s+[\w ]{0,20}?shares?", re.I)


def a_numero(tok):
    tok = tok.strip().lower()
    if tok.replace(",", "").isdigit():
        return int(tok.replace(",", ""))
    return NUM.get(tok)


def latest_form(cik, forms=("20-F", "F-6")):
    c = str(cik).lstrip("0").zfill(10)
    r = requests.get(f"https://data.sec.gov/submissions/CIK{c}.json", headers=H, timeout=30)
    if r.status_code != 200:
        return None
    rec = r.json()["filings"]["recent"]
    for want in forms:
        for i, f in enumerate(rec["form"]):
            if f == want:
                acc = rec["accessionNumber"][i].replace("-", "")
                doc = rec["primaryDocument"][i]
                url = f"https://www.sec.gov/Archives/edgar/data/{str(cik).lstrip('0')}/{acc}/{doc}"
                return url, rec["filingDate"][i], want
    return None


def parse_ratio(url):
    t = requests.get(url, headers=H, timeout=60).text
    txt = re.sub(r"\s+", " ", ihtml.unescape(re.sub(r"<[^>]+>", " ", t)))
    for rx in PATS:
        m = rx.search(txt)
        if m:
            n = a_numero(m.group(1))
            if n:
                return n, m.group(2).strip()
    # fallback: agregado M shares / N ADSs
    for m in RX_AGG.finditer(txt):
        n_ads = a_numero(m.group(1)); n_sh = a_numero(m.group(2))
        if n_ads and n_sh and n_ads > 0 and (n_sh / n_ads) == int(n_sh / n_ads):
            return int(n_sh / n_ads), "shares (derivado de agregado)"
    return None, None


def main():
    con = sqlite3.connect(DB); cur = con.cursor()
    ciks = {tk: cik for tk, cik, in cur.execute("SELECT ticker_ppal, cik FROM empresas WHERE grupo IN ('adr_arg','latam') AND fecha_facts IS NOT NULL").fetchall()
            for _ in [0]} if False else {}
    ciks = {r[0]: r[1] for r in cur.execute("SELECT ticker_ppal, cik FROM empresas WHERE fecha_facts IS NOT NULL").fetchall()}

    con.execute("""CREATE TABLE IF NOT EXISTS adr_ratios (
        edgar_ticker TEXT PRIMARY KEY, cuit TEXT, ratio INTEGER, clase TEXT,
        source_url TEXT, filing_form TEXT, filing_date TEXT)""")
    rows = []
    for tk, cuit in ADR_CUIT.items():
        cik = ciks.get(tk)
        if not cik:
            print(f"  {tk:<6} sin CIK EDGAR"); continue
        lf = latest_form(cik); time.sleep(0.3)
        if not lf:
            print(f"  {tk:<6} sin 20-F/F-6"); continue
        url, fecha, form = lf
        ratio, clase = parse_ratio(url); time.sleep(0.3)
        estado = f"ratio={ratio} ({clase})" if ratio else "NO PARSEADO -> revisar manual"
        print(f"  {tk:<6} {form} {fecha}  {estado}")
        rows.append((tk, cuit, ratio, clase, url, form, fecha))
        con.execute("INSERT OR REPLACE INTO adr_ratios VALUES (?,?,?,?,?,?,?)", (tk, cuit, ratio, clase, url, form, fecha))
    con.commit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["edgar_ticker", "cuit", "ratio", "clase", "source_url", "filing_form", "filing_date"])
        w.writerows(rows)
    ok = sum(1 for r in rows if r[2])
    print(f"\n  -> {OUT.name}: {len(rows)} ADR, {ok} con ratio oficial parseado, {len(rows)-ok} a revisar")
    con.close()


if __name__ == "__main__":
    main()
