"""
03_auditoria_empresa.py

Audita la estructura HTML de las páginas de empresas de la CNV.

No clasifica.

Descubre qué información estructurada existe.

Salida:

debug/empresa_auditoria/
    xxxx.html
    xxxx.txt
"""

from pathlib import Path
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"
DEBUG = ROOT / "debug" / "empresa_auditoria"

DEBUG.mkdir(parents=True, exist_ok=True)

EMPRESAS = DATOS / "empresas.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def limpiar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def auditar(row):

    print(row.ticker)

    r = requests.get(
        row.url_empresa,
        headers=HEADERS,
        timeout=30,
    )

    r.raise_for_status()

    html = r.text

    soup = BeautifulSoup(html, "lxml")

    (DEBUG / f"{row.ticker}.html").write_text(
        html,
        encoding="utf8",
    )

    salida = []

    salida.append("=" * 80)
    salida.append(row.ticker)
    salida.append(row.empresa)
    salida.append(row.url_empresa)
    salida.append("=" * 80)

    salida.append("\nTITLE")
    salida.append(
        soup.title.get_text(strip=True)
        if soup.title else ""
    )

    salida.append("\nHEADINGS")

    for h in soup.find_all(["h1", "h2", "h3", "h4"]):

        salida.append(
            limpiar(h.get_text())
        )

    salida.append("\nTABLES")

    for i, table in enumerate(
        soup.find_all("table"),
        start=1,
    ):

        salida.append(f"\nTABLE {i}")

        txt = limpiar(
            table.get_text(" ")
        )

        salida.append(txt[:2000])

    salida.append("\nLABELS")

    patrones = [

        "tipo",
        "especie",
        "mercado",
        "régimen",
        "regimen",
        "categoria",
        "categoría",
        "emisor",
        "sector",
        "actividad",
        "industria",
        "bolsa",
        "panel",
        "cotiza",
        "acciones",
        "ticker",
    ]

    texto = soup.get_text("\n")

    for linea in texto.splitlines():

        l = limpiar(linea)

        if len(l) < 3:
            continue

        for p in patrones:

            if p.lower() in l.lower():

                salida.append(l)

                break

    salida.append("\nSCRIPTS")

    scripts = soup.find_all("script")

    for s in scripts:

        t = s.get_text()

        if any(x in t.lower() for x in [
            "tipo",
            "empresa",
            "category",
            "market",
            "sector",
            "actividad",
            "schema",
            "json",
        ]):

            salida.append("=" * 40)

            salida.append(t[:4000])

    (DEBUG / f"{row.ticker}.txt").write_text(
        "\n".join(salida),
        encoding="utf8",
    )


def main():

    df = pd.read_csv(EMPRESAS)

    print(df.shape)

    # SOLO LAS PRIMERAS 20

    for row in df.head(20).itertuples(index=False):

        auditar(row)


if __name__ == "__main__":
    main()