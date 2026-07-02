# -*- coding: utf-8 -*-
"""
JOB 6 · E-DIV — EXTRAER DIVIDENDOS / HECHOS RELEVANTES / ACTAS
=============================================================
Consume whitelist_div.csv (JOB 4). A diferencia de los EEFF, estos formularios NO
usan la plantilla de codigos: "Pago de Dividendos" es semi-estructurado y los
"Hechos Relevantes" / "Actas" son texto libre. Por eso este job:

  1. Guarda el HTML crudo en eeff/div_html/{guid}.html  (para parseo de texto posterior)
  2. Extrae candidatos por regex: montos, fechas, moneda, dividendo por accion
  3. Carga una fila por presentacion a la tabla cnv_dividendos (data/screener.db)

Rate-limited (1 request por GUID). SEGMENTABLE con --rango. Resume-safe (log).

Uso:
    python job6_extract_div.py                    # toda la whitelist_div que falte
    python job6_extract_div.py --rango 0 300
    python job6_extract_div.py --sleep 0.3
    python job6_extract_div.py --max 800          # corta tras 800 requests (tope por corrida)
    python job6_extract_div.py --solo dividendo   # filtra por clase (dividendo|hecho_relevante|acta)
    python job6_extract_div.py --cuits empresas_subset.csv  # SOLO extrae los CUIT de ese CSV (palanca de scope)

NOTA: la extraccion de dividendos es EXPLORATORIA (los formularios varian). El HTML
crudo queda guardado para poder re-parsear sin volver a pegarle a la CNV.
"""
from __future__ import annotations
import csv, re, sys, time, sqlite3, html as ihtml
from pathlib import Path
import requests
import urllib3
urllib3.disable_warnings()

BASE = Path(__file__).resolve().parent.parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
WHITELIST = BASE / "datos" / "whitelist_div.csv"
HTML_DIR = BASE / "eeff" / "div_html"        # gitignoreado (crudo)
DONE = ROOT / "data" / "log_job6_done.txt"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Accept-Language": "es-AR"}

RX_FECHA = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
RX_MONTO = re.compile(r"(?:\$|ARS|USD|pesos?)\s*([\d\.]+,\d{2}|[\d,]+\.\d{2})", re.I)
RX_POR_ACCION = re.compile(r"por\s+acci[oó]n[^\d]{0,20}([\d\.,]+)", re.I)


def texto_plano(html):
    return re.sub(r"\s+", " ", ihtml.unescape(re.sub(r"<[^>]+>", " ", html)))


def main():
    args = sys.argv[1:]
    sleep = float(args[args.index("--sleep") + 1]) if "--sleep" in args else 0.3
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 10**9
    solo = args[args.index("--solo") + 1] if "--solo" in args else None
    r0, r1 = 0, 10**9
    if "--rango" in args:
        i = args.index("--rango"); r0, r1 = int(args[i + 1]), int(args[i + 2])
    cuits_ok = None
    if "--cuits" in args:
        cp = Path(args[args.index("--cuits") + 1])
        cp = cp if cp.exists() else BASE / "datos" / cp.name
        cuits_ok = {r["cuit"].strip() for r in csv.DictReader(open(cp, encoding="utf-8-sig")) if r.get("cuit")}

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    hechos = set(DONE.read_text(encoding="utf-8").split()) if DONE.exists() else set()
    filas = list(csv.DictReader(open(WHITELIST, encoding="utf-8-sig")))
    if cuits_ok is not None:
        filas = [f for f in filas if f["cuit"].strip() in cuits_ok]
    if solo:
        filas = [f for f in filas if f["clase"] == solo]
    filas = filas[r0:r1]

    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS cnv_dividendos (
        cuit TEXT, empresa TEXT, guid TEXT PRIMARY KEY, clase TEXT, formulario TEXT,
        fecha_candidata TEXT, monto_candidato TEXT, por_accion TEXT,
        snippet TEXT, fuente TEXT DEFAULT 'cnv-aif2')""")
    ses = requests.Session(); ses.headers.update(H)

    print(f"JOB6 · E-DIV — Extraer dividendos/HR/actas [{r0}:{r1}] = {len(filas)} GUIDs "
          f"(sleep {sleep}s, max {mx}, ya hechos {len(hechos)}{', solo '+solo if solo else ''})")
    ok = err = skip = reqs = 0
    for i, row in enumerate(filas):
        guid = row["guid"]
        if guid in hechos:
            skip += 1; continue
        if reqs >= mx:
            print(f"  Tope --max {mx} alcanzado; corté (resume-safe, volvé a correr para seguir)."); break
        reqs += 1
        try:
            html = ses.get(row["url"], timeout=30, verify=False).text
            (HTML_DIR / f"{guid}.html").write_text(html, encoding="utf-8")
            txt = texto_plano(html)
            fechas = RX_FECHA.findall(txt)
            montos = RX_MONTO.findall(txt)
            pa = RX_POR_ACCION.findall(txt)
            cur.execute("INSERT OR REPLACE INTO cnv_dividendos VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (row["cuit"], row.get("empresa", ""), guid, row["clase"], row["formulario"],
                         fechas[0] if fechas else "", montos[0] if montos else "",
                         pa[0] if pa else "", txt[:400], "cnv-aif2"))
            con.commit()
            ok += 1
            with open(DONE, "a", encoding="utf-8") as fh:
                fh.write(guid + "\n")
        except Exception as ex:
            err += 1
            print(f"  ! {guid[:8]}: {type(ex).__name__}")
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(filas)}] ok={ok} skip={skip} err={err}")
        time.sleep(sleep)
    con.close()
    print(f"\n  Listo: ok={ok} skip={skip} err={err} | HTML crudos en eeff/div_html/ | tabla cnv_dividendos")


if __name__ == "__main__":
    main()
