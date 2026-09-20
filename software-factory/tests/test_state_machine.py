"""StateMachine: transiciones validas e invalidas.

Cubre TEST 2 (pending -> running) y TEST 4 (transicion invalida rechazada)
del pedido de Fase 2.
"""
from __future__ import annotations

import pytest

from kernel.errors import InvalidTransitionError
from kernel.state_machine import RunStatus, StateMachine


def test_pending_a_running_es_valida():
    sm = StateMachine()
    assert sm.is_valid(RunStatus.PENDING, RunStatus.RUNNING)
    sm.assert_valid(RunStatus.PENDING, RunStatus.RUNNING)  # no debe levantar


def test_running_puede_ir_a_blocked_failed_o_completed():
    sm = StateMachine()
    for destino in (RunStatus.BLOCKED, RunStatus.FAILED, RunStatus.COMPLETED):
        assert sm.is_valid(RunStatus.RUNNING, destino)


def test_completed_a_running_es_invalida():
    """Ejemplo explicito del pedido de Fase 2: COMPLETED -> RUNNING nunca se
    permite."""
    sm = StateMachine()
    assert not sm.is_valid(RunStatus.COMPLETED, RunStatus.RUNNING)
    with pytest.raises(InvalidTransitionError) as exc:
        sm.assert_valid(RunStatus.COMPLETED, RunStatus.RUNNING)
    assert "COMPLETED" in str(exc.value) and "RUNNING" in str(exc.value)


def test_approved_es_terminal():
    sm = StateMachine()
    assert sm.is_terminal(RunStatus.APPROVED)
    assert sm.allowed_from(RunStatus.APPROVED) == set()


def test_pending_no_es_terminal():
    sm = StateMachine()
    assert not sm.is_terminal(RunStatus.PENDING)


def test_rejected_vuelve_a_pending():
    sm = StateMachine()
    assert sm.is_valid(RunStatus.REJECTED, RunStatus.PENDING)


@pytest.mark.parametrize("origen,destino", [
    (RunStatus.PENDING, RunStatus.COMPLETED),   # no puede saltear RUNNING
    (RunStatus.PENDING, RunStatus.BLOCKED),
    (RunStatus.FAILED, RunStatus.COMPLETED),     # FAILED solo reintenta (-> RUNNING)
    (RunStatus.BLOCKED, RunStatus.COMPLETED),    # BLOCKED solo reanuda (-> RUNNING)
    (RunStatus.APPROVED, RunStatus.PENDING),
])
def test_transiciones_invalidas_adicionales_son_rechazadas(origen, destino):
    sm = StateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.assert_valid(origen, destino)
