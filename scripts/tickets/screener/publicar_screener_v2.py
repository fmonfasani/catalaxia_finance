# -*- coding: utf-8 -*-
"""
PUBLICAR screener_v2 -- tabla nueva EN PARALELO, sin tocar la que sirve la API
==============================================================================
POR QUE ESTO Y NO LA MIGRACION

  migrate_sqlite_to_pg.py REEMPLAZA `screener`. Medido contra produccion el
  2026-08-21, ese reemplazo vaciaba 12 columnas que la API sirve hoy:

      ccl              572 filas con dato      precio_usd      569
      precio_ars       568                     precio_fuente   566
      cedear_ratio     147                     cedear_x        147
      cusip             13                     dr_level         13
      last_div_date      9                     precio_dif_iamc  53
      div_adr_12m        3                     div_yield_adr     3

  El origen (data/screener.db) ya no las trae, asi que el INSERT las dejaba en
  NULL y el swap publicaba esa tabla. La guarda de filas NO lo detecta: entran
  572 y salen 572; el dano es por columna, no por fila.

  Aqui no se reemplaza nada. La tabla vieja sigue sirviendo intacta y la nueva
  se publica al lado, para poder compararlas con datos reales antes de decidir.

LAS 12 COLUMNAS SON DOS FAMILIAS DISTINTAS

  1. Las del dolar viejo (precio_ars, precio_usd, precio_fuente,
     precio_dif_iamc, ccl). SI tienen reemplazo: son la version IAMC de lo que
     ahora se calcula con MEP (valor_mep_dolarito, precio_usd_calc_mep_dolarito,
     fecha_mep_dolarito...). Que no esten en la tabla nueva es el cambio, no una
     perdida. NO se rescatan.

  2. Las de CEDEAR y ADR (cusip, dr_level, cedear_ratio, cedear_x, div_adr_12m,
     div_yield_adr, last_div_date). NO las reemplazo nada: el pipeline dejo de
     traerlas y punto. Si la tabla nueva no las lleva, ese dato se perdio.
     SI se rescatan, copiandolas de `screener` por ticker.

  Con eso `screener_v2` es estrictamente mejor que `screener`, y el dia que se
  cambie no se pierde nada.

USO
  python publicar_screener_v2.py --dry-run     # no escribe: dice que haria
  python publicar_screener_v2.py               # crea/reemplaza screener_v2

  Nunca toca la tabla `screener`. Si algo sale mal, la marcha atras es no hacer
  nada.
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2-binary no instalado. Correr: pip install psycopg2-binary")

DESTINO = "screener_v2"
ORIGEN_PG = "screener"          # de aqui se rescatan las columnas de CEDEAR/ADR

# Mismo mapeo de nombres que usa la migracion: SQLite escribe CamelCase y
# PostgreSQL pasa a minusculas los identificadores sin comillas.
MAPEO = {
    "MargenNeto": "margen_neto",
    "DeudaEBITDA": "deuda_ebitda",
    "CAGR_EPS_5y": "cagr_eps_5y",
    "CAGR_flag": "cagr_flag",
    "PriceBook": "price_book",
    "PriceSales": "price_sales",
    "MarketCapUSD": "market_cap_usd",
    "Max52w": "max_52w",
    "Min52w": "min_52w",
}

# Familia 2: sin reemplazo, se rescatan de la tabla actual. (columna, tipo PG)
RESCATAR = [
    ("cusip",         "text"),
    ("dr_level",      "text"),
    ("cedear_ratio",  "text"),
    ("cedear_x",      "double precision"),
    ("div_adr_12m",   "double precision"),
    ("div_yield_adr", "double precision"),
    ("last_div_date", "text"),
]

# Familia 1: tienen reemplazo MEP. Se declaran para poder decir en el informe
# que la ausencia es deliberada, no un olvido.
REEMPLAZADAS = {
    "precio_ars": "precio en ARS (ahora: el precio nativo + valor_mep_dolarito)",
    "precio_usd": "precio en USD por IAMC (ahora: precio_usd_calc_mep_dolarito)",
    "precio_fuente": "de donde salia el precio (ahora: implicito en las _mep_)",
    "precio_dif_iamc": "desvio contra IAMC (ya no se compara contra IAMC)",
    "ccl": "dolar CCL (ahora: valor_mep_dolarito, que es MEP)",
}

TIPOS_SQLITE = {"INTEGER": "bigint", "REAL": "double precision",
                "TEXT": "text", "BLOB": "bytea", "NUMERIC": "double precision"}


def conn_pg():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "catalaxia"),
        user=os.environ.get("DB_USER", "catalaxia"),
        password=os.environ.get("DB_PASSWORD") or _pass_de_env(),
    )


def _pass_de_env():
    """Lee POSTGRES_PASSWORD del .env de la raiz. No se pide ni se imprime."""
    f = ROOT / ".env"
    if f.exists():
        for l in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            l = l.strip()
            for k in ("DB_PASSWORD=", "POSTGRES_PASSWORD="):
                if l.startswith(k):
                    return l.split("=", 1)[1].strip().strip('"').strip("'")
    return "catalaxia"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no escribe nada")
    a = ap.parse_args()

    if not DB.exists():
        sys.exit(f"FATAL: no existe {DB}")

    sl = sqlite3.connect(str(DB))
    sl.row_factory = sqlite3.Row
    info = sl.execute("PRAGMA table_info(screener)").fetchall()
    if not info:
        sys.exit("FATAL: la tabla `screener` no existe en el SQLite de origen")

    origen = [c[1] for c in info]
    tipos = {c[1]: TIPOS_SQLITE.get((c[2] or "TEXT").upper().split("(")[0], "text")
             for c in info}
    destino = [MAPEO.get(c, c.lower()) for c in origen]

    filas = sl.execute("SELECT * FROM screener").fetchall()
    print("PUBLICAR screener_v2 -- tabla en paralelo")
    print("=" * 64)
    print(f"  origen : {DB.name}  ({len(filas)} filas, {len(origen)} columnas)")

    pg = conn_pg()
    pg.autocommit = False
    cur = pg.cursor()

    # --- que hay hoy en produccion, para el informe y para el rescate --------
    cur.execute("SELECT count(*) FROM %s" % ORIGEN_PG)
    n_prod = cur.fetchone()[0]
    cur.execute("""SELECT lower(column_name) FROM information_schema.columns
                   WHERE table_name=%s""", (ORIGEN_PG,))
    cols_prod = {r[0] for r in cur.fetchall()}
    print(f"  actual : {ORIGEN_PG} ({n_prod} filas, {len(cols_prod)} columnas)"
          f"   <- NO se toca")

    nuevas = [c for c in destino if c not in cols_prod]
    perdidas = [c for c in cols_prod if c not in destino]
    rescatables = [c for c, _ in RESCATAR if c in cols_prod]
    print(f"\n  columnas nuevas que aporta el origen : {len(nuevas)}")
    print(f"  columnas que el origen ya no trae     : {len(perdidas)}")
    print(f"     de esas, se RESCATAN (sin reemplazo): {len(rescatables)}")
    print(f"     de esas, reemplazadas por MEP       : "
          f"{len([c for c in perdidas if c in REEMPLAZADAS])}")
    huerfanas = [c for c in perdidas
                 if c not in REEMPLAZADAS and c not in dict(RESCATAR)]
    if huerfanas:
        # Ni rescatada ni declarada como reemplazada: nadie decidio que hacer
        # con ella. Se avisa en vez de dejarla caer en silencio.
        print(f"     SIN CLASIFICAR (revisar)            : {', '.join(huerfanas)}")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        pg.rollback(); pg.close(); sl.close()
        return

    # --- crear la tabla nueva ------------------------------------------------
    cols_ddl = [f'"{d}" {tipos[o]}' for o, d in zip(origen, destino)]
    cols_ddl += [f'"{c}" {t}' for c, t in RESCATAR if c in cols_prod]
    cur.execute(f'DROP TABLE IF EXISTS "{DESTINO}"')
    cur.execute(f'CREATE TABLE "{DESTINO}" ({", ".join(cols_ddl)})')

    lista = ", ".join(f'"{c}"' for c in destino)
    psycopg2.extras.execute_values(
        cur, f'INSERT INTO "{DESTINO}" ({lista}) VALUES %s',
        [tuple(f[c] for c in origen) for f in filas], page_size=2000)

    # --- rescatar las de CEDEAR/ADR desde la tabla que sirve hoy -------------
    # Por ticker: 570 de 572 emparejan (verificado). Los que no, quedan en NULL,
    # que es exactamente lo que tendrian si no se hiciera este paso.
    sets = ", ".join(f'"{c}" = s."{c}"' for c in rescatables)
    cur.execute(f'''UPDATE "{DESTINO}" v SET {sets}
                    FROM "{ORIGEN_PG}" s WHERE s.ticker = v.ticker''')
    n_resc = cur.rowcount

    if "ticker" in destino:
        cur.execute(f'CREATE INDEX ON "{DESTINO}" (ticker)')
    if "cuit" in destino:
        cur.execute(f'CREATE INDEX ON "{DESTINO}" (cuit)')
    pg.commit()

    # --- verificacion --------------------------------------------------------
    cur.execute(f'SELECT count(*) FROM "{DESTINO}"')
    n_v2 = cur.fetchone()[0]
    print(f"\n  {DESTINO}: {n_v2} filas, {len(cols_ddl)} columnas")
    print(f"  filas con CEDEAR/ADR rescatado: {n_resc}")
    print("\n  cobertura de lo rescatado (v2 vs la tabla actual):")
    for c in rescatables:
        cur.execute(f'SELECT count("{c}") FROM "{DESTINO}"')
        a_ = cur.fetchone()[0]
        cur.execute(f'SELECT count("{c}") FROM "{ORIGEN_PG}"')
        b_ = cur.fetchone()[0]
        marca = "OK" if a_ >= b_ else "FALTAN"
        print(f"     {c:<16} v2={a_:>4}   actual={b_:>4}   {marca}")

    cur.execute(f'SELECT count(*) FROM "{ORIGEN_PG}"')
    print(f"\n  control: `{ORIGEN_PG}` sigue con {cur.fetchone()[0]} filas (intacta)")
    pg.close(); sl.close()
    print("\nOK -- la API no cambia hasta que alguien la apunte a screener_v2.")


if __name__ == "__main__":
    main()
