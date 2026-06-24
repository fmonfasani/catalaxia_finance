"""
PASO 5 — Comparar Investing.com (extraido a mano) contra SEC EDGAR + yfinance.

Actualiza IN-PLACE el archivo de seguimiento del usuario:
  "informe_seguimiento_detallado.xlsx - Investing_Ratios.csv" (raiz del repo)

Estructura del CSV (23 columnas, fila 0 y 1 son headers):
  A-G  : datos de Investing, extraidos a mano.       NUNCA SE TOCAN.
  H    : columna separadora vacia.                   NUNCA SE TOCA.
  I-O  : ticker + 6 ratios calculados con EDGAR+yfinance (este script los llena).
  P    : columna separadora vacia.                   NUNCA SE TOCA.
  Q-W  : ticker + % de divergencia con signo (EDGAR-Investing)/Investing*100.

Reglas de seguridad (pedidas explicitamente por el usuario):
  - El cruce Investing <-> EDGAR es por TEXTO de ticker (columna A), nunca por
    posicion de fila. Columna Q se reescribe siempre con el mismo ticker de A,
    para poder auditar a simple vista que A == I == Q en cada fila.
  - Si un ticker no tiene CIK, no tiene financials, o le falta el dato
    puntual de una metrica -> esa celda queda VACIA. Nunca se inventa, nunca
    se arrastra el valor de otra fila/metrica.
  - ROE compara TTM contra TTM (roe_ttm), NUNCA el roe_cagr_5y de la Fase A
    -- son magnitudes distintas (nivel vs tasa de crecimiento), confundirlas
    daria una "comparacion" sin sentido. Ver 03_calcular_ratios.py.

Formato (acordado con el usuario):
  - I-O: porcentaje con signo "13,14%" para metricas que son % (Crecimiento
    EPS, Margen Neto, ROE, Payout); numero plano "19,31" para PER y EPS.
    Coma como separador decimal en todo, igual que el lado de Investing.
  - Q-W: divergencia relativa con signo, ej "+2,45%" / "-13,80%".

Input : informe_seguimiento_detallado.xlsx - Investing_Ratios.csv (se sobreescribe)
        datos/ratios_tickets.csv
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

ENCODING = "cp1252"  # el csv viene de un Excel guardado en Windows, no UTF-8

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "informe_seguimiento_detallado.xlsx - Investing_Ratios.csv"
TMP_PATH = CSV_PATH.with_suffix(".tmp.csv")
RATIOS_CSV = Path(__file__).resolve().parent / "datos" / "ratios_tickets.csv"

# Rango sano de filas/columnas esperado. Si el archivo viene con otra forma
# (ej. Excel lo reguardo con ; como separador regional y quedo todo
# desalineado, o agrego cientos de filas de relleno) ABORTAR antes de
# escribir nada -- mejor frenar que corromper el archivo del usuario.
FILAS_MIN, FILAS_MAX = 95, 115
N_COLS = 23


class ArchivoInesperado(Exception):
    pass


def detectar_delimitador(primera_linea: str) -> str:
    """El usuario tiene Excel configurado en es-AR: a veces guarda el CSV
    con ',' (como vino originalmente) y a veces Excel lo re-exporta con ';'
    (separador de lista regional, porque ',' es el separador decimal). Hay
    que leer con el que tenga el archivo en este momento, no asumir."""
    return ";" if primera_linea.count(";") > primera_linea.count(",") else ","

HEADER_ROWS = 2  # fila 0 = grupos (Investing/EDGAR/Comparacion), fila 1 = nombres de columna
N_COLS = 23

COL_TICKER_INV = 0
COL_TICKER_EDGAR = 8
COL_TICKER_CMP = 16

# nombre de metrica -> (col Investing, col EDGAR, col Comparacion, es_porcentaje, campo en ratios_tickets.csv)
METRICAS = {
    "per":      (1, 9, 17, False, "per_ttm"),
    "eps":      (2, 10, 18, False, "eps_ttm_diluted"),
    "crec_eps": (3, 11, 19, True, "cagr_eps_5y"),
    "margen":   (4, 12, 20, True, "margen_neto_ttm"),
    "roe":      (5, 13, 21, True, "roe_ttm"),
    "payout":   (6, 14, 22, True, "payout_ttm"),
}


def parse_investing(raw: str) -> float | None:
    """Convierte '29,36%' o '20,09' a float. None si esta vacio o es texto
    no numerico (ej 'JAMAICA O SIDNY', '#VALUE!')."""
    if raw is None:
        return None
    s = raw.strip().rstrip("%").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fmt_valor(v: float, es_porcentaje: bool) -> str:
    s = f"{v:.2f}".replace(".", ",")
    return s + "%" if es_porcentaje else s


def fmt_diff(v: float) -> str:
    return f"{v:+.2f}".replace(".", ",") + "%"


def cargar_ratios_edgar() -> dict[str, dict]:
    with open(RATIOS_CSV, encoding="utf-8") as f:
        return {row["ticker"]: row for row in csv.DictReader(f)}


def leer_csv_validado() -> tuple[list[list[str]], str]:
    """Lee el CSV detectando el delimitador actual y validando que la forma
    sea la esperada. Lanza ArchivoInesperado en vez de devolver datos raros."""
    with open(CSV_PATH, encoding=ENCODING, newline="") as f:
        primera_linea = f.readline()
    delim = detectar_delimitador(primera_linea)

    with open(CSV_PATH, encoding=ENCODING, newline="") as f:
        rows = [list(r) for r in csv.reader(f, delimiter=delim)]

    if not (FILAS_MIN <= len(rows) <= FILAS_MAX):
        raise ArchivoInesperado(
            f"El archivo tiene {len(rows)} filas, se esperaban entre "
            f"{FILAS_MIN} y {FILAS_MAX}. Probablemente Excel lo re-guardo "
            f"con otro formato (delimitador='{delim}'). No se modifica nada."
        )

    fila0 = rows[0]
    if "Investing" not in fila0[0] or "EDGAR" not in "".join(fila0) or "Comparacion" not in "".join(fila0):
        raise ArchivoInesperado(
            "La fila de encabezados no tiene la forma esperada "
            "(Investing / EDGAR / Comparacion). No se modifica nada."
        )

    anchos = {len(r) for r in rows[:5]}
    if max(anchos) < N_COLS - 2:
        raise ArchivoInesperado(
            f"Las primeras filas tienen muy pocas columnas ({anchos}), "
            f"el delimitador detectado ('{delim}') probablemente esta mal. "
            f"No se modifica nada."
        )

    return rows, delim


def main() -> None:
    print("=" * 60)
    print("  PASO 5 -- Comparar Investing vs EDGAR+yfinance")
    print("=" * 60)

    rows, delim = leer_csv_validado()
    print(f"\n  Delimitador detectado          : '{delim}'")
    print(f"  Filas en el CSV de seguimiento : {len(rows)}")

    edgar = cargar_ratios_edgar()
    print(f"  Tickers con ratios EDGAR       : {len(edgar)}")

    stats = {"comparadas": 0, "sin_fila_csv": 0, "sin_cik": 0, "sin_financials": 0, "fila_vacia": 0}
    metricas_comparadas = 0
    metricas_sin_investing = 0
    metricas_sin_edgar = 0

    for i, row in enumerate(rows):
        while len(row) < N_COLS:
            row.append("")

        if i < HEADER_ROWS:
            continue

        ticker = row[COL_TICKER_INV].strip()
        if not ticker:
            stats["fila_vacia"] += 1
            continue

        edgar_row = edgar.get(ticker)

        # Columna Q siempre refleja el ticker de A -- permite auditar a ojo
        # que A == I == Q en cualquier fila.
        row[COL_TICKER_CMP] = ticker

        if edgar_row is None:
            stats["sin_cik"] += 1
            row[COL_TICKER_EDGAR] = ""
            for _, col_e, col_c, _, _ in METRICAS.values():
                row[col_e] = ""
                row[col_c] = ""
            continue

        if edgar_row.get("_error"):
            stats["sin_financials"] += 1
            row[COL_TICKER_EDGAR] = ""
            for _, col_e, col_c, _, _ in METRICAS.values():
                row[col_e] = ""
                row[col_c] = ""
            continue

        row[COL_TICKER_EDGAR] = ticker
        stats["comparadas"] += 1

        for nombre, (col_inv, col_edgar, col_cmp, es_pct, campo) in METRICAS.items():
            edgar_val = to_float(edgar_row.get(campo))

            if edgar_val is None:
                row[col_edgar] = ""
                row[col_cmp] = ""
                metricas_sin_edgar += 1
                continue

            edgar_disp = edgar_val * 100 if es_pct else edgar_val
            row[col_edgar] = fmt_valor(edgar_disp, es_pct)

            investing_val = parse_investing(row[col_inv])
            if investing_val is None or investing_val == 0:
                row[col_cmp] = ""
                metricas_sin_investing += 1
                continue

            diff_pct = (edgar_disp - investing_val) / investing_val * 100
            row[col_cmp] = fmt_diff(diff_pct)
            metricas_comparadas += 1

    # Escritura segura: primero a un .tmp, se valida que el resultado tenga
    # la forma esperada y que GS (fila de control conocida) este coherente,
    # y solo entonces se reemplaza el archivo real. Si algo de esto falla,
    # el archivo del usuario nunca se toca.
    with open(TMP_PATH, "w", encoding=ENCODING, newline="") as f:
        csv.writer(f, delimiter=delim).writerows(rows)

    with open(TMP_PATH, encoding=ENCODING, newline="") as f:
        rows_verificacion = [list(r) for r in csv.reader(f, delimiter=delim)]

    fila_gs = next((r for r in rows_verificacion if r and r[0] == "GS"), None)
    if len(rows_verificacion) != len(rows):
        TMP_PATH.unlink(missing_ok=True)
        raise ArchivoInesperado(
            f"El archivo temporal quedo con {len(rows_verificacion)} filas, "
            f"se esperaban {len(rows)}. Se descarta, el archivo real no se toca."
        )
    if fila_gs is None or fila_gs[COL_TICKER_EDGAR] != "GS" or fila_gs[COL_TICKER_CMP] != "GS":
        TMP_PATH.unlink(missing_ok=True)
        raise ArchivoInesperado(
            "La fila de control (GS) no quedo coherente en el archivo "
            "temporal (A == I == Q). Se descarta, el archivo real no se toca."
        )

    os.replace(TMP_PATH, CSV_PATH)

    print("\n" + "-" * 60)
    print(f"  Filas con ticker             : {sum(stats.values()) - stats['fila_vacia']}")
    print(f"  Filas vacias (separadores)   : {stats['fila_vacia']}")
    print(f"  Comparadas (con CIK+fin.)    : {stats['comparadas']}")
    print(f"  Sin CIK (revision manual)    : {stats['sin_cik']}")
    print(f"  Sin financials EDGAR         : {stats['sin_financials']}")
    print(f"  Metricas individuales OK     : {metricas_comparadas}")
    print(f"  Metricas sin valor EDGAR     : {metricas_sin_edgar}")
    print(f"  Metricas sin valor Investing : {metricas_sin_investing}")
    print(f"\n  OK {CSV_PATH}")
    print("\nPaso 5 completo.")


if __name__ == "__main__":
    try:
        main()
    except ArchivoInesperado as e:
        print(f"\n  ABORTADO: {e}")
        print("  Verifica que el archivo este cerrado en Excel y sin "
              "modificaciones manuales pendientes, y volve a correr el script.")
        raise SystemExit(1)
