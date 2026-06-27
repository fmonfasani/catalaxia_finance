# -*- coding: utf-8 -*-
"""
Orquestador del pipeline CNV-IR: para cada papel BYMA-only,
  descubrir EEFF (IR)  ->  descargar PDF  ->  parsear (texto/OCR)  ->
  validar por identidades contables  ->  cargar a cnv_estados (fuente='cnv-ir').

Resume-safe (cachea PDFs). Reporta por empresa: encontrado / texto-o-imagen /
items / identidad% / cargado. La identidad es el checksum: solo carga si cierra.

Uso:
  python pipeline.py                 # todas las del catalogo (sin cargar, solo reporte)
  python pipeline.py --cargar        # carga las que validan a cnv_estados
  python pipeline.py ALUA CECO2      # puntual
"""
from __future__ import annotations
import sys, re, sqlite3, requests, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalogo_ir import CATALOGO
from discovery import descubrir_eeff
from parser_eeff import procesar_pdf

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "screener.db"
CACHE = ROOT / "data" / "raw" / "cnv_ir"
UA = {"User-Agent": "Mozilla/5.0 Chrome/120"}


def descargar(url, ticker):
    CACHE.mkdir(parents=True, exist_ok=True)
    nombre = re.sub(r"[^\w.-]", "_", url.rsplit("/", 1)[-1])[:60]
    dest = CACHE / f"{ticker}__{nombre}"
    if not dest.suffix.lower() == ".pdf":
        dest = dest.with_suffix(".pdf")
    if dest.exists() and dest.stat().st_size > 10000:
        return dest
    try:
        data = requests.get(url, headers=UA, timeout=45, verify=False).content
        if len(data) < 10000:
            return None
        dest.write_bytes(data)
        return dest
    except Exception:
        return None


def periodo_de(nombre):
    """estima period_end (YYYY-MM-DD aprox) y tipo desde el nombre del PDF."""
    m = re.search(r"(20\d{2})", nombre)
    año = m.group(1) if m else None
    q = re.search(r"([1-4])\s*[QT]", nombre, re.I)
    if año and q:
        mes = {"1": "03", "2": "06", "3": "09", "4": "12"}[q.group(1)]
        return f"{año}-{mes}-30", "Q"
    return (f"{año}-12-31", "A") if año else (None, "?")


def cargar_estados(con, ticker, cik, datos, period_end, tipo, fecha_reexp, fuente="cnv-ir"):
    con.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-6k',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")
    n = 0
    for concepto, v in datos.items():
        con.execute("""INSERT OR REPLACE INTO cnv_estados
            (ticker,cik,concepto,period_end,tipo,valor,valor_comparativo,fecha_reexpresion,form,escala,accn,fuente)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ticker, str(cik), concepto, period_end, tipo, v, None, fecha_reexp, "EEFF-IR", 1, None, fuente))
        n += 1
    con.commit()
    return n


def procesar(ticker, con=None, cargar=False, verbose=True):
    pdfs = descubrir_eeff(ticker, CATALOGO)
    if not pdfs:
        if verbose: print(f"  {ticker:<7} SIN EEFF (IR bloqueado o sin link)")
        return {"ticker": ticker, "estado": "sin_eeff"}
    dest = descargar(pdfs[0], ticker)
    if not dest:
        if verbose: print(f"  {ticker:<7} no se pudo descargar")
        return {"ticker": ticker, "estado": "sin_descarga"}
    r = procesar_pdf(str(dest))
    metodo, datos, chk, ok = r["metodo"], r["datos"], r["checks"], r["ok"]
    idv = chk.get("Activo=Pas+PN")
    estado = ("OK" if ok else ("PARCIAL" if datos else ("ESCANEADO" if metodo == "vacio" else "VACIO")))
    if verbose:
        ids = f"{idv:.2f}%" if idv is not None else "n/a"
        print(f"  {ticker:<7} {metodo:<7} items={len(datos):<3} identidad={ids:<8} [{estado}] {pdfs[0].rsplit('/',1)[-1][:30]}")
    cargado = 0
    if cargar and ok and con is not None:
        cik = (con.execute("SELECT cik FROM empresas WHERE ticker_ppal=?", (ticker,)).fetchone() or [f"BYMA-{ticker}"])[0]
        pe, tipo = periodo_de(dest.name)
        from datetime import date
        cargado = cargar_estados(con, ticker, cik, datos, pe, tipo, date.today().isoformat())
    return {"ticker": ticker, "estado": estado, "metodo": metodo, "identidad": idv,
            "items": len(datos), "ratios": r["ratios"], "cargado": cargado}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cargar = "--cargar" in sys.argv
    tickers = args or list(CATALOGO)
    con = sqlite3.connect(DB) if cargar else None
    print(f"PIPELINE CNV-IR — {len(tickers)} empresas (cargar={cargar})\n")
    tally = {"OK": 0, "PARCIAL": 0, "ESCANEADO": 0, "sin_eeff": 0, "VACIO": 0, "sin_descarga": 0}
    total_cargado = 0
    for tk in tickers:
        r = procesar(tk, con, cargar)
        tally[r["estado"]] = tally.get(r["estado"], 0) + 1
        total_cargado += r.get("cargado", 0)
    print("\n=== RESUMEN ===")
    for k, v in tally.items():
        if v: print(f"  {k:<14} {v}")
    if cargar:
        print(f"  datapoints cargados: {total_cargado}")
        con.close()


if __name__ == "__main__":
    main()
