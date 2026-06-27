"""
20.6_formtypes_ecog.py

Analiza TODOS los publicview de ECOG y descubre los distintos
tipos de formularios (formTypeId / formTypeName).

Salida:
debug/ecog_formtypes.csv
"""

from pathlib import Path
import re
import time

import pandas as pd
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
    )
}

BASE = "https://aif2.cnv.gov.ar/presentations/publicview/"


def extraer(regex, html):
    m = re.search(regex, html, re.I | re.S)
    return m.group(1).strip() if m else ""


def analizar_guid(guid):

    url = BASE + guid

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        r.raise_for_status()

        html = r.text

    except Exception as e:

        return {
            "guid": guid,
            "status": "ERROR",
            "formTypeId": "",
            "formTypeName": "",
            "presentationId": "",
            "title": "",
            "error": str(e),
        }

    return {

        "guid": guid,

        "status": r.status_code,

        "presentationId": extraer(
            r"presentationIdGlobal\s*=\s*'([^']+)'",
            html,
        ),

        "formTypeId": extraer(
            r"formTypeId\s*=\s*'([^']+)'",
            html,
        ),

        "formTypeName": extraer(
            r"formTypeName\s*=\s*'([^']+)'",
            html,
        ),

        "title": extraer(
            r"<title>(.*?)</title>",
            html,
        ),

        "error": "",
    }


def main():

    df = pd.read_csv("links.csv")

    df = df[df["ticker"] == "ECOG"].copy()

    print(f"ECOG -> {len(df)} GUID\n")

    resultados = []

    for i, row in enumerate(df.itertuples(), start=1):

        print(f"[{i:03}/{len(df)}] {row.guid}")

        resultados.append(
            analizar_guid(row.guid)
        )

        time.sleep(0.2)

    out = pd.DataFrame(resultados)

    Path("debug").mkdir(exist_ok=True)

    archivo = "debug/ecog_formtypes.csv"

    out.to_csv(
        archivo,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n============================")
    print("RESUMEN")
    print("============================\n")

    print(
        out.groupby(
            ["formTypeId", "formTypeName"]
        ).size().sort_values(ascending=False)
    )

    print(f"\nCSV generado: {archivo}")


if __name__ == "__main__":
    main()