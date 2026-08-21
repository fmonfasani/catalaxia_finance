# -*- coding: utf-8 -*-
"""
FASE 0: Setup de tablas schema
Crea todas las tablas para el ETL robusto.
"""
import sqlite3
import os as _os
import os

PROD = os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))

def setup_tables():
    c = sqlite3.connect(PROD)

    print("=" * 80)
    print("FASE 0: CREAR TABLAS SCHEMA")
    print("=" * 80)

    # 1. bronze_raw (inmutable, con trazabilidad)
    c.execute("""CREATE TABLE IF NOT EXISTS bronze_raw (
        id INTEGER PRIMARY KEY,
        ticker TEXT,
        period_end TEXT,
        concepto TEXT,
        monto_raw TEXT,
        unidad TEXT,
        moneda TEXT,
        escala REAL,
        consolidado INT,
        fuente TEXT,
        docid TEXT,
        fecha_descarga TEXT,
        hash TEXT,
        ts TEXT
    )""")
    print("✅ Tabla bronze_raw")

    # 2. silver_norm (normalizado + validado)
    c.execute("""CREATE TABLE IF NOT EXISTS silver_norm (
        ticker TEXT,
        period_end TEXT,
        concepto TEXT,
        valor REAL,
        valor_original REAL,
        moneda TEXT,
        escala REAL,
        factor_aplicado INT,
        incluye_recpam INT,
        vintage_reexpresion TEXT,
        cierre_ok INT,
        continuidad_ok INT,
        ancla_ok INT,
        nivel_certificacion TEXT,
        detalle_falla TEXT,
        ts TEXT,
        PRIMARY KEY(ticker, period_end, concepto)
    )""")
    print("✅ Tabla silver_norm")

    # 3. (libre) -- la dolarización ya no vive acá: cada fuente de dólar tiene su
    #    propia tabla, creada por su propio fetcher.
    #    MEP/CCL/oficial/... -> `dolarito_cotizaciones`
    #       (scripts/dolares/fetch_dolarito_historico.py)

    # 4. validaciones (los 9 cruces)
    c.execute("""CREATE TABLE IF NOT EXISTS validaciones (
        ticker TEXT,
        period_end TEXT,
        cruce_id INT,
        cruce_nombre TEXT,
        resultado TEXT,
        valor_nuestro REAL,
        valor_esperado REAL,
        divergencia_pct REAL,
        detalle TEXT,
        ts TEXT,
        PRIMARY KEY(ticker, period_end, cruce_id)
    )""")
    print("✅ Tabla validaciones")

    # 5. certificacion_nueva (resumen por período)
    c.execute("""CREATE TABLE IF NOT EXISTS certificacion_nueva (
        ticker TEXT,
        period_end TEXT,
        identidades_ok INT,
        identidades_detalle TEXT,
        continuidad_ok INT,
        continuidad_detalle TEXT,
        ancla_investing_ok INT,
        ancla_investing_ratio REAL,
        ancla_pb_ok INT,
        ancla_ps_ok INT,
        pb_ratio REAL,
        ps_ratio REAL,
        nivel_certificacion TEXT,
        causa_falla TEXT,
        ts TEXT,
        PRIMARY KEY(ticker, period_end)
    )""")
    print("✅ Tabla certificacion_nueva")

    # 6. investing_comparacion (crosscheck)
    c.execute("""CREATE TABLE IF NOT EXISTS investing_comparacion (
        ticker TEXT,
        period_end TEXT,
        concepto TEXT,
        valor_nuestro REAL,
        valor_investing REAL,
        ratio REAL,
        dentro_tolerancia INT,
        fuente_investing TEXT,
        ts TEXT,
        PRIMARY KEY(ticker, period_end, concepto)
    )""")
    print("✅ Tabla investing_comparacion")

    c.commit()
    c.close()

    print("\n" + "=" * 80)
    print("✅ FASE 0 COMPLETADA: 5 tablas creadas en screener.db")
    print("=" * 80)

if __name__ == '__main__':
    setup_tables()
