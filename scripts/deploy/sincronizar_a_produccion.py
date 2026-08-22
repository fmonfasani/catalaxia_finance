# -*- coding: utf-8 -*-
"""
Sincroniza tablas de SQLite a PostgreSQL de produccion, sin TRUNCATE ciego
===========================================================================
POR QUE NO SE USA migrate_sqlite_to_pg.py

  Ese script hace TRUNCATE + INSERT + swap sobre `screener`. Ya esta medido que
  ese reemplazo VACIA 12 columnas que la API sirve hoy -- ccl, precio_ars,
  precio_usd, precio_fuente, precio_dif_iamc, cusip, dr_level, cedear_ratio,
  cedear_x, div_adr_12m, div_yield_adr, last_div_date.

  Y esto es lo que lo hace peligroso: la guarda de filas NO lo detecta. Entran
  572 y salen 572. El conteo dice que salio bien.

  Ver migrations/003_screener_iamc_mep.sql, seccion "OJO CON EL ORDEN".

LAS DOS ESTRATEGIAS, Y CUANDO USAR CADA UNA

  upsert    INSERT ... ON CONFLICT DO UPDATE. No borra nada. Para tablas donde
            produccion puede tener filas que local no tiene y hay que
            conservarlas.

  reemplazo DELETE + INSERT dentro de UNA transaccion. Para tablas donde local
            es la version autoritativa completa. No es TRUNCATE: si el INSERT
            falla, el DELETE se deshace.

  Ninguna de las dos toca `screener` por defecto. Esa tabla tiene columnas que
  solo viven en produccion; para ella se usa --solo-columnas.

EL NULL EN LA CLAVE PRIMARIA, QUE COSTO UNA CORRIDA

  PostgreSQL rechaza NULL en una columna NOT NULL de la PK, y `COPY ... NULL ''`
  convierte la cadena vacia de vuelta a NULL. Las filas de origen BYMA llevan
  tipo_balance = '' y se caian todas.

  Por eso el NULL viaja como el centinela @@NULL@@ y la cadena vacia viaja como
  cadena vacia. Son cosas distintas y el CSV tiene que distinguirlas.

  Lo mismo paso al reves: el primer upsert de cnv_estados_norm no coincidio con
  NINGUNA fila (84.316 + 106.421 = 190.737) porque produccion tenia
  fecha_reexpresion = '' y local traia la fecha. Distinta clave, cero conflictos,
  duplicado completo. De ahi la verificacion obligatoria de abajo.

USO
    python scripts/deploy/sincronizar_a_produccion.py --dry-run
    python scripts/deploy/sincronizar_a_produccion.py --tabla ratios_cnv
    python scripts/deploy/sincronizar_a_produccion.py --todas
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")

HOST = os.environ.get("CATALAXIA_HOST", "89.167.96.239")
USER = os.environ.get("CATALAXIA_SSH_USER", "root")
CONT = os.environ.get("CATALAXIA_DB_CONTAINER", "catalaxia-db")
PGUSER = os.environ.get("CATALAXIA_PG_USER", "catalaxia")
PGDB = os.environ.get("CATALAXIA_PG_DB", "catalaxia")

NUL = "@@NULL@@"

# tabla -> (estrategia, columnas de la PK)
#   Las columnas de la PK viajan como cadena vacia cuando son NULL en SQLite.
PLAN = {
    "cnv_estados_norm":      ("reemplazo", ("cuit", "concepto", "period_end",
                                            "fecha_reexpresion", "tipo_balance")),
    "cnv_estados_v2":        ("reemplazo", ("cuit", "concepto", "period_end",
                                            "fecha_reexpresion", "tipo_balance")),
    "ratios_cnv":            ("reemplazo", ("cuit",)),
    "silver_norm":           ("reemplazo", ()),
    "validaciones":          ("reemplazo", ()),
    "certificacion_nueva":   ("reemplazo", ()),
    "dolarito_cotizaciones": ("reemplazo", ()),
}


def sh(cmd, entrada=None):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          input=entrada)


def psql(sql):
    """Corre SQL en el PostgreSQL de produccion y devuelve la salida."""
    ruta = f"/tmp/_sync_{os.getpid()}.sql"
    local = Path(tempfile.gettempdir()) / f"_sync_{os.getpid()}.sql"
    local.write_text(sql, encoding="utf-8")
    sh(f'scp -o StrictHostKeyChecking=no "{local}" {USER}@{HOST}:{ruta}')
    r = sh(f'ssh -o StrictHostKeyChecking=no {USER}@{HOST} '
           f'"docker cp {ruta} {CONT}:{ruta} >/dev/null && '
           f'docker exec {CONT} psql -U {PGUSER} -d {PGDB} -f {ruta}"')
    local.unlink(missing_ok=True)
    return r.stdout + r.stderr


def exportar(con, tabla, pk):
    """CSV con NULL como @@NULL@@ y cadena vacia como cadena vacia.

    La distincion importa: las columnas de la PK no admiten NULL en PostgreSQL,
    y las filas de origen BYMA llevan tipo_balance = '' legitimamente.
    """
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({tabla})")]
    idx_pk = {i for i, c in enumerate(cols) if c in pk}
    destino = Path(tempfile.gettempdir()) / f"{tabla}.csv"
    n = convertidos = 0
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for fila in con.execute(f"SELECT {','.join(cols)} FROM {tabla}"):
            salida = []
            for i, x in enumerate(fila):
                if i in idx_pk:
                    if x is None:
                        convertidos += 1
                    salida.append("" if x is None else x)
                else:
                    salida.append(NUL if x is None else x)
            w.writerow(salida)
            n += 1
    return destino, cols, n, convertidos


def sincronizar(con, tabla, dry):
    estrategia, pk = PLAN[tabla]
    ruta, cols, n, conv = exportar(con, tabla, pk)
    print(f"  {tabla:<24}{n:>9,} filas   {estrategia}"
          + (f"   ({conv} NULL de PK -> '')" if conv else ""))
    if dry:
        return
    sh(f'scp -o StrictHostKeyChecking=no "{ruta}" {USER}@{HOST}:/tmp/{tabla}.csv')
    sh(f'ssh -o StrictHostKeyChecking=no {USER}@{HOST} '
       f'"docker cp /tmp/{tabla}.csv {CONT}:/tmp/ >/dev/null"')

    cuerpo = (f"DELETE FROM {tabla};\nINSERT INTO {tabla} SELECT * FROM _stage;"
              if estrategia == "reemplazo" else
              f"INSERT INTO {tabla} SELECT * FROM _stage\n"
              f"ON CONFLICT ({', '.join(pk)}) DO NOTHING;")
    salida = psql(
        "\\set ON_ERROR_STOP on\nBEGIN;\n"
        f"CREATE TEMP TABLE _stage (LIKE {tabla});\n"
        f"COPY _stage FROM '/tmp/{tabla}.csv' WITH (FORMAT csv, NULL '{NUL}');\n"
        f"SELECT count(*) AS en_stage FROM _stage;\n"
        f"{cuerpo}\n"
        f"SELECT count(*) AS final FROM {tabla};\nCOMMIT;\n")

    # VERIFICACION, no confianza. El primer upsert de cnv_estados_norm dejo la
    # tabla con las dos versiones (190.737 filas) y el COMMIT no protesto.
    final = None
    lineas = [l.strip() for l in salida.splitlines()]
    for i, l in enumerate(lineas):
        if l == "final" and i + 2 < len(lineas):
            try:
                final = int(lineas[i + 2])
            except ValueError:
                pass
    if final is None:
        print(f"     no se pudo leer el conteo final:\n{salida[-400:]}")
    elif final != n:
        print(f"     DISTINTO: local {n:,} != produccion {final:,}  <-- revisar")
    else:
        print(f"     verificado: {final:,} = {n:,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tabla")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    tablas = [a.tabla] if a.tabla else (list(PLAN) if a.todas else [])
    if not tablas:
        print("Elegi --tabla NOMBRE o --todas. Disponibles:")
        for t in PLAN:
            print(f"  {t}")
        return

    con = sqlite3.connect(str(DB))
    print(f"SINCRONIZAR -> {HOST}/{PGDB}"
          + ("   (dry-run)" if a.dry_run else ""))
    print("=" * 66)
    for t in tablas:
        if t not in PLAN:
            print(f"  {t}: no esta en PLAN, se saltea")
            continue
        sincronizar(con, t, a.dry_run)
    con.close()
    print("\n  `screener` y `facts` NO se tocan desde aca. Ver el encabezado.")


if __name__ == "__main__":
    main()
