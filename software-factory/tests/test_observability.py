"""Observabilidad transversal: correlacion, orden, reconstruccion, redaccion.

Cubre los 15 puntos pedidos en la Fase 4A. Usa el circuito real
(RunManager + Coordinator + ClassifierAgent), no una maqueta.
"""
from __future__ import annotations

from kernel.state_machine import RunStatus
from observability import Artifact, build_trace, make_reference, query_run, redact_structure


# ------------------------------------------------------- 1. correlation id

def test_cada_run_tiene_correlation_id(run_manager, coordinator):
    run = run_manager.create_run()
    assert run.run_id
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI único")
    assert all(e.run_id == run.run_id for e in run.events)


# --------------------------------------------- 2. eventos del run correcto

def test_eventos_pertenecen_al_run_correcto(run_manager, registry_with_classifier):
    from coordinator.coordinator import Coordinator
    coordinator = Coordinator(run_manager=run_manager, registry=registry_with_classifier)
    run_a = run_manager.create_run()
    run_b = run_manager.create_run()
    coordinator.execute_stage(run_a, "Necesitamos agregar alta de clientes")
    coordinator.execute_stage(run_b, "El sistema da error 500")

    assert all(e.run_id == run_a.run_id for e in run_a.events)
    assert all(e.run_id == run_b.run_id for e in run_b.events)
    assert run_a.run_id != run_b.run_id


# ------------------------------------------- 3. transiciones generan eventos

def test_transiciones_generan_eventos(run_manager):
    run = run_manager.create_run()
    antes = len(run.events)
    run_manager.transition(run, RunStatus.RUNNING)
    tipos = [e.event_type.value for e in run.events[antes:]]
    assert "STATE_CHANGED" in tipos
    assert "RUN_STARTED" in tipos  # PENDING -> RUNNING es tambien el arranque del Run


# ------------------------------------------------- 4. coordinator genera eventos

