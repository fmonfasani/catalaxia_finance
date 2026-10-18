"""Fase 5D -- hardening de FINDING-02 (Validator Verdict Trust) y FINDING-04
(Eval Exception), sobre INDEPENDENT-VERIFICATION-5C.md.

FINDING-01 (path traversal) tiene su propio archivo:
`tests/test_identifiers.py`.

Aislamiento: `tmp_path` para todo lo que el Generator escriba -- nunca
`software-factory/runs/` real.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent
from agents.generator import GeneratorAgent, GeneratorInput
from agents.specification import FieldSpec, Specification
from agents.validator import ValidatorAgent, ValidatorInput
from contracts_catalog import build_default_registry as build_contracts
from coordinator.agent_registry import AgentRegistry
from coordinator.coordinator import Coordinator
from evals_catalog import build_default_registry as build_evals
from invariants_catalog import build_default_registry as build_invariants
from kernel.run_scope import RunScope

# DEC-SF-001: alcance declarado de los Runs de este modulo (subconjunto
# legitimo de las 12 etapas de FACTORY-SPEC.md Seccion 7).
SCOPE_HARDENING = RunScope(
    scope_id="SCOPE-HARDENING-5D",
    scope_version="1.0.0",
    required_stages=("Code", "Validation"),
    required_evidence_agents=("generator", "validator"),
)


def _especificacion_valida(spec_id="SPEC-HARDENING", entity_name="Cliente") -> Specification:
    return Specification(
        spec_id=spec_id, entity_name=entity_name,
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
    def builder(artifact, evidence):
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
    # DEC-SF-001: el Run declara su alcance (Code+Validation). Sin contrato
    # declarado, `execute_pipeline()` ya no puede transicionar a COMPLETED.
    run = real_run_manager.create_run(scope=SCOPE_HARDENING)
    real_run_manager.advance_stage(run, "Code")
    return run


def _coordinator(real_run_manager, registry):
    return Coordinator(run_manager=real_run_manager, registry=registry,
                       contract_registry=build_contracts())


# ============================================================ FINDING-02

class _RogueRoleGenerator(BaseAgent):
    """Un agente CON role=GENERATOR (rol real, no VALIDATOR) que intenta
    forjar un veredicto de validacion en su output -- el caso que
    FINDING-02 exige que ya no funcione: 'El Generator NO debe poder
    producir un resultado terminal de validacion.'"""
    metadata = AgentMetadata(
        id="generator", name="RogueGen", role=AgentRole.GENERATOR,
        input_contract="cualquiera", output_contract="cualquiera",
    )

    def __init__(self, veredicto_forjado: str):
        self._veredicto = veredicto_forjado

    def execute(self, input_data):
        return AgentResult(
            agent_id="generator", input=input_data,
            output={"result": self._veredicto, "violations": [], "evidence": {"forjado": True}},
            status="OK",
        )


# ------------------------------------------- TEST 1: Validator real -> PASS -> COMPLETED

def test_validator_real_pass_completa_el_run(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
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


# -------------------------------------------- TEST 2: Validator real -> FAIL -> FAILED

def test_validator_real_fail_termina_en_failed(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))
    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "X"}, {"dni": "X"}])),
    ])
    assert pipeline_run.status.value == "FAILED"
    assert pipeline_run.evidence[-1]["output"]["result"] == "FAIL"


# ---------------------- TEST 3: agent no-Validator que intenta producir PASS no completa

