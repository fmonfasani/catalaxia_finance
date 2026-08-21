# -*- coding: utf-8 -*-
"""
TABLERO -- en que estado esta cada capa de datos
=================================================
POR QUE EXISTE
  Despues de dos meses de arreglos, cada correccion destapaba otra cosa y no
  habia forma de saber si se estaba avanzando. El problema no era la falta de
  arreglos: era que nadie llevaba la cuenta. Sin un numero por capa, cada
  hallazgo parece un retroceso aunque sea un avance.

  Esto no arregla nada. Mide. Y medir es lo que convierte una lista infinita de
  problemas en un trabajo con final.

LA IDEA DE FONDO: CADA CAPA GARANTIZA ALGO
  Una capa no es "un script mas": es una promesa sobre los datos que salen de
  ella. Si la capa N garantiza que el periodo esta bien declarado, la capa N+1
  puede confiar en eso y no volver a comprobarlo.

  Y de ahi sale la regla de secuencia: una validacion solo se puede poner en la
  capa N si todo lo que necesita ya lo garantizan las capas anteriores. Ponerla
  antes hace que dispare sobre ruido; ponerla despues deja que el dato malo se
  propague a lo derivado.

LAS CAPAS, EN ORDEN, Y POR QUE ESE ORDEN
  0 IDENTIDAD   quien es esta empresa
                Sin esto no se pueden comparar periodos: no se sabe si son de la
                misma empresa. Va primero porque TODO lo demas la supone.
  1 INGESTA     esta el documento, y una sola vez
                Antes de juzgar un dato hay que tenerlo. La PK rota descartaba
                20.628 filas en silencio.
  2 TIEMPO      que periodo es y cuantos meses cubre
                Va antes que la unidad porque las reglas de unidad comparan
                periodos entre si. Con el periodo mal, comparan cosas distintas.
  3 UNIDAD      en que magnitud estan los numeros
                Va antes que la moneda: convertir un numero mal escalado da un
                dolar mal escalado.
  4 MONEDA      pesos y dolares, con el dolar de su fecha
  5 PERIMETRO   individual o consolidado
                Va despues de identidad y tiempo, que son los que dicen que
                perimetro corresponde a que periodo.
  6 COHERENCIA  los numeros concuerdan entre si
                Va ULTIMA de las capas de hechos: es la unica que puede validar
                el RESULTADO de todos los arreglos anteriores. Ponerla antes la
                hace disparar sobre ruido de escala en vez de sobre
                incoherencias reales.
  7 DERIVADO    ratios, TTM, CAGR -- solo sobre hechos que pasaron 0..6
  8 PUBLICADO   lo que ve el consumidor

USO
  python tablero.py
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")


def q1(cur, sql, *a):
    try:
        r = cur.execute(sql, a).fetchone()
        return r[0] if r else None
    except sqlite3.Error:
        return None


def barra(ok, total, ancho=22):
    if not total:
        return "sin datos"
    p = ok / total
    lleno = int(p * ancho)
    return "#" * lleno + "." * (ancho - lleno) + f"  {p*100:5.1f}%"


def main():
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    print("TABLERO DE DATOS")
    print("=" * 78)
    print(f"  base: {DB.name}\n")

    filas = []

    # 0 IDENTIDAD ------------------------------------------------------------
    tot = q1(cur, "SELECT COUNT(*) FROM screener") or 0
    sin_id = q1(cur, "SELECT COUNT(*) FROM screener WHERE ticker LIKE '\\_%' ESCAPE '\\'") or 0
    dup = q1(cur, """SELECT COUNT(*) FROM (SELECT cuit FROM screener
                     GROUP BY cuit HAVING COUNT(*) > 1)""") or 0
    filas.append(("0 IDENTIDAD", tot - sin_id - dup, tot,
                  f"{sin_id} sin ticker resuelto, {dup} cuit duplicado"))

    # 1 INGESTA --------------------------------------------------------------
    v2 = q1(cur, "SELECT COUNT(*) FROM cnv_estados_v2") or 0
    nrm = q1(cur, "SELECT COUNT(*) FROM cnv_estados_norm") or 0
    pk = q1(cur, "SELECT sql FROM sqlite_master WHERE name='cnv_estados_v2'") or ""
    pk_ok = "tipo_balance" in pk
    filas.append(("1 INGESTA", nrm if pk_ok else 0, nrm,
                  f"{v2} crudas -> {nrm} normalizadas; PK "
                  + ("corregida" if pk_ok else "SIN CORREGIR (pierde filas)")))

    # 2 TIEMPO ---------------------------------------------------------------
    byma = q1(cur, "SELECT COUNT(*) FROM screener WHERE grupo='byma_only'") or 0
    con_cal = q1(cur, """SELECT COUNT(*) FROM screener s JOIN fiscal_calendar f
                         ON f.cuit=s.cuit WHERE s.grupo='byma_only'""") or 0
    incons = q1(cur, """SELECT COUNT(*) FROM screener s JOIN fiscal_calendar f
                        ON f.cuit=s.cuit WHERE s.grupo='byma_only' AND f.inconsistent=1""") or 0
    filas.append(("2 TIEMPO", con_cal - incons, byma,
                  f"{con_cal}/{byma} con calendario; {incons} marcados inconsistentes"))

    # 3 UNIDAD ---------------------------------------------------------------
    # Mide hechos SIN RESPUESTA, no hechos dudosos. Un hecho dudoso al que ya se
    # le propuso una correccion verificada esta resuelto aunque la duda sobre el
    # documento siga: lo que falta saber es cuanto queda por decidir, no cuanto
    # habia al principio. Con la otra medida el avance no se notaba nunca.
    hechos = q1(cur, "SELECT COUNT(*) FROM cnv_estados_norm WHERE valor_usd IS NOT NULL") or 0
    dudosos = q1(cur, """SELECT COUNT(*) FROM cnv_estados_norm
                         WHERE usd_clase IN ('unidad','no_unidad')""") or 0
    resueltos = q1(cur, """SELECT COUNT(*) FROM cnv_estados_norm
                           WHERE usd_clase IN ('unidad','no_unidad')
                             AND valor_corregido IS NOT NULL""") or 0
    pend = dudosos - resueltos
    filas.append(("3 UNIDAD", hechos - pend, hechos,
                  f"{pend} sin respuesta ({dudosos} dudosos, {resueltos} ya corregidos)"))

    # 4 MONEDA ---------------------------------------------------------------
    conv = q1(cur, "SELECT COUNT(*) FROM cnv_estados_norm WHERE valor_usd IS NOT NULL") or 0
    sinm = q1(cur, "SELECT COUNT(*) FROM cnv_estados_norm WHERE usd_clase='sin_mep'") or 0
    imp = q1(cur, """SELECT COUNT(*) FROM cnv_estados_norm WHERE valor IS NOT NULL
                     AND concepto NOT LIKE 'CNV\\_%' ESCAPE '\\'
                     AND concepto NOT LIKE 'EPS\\_%' ESCAPE '\\'""") or 0
    filas.append(("4 MONEDA", conv, imp, f"{sinm} sin MEP para su fecha"))

    # 5 PERIMETRO ------------------------------------------------------------
    tb = q1(cur, """SELECT COUNT(*) FROM cnv_estados_norm
                    WHERE tipo_balance IS NOT NULL AND tipo_balance <> ''""") or 0
    tot_n = nrm
    filas.append(("5 PERIMETRO", tb, tot_n,
                  "declara individual/consolidado" if tb else "SIN declarar"))

    # 6 COHERENCIA -----------------------------------------------------------
    docs = q1(cur, """SELECT COUNT(DISTINCT n.cuit || n.period_end) FROM cnv_estados_norm n
                      JOIN screener s ON s.cuit=n.cuit WHERE s.grupo='byma_only'""") or 0
    mal = q1(cur, """SELECT COUNT(DISTINCT n.cuit || n.period_end) FROM cnv_estados_norm n
                     JOIN screener s ON s.cuit=n.cuit
                     WHERE s.grupo='byma_only' AND n.coherencia_falla IS NOT NULL""") or 0
    filas.append(("6 COHERENCIA", docs - mal, docs,
                  f"{mal} documentos se contradicen consigo mismos"))

    # 7 DERIVADO -------------------------------------------------------------
    per_ok = q1(cur, "SELECT COUNT(*) FROM per_ttm WHERE estado='ok'") or 0
    per_tot = q1(cur, "SELECT COUNT(*) FROM per_ttm") or 0
    perd = q1(cur, "SELECT COUNT(*) FROM per_ttm WHERE estado='perdida_real'") or 0
    filas.append(("7 DERIVADO", per_ok + perd, per_tot,
                  f"{per_ok} con PER, {perd} con perdida real (correcto que no tengan)"))

    # 8 PUBLICADO ------------------------------------------------------------
    pub = q1(cur, "SELECT COUNT(*) FROM screener WHERE PER IS NOT NULL") or 0
    filas.append(("8 PUBLICADO", pub, tot, f"{pub} de {tot} con PER publicado"))

    print(f"  {'capa':<14}{'estado':<32}{'detalle'}")
    print("  " + "-" * 74)
    for nombre, ok, total, det in filas:
        print(f"  {nombre:<14}{barra(ok, total):<32}{det}")

    print("\n  Como leerlo: el porcentaje es 'hechos que esa capa da por buenos'.")
    print("  Una capa no pasa a la siguiente lo que no garantiza; lo marca.")
    con.close()


if __name__ == "__main__":
    main()
