# -*- coding: utf-8 -*-
"""Ingester de paginas de entidad de la CNV (metadata autoritativa de presentaciones).

Descarga https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT} para las entidades
de nuestro universo (byma_only + adr, primarias) que todavia NO estan en el cache,
las guarda en el mismo cache que ya usa build_fiscal_calendar.py, y registra CADA
intento en la tabla ingest_log (url, http_status, sha256, bytes, path, fetched_at).

Es la pieza que arregla el problema de raiz: raw + provenance desde el dia 1.
Idempotente: por defecto saltea lo ya bajado; usar --force para re-bajar (versiona
por hash, no pisa el log).

    python scripts/tickets/cnv/metadata/fetch_cnv_pages.py            # baja lo que falta
    python scripts/tickets/cnv/metadata/fetch_cnv_pages.py --all      # todo el universo
    python scripts/tickets/cnv/metadata/fetch_cnv_pages.py --force    # re-baja igual
    python scripts/tickets/cnv/metadata/fetch_cnv_pages.py --cuit 30500781293

Requiere red hacia cnv.gov.ar. Despues correr build_fiscal_calendar.py para
reconstruir el fiscal_calendar con las nuevas paginas.
"""
from __future__ import annotations
import os as _os
import argparse, hashlib, os, re, sqlite3, sys, time, datetime as dt

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests' (pip install requests)")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DB = os.path.join(ROOT, "data", _os.environ.get("SCREENER_DB", "screener.db"))
CACHE = os.path.join(ROOT, "scripts", "tickets", "cnv", "datos", "html_descargados")
URL = "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}"
HEADERS = {"User-Agent": "catalaxia-screener/1.0 (research; contacto: webshooks)"}
TIMEOUT = 45
PAUSE = 1.5          # cortesia entre requests
RETRIES = 3


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", (s or "")).strip("_")[:60]


def cached_cuits() -> set[str]:
    out = set()
    for f in os.listdir(CACHE) if os.path.isdir(CACHE) else []:
        if f.lower().endswith(".html"):
            out.add(f.split("_")[0])
    return out


def targets(con, mode: str, only_cuit: str | None):
    cur = con.cursor()
    rows = cur.execute(
        "select cuit,ticker,nombre from mapa_entidades "
        "where grupo in ('byma_only','adr') and coalesce(es_primario,1)=1").fetchall()
    if only_cuit:
        return [r for r in rows if r[0] == only_cuit]
    if mode == "all":
        return rows
    have = cached_cuits()
    return [r for r in rows if r[0] not in have]


def log(cur, cuit, url, status, sha, nbytes, path, err):
    cur.execute(
        "INSERT INTO ingest_log(source,cuit,url,http_status,sha256,bytes,path,fetched_at,error) "
        "VALUES('cnv_page',?,?,?,?,?,?,?,?)",
        (cuit, url, status, sha, nbytes, path, dt.datetime.now().isoformat(timespec="seconds"), err))


def fetch_one(cuit, ticker, nombre, force):
    url = URL.format(cuit=cuit)
    dest = os.path.join(CACHE, f"{cuit}_{safe(ticker or nombre)}.html")
    if os.path.exists(dest) and os.path.getsize(dest) > 0 and not force:
        return ("skip", None, None, 0, dest, None)
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            body = r.content
            sha = hashlib.sha256(body).hexdigest()
            if r.status_code == 200 and len(body) > 1000:
                os.makedirs(CACHE, exist_ok=True)
                with open(dest, "wb") as fh:
                    fh.write(body)
                return ("ok", r.status_code, sha, len(body), dest, None)
            last_err = f"status={r.status_code} bytes={len(body)}"
            return ("bad", r.status_code, sha, len(body), None, last_err)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"[:200]
            time.sleep(PAUSE * attempt)
    return ("err", None, None, 0, None, last_err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="todo el universo, no solo lo faltante")
    ap.add_argument("--force", action="store_true", help="re-baja aunque exista")
    ap.add_argument("--cuit", help="una sola entidad")
    a = ap.parse_args()

    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS ingest_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, cuit TEXT, url TEXT,
        http_status INTEGER, sha256 TEXT, bytes INTEGER, path TEXT,
        fetched_at TEXT, error TEXT)""")

    tg = targets(con, "all" if a.all else "missing", a.cuit)
    print(f"objetivo: {len(tg)} entidades | cache: {CACHE}")
    n_ok = n_skip = n_fail = 0
    for i, (cuit, ticker, nombre) in enumerate(tg, 1):
        status, code, sha, nbytes, path, err = fetch_one(cuit, ticker, nombre, a.force)
        if status == "skip":
            n_skip += 1
        else:
            log(cur, cuit, URL.format(cuit=cuit), code, sha, nbytes, path, err)
            con.commit()
            if status == "ok":
                n_ok += 1; print(f"  [{i}/{len(tg)}] OK   {ticker or cuit} ({nbytes:,} bytes)")
            else:
                n_fail += 1; print(f"  [{i}/{len(tg)}] FALLA {ticker or cuit}: {err}")
            time.sleep(PAUSE)
    print(f"\nlisto: ok={n_ok} skip={n_skip} fallas={n_fail}")
    print("ahora corre:  python scripts/tickets/cnv/metadata/build_fiscal_calendar.py")
    con.close()


if __name__ == "__main__":
    main()
