# -*- coding: utf-8 -*-
"""
_mep -- el MEP de una fecha concreta, con la fecha que realmente se uso
=======================================================================
Pieza compartida. Todo lo que convierta pesos a dolares en este proyecto pasa
por aca, para que la conversion sea una sola y se pueda auditar en un solo sitio.

POR QUE DEVUELVE TAMBIEN LA FECHA
  El MEP no cotiza fines de semana ni feriados: 1.883 ruedas en 2.843 dias
  corridos. Un balance que cierra el 31/12 (feriado) no tiene MEP ese dia, asi
  que se toma la ultima rueda ANTERIOR. Devolver solo el numero perderia el
  dato de que se uso el del 30/12, y sin eso nadie puede rehacer la cuenta.

  Regla: la rueda anterior mas cercana, nunca la posterior. Usar una rueda
  posterior seria mirar el futuro -- para un balance cerrado al 31/12, el dolar
  del 2/1 es informacion que ese dia no existia.

QUE PASA SI NO HAY DATO
  Devuelve (None, None, motivo). NUNCA cae al MEP de hoy: eso convertiria un
  balance de 2019 con el dolar de 2026 y el resultado seria basura con aspecto
  de dato. El que llama decide, pero el valor queda vacio y marcado.

LIMITE DE LA SERIE
  dolarito_cotizaciones arranca el 2018-10-29. Antes de esa fecha no hay MEP y
  se dice asi. Ninguna de las 56 empresas BYMA tiene un cierre anterior, pero
  los historicos largos si.

USO
    from _mep import MEP
    mep = MEP(con)                     # con = conexion sqlite abierta
    valor, fecha_real, motivo = mep.en("2025-12-31")
    usd = mep.convertir(pesos, "2025-12-31")   # (usd, fecha_real, motivo)
"""
from __future__ import annotations

INICIO_SERIE = "2018-10-29"


class MEP:
    """Consulta el MEP por fecha. Carga la serie una vez y resuelve en memoria."""

    def __init__(self, con, tipo="MEP"):
        self.tipo = tipo
        filas = con.execute(
            """SELECT fecha, venta, compra FROM dolarito_cotizaciones
               WHERE tipo=? AND (venta IS NOT NULL OR compra IS NOT NULL)
               ORDER BY fecha""", (tipo,)).fetchall()
        # Se usa `venta`: es a lo que se compran dolares. compra/venta son
        # iguales en esta serie, pero se fija el criterio por si dejan de serlo.
        self.serie = [(f, v if v is not None else c) for f, v, c in filas]
        self.fechas = [f for f, _ in self.serie]
        self.mapa = dict(self.serie)

    @property
    def cobertura(self):
        return (self.fechas[0], self.fechas[-1], len(self.fechas)) if self.fechas \
            else (None, None, 0)

    def en(self, fecha):
        """(valor, fecha_usada, motivo). motivo es None cuando salio bien."""
        if not fecha:
            return None, None, "sin_fecha"
        fecha = str(fecha)[:10]
        if not self.fechas:
            return None, None, "serie_vacia"
        if fecha < self.fechas[0]:
            return None, None, f"anterior_a_la_serie({self.fechas[0]})"
        if fecha in self.mapa:
            return self.mapa[fecha], fecha, None
        # ultima rueda anterior: bisect sobre la lista ya ordenada
        import bisect
        i = bisect.bisect_right(self.fechas, fecha) - 1
        if i < 0:
            return None, None, "sin_rueda_anterior"
        f = self.fechas[i]
        # Un hueco de mas de 10 dias no es un fin de semana: es serie faltante.
        # Se devuelve igual, pero declarado, para que no pase por dato normal.
        import datetime as dt
        dias = (dt.date.fromisoformat(fecha) - dt.date.fromisoformat(f)).days
        return self.mapa[f], f, (f"hueco_{dias}d" if dias > 10 else None)

    def convertir(self, pesos, fecha):
        """Pesos -> USD al MEP de esa fecha. (usd, fecha_usada, motivo)."""
        if pesos is None:
            return None, None, "sin_valor"
        v, f, motivo = self.en(fecha)
        if not v:
            return None, f, motivo
        return pesos / v, f, motivo
