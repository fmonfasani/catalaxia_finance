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
        "margenneto": "margen_neto",
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
            for row in rows:
                vals = tuple(row[k] for k in columns)
                try:
                    cur_pg2.execute(
                        f'INSERT INTO "{table}" ({cols_str}) VALUES ({ph_str})',
                        vals,
                    )
                    ok += 1
                except Exception as e2:
                    pass
                if ok % 500 == 0:
                    pg.commit()
            pg.commit()
            print(f"  -> {ok}/{len(rows)} inserted row-by-row")
            total_rows += ok
        finally:
            cur_pg.close()

    sl.close()
    pg.close()
    print(f"\nTotal: {total_rows} rows migradas a PostgreSQL")


if __name__ == "__main__":
    main()
