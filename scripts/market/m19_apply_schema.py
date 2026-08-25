# -*- coding: utf-8 -*-
"""
M19 -- Aplica el schema market_* a PostgreSQL (idempotente).
Uso:  python scripts/market/m19_apply_schema.py
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg2

HERE = Path(__file__).resolve().parent
SQL = HERE / "market_schema.sql"


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "catalaxia"),
        user=os.environ.get("DB_USER", "catalaxia"),
        password=os.environ.get("DB_PASSWORD", "catalaxia"),
    )


def main():
    ddl = SQL.read_text(encoding="utf-8")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(ddl)
    conn.commit()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_name LIKE 'market\\_%' ESCAPE '\\'
        ORDER BY 1
    """)
    tablas = [r[0] for r in cur.fetchall()]
    print(f"market_* en PG ({len(tablas)}):")
    for t in tablas:
        print("  -", t)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
