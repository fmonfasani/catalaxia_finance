"""
20.8_catalogar_formtypes.py

Genera el catálogo maestro de tipos de formularios.

Entrada:
    debug/formtypes_sample_resumen.csv

Salida:
    datos/catalogo_formtypes.csv
    datos/catalogo_formtypes.xlsx
"""

from pathlib import Path
import html

import pandas as pd

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DEBUG = ROOT / "debug"
DATOS = ROOT / "datos"

INPUT = DEBUG / "formtypes_sample_resumen.csv"

OUT_CSV = DATOS / "catalogo_formtypes.csv"
OUT_XLSX = DATOS / "catalogo_formtypes.xlsx"

# ==========================================================
# PALABRAS CLAVE
# ==========================================================

EEFF = [
    "ESTADOS CONTABLES",
    "ESTADOS FINANCIEROS",
    "BALANCE",
    "NIIF",
    "INFORMACIÓN FINANCIERA",
    "ESTADO DE SITUACIÓN",
    "ESTADO DE RESULTADOS",
    "CONTROLADAS",
    "VINCULADAS",
]

NO_EEFF = [
    "HECHO RELEVANTE",
    "ACTA",
    "ASAMBLEA",
    "DIRECTORIO",
    "PROSPECTO",
    "AVISO",
    "MEMORIA",
    "CONVOCATORIA",
    "EDICTO",
    "CALIFICACIÓN",
    "RENUNCIA",
    "DESIGNACIÓN",
    "AUTORIZACIÓN",
    "REORGANIZACIÓN",
    "FUSIÓN",
]

# ==========================================================


def clasificar(nombre: str):

    txt = html.unescape(str(nombre)).upper()

    for p in EEFF:
        if p in txt:
            return 1, 100

    for p in NO_EEFF:
        if p in txt:
            return 0, 100

    return "", 0


# ==========================================================


def main():

    df = pd.read_csv(INPUT)

    df["formTypeName"] = df["formTypeName"].fillna("").apply(html.unescape)

    resultado = []

    for _, row in df.iterrows():

        es_eeff, confianza = clasificar(row["formTypeName"])

        resultado.append({
            "formTypeId": row["formTypeId"],
            "formTypeName": row["formTypeName"],
            "cantidad": row["cantidad"],
            "es_eeff": es_eeff,
            "confianza": confianza,
            "observaciones": "",
        })

    out = pd.DataFrame(resultado)

    out = out.sort_values(
        ["es_eeff", "cantidad"],
        ascending=[False, False],
    )

    DATOS.mkdir(exist_ok=True)

    out.to_csv(
        OUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    out.to_excel(
        OUT_XLSX,
        index=False,
    )

    print("=" * 70)
    print("CATÁLOGO GENERADO")
    print("=" * 70)

    print()

    print("EEFF detectados automáticamente:",
          (out["es_eeff"] == 1).sum())

    print("No EEFF detectados:",
          (out["es_eeff"] == 0).sum())

    print("Pendientes de revisar:",
          (out["es_eeff"] == "").sum())

    print()

    print("Archivo CSV:")
    print(OUT_CSV)

    print()

    print("Archivo Excel:")
    print(OUT_XLSX)


if __name__ == "__main__":
    main()