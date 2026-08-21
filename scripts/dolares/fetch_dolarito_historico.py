#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOLARITO HISTORICO -- serie completa de dolares desde la API interna de dolarito.ar
===================================================================================
Endpoint descubierto:  GET https://api.dolarito.ar/api/frontend/history/series
Auth:                  header `auth-client` (token estatico del front)

Devuelve 10 series (oficial, mayorista, informal, bancos, ccl, mep, tarjeta,
ahorro, qatar, cripto), cada una con {compra: [[ts_ms, valor], ...], venta: [...]}.

Cobertura MEP: 2018-10-29 -> hoy  (~1883 puntos diarios)

Guarda en la tabla `dolarito_cotizaciones`. El nombre de la tabla ES la fuente:
todo lo que esta ahi adentro viene de dolarito.ar y de ningun otro lado. Cada
fuente nueva va en su propia tabla (`iamc_precios`, `criptoya_cotizaciones`, ...)
y se cruzan con UNION, nunca mezclando fuentes en la misma tabla.

Uso:  python scripts/dolares/fetch_dolarito_historico.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
API_URL = "https://api.dolarito.ar/api/frontend/history/series"

# El token NO va en el codigo: este repositorio es publico y cualquier valor
# escrito aca queda publicado, tambien en el historial de git. Se lee del
# entorno o de `.env` (ignorado por git). Ver docs/07-homologacion-cnv.md.
AUTH_CLIENT = _os.environ.get("DOLARITO_AUTH_CLIENT", "")
if not AUTH_CLIENT:
    _envf = ROOT / ".env"
    if _envf.exists():
        for _l in _envf.read_text(encoding="utf-8", errors="ignore").splitlines():
            _l = _l.strip()
            if _l.startswith("DOLARITO_AUTH_CLIENT="):
                AUTH_CLIENT = _l.split("=", 1)[1].strip().strip('"').strip("'")
                break

HEADERS = {
    "auth-client": AUTH_CLIENT,
    "origin": "https://www.dolarito.ar",
    "referer": "https://www.dolarito.ar/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "accept": "application/json",
}

# tipo en la API -> sigla nuestra (fuente_tipo)
SERIES = {
    "mep":       "MEP",
    "ccl":       "CCL",
    "oficial":   "OFICIAL",
    "mayorista": "MAYORISTA",   # ~A3500
    "informal":  "BLUE",
    "cripto":    "CRIPTO",
    "tarjeta":   "TARJETA",
    "bancos":    "BANCOS",
    "ahorro":    "AHORRO",
    "qatar":     "QATAR",
}

TABLA = "dolarito_cotizaciones"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLA} (
    fecha         TEXT NOT NULL,   -- YYYY-MM-DD
    tipo          TEXT NOT NULL,   -- MEP, CCL, OFICIAL, MAYORISTA, BLUE, ...
    compra        REAL,
    venta         REAL,
    ts_ms         INTEGER,         -- timestamp original de la API
    ts_ingesta    TEXT NOT NULL,
    PRIMARY KEY (fecha, tipo)
)
"""


def fetch_series() -> dict:
    if not AUTH_CLIENT:
        raise SystemExit(
            "FALTA DOLARITO_AUTH_CLIENT.\n"
            "  El token del header `auth-client` ya no vive en el codigo (repo publico).\n"
            "  Ponelo en el archivo .env de la raiz del repo, en una linea:\n"
            "      DOLARITO_AUTH_CLIENT=<el token>\n"
            "  o exportalo como variable de entorno antes de correr el script.\n"
            "  Se obtiene mirando el header que manda www.dolarito.ar en el navegador."
        )
    r = requests.get(API_URL, headers=HEADERS, timeout=60, verify=False)
    r.raise_for_status()
    return r.json()


def ts_to_fecha(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def build():
    print("DOLARITO HISTORICO")
    print("=" * 70)
    print(f"GET {API_URL}")

    data = fetch_series()
    print(f"  series recibidas: {list(data.keys())}")

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    cur.execute(DDL)

    ahora = datetime.now().isoformat(timespec="seconds")
    total = 0

    for api_key, sigla in SERIES.items():
        serie = data.get(api_key)
        if not serie:
            print(f"  {sigla:10} -- ausente en la respuesta")
            continue

        compras = {ts: v for ts, v in serie.get("compra", []) if v is not None}
        ventas = {ts: v for ts, v in serie.get("venta", []) if v is not None}
        todos_ts = sorted(set(compras) | set(ventas))

        filas = [
            (ts_to_fecha(ts), sigla, compras.get(ts), ventas.get(ts), ts, ahora)
            for ts in todos_ts
        ]
        cur.executemany(
            f"INSERT OR REPLACE INTO {TABLA} "
            "(fecha, tipo, compra, venta, ts_ms, ts_ingesta) VALUES (?,?,?,?,?,?)",
            filas,
        )
        total += len(filas)

        if filas:
            print(f"  {sigla:10} {len(filas):>5} puntos  {filas[0][0]} -> {filas[-1][0]}  "
                  f"(ultimo venta={filas[-1][3]})")

    con.commit()

    # resumen MEP
    print("\n" + "=" * 70)
    row = cur.execute(
        f"SELECT MIN(fecha), MAX(fecha), COUNT(*) FROM {TABLA} WHERE tipo='MEP'"
    ).fetchone()
    print(f"MEP en BD: {row[2]} filas  |  {row[0]} -> {row[1]}")

    print("\nUltimos 5 MEP:")
    for f, c, v in cur.execute(
        f"SELECT fecha, compra, venta FROM {TABLA} "
        "WHERE tipo='MEP' ORDER BY fecha DESC LIMIT 5"
    ):
        print(f"  {f}  compra={c}  venta={v}")

    con.close()
    print(f"\nTotal insertado: {total} filas -- OK")


if __name__ == "__main__":
    try:
        build()
    except requests.HTTPError as e:
        print(f"ERROR HTTP: {e}", file=sys.stderr)
        sys.exit(1)
