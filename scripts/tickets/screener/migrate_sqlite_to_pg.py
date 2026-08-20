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
DB = ROOT / "data" / "screener.db"

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

        try:
            cur_pg.execute(f'TRUNCATE TABLE "{table}" CASCADE')
            batch = []
            for row in rows:
                vals = tuple(row[k] for k in columns)
                batch.append(vals)
            psycopg2.extras.execute_values(
                cur_pg,
                f'INSERT INTO "{table}" ({cols_str}) VALUES %s',
                batch,
                page_size=5000,
            )
            pg.commit()
            print(f"OK    {table}: {len(rows)} rows")
            total_rows += len(rows)
        except Exception as e:
            pg.rollback()
            print(f"ERROR {table}: {e}")
            cur_pg2 = pg.cursor()
            ok = 0
            fallidas = 0
            for row in rows:
                vals = tuple(row[k] for k in columns)
                try:
                    cur_pg2.execute(
                        f'INSERT INTO "{table}" ({cols_str}) VALUES ({ph_str})',
                        vals,
                    )
                    ok += 1
                except Exception as e2:
                    fallidas += 1
                    if fallidas <= 3:
                        print(f"     fila rechazada: {e2}")
                if ok % 500 == 0:
                    pg.commit()
            pg.commit()
            print(f"  -> {ok}/{len(rows)} inserted row-by-row"
                  f" ({fallidas} rechazadas)")
            if fallidas:
                errores.append((table, f"{fallidas} filas rechazadas"))
            total_rows += ok
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
