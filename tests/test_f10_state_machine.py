"""F10 — la maquina de estados de RUN y STAGE tiene semantica consistente
frente a abortos.

El defecto (encontrado por F9, 16 residuos historicos): `run_scope` siempre
cerro el RUN ante una excepcion, pero nunca la ETAPA. Si el cuerpo moria entre
"escribi RUNNING" y "escribi el tramo terminal", la fila de `stage_runs`
quedaba en RUNNING para siempre, aunque el run padre ya dijera ABORTED.

La correccion vive en un solo lugar (`engine/db.py`: `abort_stage_if_open` +
`run_scope(..., stage_id=...)`) y en `engine/states.py` (nuevo
`StageState.ABORTED`, alcanzable solo desde estados SIN evidencia propia).
Seis scripts (S00-S04 + C3) pasan ahora `stage_id=STAGE_ID`.

Los tests E/G/H/K/M atacan el mecanismo real contra la base (mismo estilo que
F-040/F-050: sin DELETE — F-016 se lo quita a `catalaxia_engine` — se cierra
lo que quedo abierto, nunca se borra). K ademas ataca el `main()` REAL de
S00/S02, no una simulacion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.states import StageState, assert_transition  # noqa: E402

PIPELINE = "test-f10-state-machine"
STAGE = "TEST_F10_STAGE"


@pytest.fixture(scope="module")
def s():
    st = load_settings()
    if st.is_prod:
        pytest.skip("EXT-010")
    return st


@pytest.fixture(scope="module")
def eng(s):
    return edb.get_engine(s)


@pytest.fixture
def limpiar(eng):
    """No borra (F-016 le quita DELETE a `catalaxia_engine`): cierra.

    Cualquier run que este modulo haya dejado en RUNNING se cierra como
    ABORTED al terminar el test, en run Y en etapa — usando el propio
    mecanismo que se esta probando.
    """
    yield
    with eng.connect() as c:
        huerfanas = [r[0] for r in c.execute(text(
            "SELECT run_id FROM engine.runs "
            " WHERE pipeline_version IN (:p1, :p2) AND status='RUNNING'"),
            {"p1": PIPELINE, "p2": "test-f10-e2e-mode"})]
    for rid in huerfanas:
        edb.abort_stage_if_open(eng, rid, STAGE)
        edb.finish_run(eng, rid, "ABORTED")


def ultimo_stage_state(eng, run_id: str, stage_id: str = STAGE) -> str | None:
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT state FROM engine.stage_runs"
            " WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run_id, "s": stage_id}).first()
    return row[0] if row else None


def contar_filas_stage(eng, run_id: str, stage_id: str = STAGE) -> int:
    with eng.connect() as c:
        return c.execute(text(
            "SELECT count(*) FROM engine.stage_runs WHERE run_id=:r AND stage_id=:s"),
            {"r": run_id, "s": stage_id}).scalar()


def estado_run(eng, run_id: str):
    with eng.connect() as c:
        return c.execute(text(
            "SELECT status, finished_at FROM engine.runs WHERE run_id=:r"),
            {"r": run_id}).one()


def modulo(nombre):
    import importlib
    return importlib.import_module(nombre)


# ===========================================================================
# A-D. La matriz de transiciones (pura, sin DB)
# ===========================================================================

def test_A_ready_a_running():
    assert_transition(StageState.READY, StageState.RUNNING)


def test_B_camino_feliz_running_hasta_checkpointed():
    """RUNNING no llega a CHECKPOINTED de un salto: pasa por VALIDATING->PASSED."""
    assert_transition(StageState.RUNNING, StageState.VALIDATING)
    assert_transition(StageState.VALIDATING, StageState.PASSED)
    assert_transition(StageState.PASSED, StageState.CHECKPOINTED)


def test_C_camino_de_fallo_running_hasta_failed():
    assert_transition(StageState.RUNNING, StageState.VALIDATING)
    assert_transition(StageState.VALIDATING, StageState.FAILED)


def test_D_running_a_aborted_es_legal_desde_f10():
    assert_transition(StageState.RUNNING, StageState.ABORTED)


# ===========================================================================
# E. RUN ABORTED implica STAGE ABORTED (integracion real, modo standalone)
# ===========================================================================

def test_E_run_abortado_deja_la_etapa_abortada(eng, s, limpiar):
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
            run_id = run.run_id
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.PLANNED, StageState.READY)
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.READY, StageState.RUNNING)
            raise RuntimeError("fallo simulado durante RUNNING")

    st_run, fin = estado_run(eng, run_id)
    assert st_run == "ABORTED" and fin is not None
    assert ultimo_stage_state(eng, run_id) == "ABORTED", (
        "el run cerro ABORTED pero la etapa se quedo en el estado anterior "
        "-- exactamente el defecto que F9 encontro")


def test_E2_no_hay_transicion_evidencia_previa_para_el_aborto(eng, s, limpiar):
    """La fila ABORTED trae prev_state=RUNNING: no se inventa evidencia."""
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
            run_id = run.run_id
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.PLANNED, StageState.READY)
            raise RuntimeError("fallo en READY")
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT state, prev_state, gate_status, report FROM engine.stage_runs"
            " WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run_id, "s": STAGE}).mappings().one()
    assert row["state"] == "ABORTED"
    assert row["prev_state"] == "READY"
    assert row["gate_status"] is None, "ABORTED no trae un gate: no corrio ninguno"
    assert row["report"] is None, "ABORTED no trae report: es la ausencia de evidencia"


# ===========================================================================
# F. Nada sale de ABORTED; ABORTED no se alcanza desde estados con evidencia
# ===========================================================================

def test_F_no_permite_checkpointed_despues_de_aborted():
    with pytest.raises(ValueError):
        assert_transition(StageState.ABORTED, StageState.CHECKPOINTED)


@pytest.mark.parametrize("destino", list(StageState))
def test_F2_aborted_es_terminal_para_cualquier_destino(destino):
    if destino is StageState.ABORTED:
        pytest.skip("no aplica a si mismo")
    with pytest.raises(ValueError):
        assert_transition(StageState.ABORTED, destino)


@pytest.mark.parametrize("origen", [
    StageState.FAILED, StageState.PASSED, StageState.CHECKPOINTED, StageState.CERTIFIED,
])
def test_F3_estados_con_evidencia_no_transicionan_a_aborted(origen):
    """FAILED/PASSED/CHECKPOINTED/CERTIFIED ya tienen evidencia propia (report,
    checkpoint o certificacion). Un aborto de codigo no relacionado, mas tarde
    en el mismo run_scope, no puede retroactivamente borrarla."""
    with pytest.raises(ValueError):
        assert_transition(origen, StageState.ABORTED)


# ===========================================================================
# G. C11 no certifica un run ABORTED (sin tocar c11_certificar.py)
# ===========================================================================

def test_G_c11_niega_un_run_cuya_etapa_quedo_abortada(eng, s, limpiar):
    import c11_certificar as c11
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
            run_id = run.run_id
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.PLANNED, StageState.READY)
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.READY, StageState.RUNNING)
            raise RuntimeError("fallo antes de VALIDATING")
    acta = c11.certificar_run(eng, run_id)
    assert acta["veredicto"] == "NEGADA", (
        f"C11 certifico un run con etapa ABORTED sin evidencia: {acta}")


# ===========================================================================
# H. C12 no publica un run ABORTED (via la regla pura del publisher)
# ===========================================================================

def test_H_c12_bloquea_un_run_abortado_antes_de_publicar(eng, s, limpiar):
    import publisher as c12
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
            run_id = run.run_id
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.PLANNED, StageState.READY)
            raise RuntimeError("fallo antes de RUNNING")

    with eng.connect() as conn:
        c10_pass, detalle = c12.collect_c10(conn, run_id)
        cert = c12.fetch_certification(conn, run_id)
    assert c10_pass is False, (
        f"la unica etapa quedo ABORTED (sin gate PASS) y C10 la dio por buena: {detalle}")
    permitido, motivo = c12.gate_decide(c10_pass, cert["veredicto"] if cert else None)
    assert permitido is False
    assert motivo.startswith("BLOCK:"), f"se esperaba BLOCK, dio {motivo!r}"


# ===========================================================================
# I/J. Idempotencia del cierre
# ===========================================================================

def test_I_cerrar_dos_veces_no_duplica_la_fila(eng, s, limpiar):
    run = edb.start_run(eng, s, PIPELINE)
    edb.record_stage_transition(eng, run.run_id, STAGE,
                                StageState.PLANNED, StageState.READY)
    edb.record_stage_transition(eng, run.run_id, STAGE,
                                StageState.READY, StageState.RUNNING)
    antes = contar_filas_stage(eng, run.run_id)

    primero = edb.abort_stage_if_open(eng, run.run_id, STAGE)
    segundo = edb.abort_stage_if_open(eng, run.run_id, STAGE)

    assert primero is True, "el primer cierre debia escribir la fila ABORTED"
    assert segundo is False, "el segundo cierre debia ser un no-op"
    despues = contar_filas_stage(eng, run.run_id)
    assert despues == antes + 1, f"se esperaba +1 fila, hubo {despues - antes}"
    edb.finish_run(eng, run.run_id, "ABORTED")


def test_J_doble_cierre_no_altera_el_historial(eng, s, limpiar):
    """La fila ABORTED original queda intacta: mismo prev_state, mismo id."""
    run = edb.start_run(eng, s, PIPELINE)
    edb.record_stage_transition(eng, run.run_id, STAGE,
                                StageState.PLANNED, StageState.READY)
    edb.abort_stage_if_open(eng, run.run_id, STAGE)
    with eng.connect() as c:
        antes = c.execute(text(
            "SELECT id, state, prev_state FROM engine.stage_runs"
            " WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run.run_id, "s": STAGE}).mappings().one()

    edb.abort_stage_if_open(eng, run.run_id, STAGE)   # segundo intento
    with eng.connect() as c:
        despues = c.execute(text(
            "SELECT id, state, prev_state FROM engine.stage_runs"
            " WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run.run_id, "s": STAGE}).mappings().one()

    assert dict(antes) == dict(despues), "la fila terminal cambio tras un segundo cierre"
    edb.finish_run(eng, run.run_id, "ABORTED")


# ===========================================================================
# K. Excepcion dentro del main() REAL de una etapa produce el estado correcto
#
# `_correr` envuelve TODO el ciclo de vida de la etapa (incluida la escritura
# de READY/RUNNING): monkeypatchearla entera -- como hace F-050, que solo le
# importa el RUN -- deja cero filas en stage_runs (caso N3, correcto pero no
# es lo que este test quiere probar). Para reproducir "murio CON evidencia
# parcial ya escrita" (el escenario real que dejo los 16 residuos de F9) se
# envuelve `edb.record_stage_transition` y se deja pasar todo salvo la
# escritura de VALIDATING: RUNNING ya quedo grabado cuando explota, igual que
# en los 16 casos historicos.
# ===========================================================================

@pytest.mark.parametrize("etapa,stage_id", [
    ("s00_smoke", "S00_bootstrap"),
    ("s01_identity", "S01_identity"),
    ("s02_fetch_ypf", "S02_fetch"),
])
def test_K_fallo_real_deja_run_y_etapa_abortados(eng, monkeypatch, etapa, stage_id):
    m = modulo(etapa)
    pipeline = m.PIPELINE_VERSION
    original = edb.record_stage_transition

    def explota_en_validating(engine, run_id, sid, prev_state, new_state, **kw):
        if new_state is StageState.VALIDATING:
            raise RuntimeError(f"fallo inyectado F10 en {etapa}: murio justo "
                              f"despues de RUNNING (prev_state={prev_state})")
        return original(engine, run_id, sid, prev_state, new_state, **kw)

    monkeypatch.setattr(m.edb, "record_stage_transition", explota_en_validating)
    monkeypatch.setattr(sys, "argv", [etapa])
    with pytest.raises((RuntimeError, SystemExit)):
        m.main()

    with eng.connect() as c:
        run_id, st = c.execute(text(
            "SELECT run_id, status FROM engine.runs WHERE pipeline_version=:p"
            " ORDER BY started_at DESC LIMIT 1"), {"p": pipeline}).one()
    assert st == "ABORTED", f"{etapa}: el run quedo {st}"
    ultimo = ultimo_stage_state(eng, run_id, stage_id)
    assert ultimo == "ABORTED", (
        f"{etapa}: la etapa {stage_id} quedo en {ultimo!r} tras el fallo real, no ABORTED")


# ===========================================================================
# L. El estado RUNNING legitimo (corrida que SI termina bien) sigue intacto
# ===========================================================================

def test_L_una_corrida_exitosa_nunca_pasa_por_aborted(eng, s, limpiar):
    run_id = None
    with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
        run_id = run.run_id
        cur = StageState.PLANNED
        for nxt in (StageState.READY, StageState.RUNNING, StageState.VALIDATING,
                   StageState.PASSED, StageState.CHECKPOINTED):
            edb.record_stage_transition(eng, run.run_id, STAGE, prev_state=cur, new_state=nxt)
            cur = nxt
        run.status = "OK"

    assert estado_run(eng, run_id)[0] == "OK"
    assert ultimo_stage_state(eng, run_id) == "CHECKPOINTED"
    with eng.connect() as c:
        n_aborted = c.execute(text(
            "SELECT count(*) FROM engine.stage_runs"
            " WHERE run_id=:r AND stage_id=:s AND state='ABORTED'"),
            {"r": run_id, "s": STAGE}).scalar()
    assert n_aborted == 0, "una corrida exitosa no debe dejar NINGUNA fila ABORTED"


def test_L2_corridas_huerfanas_vivas_no_se_confunden_con_residuo_muerto(eng):
    """El detector de huerfanas (run.status='RUNNING' de verdad) es un
    mecanismo distinto del cierre de F10 y no debe verse afectado por el."""
    vivas = edb.corridas_huerfanas(eng, horas=0.0)
    for v in vivas:
        assert v["mode"] in ("FAST", "FULL", "AUDIT")


# ===========================================================================
# M. Comportamiento del orchestrator (modo E2E: run_id compartido)
# ===========================================================================

def test_M_modo_e2e_cierra_la_etapa_aunque_no_cierre_el_run(eng, s, limpiar):
    """En modo E2E (run_id provisto), run_scope NO cierra el run -- el
    orquestador es su dueno declarado -- pero SI debe cerrar la etapa: el
    dueno de la etapa es la etapa, no quien comparte el run_id."""
    run = edb.start_run(eng, s, "test-f10-e2e-mode")
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, "test-f10-e2e-mode", run_id=run.run_id,
                           stage_id=STAGE) as inner:
            edb.record_stage_transition(eng, inner.run_id, STAGE,
                                        StageState.PLANNED, StageState.READY)
            edb.record_stage_transition(eng, inner.run_id, STAGE,
                                        StageState.READY, StageState.RUNNING)
            raise RuntimeError("fallo simulado dentro de una subetapa E2E")

    st_run, fin = estado_run(eng, run.run_id)
    assert st_run == "RUNNING" and fin is None, (
        "run_scope en modo E2E NO debe cerrar el run: eso es responsabilidad "
        "del orquestador, sin cambios por F10")
    assert ultimo_stage_state(eng, run.run_id) == "ABORTED", (
        "la etapa debe cerrarse aunque el run siga abierto: son dos dueños "
        "distintos")
    edb.finish_run(eng, run.run_id, "ABORTED")   # lo hace el "orquestador" (el test)


def test_M2_orchestrator_cierra_el_run_cuando_una_subetapa_falla(eng):
    """El orquestador real ya cerraba el run correctamente (linea 202); F10 no
    lo toca. Se verifica leyendo el codigo, no reimplementando el orquestador."""
    src = (REPO / "scripts" / "engine" / "e2e_orchestrator.py").read_text(encoding="utf-8")
    assert 'edb.finish_run(engine, run_id, "ABORTED")' in src
    assert "run_scope con run_id no hace finish_run" in src, (
        "el comentario que documenta la division de responsabilidades debe seguir ahi")


# ===========================================================================
# N. run_scope: modo standalone (run_id=None) explicito
# ===========================================================================

def test_N_modo_standalone_cierra_run_y_etapa_juntos(eng, s, limpiar):
    run_id = None
    with pytest.raises(ZeroDivisionError):
        with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
            run_id = run.run_id
            edb.record_stage_transition(eng, run.run_id, STAGE,
                                        StageState.PLANNED, StageState.READY)
            1 / 0
    assert estado_run(eng, run_id)[0] == "ABORTED"
    assert ultimo_stage_state(eng, run_id) == "ABORTED"


def test_N2_sin_stage_id_el_comportamiento_es_identico_al_anterior(eng, s, limpiar):
    """Retrocompatibilidad: `stage_id` es opt-in. Sin el, cero filas en
    stage_runs y el run se cierra igual que siempre (comportamiento pre-F10)."""
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE) as run:      # SIN stage_id
            run_id = run.run_id
            raise RuntimeError("fallo sin stage_id")
    assert estado_run(eng, run_id)[0] == "ABORTED"
    with eng.connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM engine.stage_runs WHERE run_id=:r"),
            {"r": run_id}).scalar()
    assert n == 0, "sin stage_id, run_scope no debe escribir en stage_runs"


def test_N3_stage_sin_ninguna_fila_no_produce_escritura_fantasma(eng, s, limpiar):
    """Si la etapa murio ANTES de escribir su primera transicion (ni siquiera
    READY), no hay nada que abortar: `abort_stage_if_open` no inventa una fila
    de la nada."""
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE, stage_id=STAGE) as run:
            run_id = run.run_id
            raise RuntimeError("fallo antes de la primera transicion")
    assert estado_run(eng, run_id)[0] == "ABORTED"
    assert ultimo_stage_state(eng, run_id) is None, (
        "no debe aparecer ninguna fila de stage_runs para una etapa que nunca arranco")
