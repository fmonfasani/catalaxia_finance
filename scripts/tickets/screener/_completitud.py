# -*- coding: utf-8 -*-
"""
_completitud -- que periodos DEBERIA tener cada empresa, y cuales faltan
=========================================================================
LA COBERTURA NO ALCANZA
  `_expectativa` responde "tiene la fuente que le corresponde?" y con eso los
  huecos bajaron de 500 aparentes a 2 reales. Pero una empresa puede tener su
  fuente y aun asi faltarle la mitad de la serie: presento veinte trimestres y
  nosotros tenemos ocho.

  Eso no lo ve la cobertura. Hace falta contar periodos.

EL ESPERADO SALE DEL CALENDARIO, NO DE UNA REGLA FIJA
  Con `fiscal_calendar` sabemos cuando cierra el ejercicio de cada empresa. Con
  eso, entre su primer periodo conocido y hoy deberia haber un cierre cada tres
  meses. No se inventa una fecha de inicio: se toma la primera que la empresa
  efectivamente presento -- si empezo a cotizar en 2021, exigirle 2018 seria un
  falso hueco.

  Es la misma leccion de la cobertura: un hueco solo es un hueco contra lo que
  DEBERIA estar, y "deberia" no es una constante.

EL DESFASAJE DE PRESENTACION
  Un balance al 30 de junio no esta disponible el 1 de julio: la CNV da plazo y
  la SEC tambien. Exigir el trimestre recien cerrado produce un hueco en TODAS
  las empresas, todos los meses, y el aviso deja de significar algo.

  Por eso el ultimo periodo esperado se corre `MESES_GRACIA` hacia atras.

CLASIFICA EL HUECO, NO SOLO LO CUENTA
  Un faltante al principio de la serie y uno en el medio son problemas
  distintos:

    cola_vieja   antes del primer dato que tenemos. Puede ser que la empresa no
                 cotizaba, o que la extraccion no llego tan atras. Se informa,
                 no se persigue.
    interior     un hueco ENTRE dos periodos que si tenemos. Ese es el
                 sospechoso: la empresa presento antes y despues, asi que lo del
                 medio deberia estar. Es lo que rompe las series -- el TTM no se
                 puede armar con un hueco en el medio.
    punta        los mas recientes. Suele ser atraso de actualizacion, no de
                 historia, y se arregla con el actualizador diario.

  La distincion importa porque cuestan cosas distintas: un hueco `interior` es
  un dato que se perdio; uno de `punta` es un dato que todavia no se busco.
"""
from __future__ import annotations
import datetime as dt

MESES_GRACIA = 4        # plazo tipico entre el cierre y su presentacion


def _meses(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def periodos_esperados(primero, fy_end_month, hoy=None, meses_gracia=MESES_GRACIA):
    """Los cierres trimestrales entre `primero` y hoy, segun el calendario.

    Devuelve [] si falta el calendario: sin saber cuando cierra el ejercicio no
    se puede decir que periodos le tocan, y adivinarlo genera huecos falsos.
    """
    if not primero or not fy_end_month:
        return []
    hoy = hoy or dt.date.today()
    limite = hoy - dt.timedelta(days=meses_gracia * 30)
    y, m = int(primero[:4]), int(primero[5:7])
    # alinear el arranque al trimestre fiscal mas cercano hacia adelante
    while (fy_end_month - m) % 3 != 0:
        m += 1
        if m > 12:
            m, y = 1, y + 1
    out = []
    while True:
        # ultimo dia del mes m
        d = (dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1))
        if d > limite:
            break
        out.append(d.isoformat())
        m += 3
        if m > 12:
            m -= 12
            y += 1
    return out


def faltantes(tenemos, esperados):
    """[(period_end, clase)] con clase = cola_vieja | interior | punta."""
    if not esperados:
        return []
    tenemos = sorted(set(tenemos))
    if not tenemos:
        return [(p, "cola_vieja") for p in esperados]
    primero, ultimo = tenemos[0], tenemos[-1]
    out = []
    for p in esperados:
        if p in tenemos:
            continue
        if p < primero:
            out.append((p, "cola_vieja"))
        elif p > ultimo:
            out.append((p, "punta"))
        else:
            out.append((p, "interior"))
    return out


def diagnostico(con, cuit, fy_end_month, concepto="Revenue", hoy=None):
    """(tenemos, esperados, faltantes) para una empresa."""
    tenemos = [r[0] for r in con.execute(
        """SELECT DISTINCT period_end FROM cnv_estados_norm
           WHERE cuit=? AND concepto LIKE ? AND valor IS NOT NULL
           ORDER BY period_end""", (cuit, f"%{concepto}%"))]
    if not tenemos:
        return [], [], []
    esp = periodos_esperados(tenemos[0], fy_end_month, hoy)
    return tenemos, esp, faltantes(tenemos, esp)
