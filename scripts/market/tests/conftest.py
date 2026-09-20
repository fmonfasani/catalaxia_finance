# -*- coding: utf-8 -*-
"""Infraestructura de la matriz de tests Market Data.

Cada corrida de pytest levanta una base PostgreSQL descartable
(`catalaxia_market_test`) con el DDL real de `market_schema.sql`, y un RAW
base descartable bajo data/raw/_test/. Cero red: la fuente es FixtureSource.

Destino de test (fix de la regresion F-001, ver
outputs/docs/fase_market/F001_REGRESION_TEST_MATRIX.md): DEV (`DB_PORT=5433`,
contenedor `catalaxia-engine-dev`) por defecto, nunca produccion -- mismo
patron que `engine/config.py` ya usa para SEC/CNV (`ENGINE_DB_PORT` default
"5433"). El override de `DB_HOST`/`DB_PORT` es TRANSITORIO (context manager
`_target_dev()`), scoped a las llamadas que crean/pueblan la base de test --
NO se deja pisado en `os.environ` para el resto del proceso de pytest. Motivo
concreto: `tests/test_f014_venue_ticker.py` corre en el mismo proceso y
necesita leer produccion real (5432) a proposito (evidencia post-migracion
013); un `os.environ.setdefault` a nivel de modulo lo hubiera roto en
silencio (encontrado y corregido en esta misma pasada).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg2
import pytest

HERE = Path(__file__).resolve().parent
MARKET_DIR = HERE.parent
sys.path.insert(0, str(MARKET_DIR))

import m2_fetch_engine as eng                    # noqa: E402
import market_core as core                       # noqa: E402
from market_source import FetchResult            # noqa: E402

ROOT = eng.ROOT
TEST_DB = os.environ.get("MARKET_TEST_DB", "catalaxia_market_test")
RAW_TEST_BASE = ROOT / "data" / "raw" / "_test"
DEV_HOST = os.environ.get("MARKET_TEST_DB_HOST", "localhost")
DEV_PORT = os.environ.get("MARKET_TEST_DB_PORT", "5433")

TZ_BUE = ZoneInfo("America/Argentina/Buenos_Aires")
TZ_NY = ZoneInfo("America/New_York")


@contextlib.contextmanager
def _target_dev():
    """Fuerza DB_HOST/DB_PORT a dev SOLO durante el bloque -- restaura lo que
    hubiera antes al salir. No usar `setdefault`: eso mutaria el proceso
    entero de pytest, incluidos modulos de test que a proposito necesitan
    otro destino (ver docstring del archivo)."""
    previos = {k: os.environ.get(k) for k in ("DB_HOST", "DB_PORT")}
    os.environ["DB_HOST"] = DEV_HOST
    os.environ["DB_PORT"] = DEV_PORT
    try:
        yield
    finally:
        for k, v in previos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _admin_conn():
    with _target_dev():
        # R2: este default es FIXTURE de desarrollo (contenedor local 5433,
        # base descartable), NO credencial de produccion. Permanece como
        # excepcion allowlisted en tests/test_r2_secretos.py
        # (test_scripts_sin_default_credencial). Override con DB_PASSWORD.
        c = psycopg2.connect(
            host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]),
            dbname="postgres",
            user=os.environ.get("DB_USER", "catalaxia"),
            password=os.environ.get("DB_PASSWORD", "catalaxia"))
    c.autocommit = True
    return c


@pytest.fixture(scope="session")
def db():
    adm = _admin_conn()
    cur = adm.cursor()
    cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (TEST_DB,))
    cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
    cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    adm.close()

    # write=True: crea el esquema de test. Nunca dispara la guarda F-001
    # (MarketProdWriteBlocked) porque, dentro de `_target_dev()`, DB_PORT=5433
    # no es "produccion" para `market_db.es_produccion()`.
    with _target_dev():
        conn = eng.pg_conn(TEST_DB, write=True)
    ddl = (MARKET_DIR / "market_schema.sql").read_text(encoding="utf-8")
    with conn.cursor() as c:
        c.execute(ddl)
    conn.commit()
    yield conn
    conn.close()
    if os.environ.get("MARKET_TEST_KEEP") != "1":
        adm = _admin_conn()
        with adm.cursor() as c:
            c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                      "WHERE datname=%s AND pid<>pg_backend_pid()", (TEST_DB,))
            c.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
        adm.close()
        shutil.rmtree(RAW_TEST_BASE, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def raw_base():
    shutil.rmtree(RAW_TEST_BASE, ignore_errors=True)
    RAW_TEST_BASE.mkdir(parents=True, exist_ok=True)
    original = eng.RAW_BASE
    eng.RAW_BASE = RAW_TEST_BASE
    yield RAW_TEST_BASE
    eng.RAW_BASE = original


@pytest.fixture
def limpiar(db):
    """Aisla cada escenario: vacia las tablas de datos, conserva el DDL."""
    with db.cursor() as c:
        c.execute("""TRUNCATE market_price_daily, market_data_changes,
                     market_corporate_actions, market_snapshots,
                     market_data_quality, market_fetch_log, market_raw_files,
                     market_raw_runs RESTART IDENTITY CASCADE""")
        c.execute("""DELETE FROM market_symbol_mappings""")
        c.execute("""DELETE FROM market_instruments""")
    db.commit()
    yield db


# ------------------------------------------------------------- utilidades

def alta_instrumento(conn, iid, entity_id, canon, ticker_yahoo, currency,
                     exchange, itype="LOCAL", status="MAPPED"):
    with conn.cursor() as c:
        c.execute("""INSERT INTO market_instruments
            (instrument_id, entity_id, ticker_canonico, instrument_type,
             exchange, country, currency, source)
            VALUES (%s,%s,%s,%s,%s,'AR',%s,'test')
            ON CONFLICT (instrument_id) DO NOTHING""",
                  (iid, entity_id, canon, itype, exchange, currency))
        c.execute("""INSERT INTO market_symbol_mappings
            (instrument_id, ticker_yahoo, exchange_expected, currency_expected,
             status, source, resolved_at)
            VALUES (%s,%s,%s,%s,%s,'test',now())
            ON CONFLICT (instrument_id) DO UPDATE SET
              ticker_yahoo=EXCLUDED.ticker_yahoo, status=EXCLUDED.status""",
                  (iid, ticker_yahoo, exchange, currency, status))
    conn.commit()
    return eng.InstrumentSpec(iid, entity_id, canon, ticker_yahoo,
                              currency, exchange)


def ruedas(n, hasta: date, tz=TZ_BUE):
    """n fechas habiles consecutivas terminando en `hasta`."""
    out, d = [], hasta
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def serie(fechas, tz=TZ_BUE, base=100.0, dividendos=None, splits=None):
    """DataFrame estilo yfinance (auto_adjust=False, actions=True)."""
    dividendos = dividendos or {}
    splits = splits or {}
    filas = []
    for i, d in enumerate(fechas):
        o = round(base + i, 2)
        c = round(o + 0.5, 2)
        h = round(max(o, c) + 0.75, 2)
        lo = round(min(o, c) - 0.75, 2)
        filas.append({
            "Open": o, "High": h, "Low": lo, "Close": c,
            "Adj Close": round(c * 0.93, 6), "Volume": 1000 + i * 7,
            "Dividends": float(dividendos.get(d, 0.0)),
            "Stock Splits": float(splits.get(d, 0.0)),
        })
    idx = pd.DatetimeIndex([datetime(d.year, d.month, d.day, tzinfo=tz)
                            for d in fechas])
    return pd.DataFrame(filas, index=idx)


def resultado(df, metadata=None, attempts=1) -> FetchResult:
    return FetchResult(ok=True, df=df, metadata=dict(metadata or {}),
                       raw_bytes=df.to_csv(index=True).encode("utf-8"),
                       attempts=attempts)


META_BUE = {"currency": "ARS", "exchangeName": "BUE",
            "fullExchangeName": "Buenos Aires", "symbol": "TST.BA",
            "instrumentType": "EQUITY"}
META_NY = {"currency": "USD", "exchangeName": "NYQ",
           "fullExchangeName": "NYSE", "symbol": "TST",
           "instrumentType": "EQUITY"}


def contar(conn, sql, args=()):
    with conn.cursor() as c:
        c.execute(sql, args)
        return c.fetchall()


def uno(conn, sql, args=()):
    with conn.cursor() as c:
        c.execute(sql, args)
        r = c.fetchone()
    return r[0] if r else None