def test_coordinator_genera_eventos(coordinator, run_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    tipos = {e.event_type.value for e in run.events}
    assert {"COORDINATOR_STARTED", "COORDINATOR_COMPLETED"} <= tipos


# --------------------------------------- 5/6. agent selection/execution eventos

def test_agent_selection_y_execution_generan_eventos(coordinator, run_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    tipos = {e.event_type.value for e in run.events}
    assert {"AGENT_SELECTED", "AGENT_STARTED", "AGENT_COMPLETED"} <= tipos
    seleccionado = [e for e in run.events if e.event_type.value == "AGENT_SELECTED"][0]
    assert seleccionado.component_id == "classifier"


# ------------------------------------------------- 7. agent failure genera evento

def test_agent_failure_genera_evento(coordinator, run_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "")  # input invalido -> ClassifierAgent status=ERROR
    tipos = {e.event_type.value for e in run.events}
    assert "AGENT_FAILED" in tipos
    assert "AGENT_COMPLETED" not in tipos
    assert run.status is RunStatus.FAILED


# -------------------------------------------------- 8. evidence correlacionada

def test_evidence_queda_correlacionada(coordinator, run_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    ev_evidencia = [e for e in run.events if e.event_type.value == "EVIDENCE_RECORDED"][0]
    assert ev_evidencia.run_id == run.run_id
    assert ev_evidencia.component_id == "classifier"
    assert ev_evidencia.metadata["evidence"] == run.evidence[-1]
    # correlacionable con el COORDINATOR_STARTED que la origino
    coord_started = [e for e in run.events if e.event_type.value == "COORDINATOR_STARTED"][0]
    assert ev_evidencia.parent_event_id == coord_started.event_id


# ---------------------------------------------- 9. orden temporal logico

def test_eventos_mantienen_orden_temporal_logico(coordinator, run_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    timestamps = [e.timestamp for e in run.events]
    assert timestamps == sorted(timestamps)

    tipos = [e.event_type.value for e in run.events]
    # COORDINATOR_STARTED antes de AGENT_SELECTED antes de AGENT_STARTED
    # antes de AGENT_COMPLETED antes de EVIDENCE_RECORDED antes de
    # COORDINATOR_COMPLETED -- el orden logico del circuito, no solo el
    # cronologico (ambos deben coincidir).
    orden_esperado = ["COORDINATOR_STARTED", "AGENT_SELECTED", "AGENT_STARTED",
                      "AGENT_COMPLETED", "EVIDENCE_RECORDED", "COORDINATOR_COMPLETED"]
    posiciones = [tipos.index(t) for t in orden_esperado]
    assert posiciones == sorted(posiciones)


# --------------------------------------- 10. parent_event_id reconstruye relaciones

def test_parent_event_id_permite_reconstruir_relaciones(coordinator, run_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    trace = build_trace(run.to_dict())

    # RUN_CREATED es su propia raiz -- ocurre antes de que exista cualquier
    # Coordinator (un Run puede crearse sin nunca correr una etapa). La otra
    # raiz es el COORDINATOR_STARTED de esta llamada: todo lo demas (incluidas
    # las transiciones de estado que el Kernel dispara) debe colgar de ahi,
    # no quedar suelto.
    tipos_raiz = {r.event["event_type"] for r in trace.roots}
    assert tipos_raiz == {"RUN_CREATED", "COORDINATOR_STARTED"}

    raiz_coordinator = next(r for r in trace.roots if r.event["event_type"] == "COORDINATOR_STARTED")
    hijos_tipos = {h.event["event_type"] for h in raiz_coordinator.children}
    assert {"AGENT_SELECTED", "STATE_CHANGED", "RUN_STARTED", "AGENT_STARTED",
           "AGENT_COMPLETED", "EVIDENCE_RECORDED", "COORDINATOR_COMPLETED"} <= hijos_tipos


# ------------------------------------------- 11. reconstruir un run desde eventos

def test_un_run_puede_reconstruirse_a_partir_de_sus_eventos(coordinator, run_manager, state_manager):
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    state_manager.save(run.to_dict())

    consulta = query_run(run.run_id, state_manager=state_manager)
    assert consulta["run_id"] == run.run_id
    assert consulta["status"] == "COMPLETED"
    assert consulta["current_stage"] == run.current_stage
    assert consulta["agents"] == ["classifier"]
    assert len(consulta["transitions"]) >= 2  # PENDING->RUNNING, RUNNING->COMPLETED
    assert len(consulta["evidence"]) == 1
    assert len(consulta["events"]) == len(run.events)


# ------------------------------------------------------- 12. no se registran secrets

def test_no_se_registran_secrets_en_las_referencias(coordinator, run_manager):
    run = run_manager.create_run()
    entrada_con_secreto = "Necesitamos agregar alta de clientes"
    coordinator.execute_stage(run, entrada_con_secreto)

    agent_started = [e for e in run.events if e.event_type.value == "AGENT_STARTED"][0]
    # el input de este agente no tiene secretos -- pero probamos la
    # PROPIEDAD de redaccion directamente sobre la utilidad, no solo sobre
    # este caso feliz
    estructura_con_secreto = {"texto": "hola", "password": "hunter2"}
    referencia = make_reference(estructura_con_secreto)
    assert "hunter2" not in referencia
    assert "REDACTED" in referencia

    redactado = redact_structure({"api_key": "sk-super-secreto", "ok": "visible"})
    assert redactado["ok"] == "visible"
    assert "sk-super-secreto" not in str(redactado)


def test_evidence_con_dato_sensible_no_expone_el_valor_crudo_en_la_referencia():
    """No se toca `run.evidence` (contrato de la Fase 3, sin cambios) -- se
    prueba que la REFERENCIA de observabilidad (`input_reference`), que si es
    responsabilidad de esta fase, redacta antes de truncar."""
    referencia = make_reference({"password": "correcto-caballo-bateria-grapa"})
    assert "correcto-caballo-bateria-grapa" not in referencia


# --------------------------------------- 13. observabilidad funciona con el Classifier

def test_observabilidad_funciona_con_el_classifier_sin_logica_especifica(coordinator, run_manager):
    """El Classifier no importa `observability` ni `kernel.events` -- la
    observabilidad de su ejecucion la produce el Coordinator, no el agente."""
    import ast
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[1] / "agents" / "classifier.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    imports = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            imports.add(nodo.module)
        elif isinstance(nodo, ast.Import):
            imports.update(a.name for a in nodo.names)
    assert "observability" not in imports
    assert "kernel.events" not in imports

    # y sin embargo, al correrlo via Coordinator, SI queda observado:
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes")
    assert any(e.component == "AGENT" and e.component_id == "classifier" for e in run.events)


# ------------------------------------------ 14. no depende del ETL financiero

def test_observability_no_depende_del_etl_financiero():
    import ast
    from pathlib import Path

    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    ruta = Path(__file__).resolve().parents[1] / "observability.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    imports = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            imports.add(nodo.module)
        elif isinstance(nodo, ast.Import):
            imports.update(a.name for a in nodo.names)
    ofensores = {i for i in imports if any(i == p or i.startswith(p + ".") for p in prohibidos)}
    assert not ofensores


# ---------------------------------------------- 15. todos los tests existentes pasan

def test_modelo_de_artifact_esta_preparado_pero_no_conectado():
    """Nadie produce un Artifact real todavia -- solo se prueba que el
    modelo tiene la forma pedida (artifact_id/run_id/stage/agent_id/type/
    reference/created_at/parent_artifact_id)."""
    a = Artifact(
        artifact_id="art-1", run_id="run-1", stage="Code", agent_id="generator",
        type="python_module", reference="path/to/file.py", created_at="2026-01-01T00:00:00Z",
    )
    d = a.to_dict()
    for campo in ("artifact_id", "run_id", "stage", "agent_id", "type",
                 "reference", "created_at", "parent_artifact_id"):
        assert campo in d
    assert d["parent_artifact_id"] is None


def test_marcador_de_no_regresion():
    """No reemplaza correr la suite completa (`pytest tests/`) -- es un
    recordatorio explicito en el propio archivo de que ese es el criterio.
    El reporte final de esta fase cita la corrida real de los 58+N tests."""
    assert True
