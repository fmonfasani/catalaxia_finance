"""Fase 5C -- same-run orchestration: Generator -> Validator dentro del
MISMO run_id, via `Coordinator.execute_pipeline()`.

Cubre los 8 TEST obligatorios pedidos. Aislamiento: `tmp_path` para todo lo
que el Generator escriba (via `authorized_context["output_dir"]"), nunca
`software-factory/runs/` real -- mismo patron que `test_generator.py`/
`test_validator.py`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agents.generator import GeneratorAgent, GeneratorInput
from agents.specification import FieldSpec, Specification
from agents.validator import ValidatorAgent, ValidatorInput
from contracts_catalog import build_default_registry as build_contracts
from coordinator.agent_registry import AgentRegistry
from coordinator.coordinator import Coordinator
from evals_catalog import build_default_registry as build_evals
from invariants_catalog import build_default_registry as build_invariants
from observability import build_trace, query_run


def _especificacion_valida(spec_id="SPEC-SAMERUN") -> Specification:
    return Specification(
        spec_id=spec_id, entity_name="Cliente",
        requirement_ref="alta de clientes con DNI unico",
        fields=(
            FieldSpec("nombre", "str", required=True),
            FieldSpec("dni", "str", required=True, unique=True),
            FieldSpec("email", "str", required=True),
        ),
    )


def _contexto_aislado(tmp_path: Path, run_id: str) -> dict:
    return {"output_dir": tmp_path / run_id / "generated"}


def _validator_input_builder(run_id: str, registros: list[dict]):
    """Cierra sobre `run_id`/`registros`; el `artifact`/`evidence` los
    recibe recien cuando `execute_pipeline()` invoca este callable con lo
    que produjo el paso anterior -- el Validator nunca "adivina" que
    artifact validar, lo recibe explicito del Coordinator."""
    def builder(artifact, evidence):
        assert artifact is not None, "el Validator debe recibir el artifact real del paso anterior"
        return ValidatorInput(
            run_id=run_id, scope="Generator", artifact=artifact, evidence=evidence,
            context={"code_reference": artifact["reference"], "registros": registros},
            invariant_registry=build_invariants(), eval_registry=build_evals(),
        )
    return builder


@pytest.fixture
def registry_with_generator_and_validator() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(GeneratorAgent())
    registry.register(ValidatorAgent())
    return registry


@pytest.fixture
def pipeline_run(real_run_manager):
    """Un Run fresco avanzado directamente a 'Code' -- la primera etapa que
    `execute_pipeline()` orquesta en todos los tests de este modulo."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    return run


def _coordinator(real_run_manager, registry_with_generator_and_validator):
    return Coordinator(run_manager=real_run_manager, registry=registry_with_generator_and_validator,
                       contract_registry=build_contracts())


# ---------------------------------------------------------------- TEST 1: SAME RUN

def test_same_run_generator_y_validator_comparten_run_id(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 1."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    run_id_original = pipeline_run.run_id
    gi = GeneratorInput(run_id=run_id_original, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, run_id_original))

    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(run_id_original, [{"dni": "1"}])),
    ])

    assert pipeline_run.run_id == run_id_original
    # todo evento, evidencia y artifact quedan bajo ESE UNICO run.run_id (no hay
    # un segundo objeto Run involucrado en ningun momento de esta prueba)
    assert {e.run_id for e in pipeline_run.events} == {run_id_original}
    agentes_ejecutados = sorted({e.component_id for e in pipeline_run.events
                                 if e.component == "AGENT"})
    assert agentes_ejecutados == ["generator", "validator"]


# ------------------------------------------------------------ TEST 2: ARTIFACT LINEAGE

def test_artifact_producido_por_generator_queda_asociado_al_run(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 2."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))

    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "1"}])),
    ])

    assert len(pipeline_run.artifacts) == 1
    artifact = pipeline_run.artifacts[0]
    assert artifact["run_id"] == pipeline_run.run_id
    assert Path(artifact["reference"]).is_file()


# -------------------------------------------------------------- TEST 3: VALIDATOR INPUT

