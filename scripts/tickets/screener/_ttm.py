# -*- coding: utf-8 -*-
"""
_ttm -- flujos de doce meses, detectando si la empresa acumula o no
====================================================================
LA DISTINCION QUE MOTIVA ESTO
  Un balance tiene dos clases de numeros y no se tratan igual:

    STOCK   Patrimonio, Activo, Deuda, Caja. Es una FOTO al cierre: el valor de
            un cierre es el valor, sin sumar nada.
    FLUJO   Ganancia, Ventas, EBITDA. Es lo que paso DURANTE un lapso.

  Un ratio que divide un flujo por un stock -- ROE, ROA, margen -- exige que el
  flujo sea de DOCE MESES. Si no, queda dividido por cuatro sin que se note,
  porque el numero sigue siendo plausible.

TRES CONFIRMACIONES INDEPENDIENTES DE QUE HACIA FALTA
  1. Los 37 papeles BYMA cuyo `ultimo_periodo` es un periodo intermedio.
  2. Los 12 ROE contradictorios entre `screener` y `ratios_cnv`.
  3. El cruce ADR: GGAL da ROE 0,208 por EDGAR y 0,025 por CNV. La CNV usaba
     196.134.493.000 -- un solo periodo -- contra los 1.401.267.579.000 de doce
     meses que reporta EDGAR.

SE DETECTA SI ACUMULA; NO SE SUPONE
  Los parciales de la CNV son ACUMULADOS desde el inicio del ejercicio en la
  gran mayoria de los casos, pero NO en todos. Medido sobre 71 empresas con
  serie suficiente: 66 acumulan, 4 no, 1 mixta.

  Suponerlo cuesta caro en las dos direcciones. Con GGAL -- que no acumula --
  restar dio trimestres negativos y un TTM identico al valor original:
      Q1 = 146          Q3 = 259 - 327 = -68
      Q2 = 327 - 146    Q4 = 196 - 259 = -63    suma = 196

EL DETECTOR USA Revenue, NO NetIncome
  Las ventas no pueden ser negativas, asi que un acumulado de ventas SOLO puede
  crecer dentro del ejercicio. La ganancia si puede bajar acumulada -- un
  trimestre con perdida hace retroceder el acumulado del año -- de modo que
  NetIncome no distingue "acumula" de "tuvo un mal trimestre".

  Comprobado: con NetIncome, ALUA y SEMI daban "SUELTO" cuando su Revenue
  muestra claramente que acumulan (15.194 -> 30.971 -> 50.418 millones).

DEVUELVE None ANTES QUE UN NUMERO A MEDIAS
  Si faltan trimestres, si hay un hueco, si no hay calendario fiscal o si no se
  puede determinar como informa, no se entrega un TTM parcial: se devuelve None
  con el motivo. Un ROE calculado sobre nueve meses es peor que uno ausente,
  porque el ausente se nota.
"""
from __future__ import annotations

CONCEPTO_DETECTOR = "Revenue"


def _meses(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def _trimestre(period_end, fy_end_month):
    """1..4, con fy_end_month = Q4."""
    return 4 - ((fy_end_month - int(period_end[5:7])) % 12) // 3


def _serie(con, cuit, concepto, hasta=None, perimetro=None):
    """{period_end: valor} con un solo valor por cierre."""
    q = """SELECT period_end, COALESCE(valor_corregido, valor), tipo_balance
           FROM cnv_estados_norm
           WHERE cuit=? AND concepto=? AND valor IS NOT NULL"""
    p = [cuit, concepto]
    if hasta:
        q += " AND period_end <= ?"
        p.append(hasta)
    out = {}
    for pe, v, tb in con.execute(q + " ORDER BY period_end", p):
        if perimetro and tb != perimetro:
            continue
        # el consolidado gana: mezclar perimetros en una ventana de doce meses
        # produce un flujo que no corresponde a ninguna entidad real
        if pe not in out or tb == "CONSOLIDADO":
            out[pe] = v
    return sorted(out.items())


def acumula(con, cuit, fy_end_month):
    """(True|False|None, votos). None = no se pudo determinar.

    Dentro de un ejercicio, un acumulado de ventas solo puede crecer. Se miran
    todos los ejercicios completos disponibles y gana la mayoria.
    """
    if not fy_end_month:
        return None, "sin_calendario"
    serie = dict(_serie(con, cuit, CONCEPTO_DETECTOR))
    pes = sorted(serie)
    crece = no_crece = 0
    for i in range(len(pes) - 3):
        w = pes[i:i + 4]
        if int(w[-1][5:7]) != fy_end_month:
            continue
        if any(_meses(w[j], w[j + 1]) != 3 for j in range(3)):
            continue
        v = [serie[x] for x in w]
        # 0,95 tolera un redondeo, no una caida real
        if all(v[j + 1] >= v[j] * 0.95 for j in range(3)):
            crece += 1
        else:
            no_crece += 1
    if crece + no_crece == 0:
        return None, "sin ejercicio completo"
    if crece == no_crece:
        return None, f"ambiguo ({crece} vs {no_crece})"
    return crece > no_crece, f"{max(crece, no_crece)} de {crece + no_crece}"


def desacumular(serie, fy_end_month):
    """[(pe, acumulado)] -> [(pe, suelto)]. None donde no se puede reconstruir."""
    out, prev = [], None
    for pe, cum in serie:
        if _trimestre(pe, fy_end_month) == 1:
            suelto = cum
        elif prev and _meses(prev[0], pe) == 3:
            suelto = cum - prev[1]
        else:
            suelto = None
        out.append((pe, suelto))
        prev = (pe, cum)
    return out


def ttm(con, cuit, concepto, fy_end_month, hasta=None, perimetro=None,
        acumulado=None):
    """(valor, ventana, metodo, motivo). valor None si no se puede armar el año.

    acumulado: True/False para forzar; None para detectarlo.
    metodo:    'decum' si hubo que des-acumular, 'suma' si ya venian sueltos.
    """
    if not fy_end_month:
        return None, None, None, "sin_calendario_fiscal"
    if acumulado is None:
        acumulado, votos = acumula(con, cuit, fy_end_month)
        if acumulado is None:
            return None, None, None, f"no se pudo determinar si acumula ({votos})"

    serie = _serie(con, cuit, concepto, hasta, perimetro)
    if len(serie) < 4:
        return None, None, None, f"solo {len(serie)} periodos"

    if acumulado:
        sueltos = [(pe, v) for pe, v in desacumular(serie, fy_end_month)
                   if v is not None]
        metodo = "decum"
    else:
        sueltos = serie
        metodo = "suma"

    if len(sueltos) < 4:
        return None, None, metodo, "no se pudieron reconstruir 4 trimestres"
    w = sueltos[-4:]
    if any(_meses(w[i][0], w[i + 1][0]) != 3 for i in range(3)):
        return None, None, metodo, "hueco en la serie trimestral"
    return sum(v for _, v in w), (w[0][0], w[-1][0]), metodo, None
