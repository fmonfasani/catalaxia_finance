# -*- coding: utf-8 -*-
"""
FASE 9b · El rango de 52 semanas, para los tres grupos
======================================================
s9 calcula el rango solo para BYMA, porque nació resolviendo dos problemas que
son de BYMA: la colisión de tickers contra símbolos de EEUU y la conversión a
dólares por MEP. Resultado medido el 2026-08-22 sobre las 572 filas:

    max_52w_ars_yfinance      46 de 572      sp500 0 · adr 0 · byma 46
    dif_max_52w_pct           46 de 572      sp500 0 · adr 0 · byma 46

Es el hueco más grande de `screener`, y el dato ya estaba: `precios.year_high`
y `year_low` los traen para las 672 filas. Solo faltaba copiarlos.

LA MONEDA NO SE CONVIERTE
  El máximo va en `max_52w_abs`, en la moneda que declara `currency` en esa
  misma fila. Para el S&P 500 eso es dólares nativos, no una traducción; para
  BYMA, pesos. Las columnas `_ars_` y `_usd_calc_mep_` siguen siendo de BYMA,
  que es lo que su nombre promete. Ver migrations/005.

UNA SOLA CONVENCION DE SIGNO
      dif_max_52w_pct = precio/máximo − 1     negativo = por debajo del máximo
      dif_min_52w_pct = precio/mínimo − 1     positivo = por encima del mínimo
  Es la de finviz e investing, y la que ya usaba s9.

  Las viejas `max_52w` y `min_52w` usan otra —y entre sí, dos distintas—, pero
  la API las sirve hoy: se dejan quietas. Ver el encabezado de la migración.

SE RESPETAN LOS GUARDS DE s9
  Una fila cuyo precio quedó en NULL por colisión de ticker o por iliquidez
  tampoco publica rango. Publicar el rango de un papel cuyo precio no
  confiamos es peor que dejarlo vacío: da la apariencia de dato.

  Y hay una razón concreta: hasta hoy, AGRO salía en producción a USD 10 —que
  es Adecoagro, no Agrometal—. Si el rango se copiara sin mirar el guard, se
  publicaría el rango de la empresa equivocada.

EL EMPATE DE TICKERS
  48 tickers tienen DOS filas en `precios`: la de yfinance directo y la resuelta
  por BYMA. Se desempata en tres pasos —moneda, identidad, y rango idéntico— y
  si queda ambigüedad real no se publica. El detalle está en `rango()`.

QUE SE MIDIO AL CORRERLO
      se llenan                   557 de 572
      sp500                       499 de 499
      byma_only                    52 de 56
      adr                           6 de 17     (11 sin fila en `precios`)

  Y el control de signo dejó 8 papeles apenas por encima de su máximo —ANET
  1,9%, el resto bajo 1%— y uno apenas por debajo del mínimo. Es el desfase
  entre la captura del precio y la del rango, no un error: el papel hizo un
  máximo nuevo. Por eso el umbral de alarma está en 3% y no en cero.

Orden en el pipeline:  s9 -> **s9b** -> s5
Uso:  python scripts/tickets/screener/s9b_rango_52w.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")

COLS = ("max_52w_abs", "min_52w_abs", "dif_max_52w_pct", "dif_min_52w_pct")


def asegurar_columnas(con):
    """En SQLite las columnas nuevas se agregan acá; en PostgreSQL las trae 005."""
    hay = {r[1] for r in con.execute("PRAGMA table_info(screener)")}
    for c in ("max_52w_abs", "min_52w_abs"):
        if c not in hay:
            con.execute(f"ALTER TABLE screener ADD COLUMN {c} REAL")
    con.commit()


def rango(con, ticker, moneda, cuit=None):
    """(precio, maximo, minimo) de `precios`. None si no se puede desempatar.

    48 tickers tienen DOS filas: la de yfinance directo y la resuelta por BYMA.
    Elegir "la primera" es exactamente como AGRO terminó publicando el precio de
    Adecoagro, así que se desempata en tres pasos, del más estricto al más laxo:

      1. la moneda tiene que coincidir con la de `screener`;
      2. si queda más de una, gana la que tenga el mismo identificador que la
         empresa (cik = cuit) -- es la fila de la entidad, no la del símbolo;
      3. si sigue habiendo empate pero TODAS coinciden en máximo y mínimo, el
         empate no afecta lo que se busca. Medido: las 48 traen el mismo rango
         y difieren solo en `precio`, por la hora de captura.

    Si después de eso queda ambigüedad real, se devuelve None. Un rango de la
    empresa equivocada es peor que un campo vacío.
    """
    filas = con.execute(
        "SELECT precio, year_high, year_low, currency, cik FROM precios "
        "WHERE ticker=?", (ticker,)).fetchall()
    if not filas:
        return None
    if moneda:
        filas = [f for f in filas if (f[3] or "") == moneda]
    if not filas:
        return None
    if len(filas) > 1 and cuit:
        propias = [f for f in filas if (f[4] or "") == cuit]
        if len(propias) == 1:
            filas = propias
    if len(filas) > 1:
        rangos = {(f[1], f[2]) for f in filas}
        if len(rangos) != 1:
            return None                   # discrepan de verdad: no se publica
    p, hi, lo = filas[0][0], filas[0][1], filas[0][2]
    if not (p and hi and lo):
        return None
    # Un rango donde el maximo es el minimo no es un rango. Pasa cuando el papel
    # casi no opera y yfinance devuelve el mismo valor en las dos puntas: A3 daba
    # max = min = 2.215 con el precio en 3.425, o sea 54,6% "por encima de su
    # maximo". Publicar eso es peor que dejarlo vacio.
    if hi <= lo:
        return None
    return (p, hi, lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA busy_timeout=60000")
    asegurar_columnas(con)

    print("FASE 9b -- rango de 52 semanas, los tres grupos")
    print("=" * 66)

    filas = con.execute(
        "SELECT cuit, ticker, grupo, Precio, Currency, guard_motivo FROM screener"
    ).fetchall()

    upd, sin_precios, sin_desempate, por_guard, sin_precio = [], 0, 0, 0, 0
    for cuit, ticker, grupo, precio, moneda, guard in filas:
        if precio is None:
            # El precio ya venia anulado (guard de moneda o de liquidez de s9).
            sin_precio += 1
            if guard:
                por_guard += 1
            continue
        r = rango(con, ticker, moneda, cuit)
        if r is None:
            n = con.execute("SELECT COUNT(*) FROM precios WHERE ticker=?",
                            (ticker,)).fetchone()[0]
            if n == 0:
                sin_precios += 1
            else:
                sin_desempate += 1
            continue
        _, hi, lo = r
        upd.append((hi, lo, precio / hi - 1, precio / lo - 1, cuit))

    print(f"  filas                       {len(filas):>5}")
    print(f"  se llenan                   {len(upd):>5}")
    print(f"  sin precio (guard de s9)    {sin_precio:>5}"
          f"   de los cuales {por_guard} con motivo declarado")
    print(f"  ticker sin fila en precios  {sin_precios:>5}")
    print(f"  empate de moneda sin lugar  {sin_desempate:>5}")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        return

    con.executemany(
        "UPDATE screener SET max_52w_abs=?, min_52w_abs=?, "
        "dif_max_52w_pct=?, dif_min_52w_pct=? WHERE cuit=?", upd)
    con.commit()

    print("\n  resultado por grupo:")
    for g, n, k in con.execute(
            "SELECT grupo, COUNT(*), COUNT(max_52w_abs) FROM screener "
            "GROUP BY grupo ORDER BY COUNT(*) DESC"):
        print(f"    {str(g):<12}{k:>4} de {n:<4}")

    # CONTROL DE SIGNO
    #   Un precio por encima del maximo de 52 semanas es imposible... salvo por
    #   un desfase de captura: el precio se toma en un momento y el rango en
    #   otro, y si el papel hizo un maximo nuevo queda apenas afuera. Medido en
    #   sp500: ANET 1,9%, EXPD 1,2%, y seis mas por debajo del 1%.
    #
    #   Por eso el control tiene DOS umbrales. Hasta 3% es el desfase y se
    #   informa; mas que eso es un dato malo y hay que mirarlo.
    for etiqueta, cond in (
            ("por encima del maximo", "dif_max_52w_pct > {u}"),
            ("por debajo del minimo", "dif_min_52w_pct < -{u}")):
        leve = con.execute("SELECT COUNT(*) FROM screener WHERE "
                           + cond.format(u="0.001")).fetchone()[0]
        grave = con.execute("SELECT COUNT(*) FROM screener WHERE "
                            + cond.format(u="0.03")).fetchone()[0]
        print(f"  {etiqueta:<24}{leve:>4} fuera   {grave:>3} por mas de 3%")
    if con.execute("SELECT COUNT(*) FROM screener WHERE abs(dif_max_52w_pct) > 0.03 "
                   "AND dif_max_52w_pct > 0").fetchone()[0]:
        print("  ATENCION: hay rangos con desvio grande. Revisar esas filas.")
    con.close()


if __name__ == "__main__":
    main()
