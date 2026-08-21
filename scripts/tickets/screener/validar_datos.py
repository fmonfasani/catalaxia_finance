# -*- coding: utf-8 -*-
"""
VALIDAR LOS DATOS -- que lo publicado se sostenga solo
=======================================================
Cinco pruebas independientes sobre lo que el screener publica. Ninguna necesita
una fuente externa: son verdades que los datos tienen que cumplir consigo
mismos.

POR QUE ESTA ES LA VALIDACION QUE FALTABA
  Las capas 0..6 validan los HECHOS -- que el numero este bien leido, en la
  unidad correcta, del periodo correcto. Esta valida lo PUBLICADO: que el PER
  que sale por la API se pueda reproducir con los numeros que la misma API
  entrega.

  Es la diferencia entre "el dato es correcto" y "el dato es verificable". Un
  consumidor no puede auditar lo primero, pero lo segundo lo comprueba en dos
  cuentas -- y si no le cierra, la conclusion razonable es que la fuente entera
  no es confiable. Ya paso: el PER no reproducia con Precio/EPS y no habia forma
  de saber por que.

LAS CINCO PRUEBAS

  1 ARITMETICA      Cada ratio se recalcula desde sus insumos publicados y se
                    compara con el valor publicado. Es la mas importante: mide
                    si un tercero puede verificar lo que le damos.
  2 COHERENCIA      Relaciones que no pueden fallar: si hay ganancia el ROE
                    tiene el mismo signo, un margen no supera el 100%, un PER
                    positivo exige ganancia positiva.
  3 RANGO           Los valores caen donde un ratio de ese tipo puede caer. Un
                    ROE de 400% o un PER de 5.000 no es un dato, es un sintoma.
  4 CRUZADA         El mismo hecho vive en varias tablas (screener, ratios_cnv,
                    per_ttm). Tienen que coincidir.
  5 COMPLETITUD     Que lo que falta este DECLARADO. Un vacio con motivo es un
                    dato; un vacio sin motivo es una pregunta abierta.

QUE HACE CON LO QUE ENCUENTRA
  Nada. Informa. Es de solo lectura a proposito: decidir que hacer con un ratio
  que no reproduce es una decision de producto, no un automatismo.

USO
  python validar_datos.py
  python validar_datos.py --grupo byma_only
  python validar_datos.py --ticker ALUA
  python validar_datos.py --detalle       # lista los casos, no solo el conteo
"""
from __future__ import annotations
import argparse
import collections
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _foco import Foco  # noqa: E402

TOL = 0.02          # 2%: por debajo de eso, reproduce

# (ratio, insumos, funcion, como se lee)
def _div(a, b):
    return (a / b) if (a is not None and b) else None

# EL PER NO TIENE UNA SOLA FORMULA, Y ESA ES LA TRAMPA
#   La primera version de esta prueba comparaba todo contra Precio/EPS y daba
#   13,9% de reproducibilidad. No es que los datos estuvieran mal: es que el
#   S&P 500 calcula el PER como market_cap/netincome_ttm, no con el precio.
#   Los dos caminos deberian dar lo mismo, pero solo si el recuento de acciones
#   coincide -- y no coincide: yfinance usa las acciones de HOY y EDGAR el
#   promedio ponderado del periodo.
#
#   Para eso existe `per_base`, que dice con que formula salio CADA fila. Sin
#   consultarlo, la prueba mide su propia suposicion y no los datos.
POR_BASE = {
    "mcap_ni_ttm": (("market_cap_ttm", "netincome_ttm"), lambda m, n: _div(m, n),
                    "Capitalizacion / NetIncome_TTM"),
    "anual":       (("Precio", "EPS"), lambda p, e: _div(p, e), "Precio / EPS"),
}

ARITMETICA = [
    ("PriceBook",  ("MarketCapUSD", "Equity"),   lambda m, q: _div(m, q),
     "Capitalizacion / Patrimonio"),
    ("PriceSales", ("MarketCapUSD", "Revenue"),  lambda m, r: _div(m, r),
     "Capitalizacion / Ventas"),
]

# (ratio, minimo, maximo, por que ese rango)
RANGOS = [
    ("PER",         0,   150,  "un PER sobre 150 no informa nada util"),
    ("ROE",        -3,     3,  "un ROE de +/-300% ya no es rentabilidad"),
    ("MargenNeto", -5,     1,  "el margen neto no puede superar el 100%"),
    ("PriceBook",   0,    50,  "sobre 50 veces libros es implausible"),
    ("PriceSales",  0,   100,  "idem ventas"),
    ("Payout",      0,     3,  "repartir mas de 3x la ganancia es excepcional"),
]


