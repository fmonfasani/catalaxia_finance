"""Invariants + Evals + Validator: modelo, registries, agente real, e
integracion con el Coordinator/Kernel para bloquear el avance de un Run
cuando la validacion es FAIL.

Cubre los 17 puntos pedidos en la Fase 5B. Sigue el mismo patron de
aislamiento que `tests/test_generator.py`/`tests/test_contracts.py`:
`tmp_path` para todo lo que el Generator escriba, nunca `software-factory/
runs/` real.

Diseno de las pruebas de circuito completo (documentado, mismo criterio que
GENERATOR.md): el Generator corre en un Run (etapa "Code"); el Validator
corre en OTRO Run, fresco, avanzado directamente a "Validation", recibiendo
como input el artifact/evidence que produjo el primer Run. La StateMachine
actual no permite COMPLETED->RUNNING sobre el mismo Run (misma brecha que
GENERATOR.md ya documento en Fase 4B) -- encadenar dos etapas reales sobre
un unico Run sigue siendo trabajo de una fase futura, no de esta.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_contract import AgentResult
from agents.generator import GeneratorAgent, GeneratorInput
from agents.specification import FieldSpec, Specification
from agents.validator import ValidationResult, ValidatorAgent, ValidatorInput
from contracts_catalog import build_default_registry as build_contracts
from coordinator.agent_registry import AgentRegistry
from coordinator.coordinator import Coordinator
from evals import Eval, EvalCheckResult, EvalRegistry
from evals_catalog import build_default_registry as build_evals
from invariants import Invariant, InvariantCheckResult, InvariantRegistry, Severity
from invariants_catalog import build_default_registry as build_invariants
from observability import build_trace, query_run


def _especificacion_valida(spec_id="SPEC-VAL-001") -> Specification:
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


@pytest.fixture
def generator_artifact(real_run_manager, tmp_path):
    """Corre el Generator real (Run A, etapa Code) y devuelve
    (artifact, evidence, run) -- el insumo que las pruebas de Validator usan
    como si vinieran de una ejecucion previa real."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    registry = AgentRegistry()
    registry.register(GeneratorAgent())
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry,
                              contract_registry=build_contracts())
    gi = GeneratorInput(run_id=run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))
    coordinator.execute_stage(run, gi)
    assert run.status.value == "COMPLETED"
    return run.artifacts[-1], run.evidence[-1], run


@pytest.fixture
def validation_run(real_run_manager):
    """Un Run fresco avanzado directamente a 'Validation' -- ver docstring
    del modulo."""
    real_run_manager_2 = real_run_manager
    run = real_run_manager_2.create_run()
    real_run_manager_2.advance_stage(run, "Validation")
    return run


@pytest.fixture
def registry_with_validator() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(ValidatorAgent())
    return registry


# ------------------------------------------------------- 1/2. registrar/ejecutar Invariant

def test_registrar_y_ejecutar_invariant():
    """TEST 1, TEST 2."""
    registry = InvariantRegistry()
    inv = Invariant(
        invariant_id="INV-TEST", version="1.0", name="siempre pasa",
        description="dummy", severity=Severity.WARNING, scope="Dummy",
        check=lambda ctx: InvariantCheckResult("INV-TEST", passed=True),
    )
    registry.register(inv)
    assert registry.is_registered("INV-TEST")
    resultados = registry.evaluate_all("Dummy", {})
    assert len(resultados) == 1
    assert resultados[0].passed is True


# --------------------------------------------------------- 3. detectar violation

def test_invariant_detecta_violation():
    """TEST 3."""
    registry = build_invariants()
    resultados = registry.evaluate_all("Generator", {
        "artifact": None,
        "registros": [{"dni": "1"}, {"dni": "1"}],
    })
    fallos = [r for r in resultados if not r.passed]
    assert any(r.invariant_id == "INV-002" for r in fallos)


# ------------------------------------------------------------ 4/5. registrar/ejecutar Eval

def test_registrar_y_ejecutar_eval():
    """TEST 4, TEST 5."""
    registry = EvalRegistry()
    ev = Eval(
        eval_id="EVAL-TEST", version="1.0", name="siempre pasa", description="dummy",
        input=None, expected=None,
        evaluation_method=lambda i, e, ctx: EvalCheckResult("EVAL-TEST", passed=True),
        scope="Dummy",
    )
    registry.register(ev)
    assert registry.is_registered("EVAL-TEST")
    resultados = registry.run_all("Dummy", {})
    assert len(resultados) == 1 and resultados[0].passed


# ---------------------------------------------------------------- 6. Eval failure