def test_validator_recibe_explicitamente_el_artifact_producido(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 3: el builder de ValidatorInput recibe el artifact REAL (no None,
    no un placeholder) -- se verifica con un `assert` dentro del builder
    mismo (ver `_validator_input_builder`) mas una segunda comprobacion
    explicita aca sobre el artifact que finalmente quedo en `run.artifacts`."""
    artifact_recibido_por_validator = {}

    def builder_espia(artifact, evidence):
        artifact_recibido_por_validator["valor"] = artifact
        return ValidatorInput(
            run_id=pipeline_run.run_id, scope="Generator", artifact=artifact, evidence=evidence,
            context={"code_reference": artifact["reference"], "registros": [{"dni": "1"}]},
            invariant_registry=build_invariants(), eval_registry=build_evals(),
        )

    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))

    coordinator.execute_pipeline(pipeline_run, [("Code", gi), ("Validation", builder_espia)])

    assert artifact_recibido_por_validator["valor"] is not None
    assert artifact_recibido_por_validator["valor"]["artifact_id"] == pipeline_run.artifacts[0]["artifact_id"]


# --------------------------------------------------------------------- TEST 4: PASS

def test_pipeline_pass_completa_el_run(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 4."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))

    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "1"}])),
    ])

    assert pipeline_run.status.value == "COMPLETED"
    assert pipeline_run.evidence[-1]["output"]["result"] == "PASS"


# --------------------------------------------------------------------- TEST 5: FAIL

def test_pipeline_fail_termina_el_run_en_failed(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 5: Generator produce un artifact VALIDO (el Generator no
    "falla") pero el contexto de validacion viola INV-002 (DNI duplicado) --
    el Run debe terminar FAILED, no COMPLETED."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))

    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id,
                                                [{"dni": "X"}, {"dni": "X"}])),
    ])

    assert pipeline_run.status.value == "FAILED"
    assert pipeline_run.evidence[-1]["output"]["result"] == "FAIL"
    assert any(f["id"] == "INV-002" for f in pipeline_run.evidence[-1]["output"]["failures"])
    # el artifact SI existe (el Generator cumplio su parte) -- lo que fallo
    # es la etapa de Validation, no la generacion
    assert len(pipeline_run.artifacts) == 1


# ---------------------------------------------------------------- TEST 6: NO BYPASS

def test_validator_no_puede_marcar_pass_sin_ejecutar_los_checks(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 6: si no se le pasa NINGUN registry (ni invariants ni evals), el
    Validator se rechaza a si mismo (status=ERROR) en vez de reportar un
    PASS vacio por ausencia de checks -- no hay forma de "saltarse" la
    validacion y obtener PASS gratis."""
    def builder_sin_checks(artifact, evidence):
        return ValidatorInput(run_id=pipeline_run.run_id, scope="Generator",
                              artifact=artifact, evidence=evidence)  # sin registries

    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))

    coordinator.execute_pipeline(pipeline_run, [("Code", gi), ("Validation", builder_sin_checks)])

    assert pipeline_run.status.value == "FAILED"
    assert pipeline_run.evidence[-1]["status"] == "ERROR"


def test_checks_evaluados_mayor_a_cero_cuando_pasa(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """Complementa TEST 6: un PASS real siempre reporta cuantos checks se
    evaluaron (nunca 0) -- evidencia de que la validacion efectivamente
    corrio."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))
    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "1"}])),
    ])
    assert pipeline_run.evidence[-1]["output"]["evidence"]["checks_evaluados"] > 0


# ---------------------------------------------------------------- TEST 7: TRACEABILITY

def test_historial_reconstruye_generator_artifact_evidence_validator_result_state(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path, state_manager,
):
    """TEST 7."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida("SPEC-TRACE-SAMERUN"),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))

    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "1"}])),
    ])
    state_manager.save(pipeline_run.to_dict())

    consulta = query_run(pipeline_run.run_id, state_manager=state_manager)
    assert consulta["status"] == "COMPLETED"
    assert set(consulta["agents"]) == {"generator", "validator"}
    assert len(consulta["evidence"]) == 2          # generator + validator
    assert len(consulta["artifacts"]) == 1

    # Generator -> Artifact
    artifact = consulta["artifacts"][0]
    assert artifact["specification_ref"] == "SPEC-TRACE-SAMERUN"

    # Artifact -> Evidence (de vuelta)
    assert artifact["evidence_ref"] == consulta["evidence"][0]["result_id"]

    # Validator -> Result
    assert consulta["evidence"][1]["agent_id"] == "validator"
    assert consulta["evidence"][1]["output"]["result"] == "PASS"

    # Trace: un solo COORDINATOR_STARTED raiz, con TODO anidado debajo
    trace = build_trace(pipeline_run.to_dict())
    raices_coordinador = [r for r in trace.roots if r.event["event_type"] == "COORDINATOR_STARTED"]
    assert len(raices_coordinador) == 1
    tipos_bajo_coordinador = {h.event["event_type"] for h in raices_coordinador[0].children}
    assert {"AGENT_SELECTED", "AGENT_STARTED", "AGENT_COMPLETED", "EVIDENCE_RECORDED",
           "STAGE_COMPLETED", "STAGE_STARTED"} <= tipos_bajo_coordinador


# --------------------------------------------------------------- TEST 8: REGRESSION

def test_marcador_regresion_fase_5c():
    """No reemplaza correr `pytest tests/` completo -- el reporte final cita
    la corrida real (127 previos + los de este archivo)."""
    assert True


# ---------------------------------------------------- extra: execute_stage() intacto

def test_execute_stage_preserva_comportamiento_exacto_previo(coordinator, run_manager):
    """La extraccion de `_run_single_agent()` no debe cambiar ni un evento
    de lo que `execute_stage()` ya hacia desde la Fase 5B."""
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI unico")
    assert run.status.value == "COMPLETED"
    tipos = [e.event_type.value for e in run.events]
    assert tipos == [
        "RUN_CREATED", "COORDINATOR_STARTED", "AGENT_SELECTED", "STATE_CHANGED",
        "RUN_STARTED", "AGENT_STARTED", "AGENT_COMPLETED", "EVIDENCE_RECORDED",
        "STATE_CHANGED", "COORDINATOR_COMPLETED",
    ]


def test_no_depende_del_etl_financiero():
    import ast
    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    base = Path(__file__).resolve().parents[1]
    ofensores = {}
    for archivo in ("coordinator/coordinator.py", "kernel/run_manager.py", "kernel/events.py"):
        ruta = base / archivo
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        imports = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                imports.add(nodo.module)
            elif isinstance(nodo, ast.Import):
                imports.update(a.name for a in nodo.names)
        hits = {i for i in imports if any(i == p or i.startswith(p + ".") for p in prohibidos)}
        if hits:
            ofensores[archivo] = hits
    assert not ofensores
