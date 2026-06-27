# -*- coding: utf-8 -*-
"""
Pipeline AUTOMATICO de estados contables argentinos (formato CNV/FACPCE) desde
los 6-K / 20-F de EDGAR (que adjuntan los estados como exhibit HTML).

Resuelve el dato trimestral que el XBRL no tiene, NIC 29 coherente por filing.
La CNV directa esta geo-bloqueada; esta via (EDGAR) cubre los ~16 ADR argentinos.

Capas:
  descubrir(cik)        -> filings con estados financieros (via index.json), cache
  fetch_texto(url)      -> HTML->texto o PDF->texto (pdfplumber), cache en raw/
  detectar_escala(txt)  -> multiplicador (miles/millones)
  detectar_periodo(txt) -> fecha de cierre + si es trimestral/anual
  parsear(txt)          -> line items canonicos (variantes de etiqueta por concepto)
  validar(d)            -> identidades contables (Activo=Pasivo+PN; Gross=Rev+COGS)
  procesar_ticker(tk)   -> pipeline completo de una empresa

Uso:
  python cnv_auto.py LOMA TGS CRESY     # prueba puntual
  python cnv_auto.py --todos            # todas las argentinas (carga a la base)
"""
from __future__ import annotations
import re, json, glob, time, html as ihtml, sqlite3
from pathlib import Path
from datetime import datetime
import requests

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "screener.db"
CACHE = ROOT / "data" / "raw" / "cnv"
UA = {"User-Agent": "catalaxia research fmonfasani@gmail.com"}

# ---- concepto canonico -> variantes de etiqueta (regex), de mas especifica a menos ----
ETIQUETAS = {
    "Revenue": [r"Net revenue", r"Revenue from contracts with customers", r"Net sales",
                r"Total revenue", r"Revenues", r"Sales revenue"],
    "COGS": [r"Cost of sales", r"Cost of revenue", r"Costs of sales"],
    "GrossProfit": [r"Gross profit", r"Gross income"],
    "OperatingIncome": [r"Operating income", r"Operating profit", r"Profit from operations"],
    "NetIncome": [r"NET PROFIT FOR THE PERIOD", r"Net income for the period",
                  r"Profit for the period", r"Net profit for the period",
                  r"Net income for the year", r"Profit for the year", r"NET INCOME"],
    "AssetsCurrent": [r"Total current assets"],
    "Assets": [r"Total assets"],
    "LiabilitiesCurrent": [r"Total current liabilities"],
    "Liabilities": [r"Total liabilities"],
    "Equity": [r"Total equity", r"Equity attributable to the owners of the Company",
               r"Total shareholders.{0,3} equity", r"Total stockholders.{0,3} equity"],
    "Cash": [r"Cash and cash equivalents at the end", r"Cash and cash equivalents"],
}
NUMRE = r"\(?-?\d{1,3}(?:,\d{3})+\)?(?:\.\d+)?"


def num(s):
    s = s.strip().replace(",", "")
    neg = s.startswith("(") or s.startswith("-")
    s = s.strip("()").lstrip("-")
    try:
        return -float(s) if neg else float(s)
    except ValueError:
        return None


def http(url, binario=False):
    for intento in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            time.sleep(0.2)
            return r.content if binario else r.text
        except Exception:
            time.sleep(1.5)
    return None


