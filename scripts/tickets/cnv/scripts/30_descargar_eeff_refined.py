"""
30_descargar_eeff_refined.py

Descarga utilizando `links_eeff_refined.csv` (filtrado por formtypes whitelist).
Es una copia ligera de `30_descargar_eeff.py` apuntando al CSV refinado.
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import time
import argparse

from cnv_ir.downloader import Downloader
import cnv_ir.filesystem as fs
import cnv_ir.validator as validator
import cnv_ir.logger as logger

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"

EEFF = ROOT / "eeff"

LINKS = DATOS / "links_eeff_refined.csv"

EEFF.mkdir(exist_ok=True)

# ==========================================================
# CONFIG
# ==========================================================

MAX_WORKERS = 8

TIMEOUT = 30

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "Chrome/137 Safari/537.36"
)


def crear_carpetas(df):
    for ticker in sorted(df.ticker.unique()):
        (EEFF / ticker).mkdir(exist_ok=True)


def archivos_existentes():
    existentes = set()
    for html in EEFF.rglob("*.html"):
        existentes.add(html.stem)
    return existentes


def presentation_key(value):
    if pd.isna(value):
        return ""
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return str(value).strip()


def construir_trabajos(df):
    existentes = archivos_existentes()
    trabajos = []
    for row in df.itertuples():
        presentation = presentation_key(row.presentationId)
        if presentation and presentation in existentes:
            continue
        trabajos.append(row)
    return trabajos


def main():
    print("=" * 70)
    print("DESCARGADOR EEFF (REFINED)")
    print("=" * 70)

    df = pd.read_csv(LINKS, low_memory=False)

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of downloads (for testing)")
    args = parser.parse_args()

    crear_carpetas(df)

    trabajos = construir_trabajos(df)

    if args.limit and args.limit > 0:
        trabajos = trabajos[: args.limit]
        print(f"Limit applied: {len(trabajos)} trabajos (test mode)")

    print("Pendientes:", len(trabajos))

    inicio = time.time()
    ok = 0
    error = 0

    downloader = Downloader(
        filesystem=fs,
        validator=validator,
        csv_logger=logger,
        timeout=(5, TIMEOUT),
        user_agent=USER_AGENT,
    )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = []
        for row in trabajos:
            payload = {"ticker": row.ticker, "guid": row.guid, "url": getattr(row, "url", None)}
            futures.append(pool.submit(downloader.download, payload))

        for i, future in enumerate(as_completed(futures), start=1):
            try:
                res = future.result()
                status = getattr(res, "status", None)
                status_value = getattr(status, "value", None) if status is not None else None
                if status_value is None:
                    status_value = str(status)
                if status_value == "SUCCESS":
                    ok += 1
                else:
                    error += 1
            except Exception as e:
                error += 1
                print(e)

            if i % 50 == 0:
                print(f"[{i}/{len(futures)}] OK={ok} ERROR={error}")

    downloader.close()

    segundos = round(time.time() - inicio, 1)

    print()
    print("=" * 70)
    print("FINALIZADO")
    print("=" * 70)
    print()
    print("OK:", ok)
    print("ERROR:", error)
    print("Tiempo:", segundos, "seg")


if __name__ == "__main__":
    main()
