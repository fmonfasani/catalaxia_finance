# -*- coding: utf-8 -*-
"""
JOB 3 · D3 — CLASIFICACION OFFLINE (parser del acordeon)
========================================================
LEE los HTML de company pages ya bajados (JOB 2) y extrae, SIN RED, el mapeo
GUID -> tipo de formulario. Reemplaza el approach de fuerza bruta que abria
79.772 publicview (~9 h) por un parseo local de segundos.

Como funciona: la company page agrupa las presentaciones en secciones de acordeon
(un heading con el NOMBRE del formulario, y debajo los GUIDs de ese tipo). Se
recorre el HTML en orden: cada GUID hereda el ultimo heading (formulario) visto.

Salida: datos/guid_formtype.csv  (cuit, empresa, guid, formulario, url)

Uso:
    python job3_formtype.py           # procesa todos los HTML en html_descargados/
    python job3_formtype.py --debug   # imprime el resumen de formularios por empresa

0 requests. Reusable. Se puede re-correr cuando bajes mas company pages.
"""
from __future__ import annotations
import csv, re, sys, html as ihtml
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent
DATOS = BASE / "datos"
HTMLS = DATOS / "html_descargados"
OUT = DATOS / "guid_formtype.csv"

RX_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
# heading del acordeon: id="heading..." seguido del nombre del formulario (texto)
RX_HEADING = re.compile(r'id=["\']heading[\w-]+["\'][^>]*>(.*?)(?:</button|</a|</h\d|</div)', re.I | re.S)


def texto(fragmento):
    t = ihtml.unescape(re.sub(r"<[^>]+>", " ", fragmento))
    return re.sub(r"\s+", " ", t).strip()


def parsear_html(html):
    """Devuelve lista de (guid, formulario) recorriendo el HTML en orden."""
    eventos = []
    for m in RX_HEADING.finditer(html):
        nombre = texto(m.group(1))
        if 3 <= len(nombre) <= 90:
            eventos.append((m.start(), "form", nombre))
    for m in RX_GUID.finditer(html):
        eventos.append((m.start(), "guid", m.group(0).lower()))
    eventos.sort(key=lambda x: x[0])
    out, actual = [], ""
    vistos = set()
    for _, tipo, val in eventos:
        if tipo == "form":
            actual = val
        elif val not in vistos:
            vistos.add(val); out.append((val, actual))
    return out


def datos_empresa(nombre_archivo):
    # {cuit}_{nombre}.html
    m = re.match(r"(\d{11})_(.+)\.html$", nombre_archivo)
    return (m.group(1), m.group(2).replace("_", " ")) if m else ("", nombre_archivo)


def main():
    debug = "--debug" in sys.argv
    archivos = sorted(HTMLS.glob("*.html"))
    print(f"JOB3 · D3 — Clasificacion offline | {len(archivos)} company pages")
    filas = []
    resumen = {}
    for f in archivos:
        cuit, empresa = datos_empresa(f.name)
        html = f.read_text(encoding="utf-8", errors="ignore")
        pares = parsear_html(html)
        for guid, formulario in pares:
            filas.append({"cuit": cuit, "empresa": empresa, "guid": guid,
                          "formulario": formulario,
                          "url": f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"})
        resumen[empresa] = Counter(fm for _, fm in pares)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["cuit", "empresa", "guid", "formulario", "url"])
        w.writeheader(); w.writerows(filas)
    print(f"  -> {OUT.name}: {len(filas)} GUIDs clasificados, {len(archivos)} empresas")
    tot = Counter(r["formulario"] for r in filas)
    print("  Top formularios (global):")
    for fm, n in tot.most_common(15):
        print(f"    {n:>6}  {fm[:55]}")
    if debug:
        print("\n  Por empresa:")
        for emp, c in list(resumen.items())[:10]:
            print(f"    {emp[:30]:<32} {dict(c.most_common(4))}")


if __name__ == "__main__":
    main()
