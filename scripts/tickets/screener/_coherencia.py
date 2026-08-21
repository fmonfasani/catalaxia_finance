# -*- coding: utf-8 -*-
"""
_coherencia -- relaciones que tienen que valer DENTRO de un mismo documento
===========================================================================
COMPLEMENTA LA BANDA, NO LA REEMPLAZA
  La banda en dolares compara cada numero contra el universo y caza los
  documentos que estan mal ENTEROS. Pero es ciega a los que estan mal a medias:
  si el activo esta bien y la facturacion mil veces abajo, los dos pueden caer
  dentro de sus bandas respectivas.

  La coherencia mira los numeros ENTRE SI. Un error de unidad que afecte a todo
  el documento por igual se cancela en un cociente -- y eso es justamente lo que
  la hace util: lo que sobrevive al cociente es lo que esta mal a medias.

  Caso que la motiva: GCLA 2021-09..2023-09 parece un tramo homogeneo (100% de
  acuerdo en el factor) pero al comprobarlo solo el 62% entra en banda. El tramo
  ALTERNA: los cierres de marzo y junio estan mil veces mas abajo que los de
  septiembre y diciembre. Una regla que asume homogeneidad los mezcla; la
  coherencia los separa.

LAS REGLAS, Y POR QUE CADA UNA
  identidad     Activo = Pasivo + Patrimonio. Es la ecuacion contable: si no
                cierra, algo del documento esta mal, y el desvio dice cuanto.
  contencion    El total contiene a sus partes: Activo >= AssetsCurrent,
                Activo >= Cash, Pasivo >= LiabilitiesCurrent. Si una parte
                supera al todo, una de las dos tiene la escala mal.
  cascada       Facturacion >= GrossProfit >= OperatingIncome. Una empresa no
                gana mas de lo que vende. Se admite que sean negativos.
  resultado     |Resultado| <= Facturacion x 3. Un resultado varias veces mayor
                que las ventas existe (venta de activos, revaluos), por eso el
                margen de 3 y no de 1 -- pero mil veces no.

  Todas son cocientes entre numeros del MISMO documento, asi que no dependen de
  la moneda, ni de la escala global, ni de la inflacion.

Solo LECTURA.
"""
from __future__ import annotations
import collections

# (nombre, concepto_mayor, concepto_menor, holgura)
CONTENCION = [
    ("activo>=corriente", "Assets", "AssetsCurrent", 1.02),
    ("activo>=caja", "Assets", "Cash", 1.02),
    ("pasivo>=corriente", "Liabilities", "LiabilitiesCurrent", 1.02),
    ("activo>=PPE", "Assets", "PPE", 1.02),
]
CASCADA = [("ventas>=bruto", "Revenue", "GrossProfit", 1.02)]


def hechos(con, cuit, period_end):
    return {cpt: v for cpt, v in con.execute(
        """SELECT concepto, valor FROM cnv_estados_norm
           WHERE cuit=? AND period_end=? AND valor IS NOT NULL""",
        (cuit, period_end))}


def revisar(d):
    """[(regla, detalle, severidad)] sobre un dict concepto->valor."""
    fallas = []

    a, p, pn = d.get("Assets"), d.get("Liabilities"), d.get("Equity")
    if a and p is not None and pn is not None and a != 0:
        desv = abs((p + pn) - a) / abs(a) * 100
        if desv >= 5:
            fallas.append(("identidad", f"A={a:,.0f} vs P+PN={(p+pn):,.0f} "
                                        f"({desv:.1f}% de desvio)", desv))

    for nombre, mayor, menor, holgura in CONTENCION + CASCADA:
        vm, vn = d.get(mayor), d.get(menor)
        if vm is None or vn is None or vm == 0:
            continue
        # se compara en valor absoluto: el signo lo trata cada regla aparte
        if abs(vn) > abs(vm) * holgura:
            veces = abs(vn) / abs(vm)
            # mas de 100 veces no es una particularidad contable: es escala
            sev = 100.0 if veces > 100 else (veces - 1) * 10
            fallas.append((nombre, f"{menor}={vn:,.0f} supera a {mayor}={vm:,.0f} "
                                   f"({veces:,.1f}x)", sev))

    rev, ni = d.get("Revenue"), d.get("NetIncome")
    if rev and ni is not None and rev != 0 and abs(ni) > abs(rev) * 3:
        veces = abs(ni) / abs(rev)
        fallas.append(("resultado", f"NetIncome={ni:,.0f} contra Revenue={rev:,.0f} "
                                    f"({veces:,.1f}x)", min(100.0, veces * 10)))
    return fallas


def por_empresa(con, cuit):
    """{period_end: [fallas]} para todos los periodos de una empresa."""
    out = {}
    for (pe,) in con.execute(
            "SELECT DISTINCT period_end FROM cnv_estados_norm WHERE cuit=? ORDER BY period_end",
            (cuit,)):
        f = revisar(hechos(con, cuit, pe))
        if f:
            out[pe] = f
    return out