def descubrir(cik, formas=("6-K", "20-F"), max_filings=4, max_examinar=25):
    """[(form, fecha, accn, doc_url)]. Candidato = exhibit MAS GRANDE del filing
    (los estados son el doc mas pesado). max_examinar limita filings revisados
    para no churnear si una empresa no tiene estados tagueables."""
    subs = glob.glob(str(ROOT / "data" / "raw" / "submissions" / f"CIK{int(cik):010d}.json"))
    if not subs:
        return []
    rec = json.load(open(subs[0], encoding="utf-8"))["filings"]["recent"]
    out, examinados = [], 0
    for i, form in enumerate(rec["form"]):
        if form not in formas:
            continue
        if len(out) >= max_filings or examinados >= max_examinar:
            break
        examinados += 1
        accn = rec["accessionNumber"][i].replace("-", "")
        fecha = rec["filingDate"][i]
        idx = http(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/index.json")
        if not idx:
            continue
        try:
            items = json.loads(idx)["directory"]["item"]
        except Exception:
            continue
        # candidato = .htm/.pdf mas grande, excluyendo indices/headers
        cands = []
        for it in items:
            nm = it["name"].lower()
            if nm.endswith((".htm", ".html", ".pdf")) and "index" not in nm and "header" not in nm:
                try:
                    cands.append((int(it.get("size", 0) or 0), it["name"]))
                except ValueError:
                    pass
        # top-3 mas grandes como candidatos (probamos cual tiene los estados)
        cands.sort(reverse=True)
        urls = [f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{nm}" for _, nm in cands[:3]]
        if urls:
            out.append((form, fecha, accn, urls))
    return out


def fetch_texto(url, ticker, accn):
    """HTML->texto o PDF->texto, con cache (por documento)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    doc = url.rsplit("/", 1)[-1]
    cf = CACHE / f"{ticker}_{accn}_{doc}.txt"
    if cf.exists():
        return cf.read_text(encoding="utf-8")
    if url.lower().endswith(".pdf"):
        data = http(url, binario=True)
        if not data:
            return None
        try:
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                txt = " ".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:
            return None
    else:
        raw = http(url)
        if not raw:
            return None
        txt = ihtml.unescape(re.sub("<[^>]+>", " ", raw))
    txt = re.sub(r"\s+", " ", txt)          # colapsa TODO el whitespace (\n, \xa0, etc.)
    cf.write_text(txt, encoding="utf-8")
    return txt


def detectar_escala(txt):
    low = txt[:8000].lower()
    if re.search(r"in (thousands|miles)|thousands of|miles de", low):
        return 1000
    if re.search(r"in (millions|millones)|millions of|millones de", low):
        return 1_000_000
    return 1


def detectar_periodo(txt):
    """Fecha de cierre + tipo (Q/A) desde el encabezado."""
    cabeza = txt[:3000]
    meses = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
             "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
    fechas = re.findall(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})", cabeza, re.I)
    end = None
    if fechas:
        # fechas validas (2015..2027), tomar la MAS RECIENTE (cierre del reporte)
        cand = sorted(f"{int(y):04d}-{meses[mes.lower()]:02d}-{int(d):02d}"
                      for mes, d, y in fechas if 2015 <= int(y) <= 2027 and 1 <= int(d) <= 31)
        end = cand[-1] if cand else None
    tipo = "Q" if re.search(r"three-month|three month|quarter|condensed interim", cabeza, re.I) else "A"
    return end, tipo


def parsear(txt, escala=1):
    out = {}
    for concepto, variantes in ETIQUETAS.items():
        for patron in variantes:
            m = re.search(patron + r".{0,30}?(" + NUMRE + r")\s+(" + NUMRE + r")", txt)
            if m:
                v1, v2 = num(m.group(1)), num(m.group(2))
                if v1 is not None:
                    out[concepto] = (v1 * escala, (v2 * escala) if v2 is not None else None)
                    break
    return out


def validar(d):
    chk = {}
    if all(k in d for k in ("Revenue", "COGS", "GrossProfit")):
        c = d["Revenue"][0] + d["COGS"][0]
        chk["Gross=Rev+COGS"] = abs(c - d["GrossProfit"][0]) / abs(d["GrossProfit"][0]) * 100
    if all(k in d for k in ("Assets", "Liabilities", "Equity")):
        c = d["Liabilities"][0] + d["Equity"][0]
        chk["Activo=Pas+PN"] = abs(c - d["Assets"][0]) / abs(d["Assets"][0]) * 100
    return chk


def procesar_ticker(ticker, cik, max_filings=4, verbose=True):
    filings = descubrir(cik, max_filings=max_filings)
    resultados = []
    for form, fecha, accn, urls in filings:
        # probar candidatos: el doc de estados tiene el titulo IFRS estandar
        txt = None
        for u in urls:
            t = fetch_texto(u, ticker, accn)
            if t and ("statement of financial position" in t.lower() or "Total assets" in t):
                txt = t; break
        if not txt:
            continue
        escala = detectar_escala(txt)
        end, tipo = detectar_periodo(txt)
        d = parsear(txt, escala)
        chk = validar(d)
        ok = chk and all(e < 2 for e in chk.values())
        resultados.append({"form": form, "filed": fecha, "end": end, "tipo": tipo,
                           "escala": escala, "datos": d, "checks": chk, "ok": ok, "accn": accn})
        if verbose:
            estado = "OK" if ok else ("PARCIAL" if d else "VACIO")
            ch = " ".join(f"{k}:{v:.1f}%" for k, v in chk.items())
            print(f"  {form:<5} filed={fecha} end={end} {tipo} x{escala} | {len(d)} items [{estado}] {ch}")
    return resultados


def crear_tabla(con):
    con.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-6k',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")
    con.commit()


def cargar_a_base(con, ticker, cik, resultados):
    """Inserta cada line item con su FECHA DE RE-EXPRESION (= filed del 6-K).
    El mismo period_end desde filings distintos = filas distintas (NIC 29)."""
    n = 0
    for r in resultados:
        if not r["datos"] or not r["end"]:
            continue
        for concepto, (v1, v2) in r["datos"].items():
            con.execute("""INSERT OR REPLACE INTO cnv_estados
                (ticker,cik,concepto,period_end,tipo,valor,valor_comparativo,fecha_reexpresion,form,escala,accn)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ticker, str(cik), concepto, r["end"], r["tipo"], v1, v2, r["filed"], r["form"], r["escala"], r.get("accn")))
            n += 1
    con.commit()
    return n


if __name__ == "__main__":
    import sys
    con = sqlite3.connect(DB)
    crear_tabla(con)
    todos = "--todos" in sys.argv
    cargar = todos or "--cargar" in sys.argv
    pedidos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if todos:
        tickers = con.execute("SELECT ticker_ppal, cik FROM empresas WHERE grupo='adr_arg' AND fecha_facts IS NOT NULL").fetchall()
    else:
        tickers = [con.execute("SELECT ticker_ppal, cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg'", (a,)).fetchone() for a in pedidos]
        tickers = [t for t in tickers if t]
    total_cargado = 0
    for tk, cik in tickers:
        print(f"\n=== {tk} (CIK {cik}) ===")
        res = procesar_ticker(tk, cik)
        if cargar:
            total_cargado += cargar_a_base(con, tk, cik, res)
    if cargar:
        print(f"\n>>> Cargados {total_cargado} datapoints en tabla cnv_estados")
        n_emp = con.execute("SELECT COUNT(DISTINCT ticker) FROM cnv_estados").fetchone()[0]
        print(f">>> Empresas en cnv_estados: {n_emp}")
    con.close()
