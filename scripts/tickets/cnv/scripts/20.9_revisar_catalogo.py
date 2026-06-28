"""
20.9_revisar_catalogo.py

Revisión interactiva del catálogo de formType.

Entrada:
    datos/catalogo_formtypes.csv

Salida:
    datos/catalogo_formtypes.csv (actualizado)
    datos/catalogo_formtypes.xlsx
"""

from pathlib import Path
import html
import pandas as pd

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"

CATALOGO = DATOS / "catalogo_formtypes.csv"
EXCEL = DATOS / "catalogo_formtypes.xlsx"

# ==========================================================

df = pd.read_csv(CATALOGO)

# asegurar texto
df["formTypeName"] = (
    df["formTypeName"]
    .fillna("")
    .apply(html.unescape)
)

# convertir es_eeff a string para detectar vacíos
df["es_eeff"] = df["es_eeff"].fillna("").astype(str)

pendientes = df[df["es_eeff"] == ""].copy()

print("=" * 80)
print("REVISIÓN DE FORMULARIOS")
print("=" * 80)
print()

print(f"Pendientes: {len(pendientes)}")
print()

for idx in pendientes.index:

    row = df.loc[idx]

    print("-" * 80)
    print(f"formTypeId   : {row.formTypeId}")
    print(f"Cantidad     : {row.cantidad}")
    print(f"Formulario   : {row.formTypeName}")
    print()

    while True:

        r = input(
            "[1]=EEFF   [0]=NO EEFF   [ENTER]=pendiente : "
        ).strip()

        if r == "":
            break

        if r in ("0", "1"):

            df.at[idx, "es_eeff"] = int(r)

            break

        print("Valor inválido.")

print()
print("=" * 80)

# ordenar
df = df.sort_values(
    ["es_eeff", "cantidad"],
    ascending=[False, False],
)

df.to_csv(
    CATALOGO,
    index=False,
    encoding="utf-8-sig",
)

df.to_excel(
    EXCEL,
    index=False,
)

print("Catálogo actualizado.")
print(CATALOGO)
print(EXCEL)

print()

print("RESUMEN")

print(df["es_eeff"].value_counts(dropna=False))