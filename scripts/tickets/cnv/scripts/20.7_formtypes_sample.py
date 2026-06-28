"""
20.7_formtypes_sample.py

Construye un catálogo de formType utilizando una muestra
balanceada por empresa.

Entrada:
    datos/links.csv

Salida:
    debug/formtypes_sample.csv
    debug/formtypes_sample_resumen.csv
"""

from pathlib import Path
import random
import re
import time

import pandas as pd
import requests

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"
DEBUG = ROOT / "debug"

LINKS = DATOS / "links.csv"

OUT = DEBUG / "formtypes_sample.csv"
RESUMEN = DEBUG / "formtypes_sample_resumen.csv"

DEBUG.mkdir(exist_ok=True)

# ==========================================================
# CONFIG
# ==========================================================

GUIDS_POR_EMPRESA = 50
SEED = 1234
SLEEP = 0.10

BASE = "https://aif2.cnv.gov.ar/presentations/publicview/"

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137 Safari/537.36"
}

random.seed(SEED)

# ==========================================================
# REGEX
# ==========================================================

RX_PRESENTATION = re.compile(
    r"presentationIdGlobal\s*=\s*'([^']+)'",
    re.I,
)

RX_FORM_ID = re.compile(
    r"formTypeId\s*=\s*'([^']+)'",
    re.I,
)

RX_FORM_NAME = re.compile(
    r"formTypeName\s*=\s*'([^']+)'",
    re.I,
)

# ==========================================================

def extraer(rx, html):

    m = rx.search(html)

    return m.group(1).strip() if m else ""


def analizar(guid):

    try:

        r = requests.get(
            BASE + guid,
            headers=HEADERS,
            timeout=30,
        )

        r.raise_for_status()

        html = r.text

        return {

            "status": r.status_code,

            "presentationId":
                extraer(RX_PRESENTATION, html),

            "formTypeId":
                extraer(RX_FORM_ID, html),

            "formTypeName":
                extraer(RX_FORM_NAME, html),

            "error": "",

        }

    except Exception as e:

        return {

            "status": "ERROR",

            "presentationId": "",

            "formTypeId": "",

            "formTypeName": "",

            "error": str(e),

        }

# ==========================================================

def construir_muestra(df):

    muestras = []

    for ticker, grupo in df.groupby("ticker"):

        n = min(GUIDS_POR_EMPRESA, len(grupo))

        muestras.append(
            grupo.sample(
                n=n,
                random_state=SEED,
            )
        )

    return pd.concat(muestras).reset_index(drop=True)

# ==========================================================

def main():

    df = pd.read_csv(LINKS)

    muestra = construir_muestra(df)

    print("=" * 70)
    print("FORMTYPES SAMPLE")
    print("=" * 70)

    print()

    print("Empresas:", muestra.ticker.nunique())

    print("GUID seleccionados:", len(muestra))

    print()

    resultados = []

    total = len(muestra)

    for i, row in enumerate(
        muestra.itertuples(index=False),
        start=1,
    ):

        print(
            f"[{i:04}/{total}] "
            f"{row.ticker}"
        )

        r = analizar(row.guid)

        r["ticker"] = row.ticker
        r["empresa"] = row.empresa
        r["guid"] = row.guid

        resultados.append(r)

        time.sleep(SLEEP)

    out = pd.DataFrame(resultados)

    out.to_csv(
        OUT,
        index=False,
        encoding="utf-8-sig",
    )

    resumen = (

        out.groupby(
            [
                "formTypeId",
                "formTypeName",
            ],
            dropna=False,
        )

        .size()

        .reset_index(name="cantidad")

        .sort_values(
            "cantidad",
            ascending=False,
        )

    )

    resumen.to_csv(
        RESUMEN,
        index=False,
        encoding="utf-8-sig",
    )

    print()

    print("=" * 70)
    print("FORM TYPES")
    print("=" * 70)

    print(
        resumen.to_string(index=False)
    )

    print()

    print("CSV:")
    print(OUT)

    print()

    print("RESUMEN:")
    print(RESUMEN)


if __name__ == "__main__":
    main()