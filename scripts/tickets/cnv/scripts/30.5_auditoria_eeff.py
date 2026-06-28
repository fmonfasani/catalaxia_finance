"""
30.5_auditoria_eeff.py

Audita todos los EEFF descargados.

Genera:

debug/auditoria_eeff.csv

Para cada HTML obtiene:

- ticker
- archivo
- presentationId
- formTypeId
- formTypeName
- title
- tamaño
- tablas
- filas
- columnas
- modeloDatos
- xml
- json
- blob
- pdf
- guid
- scripts
"""

from pathlib import Path
import re

import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent

EEFF = ROOT / "eeff"
DEBUG = ROOT / "debug"

DEBUG.mkdir(exist_ok=True)

RX_PRESENTATION = re.compile(r"presentationIdGlobal\s*=\s*'([^']+)'", re.I)
RX_FORMTYPE = re.compile(r"formTypeId\s*=\s*'([^']+)'", re.I)
RX_FORMNAME = re.compile(r"formTypeName\s*=\s*'([^']+)'", re.I)


def extraer(rx, texto):
    m = rx.search(texto)
    return m.group(1) if m else ""


rows = []

archivos = sorted(EEFF.rglob("*.html"))

print(f"HTML encontrados: {len(archivos)}")

for i, archivo in enumerate(archivos, start=1):

    print(f"[{i}/{len(archivos)}] {archivo.name}")

    html = archivo.read_text(
        encoding="utf8",
        errors="ignore",
    )

    soup = BeautifulSoup(html, "lxml")

    tablas = soup.find_all("table")

    filas = 0
    columnas = 0

    for t in tablas:

        trs = t.find_all("tr")

        filas += len(trs)

        if trs:

            columnas = max(
                columnas,
                len(trs[0].find_all(["td", "th"]))
            )

    rows.append({

        "ticker": archivo.parent.name,

        "archivo": archivo.name,

        "bytes": archivo.stat().st_size,

        "presentationId": extraer(
            RX_PRESENTATION,
            html,
        ),

        "formTypeId": extraer(
            RX_FORMTYPE,
            html,
        ),

        "formTypeName": extraer(
            RX_FORMNAME,
            html,
        ),

        "title": soup.title.text.strip()
        if soup.title else "",

        "tablas": len(tablas),

        "filas": filas,

        "columnas": columnas,

        "modeloDatos": html.count("modeloDatos"),

        "xml": html.lower().count("<?xml"),

        "json": html.lower().count(".json"),

        "blob": html.lower().count("blob"),

        "pdf": html.lower().count(".pdf"),

        "guid": len(re.findall(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            html,
            re.I,
        )),

        "scripts": len(
            soup.find_all("script")
        ),

    })

df = pd.DataFrame(rows)

salida = DEBUG / "auditoria_eeff.csv"

df.to_csv(
    salida,
    index=False,
    encoding="utf-8-sig",
)

print()
print("=" * 80)
print("RESUMEN")
print("=" * 80)

print(df.describe(include="all"))

print()

print(df.groupby("formTypeId").size())

print()

print(df.groupby("ticker").size())

print()

print("Generado:")
print(salida)