#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Market — puerta unica de conexion a PostgreSQL. Cierra F-001.

PROBLEMA QUE RESUELVE
---------------------
Cada script de Market abria su propia conexion con `psycopg2.connect(...)` y
`DB_PORT` por defecto **5432**, que es PRODUCCION. No habia ninguna guarda: un
`python m2_fetch_engine.py` sin variables de entorno escribia en la base viva.
El engine tiene EXT-010 desde hace tiempo; Market nunca lo tuvo, y es el
workstream que mas filas mueve (`m6_scale.py` escala a 584 instrumentos).

DOS BARRERAS INDEPENDIENTES
---------------------------
1. **Codigo** — `connect()` es de solo lectura por defecto. Escribir exige
   `write=True` explicito en el call site, y si el destino es el puerto 5432
   ademas exige `MARKET_ALLOW_PROD_WRITE=1`. Sin eso levanta y no conecta.
2. **Privilegios** — en modo lectura se conecta como `catalaxia_market_ro`
   (migracion `012_rol_market_readonly.sql`), que tiene SELECT y nada mas.
   Aunque el codigo se equivoque, la base rechaza la escritura.

Ademas, en modo lectura la sesion se abre con `readonly=True`, de modo que un
`INSERT` falla en el cliente antes de viajar.

USO
---
    import market_db

    with market_db.connect() as conn:              # lectura, seguro por defecto
        ...

    with market_db.connect(write=True) as conn:    # escritura; en 5432 exige
        ...                                        # MARKET_ALLOW_PROD_WRITE=1

Variables de entorno:
    DB_HOST DB_PORT DB_NAME              destino (DB_PORT=5432 => PRODUCCION)
    MARKET_DB_USER_RO                    rol de lectura  (def. catalaxia_market_ro)
    MARKET_DB_USER                       rol de escritura (def. catalaxia)
    DB_PASSWORD / POSTGRES_PASSWORD      credencial
    MARKET_ALLOW_PROD_WRITE=1            unico modo de escribir en 5432
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg2

PUERTO_PRODUCCION = "5432"


class MarketProdWriteBlocked(RuntimeError):
    """Se intento escribir en produccion sin habilitacion explicita (F-001)."""


def _env() -> dict:
    """Variables de proceso, con .env del repo como respaldo."""
    valores = {}
    raiz = next((p for p in Path(__file__).resolve().parents if (p / ".env").exists()), None)
    if raiz:
        for linea in (raiz / ".env").read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, _, v = linea.partition("=")
                valores[k.strip()] = v.strip().strip('"').strip("'")
    valores.update(os.environ)
    return valores


def destino() -> dict:
    e = _env()
    return {
        "host": e.get("DB_HOST", "localhost"),
        "port": str(e.get("DB_PORT", PUERTO_PRODUCCION)),
        "dbname": e.get("DB_NAME", "catalaxia"),
        "user_ro": e.get("MARKET_DB_USER_RO", "catalaxia_market_ro"),
        "user_rw": e.get("MARKET_DB_USER", e.get("DB_USER", "catalaxia")),
        "password": e.get("DB_PASSWORD", e.get("POSTGRES_PASSWORD", "catalaxia")),
        "allow_prod_write": e.get("MARKET_ALLOW_PROD_WRITE", "0") == "1",
    }


def es_produccion(port: str | None = None) -> bool:
    return str(port or destino()["port"]) == PUERTO_PRODUCCION


def describe() -> str:
    d = destino()
    return (f"{d['host']}:{d['port']}/{d['dbname']} "
            f"prod={es_produccion(d['port'])} "
            f"prod_write_habilitado={d['allow_prod_write']}")


def connect(dbname: str | None = None, *, write: bool = False):
    """Conexion a PostgreSQL. SOLO LECTURA salvo `write=True` explicito.

    Levanta `MarketProdWriteBlocked` si se pide escritura contra el puerto 5432
    sin `MARKET_ALLOW_PROD_WRITE=1`.
    """
    d = destino()
    prod = es_produccion(d["port"])

    if write and prod and not d["allow_prod_write"]:
        raise MarketProdWriteBlocked(
            f"F-001: se intento ESCRIBIR en {d['host']}:{d['port']}/{dbname or d['dbname']}, "
            f"que es el puerto de PRODUCCION.\n"
            f"  Para trabajar en dev:      DB_PORT=5433\n"
            f"  Para escribir en prod a proposito y bajo responsabilidad explicita:\n"
            f"                             MARKET_ALLOW_PROD_WRITE=1\n"
            f"  (esta guarda existe porque m6_scale.py escala a 584 instrumentos)"
        )

    conn = psycopg2.connect(
        host=d["host"], port=int(d["port"]), dbname=dbname or d["dbname"],
        user=d["user_rw"] if write else d["user_ro"], password=d["password"],
        application_name=f"market-{'rw' if write else 'ro'}",
    )
    if not write:
        # segunda barrera del lado cliente: la sesion no admite escritura
        conn.set_session(readonly=True)
    return conn


def exigir_dev(operacion: str) -> None:
    """Aborta si el destino es produccion. Para jobs masivos como m6_scale."""
    if es_produccion() and not destino()["allow_prod_write"]:
        raise MarketProdWriteBlocked(
            f"F-001: '{operacion}' no corre contra produccion sin "
            f"MARKET_ALLOW_PROD_WRITE=1. Destino actual: {describe()}"
        )


if __name__ == "__main__":
    print(f"Market · destino: {describe()}")
    try:
        with connect() as c:
            with c.cursor() as cur:
                cur.execute("SELECT current_user, "
                            "(SELECT count(*) FROM market_instruments)")
                usuario, n = cur.fetchone()
        print(f"  lectura OK como {usuario} · {n} instrumentos")
    except Exception as e:
        print(f"  lectura FALLO: {type(e).__name__}: {e}")
    try:
        connect(write=True)
        print("  escritura: PERMITIDA (MARKET_ALLOW_PROD_WRITE=1 o destino dev)")
    except MarketProdWriteBlocked:
        print("  escritura: BLOQUEADA por la guarda F-001")