def test_agente_no_validator_no_puede_forzar_pass(real_run_manager):
    """Un Generator (role=GENERATOR) que devuelve output['result']='PASS'
    NO debe hacer que ese 'PASS' sea tratado como veredicto -- su exito
    depende SOLO de AgentResult.status, exactamente como antes de la Fase
    5B. Se prueba con status='OK' (el resultado debe seguir siendo
    aceptado, pero NO por el veredicto forjado sino por status)."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    registry = AgentRegistry()
    registry.register(_RogueRoleGenerator("PASS"))
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry)

    coordinator.execute_stage(run, "cualquier input")
    # Con status=OK, avanza igual (por status, no por el "PASS" forjado) --
    # lo que importa es que un "FAIL" forjado por un no-Validator TAMPOCO
    # bloquee (ver siguiente test): la forma del output ya no tiene ningun
    # efecto sobre el veredicto para este rol.
    assert run.status.value == "COMPLETED"


def test_agente_no_validator_no_puede_forzar_fail_de_validacion(real_run_manager):
    """Complementa TEST 3: un Generator (role=GENERATOR) que devuelve
    output['result']='FAIL' con status='OK' NO logra bloquear el Run --
    antes de esta correccion, cualquier agente con esa forma de output
    hubiera causado FAILED. Ahora solo un role=VALIDATOR puede hacerlo."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    registry = AgentRegistry()
    registry.register(_RogueRoleGenerator("FAIL"))
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry)

    coordinator.execute_stage(run, "cualquier input")
    assert run.status.value == "COMPLETED"
    assert run.evidence[-1]["output"]["result"] == "FAIL"  # el dato queda, pero no domina el veredicto


# --------------------------------- TEST 4: resultado malformado sigue rechazado por Contract

def test_resultado_malformado_sigue_siendo_rechazado_por_contract(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """El fix de FINDING-02 no reemplaza a Contracts (Fase 5A) -- un output
    de Generator sin `code_reference` sigue siendo rechazado por
    GENERATOR_OUTPUT, sin relacion con el rol."""
    class _GeneratorRoto(GeneratorAgent):
        def execute(self, input_data):
            return AgentResult(agent_id=self.metadata.id, input=input_data,
                               output={"artifact": {"artifact_id": "ART-ROTO"}},  # sin code_reference
                               status="OK")

    registry = AgentRegistry()
    registry.register(_GeneratorRoto())
    coordinator = _coordinator(real_run_manager, registry)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="algo",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))
    coordinator.execute_stage(pipeline_run, gi)

    assert pipeline_run.status.value == "FAILED"
    assert pipeline_run.evidence[-1]["output"]["error"] == "contract_violation"


# --------------------------- TEST 5: Coordinator no puede fabricar el veredicto unilateralmente

def test_coordinator_no_fabrica_veredictos_sin_relacion_al_rol():
    """Verificacion estatica: el Coordinator lee `output.get("result")`
    (una LECTURA), nunca asigna un literal "PASS"/"FAIL" el mismo -- y esa
    lectura ahora esta condicionada a `agent.metadata.role is
    AgentRole.VALIDATOR`. Se confirma por AST que no hay ningun string
    literal "PASS"/"FAIL" asignado a una variable de veredicto en
    coordinator.py (evita que una futura edicion reintroduzca una
    fabricacion silenciosa)."""
    import ast
    ruta = Path(__file__).resolve().parents[1] / "coordinator" / "coordinator.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    asignaciones_forjadas = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign):
            if isinstance(nodo.value, ast.Constant) and nodo.value.value in ("PASS", "FAIL"):
                asignaciones_forjadas.append(nodo)
    assert not asignaciones_forjadas, "coordinator.py no debe asignar literales PASS/FAIL a mano"

    # y la condicion de rol esta presente literalmente en el archivo
    texto = ruta.read_text(encoding="utf-8")
    assert "AgentRole.VALIDATOR" in texto


# ============================================================ FINDING-04

def test_eval_pass_comportamiento_normal(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 1 (Fase 5D, Finding Eval Exception): Eval PASS -> comportamiento
    normal, sin cambios."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))
    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "1"}])),
    ])
    assert pipeline_run.status.value == "COMPLETED"
    assert any(c["id"] == "EVAL-001" and c["status"] == "PASS"
              for c in pipeline_run.evidence[-1]["output"]["checks"])


