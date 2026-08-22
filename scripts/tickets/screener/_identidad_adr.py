# -*- coding: utf-8 -*-
"""
_identidad_adr -- el puente entre el simbolo local y el registro en la SEC
===========================================================================
UN PROBLEMA DE CAPA 0, NO DE DESCARGA
  Diez ADR figuraban "sin datos de EDGAR" cuando sus hechos estaban bajados hace
  meses. El motivo: la misma empresa tiene DOS simbolos y nadie tenia la
  correspondencia. Para el sistema, el ADR de Pampa en EDGAR (`PAM`) y el papel
  local (`PAMP`) eran dos empresas distintas.

  No hay nada que bajar. Es identidad, y se arregla sin tocar la red.

LA CLAVE ES EL CIK, NUNCA EL TICKER
  El ticker colisiona entre mercados: INTR es un papel de BYMA y tambien un ADR
  brasilero. Y `ratios` guarda ademas precios de yfinance con el ticker local
  (grupo='byma_yf'), asi que emparejar por ticker daba que 54 de las 56
  BYMA-only "tienen datos de EDGAR". Ninguna emparejaba por CIK.

DOS CASOS QUE PARECIAN HUECOS Y NO LO SON
  YPFLUZ  YPF Luz tiene CUIT propio (30714128309) y NO figura en el registro de
          la SEC. Es la subsidiaria de energia, una empresa distinta de YPF.
          Asociarle el CIK de la matriz le pondria los estados de otra compania.
          No es un hueco: es una empresa que legitimamente no presenta alla.

  CAAP    SI existe en la SEC (cik 1717393, CORPORACION AMERICA AIRPORTS S.A.),
          pero falta en `ratios`. El hueco es real y de descarga, no de mapeo.

Verificado contra https://www.sec.gov/files/company_tickers.json el 2026-08-21.
"""
from __future__ import annotations

# simbolo local (BYMA) -> (simbolo SEC, cik). El cik es la clave real.
PUENTE = {
    "GGAL":  ("GGAL",  "0001114700"),
    "GGALB": ("GGAL",  "0001114700"),   # clase B del mismo emisor
    "BBAR":  ("BBAR",  "0000913059"),
    "SUPV":  ("SUPV",  "0001517399"),
    "SUPVB": ("SUPV",  "0001517399"),   # clase B
    "BMA":   ("BMA",   "0001347426"),
    "CEPU":  ("CEPU",  "0001717161"),
    "LOMA":  ("LOMA",  "0001711375"),
    "VIST":  ("VIST",  None),           # cik se resuelve de `ratios`
    "CRES":  ("CRESY", "0001034957"),
    "IRSA":  ("IRS",   "0000933267"),
    "PAMP":  ("PAM",   "0001469395"),
    "TECO2": ("TEO",   "0000932470"),
    "TGSU2": ("TGS",   "0000931427"),
    "YPFD":  ("YPF",   "0000904851"),
    "CAAP":  ("CAAP",  "0001717393"),
}

# Empresas del grupo `adr` que NO tienen registro propio en la SEC. No son
# huecos: exigirles datos de EDGAR produce un falso faltante.
SIN_REGISTRO_SEC = {
    "YPFLUZ": "YPF Luz (cuit 30714128309) es subsidiaria y no presenta en la SEC",
}


def cik_de(ticker_local, con=None):
    """CIK del emisor en la SEC, o None si no le corresponde tener uno."""
    if ticker_local in SIN_REGISTRO_SEC:
        return None
    par = PUENTE.get(ticker_local)
    if not par:
        return None
    sec, cik = par
    if cik:
        return cik
    if con is not None:
        r = con.execute(
            "SELECT cik FROM ratios WHERE ticker=? AND grupo NOT LIKE 'byma_yf'",
            (sec,)).fetchone()
        return r[0] if r else None
    return None


def espera_edgar(ticker_local):
    """False cuando la empresa legitimamente no presenta en la SEC."""
    return ticker_local not in SIN_REGISTRO_SEC
