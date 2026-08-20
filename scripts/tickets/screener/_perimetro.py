# -*- coding: utf-8 -*-
"""
Regla de perímetro contable — compartida por s2, s4 y s8
=========================================================
Una empresa presenta ante la CNV estados INDIVIDUAL y CONSOLIDADO, y ambos
alimentan `cnv_estados_norm`. Combinar conceptos de los dos en un mismo ratio
produce números sin significado: en una holding, dividir el NetIncome individual
(resultado por participación) entre el Revenue consolidado (ventas del grupo) no
es un margen.

LA REGLA
  Por cada (cuit, period_end) se elige UN perímetro y se usan SOLO sus conceptos.
  Se prefiere el que contenga `Revenue`, porque es el que refleja la actividad
  económica real -- en holdings eso da consolidado, que es el correcto. A igualdad,
  el más completo. Los conceptos que falten quedan sin dato; NO se rellenan con el
  otro perímetro.

SE DESCARTARON DOS REGLAS ANTES DE ESTA, y las dos parecían razonables:
  - "consolidado siempre": destruye el 73 % de los conceptos en casos mixtos.
  - "el más completo":     en una holding elige el individual, que es justo el
                           perímetro sin operaciones.
Ver docs/07-homologacion-cnv.md §7.3.

Vive en un módulo aparte para que s2, s4 y s8 apliquen exactamente el mismo
criterio. Si cada uno tuviera su copia, divergirían al primer cambio.
"""
from __future__ import annotations

_CACHE = {}


def limpiar_cache():
    """Para tests o corridas encadenadas dentro del mismo proceso."""
    _CACHE.clear()


def perimetro_preferido(cur, cuit, period_end):
    """Perímetro a usar para ese cuit+periodo. None si ninguno está declarado.

    None significa "no filtrar": pasa con las filas de origen BYMA, que no llevan
    tipo_balance porque no vienen de un documento de la CNV.
    """
    k = (cuit, period_end)
    if k in _CACHE:
        return _CACHE[k]
    try:
        cur.execute("""
            SELECT tipo_balance,
                   SUM(CASE WHEN concepto='Revenue' AND valor IS NOT NULL
                            THEN 1 ELSE 0 END) tiene_rev,
                   COUNT(DISTINCT concepto) n
            FROM cnv_estados_norm
            WHERE cuit=? AND period_end=? AND tipo_balance IS NOT NULL
              AND tipo_balance!=''
            GROUP BY tipo_balance
        """, (cuit, period_end))
        filas = cur.fetchall()
    except Exception:
        # Base sin la columna todavía (pipeline a medio migrar): no filtrar.
        filas = []
    if not filas:
        elegido = None
    elif len(filas) == 1:
        elegido = filas[0][0]
    else:
        # 1o el que tenga Revenue; a igualdad, el más completo
        filas = sorted(filas, key=lambda f: (f[1], f[2]), reverse=True)
        elegido = filas[0][0]
    _CACHE[k] = elegido
    return elegido


def filtro_sql(cur, cuit, period_end):
    """(fragmento_sql, params) para restringir al perímetro elegido.

    Uso:
        extra, pars = filtro_sql(cur, cuit, pe)
        cur.execute("SELECT ... WHERE cuit=? AND concepto=?" + extra,
                    [cuit, concepto] + pars)
    """
    p = perimetro_preferido(cur, cuit, period_end)
    return (" AND tipo_balance=? ", [p]) if p else ("", [])
