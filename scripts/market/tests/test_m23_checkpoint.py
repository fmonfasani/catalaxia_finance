# -*- coding: utf-8 -*-
"""
F-013 (recorte MARKET) -- validacion del contrato de checkpoint/reanudacion de M23
====================================================================================
`m6_scale.py` no reimplementa el motor de fetch: decide que instrumentos
saltear leyendo `market_raw_runs`, la tabla que `run_instrument()` ya escribe.
Esta suite prueba, contra el motor REAL (no una maqueta), las tres preguntas
del pedido:

  1. como se decide COMPLETADO / FALLIDO / A REINTENTAR
     -> `ya_exitosos()`, `test_ya_exitosos_*`
  2. que pasa si el proceso muere a mitad de un `run_instrument()`
     -> `test_crash_a_mitad_de_camino_*` (crash simulado con monkeypatch,
        no una maqueta del motor: se interrumpe la funcion REAL despues de
        que el RAW ya se escribio en disco y las filas de provenance ya se
        INSERTaron sin commit -- exactamente donde moriria un proceso matado
        en ese punto. `conn.rollback()` reproduce lo que Postgres hace solo
        cuando la conexion se cae).
  3. reanudacion sin duplicar RAW ni perder provenance
     -> `test_resume_no_duplica_ni_pierde_provenance`, `test_auditar_raw_huerfano_*`

Diseno completo, con el analisis de los limites exactos de transaccion:
outputs/docs/fase_market/F013_M23_CHECKPOINT_CONTRACT.md
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import m2_fetch_engine as eng                              # noqa: E402
import market_core as core                                 # noqa: E402
import m6_scale as scale                                    # noqa: E402
from market_source import FixtureSource                     # noqa: E402

from conftest import (META_BUE, TZ_BUE, alta_instrumento,   # noqa: E402
                      contar, resultado, ruedas, serie, uno)

HOY_BUE = datetime.now(TZ_BUE).date()
AYER_HABIL = ruedas(1, HOY_BUE - timedelta(days=1))[0]


def _spec(conn, iid, ticker="TST.BA"):
    return alta_instrumento(conn, iid, f"E{iid}", f"T{iid}", ticker, "ARS", "BUE")


def _correr(conn, spec, df, stage, guion=None):
    src = FixtureSource(guion or [resultado(df, META_BUE)],
                        snapshot_payload={"last_price": 101.0, "currency": "ARS",
                                          "volume": 1234})
    return eng.run_instrument(conn, spec, src, stage)


# ================================================== 1. completado / fallido

def test_ya_exitosos_incluye_solo_SUCCESS_de_ese_stage(limpiar):
    conn = limpiar
    a = _spec(conn, "CA")
    b = _spec(conn, "CB")
    _correr(conn, a, serie(ruedas(5, AYER_HABIL)), "chk1")
    # b falla (fuente sin filas) -> no debe aparecer en ya_exitosos
    from market_source import FetchResult
    rep_b = eng.run_instrument(conn, b, FixtureSource(
        [FetchResult(ok=False, error_type="EMPTY", error_message="sin filas", attempts=1)]),
        "chk1")
    assert rep_b.status == "FAILED"

    with conn.cursor() as cur:
        listos = scale.ya_exitosos(cur, "chk1")
    assert listos == {"CA"}


def test_ya_exitosos_no_mezcla_stages_distintos(limpiar):
    conn = limpiar
    a = _spec(conn, "CC")
    _correr(conn, a, serie(ruedas(5, AYER_HABIL)), "stage-x")
    with conn.cursor() as cur:
        assert scale.ya_exitosos(cur, "stage-x") == {"CC"}
        assert scale.ya_exitosos(cur, "stage-y") == set()   # otro stage, 0


def test_cuarentena_no_cuenta_como_exitosa(limpiar):
    """QUARANTINED (market_raw_runs.status='PARTIAL') no debe aparecer en
    ya_exitosos -- se re-intenta, pero cuarentenados_previamente() lo tiene
    que poder ver para no reintentar en silencio."""
    conn = limpiar
    a = _spec(conn, "CD")
    fechas = ruedas(40, AYER_HABIL)
    _correr(conn, a, serie(fechas), "chk-cuar")
    truncada = serie(fechas[-10:])
    rep = eng.run_instrument(conn, a, FixtureSource([resultado(truncada, META_BUE)]),
                             "chk-cuar")
    assert rep.status == "QUARANTINED"

    with conn.cursor() as cur:
        assert scale.ya_exitosos(cur, "chk-cuar") == {"CD"}  # la 1ra corrida SI valio
        previa = scale.cuarentenados_previamente(cur, "chk-cuar")
    iids = {r[0] for r in previa}
    assert iids == {"CD"}, "la cuarentena debe quedar visible para el resume"


# ============================================= 2. crash a mitad de camino

def test_crash_a_mitad_de_camino_no_deja_SUCCESS_a_medias(limpiar, raw_base):
    """Interrumpe `run_instrument()` REAL justo despues de que el RAW se
    escribio en disco y market_raw_runs/market_raw_files se INSERTaron sin
    commit -- el punto exacto donde moriria un proceso matado ahi. El
    rollback explicito reproduce lo que Postgres hace solo cuando la
    conexion se cae a mitad de una transaccion."""
    conn = limpiar
    spec = _spec(conn, "CR")
    df = serie(ruedas(5, AYER_HABIL))
    src = FixtureSource([resultado(df, META_BUE)])

    with patch.object(core, "classify_batch", side_effect=RuntimeError("crash simulado")):
        with pytest.raises(RuntimeError, match="crash simulado"):
            eng.run_instrument(conn, spec, src, "chk-crash")
    conn.rollback()      # esto es lo que Postgres hace solo si el proceso muere

    # 1. cero SUCCESS a medias -- ya_exitosos() no lo ve
    with conn.cursor() as cur:
        assert scale.ya_exitosos(cur, "chk-crash") == set()

    # 2. cero filas de provenance sobrevivieron (todo el bloque era una sola txn)
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_runs "
                     "WHERE instrument_id=%s", ("CR",)) == 0
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_files "
                     "WHERE run_id LIKE %s", ("chk-crash-CR-%",)) == 0
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily "
                     "WHERE instrument_id=%s", ("CR",)) == 0

    # 3. el market_fetch_log SI sobrevive -- se comitea aparte, al principio,
    #    ANTES del punto de crash. Queda como REQUESTED para siempre: la
    #    firma de "esto murio a mitad de camino".
    huerfano_log = contar(conn, "SELECT run_id, status FROM market_fetch_log "
                                "WHERE instrument_id=%s AND status='REQUESTED'", ("CR",))
    assert len(huerfano_log) == 1

    # 4. el RAW SI sobrevive en disco -- se escribe ANTES del punto de
    #    crash, fuera de la transaccion de Postgres.
    run_id = huerfano_log[0][0]
    raw_dir = eng.RAW_BASE / "CR" / run_id
    assert (raw_dir / "history.csv").exists()
    assert (raw_dir / "meta.json").exists()


def test_crash_luego_reintento_no_duplica_raw_ni_pisa_nada(limpiar, raw_base):
    """Tras el crash simulado, un reintento normal debe: (a) generar un
    run_id NUEVO (nunca reusa el del intento muerto), (b) tener exito limpio,
    (c) dejar el RAW del intento muerto intacto y aparte (no se sobreescribe,
    no se borra -- doctrina de RAW inmutable)."""
    conn = limpiar
    spec = _spec(conn, "CX")
    df = serie(ruedas(5, AYER_HABIL))

    with patch.object(core, "classify_batch", side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError):
            eng.run_instrument(conn, spec, FixtureSource([resultado(df, META_BUE)]),
                               "chk-retry")
    conn.rollback()
    run_id_muerto = uno(conn, "SELECT run_id FROM market_fetch_log "
                              "WHERE instrument_id=%s", ("CX",))
    dir_muerto = eng.RAW_BASE / "CX" / run_id_muerto
    assert (dir_muerto / "history.csv").exists()

    # reintento real, limpio
    rep2 = eng.run_instrument(conn, spec, FixtureSource([resultado(df, META_BUE)]),
                              "chk-retry")
    assert rep2.status == "SUCCESS"
    assert rep2.run_id != run_id_muerto, "el reintento debe usar un run_id nuevo"

    with conn.cursor() as cur:
        assert scale.ya_exitosos(cur, "chk-retry") == {"CX"}

    # el directorio del intento muerto sigue estando, intacto, sin fila que lo
    # referencie -- es RAW huerfano, no RAW duplicado ni corrompido
    assert (dir_muerto / "history.csv").exists()
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_files WHERE run_id=%s",
              (run_id_muerto,)) == 0
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_files WHERE run_id=%s",
              (rep2.run_id,)) == 2


# =================================================== 3. auditoria de huerfanos

def test_auditar_raw_huerfano_detecta_el_crash(limpiar, raw_base):
    conn = limpiar
    spec = _spec(conn, "CH")
    df = serie(ruedas(5, AYER_HABIL))
    with patch.object(core, "classify_batch", side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError):
            eng.run_instrument(conn, spec, FixtureSource([resultado(df, META_BUE)]),
                               "chk-audit")
    conn.rollback()

    huerfanos = scale.auditar_raw_huerfano(["CH"], conn=conn)
    assert len(huerfanos) == 2   # history.csv + meta.json
    assert {h["instrument_id"] for h in huerfanos} == {"CH"}


def test_auditar_raw_huerfano_no_marca_corridas_sanas(limpiar, raw_base):
    conn = limpiar
    spec = _spec(conn, "CS")
    _correr(conn, spec, serie(ruedas(5, AYER_HABIL)), "chk-sano")
    assert scale.auditar_raw_huerfano(["CS"], conn=conn) == []


# ============================================ 4. resume end-to-end (batch)

def test_resume_no_duplica_ni_pierde_provenance(limpiar, raw_base):
    """Simula dos invocaciones de m6_scale: la 1ra procesa 2 instrumentos (1
    ok, 1 falla); la 2da, con resume, debe re-fetchear SOLO el que fallo --
    nunca re-tocar el que ya esta SUCCESS."""
    conn = limpiar
    a = _spec(conn, "RA")
    b = _spec(conn, "RB")
    df = serie(ruedas(5, AYER_HABIL))
    stage = "chk-resume"

    from market_source import FetchResult
    rep_a = eng.run_instrument(conn, a, FixtureSource([resultado(df, META_BUE)]), stage)
    rep_b = eng.run_instrument(conn, b, FixtureSource(
        [FetchResult(ok=False, error_type="EMPTY", error_message="sin filas", attempts=1)]),
        stage)
    assert rep_a.status == "SUCCESS"
    assert rep_b.status == "FAILED"

    with conn.cursor() as cur:
        listos = scale.ya_exitosos(cur, stage)
    assert listos == {"RA"}

    filas_antes_de_a = contar(conn, "SELECT COUNT(*) FROM market_price_daily "
                                    "WHERE instrument_id='RA'")[0][0]

    # "2da invocacion": solo reprocesa lo que resume dejo afuera de `listos`
    especs_a_reintentar = [s for s in (a, b) if s.instrument_id not in listos]
    assert [s.instrument_id for s in especs_a_reintentar] == ["RB"]
    rep_b2 = eng.run_instrument(conn, b, FixtureSource([resultado(df, META_BUE)]), stage)
    assert rep_b2.status == "SUCCESS"

    # RA nunca se volvio a tocar: mismas filas, ninguna corrida nueva registrada
    filas_despues_de_a = contar(conn, "SELECT COUNT(*) FROM market_price_daily "
                                      "WHERE instrument_id='RA'")[0][0]
    assert filas_despues_de_a == filas_antes_de_a
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_runs WHERE instrument_id='RA'") == 1

    with conn.cursor() as cur:
        assert scale.ya_exitosos(cur, stage) == {"RA", "RB"}


# ================================= 5. prueba controlada a nivel de LOTE (m6_scale.correr_lote)

def test_lote_interrumpido_y_reanudado_control_completo(limpiar, raw_base):
    """Prueba controlada de interrupcion/reanudacion pedida explicitamente:
    4 instrumentos FALSOS (sin red, FixtureSource), corridos a traves del
    orquestador REAL de M23 (`m6_scale.correr_lote`), no una simulacion
    aparte. El instrumento 2 muere a mitad de camino (mismo mecanismo de
    crash de los tests de arriba) y arrastra la excepcion HASTA AFUERA de
    `correr_lote()` -- exactamente lo que pasaria si el proceso completo
    muriera ahi: 3 y 4 JAMAS se llegan a tocar en la 1ra invocacion.

    Verifica las tres propiedades pedidas explicitamente:
      (a) el resume selecciona EXACTAMENTE los instrumentos pendientes
      (b) cero duplicacion de RAW contado/registrado (el huerfano del
          intento muerto no se pisa ni se cuenta dos veces)
      (c) todo instrumento termina en un estado TERMINAL
          (market_fetch_log.status != 'REQUESTED' en su ULTIMA corrida)

    No toca red ni instrumentos reales -- I1..I4 son sinteticos.
    """
    conn = limpiar
    stage = "chk-lote-e2e"
    universo = [_spec(conn, f"L{n}") for n in range(1, 5)]     # L1..L4
    df = serie(ruedas(5, AYER_HABIL))
    source_real = None  # cada spec usa su propia FixtureSource via correr_lote

    # correr_lote llama eng.run_instrument(conn, spec, source, stage, ...) con
    # UNA sola `source` para todo el lote -- necesitamos que L2 falle y el
    # resto ande, asi que la fuente decide por ticker_yahoo.
    class FuenteControlada:
        name = "fixture"
        version = "fixture-e2e@1"

        def __init__(self, instrumento_que_muere):
            self.muere = instrumento_que_muere

        def fetch(self, ticker, params=None):
            from market_source import FetchResult
            return FetchResult(ok=True, df=df, metadata=META_BUE,
                               raw_bytes=df.to_csv(index=True).encode("utf-8"),
                               attempts=1)

        def snapshot(self, ticker):
            return {"last_price": 1.0, "currency": "ARS", "volume": 1}

    fuente = FuenteControlada("L2")
    real_classify = core.classify_batch

    # PriceRow no lleva instrument_id (solo entra al hash) -- pero
    # correr_lote() procesa `universo` en orden estricto, asi que la fila
    # "L2" es, por construccion, la 2da llamada a classify_batch.
    llamada = {"n": 0}

    def classify_que_mata_la_2da(nuevas, existentes, market_tz, now_utc=None):
        llamada["n"] += 1
        if llamada["n"] == 2:
            raise RuntimeError("crash simulado: proceso muerto procesando L2")
        return real_classify(nuevas, existentes, market_tz, now_utc)

    print("\n== INVOCACION 1: procesa L1..L4, L2 muere a mitad de camino ==")
    with patch.object(core, "classify_batch", side_effect=classify_que_mata_la_2da):
        with pytest.raises(RuntimeError, match="crash simulado"):
            scale.correr_lote(conn, universo, fuente, stage, sleep_s=0, con_snapshot=True)
    conn.rollback()
    print("   proceso 'murio' -- L3 y L4 nunca se tocaron")

    # -------- estado inmediatamente despues del crash --------
    con_log = contar(conn, "SELECT instrument_id, status FROM market_fetch_log ORDER BY 1")
    print(f"   market_fetch_log tras el crash: {con_log}")
    assert dict(con_log) == {"L1": "SUCCESS", "L2": "REQUESTED"}, (
        "L1 debe quedar terminal; L2 debe quedar en REQUESTED (la firma del "
        "crash); L3/L4 no deben existir -- nunca se llego a pedirlos")

    with conn.cursor() as cur:
        pendientes_pre = scale.ya_exitosos(cur, stage)
    assert pendientes_pre == {"L1"}

    huerfanos_L2 = scale.auditar_raw_huerfano(["L2"], conn=conn)
    print(f"   RAW huerfano de L2 tras el crash: {len(huerfanos_L2)} archivo(s)")
    assert len(huerfanos_L2) == 2   # el intento muerto SI dejo RAW en disco

    # -------- INVOCACION 2: resume --------
    print("\n== INVOCACION 2: --resume ==")
    with conn.cursor() as cur:
        listos = scale.ya_exitosos(cur, stage)
    pendientes = [s for s in universo if s.instrument_id not in listos]
    print(f"   ya_exitosos()={sorted(listos)} -> resume selecciona: "
          f"{[s.instrument_id for s in pendientes]}")

    # propiedad (a): el resume selecciona EXACTAMENTE lo pendiente
    assert [s.instrument_id for s in pendientes] == ["L2", "L3", "L4"]

    reportes2 = scale.correr_lote(conn, pendientes, fuente, stage, sleep_s=0,
                                  con_snapshot=True)
    assert {r.instrument_id: r.status for r in reportes2} == {
        "L2": "SUCCESS", "L3": "SUCCESS", "L4": "SUCCESS"}

    # -------- verificacion final: las 3 propiedades pedidas --------
    with conn.cursor() as cur:
        final = scale.ya_exitosos(cur, stage)
    print(f"\n   ya_exitosos() final: {sorted(final)}")
    assert final == {"L1", "L2", "L3", "L4"}, "(a) resume completo, universo entero SUCCESS"

    # (b) cero duplicacion de RAW CONTADO: cada instrumento tiene exactamente
    #     1 corrida SUCCESS con exactamente 2 archivos registrados -- el
    #     directorio huerfano de L2 (el intento muerto) sigue en disco, pero
    #     NUNCA se cuenta ni se pisa.
    for iid in ("L1", "L2", "L3", "L4"):
        n_success = uno(conn, "SELECT COUNT(*) FROM market_raw_runs "
                             "WHERE instrument_id=%s AND status='SUCCESS'", (iid,))
        assert n_success == 1, f"{iid}: {n_success} corridas SUCCESS (debia ser 1)"
    n_files_L2 = uno(conn, "SELECT COUNT(*) FROM market_raw_files f "
                          "JOIN market_raw_runs r USING (run_id) "
                          "WHERE r.instrument_id=%s", ("L2",))
    assert n_files_L2 == 2, "L2: RAW registrado debe ser 2 archivos, no 4 (sin duplicar)"
    huerfanos_final = scale.auditar_raw_huerfano(["L1", "L2", "L3", "L4"], conn=conn)
    print(f"   RAW huerfano final (deuda tecnica del crash, no duplicacion): "
          f"{[h['instrument_id'] for h in huerfanos_final]}")
    assert {h["instrument_id"] for h in huerfanos_final} == {"L2"}, (
        "solo L2 debe tener huerfano (el intento muerto); L1/L3/L4 corrieron limpio")

    # (c) todo estado de ejecucion final es TERMINAL (nunca REQUESTED)
    ultimo_status_por_instrumento = contar(conn, """
        SELECT DISTINCT ON (instrument_id) instrument_id, status
        FROM market_fetch_log ORDER BY instrument_id, log_id DESC""")
    print(f"   ultimo status por instrumento: {ultimo_status_por_instrumento}")
    TERMINALES = {"SUCCESS", "SIN_CAMBIOS", "FAILED", "PARTIAL"}
    for iid, status in ultimo_status_por_instrumento:
        assert status in TERMINALES, f"{iid}: ultimo status '{status}' no es terminal"
    assert {iid for iid, _ in ultimo_status_por_instrumento} == {"L1", "L2", "L3", "L4"}
    print("\n== las 3 propiedades pedidas quedaron verificadas: resume exacto, "
          "cero duplicacion de RAW contado, todo estado final terminal ==")