def test_eval_fail_termina_failed(
    pipeline_run, real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 2: Eval FAIL -> FAILED (comportamiento ya cubierto en
    test_validator.py, repetido aca como parte del set de Fase 5D)."""
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=pipeline_run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, pipeline_run.run_id))
    coordinator.execute_pipeline(pipeline_run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(pipeline_run.run_id, [{"dni": "X"}, {"dni": "X"}])),
    ])
    assert pipeline_run.status.value == "FAILED"


def test_eval_exception_comportamiento_controlado(
    real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 3: reproduce exactamente el escenario del reporte (entity_name
    distinto de "Cliente" -> EVAL-001 levanta AttributeError al buscar
    "AltaClientes" en el modulo generado) -- debe terminar en un estado
    terminal seguro (FAILED), nunca RUNNING indefinido."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=run.run_id, requirement="algo",
                        specification=_especificacion_valida(entity_name="TallerX"),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))

    coordinator.execute_pipeline(run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status.value in ("FAILED", "COMPLETED"), \
        f"el Run debe llegar a un estado TERMINAL, nunca quedar en RUNNING; quedo en {run.status.value}"
    assert run.status.value == "FAILED"
    assert run.evidence[-1]["status"] == "ERROR"
    assert run.evidence[-1]["output"]["error"] == "validation_exception"
    tipos = [e.event_type.value for e in run.events]
    assert "AGENT_FAILED" in tipos
    assert tipos[-1] == "COORDINATOR_COMPLETED"


def test_eval_exception_no_deja_el_run_en_running():
    """Complemento explicito del TEST 3: aisla la llamada directa al
    ValidatorAgent (sin Coordinator de por medio) para confirmar que la
    excepcion se captura DENTRO del Agent -- no depende de que el
    Coordinator la atrape."""
    def eval_que_explota(input_, expected, context):
        raise AttributeError("simulando el AttributeError real del reporte")

    from evals import Eval, EvalRegistry
    registry = EvalRegistry()
    registry.register(Eval(
        eval_id="EVAL-BOOM", version="1.0", name="explota", description="test",
        input=None, expected=None, evaluation_method=eval_que_explota, scope="Generator",
    ))

    agente = ValidatorAgent()
    resultado = agente.execute(ValidatorInput(
        run_id="r1", scope="Generator", artifact={"artifact_id": "ART-X"}, evidence=None,
        eval_registry=registry,
    ))
    assert resultado.status == "ERROR"
    assert resultado.output["error"] == "validation_exception"
    assert "AttributeError" in resultado.output["detail"] or "simulando" in resultado.output["detail"]


def test_estado_persistido_consistente_tras_eval_exception(
    real_run_manager, registry_with_generator_and_validator, tmp_path, state_manager,
):
    """TEST 4: el estado persistido (JSON) es consistente -- se puede
    guardar/cargar sin errores, y la evidencia de la excepcion sobrevive."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=run.run_id, requirement="algo",
                        specification=_especificacion_valida(entity_name="OtraEntidad"),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))
    coordinator.execute_pipeline(run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(run.run_id, [{"dni": "1"}])),
    ])
    state_manager.save(run.to_dict())

    cargado = state_manager.load(run.run_id)
    assert cargado["status"] == "FAILED"
    assert cargado["evidence"][-1]["output"]["error"] == "validation_exception"


def test_no_puede_terminar_completed_por_una_excepcion(
    real_run_manager, registry_with_generator_and_validator, tmp_path,
):
    """TEST 5: una excepcion de Eval jamas produce COMPLETED -- ninguna
    falsa apariencia de exito."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    coordinator = _coordinator(real_run_manager, registry_with_generator_and_validator)
    gi = GeneratorInput(run_id=run.run_id, requirement="algo",
                        specification=_especificacion_valida(entity_name="EntidadRota"),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))
    coordinator.execute_pipeline(run, [
        ("Code", gi),
        ("Validation", _validator_input_builder(run.run_id, [{"dni": "1"}])),
    ])
    assert run.status.value != "COMPLETED"


# ================================================================= regresion

def test_no_depende_del_etl_financiero():
    import ast
    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    base = Path(__file__).resolve().parents[1]
    ofensores = {}
    for archivo in ("coordinator/coordinator.py", "agents/validator.py", "kernel/identifiers.py"):
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
