"""
20.7_formtypes_global.py

Analiza TODOS los publicview de links.csv y construye
el catálogo global de formTypeId.

Proyecto:

cnv/
│
├── datos/
│   └── links.csv
│
├── debug/
│   ├── formtypes_global.csv
│   └── formtypes_resumen.csv
│
└── scripts/

"""

from pathlib import Path
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

OUT = DEBUG / "formtypes_global.csv"
RESUMEN = DEBUG / "formtypes_resumen.csv"

DEBUG.mkdir(exist_ok=True)


# ==========================================================
# CONFIG
# ==========================================================

BASE = "https://aif2.cnv.gov.ar/presentations/publicview/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137 Safari/537.36"
    )
}

SLEEP = 0.10


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
# HELPERS
# ==========================================================

def extraer(regex, html):
    m = regex.search(html)
    return m.group(1).strip() if m else ""


def analizar(guid):

    url = BASE + guid

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        r.raise_for_status()

        html = r.text

        return (
            r.status_code,
            extraer(RX_PRESENTATION, html),
            extraer(RX_FORM_ID, html),
            extraer(RX_FORM_NAME, html),
            "",
        )

    except Exception as e:

        return (
            "ERROR",
            "",
            "",
            "",
            str(e),
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=" * 80)
    print("FORM TYPES GLOBAL")
    print("=" * 80)

    df = pd.read_csv(LINKS)

    print(f"\nGUID encontrados: {len(df):,}")

    if OUT.exists():

        procesados = pd.read_csv(OUT)

        guids_ok = set(procesados.guid)

        print(f"Ya procesados: {len(guids_ok):,}")

    else:

        procesados = pd.DataFrame()

        guids_ok = set()

    pendientes = df[~df.guid.isin(guids_ok)].copy()

    print(f"Pendientes: {len(pendientes):,}\n")

    total = len(df)

    nuevos = []

    for i, row in enumerate(
        pendientes.itertuples(index=False),
        start=1,
    ):

        print(
            f"[{len(guids_ok)+i:06}/{total}] "
            f"{row.ticker} "
            f"{row.guid}"
        )

        status, pid, fid, fname, error = analizar(row.guid)

        nuevos.append(
            {
                "ticker": row.ticker,
                "empresa": row.empresa,
                "guid": row.guid,
                "presentationId": pid,
                "formTypeId": fid,
                "formTypeName": fname,
                "status": status,
                "error": error,
            }
        )

        if len(nuevos) >= 50:

            bloque = pd.DataFrame(nuevos)

            if OUT.exists():

                bloque.to_csv(
                    OUT,
                    mode="a",
                    header=False,
                    index=False,
                    encoding="utf-8-sig",
                )

            else:

                bloque.to_csv(
                    OUT,
                    index=False,
                    encoding="utf-8-sig",
                )

            nuevos = []

        time.sleep(SLEEP)

    if nuevos:

        bloque = pd.DataFrame(nuevos)

        if OUT.exists():

            bloque.to_csv(
                OUT,
                mode="a",
                header=False,
                index=False,
                encoding="utf-8-sig",
            )

        else:

            bloque.to_csv(
                OUT,
                index=False,
                encoding="utf-8-sig",
            )

    print("\nGenerando resumen...")

    out = pd.read_csv(OUT)

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

    resumen.to_csv(
        RESUMEN,
        index=False,
        encoding="utf-8-sig",
    )

    print()

    print(resumen.to_string(index=False))

    print("\n===========================================")
    print("Archivos generados")
    print("===========================================")
    print(OUT)
    print(RESUMEN)

    print("\nTotal GUID:", len(out))
    print("FormTypes distintos:", resumen.shape[0])


if __name__ == "__main__":
    main()