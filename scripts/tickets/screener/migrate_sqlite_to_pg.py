"""
Migracion: SQLite -> PostgreSQL.
Copia todas las tablas from data/screener.db a la DB configurada via env vars.

Uso:
  DB_TYPE=postgresql DB_HOST=... DB_NAME=catalaxia DB_USER=catalaxia DB_PASSWORD=... \\
    python migrate_sqlite_to_pg.py

  # O con defaults (localhost:5432, catalaxia/catalaxia)
  python migrate_sqlite_to_pg.py
"""
import os, sys, sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2-binary no instalado. Correr: pip install psycopg2-binary")
    sys.exit(1)


def get_pg_conn():
    params = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "catalaxia"),
        "user": os.environ.get("DB_USER", "catalaxia"),
        "password": os.environ.get("DB_PASSWORD", "catalaxia"),
    }
    return psycopg2.connect(**params)


TABLES_ORDER = [
    "empresas", "tickers", "facts", "ratios", "precios",
    "cnv_estados_v2", "cnv_estados_norm", "cnv_estados_suspect",
    "cnv_dividendos", "cnv_estados",
    "adr_ratios", "adr_dividendos", "cedear_ratios",
    "iamc_precios", "mapa_entidades", "ratios_cnv",
    "screener", "instrumentos", "descargas_log",
]

COLUMN_MAPPING = {
    "screener": {
        "MargenNeto": "margen_neto",
        "DeudaEBITDA": "deuda_ebitda",
        "CAGR_EPS_5y": "cagr_eps_5y",
        "CAGR_flag": "cagr_flag",
        "PriceBook": "price_book",
        "PriceSales": "price_sales",
        "MarketCapUSD": "market_cap_usd",
        "Max52w": "max_52w",
        "Min52w": "min_52w",
    },
    "ratios_cnv": {
        # OJO: las claves deben coincidir EXACTO con el nombre en SQLite.
        # Estaba "margenneto" en minusculas y la columna real es "MargenNeto",
        # asi que el mapeo nunca se aplicaba y el INSERT fallaba.
        "MargenNeto": "margen_neto",
        "DeudaEBITDA": "deuda_ebitda",
        "FCFYield": "fcf_yield",
        "CAGR_EPS_5y": "cagr_eps_5y",
        "CAGR_flag": "cagr_flag",
    }
}


