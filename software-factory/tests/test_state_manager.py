"""StateManager: persistencia de un Run (round-trip)."""
from __future__ import annotations

import pytest

from kernel.errors import RunNotFoundError
from kernel.state_machine import RunStatus


def test_guardar_y_cargar_un_run(run_manager, state_manager):
    run = run_manager.create_run()
    run_manager.transition(run, RunStatus.RUNNING)

    state_manager.save(run.to_dict())
    cargado = state_manager.load(run.run_id)

    assert cargado["run_id"] == run.run_id
    assert cargado["status"] == "RUNNING"
    assert len(cargado["events"]) == 3  # RUN_CREATED, STATE_CHANGED, RUN_STARTED (Fase 4A)


def test_cargar_un_run_inexistente_falla_explicito(state_manager):
    with pytest.raises(RunNotFoundError):
        state_manager.load("no-existe")


def test_list_run_ids(run_manager, state_manager):
    a = run_manager.create_run()
    b = run_manager.create_run()
    state_manager.save(a.to_dict())
    state_manager.save(b.to_dict())
    assert set(state_manager.list_run_ids()) == {a.run_id, b.run_id}


def test_exists(run_manager, state_manager):
    run = run_manager.create_run()
    assert not state_manager.exists(run.run_id)
    state_manager.save(run.to_dict())
    assert state_manager.exists(run.run_id)
