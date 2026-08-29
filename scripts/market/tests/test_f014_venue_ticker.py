# -*- coding: utf-8 -*-
"""
F-014 -- Acceptance tests del contrato propuesto (venue vs. proveedor)
========================================================================
`docs/review/FINDINGS.md` F-014, acceptance_test literal:

    "Para todo instrumento con exchange <> 'BUE', el simbolo publicado en el
    namespace de ese exchange debe provenir de un campo que la fuente
    declare como el simbolo de ese mercado, no de ticker_canonico."

ESTADO (post-migracion 013, implementado): F-014 se resolvio AGREGANDO
`market_instruments.venue_ticker`, no modificando `ticker_canonico` -- ese
campo sigue siendo, a proposito, la clave del emisor (ver
F014_VENUE_TICKER_CONTRACT.md). Por eso `TestBugCaracterizado` (que mira
`ticker_canonico`) sigue y debe seguir en VERDE: el "bug" que caracteriza
nunca se toco, se lo dejo atras con un campo nuevo. La prueba de que F-014
esta resuelto es `TestVenueTickerProduccion`, no un cambio de veredicto en
`TestBugCaracterizado`.

Tres capas:

  1. TestContratoPropuesto -- ejercita `f014_venue_ticker.derivar_venue_ticker`
     (la misma funcion que ahora usa `m1_symbol_mapping.py` en produccion)
     contra los datos reales de `data/screener.db`.

  2. TestBugCaracterizado -- lee `market_instruments.ticker_canonico` REAL en
     Postgres y documenta que ese campo especifico sigue mostrando el ticker
     local en la fila del ADR -- a proposito, por diseno (no es el fix, es lo
     que el fix decidio no tocar). Si esta clase falla, es porque alguien
     reasigno `ticker_canonico` -- revisar contra F-014 antes de arreglar el
     test.

  3. TestVenueTickerProduccion -- lee `market_instruments.venue_ticker` REAL
     en Postgres (post-migracion 013) y verifica el acceptance_test de F-014
     con la semantica NULL correcta (`exchange IS DISTINCT FROM 'BUE'`, no
     `<>`, por el hallazgo de la revision independiente: 499 filas
     `instrument_type='US'` tienen `exchange` NULL).

Universo verificado: los 12 instrumentos ADR que existen hoy en
`dim_instrument` (ver evidencia completa en
outputs/docs/fase_market/F014_VENUE_TICKER_CONTRACT.md), no una muestra.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

MARKET_DIR = Path(__file__).resolve().parent.parent
ROOT = next(p for p in MARKET_DIR.parents if (p / "data").is_dir())
sys.path.insert(0, str(MARKET_DIR))

from f014_venue_ticker import derivar_venue_ticker  # noqa: E402

SQLITE_PATH = ROOT / "data" / "screener.db"

# Verdad de referencia, independiente del codigo: simbolos NYSE/NASDAQ reales
# de estos 4 emisores, tal como cotizan hoy (no derivados de ninguna tabla
# del repo -- son el ground truth externo contra el que se audita).
VENUE_TICKER_REAL_CONOCIDO = {
    "YPFD": "YPF",      # YPF S.A. -- ADR NYSE
    "CEPU": "CEPU",     # Central Puerto -- ADR NYSE (coincide con local)
    "GGAL": "GGAL",     # Grupo Financiero Galicia -- ADR NASDAQ (coincide)
    "TGSU2": "TGS",      # Transportadora de Gas del Sur -- ADR NYSE
}

# Los 12 pares (BUE, NYSE/NASDAQ) completos, clasificados durante la
# auditoria F-014 (2026-08-26) contra data/screener.db en este repo.
UNIVERSO_ADR_COMPLETO = {
    "CRES":  ("CRESY", "VISIBLE"),
    "LOMA":  ("LOMA",  "MASKED"),
    "VIST":  ("VIST",  "MASKED"),
    "TGSU2": ("TGS",   "VISIBLE"),
    "PAMP":  ("PAM",   "VISIBLE"),
    "IRSA":  ("IRS",   "VISIBLE"),
    "GGAL":  ("GGAL",  "MASKED"),
    "SUPV":  ("SUPV",  "MASKED"),
    "BBAR":  ("BBAR",  "MASKED"),
    "TECO2": ("TEO",   "VISIBLE"),
    "CEPU":  ("CEPU",  "MASKED"),
    "YPFD":  ("YPF",   "VISIBLE"),
}


def _filas_dim_instrument():
    """(entity_canon, instrument_ticker, mercado, tipo) para TODO dim_instrument."""
    if not SQLITE_PATH.exists():
        pytest.skip(f"no existe {SQLITE_PATH}")
    conn = sqlite3.connect(str(SQLITE_PATH))
    try:
        rows = conn.execute("""
            SELECT de.ticker_canonico, di.ticker, di.mercado, di.tipo
            FROM dim_instrument di
            LEFT JOIN dim_entity de ON de.entity_id = di.entity_id
        """).fetchall()
    finally:
        conn.close()
    return rows


def _exchange_de(mercado: str) -> str:
    m = (mercado or "").upper()
    if m.startswith("BYMA"):
        return "BUE"
    if "NYSE" in m or "NASDAQ" in m:
        return "NYSE"
    return m


# ============================================================ contrato propuesto

class TestContratoPropuesto:
    """`derivar_venue_ticker` contra los datos reales de screener.db."""

    @pytest.mark.parametrize("entity_canon,exchange_symbol",
                             sorted(VENUE_TICKER_REAL_CONOCIDO.items()))
    def test_las_4_companias_pedidas(self, entity_canon, exchange_symbol):
        """YPF, CEPU, GGAL, TGSU2: el venue_ticker de la fila ADR coincide
        con el simbolo NYSE/NASDAQ real, no con el ticker_canonico del
        emisor cuando difieren."""
        filas = _filas_dim_instrument()
        adr = [r for r in filas if r[0] == entity_canon
              and _exchange_de(r[2]) == "NYSE"]
        assert len(adr) == 1, f"esperaba exactamente 1 fila ADR para {entity_canon}"
        canon, tick, mercado, tipo = adr[0]
        r = derivar_venue_ticker(canon, tick, "NYSE")
        assert r.status == "OK"
        assert r.venue_ticker == exchange_symbol, (
            f"{entity_canon}: venue_ticker={r.venue_ticker!r}, "
            f"esperado={exchange_symbol!r}")
        assert r.venue_ticker_source == "dim_instrument.ticker"

    def test_las_4_companias_local_BUE_tambien_correcto(self):
        """La fila LOCAL de las 4 companias: venue_ticker debe coincidir con
        ticker_canonico (mismo dato a las dos escalas, verificado)."""
        filas = _filas_dim_instrument()
        for entity_canon in VENUE_TICKER_REAL_CONOCIDO:
            local = [r for r in filas if r[0] == entity_canon
                    and _exchange_de(r[2]) == "BUE"]
            assert len(local) == 1
            canon, tick, mercado, tipo = local[0]
            r = derivar_venue_ticker(canon, tick, "BUE")
            assert r.status == "OK"
            assert r.venue_ticker == canon == entity_canon

    def test_universo_completo_12_adr(self):
        """Los 12 instrumentos ADR que existen hoy en dim_instrument, sin
        muestreo: cada uno resuelve al simbolo correcto conocido."""
        filas = _filas_dim_instrument()
        adr_rows = [r for r in filas if _exchange_de(r[2]) == "NYSE"]
        assert len(adr_rows) == 12, (
            f"universo ADR cambio: {len(adr_rows)} filas (se esperaban 12; "
            f"si esto crecio, ampliar UNIVERSO_ADR_COMPLETO)")
        vistos = set()
        for canon, tick, mercado, tipo in adr_rows:
            assert canon in UNIVERSO_ADR_COMPLETO, f"emisor ADR no catalogado: {canon}"
            esperado, clase = UNIVERSO_ADR_COMPLETO[canon]
            r = derivar_venue_ticker(canon, tick, "NYSE")
            assert r.status == "OK", f"{canon}: {r.note}"
            assert r.venue_ticker == esperado, (
                f"{canon} ({clase}): venue_ticker={r.venue_ticker!r} != {esperado!r}")
            vistos.add(canon)
        assert vistos == set(UNIVERSO_ADR_COMPLETO), "universo ADR no coincide 1:1"

    def test_acceptance_criterion_literal_F014(self):
        """Fraseo literal del acceptance_test de F-014: para exchange<>'BUE',
        el simbolo publicado NUNCA debe ser igual a ticker_canonico salvo que
        el dato de origen (a nivel instrumento) realmente coincida -- nunca
        por construccion/copiado del emisor."""
        filas = _filas_dim_instrument()
        for canon, tick, mercado, tipo in filas:
            exch = _exchange_de(mercado)
            if exch == "BUE":
                continue
            r = derivar_venue_ticker(canon, tick, exch)
            if r.status != "OK":
                continue
            # la propiedad que importa: el resultado vino de dim_instrument.ticker,
            # nunca del campo de emisor -- se cumple aunque el VALOR coincida
            # (6 de 12 casos), porque la fuente declarada es la correcta.
            assert r.venue_ticker_source == "dim_instrument.ticker"
            assert r.venue_ticker == tick


# ============================================================ bug caracterizado

class TestBugCaracterizado:
    """Evidencia contra la tabla REAL en Postgres (solo lectura). Si estas
    pruebas empiezan a fallar, es porque `ticker_canonico` ya no tiene el bug
    -- hay que revisar F-014, no arreglar este archivo."""

    @classmethod
    @pytest.fixture(scope="class")
    def filas_pg(cls):
        try:
            import market_db
        except ImportError:
            pytest.skip("market_db no importable (sys.path)")
        try:
            conn = market_db.connect()
        except Exception as e:                          # noqa: BLE001
            pytest.skip(f"Postgres no disponible para caracterizar el bug: {e}")
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT i.ticker_canonico, i.exchange, m.ticker_yahoo
                    FROM market_instruments i
                    JOIN market_symbol_mappings m USING (instrument_id)
                    WHERE i.instrument_type = 'ADR'
                """)
                rows = cur.fetchall()
        finally:
            conn.close()
        return rows

    def test_bug_sigue_presente_en_produccion_hoy(self, filas_pg):
        """Al menos las 6 filas ADR 'VISIBLE' del universo conocido deben
        seguir mostrando ticker_canonico == ticker local (el bug), NO el
        simbolo NYSE real, mientras F-014 siga OPEN."""
        visibles_esperados = {c: t for c, (t, clase) in UNIVERSO_ADR_COMPLETO.items()
                              if clase == "VISIBLE"}
        encontrados = 0
        for canon, exch, ticker_yahoo in filas_pg:
            if canon in visibles_esperados:
                simbolo_real = visibles_esperados[canon]
                assert canon != simbolo_real, (
                    f"{canon}: coincide con el simbolo real ({simbolo_real}) -- "
                    f"si esto paso porque F-014 ya se corrigio, actualizar esta suite")
                # el dato correcto sigue vivo, pero solo en ticker_yahoo (proveedor)
                assert ticker_yahoo == simbolo_real
                encontrados += 1
        assert encontrados == len(visibles_esperados), (
            f"se esperaban {len(visibles_esperados)} filas VISIBLE en market_instruments, "
            f"se encontraron {encontrados}")


