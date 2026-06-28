"""
01_auditoria_autocomplete.py

Audita el endpoint AutoComplete de la CNV.

Objetivos:

- Cantidad de registros
- Campos disponibles
- Empresas sin ticker
- CUIT duplicados
- Tickers duplicados
- Tipos de entidades
- Estadísticas generales
"""

from pathlib import Path
import json

import pandas as pd
import requests


URL = "https://www.cnv.gov.ar/SitioWeb/Empresas/AutoComplete"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def main():

    print("=" * 80)
    print("AUDITORIA AUTOCOMPLETE CNV")
    print("=" * 80)

    r = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )

    r.raise_for_status()

    data = r.json()

    print("\nCantidad de registros:", len(data))

    Path("../debug").mkdir(exist_ok=True)

    with open(
        "../debug/autocomplete.json",
        "w",
        encoding="utf8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )

    df = pd.DataFrame(data)

    print("\n==============================")
    print("COLUMNAS")
    print("==============================")

    print(df.columns.tolist())

    print("\n==============================")
    print("TIPOS")
    print("==============================")

    print(df.dtypes)

    print("\n==============================")
    print("NULOS")
    print("==============================")

    print(df.isna().sum())

    print("\n==============================")
    print("EMPRESAS SIN TICKER")
    print("==============================")

    if "ticker" in df.columns:

        sin_ticker = (
            df["ticker"]
            .fillna("")
            .astype(str)
            .str.strip()
            == ""
        ).sum()

        print(sin_ticker)

    print("\n==============================")
    print("EMPRESAS SIN CUIT")
    print("==============================")

    if "cuit" in df.columns:

        sin_cuit = (
            df["cuit"]
            .fillna("")
            .astype(str)
            .str.strip()
            == ""
        ).sum()

        print(sin_cuit)

    print("\n==============================")
    print("TICKERS UNICOS")
    print("==============================")

    if "ticker" in df.columns:
        print(df["ticker"].nunique())

    print("\n==============================")
    print("CUIT UNICOS")
    print("==============================")

    if "cuit" in df.columns:
        print(df["cuit"].nunique())

    print("\n==============================")
    print("TICKERS DUPLICADOS")
    print("==============================")

    if "ticker" in df.columns:

        dup = (
            df.groupby("ticker")
            .size()
            .reset_index(name="cantidad")
        )

        dup = dup[dup.cantidad > 1]

        print(dup)

    print("\n==============================")
    print("CUIT DUPLICADOS")
    print("==============================")

    if "cuit" in df.columns:

        dup = (
            df.groupby("cuit")
            .size()
            .reset_index(name="cantidad")
        )

        dup = dup[dup.cantidad > 1]

        print(dup)

    print("\n==============================")
    print("VALORES DISTINTOS")
    print("==============================")

    for c in df.columns:

        try:

            if df[c].nunique() <= 30:

                print("\n", c)

                print(df[c].value_counts())

        except Exception:
            pass

    print("\n==============================")
    print("PRIMEROS 10 REGISTROS")
    print("==============================")

    print(df.head(10))

    salida = "../debug/autocomplete_auditoria.xlsx"

    with pd.ExcelWriter(salida) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="datos",
        )

    print("\nExcel generado:")
    print(salida)


if __name__ == "__main__":
    main()