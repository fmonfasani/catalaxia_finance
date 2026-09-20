"""Coordinator: obtiene el agente autorizado, lo ejecuta, registra evidencia,
pide la transicion de estado al Kernel -- y nunca se salta ninguna de esas
reglas.

Cubre TEST 7 a TEST 12 del pedido de Fase 3.
"""
from __future__ import annotations

import pytest

from coordinator.coordinator import Coordinator
from kernel.errors import AgentNotFoundError, InvalidTransitionError, NoAgentAuthorizedError
from kernel.state_machine import RunStatus


def test_coordinator_obtiene_el_agente_desde_el_registry(run_manager, registry_with_classifier):
    """TEST 7."""
    coordinator = Coordinator(run_manager=run_manager, registry=registry_with_classifier)
    run = run_manager.create_run()
    assert run.current_stage == "Requirement"
    agent_id = coordinator._agent_id_for_current_stage(run)
    assert agent_id == "classifier"
    assert registry_with_classifier.get(agent_id) is registry_with_classifier.get("classifier")


def test_coordinator_ejecuta_el_classifier(coordinator, run_manager):
    """TEST 8."""
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI único")
    assert run.last_agent == "classifier"
    assert run.last_result["output"]["category"] == "FEATURE"


def test_resultado_queda_registrado_como_evidence(coordinator, run_manager):
    """TEST 9."""
    run = run_manager.create_run()
    coordinator.execute_stage(run, "El sistema da error 500")
    assert len(run.evidence) == 1
    ev = run.evidence[0]
    for campo in ("agent_id", "input", "output", "status", "timestamp"):
        assert campo in ev
    assert ev["agent_id"] == "classifier"
    assert ev["output"]["category"] == "BUG"
    tipos = [e.event_type.value for e in run.events]
    assert "EVIDENCE_RECORDED" in tipos


def test_kernel_controla_la_transicion_de_estado(coordinator, run_manager):
    """TEST 10: el Run termina en COMPLETED (via StateMachine, no a mano) y
    la etapa avanzo de la mano del Pipeline -- no del Coordinator
    inventando un estado."""
    run = run_manager.create_run()
    assert run.status is RunStatus.PENDING
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI único")
    assert run.status is RunStatus.COMPLETED
    # la transicion PENDING->RUNNING->COMPLETED debe estar en el historial de eventos
    cambios = [e.metadata for e in run.events if e.event_type.value == "STATE_CHANGED"]
    secuencia = [(c["from_status"], c["to_status"]) for c in cambios]
    assert secuencia == [("PENDING", "RUNNING"), ("RUNNING", "COMPLETED")]


def test_coordinator_no_puede_saltearse_la_state_machine(coordinator, run_manager):
    """TEST 11: forzar el Run a un estado terminal (APPROVED) y confirmar
    que el Coordinator no puede simplemente "correr igual" -- la
    StateMachine lo rechaza al intentar volver a RUNNING."""
    run = run_manager.create_run()
    run_manager.transition(run, RunStatus.RUNNING)
    run_manager.transition(run, RunStatus.COMPLETED)
    run_manager.transition(run, RunStatus.APPROVED)

    with pytest.raises(InvalidTransitionError):
        coordinator.execute_stage(run, "otro requerimiento")
    # APPROVED es terminal: el intento invalido no debe haber cambiado el status
    assert run.status is RunStatus.APPROVED


def test_coordinator_no_ejecuta_agentes_no_registrados(run_manager):
    """Complementa TEST 3 desde el lado del Coordinator: si el Registry esta
    vacio, el Coordinator no puede ejecutar nada -- no inventa un
    fallback."""
    from coordinator.agent_registry import AgentRegistry
    coordinator = Coordinator(run_manager=run_manager, registry=AgentRegistry())
    run = run_manager.create_run()
    with pytest.raises(AgentNotFoundError):
        coordinator.execute_stage(run, "cualquier input")


def test_coordinator_no_ejecuta_un_agente_no_autorizado_para_la_etapa(
    run_manager, registry_with_classifier, dummy_agent_factory,
):
    """Registra un segundo agente ("dummy") ademas del classifier. La etapa
    Requirement solo autoriza "Classifier" (Seccion 7 / toy_pipeline) -- el
    Coordinator debe llamar al classifier, nunca al dummy, aunque el dummy
    tambien este registrado y habilitado."""
    dummy = dummy_agent_factory("dummy")
    registry_with_classifier.register(dummy)
    coordinator = Coordinator(run_manager=run_manager, registry=registry_with_classifier)
    run = run_manager.create_run()

    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI único")

    assert run.last_agent == "classifier"
    assert dummy.calls == [], "el Coordinator nunca debio invocar al agente no autorizado"


def test_coordinator_reporta_si_ninguna_etapa_autoriza_un_agente(run_manager, registry_with_classifier):
    """La etapa de prueba "SinAgente" del toy_pipeline no declara ningun
    agente tipico -- el Coordinator debe fallar explicito, no inventar uno."""
    coordinator = Coordinator(run_manager=run_manager, registry=registry_with_classifier)
    run = run_manager.create_run()
    run_manager.advance_stage(run, "SinAgente")
    with pytest.raises(NoAgentAuthorizedError):
        coordinator.execute_stage(run, "cualquier input")


def test_coordinator_no_depende_del_etl_financiero():
    """TEST 12 -- misma tecnica que kernel/test_independence.py, aplicada a
    coordinator/ y agents/."""
    import ast
    from pathlib import Path

    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    base = Path(__file__).resolve().parents[1]
    ofensores = {}
    for carpeta in ("coordinator", "agents"):
        for py_file in (base / carpeta).glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
            hits = {i for i in imports if any(i == p or i.startswith(p + ".") for p in prohibidos)}
            if hits:
                ofensores[f"{carpeta}/{py_file.name}"] = hits
    assert not ofensores, f"coordinator/ o agents/ importa el ETL financiero: {ofensores}"


def test_run_completo_via_coordinator_persiste_correctamente(coordinator, run_manager, state_manager):
    """Circuito completo con persistencia real, sin mocks del Kernel."""
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI único")
    state_manager.save(run.to_dict())

    cargado = state_manager.load(run.run_id)
    assert cargado["status"] == "COMPLETED"
    assert cargado["agent"] == "classifier"
    assert cargado["result"]["output"]["category"] == "FEATURE"
    assert len(cargado["evidence"]) == 1