def main():
    if not DB.exists():
        print(f"FATAL: {DB} no existe")
        sys.exit(1)

    sl = sqlite3.connect(str(DB))
    sl.row_factory = sqlite3.Row
    pg = get_pg_conn()
    pg.autocommit = False

    total_rows = 0
    errores = []

    for table in TABLES_ORDER:
        # Check if table exists in SQLite
        cur = sl.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cur.fetchone():
            print(f"SKIP  {table}: no existe en SQLite")
            continue

        rows = sl.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"OK    {table}: 0 rows")
            continue

        col_info = sl.execute(f"PRAGMA table_info({table})").fetchall()
        columns = [c[1] for c in col_info]
        # PG lowercases unquoted identifiers; match SQLite uppercase names
        pg_columns = [c.lower() for c in columns]

        # Aplicar mapeo de columnas si existe
        if table in COLUMN_MAPPING:
            mapping = COLUMN_MAPPING[table]
            pg_columns = [mapping.get(orig, pg_col) for orig, pg_col in zip(columns, pg_columns)]

        # Batch insert
        placeholders = ["%s"] * len(columns)
        qcols = [f'"{c}"' for c in pg_columns]
        cols_str = ", ".join(qcols)
        ph_str = ", ".join(placeholders)

        cur_pg = pg.cursor()

        # --- PRECONDICION: comprobar el destino ANTES de destruir nada ---------
        # TRUNCATE vacia la tabla y despues inserta. Si el INSERT falla (por
        # ejemplo, porque el esquema de destino no tiene una columna nueva), la
        # tabla queda VACIA en produccion y el fallback fila-por-fila lo silencia.
        # Medido el 2026-08-20: `screener` habria quedado en 0 filas por 11
        # columnas de la migracion MEP ausentes en PostgreSQL.
        cur_pg.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s
        """, (table,))
        destino = {r[0].lower() for r in cur_pg.fetchall()}
        if not destino:
            print(f"ABORTA {table}: la tabla no existe en PostgreSQL. "
                  f"Aplica sql/init/01_schema.sql primero.")
            errores.append((table, "tabla inexistente en destino"))
            cur_pg.close()
            continue
        faltan = [c for c in pg_columns if c.lower() not in destino]
        if faltan:
            print(f"ABORTA {table}: faltan columnas en PostgreSQL: {', '.join(faltan)}")
            print(f"       No se hace TRUNCATE. Aplica sql/init/01_schema.sql primero.")
            errores.append((table, "faltan columnas: " + ", ".join(faltan)))
            cur_pg.close()
            continue
        # ----------------------------------------------------------------------

        # ── SWAP ATOMICO ──────────────────────────────────────────────────────
        # En vez de TRUNCATE + INSERT sobre la tabla en produccion (que la deja
        # vacia si el INSERT falla), se carga en una tabla nueva y se cambia el
        # nombre. PostgreSQL tiene DDL transaccional, asi que el swap es atomico:
        # o entra entera, o no se toca nada. Mientras carga, la tabla vieja sigue
        # sirviendo a la API sin enterarse.
        #
        # La anterior NO se borra: queda como "<tabla>__prev" para poder volver
        # atras con un solo RENAME.
        tmp = f"{table}__new"
        prev = f"{table}__prev"

        # El punto ciego del patron: en PostgreSQL las claves foraneas y las
        # vistas apuntan al OID de la tabla, no a su nombre. Si algo depende de
        # `table`, al renombrarla la dependencia SIGUE a "<tabla>__prev" y la
        # tabla nueva se queda sin ella -- en silencio.
        # Por eso se detecta antes y se cae con un mensaje, en vez de publicar una
        # tabla a la que le falta la mitad de sus garantias.
        cur_pg.execute("""
            SELECT c.conname, c.conrelid::regclass::text
            FROM pg_constraint c
            WHERE c.confrelid = %s::regclass AND c.contype = 'f'
        """, (table,))
        fks = cur_pg.fetchall()
        cur_pg.execute("""
            SELECT DISTINCT dependent.relname
            FROM pg_depend d
            JOIN pg_rewrite r     ON r.oid = d.objid
            JOIN pg_class dependent ON dependent.oid = r.ev_class
            WHERE d.refobjid = %s::regclass AND dependent.relkind IN ('v', 'm')
        """, (table,))
        vistas = [r[0] for r in cur_pg.fetchall()]
        if fks or vistas:
            det = []
            if fks:
                det.append("FK desde " + ", ".join(f"{t} ({n})" for n, t in fks))
            if vistas:
                det.append("vistas: " + ", ".join(vistas))
            print(f"ABORTA {table}: hay dependencias que seguirian a la tabla vieja "
                  f"al renombrar -> {' | '.join(det)}")
            print(f"       Para esta tabla usa carga in-place, o recrea las "
                  f"dependencias despues del swap.")
            errores.append((table, "dependencias impiden el swap: " + " | ".join(det)))
            cur_pg.close()
            continue

        try:
            cur_pg.execute(f'DROP TABLE IF EXISTS "{tmp}"')
            # LIKE ... INCLUDING ALL copia tipos, defaults, constraints e indices.
            cur_pg.execute(f'CREATE TABLE "{tmp}" (LIKE "{table}" INCLUDING ALL)')
            batch = []
            for row in rows:
                vals = tuple(row[k] for k in columns)
                batch.append(vals)
            psycopg2.extras.execute_values(
                cur_pg,
                f'INSERT INTO "{tmp}" ({cols_str}) VALUES %s',
                batch,
                page_size=5000,
            )

            # Guarda de cordura: no publicar una tabla drasticamente mas chica que
            # la que ya estaba. Un origen a medias no deberia vaciar produccion.
            cur_pg.execute(f'SELECT COUNT(*) FROM "{table}"')
            antes = cur_pg.fetchone()[0]
            ahora = len(rows)
            if antes > 0 and ahora < antes * 0.5:
                raise RuntimeError(
                    f"la carga nueva tiene {ahora} filas contra {antes} actuales "
                    f"(menos de la mitad). Se aborta el swap; la tabla vieja sigue.")

            # El swap, en una sola transaccion.
            cur_pg.execute(f'DROP TABLE IF EXISTS "{prev}" CASCADE')
            cur_pg.execute(f'ALTER TABLE "{table}" RENAME TO "{prev}"')
            cur_pg.execute(f'ALTER TABLE "{tmp}" RENAME TO "{table}"')
            pg.commit()
            print(f"OK    {table}: {ahora} rows (antes {antes}; anterior en {prev})")
            total_rows += ahora
        except Exception as e:
            pg.rollback()
            try:
                cur_pg.execute(f'DROP TABLE IF EXISTS "{tmp}"')
                pg.commit()
            except Exception:
                pg.rollback()
            print(f"ERROR {table}: {e}")
            print(f"      La tabla en produccion NO se toco.")
            errores.append((table, str(e)[:120]))
            cur_pg.close()
            continue
        # Ya no hay fallback fila-por-fila: con el swap atomico o entra la tabla
        # entera o no se toca nada, asi que insertar "lo que se pueda" dejaria la
        # tabla a medias sin que nadie lo note. Es justo lo que se quiso evitar.
        finally:
            cur_pg.close()

    sl.close()
    pg.close()
    print(f"\nTotal: {total_rows} rows migradas a PostgreSQL")

    # Un resumen que se pueda creer: antes, migrar 400 de 572 filas y abortar
    # tablas enteras terminaba igual que un exito. Ahora se reporta y se sale
    # con codigo != 0, para que un job encadenado se entere.
    if errores:
        print("\n" + "=" * 62)
        print("MIGRACION INCOMPLETA -- %d tabla(s) con problemas:" % len(errores))
        for t, motivo in errores:
            print("   %-24s %s" % (t, motivo))
        print("=" * 62)
        sys.exit(1)


if __name__ == "__main__":
    main()