# ==================================================== venue_ticker en produccion

class TestVenueTickerProduccion:
    """Post-migracion 013 (`ALTER TABLE market_instruments ADD COLUMN
    venue_ticker ...`) + backfill real via `m1_symbol_mapping.py`. Lee
    Postgres REAL, solo lectura. Esta es la prueba de que F-014 esta resuelto
    -- no `TestBugCaracterizado`, que a proposito sigue en verde.

    Usa `exchange IS DISTINCT FROM 'BUE'` (NULL-safe), no `exchange <> 'BUE'`,
    por el hallazgo de la revision independiente: 499 filas
    `instrument_type='US'` tienen `exchange` NULL y una comparacion con `<>`
    las excluiria en silencio (logica de tres valores de SQL)."""

    @classmethod
    @pytest.fixture(scope="class")
    def filas_pg(cls):
        try:
            import market_db
        except ImportError:
            pytest.skip("market_db no importable (sys.path)")
        try:
            conn = market_db.connect()
        except Exception as e:                          # noqa: BLE001
            pytest.skip(f"Postgres no disponible: {e}")
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT instrument_id, ticker_canonico, venue_ticker,
                           venue_ticker_source, exchange, instrument_type
                    FROM market_instruments
                    WHERE exchange IS DISTINCT FROM 'BUE'
                """)
                rows = cur.fetchall()
        finally:
            conn.close()
        return rows

    def test_acceptance_criterion_F014_null_safe(self, filas_pg):
        """acceptance_test de F-014, version NULL-safe: toda fila con
        exchange IS DISTINCT FROM 'BUE' (incluye NULL) tiene un venue_ticker
        no vacio, declarado por una fuente explicita -- nunca por copia de
        ticker_canonico."""
        assert len(filas_pg) == 12 + 499, (
            f"se esperaban 511 filas no-BUE (12 ADR + 499 US), hubo {len(filas_pg)}")
        for iid, canon, venue, source, exch, itype in filas_pg:
            assert venue, f"instrument_id={iid}: venue_ticker vacio"
            assert source == "dim_instrument.ticker", (
                f"instrument_id={iid}: venue_ticker_source={source!r}")

    def test_universo_12_adr_valores_reales(self, filas_pg):
        """Los 12 ADR, valores exactos -- incluye los 6 pedidos explicitamente
        (YPF, TGSU2, CRES, PAMP, IRSA, TECO2) y los 2 de coincidencia (CEPU,
        GGAL)."""
        adr = {int(iid): venue for iid, canon, venue, source, exch, itype
              in filas_pg if itype == "ADR"}
        assert adr == {
            59: "CRESY", 61: "LOMA", 63: "VIST", 66: "TGS", 68: "PAM",
            70: "IRS", 72: "GGAL", 74: "SUPV", 76: "BBAR", 78: "TEO",
            81: "CEPU", 84: "YPF",
        }

    def test_los_6_visibles_ya_no_repiten_ticker_canonico(self, filas_pg):
        """Los 6 casos donde F-014 era visible (YPF, TGSU2, CRES, PAMP, IRSA,
        TECO2): venue_ticker ahora difiere de ticker_canonico."""
        visibles = {59, 66, 68, 70, 78, 84}
        vistos = set()
        for iid, canon, venue, source, exch, itype in filas_pg:
            if int(iid) in visibles:
                assert venue != canon, (
                    f"instrument_id={iid}: venue_ticker sigue igual a "
                    f"ticker_canonico ({canon}) -- F-014 no se resolvio para esta fila")
                vistos.add(int(iid))
        assert vistos == visibles

    def test_los_2_coincidentes_siguen_correctos(self, filas_pg):
        """CEPU (81) y GGAL (72): coinciden por dato real, no por bug --
        venue_ticker == ticker_canonico debe seguir siendo cierto."""
        coincidentes = {81: "CEPU", 72: "GGAL"}
        vistos = {}
        for iid, canon, venue, source, exch, itype in filas_pg:
            if int(iid) in coincidentes:
                assert venue == canon == coincidentes[int(iid)]
                vistos[int(iid)] = venue
        assert vistos == coincidentes

    def test_499_filas_US_no_quedaron_afuera(self, filas_pg):
        """Regresion directa del hallazgo de la revision independiente: las
        filas US (exchange NULL) deben aparecer en la consulta NULL-safe."""
        us = [r for r in filas_pg if r[5] == "US"]
        assert len(us) == 499
        assert all(r[4] is None for r in us), "exchange de las filas US debia ser NULL"
