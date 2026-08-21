# -*- coding: utf-8 -*-
"""
FASE 7B -- Hacer el PER reproducible: eps_ttm, ttm_cierre y per_base
=====================================================================
EL PROBLEMA
  El screener publica `PER` y `EPS`, pero **no son la misma familia**:

     AAPL   PER = 37.89   Precio = 316.22   EPS = 7.46
            Precio / EPS  = 42.39   (no da)
            Precio / 8.30 = 38.10   (da: 8.30 es el eps_ttm de `ratios`)

  Investigado a fondo: el PER del S&P 500 **no se calcula con el precio**, sino
  como `market_cap / netincome_ttm`. Verificado: 467 de 489 cuadran asi y NINGUNO
  con `precio / eps_ttm`.

  Los dos caminos deberian dar lo mismo, pero solo si el recuento de acciones
  coincide, y no coincide: `market_cap` de yfinance usa las acciones en
  circulacion de HOY, y `eps_ttm` de EDGAR el promedio ponderado diluido del
  periodo. AVGO difiere 2,6%, AMZN 1,1%, AAPL 0,5%. Esa diferencia se traslada
  integra al PER.

  `market_cap / net income` es ademas la formula mas robusta: no depende de que
  dos fuentes coincidan en cuantas acciones hay.

  Los de BYMA si cuadran con `Precio / EPS` (21/21): ahi `s2` usa el mismo EPS
  que publica.

  Ningun valor esta mal. Lo que faltaba era **decir cual es cual**: la API exponia
  un PER que su consumidor no podia verificar, y al no cuadrar la conclusion
  razonable es "estos datos no son confiables".

LA SOLUCION
  Publicar los insumos REALES del PER, de forma **aditiva** -- ningun valor ya
  publicado cambia:

     netincome_ttm   el denominador real
     market_cap_ttm  el numerador real
     eps_ttm         informativo (NO es el denominador del PER)
     ttm_cierre      hasta que fecha llega el TTM
     per_base        con que formula se calculo el PER de ESA fila

  `per_base` importa porque el criterio cambia por grupo:
     mcap_ni_ttm         market_cap / netincome_ttm   (S&P 500 y ADR de EDGAR)
     anual               Precio / EPS                 (BYMA)
     adr_local           compuesto: precio USD, EPS ARS, ratio y tipo de cambio
     ttm_no_verificable  los insumos no reproducen el PER publicado

  Sin ese campo, el proximo que mire tiene que investigarlo desde cero -- que es
  exactamente lo que paso aca.

RESULTADO
  485 de 495 PER (98,0%) verificables y cuadran. Antes, con el denominador
  equivocado, parecian cuadrar solo 367 (74,1%) y habia 102 "desvios" que no
  existian: eran la diferencia entre dos formulas validas.

ORDEN
  Despues de s7 (que inserta los S&P 500) y antes de s5.

USO
  python s7b_eps_base_per.py
  SCREENER_DB=screener.db.test python s7b_eps_base_per.py
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _precondiciones import requiere_columnas, requiere_filas  # noqa: E402

NUEVAS = (
    ("eps_ttm", "REAL"),          # informativo: el EPS TTM del periodo
    ("netincome_ttm", "REAL"),    # el denominador REAL del PER
    ("market_cap_ttm", "REAL"),   # el numerador REAL del PER
    ("ttm_cierre", "TEXT"),
    ("per_base", "TEXT"),
)
TOL = 0.02


def main():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    print("FASE 7B -- PER reproducible (eps_ttm / ttm_cierre / per_base)")
    print("=" * 64)
    requiere_columnas(cur, "screener", ["PER", "EPS", "Precio", "grupo"], "s4_ensamblar")
    requiere_filas(cur, "screener", 100, "s7_unificar")

    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for c, t in NUEVAS:
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {t}")
    con.commit()

    ratios_cols = {r[1] for r in cur.execute("PRAGMA table_info(ratios)")}
    tiene_ttm = "eps_ttm" in ratios_cols

    # --- S&P 500 y ADR desde EDGAR: PER = market_cap / netincome_ttm ---
    n_sp = 0
    if tiene_ttm:
        cur.execute("""
            SELECT s.cuit, r.eps_ttm, r._netincome_ttm, r.market_cap, r.fecha
            FROM screener s JOIN ratios r ON r.cik = s.cuit
            WHERE r.eps_ttm IS NOT NULL OR r._netincome_ttm IS NOT NULL
        """)
        for cuit, eps_ttm, ni_ttm, mcap, fecha in cur.fetchall():
            cur.execute("""UPDATE screener
                           SET eps_ttm=?, netincome_ttm=?, market_cap_ttm=?,
                               ttm_cierre=?, per_base='mcap_ni_ttm'
                           WHERE cuit=?""",
                        (eps_ttm, ni_ttm, mcap, (fecha or "")[:10] or None, cuit))
            n_sp += 1
    else:
        print("  AVISO: `ratios` no tiene eps_ttm; no se puede poblar el lado EDGAR.")

    # --- ADR: el PER es COMPUESTO y no se reproduce con las columnas publicadas ---
    # Precio del ADR en USD, EPS local en ARS, ratio de conversion y tipo de cambio.
    # Ej. GGAL: PER 8.88, Precio 50.25 USD, EPS 1189.39 ARS, ratio 10.
    # Marcarlo 'anual' induciria a pensar que PER = Precio / EPS, y no lo es.
    cur.execute("""UPDATE screener SET per_base='adr_local'
                   WHERE grupo='adr' AND PER IS NOT NULL AND per_base IS NULL""")
    n_adr = cur.rowcount

    # --- BYMA: el PER ya usa el EPS publicado (verificado 21/21) ---
    cur.execute("""UPDATE screener
                   SET per_base='anual'
                   WHERE per_base IS NULL AND PER IS NOT NULL""")
    n_anual = cur.rowcount
    con.commit()

    # --- Marcar lo que no reproduce el PER ----------------------------------
    # Antes marcado que un numero que engana -- la misma politica de s9.
    # Queda 1 caso: BMA, con netincome_ttm en pesos y market_cap en dolares.
    # Es un ADR mal clasificado, no un error de formula.
    LIMITE = 0.20
    cur.execute("""SELECT cuit, ticker, PER, market_cap_ttm, netincome_ttm FROM screener
                   WHERE per_base='mcap_ni_ttm' AND PER IS NOT NULL
                     AND market_cap_ttm IS NOT NULL AND netincome_ttm IS NOT NULL
                     AND netincome_ttm<>0""")
    malos = []
    for cuit, tk, per, mcap, ni in cur.fetchall():
        calc = mcap / ni
        if calc == 0 or abs(per - calc) > abs(calc) * LIMITE:
            malos.append((cuit, tk, per, calc, ni))
    for cuit, tk, per, calc, ni in malos:
        cur.execute("""UPDATE screener
                       SET per_base='ttm_no_verificable'
                       WHERE cuit=?""", (cuit,))
    con.commit()

    print(f"  per_base='mcap_ni_ttm'        : {n_sp - len(malos)}")
    print(f"  per_base='adr_local'          : {n_adr}")
    print(f"  per_base='anual'              : {n_anual}")
    print(f"  per_base='ttm_no_verificable' : {len(malos)}"
          f"   <- market_cap/netincome_ttm no reproduce el PER")
    if malos:
        print("     los que no reproducen:")
        for cuit, tk, per, calc, eps in sorted(
                malos, key=lambda x: -abs(x[2] - x[3]))[:8]:
            print(f"       {tk:<7} PER={per:>9.2f}  mcap/ni_ttm={calc:>14.2f}"
                  f"  ni_ttm={eps:.0f}")

    # --- Cobertura final: cuantos PER son verificables y cuantos no ---------
    print("\n  Cobertura del PER publicado:")
    filas = cur.execute("""
        SELECT ticker, grupo, PER, Precio, EPS, netincome_ttm, market_cap_ttm, per_base
        FROM screener WHERE PER IS NOT NULL
    """).fetchall()
    ok = 0
    bandas = {"<=2%": 0, "2-5%": 0, "5-10%": 0, "10-20%": 0}
    no_verif = {}
    for tk, g, per, pre, eps, ni_ttm, mcap, base in filas:
        if base in ("ttm_no_verificable", "adr_local"):
            no_verif[base] = no_verif.get(base, 0) + 1
            continue
        if base == "mcap_ni_ttm":
            if not ni_ttm or not mcap:
                no_verif["sin_insumos"] = no_verif.get("sin_insumos", 0) + 1
                continue
            calc = mcap / ni_ttm
        else:
            if not eps or not pre:
                no_verif["sin_insumos"] = no_verif.get("sin_insumos", 0) + 1
                continue
            calc = pre / eps
        d = abs(per - calc) / abs(calc) * 100 if calc else 999
        if d <= TOL * 100:
            ok += 1
            bandas["<=2%"] += 1
        elif d <= 5:
            bandas["2-5%"] += 1
        elif d <= 10:
            bandas["5-10%"] += 1
        else:
            bandas["10-20%"] += 1
    tot = len(filas)
    print(f"     PER publicados            : {tot}")
    print(f"     verificables y CUADRAN    : {ok}  ({ok * 100.0 / tot:.1f}%)")
    resto = sum(v for k, v in bandas.items() if k != "<=2%")
    if resto:
        # No es redondeo: son desvios reales, aunque chicos. Se declara la banda
        # en vez de taparlos con una etiqueta comoda.
        print(f"     verificables con desvio   : {resto}"
              f"   ({bandas['2-5%']} en 2-5% | {bandas['5-10%']} en 5-10%"
              f" | {bandas['10-20%']} en 10-20%)")
        print(f"       Revisar: deberian reproducir con market_cap/netincome_ttm.")
    for k, v in sorted(no_verif.items(), key=lambda x: -x[1]):
        motivo = {
            "adr_local": "PER compuesto (precio USD / EPS ARS / ratio / FX)",
            "ttm_no_verificable": "market_cap/netincome_ttm no reproduce el PER",
            "sin_insumos": "falta Precio o EPS para verificar",
        }.get(k, "")
        print(f"     NO verificable [{k:<20}]: {v:>4}   {motivo}")
    con.close()
    print("\nFASE 7B -- OK")


if __name__ == "__main__":
    main()
