"""
21_filtrar_eeff.py

Filtra únicamente los Estados Financieros (EEFF).

Entradas
---------
datos/links.csv
debug/formtypes_global.csv
datos/catalogo_formtypes.csv

Salida
------
datos/links_eeff.csv
"""

from pathlib import Path
import pandas as pd

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"
DEBUG = ROOT / "debug"

LINKS = DATOS / "links.csv"
FORMTYPES = DEBUG / "formtypes_global.csv"
CATALOGO = DATOS / "catalogo_formtypes.csv"

SALIDA = DATOS / "links_eeff.csv"

# ==========================================================

print("=" * 80)
print("FILTRANDO ESTADOS FINANCIEROS")
print("=" * 80)
print()

print("Leyendo archivos...")

links = pd.read_csv(
    LINKS,
    low_memory=False,
)

formtypes = pd.read_csv(
    FORMTYPES,
    low_memory=False,
)

catalogo = pd.read_csv(
    CATALOGO,
    low_memory=False,
)

# ==========================================================
# Normalización
# ==========================================================

links["guid"] = links["guid"].astype(str)

formtypes["guid"] = formtypes["guid"].astype(str)

catalogo["formTypeId"] = (
    catalogo["formTypeId"]
    .astype(str)
)

formtypes["formTypeId"] = (
    formtypes["formTypeId"]
    .astype(str)
)

# ==========================================================
# Merge GUID
# ==========================================================

print()

print("Merge links + formtypes...")

df = links.merge(

    formtypes[
        [
            "guid",
            "presentationId",
            "formTypeId",
            "formTypeName",
            "status",
        ]
    ],

    on="guid",

    how="left",

)

print("OK")

# ==========================================================
# Merge catálogo
# ==========================================================

print()

print("Merge catálogo...")

df = df.merge(

    catalogo[
        [
            "formTypeId",
            "es_eeff",
        ]
    ],

    on="formTypeId",

    how="left",

)

print("OK")

# ==========================================================
# Solo EEFF
# ==========================================================

eeff = df[

    df["es_eeff"] == 1

].copy()

eeff = eeff.sort_values(

    [

        "ticker",

        "presentationId",

    ]

)

# ==========================================================
# Guardar
# ==========================================================

eeff.to_csv(

    SALIDA,

    index=False,

    encoding="utf-8-sig",

)

# ==========================================================
# Estadísticas
# ==========================================================

print()

print("=" * 80)

print("RESUMEN")

print("=" * 80)

print()

print("Links originales:")

print(f"{len(links):,}")

print()

print("FormTypes:")

print(f"{len(formtypes):,}")

print()

print("EEFF:")

print(f"{len(eeff):,}")

print()

print("Empresas:")

print(

    eeff["ticker"]

    .nunique()

)

print()

print("Tipos EEFF:")

print(

    eeff[
        [

            "formTypeId",

            "formTypeName",

        ]

    ]

    .drop_duplicates()

    .sort_values(

        "formTypeId"

    )

)

print()

print("Balances por empresa")

print(

    eeff

    .groupby(

        "ticker"

    )

    .size()

    .sort_values(

        ascending=False

    )

)

print()

print("Archivo generado:")

print(SALIDA)