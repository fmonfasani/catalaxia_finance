"""RunManager: creacion, avance y finalizacion de un Run.

Cubre TEST 1 (crear una ejecucion correctamente), TEST 3 (una ejecucion puede
finalizar correctamente) y TEST 5 (los eventos quedan registrados) del pedido
de Fase 2.
"""
from __future__ import annotations

import pytest

from kernel.errors import InvalidTransitionError, UnknownStageError
from kernel.events import EventType
from kernel.state_machine import RunStatus


def test_crear_run_correctamente(run_manager):
    """TEST 1."""
    run = run_manager.create_run()
    assert run.run_id
    assert run.factory_version == "0.1.0-test"
    assert run.status is RunStatus.PENDING
    assert run.current_stage == "Requirement"          # primera etapa del toy_pipeline
    assert run.created_at == run.updated_at             # recien creado
    assert len(run.events) == 1
    assert run.events[0].event_type is EventType.RUN_CREATED


def test_run_pasa_de_pending_a_running(run_manager):
    """TEST 2 a nivel de Run completo (StateMachine ya lo cubre aislado)."""
    run = run_manager.create_run()
    run_manager.transition(run, RunStatus.RUNNING)
    assert run.status is RunStatus.RUNNING


def test_run_finaliza_correctamente(run_manager):
    """TEST 3: PENDING -> RUNNING -> COMPLETED -> APPROVED, con avance de
    etapa hasta Delivery en el medio."""
    run = run_manager.create_run()
    run_manager.transition(run, RunStatus.RUNNING)
    run_manager.advance_stage(run, "Specification")
    run_manager.advance_stage(run, "Delivery")
    run_manager.transition(run, RunStatus.COMPLETED)
    run_manager.transition(run, RunStatus.APPROVED)

    assert run.status is RunStatus.APPROVED
    assert run.current_stage == "Delivery"
    from kernel.state_machine import StateMachine
    assert StateMachine().is_terminal(run.status)


def test_transicion_invalida_es_rechazada_y_no_muta_el_run(run_manager):
    """TEST 4."""
    run = run_manager.create_run()
    estado_antes = run.status
    eventos_antes = len(run.events)
    with pytest.raises(InvalidTransitionError):
        run_manager.transition(run, RunStatus.COMPLETED)   # PENDING -> COMPLETED, invalida
    assert run.status == estado_antes, "un intento rechazado no debe cambiar el status"
    # si queda registrado como evento ERROR, es +1; nunca de mas
    assert len(run.events) == eventos_antes + 1
    assert run.events[-1].event_type is EventType.ERROR


def test_eventos_quedan_registrados_en_orden(run_manager):
    """TEST 5."""
    run = run_manager.create_run()
    run_manager.transition(run, RunStatus.RUNNING)
    run_manager.advance_stage(run, "Specification")
    run_manager.transition(run, RunStatus.BLOCKED)
    run_manager.transition(run, RunStatus.RUNNING)

    tipos = [e.event_type for e in run.events]
    assert tipos == [
        EventType.RUN_CREATED,
        EventType.STATE_CHANGED,     # PENDING -> RUNNING
        EventType.RUN_STARTED,       # Fase 4A: primer arranque del Run
        EventType.STAGE_COMPLETED,   # cierre de Requirement
        EventType.STAGE_STARTED,     # apertura de Specification
        EventType.STATE_CHANGED,     # RUNNING -> BLOCKED
        EventType.BLOCKED,           # motivo del bloqueo
        EventType.STATE_CHANGED,     # BLOCKED -> RUNNING
    ]
    # cada evento reconstruible sin inferencia: run_id presente y consistente
    assert all(e.run_id == run.run_id for e in run.events)


def test_no_se_puede_avanzar_a_una_etapa_inexistente(run_manager):
    run = run_manager.create_run()
    with pytest.raises(UnknownStageError):
        run_manager.advance_stage(run, "Etapa que no existe")


def test_run_to_dict_y_from_dict_son_consistentes(run_manager):
    run = run_manager.create_run()
    run_manager.transition(run, RunStatus.RUNNING)
    d = run.to_dict()
    assert d["status"] == "RUNNING"
    assert d["run_id"] == run.run_id
    assert len(d["events"]) == 3  # RUN_CREATED, STATE_CHANGED, RUN_STARTED (Fase 4A)

    from kernel.run_manager import Run
    reconstruido = Run.from_dict(d)
    assert reconstruido.status is RunStatus.RUNNING
    assert reconstruido.run_id == run.run_id
    assert reconstruido.current_stage == run.current_stage
