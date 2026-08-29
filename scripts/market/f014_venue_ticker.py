# -*- coding: utf-8 -*-
"""
F-014 -- contrato venue vs. proveedor -- IMPLEMENTADO (migracion 013 aplicada)
==============================================================================
Cableado desde `m1_symbol_mapping.py`, que llama `derivar_venue_ticker()` para
poblar `market_instruments.venue_ticker`/`venue_ticker_source`. Nace como
propuesta pura no cableada (revisada independientemente, ACCEPT_WITH_CONDITIONS,
ver outputs/docs/fase_market/F014_VENUE_TICKER_CONTRACT.md §0); esta version ya
es la logica de produccion -- una sola fuente de verdad, no hay una segunda
copia de la derivacion en el escritor. `ticker_canonico` no cambio de
significado ni de escritor: sigue siendo la clave del emisor.

EL PROBLEMA (verificado, no supuesto)
--------------------------------------
`scripts/market/m1_symbol_mapping.py:81`:

    ticker_canonico=(canon or tick or "").strip()

`canon` = `dim_entity.ticker_canonico` (nivel EMISOR: una fila por entity_id).
`tick`  = `dim_instrument.ticker`      (nivel INSTRUMENTO: una fila por listing).

Para un emisor con dos listados (BUE + NYSE/NASDAQ), `canon` es el MISMO valor
en las dos filas de `dim_instrument` (verificado: 0 divergencias en 73 filas
LOCAL/BYMA). El fetch de Market prefiere `canon` sobre `tick` incondicional-
mente, asi que la fila ADR hereda el ticker de BUE en vez del suyo propio.
`tick` (la columna descartada) YA es correcto en el 100% de los 12 casos ADR
existentes (ver `test_f014_venue_ticker.py::test_todos_los_adr_reales`).

EL CONTRATO PROPUESTO
----------------------
Tres conceptos que HOY viven en dos columnas se separan en tres:

  1. issuer_key      -- clave del EMISOR. Igual para todas las filas del
                         mismo entity_id. Es lo que `ticker_canonico` YA es
                         hoy en la practica (no se toca, solo se documenta).
  2. venue_ticker     -- simbolo con el que ESTA fila cotiza en `exchange`.
                         NUEVO. Se deriva de `dim_instrument.ticker` (nivel
                         instrumento), nunca de `dim_entity.ticker_canonico`
                         (nivel emisor). Para BUE coincide con issuer_key
                         (mismo dato, doble verificado); para no-BUE es el
                         valor que hoy solo sobrevive, sin declararlo, dentro
                         de `ticker_yahoo`.
  3. provider_symbol  -- clave de consulta al proveedor (Yahoo). Es lo que
                         `market_symbol_mappings.ticker_yahoo` YA es hoy (no
                         se toca). Para BUE lleva el sufijo `.BA` que Yahoo
                         exige y que NO es el simbolo real del mercado; para
                         no-BUE coincide con venue_ticker hoy, por convencion
                         de Yahoo, no porque el pipeline lo derive de una
                         fuente que declare autoridad sobre ese mercado.

`venue_ticker` es intencionalmente honesto sobre su procedencia: hoy la unica
fuente disponible es el ticker legado por-instrumento de `dim_instrument`, NO
un registro de mercado independiente (NYSE symbol directory, EDGAR company
tickers, etc.). Ese es el techo real de esta propuesta -- no reclama mas
certeza de la que tiene evidencia.

QUE SIGUE SIN HACER ESTE MODULO
--------------------------------
* No escribe en la base -- `derivar_venue_ticker()` es pura (sin I/O, sin
  conexion). El INSERT/UPDATE real vive en `m1_symbol_mapping.py`.
* No toca `m2_fetch_engine.py`, `m4_quality.py`, `m5_golden_case.py` ni
  `m6_scale.py`: F-014 se cerro con el consumidor estrictamente necesario
  (`m1_symbol_mapping.py`, el escritor). Esos otros siguen leyendo solo
  `ticker_canonico`/`ticker_yahoo` como antes.
* No cambia el comportamiento de ningun fetcher ni corre M23.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class VenueTickerResult:
    venue_ticker: Optional[str]
    venue_ticker_source: Optional[str]   # de que columna/fuente salio
    status: str                          # OK | REVISAR | SIN_DATO
    note: str = ""


def derivar_venue_ticker(ticker_canonico_emisor: Optional[str],
                         ticker_instrumento: Optional[str],
                         exchange: Optional[str]) -> VenueTickerResult:
    """Devuelve el simbolo que corresponde publicar en el namespace de
    `exchange` para ESTA fila.

    Regla unica: el venue_ticker sale de `ticker_instrumento` (nivel
    instrumento), nunca de `ticker_canonico_emisor` (nivel emisor) -- pase lo
    que pase con `exchange`. La coincidencia para filas BUE no es una regla
    especial: es que a nivel instrumento y a nivel emisor ya vale lo mismo
    (verificado, 0 divergencias en 73 filas).
    """
    t = (ticker_instrumento or "").strip()
    canon = (ticker_canonico_emisor or "").strip()

    if not t:
        return VenueTickerResult(
            None, None, "SIN_DATO",
            "dim_instrument.ticker vacio: no hay venue_ticker derivable")

    if "." in t or t.startswith("_ADR_"):
        return VenueTickerResult(
            None, None, "SIN_DATO",
            f"ticker_instrumento con forma sospechosa: {t!r}")

    resultado = VenueTickerResult(t, "dim_instrument.ticker", "OK")
    if canon and canon != t:
        resultado.note = (f"diverge del ticker_canonico del emisor "
                          f"({canon!r}) -- esperado si exchange={exchange!r} "
                          f"no es el mercado local del emisor")
    return resultado
