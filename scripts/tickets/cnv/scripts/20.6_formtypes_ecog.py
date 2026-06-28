"""
20.6_formtypes_ecog.py

Analiza TODOS los publicview de ECOG y descubre los distintos
tipos de formularios (formTypeId / formTypeName).

Salida:
cnv/debug/ecog_formtypes.csv
"""

from pathlib import Path
import re
import time

import pandas as pd
import requests


# ==========================================================
# RUTAS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"
DEBUG = ROOT / "debug"

LINKS_CSV = DATOS / "links.csv"

DEBUG.mkdir(exist_ok=True)


# ==========================================================
# CONFIG
# ==========================================================

BASE = "https://aif2.cnv.gov.ar/presentations/publicview/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
    )
}


# ==========================================================
# HELPERS
# ==========================================================

def extraer(regex: str, html: str) -> str:
    m = re.search(regex, html, re.I | re.S)
    return m.group(1).strip() if m else ""


def analizar_guid(guid: str) -> dict:

    url = BASE + guid

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        r.raise_for_status()

        html = r.text

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

    except Exception as e:

        return {

            "guid": guid,

            "status": "ERROR",

            "presentationId": "",

            "formTypeId": "",

            "formTypeName": "",

            "title": "",

            "error": str(e),
        }


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=" * 70)
    print("ANALISIS DE FORM TYPES - ECOG")
    print("=" * 70)

    print(f"\nLeyendo:\n{LINKS_CSV}")

    if not LINKS_CSV.exists():
        raise FileNotFoundError(
            f"\nNo existe:\n{LINKS_CSV}"
        )

    df = pd.read_csv(LINKS_CSV)

    print(f"\nTotal registros: {len(df):,}")

    df = df[df["ticker"] == "ECOG"].copy()

    print(f"GUID ECOG: {len(df)}\n")

    resultados = []

    total = len(df)

    for i, row in enumerate(df.itertuples(index=False), start=1):

        print(f"[{i:03}/{total}] {row.guid}")

        resultados.append(
            analizar_guid(row.guid)
        )

        time.sleep(0.20)

    out = pd.DataFrame(resultados)

    archivo = DEBUG / "ecog_formtypes.csv"

    out.to_csv(
        archivo,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n")
    print("=" * 70)
    print("FORM TYPES ENCONTRADOS")
    print("=" * 70)

    resumen = (
        out.groupby(
            ["formTypeId", "formTypeName"],
            dropna=False,
        )
        .size()
        .reset_index(name="cantidad")
        .sort_values(
            "cantidad",
            ascending=False,
        )
    )

    print(resumen.to_string(index=False))

    print("\n")
    print("=" * 70)
    print("CSV GENERADO")
    print("=" * 70)
    print(archivo)

    resumen_csv = DEBUG / "ecog_formtypes_resumen.csv"

    resumen.to_csv(
        resumen_csv,
        index=False,
        encoding="utf-8-sig",
    )

    print(resumen_csv)


if __name__ == "__main__":
    main()