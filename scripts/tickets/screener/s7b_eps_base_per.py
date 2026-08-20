# -*- coding: utf-8 -*-
"""
FASE 7B -- Hacer el PER reproducible: eps_ttm, ttm_cierre y per_base
=====================================================================
EL PROBLEMA
  El screener publica `PER` y `EPS`, pero **no son la misma familia**:

     AAPL   PER = 37.89   Precio = 316.22   EPS = 7.46
            Precio / EPS  = 42.39   (no da)
            Precio / 8.30 = 38.10   (da: 8.30 es el eps_ttm de `ratios`)

  El PER del S&P 500 sale de `ratios.per`, que se calcula con **eps_ttm**,
  mientras la columna `EPS` publica **eps_anual**. Medido: de 452 papeles del
  S&P 500 con los tres campos, solo 45 reproducen `PER = Precio / EPS`.
  Los de BYMA sí cuadran (21/21): ahí `s2` usa el mismo EPS que publica.

  Ninguno de los dos valores está mal. Lo que falta es **decir cuál es cuál**:
  hoy la API expone un PER que su consumidor no puede verificar, y al no cuadrar
  la conclusión razonable es "estos datos no son confiables".

LA SOLUCION
  La que ya usa `screener_gold`: dos familias, cada una con su fecha de corte
  declarada (`periodo_cierre` / `ttm_cierre`, `per` / `per_ttm`). Aca se hace lo
  mismo de forma **aditiva**, sin cambiar ningun valor ya publicado:

     eps_ttm      el EPS que realmente alimenta el PER (NULL si no aplica)
     ttm_cierre   hasta que fecha llega ese TTM
     per_base     'ttm' | 'anual'  -- que EPS uso el PER de ESA fila

  `per_base` importa porque el criterio cambia por grupo: BYMA usa el anual y el
  S&P 500 el TTM. Sin ese campo, el proximo que mire tiene que investigarlo.

  Nada se rompe: quien lee `PER` y `EPS` sigue viendo lo mismo.

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
    ("eps_ttm", "REAL"),
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

    # --- S&P 500 y ADR desde EDGAR: el PER usa eps_ttm ---
    n_sp = 0
    if tiene_ttm:
        cur.execute("""
            SELECT s.cuit, r.eps_ttm, r.fecha
            FROM screener s JOIN ratios r ON r.cik = s.cuit
            WHERE r.eps_ttm IS NOT NULL
        """)
        for cuit, eps_ttm, fecha in cur.fetchall():
            cur.execute("""UPDATE screener
                           SET eps_ttm=?, ttm_cierre=?, per_base='ttm'
                           WHERE cuit=?""",
                        (eps_ttm, (fecha or "")[:10] or None, cuit))
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

    # --- Marcar el eps_ttm que no reproduce el PER --------------------------
    # `ratios.eps_ttm` tiene basura en unas decenas de casos: MCD y ERIE con
    # eps_ttm ~0 (PER calculado en millones), WAT con 68.953 contra un PER de 82.
    # Antes NULL que un numero que engana -- la misma politica de s9.
    LIMITE = 0.20
    cur.execute("""SELECT cuit, ticker, PER, Precio, eps_ttm FROM screener
                   WHERE per_base='ttm' AND PER IS NOT NULL
                     AND Precio IS NOT NULL AND eps_ttm IS NOT NULL AND eps_ttm<>0""")
    malos = []
    for cuit, tk, per, pre, eps_ttm in cur.fetchall():
        calc = pre / eps_ttm
        if calc == 0 or abs(per - calc) > abs(calc) * LIMITE:
            malos.append((cuit, tk, per, calc, eps_ttm))
    for cuit, tk, per, calc, eps_ttm in malos:
        cur.execute("""UPDATE screener
                       SET eps_ttm=NULL, per_base='ttm_no_verificable'
                       WHERE cuit=?""", (cuit,))
    con.commit()

    print(f"  per_base='ttm'                : {n_sp - len(malos)}")
    print(f"  per_base='adr_local'          : {n_adr}")
    print(f"  per_base='anual'              : {n_anual}")
    print(f"  per_base='ttm_no_verificable' : {len(malos)}"
          f"   <- eps_ttm de `ratios` no reproduce el PER")
    if malos:
        print("     los peores (eps_ttm sospechoso):")
        for cuit, tk, per, calc, eps in sorted(
                malos, key=lambda x: -abs(x[2] - x[3]))[:8]:
            print(f"       {tk:<7} PER={per:>9.2f}  Precio/eps_ttm={calc:>12.2f}"
                  f"  eps_ttm={eps:.4f}")

    # --- Cobertura final: cuantos PER son verificables y cuantos no ---------
    print("\n  Cobertura del PER publicado:")
    filas = cur.execute("""
        SELECT ticker, grupo, PER, Precio, EPS, eps_ttm, per_base
        FROM screener WHERE PER IS NOT NULL
    """).fetchall()
    ok = 0
    bandas = {"<=2%": 0, "2-5%": 0, "5-10%": 0, "10-20%": 0}
    no_verif = {}
    for tk, g, per, pre, eps, eps_ttm, base in filas:
        if base in ("ttm_no_verificable", "adr_local"):
            no_verif[base] = no_verif.get(base, 0) + 1
            continue
        base_eps = eps_ttm if base == "ttm" else eps
        if not base_eps or not pre:
            no_verif["sin_insumos"] = no_verif.get("sin_insumos", 0) + 1
            continue
        calc = pre / base_eps
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
        print(f"       El PER de `ratios` se calculo con una foto de eps_ttm que no")
        print(f"       coincide exactamente con la almacenada. Revisar en origen.")
    for k, v in sorted(no_verif.items(), key=lambda x: -x[1]):
        motivo = {
            "adr_local": "PER compuesto (precio USD / EPS ARS / ratio / FX)",
            "ttm_no_verificable": "eps_ttm de `ratios` no reproduce el PER",
            "sin_insumos": "falta Precio o EPS para verificar",
        }.get(k, "")
        print(f"     NO verificable [{k:<20}]: {v:>4}   {motivo}")
    con.close()
    print("\nFASE 7B -- OK")


if __name__ == "__main__":
    main()
