# -*- coding: utf-8 -*-
"""
FASE 7C -- Crecimiento a 5 años, en dolares
============================================
Calcula el CAGR (crecimiento anual compuesto) de los ultimos cinco ejercicios,
EN DOLARES al MEP de cada cierre.

POR QUE EN DOLARES Y NO EN PESOS -- ES LA RAZON DE SER DE ESTA FASE
  El screener ya publica CAGR_EPS_5y calculado en pesos, y ese numero no
  significa nada. Ejemplo medido:

      RICH  CAGR_EPS_5y = 0,4   ->  +40% anual
      inflacion del mismo tramo (2021-12 a 2026-03) = 80% anual
                                    (los precios se multiplicaron por 19)

  Ese "+40% de crecimiento" es en realidad una CAIDA de mas de la mitad en
  terminos reales. El numero no esta mal calculado: esta calculado sobre pesos
  de distinto poder adquisitivo.

  Y el propio sistema ya lo avisaba, sin que nadie lo escuchara:

      CAGR_flag = vintage_mixto(2021-12-31..2026-03-31)

  En dolares el problema desaparece: el dolar no se licua, asi que dos cifras de
  años distintos son comparables. Verificado en la capa 1: la mediana anual de
  facturacion en USD queda plana ocho años seguidos.

POR QUE ESTO NO SE PODIA HACER ANTES
  Depende de tres capas que estaban rotas y se arreglaron:

    capa 2 TIEMPO    hay que saber cuales son los cierres ANUALES. Con el
                     calendario en duda, el calculo tomaba trimestres sueltos
                     como si fueran ejercicios: dio 100% anual de crecimiento
                     para Aluar, que fue lo que destapo todo.
    capa 3 UNIDAD    un solo año con la escala mal convierte el CAGR en una
                     potencia de mil: no +30% sino +100.000%.
    capa 4 MONEDA    es la conversion misma.

  Correr esto antes de esas tres no da un resultado peor: da un resultado
  inventado con cara de dato.

QUE SE PUBLICA, Y QUE NO
  Se calcula solo si:
    - hay al menos 5 cierres anuales,
    - el primero y el ultimo son POSITIVOS (un CAGR entre -100 y +50 no existe
      matematicamente, y forzarlo produce numeros sin sentido),
    - ninguno de los dos extremos esta marcado por la capa 3 sin corregir.
  Si algo falta, queda VACIO con el motivo. Cada fila dice sobre que ventana se
  calculo y con cuantos ejercicios.

USO
  python s7c_cagr.py --dry-run
  python s7c_cagr.py
  python s7c_cagr.py --ticker ALUA
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _foco import Foco  # noqa: E402

MIN_EJERCICIOS = 5
CONCEPTOS = [("Revenue", "cagr_revenue_usd_5y"), ("NetIncome", "cagr_netincome_usd_5y")]
NUEVAS = [("cagr_revenue_usd_5y", "REAL"), ("cagr_netincome_usd_5y", "REAL"),
          ("cagr_desde", "TEXT"), ("cagr_hasta", "TEXT"),
          ("cagr_ejercicios", "INTEGER"), ("cagr_motivo", "TEXT")]


def serie_anual(cur, cuit, fy, concepto):
    """[(period_end, usd)] de los cierres ANUALES, del mas viejo al mas nuevo.

    Solo cierres cuyo mes coincide con el fin de ejercicio. Se prefiere el
    consolidado cuando existe, y se usa valor_corregido si la capa 3 dejo uno.
    """
    filas = cur.execute(
        """SELECT period_end, valor, valor_corregido, mep_valor, usd_clase, tipo_balance
           FROM cnv_estados_norm
           WHERE cuit=? AND concepto LIKE ? AND valor IS NOT NULL
             AND mep_valor IS NOT NULL
           ORDER BY period_end""", (cuit, f"%{concepto}%")).fetchall()
    por_pe = {}
    for pe, v, vc, mep, clase, tb in filas:
        if int(pe[5:7]) != fy:
            continue                       # no es cierre de ejercicio
        val = vc if vc is not None else v
        dudoso = clase in ("unidad", "no_unidad") and vc is None
        # el consolidado gana; a igualdad, la primera que llega
        if pe not in por_pe or tb == "CONSOLIDADO":
            por_pe[pe] = (val / mep, dudoso)
    return sorted((pe, u, d) for pe, (u, d) in por_pe.items())


def cagr(v0, v1, años):
    if v0 is None or v1 is None or v0 <= 0 or v1 <= 0 or años <= 0:
        return None
    return ((v1 / v0) ** (1.0 / años) - 1.0) * 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ticker")
    a = ap.parse_args()
    foco = Foco()

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    print("FASE 7C -- crecimiento a 5 años, en dolares")
    print("=" * 74)
    foco.anuncia()

    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    if not a.dry_run:
        for c_, t_ in NUEVAS:
            if c_ not in cols:
                cur.execute(f"ALTER TABLE screener ADD COLUMN {c_} {t_}")
        con.commit()

    fcal = {cu: fy for cu, fy in cur.execute(
        "SELECT cuit, fy_end_month FROM fiscal_calendar")}
    filas = cur.execute(
        "SELECT ticker, cuit FROM screener WHERE grupo='byma_only' ORDER BY ticker"
    ).fetchall()

    datos, motivos = [], collections.Counter()
    ok_list = []
    for tk, cuit in filas:
        if not foco.alcanza(tk):
            continue
        fy = fcal.get(cuit)
        if not fy:
            motivos["sin_calendario"] += 1
            datos.append((None, None, None, None, None, "sin_calendario", tk))
            continue
        res, desde, hasta, n = {}, None, None, 0
        motivo = None
        for concepto, col in CONCEPTOS:
            s = serie_anual(cur, cuit, fy, concepto)
            if len(s) < MIN_EJERCICIOS:
                motivo = motivo or f"solo {len(s)} ejercicios"
                continue
            s = s[-6:]                     # los ultimos 6 cierres -> hasta 5 años
            (pe0, v0, d0), (pe1, v1, d1) = s[0], s[-1]
            if d0 or d1:
                motivo = motivo or "extremo con la unidad en duda"
                continue
            # COHERENCIA DE LA SERIE, no solo de cada punto.
            # No alcanza con que los extremos pasen la banda: un año base mil
            # veces por debajo del resto ES plausible para una empresa chica, y
            # la banda lo deja pasar. El error solo se ve contra los OTROS años
            # de la misma serie.
            #
            # Medido: GCLA daba 353% anual porque su 2020 valia 190.299 USD
            # contra 217.556.293 en 2023 -- un salto de mil veces dentro de la
            # serie. CGPA2 igual, BOLT_2 17x. Un CAGR sobre una base mil veces
            # mal no es un crecimiento alto: es una potencia de mil disfrazada.
            _vs = sorted(u for _, u, _ in s if u > 0)
            if len(_vs) >= 3:
                _med = _vs[len(_vs) // 2]
                _rotos = [u for u in (v0, v1) if u > 0 and
                          (u < _med / 100.0 or u > _med * 100.0)]
                if _rotos:
                    motivo = motivo or ("extremo 100x fuera de su propia serie "
                                        "(escala del año base)")
                    continue
            años = (dt.date.fromisoformat(pe1) - dt.date.fromisoformat(pe0)).days / 365.25
            g = cagr(v0, v1, años)
            if g is None:
                motivo = motivo or ("extremo negativo: el CAGR no existe"
                                    if (v0 <= 0 or v1 <= 0) else "sin datos")
                continue
            res[col] = g
            desde, hasta, n = pe0, pe1, len(s)
        if res:
            ok_list.append((tk, res.get("cagr_revenue_usd_5y"),
                            res.get("cagr_netincome_usd_5y"), desde, hasta, n))
            motivos["calculado"] += 1
        else:
            motivos[motivo or "sin datos"] += 1
        datos.append((res.get("cagr_revenue_usd_5y"), res.get("cagr_netincome_usd_5y"),
                      desde, hasta, n or None, None if res else motivo, tk))

    print(f"  empresas evaluadas: {len(datos)}")
    for k, v in motivos.most_common():
        print(f"     {k:<34} {v:>3}")

    if ok_list:
        print(f"\n  {'tk':<9}{'ventas %/año':>14}{'ganancia %/año':>16}{'ventana':<26}{'ej.'}")
        for tk, r, ni, d, h, n in sorted(ok_list, key=lambda x: -(x[1] or -999))[:18]:
            rr = f"{r:,.1f}" if r is not None else "-"
            nn = f"{ni:,.1f}" if ni is not None else "-"
            print(f"  {tk:<9}{rr:>14}{nn:>16}  {d}..{h}  {n}")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        return
    cur.executemany(
        """UPDATE screener SET cagr_revenue_usd_5y=?, cagr_netincome_usd_5y=?,
                               cagr_desde=?, cagr_hasta=?, cagr_ejercicios=?,
                               cagr_motivo=? WHERE ticker=?""", datos)
    con.commit()
    n = cur.execute("SELECT COUNT(*) FROM screener WHERE cagr_revenue_usd_5y IS NOT NULL").fetchone()[0]
    print(f"\n  screener: {n} empresas con crecimiento de ventas a 5 años en USD")
    con.close()
    print("\nFASE 7C -- OK")


if __name__ == "__main__":
    main()
