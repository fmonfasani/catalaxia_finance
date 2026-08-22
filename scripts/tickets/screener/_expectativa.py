# -*- coding: utf-8 -*-
"""
_expectativa -- que fuentes le CORRESPONDEN a cada empresa
===========================================================
LA PIEZA QUE FALTABA PARA PODER AUDITAR
  Auditar sin expectativa produce falsos huecos. Una medicion ingenua sobre las
  572 empresas daba "500 sin datos de la CNV" -- y esta bien que no los tengan:
  son companias de Estados Unidos que nunca presentaron nada en Argentina.

  Un hueco solo es un hueco contra lo que DEBERIA estar. Sin esa referencia, el
  auditor reporta ruido y nadie lo mira.

LAS TRES FAMILIAS, Y QUE LE TOCA A CADA UNA

  sp500      499 empresas.  Solo SEC EDGAR (10-K / 10-Q trimestral).
             No presentan en la CNV: exigirselo es un falso hueco.

  byma_only   56 empresas.  Solo CNV. Cotizan unicamente en Buenos Aires y no
             tienen registro en la SEC. El precio viene de yfinance, pero eso es
             mercado, no estados contables.

  adr         17 empresas.  LAS DOS. Presentan en la CNV (balance argentino, en
             pesos, con reexpresion RT 6) y en la SEC (20-F anual y 6-K para los
             intermedios). Es el unico grupo con validacion cruzada posible, y
             por eso la expectativa es la mas exigente.

UNA TRAMPA QUE COSTO ENCONTRAR
  La tabla `ratios` mezcla dos fuentes bajo el mismo techo: los hechos de EDGAR
  y los precios de yfinance, distinguidos solo por la columna `grupo`
  ('adr_arg', 'sp500' contra 'byma_yf'). Una medicion por ticker daba que 54 de
  las 56 BYMA-only "tienen datos de EDGAR" -- y ninguna empareja por CIK. Eran
  filas de yfinance.

  Por eso la comprobacion de EDGAR se hace por CIK y NUNCA por ticker: el ticker
  colisiona entre mercados (INTR es un papel de BYMA y tambien un ADR brasilero).

PERIODICIDAD ESPERADA, que es lo que permite contar los huecos
  sp500       4 por año   10-Q x3 + 10-K
  byma_only   4 por año   la CNV pide trimestral (PeriodoBalance=3)
  adr         4 por año por CNV; por SEC 1 anual (20-F) + los 6-K que haya
"""
from __future__ import annotations

# grupo -> (fuentes obligatorias, fuentes opcionales, periodos esperados por año)
EXPECTATIVA = {
    "sp500":     ({"edgar"}, set(), 4),
    "byma_only": ({"cnv"},   {"yfinance"}, 4),
    "adr":       ({"cnv", "edgar"}, {"yfinance"}, 4),
}


def fuentes_esperadas(grupo):
    """(obligatorias, opcionales). Grupo desconocido -> nada exigido."""
    o, op, _ = EXPECTATIVA.get(grupo, (set(), set(), 0))
    return o, op


def periodos_por_año(grupo):
    return EXPECTATIVA.get(grupo, (None, None, 0))[2]


def fuentes_presentes(con, cuit, ticker):
    """Que fuentes tiene DE HECHO esta empresa."""
    hay = set()
    if con.execute("SELECT 1 FROM cnv_estados_norm WHERE cuit=? LIMIT 1",
                   (cuit,)).fetchone():
        hay.add("cnv")
    # EDGAR SOLO por CIK. Por ticker da falsos positivos: `ratios` guarda
    # tambien filas de yfinance (grupo='byma_yf') con el ticker local.
    if con.execute("SELECT 1 FROM facts WHERE cik=? LIMIT 1", (cuit,)).fetchone():
        hay.add("edgar")
    else:
        r = con.execute("SELECT cik FROM ratios WHERE ticker=? AND grupo NOT LIKE 'byma_yf'",
                        (ticker,)).fetchone()
        if r and con.execute("SELECT 1 FROM facts WHERE cik=? LIMIT 1",
                             (r[0],)).fetchone():
            hay.add("edgar")
    if con.execute("SELECT 1 FROM ratios WHERE ticker=? AND grupo='byma_yf' LIMIT 1",
                   (ticker,)).fetchone():
        hay.add("yfinance")
    return hay


def diagnostico(con, cuit, ticker, grupo):
    """(faltantes, presentes, extra). `extra` = fuentes que no se esperaban."""
    oblig, opc = fuentes_esperadas(grupo)
    hay = fuentes_presentes(con, cuit, ticker)
    return oblig - hay, hay, hay - oblig - opc
