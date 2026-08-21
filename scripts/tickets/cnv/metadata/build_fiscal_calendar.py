# -*- coding: utf-8 -*-
"""Capa de metadata CNV (autoritativa, sin red).

Parsea las paginas de entidad de la CNV ya cacheadas (indice de presentaciones)
y construye, con provenance:
  - cnv_filings     : una fila por presentacion (norma, tipo balance, periodicidad,
                      fecha de cierre, archivo fuente).
  - cnv_documents   : punteros a los documentos (publicview docid) para la futura
                      re-ingesta de los numeros.
  - fiscal_calendar : fin de ejercicio por CUIT = mes de cierre del ULTIMO anual,
                      con flag de inconsistencia (si el cierre cambio en el tiempo).

Fuente = paginas https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT} (Periodicidad
1=Anual / 3=Trimestral, Fecha de cierre, Consolidado/Individual). Es la fuente
autoritativa del fin de ejercicio que necesita la des-acumulacion (ver recompute_ttm).

Uso:  python scripts/tickets/cnv/metadata/build_fiscal_calendar.py
Idempotente: reconstruye las 3 tablas derivadas desde el cache en cada corrida.
"""
from __future__ import annotations
import os as _os
import glob, os, re, sqlite3, collections, datetime as dt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DB = os.path.join(ROOT, "data", _os.environ.get("SCREENER_DB", "screener.db"))
CACHE = os.path.join(ROOT, "scripts", "tickets", "cnv", "datos", "html_descargados")
CNV_URL = "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}"

# "NORMA CONTABLE: NIIF - TIPO BALANCE: INDIVIDUAL - PERIODICIDAD: 3 - FECHA CIERRE: 2026-03-31"
RX_META = re.compile(
    r"NORMA CONTABLE:\s*(?P<norma>[^-<]+?)\s*-\s*"
    r"TIPO BALANCE:\s*(?P<tipo>[^-<]+?)\s*-\s*"
    r"PERIODICIDAD:\s*(?P<per>[^-<]+?)\s*-\s*"
    r"FECHA CIERRE:\s*(?P<cierre>\d{4}-\d{2}-\d{2})", re.I)
RX_DOC = re.compile(r"aif2\.cnv\.gov\.ar/presentations/publicview/([0-9a-f-]{36})", re.I)


def norm_per(p: str) -> str:
    p = p.strip().upper()
    return {"1": "A", "ANUAL": "A", "3": "T", "TRIMESTRAL": "T",
            "6": "S", "SEMESTRAL": "S", "9": "T9"}.get(p, p)


def parse_cache():
    filings, docs = [], []
    for f in glob.glob(os.path.join(CACHE, "*.html")):
        cuit = os.path.basename(f).split("_")[0]
        if not cuit.isdigit():
            continue
        txt = open(f, encoding="utf-8", errors="ignore").read()
        src = os.path.basename(f)
        for m in RX_META.finditer(txt):
            filings.append((cuit, m["norma"].strip().upper(), m["tipo"].strip().upper(),
                            norm_per(m["per"]), m["cierre"], src))
        for did in set(RX_DOC.findall(txt)):
            docs.append((cuit, did.lower(),
                         f"https://aif2.cnv.gov.ar/presentations/publicview/{did.lower()}", src))
    return filings, docs


def fiscal_calendar(filings, tickers):
    """FY-end = mes de cierre del ULTIMO anual; flag si hubo cambio historico."""
    ann = collections.defaultdict(list)  # cuit -> [(fecha_cierre, ...)]
    for cuit, norma, tipo, per, cierre, src in filings:
        if per == "A":
            ann[cuit].append(cierre)
    rows = []
    now = dt.datetime.now().isoformat(timespec="seconds")
    for cuit, cierres in ann.items():
        cierres = sorted(set(cierres))
        last = cierres[-1]
        fy_month = int(last[5:7])
        months = sorted({int(c[5:7]) for c in cierres})
        rows.append((cuit, tickers.get(cuit), fy_month, last, len(cierres),
                     ",".join(f"{m:02d}" for m in months), int(len(months) > 1),
                     "cnv_cache", now))
    return rows


def main():
    con = sqlite3.connect(DB); cur = con.cursor()
    tickers = {cu: tk for cu, tk in cur.execute("select cuit,ticker from mapa_entidades")}

    filings, docs = parse_cache()
    fcal = fiscal_calendar(filings, tickers)

    cur.executescript("""
        DROP TABLE IF EXISTS cnv_filings;
        DROP TABLE IF EXISTS cnv_documents;
        DROP TABLE IF EXISTS fiscal_calendar;
        CREATE TABLE cnv_filings(
            cuit TEXT, ticker TEXT, norma TEXT, tipo_balance TEXT,
            periodicidad TEXT, fecha_cierre TEXT, source_file TEXT, parsed_at TEXT);
        CREATE TABLE cnv_documents(
            cuit TEXT, docid TEXT, url TEXT, source_file TEXT);
        CREATE TABLE fiscal_calendar(
            cuit TEXT PRIMARY KEY, ticker TEXT, fy_end_month INTEGER, fy_end_last TEXT,
            n_annual INTEGER, months_seen TEXT, inconsistent INTEGER, source TEXT, built_at TEXT);
        CREATE TABLE IF NOT EXISTS ingest_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, cuit TEXT, url TEXT,
            http_status INTEGER, sha256 TEXT, bytes INTEGER, path TEXT,
            fetched_at TEXT, error TEXT);
    """)
    now = dt.datetime.now().isoformat(timespec="seconds")
    cur.executemany("INSERT INTO cnv_filings(cuit,ticker,norma,tipo_balance,periodicidad,fecha_cierre,source_file,parsed_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    [(cu, tickers.get(cu), no, ti, pe, ci, sr, now) for cu, no, ti, pe, ci, sr in filings])
    cur.executemany("INSERT INTO cnv_documents(cuit,docid,url,source_file) VALUES(?,?,?,?)", docs)
    cur.executemany("INSERT INTO fiscal_calendar VALUES(?,?,?,?,?,?,?,?,?)", fcal)
    con.commit()

    # ---- reporte ----
    print(f"DB: {DB}")
    print(f"cnv_filings   : {len(filings)} presentaciones")
    print(f"cnv_documents : {len(docs)} punteros a documentos")
    print(f"fiscal_calendar: {len(fcal)} CUITs con FY-end")
    uni = cur.execute("select cuit,ticker,grupo from mapa_entidades where grupo in ('byma_only','adr')").fetchall()
    have = cur.execute("select cuit from fiscal_calendar").fetchall(); have = {r[0] for r in have}
    cov = [tk for cu, tk, g in uni if cu in have]
    miss = [tk for cu, tk, g in uni if cu not in have]
    incon = [r[0] for r in cur.execute("select ticker from fiscal_calendar where inconsistent=1 and ticker is not null")]
    print(f"\ncobertura universo ({len(uni)}): {len(cov)} con FY, {len(miss)} sin")
    print(f"inconsistentes (cambio de cierre): {len(incon)} -> {sorted(incon)[:12]}")
    print(f"faltan fetch ({len(miss)}): {sorted(miss)}")
    con.close()


if __name__ == "__main__":
    main()
