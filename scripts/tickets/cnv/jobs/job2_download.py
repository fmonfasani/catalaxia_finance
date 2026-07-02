# -*- coding: utf-8 -*-
"""
JOB 2 · D2 — DESCARGAR COMPANY PAGES
====================================
Para cada empresa de empresas_556.csv, baja su pagina publica de la CNV y la
GUARDA en datos/html_descargados/. Esa pagina contiene, en secciones de acordeon,
TODOS los GUIDs de esa empresa agrupados por tipo de formulario (lo usa el JOB 3).

Es el "discovery call barato": 1 request por empresa trae todo su universo de
presentaciones. Resume-safe (saltea las ya bajadas). Rate-limited a CNV.

Salida: datos/html_descargados/{cuit}_{nombre}.html

Uso:
    python job2_download.py                          # todas las que falten
    python job2_download.py --rango 0 150            # solo empresas [0,150) — para segmentar
    python job2_download.py --sleep 1.0              # segundos entre requests (default 1.0)
    python job2_download.py --max 200                # corta tras 200 requests reales (tope por corrida)
    python job2_download.py --empresas empresas_subset.csv   # baja solo el subset (mismo formato de CSV)

Rate limit: NO correr dos instancias en paralelo contra CNV. Para paralelizar,
usar --rango disjuntos SOLO si controlás el rate agregado. --max acota cada corrida
para no pasarte de rosca; al ser resume-safe, volvés a correr y sigue donde quedó.
"""
from __future__ import annotations
import csv, re, sys, time
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
HTMLS = DATOS / "html_descargados"
EMPRESAS = DATOS / "empresas_556.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Accept-Language": "es-AR"}


def slug(s):
    return re.sub(r"[^\w]+", "_", (s or "").strip())[:50].strip("_") or "empresa"


def main():
    args = sys.argv[1:]
    sleep = float(args[args.index("--sleep") + 1]) if "--sleep" in args else 1.0
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 10**9
    r0, r1 = (0, 10**9)
    if "--rango" in args:
        i = args.index("--rango"); r0, r1 = int(args[i + 1]), int(args[i + 2])
    emp_path = EMPRESAS
    if "--empresas" in args:
        p = Path(args[args.index("--empresas") + 1])
        emp_path = p if (p.is_absolute() or p.exists()) else DATOS / p
    HTMLS.mkdir(parents=True, exist_ok=True)

    empresas = list(csv.DictReader(open(emp_path, encoding="utf-8-sig")))[r0:r1]
    print(f"  fuente: {emp_path.name}")
    print(f"JOB2 · D2 — Descargar company pages [{r0}:{r1}] = {len(empresas)} empresas (sleep {sleep}s, max {mx})")
    ok = skip = err = reqs = 0
    for i, e in enumerate(empresas):
        cuit = e["cuit"].strip()
        dest = HTMLS / f"{cuit}_{slug(e.get('empresa'))}.html"
        if dest.exists() and dest.stat().st_size > 5000:
            skip += 1; continue
        if reqs >= mx:
            print(f"  Tope --max {mx} alcanzado; corté (resume-safe, volvé a correr para seguir)."); break
        reqs += 1
        try:
            html = requests.get(f"https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}",
                                headers=HEADERS, timeout=120).text
            if len(html) < 5000:
                err += 1
            else:
                dest.write_text(html, encoding="utf-8"); ok += 1
        except Exception as ex:
            err += 1
            print(f"  ! {e.get('ticker') or cuit}: {type(ex).__name__}")
        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(empresas)}] ok={ok} skip={skip} err={err}")
        time.sleep(sleep)
    print(f"\n  Listo: {ok} bajadas, {skip} ya estaban, {err} error. Total en disco: {len(list(HTMLS.glob('*.html')))}")


if __name__ == "__main__":
    main()
