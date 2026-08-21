# -*- coding: utf-8 -*-
"""
ESCALA de las filas BYMA -- deducir el factor y VERIFICARLO antes de escribir
=============================================================================
EL PROBLEMA
  cnv_estados_norm tiene dos fuentes. La extraccion de la CNV (source_type
  'CUIT') lee del documento si los numeros van en unidades, miles o millones:
  usa escalas 1, 1.000 y 1.000.000. La fuente BYMA (4.098 filas) asume SIEMPRE
  escala 1.

  Resultado: las empresas que presentan en miles quedan divididas por mil, y las
  que presentan en millones, por un millon. Ejemplos medidos:

      CELU 2026-02-28  Revenue =     104.190.823   (sus otros periodos: ~48.000 millones)
      MIRG 2026-03-31  Revenue =         648.534   (sus otros periodos: ~291.000 millones)

  Y son siempre los periodos MAS RECIENTES: la fuente BYMA es la que trae lo
  ultimo. O sea, el dato mas nuevo de cada empresa -- el que usa el screener
  para los ratios -- es el que mas riesgo tiene.

POR QUE NO SE USA "EL FACTOR MAS FRECUENTE DE LA EMPRESA"
  Fue el primer intento y estaba mal. Las empresas CAMBIAN de unidad con la
  inflacion: CECO2 uso factor 1 hasta 2024-03 y 1.000 desde 2024-06. Aplicarle
  el mas frecuente a los periodos viejos los habria multiplicado por mil,
  rompiendo datos que estaban bien.

  Peor: el conteo por moda daba "MIRG deberia ser 1.000" cuando MIRG usa
  1.000.000 en todos sus periodos. La cifra que salia de ahi (1.162 filas
  afectadas) no era de fiar.

COMO SE HACE
  1. DEDUCIR por vecino temporal: el documento de la MISMA empresa mas proximo
     en fecha que si declare factor. Eso respeta los cambios de unidad.
  2. VERIFICAR con una regla independiente: los parciales de la CNV son
     ACUMULADOS desde el inicio del ejercicio, asi que dentro de un mismo
     ejercicio las ventas acumuladas NO PUEDEN BAJAR. Si al aplicar el factor
     deducido la serie pasa a crecer, el factor era correcto. Si sigue rota, la
     deduccion se descarta.
  3. Solo se propone lo que pasa las DOS. Lo demas queda marcado, sin tocar.

AMBIGUEDAD = NO SE TOCA
  CVH tiene el mismo cierre (2025-06-30) declarado con factor 1 y con
  1.000.000. Un documento duplicado con escalas incompatibles -- de lo que
  escondia la PK vieja. Ahi no se deduce nada: se marca y se deja para revisar
  a mano.

Solo LECTURA. Este modulo propone; no escribe.
"""
from __future__ import annotations
import collections


def factores_declarados(con):
    """{(cuit, period_end): factor} y el conjunto de cierres ambiguos."""
    por = collections.defaultdict(set)
    for cuit, pe, uf in con.execute(
            """SELECT cuit, period_end, unidad_factor FROM cnv_estados_v2
               WHERE unidad_factor IS NOT NULL AND period_end IS NOT NULL"""):
        try:
            por[(cuit, pe)].add(int(uf))
        except (TypeError, ValueError):
            pass
    ambiguos = {k for k, v in por.items() if len(v) > 1}
    return {k: v.pop() for k, v in por.items() if len(v) == 1}, ambiguos


def vecino(declarados, cuit, pe):
    """(factor, period_end_usado, distancia_dias) del documento mas proximo."""
    import datetime as dt
    try:
        d0 = dt.date.fromisoformat(pe)
    except Exception:
        return None, None, None
    mejor = None
    for (cu, p), f in declarados.items():
        if cu != cuit:
            continue
        try:
            dist = abs((dt.date.fromisoformat(p) - d0).days)
        except Exception:
            continue
        if mejor is None or dist < mejor[2]:
            mejor = (f, p, dist)
    return mejor if mejor else (None, None, None)


def serie_acumulada(con, cuit, pe, fy_end_month):
    """Ventas del mismo ejercicio que `pe`, en orden. [(period_end, valor)]."""
    y, m = int(pe[:4]), int(pe[5:7])
    # el ejercicio que contiene a `pe` termina en el proximo fy_end_month
    fin_y = y if m <= fy_end_month else y + 1
    ini = f"{fin_y - 1}-{fy_end_month:02d}-32"   # exclusivo, '32' ordena despues
    fin = f"{fin_y}-{fy_end_month:02d}-31"
    return con.execute(
        """SELECT period_end, valor FROM cnv_estados_norm
           WHERE cuit=? AND concepto LIKE '%Revenue%'
             AND period_end > ? AND period_end <= ?
             AND valor IS NOT NULL
           ORDER BY period_end""", (cuit, ini, fin)).fetchall()


def crece(serie, tol=0.9):
    """True si el acumulado no baja. tol deja pasar caidas menores al 10%."""
    vals = [v for _, v in serie if v]
    if len(vals) < 2:
        return None          # no se puede juzgar
    return all(vals[i] >= vals[i - 1] * tol for i in range(1, len(vals)))
