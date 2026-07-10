"""
Conexion a base de datos, activando SQLite o PostgreSQL segun DB_TYPE.

PostgreSQL se activa con variables de entorno:
  DB_TYPE=postgresql
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

Por defecto usa SQLite (data/screener.db) para compatibilidad hacia atras.
"""
import os, sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
SQLITE_PATH = ROOT / "data" / "screener.db"

_use_pg = os.environ.get("DB_TYPE", "").lower() in ("postgresql", "postgres", "pg")
_pg_conn = None


def _get_pg_conn():
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "catalaxia"),
        user=os.environ.get("DB_USER", "catalaxia"),
        password=os.environ.get("DB_PASSWORD", "catalaxia"),
    )


def get_conn():
    global _pg_conn
    if _use_pg:
        if _pg_conn is None or _pg_conn.closed:
            _pg_conn = _get_pg_conn()
        return _pg_conn
    else:
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=60000")
        return conn


def close_conn(conn):
    global _pg_conn
    if _use_pg:
        _pg_conn = None
    if conn:
        conn.close()


def using_postgresql():
    return _use_pg
