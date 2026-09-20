"""Contract Model: Schema, Contract, ContractRegistry, e integracion generica
con el Coordinator (validar el output de un Agent contra su Contract
declarado en `contracts_catalog.py`, sin ningun `if agent_id == "..."`).

Cubre los 13 puntos pedidos en la Fase 5A. Los tests que ejecutan el
Generator real usan `tmp_path` para el `output_dir` (mismo patron de
aislamiento que `tests/test_generator.py`) -- nunca escriben en el
`software-factory/runs/` real.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_contract import AgentResult
from agents.generator import GeneratorAgent, GeneratorInput
from agents.specification import FieldSpec, Specification
from contracts import (
    Contract, ContractNotFoundError, ContractRegistry, ContractViolationError,
    FieldRule, Schema,
)
from contracts_catalog import (
    ALL_CONTRACTS, CLASSIFIER_OUTPUT, GENERATOR_OUTPUT, build_default_registry,
)
from coordinator.agent_registry import AgentRegistry
from coordinator.coordinator import Coordinator


def _especificacion_valida(spec_id="SPEC-C-001") -> Specification:
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


# ------------------------------------------------------- 1. contrato valido

def test_contrato_valido_acepta_output_conforme():
    """TEST 1."""
    contrato = GENERATOR_OUTPUT
    problemas = contrato.validate_output({
        "artifact": {"artifact_id": "ART-1"}, "code_reference": "/tmp/x.py",
    })
    assert problemas == []


# ------------------------------------------------------ 2/3. input/output invalido

def test_input_invalido_es_detectado():
    """TEST 2."""
    schema = Schema(fields=(FieldRule("run_id", str, required=True),))
    problemas = schema.validate({"otra_cosa": 1})
    assert "falta el campo obligatorio 'run_id'" in problemas


def test_output_invalido_es_detectado():
    """TEST 3."""
    problemas = GENERATOR_OUTPUT.validate_output({"artifact": {"artifact_id": "ART-1"}})
    assert any("code_reference" in p for p in problemas)


# ------------------------------------------------- 4. campo obligatorio ausente

def test_campo_obligatorio_ausente_es_reportado():
    """TEST 4."""
    problemas = CLASSIFIER_OUTPUT.validate_output({"category": "FEATURE", "confidence": 0.9})
    assert problemas == ["falta el campo obligatorio 'reason'"]


# ------------------------------------------------------------ 5. tipo incorrecto

def test_tipo_incorrecto_es_reportado():
    """TEST 5."""
    problemas = CLASSIFIER_OUTPUT.validate_output(
        {"category": "FEATURE", "confidence": "alta", "reason": "porque si"}
    )
    assert any("confidence" in p and "float" in p for p in problemas)


# ---------------------------------------------------------- 6. contrato inexistente

def test_contrato_inexistente_levanta_error():
    """TEST 6."""
    registry = ContractRegistry()
    with pytest.raises(ContractNotFoundError):
        registry.get("NO_EXISTE")


# -------------------------------------------------------------- 7. version invalida

def test_version_inexistente_levanta_error():
    """TEST 7."""
    registry = build_default_registry()
    with pytest.raises(ContractNotFoundError):
        registry.get("GENERATOR_OUTPUT", version="9.9")


def test_version_por_defecto_es_la_mas_alta():
    registry = ContractRegistry()
    base = GENERATOR_OUTPUT
    registry.register(base)
    registry.register(Contract(
        contract_id=base.contract_id, version="2.0", producer=base.producer,
        consumer=base.consumer, input_schema=base.input_schema,
        output_schema=base.output_schema,
    ))
    obtenido = registry.get("GENERATOR_OUTPUT")
    assert obtenido.version == "2.0"


# --------------------------------------------------------- 8/9. AgentResult valido/invalido

def test_agent_result_valido_contra_su_contrato():
    """TEST 8."""
    resultado = AgentResult(agent_id="classifier", input="algo",
                            output={"category": "BUG", "confidence": 0.85, "reason": "x"},
                            status="OK")
    assert CLASSIFIER_OUTPUT.validate_output(resultado.output) == []


def test_agent_result_invalido_contra_su_contrato():
    """TEST 9."""
    resultado = AgentResult(agent_id="classifier", input="algo",
                            output={"category": "BUG"}, status="OK")
    problemas = CLASSIFIER_OUTPUT.validate_output(resultado.output)
    assert problemas  # confidence y reason faltan


# --------------------------------------- 10. Coordinator rechaza output incompatible

def test_coordinator_rechaza_output_incompatible_con_contrato(
    real_run_manager, registry_with_generator, tmp_path,
):
    """TEST 10: un Generator que devuelve un output OK pero con forma
    invalida (falta code_reference) no debe terminar en COMPLETED ni dejar
    artifact -- el Contract lo intercepta antes de que el Coordinator lo
    acepte como exitoso."""
    class _GeneratorRoto(GeneratorAgent):
        def execute(self, input_data):
            return AgentResult(agent_id=self.metadata.id, input=input_data,
                               output={"artifact": {"artifact_id": "ART-ROTO"}},
                               status="OK")  # sin "code_reference" -- viola GENERATOR_OUTPUT

    registry = AgentRegistry()
    registry.register(_GeneratorRoto())
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")

    coordinator = Coordinator(run_manager=real_run_manager, registry=registry,
                              contract_registry=build_default_registry())
    gi = GeneratorInput(run_id=run.run_id, requirement="algo",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))
    coordinator.execute_stage(run, gi)

    assert run.status.value == "FAILED"
    assert run.artifacts == [], "un output que viola su Contract no debe dejar un artifact"
    assert run.evidence[0]["status"] == "ERROR"
    assert run.evidence[0]["output"]["error"] == "contract_violation"
    assert run.evidence[0]["output"]["contract_id"] == "GENERATOR_OUTPUT"
    tipos = {e.event_type.value for e in run.events}
    assert "AGENT_FAILED" in tipos
    assert "AGENT_COMPLETED" not in tipos


# ------------------------------------------ 11. Coordinator acepta output valido

def test_coordinator_acepta_output_valido_con_contrato(
    real_run_manager, registry_with_generator, tmp_path,
):
    """TEST 11: el Generator real (sin romper nada) sigue completando el Run
    normalmente cuando SI se le pasa un ContractRegistry -- el Contract no
    interfiere con un output conforme."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_generator,
                              contract_registry=build_default_registry())
    gi = GeneratorInput(run_id=run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))
    coordinator.execute_stage(run, gi)

    assert run.status.value == "COMPLETED"
    assert len(run.artifacts) == 1
    assert Path(run.artifacts[0]["reference"]).is_file()