def pct(n, d):
    return f"{n*100.0/d:5.1f}%" if d else "    -"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grupo")
    ap.add_argument("--ticker")
    ap.add_argument("--detalle", action="store_true")
    a = ap.parse_args()
    foco = Foco()

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}

    print("VALIDACION DE LOS DATOS PUBLICADOS")
    print("=" * 78)
    foco.anuncia()
    where = "WHERE 1=1" + (f" AND grupo='{a.grupo}'" if a.grupo else "")
    universo = cur.execute(
        f"SELECT ticker, grupo FROM screener {where}").fetchall()
    universo = [(t, g) for t, g in universo if foco.alcanza(t)]
    print(f"  universo: {len(universo)} empresas"
          + (f"  (grupo {a.grupo})" if a.grupo else ""))
    tks = {t for t, _ in universo}

    fallas = collections.defaultdict(list)

    # ---------------------------------------------------- 1. ARITMETICA
    print("\n1 ARITMETICA -- el ratio publicado se reproduce de sus insumos?")
    print(f"   {'ratio':<12}{'formula':<32}{'con insumos':>12}{'reproduce':>11}{'%':>8}")

    # --- PER, segun la formula que declara CADA fila -------------------------
    if "per_base" in cols:
        for base, (insumos, fn, leyenda) in POR_BASE.items():
            if any(i not in cols for i in insumos):
                continue
            sel = ", ".join(f'"{x}"' for x in ("ticker", "PER") + insumos)
            n_ok = n_con = 0
            for fila in cur.execute(
                    f"SELECT {sel} FROM screener {where} AND per_base=?", (base,)):
                tk, pub = fila[0], fila[1]
                if tk not in tks or pub is None:
                    continue
                calc = fn(*fila[2:])
                if calc is None or calc == 0:
                    continue
                n_con += 1
                d = abs(pub - calc) / abs(calc)
                if d <= TOL:
                    n_ok += 1
                else:
                    fallas[f"aritmetica:PER({base})"].append(
                        (tk, f"publicado {pub:,.2f} vs {leyenda} = {calc:,.2f}"
                             f"  ({d * 100:,.0f}% de desvio)"))
            print(f"   {'PER':<12}{leyenda:<32}{n_con:>12}{n_ok:>11}{pct(n_ok, n_con):>8}")
        # Bases que NO se pueden reproducir con lo publicado. Se cuentan y se
        # declaran: un ratio no verificable no es un error, pero el consumidor
        # tiene derecho a saber cuales lo son.
        for base, motivo in (
                ("adr_local", "PER compuesto: precio USD / EPS ARS / ratio / FX"),
                ("ttm_no_verificable", "sus insumos no reproducen el PER")):
            n = cur.execute(f"SELECT COUNT(*) FROM screener {where} AND per_base=?",
                            (base,)).fetchone()[0]
            if n:
                print(f"   {'PER':<12}{'(no reproducible)':<32}{n:>12}{'-':>11}"
                      f"    {motivo}")
    else:
        print(f"   {'PER':<12}falta per_base: corre s7b_eps_base_per primero")

    for ratio, insumos, fn, leyenda in ARITMETICA:
        if ratio not in cols or any(i not in cols for i in insumos):
            print(f"   {ratio:<12}{leyenda:<32}{'sin columnas':>12}")
            continue
        sel = ", ".join(f'"{x}"' for x in ("ticker", ratio) + insumos)
        n_ok = n_con = 0
        for fila in cur.execute(f"SELECT {sel} FROM screener {where}"):
            tk, pub = fila[0], fila[1]
            if tk not in tks or pub is None:
                continue
            calc = fn(*fila[2:])
            if calc is None or calc == 0:
                continue
            n_con += 1
            d = abs(pub - calc) / abs(calc)
            if d <= TOL:
                n_ok += 1
            else:
                fallas[f"aritmetica:{ratio}"].append(
                    (tk, f"publicado {pub:,.2f} vs {leyenda} = {calc:,.2f}"
                         f"  ({d*100:,.0f}% de desvio)"))
        print(f"   {ratio:<12}{leyenda:<32}{n_con:>12}{n_ok:>11}{pct(n_ok, n_con):>8}")

    # ---------------------------------------------------- 2. COHERENCIA
    print("\n2 COHERENCIA -- relaciones que no pueden fallar")
    reglas = [
        ("PER positivo exige ganancia positiva",
         f'SELECT ticker FROM screener {where} AND PER > 0 AND netincome_ttm < 0'),
        ("ROE y ganancia con el mismo signo",
         f'SELECT ticker FROM screener {where} AND ROE IS NOT NULL '
         f'AND netincome_ttm IS NOT NULL AND ROE * netincome_ttm < 0'),
        ("margen neto sin ganancia declarada",
         f'SELECT ticker FROM screener {where} AND MargenNeto IS NOT NULL '
         f'AND netincome_ttm IS NULL'),
        ("precio sin capitalizacion",
         f'SELECT ticker FROM screener {where} AND Precio > 0 '
         f'AND (MarketCapUSD IS NULL OR MarketCapUSD = 0)'),
    ]
    for nombre, sql in reglas:
        try:
            r = [x[0] for x in cur.execute(sql) if x[0] in tks]
        except sqlite3.Error as e:
            print(f"   {nombre:<44} no evaluable ({e})")
            continue
        print(f"   {nombre:<44}{len(r):>5} incumplen")
        for tk in r[:40]:
            fallas[f"coherencia:{nombre}"].append((tk, ""))

    # ---------------------------------------------------- 3. RANGO
    print("\n3 RANGO -- los valores caen donde pueden caer")
    print(f"   {'ratio':<12}{'rango':<16}{'publicados':>11}{'fuera':>7}")
    for ratio, lo, hi, por_que in RANGOS:
        if ratio not in cols:
            continue
        n = fue = 0
        for tk, v in cur.execute(f'SELECT ticker, "{ratio}" FROM screener {where}'):
            if tk not in tks or v is None:
                continue
            n += 1
            if v < lo or v > hi:
                fue += 1
                fallas[f"rango:{ratio}"].append((tk, f"{v:,.2f}  ({por_que})"))
        print(f"   {ratio:<12}{f'{lo} .. {hi}':<16}{n:>11}{fue:>7}")

    # ---------------------------------------------------- 4. CRUZADA
    print("\n4 CRUZADA -- el mismo hecho en dos tablas")
    cruces = [
        ("PER de screener vs per_ttm", """
            SELECT s.ticker, s.PER, p.per_ttm FROM screener s
            JOIN per_ttm p ON p.ticker = s.ticker
            WHERE s.PER IS NOT NULL AND p.per_ttm IS NOT NULL"""),
        ("ROE de screener vs ratios_cnv", """
            SELECT s.ticker, s.ROE, r.ROE FROM screener s
            JOIN ratios_cnv r ON r.cuit = s.cuit
            WHERE s.ROE IS NOT NULL AND r.ROE IS NOT NULL"""),
    ]
    for nombre, sql in cruces:
        try:
            filas = [f for f in cur.execute(sql) if f[0] in tks]
        except sqlite3.Error as e:
            print(f"   {nombre:<40} no evaluable ({e})")
            continue
        ok = 0
        for tk, x, y in filas:
            if y and abs(x - y) / abs(y) <= 0.05:
                ok += 1
            else:
                fallas[f"cruzada:{nombre}"].append((tk, f"{x:,.2f} vs {y:,.2f}"))
        print(f"   {nombre:<40}{len(filas):>5} comparables{ok:>6} coinciden"
              f" {pct(ok, len(filas))}")

    # ---------------------------------------------------- 5. COMPLETITUD
    print("\n5 COMPLETITUD -- lo que falta, esta declarado?")
    campos = [("PER", "per_ttm_estado"), ("cagr_revenue_usd_5y", "cagr_motivo")]
    for campo, motivo in campos:
        if campo not in cols:
            continue
        sinm = 0
        if motivo in cols:
            sinm = cur.execute(
                f'SELECT COUNT(*) FROM screener {where} AND "{campo}" IS NULL '
                f'AND ("{motivo}" IS NULL OR "{motivo}" = "")').fetchone()[0]
        vac = cur.execute(
            f'SELECT COUNT(*) FROM screener {where} AND "{campo}" IS NULL').fetchone()[0]
        est = "todos declarados" if not sinm else f"{sinm} SIN motivo"
        print(f"   {campo:<26}{vac:>5} vacios   {est}")

    # ---------------------------------------------------- resumen
    tot = sum(len(v) for v in fallas.values())
    print("\n" + "=" * 78)
    print(f"  TOTAL DE OBSERVACIONES: {tot}")
    for k, v in sorted(fallas.items(), key=lambda x: -len(x[1])):
        print(f"     {k:<52}{len(v):>5}")
    if a.detalle:
        for k, v in sorted(fallas.items(), key=lambda x: -len(x[1])):
            print(f"\n  --- {k}")
            for tk, det in v[:14]:
                print(f"     {tk:<10}{det}")
    else:
        print("\n  (--detalle para ver los casos)")
    con.close()


if __name__ == "__main__":
    main()
