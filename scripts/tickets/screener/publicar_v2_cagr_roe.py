# -*- coding: utf-8 -*-
"""
PUBLICAR en screener_v2 las 11 columnas de CAGR en USD, ROE de dos fuentes y SEC
===============================================================================
QUE PUBLICA

  Once columnas que hoy existen solo en el SQLite del pipeline y que ninguna
  tabla de PostgreSQL tiene todavia:

      cagr_revenue_usd_5y    cagr_netincome_usd_5y   cagr_desde
      cagr_hasta             cagr_ejercicios         cagr_motivo
      roe_cnv                roe_edgar               roe_divergencia
      ticker_sec             dos_fuentes

POR QUE ADITIVO Y NO REGENERANDO LA TABLA

  publicar_screener_v2.py hace DROP TABLE + CREATE + INSERT: reconstruye
  screener_v2 entera desde el SQLite. Eso sirve cuando lo que se quiere es la
  foto completa, pero arrastra CUALQUIER otro cambio que el origen tenga en ese
  momento -- y el SQLite lo esta escribiendo otro proceso en paralelo.

  Aca solo hacen falta 11 columnas. Se agregan con ALTER TABLE y se rellenan con
  UPDATE por cuit. Las otras 68 columnas de screener_v2 no se tocan, y si algo
  sale mal la marcha atras es un DROP COLUMN.

QUE NO TOCA

  - `screener`: es la tabla que sirve la API (SELECT * en api/main.py:100).
    Agregarle columnas le cambiaria los 45 campos de la respuesta. No se toca.
  - El SQLite de origen: se abre en modo SOLO LECTURA (file:...?mode=ro).

USO
  set SCREENER_DB=D:/ruta/completa/a/screener.db     (o export en bash)
  python publicar_v2_cagr_roe.py --dry-run     # no escribe: dice que haria
  python publicar_v2_cagr_roe.py

MARCHA ATRAS
  ALTER TABLE screener_v2 DROP COLUMN cagr_revenue_usd_5y, DROP COLUMN ... ;
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2-binary no instalado. Correr: pip install psycopg2-binary")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
# SCREENER_DB admite ruta absoluta (el SQLite puede vivir fuera de este worktree)
# o solo el nombre del archivo, que se busca en data/.
DB = Path(os.environ.get("SCREENER_DB", "")) if os.environ.get("SCREENER_DB") else ROOT / "data" / "screener.db"
if not DB.is_absolute():
    DB = ROOT / "data" / DB

DESTINO = "screener_v2"
CLAVE = "cuit"

# (columna, tipo PG). Los tipos salen del PRAGMA table_info del origen:
# REAL -> double precision, TEXT -> text, INTEGER -> bigint.
COLUMNAS = [
    ("cagr_revenue_usd_5y",   "double precision"),
    ("cagr_netincome_usd_5y", "double precision"),
    ("cagr_desde",            "text"),
    ("cagr_hasta",            "text"),
    ("cagr_ejercicios",       "bigint"),
    ("cagr_motivo",           "text"),
    ("roe_cnv",               "double precision"),
    ("roe_edgar",             "double precision"),
    ("roe_divergencia",       "double precision"),
    ("ticker_sec",            "text"),
    ("dos_fuentes",           "bigint"),
]


def conn_pg():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "catalaxia"),
        user=os.environ.get("DB_USER", "catalaxia"),
        password=os.environ.get("DB_PASSWORD") or _pass_de_env(),
    )


def _pass_de_env():
    """Lee la clave del .env de la raiz. No se pide ni se imprime."""
    f = ROOT / ".env"
    if f.exists():
        for l in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            l = l.strip()
            for k in ("DB_PASSWORD=", "POSTGRES_PASSWORD="):
                if l.startswith(k):
                    return l.split("=", 1)[1].strip().strip('"').strip("'")
    return "catalaxia"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no escribe nada")
    a = ap.parse_args()

    if not DB.exists():
        sys.exit(f"FATAL: no existe {DB}\n  Definir SCREENER_DB con la ruta completa.")

    nombres = [c for c, _ in COLUMNAS]

    # --- origen: SOLO LECTURA. Otro proceso esta escribiendo este archivo. ----
    sl = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    sl.row_factory = sqlite3.Row
    cols_origen = {c[1] for c in sl.execute("PRAGMA table_info(screener)")}
    faltan = [c for c in nombres + [CLAVE] if c not in cols_origen]
    if faltan:
        sys.exit(f"ABORTA: al origen le faltan columnas: {', '.join(faltan)}")

    filas = sl.execute(
        f'SELECT "{CLAVE}", {", ".join(chr(34)+c+chr(34) for c in nombres)} '
        f"FROM screener").fetchall()
    cob_origen = {c: sum(1 for f in filas if f[c] is not None) for c in nombres}

    print("PUBLICAR en screener_v2: CAGR en USD, ROE de dos fuentes, SEC")
    print("=" * 68)
    print(f"  origen : {DB.name}  ({len(filas)} filas)   <- solo lectura")

    pg = conn_pg()
    pg.autocommit = False
    cur = pg.cursor()

    cur.execute("SELECT count(*) FROM %s" % DESTINO)
    n_dest = cur.fetchone()[0]
    cur.execute("""SELECT lower(column_name) FROM information_schema.columns
                   WHERE table_name=%s""", (DESTINO,))
    cols_dest = {r[0] for r in cur.fetchall()}
    print(f"  destino: {DESTINO} ({n_dest} filas, {len(cols_dest)} columnas)")

    nuevas = [c for c in nombres if c not in cols_dest]
    ya = [c for c in nombres if c in cols_dest]
    print(f"\n  columnas a agregar : {len(nuevas)}")
    if ya:
        print(f"  columnas que ya estaban (se refrescan): {', '.join(ya)}")

    # --- PRECONDICION: sin clave comun no hay nada que actualizar -------------
    cur.execute(f'SELECT "{CLAVE}" FROM "{DESTINO}"')
    claves_dest = {r[0] for r in cur.fetchall()}
    emparejan = sum(1 for f in filas if f[CLAVE] in claves_dest)
    print(f"\n  filas del origen que emparejan por {CLAVE}: {emparejan} de {len(filas)}")
    if emparejan == 0:
        pg.rollback(); pg.close(); sl.close()
        sys.exit(f"ABORTA: ninguna fila empareja por {CLAVE}. Revisar la clave.")

    print("\n  cobertura en el origen (cuantas filas traen dato):")
    for c in nombres:
        print(f"     {c:<24} {cob_origen[c]:>4}")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        pg.rollback(); pg.close(); sl.close()
        return

    # --- ALTER + UPDATE, todo en una transaccion -----------------------------
    for c, t in COLUMNAS:
        cur.execute(f'ALTER TABLE "{DESTINO}" ADD COLUMN IF NOT EXISTS "{c}" {t}')

    cur.execute("CREATE TEMP TABLE _carga (%s) ON COMMIT DROP" %
                ", ".join([f'"{CLAVE}" text'] + [f'"{c}" {t}' for c, t in COLUMNAS]))
    psycopg2.extras.execute_values(
        cur, f'INSERT INTO _carga VALUES %s',
        [tuple([f[CLAVE]] + [f[c] for c in nombres]) for f in filas], page_size=1000)

    sets = ", ".join(f'"{c}" = t."{c}"' for c in nombres)
    cur.execute(f'UPDATE "{DESTINO}" v SET {sets} FROM _carga t '
                f'WHERE t."{CLAVE}" = v."{CLAVE}"')
    n_upd = cur.rowcount
    pg.commit()

    # --- verificacion: la cobertura publicada tiene que igualar a la del origen
    print(f"\n  filas actualizadas: {n_upd}")
    print("\n  verificacion (destino vs origen):")
    malas = []
    for c in nombres:
        cur.execute(f'SELECT count("{c}") FROM "{DESTINO}"')
        n = cur.fetchone()[0]
        ok = "OK" if n == cob_origen[c] else "REVISAR"
        if n != cob_origen[c]:
            malas.append(c)
        print(f"     {c:<24} v2={n:>4}   origen={cob_origen[c]:>4}   {ok}")

    cur.execute("SELECT count(*) FROM screener")
    print(f"\n  control: `screener` sigue con {cur.fetchone()[0]} filas y "
          f"sus columnas intactas (no se toco)")
    cur.execute(f'SELECT count(*) FROM "{DESTINO}"')
    print(f"  control: `{DESTINO}` sigue con {cur.fetchone()[0]} filas")
    pg.close(); sl.close()

    if malas:
        sys.exit(f"\nATENCION: no coincide la cobertura en: {', '.join(malas)}")
    print("\nOK -- la API no cambia: sigue sirviendo `screener`.")


if __name__ == "__main__":
    main()