# --------------------------------- 12/13. compatibilidad con Generator/Classifier existentes

@pytest.fixture
def registry_with_generator() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(GeneratorAgent())
    return registry


def test_generator_existente_es_compatible_con_su_contrato(tmp_path):
    """TEST 12: el Generator implementado en Fase 4B, sin ningun cambio de
    comportamiento, produce un output que YA cumple GENERATOR_OUTPUT."""
    agente = GeneratorAgent()
    gi = GeneratorInput(run_id="r-compat-gen", requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida("SPEC-COMPAT-GEN"),
                        authorized_context=_contexto_aislado(tmp_path, "r-compat-gen"))
    resultado = agente.execute(gi)
    assert resultado.status == "OK"
    assert GENERATOR_OUTPUT.validate_output(resultado.output) == []


def test_classifier_existente_es_compatible_con_su_contrato(registry_with_classifier):
    """TEST 13: el Classifier implementado en Fase 3, sin ningun cambio de
    comportamiento, produce un output que YA cumple CLASSIFIER_OUTPUT."""
    classifier = registry_with_classifier.get("classifier")
    resultado = classifier.execute("Necesitamos agregar alta de clientes con DNI unico")
    assert resultado.status == "OK"
    assert CLASSIFIER_OUTPUT.validate_output(resultado.output) == []


# --------------------------------------------------------------- extras de cobertura

def test_contract_registry_expone_todos_los_contratos_del_catalogo():
    registry = build_default_registry()
    esperados = {c.contract_id for c in ALL_CONTRACTS}
    assert set(registry.list_ids()) == esperados


def test_assert_output_valid_levanta_contract_violation_error():
    with pytest.raises(ContractViolationError):
        GENERATOR_OUTPUT.assert_output_valid({"artifact": {}})


def test_coordinator_sin_contract_registry_preserva_comportamiento_previo(
    real_run_manager, registry_with_generator, tmp_path,
):
    """Sin pasar `contract_registry` (default None), el Coordinator se
    comporta exactamente como en la Fase 4B -- ninguna validacion de
    Contract se interpone."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_generator)
    gi = GeneratorInput(run_id=run.run_id, requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida("SPEC-NO-CONTRACT"),
                        authorized_context=_contexto_aislado(tmp_path, run.run_id))
    coordinator.execute_stage(run, gi)
    assert run.status.value == "COMPLETED"
    assert len(run.artifacts) == 1


def test_validator_y_reviewer_tienen_contratos_definidos_sin_implementacion():
    """Los agentes de Validation/Review no existen todavia como codigo
    (fuera de alcance de esta fase) -- pero sus Contracts deben estar
    registrados, listos para cuando se implementen."""
    registry = build_default_registry()
    for contract_id in ("VALIDATOR_INPUT", "VALIDATOR_OUTPUT",
                        "REVIEWER_INPUT", "REVIEWER_OUTPUT"):
        assert registry.is_registered(contract_id)
    assert not AgentRegistry().is_registered("validator")
    assert not AgentRegistry().is_registered("reviewer")


def test_no_depende_del_etl_financiero():
    import ast
    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    base = Path(__file__).resolve().parents[1]
    ofensores = {}
    for archivo in ("contracts.py", "contracts_catalog.py"):
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
