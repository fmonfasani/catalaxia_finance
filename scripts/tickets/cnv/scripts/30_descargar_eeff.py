"""
30_descargar_eeff.py

Descargador industrial de EEFF CNV

Responsabilidad:
- Leer links_eeff.csv
- Crear estructura de carpetas
- Lanzar workers
- Reanudar descargas
- Mostrar estadísticas

La descarga HTTP vive en:

cnv_ir/downloader.py
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
import time

from cnv_ir.downloader import descargar_eeff

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"

EEFF = ROOT / "eeff"

LINKS = DATOS / "links_eeff.csv"

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

# ==========================================================
# SESSION
# ==========================================================

session = requests.Session()

session.headers.update({

    "User-Agent": USER_AGENT

})

# ==========================================================


def crear_carpetas(df):

    print()

    print("Creando carpetas...")

    for ticker in sorted(df.ticker.unique()):

        (EEFF / ticker).mkdir(

            exist_ok=True

        )

    print("OK")


# ==========================================================


def archivos_existentes():

    existentes = set()

    for html in EEFF.rglob("*.html"):

        existentes.add(html.stem)

    return existentes


# ==========================================================


def construir_trabajos(df):

    existentes = archivos_existentes()

    trabajos = []

    for row in df.itertuples():

        presentation = str(row.presentationId)

        if presentation in existentes:

            continue

        trabajos.append(row)

    return trabajos


# ==========================================================


def main():

    print("=" * 70)

    print("DESCARGADOR EEFF")

    print("=" * 70)

    print()

    print("Leyendo links...")

    df = pd.read_csv(

        LINKS,

        low_memory=False,

    )

    print(df.shape)

    crear_carpetas(df)

    trabajos = construir_trabajos(df)

    print()

    print("Pendientes:", len(trabajos))

    print()

    inicio = time.time()

    ok = 0

    error = 0

    with ThreadPoolExecutor(

        max_workers=MAX_WORKERS

    ) as pool:

        futures = [

            pool.submit(

                descargar_eeff,

                session,

                row,

                EEFF,

                TIMEOUT,

            )

            for row in trabajos

        ]

        for i, future in enumerate(

            as_completed(futures),

            start=1,

        ):

            try:

                future.result()

                ok += 1

            except Exception as e:

                error += 1

                print(e)

            if i % 50 == 0:

                print(

                    f"[{i}/{len(futures)}] "

                    f"OK={ok} "

                    f"ERROR={error}"

                )

    segundos = round(

        time.time() - inicio,

        1,

    )

    print()

    print("=" * 70)

    print("FINALIZADO")

    print("=" * 70)

    print()

    print("OK:", ok)

    print("ERROR:", error)

    print("Tiempo:", segundos, "seg")


# ==========================================================

if __name__ == "__main__":

    main()