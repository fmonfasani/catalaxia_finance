#!/usr/bin/env python3
"""
Carga tabla 'screener' (572 empresas) a PostgreSQL con histórico.

Crea dos tablas:
1. screener_ratios: snapshot actual (última carga)
2. screener_ratios_hist: histórico (todos los cambios capturados)

Uso:
  python load_screener_ratios.py [--db-host localhost] [--db-port 5432]

Variables de entorno:
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""
import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import psycopg2
import psycopg2.extras

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB_SQLITE = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
EXPORT_JSON = ROOT / "data" / "screener_export.json"


def get_pg_conn():
    params = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "catalaxia"),
        "user": os.environ.get("DB_USER", "catalaxia"),
        "password": os.environ.get("DB_PASSWORD", "catalaxia"),
    }
    return psycopg2.connect(**params)


def create_schema(pg):
    """Crea tablas screener_ratios y screener_ratios_hist"""
    cursor = pg.cursor()

    # Tabla principal: snapshot actual
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS screener_ratios (
        ticker TEXT PRIMARY KEY,
        cuit TEXT,
        period_ref DATE,
        grupo TEXT,  -- sp500, adr, byma_only

        -- Ratios fundamentales
        roe NUMERIC,
        roa NUMERIC,
        margen_neto NUMERIC,
        deuda_ebitda NUMERIC,
        eps NUMERIC,
        fcf_ce NUMERIC,
        payout NUMERIC,
        cagr_eps_5y NUMERIC,
        cagr_flag TEXT,
        per NUMERIC,
        price_book NUMERIC,
        price_sales NUMERIC,

        -- Precios
        precio_usd NUMERIC,
        precio_ars NUMERIC,
        precio_fuente TEXT,  -- iamc, yfinance, ccl, implied
        ccl NUMERIC,

        -- Valuación
        market_cap_usd NUMERIC,
        currency TEXT,
        max_52w NUMERIC,
        min_52w NUMERIC,
        ev_ebitda NUMERIC,
        margen_operativo NUMERIC,

        -- Metadata
        es_financiera BOOLEAN,
        sector TEXT,
        fuente_fund TEXT,  -- edgar, cnv
        payout_status TEXT,  -- calculado, no_paga, falta_dato

        -- Flags
        flag_cnv_fallback BOOLEAN,
        flag_no_significativo BOOLEAN,
        dato_desactualizado BOOLEAN,
        precio_dif_iamc NUMERIC,

        -- ADR / CEDEAR
        adr_ratio INTEGER,
        cedear_ratio TEXT,
        cedear_x NUMERIC,
        cusip TEXT,
        dr_level TEXT,
        div_adr_12m NUMERIC,
        last_div_date DATE,
        div_yield_adr NUMERIC,

        -- Metadata técnica
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        provenance TEXT
    )
    """)

    # Tabla histórica: todos los snapshots
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS screener_ratios_hist (
        id SERIAL PRIMARY KEY,
        ticker TEXT,
        cuit TEXT,
        period_ref DATE,
        grupo TEXT,

        roe NUMERIC, roa NUMERIC, margen_neto NUMERIC, deuda_ebitda NUMERIC,
        eps NUMERIC, fcf_ce NUMERIC, payout NUMERIC, cagr_eps_5y NUMERIC,
        cagr_flag TEXT, per NUMERIC, price_book NUMERIC, price_sales NUMERIC,

        precio_usd NUMERIC, precio_ars NUMERIC, precio_fuente TEXT, ccl NUMERIC,
        market_cap_usd NUMERIC, currency TEXT, max_52w NUMERIC, min_52w NUMERIC,
        ev_ebitda NUMERIC, margen_operativo NUMERIC,

        es_financiera BOOLEAN, sector TEXT, fuente_fund TEXT, payout_status TEXT,
        flag_cnv_fallback BOOLEAN, flag_no_significativo BOOLEAN,
        dato_desactualizado BOOLEAN, precio_dif_iamc NUMERIC,

        adr_ratio INTEGER, cedear_ratio TEXT, cedear_x NUMERIC,
        cusip TEXT, dr_level TEXT, div_adr_12m NUMERIC,
        last_div_date DATE, div_yield_adr NUMERIC,

        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        provenance TEXT,

        UNIQUE(ticker, period_ref, loaded_at)
    )
    """)

    # Índices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_screener_ratios_ticker ON screener_ratios(ticker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_screener_ratios_hist_ticker ON screener_ratios_hist(ticker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_screener_ratios_hist_period ON screener_ratios_hist(period_ref)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_screener_ratios_hist_grupo ON screener_ratios_hist(grupo)")

    pg.commit()
    cursor.close()
    print("[OK] Schema creado")


def load_from_sqlite(sqlite_path):
    """Lee tabla 'screener' desde SQLite"""
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM screener ORDER BY ticker")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def normalize_value(val):
    """Convierte valores SQLite a tipos PostgreSQL"""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        if val.lower() in ("true", "1"):
            return True
        elif val.lower() in ("false", "0", ""):
            return False
        elif val == "":
            return None
    return val


def insert_ratios(pg, rows):
    """Inserta filas en screener_ratios y screener_ratios_hist"""
    cursor = pg.cursor()

    # TRUNCATE screener_ratios para evitar duplicados
    cursor.execute("TRUNCATE TABLE screener_ratios")

    columns = [
        "ticker", "cuit", "period_ref", "grupo",
        "roe", "roa", "margen_neto", "deuda_ebitda", "eps", "fcf_ce", "payout",
        "cagr_eps_5y", "cagr_flag", "per", "price_book", "price_sales",
        "precio_usd", "precio_ars", "precio_fuente", "ccl",
        "market_cap_usd", "currency", "max_52w", "min_52w", "ev_ebitda", "margen_operativo",
        "es_financiera", "sector", "fuente_fund", "payout_status",
        "flag_cnv_fallback", "flag_no_significativo", "dato_desactualizado", "precio_dif_iamc",
        "adr_ratio", "cedear_ratio", "cedear_x", "cusip", "dr_level", "div_adr_12m", "last_div_date",
        "div_yield_adr", "provenance"
    ]

    placeholders = ", ".join(["%s"] * len(columns))
    col_str = ", ".join([f'"{c}"' for c in columns])

    batch = []
    for row in rows:
        # Map de columnas SQLite → PostgreSQL
        values = (
            row.get("ticker"),
            row.get("cuit"),
            row.get("ultimo_periodo"),
            row.get("grupo"),
            normalize_value(row.get("ROE")),
            normalize_value(row.get("ROA")),
            normalize_value(row.get("MargenNeto")),
            normalize_value(row.get("DeudaEBITDA")),
            normalize_value(row.get("EPS")),
            normalize_value(row.get("FCF_CE")),
            normalize_value(row.get("Payout")),
            normalize_value(row.get("CAGR_EPS_5y")),
            row.get("CAGR_flag"),
            normalize_value(row.get("PER")),
            normalize_value(row.get("PriceBook")),
            normalize_value(row.get("PriceSales")),
            normalize_value(row.get("Precio")),
            normalize_value(row.get("precio_ars")),
            row.get("precio_fuente"),
            normalize_value(row.get("ccl")),
            normalize_value(row.get("MarketCapUSD")),
            row.get("Currency"),
            normalize_value(row.get("Max52w")),
            normalize_value(row.get("Min52w")),
            normalize_value(row.get("ev_ebitda")),
            normalize_value(row.get("margen_operativo")),
            row.get("es_financiera") == 1,
            row.get("sector"),
            row.get("fuente_fund"),
            row.get("payout_status"),
            row.get("flag_cnv_fallback") == 1,
            row.get("flag_no_significativo") == 1,
            row.get("dato_desactualizado") == 1,
            normalize_value(row.get("precio_dif_iamc")),
            normalize_value(row.get("adr_ratio")),
            row.get("cedear_ratio"),
            normalize_value(row.get("cedear_x")),
            row.get("cusip"),
            row.get("dr_level"),
            normalize_value(row.get("div_adr_12m")),
            row.get("last_div_date"),
            normalize_value(row.get("div_yield_adr")),
            row.get("provenance"),
        )
        batch.append(values)

    # Insert en tabla principal
    try:
        psycopg2.extras.execute_values(
            cursor,
            f'INSERT INTO screener_ratios ({col_str}) VALUES %s',
            batch,
            page_size=1000,
        )
        print(f"[OK] Insertadas {len(batch)} filas en screener_ratios")
    except Exception as e:
        print(f"[X] Error al insertar: {e}")
        pg.rollback()
        return False

    # Insert en tabla histórica (duplicar)
    try:
        psycopg2.extras.execute_values(
            cursor,
            f'INSERT INTO screener_ratios_hist ({col_str}) VALUES %s',
            batch,
            page_size=1000,
        )
        print(f"[OK] Insertadas {len(batch)} filas en screener_ratios_hist")
    except Exception as e:
        print(f"[X] Error en historico: {e}")

    pg.commit()
    cursor.close()
    return True


def main():
    print("[*] Cargando screener_ratios desde SQLite a PostgreSQL")

    # Verificar archivos
    if not DB_SQLITE.exists():
        print(f"[X] {DB_SQLITE} no existe")
        sys.exit(1)

    # Conectar
    print("[*] Conectando a PostgreSQL (localhost:5432)...")
    pg = get_pg_conn()

    # Crear schema
    print("[*] Creando schema...")
    create_schema(pg)

    # Leer datos
    print(f"[*] Leyendo screener.db ({DB_SQLITE})...")
    rows = load_from_sqlite(DB_SQLITE)
    print(f"    Encontradas {len(rows)} empresas")

    # Insertar
    print("[*] Cargando a PostgreSQL...")
    ok = insert_ratios(pg, rows)

    pg.close()

    if ok:
        print("\n[OK] MIGRACION COMPLETADA")
        print(f"     - screener_ratios: {len(rows)} empresas (snapshot actual)")
        print(f"     - screener_ratios_hist: {len(rows)} registros (historico)")
    else:
        print("\n[FAIL] MIGRACION FALLO")
        sys.exit(1)


if __name__ == "__main__":
    main()
