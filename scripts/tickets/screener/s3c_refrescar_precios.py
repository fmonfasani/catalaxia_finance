# -*- coding: utf-8 -*-
"""
FASE 3C -- Refrescar `precios` desde la serie diaria
=====================================================
`precios` guarda UNA foto por ticker y la consumen s4, s7 y s9. `s3_precios`
solo baja los que aun no estan (`NOT EXISTS`): no tiene modo refresco, y
vaciar la tabla a mano es destructivo (borra tambien los 499 del S&P 500, que
s3 no repone porque su universo es solo el subset CNV).

Este paso deja `precios` como lo que debe ser: **una vista derivada** del ultimo
cierre de `precios_diarios`. Los hechos viven en la serie; la foto se recalcula.
Ningun consumidor cambia.

QUE ACTUALIZA
  precio  <- close de la ultima rueda disponible en precios_diarios
  fecha   <- la fecha de esa rueda

QUE HACE CON market_cap  (y por que hay que saberlo)
  `precios_diarios` no trae capitalizacion: yfinance la da en `fast_info`, no en
  la serie. Pero el PER se calcula con market_cap, asi que actualizar el precio y
  dejar la capitalizacion vieja dejaria el screener incoherente: precio fresco y
  PER de hace seis semanas.

  Se reescala por la variacion del precio:

      market_cap_nuevo = market_cap_viejo * (precio_nuevo / precio_viejo)

  Eso ASUME que el numero de acciones no cambio entre las dos fechas. Sobre
  semanas es razonable; sobre meses, con recompras o emisiones de por medio, deja
  de serlo. Por eso se marca la fila con `mcap_metodo='escalado'`: quien lo
  consuma sabe que es una estimacion y no un dato bajado.

  Lo correcto a futuro es que `s3b` guarde tambien shares_outstanding por rueda.

QUE NO TOCA
  year_high / year_low: la serie arranca el 2026-07-09, seis semanas. No alcanza
  para un rango de 52 semanas, asi que se conservan los de yfinance.

USO
  python s3c_refrescar_precios.py
  SCREENER_DB=screener.db.test python s3c_refrescar_precios.py --dry-run
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _precondiciones import requiere_filas  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="mostrar sin escribir")
    ap.add_argument("--max-salto", type=float, default=60.0,
                    help="%% de variacion sobre el que se considera sospechoso")
    a = ap.parse_args()

    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    print("FASE 3C -- refrescar `precios` desde la serie diaria")
    print("=" * 62)
    requiere_filas(cur, "precios_diarios", 100, "s3b_precios_historicos")

    cols = {r[1] for r in cur.execute("PRAGMA table_info(precios)")}
    if "mcap_metodo" not in cols and not a.dry_run:
        cur.execute("ALTER TABLE precios ADD COLUMN mcap_metodo TEXT")
        con.commit()

    # ultimo cierre por ticker
    cur.execute("""
        SELECT d.ticker, d.fecha, d.close
        FROM precios_diarios d
        JOIN (SELECT ticker, MAX(fecha) f FROM precios_diarios
              WHERE close IS NOT NULL GROUP BY ticker) u
          ON u.ticker = d.ticker AND u.f = d.fecha
        WHERE d.close IS NOT NULL
    """)
    ultimos = {t: (f, c) for t, f, c in cur.fetchall()}
    print(f"tickers con cierre en la serie: {len(ultimos)}")

    cur.execute("SELECT cik, ticker, precio, market_cap, fecha FROM precios")
    actuales = cur.fetchall()
    print(f"filas en `precios`: {len(actuales)}\n")

    act = igual = sin_serie = sin_previo = 0
    sospechosos = []
    for cik, tk, pre_viejo, mcap_viejo, fecha_vieja in actuales:
        if tk not in ultimos:
            sin_serie += 1
            continue
        f_new, p_new = ultimos[tk]
        if (fecha_vieja or "")[:10] >= f_new:
            igual += 1
            continue
        if not pre_viejo or pre_viejo == 0:
            sin_previo += 1
            mcap_new, metodo = mcap_viejo, "sin_referencia"
        else:
            var = (p_new - pre_viejo) / pre_viejo * 100
            if abs(var) >= a.max_salto:
                sospechosos.append((tk, pre_viejo, p_new, var))
            mcap_new = (mcap_viejo * (p_new / pre_viejo)) if mcap_viejo else None
            metodo = "escalado" if mcap_viejo else None
        if not a.dry_run:
            cur.execute("""UPDATE precios
                           SET precio=?, fecha=?, market_cap=?, mcap_metodo=?
                           WHERE cik=?""",
                        (p_new, f_new, mcap_new, metodo, cik))
        act += 1
    if not a.dry_run:
        con.commit()

    print(f"  actualizados        : {act}")
    print(f"  ya estaban al dia   : {igual}")
    print(f"  sin serie diaria    : {sin_serie}")
    if sin_previo:
        print(f"  sin precio previo   : {sin_previo}  (market_cap sin reescalar)")
    if sospechosos:
        print(f"\n  variaciones >= {a.max_salto:.0f}% (revisar, no se bloquean):")
        for tk, v, n, var in sorted(sospechosos, key=lambda x: -abs(x[3]))[:10]:
            print(f"     {tk:<9} {v:>12.2f} -> {n:>12.2f}   {var:+.1f}%")

    cur.execute("SELECT substr(fecha,1,10), COUNT(*) FROM precios GROUP BY 1 ORDER BY 1 DESC")
    print("\n  frescura de `precios` tras el refresco:")
    for f, n in cur.fetchall()[:5]:
        print(f"     {f}  {n} tickers")
    con.close()
    print("\nFASE 3C -- OK" + ("  (dry-run: no se escribio nada)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
