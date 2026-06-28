"""
02_clasificar_entidades.py

Clasifica las entidades del AutoComplete de la CNV
utilizando reglas heurísticas.

Salida:

datos/entidades_clasificadas.csv
datos/entidades_clasificadas.xlsx
"""

from pathlib import Path
import re

import pandas as pd


# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"
DEBUG = ROOT / "debug"

AUTOCOMPLETE = DEBUG / "autocomplete.json"

OUT_CSV = DATOS / "entidades_clasificadas.csv"
OUT_XLSX = DATOS / "entidades_clasificadas.xlsx"


# ==========================================================
# REGLAS
# ==========================================================

REGLAS = [

    ("Sociedad de Garantía Recíproca",
     100,
     [
         r"\bSGR\b",
         r"GARANTIA RECIPROCA",
     ]),

    ("Fondo Común de Inversión",
     100,
     [
         r"FONDO",
         r"\bFCI\b",
     ]),

    ("Fideicomiso",
     100,
     [
         r"FIDEICOMISO",
     ]),

    ("Banco",
     100,
     [
         r"\bBANCO\b",
     ]),

    ("Aseguradora",
     100,
     [
         r"SEGUROS",
         r"ASEGURAD",
     ]),

    ("Mercado",
     100,
     [
         r"MERCADO",
     ]),

    ("ALyC / Valores",
     95,
     [
         r"VALORES",
         r"SECURITIES",
         r"BROKER",
     ]),

    ("Sociedad Gerente",
     100,
     [
         r"SOCIEDAD GERENTE",
         r"GERENTE",
     ]),

    ("PyME",
     90,
     [
         r"PYME",
         r"PYMES",
     ]),

    ("Cooperativa",
     100,
     [
         r"COOPERATIVA",
     ]),

    ("Empresa S.A.",
     70,
     [
         r"\bS\.A\b",
         r"\bS\.A\.",
     ]),

]


# ==========================================================
# CLASIFICADOR
# ==========================================================

def clasificar(nombre):

    texto = nombre.upper()

    for categoria, score, reglas in REGLAS:

        for r in reglas:

            if re.search(r, texto):

                return categoria, score

    return "Sin clasificar", 0


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=" * 80)
    print("CLASIFICADOR DE ENTIDADES CNV")
    print("=" * 80)

    df = pd.read_json(AUTOCOMPLETE)

    categorias = []
    scores = []

    for nombre in df.descripcion:

        cat, score = clasificar(nombre)

        categorias.append(cat)
        scores.append(score)

    df["categoria"] = categorias
    df["confianza"] = scores

    df = df.sort_values(
        ["categoria", "descripcion"]
    )

    df.to_csv(
        OUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    df.to_excel(
        OUT_XLSX,
        index=False,
    )

    print("\n==============================")
    print("RESUMEN")
    print("==============================\n")

    resumen = (
        df.groupby("categoria")
        .size()
        .reset_index(name="cantidad")
        .sort_values(
            "cantidad",
            ascending=False,
        )
    )

    print(resumen.to_string(index=False))

    print("\n==============================")
    print("SIN CLASIFICAR")
    print("==============================\n")

    pendientes = df[df.categoria == "Sin clasificar"]

    print(len(pendientes))

    if len(pendientes):

        print()

        print(
            pendientes[
                [
                    "descripcion"
                ]
            ].head(50).to_string(index=False)
        )

    print("\n==============================")
    print("ARCHIVOS")
    print("==============================")

    print(OUT_CSV)
    print(OUT_XLSX)


if __name__ == "__main__":
    main()