def test_eval_detecta_failure_de_comportamiento(tmp_path):
    """TEST 6: el Eval real (EVAL-001) ejecuta el modulo generado y detecta
    que el comportamiento NO coincide con lo esperado (se le pasa un
    code_reference cuyo modulo generado no rechaza duplicados -- simulado
    con un archivo que no expone la clase esperada)."""
    modulo_falso = tmp_path / "roto.py"
    modulo_falso.write_text("class AltaClientes:\n    def alta(self, **kw):\n        return kw\n",
                            encoding="utf-8")
    registry = build_evals()
    resultados = registry.run_all("Generator", {"code_reference": str(modulo_falso)})
    assert len(resultados) == 1
    assert resultados[0].passed is False


# ----------------------------------------------------------- 7/8. Validator PASS/FAIL

def test_validator_pass(generator_artifact):
    """TEST 7."""
    artifact, evidence, _ = generator_artifact
    agente = ValidatorAgent()
    vi = ValidatorInput(
        run_id="r-val-pass", scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"], "registros": [{"dni": "1"}]},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    resultado = agente.execute(vi)
    assert resultado.status == "OK"
    assert resultado.output["result"] == "PASS"
    assert resultado.output["failures"] == []


def test_validator_fail(generator_artifact):
    """TEST 8."""
    artifact, evidence, _ = generator_artifact
    agente = ValidatorAgent()
    vi = ValidatorInput(
        run_id="r-val-fail", scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"],
                "registros": [{"dni": "X"}, {"dni": "X"}]},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    resultado = agente.execute(vi)
    assert resultado.status == "OK"  # el Agent se ejecuto bien -- el VEREDICTO es FAIL
    assert resultado.output["result"] == "FAIL"
    assert any(f["id"] == "INV-002" for f in resultado.output["failures"])


# -------------------------------------------------------- 9. ValidationResult con evidence

def test_validation_result_contiene_evidence(generator_artifact):
    """TEST 9."""
    artifact, evidence, _ = generator_artifact
    resultado = ValidationResult(status="PASS", checks=[{"id": "X", "status": "PASS"}],
                                 evidence={"run_id": "r1", "artifact_id": artifact["artifact_id"]})
    d = resultado.to_dict()
    assert d["evidence"]["artifact_id"] == artifact["artifact_id"]


# ----------------------------------------------- 10. Validator no modifica el artifact

def test_validator_no_modifica_el_artifact(generator_artifact):
    """TEST 10."""
    artifact, evidence, _ = generator_artifact
    copia_original = dict(artifact)
    agente = ValidatorAgent()
    vi = ValidatorInput(
        run_id="r-no-mod", scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"], "registros": []},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    agente.execute(vi)
    assert artifact == copia_original


def test_validator_no_modifica_el_archivo_generado(generator_artifact):
    """Complementa TEST 10 desde el filesystem: el contenido del modulo
    generado no cambia despues de validar."""
    artifact, evidence, _ = generator_artifact
    contenido_antes = Path(artifact["reference"]).read_text(encoding="utf-8")
    agente = ValidatorAgent()
    vi = ValidatorInput(
        run_id="r-no-mod-fs", scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"], "registros": []},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    agente.execute(vi)
    assert Path(artifact["reference"]).read_text(encoding="utf-8") == contenido_antes


# --------------------------------------------- 11. Validator no modifica State directamente

def test_validator_no_modifica_state_directamente():
    """TEST 11: `agents/validator.py` no importa kernel.run_manager,
    kernel.state_machine ni coordinator.coordinator -- verificado por AST,
    no solo por convencion (mismo patron que test_generator.py)."""
    import ast
    ruta = Path(__file__).resolve().parents[1] / "agents" / "validator.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    imports = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            imports.add(nodo.module)
        elif isinstance(nodo, ast.Import):
            imports.update(a.name for a in nodo.names)
    prohibidos = {"kernel.run_manager", "kernel.state_machine", "coordinator.coordinator"}
    assert not (imports & prohibidos)


# ------------------------------------------ 12/13. Kernel impide/permite avanzar

def test_kernel_impide_avanzar_cuando_validator_fail(
    validation_run, registry_with_validator, real_run_manager, generator_artifact,
):
    """TEST 12 -- CASO B: FAIL debe bloquear el avance (Run cae a FAILED, no
    COMPLETED), dejando evento/evidencia/motivo."""
    artifact, evidence, _ = generator_artifact
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_validator,
                              contract_registry=build_contracts())
    vi = ValidatorInput(
        run_id=validation_run.run_id, scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"],
                "registros": [{"dni": "Y"}, {"dni": "Y"}]},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    coordinator.execute_stage(validation_run, vi)

    assert validation_run.status.value == "FAILED"
    tipos = {e.event_type.value for e in validation_run.events}
    assert "AGENT_FAILED" in tipos
    assert "AGENT_COMPLETED" not in tipos
    assert validation_run.evidence[-1]["output"]["result"] == "FAIL"
    assert validation_run.evidence[-1]["output"]["failures"]


def test_kernel_permite_avanzar_cuando_validator_pass(
    validation_run, registry_with_validator, real_run_manager, generator_artifact,
):
    """TEST 13 -- CASO A: PASS debe permitir el avance (Run llega a
    COMPLETED)."""
    artifact, evidence, _ = generator_artifact
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_validator,
                              contract_registry=build_contracts())
    vi = ValidatorInput(
        run_id=validation_run.run_id, scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"], "registros": [{"dni": "Z"}]},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    coordinator.execute_stage(validation_run, vi)

    assert validation_run.status.value == "COMPLETED"
    assert validation_run.evidence[-1]["output"]["result"] == "PASS"


# ------------------------------------------------ 14. eventos de validacion registrados

def test_eventos_de_validacion_quedan_registrados(
    validation_run, registry_with_validator, real_run_manager, generator_artifact,
):
    """TEST 14."""
    artifact, evidence, _ = generator_artifact
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_validator,
                              contract_registry=build_contracts())
    vi = ValidatorInput(
        run_id=validation_run.run_id, scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"], "registros": []},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    coordinator.execute_stage(validation_run, vi)
    tipos = [e.event_type.value for e in validation_run.events]
    assert "AGENT_SELECTED" in tipos
    assert "AGENT_STARTED" in tipos
    assert "EVIDENCE_RECORDED" in tipos
    validador_events = [e for e in validation_run.events if e.component_id == "validator"]
    assert len(validador_events) >= 2  # al menos AGENT_STARTED + (AGENT_COMPLETED|AGENT_FAILED)


# ------------------------------------------ 15. reconstruible mediante observabilidad

def test_ejecucion_reconstruible_via_observabilidad(
    validation_run, registry_with_validator, real_run_manager, state_manager, generator_artifact,
):
    """TEST 15."""
    artifact, evidence, _ = generator_artifact
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_validator,
                              contract_registry=build_contracts())
    vi = ValidatorInput(
        run_id=validation_run.run_id, scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"],
                "registros": [{"dni": "W"}, {"dni": "W"}]},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    coordinator.execute_stage(validation_run, vi)
    state_manager.save(validation_run.to_dict())

    consulta = query_run(validation_run.run_id, state_manager=state_manager)
    assert consulta["status"] == "FAILED"
    assert "validator" in consulta["agents"]
    assert len(consulta["evidence"]) == 1

    trace = build_trace(validation_run.to_dict())
    raiz = next(r for r in trace.roots if r.event["event_type"] == "COORDINATOR_STARTED")
    tipos_hijos = {h.event["event_type"] for h in raiz.children}
    assert {"AGENT_SELECTED", "AGENT_STARTED", "AGENT_FAILED", "EVIDENCE_RECORDED"} <= tipos_hijos


# --------------------------------------------------------- 16. sin dependencia del ETL

def test_no_depende_del_etl_financiero():
    """TEST 16."""
    import ast
    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    base = Path(__file__).resolve().parents[1]
    ofensores = {}
    for archivo in ("invariants.py", "evals.py", "invariants_catalog.py",
                    "evals_catalog.py", "agents/validator.py"):
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


# --------------------------------------------------------- extra: contrato compatible

def test_validator_output_compatible_con_su_contrato(generator_artifact):
    """El output real del ValidatorAgent (no un mock) cumple
    VALIDATOR_OUTPUT (Fase 5A) -- extra de cobertura, complementa TEST 17."""
    from contracts_catalog import VALIDATOR_OUTPUT
    artifact, evidence, _ = generator_artifact
    agente = ValidatorAgent()
    vi = ValidatorInput(
        run_id="r-contract", scope="Generator", artifact=artifact, evidence=evidence,
        context={"code_reference": artifact["reference"], "registros": []},
        invariant_registry=build_invariants(), eval_registry=build_evals(),
    )
    resultado = agente.execute(vi)
    assert VALIDATOR_OUTPUT.validate_output(resultado.output) == []


def test_validator_sin_invariants_ni_evals_es_rechazado():
    agente = ValidatorAgent()
    vi = ValidatorInput(run_id="r1", scope="Generator", artifact=None, evidence=None)
    resultado = agente.execute(vi)
    assert resultado.status == "ERROR"


def test_coordinator_sin_veredicto_preserva_comportamiento_previo(coordinator, run_manager):
    """El mecanismo de veredicto (`output["result"]`) no interfiere con
    agentes que nunca devuelven esa forma (Classifier) -- mismo
    comportamiento que antes de esta fase."""
    run = run_manager.create_run()
    coordinator.execute_stage(run, "Necesitamos agregar alta de clientes con DNI unico")
    assert run.status.value == "COMPLETED"
