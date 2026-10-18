"""DEC-SF-001 -- Run Completion Semantics.

Verifica la regla central de la decision: COMPLETED significa "el Run
satisfizo el contrato de ejecucion que declaro", no "el llamador agoto la
lista de pasos que trajo".

Los Runs de este modulo usan el Generator y el Validator reales (no mocks):
el punto de DEC-SF-001 es justamente que agotar pasos no alcanza, asi que
los pasos tienen que ejecutarse de verdad para que la diferencia se note.
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
from kernel.errors import IncompleteScopeError, InvalidScopeError
from kernel.factory_spec_loader import FactorySpecLoader
from kernel.run_manager import Run, RunManager
from kernel.run_scope import RunScope
from kernel.state_machine import RunStatus
from kernel.state_manager import StateManager

SCOPE_VALIDO = RunScope(
    scope_id="SCOPE-DEC-SF-001",
    scope_version="1.0.0",
    required_stages=("Code", "Validation"),
    required_evidence_agents=("generator", "validator"),
)


@pytest.fixture
def spec():
    return FactorySpecLoader().load()


@pytest.fixture
def real_run_manager(spec):
    return RunManager(pipeline=spec.pipeline, factory_version=spec.version)


@pytest.fixture
def registry():
    r = AgentRegistry()
    r.register(GeneratorAgent())
    r.register(ValidatorAgent())
    return r


def _coordinator(run_manager, registry):
    return Coordinator(
        run_manager=run_manager, registry=registry,
        contract_registry=build_contracts(),
    )


def _especificacion(spec_id="SPEC-DEC", entity_name="Cliente"):
    return Specification(
        spec_id=spec_id, entity_name=entity_name,
        requirement_ref="alta de clientes con DNI unico",
        fields=(
            FieldSpec("nombre", "str", required=True),
            FieldSpec("dni", "str", required=True, unique=True),
            FieldSpec("email", "str", required=True),
        ),
    )


def _contexto(tmp_path: Path, run_id: str) -> dict:
    return {"output_dir": tmp_path / run_id / "generated"}


def _generator_input(run_id, tmp_path, spec_id="SPEC-DEC", entity_name="Cliente"):
    return GeneratorInput(
        run_id=run_id, requirement="alta de clientes con DNI unico",
        specification=_especificacion(spec_id, entity_name),
        authorized_context=_contexto(tmp_path, run_id),
    )


def _validator_builder(run_id, registros):
    """Misma convencion que `tests/test_same_run_pipeline.py`: el Validator
    recibe el artifact real del paso anterior, no lo adivina."""
    def builder(artifact, evidence):
        assert artifact is not None, (
            "el Validator debe recibir el artifact real del paso anterior"
        )
        return ValidatorInput(
            run_id=run_id, scope="Generator", artifact=artifact, evidence=evidence,
            context={"code_reference": artifact["reference"], "registros": registros},
            invariant_registry=build_invariants(), eval_registry=build_evals(),
        )
    return builder


# ---------------------------------------------------------------- 1. PASS

def test_alcance_valido_con_todo_cumplido_llega_a_completed(
    real_run_manager, registry, tmp_path,
):
    """DEC-SF-001 regla 3: alcance identificable + criterios satisfechos +
    evidencia trazable -> COMPLETED."""
    run = real_run_manager.create_run(scope=SCOPE_VALIDO)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.COMPLETED
    assert run.executed_stages == ["Code", "Validation"]


# ------------------------------------------------- 2. test requerido FALLA

def test_un_test_requerido_que_falla_impide_completed(
    real_run_manager, registry, tmp_path,
):
    """Un DNI duplicado hace fallar INV-002; el Run no puede completar."""
    run = real_run_manager.create_run(scope=SCOPE_VALIDO)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "9"}, {"dni": "9"}])),
    ])

    assert run.status is RunStatus.FAILED


# ------------------------------------------------ 3. test requerido OMITIDO

def test_un_test_requerido_que_no_se_ejecuta_impide_completed(
    real_run_manager, registry, tmp_path,
):
    """Omitir un test y reprobarlo bloquean COMPLETED por igual: el alcance
    exige un check que este Run nunca ejecuta."""
    scope = RunScope(
        scope_id="SCOPE-TEST-OMITIDO", scope_version="1.0.0",
        required_stages=("Code", "Validation"),
        required_tests=("INV-999-QUE-NADIE-EJECUTA",),
    )
    run = real_run_manager.create_run(scope=scope)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.FAILED


def test_tests_realmente_ejecutados_quedan_registrados(
    real_run_manager, registry, tmp_path,
):
    """`passed_tests` refleja checks que CORRIERON y dieron PASS."""
    scope = RunScope(
        scope_id="SCOPE-TESTS-REALES", scope_version="1.0.0",
        required_stages=("Code", "Validation"),
        required_tests=("INV-001", "INV-002", "EVAL-001"),
    )
    run = real_run_manager.create_run(scope=scope)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.COMPLETED
    for check in ("INV-001", "INV-002", "EVAL-001"):
        assert check in run.passed_tests


# --------------------------------------------- 4. etapa del alcance OMITIDA

def test_una_etapa_requerida_omitida_impide_completed(
    real_run_manager, registry, tmp_path,
):
    """El alcance exige Code+Validation pero el llamador solo trae Code."""
    run = real_run_manager.create_run(scope=SCOPE_VALIDO)
    real_run_manager.advance_stage(run, "Code")

    with pytest.raises(IncompleteScopeError) as exc:
        _coordinator(real_run_manager, registry).execute_pipeline(run, [
            ("Code", _generator_input(run.run_id, tmp_path)),
        ])

    assert "Validation" in exc.value.missing_stages
    assert run.status is not RunStatus.COMPLETED


# ------------------------------- 5. etapa FUERA del alcance no es obligatoria

def test_etapa_fuera_del_alcance_no_es_obligatoria(
    real_run_manager, registry, tmp_path, spec,
):
    """Nucleo de la reconciliacion normativa: el pipeline global declara 12
    etapas, pero un Run cuyo alcance son 2 completa con esas 2. "Ninguna
    etapa puede saltearse" se lee DENTRO del alcance declarado."""
    assert len(spec.pipeline.stage_names) == 12
    assert "Delivery" in spec.pipeline.stage_names
    assert "Delivery" not in SCOPE_VALIDO.required_stages

    run = real_run_manager.create_run(scope=SCOPE_VALIDO)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.COMPLETED


# ------------------- 6. pasos del llamador OK pero contrato no satisfecho

def test_pasos_del_llamador_exitosos_no_bastan_sin_contrato(
    real_run_manager, registry, tmp_path,
):
    """DEC-SF-001 regla 4, el agujero original: antes de la decision, un Run
    sin alcance declarado llegaba a COMPLETED solo por agotar los steps."""
    run = real_run_manager.create_run()  # sin scope
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.FAILED, (
        "sin contrato declarado, agotar los steps no puede producir COMPLETED"
    )
    mensajes = [
        (e.to_dict().get("metadata") or {}).get("message", "") for e in run.events
    ]
    assert any("DEC-SF-001" in str(m) for m in mensajes), (
        "el bloqueo debe quedar trazado como evento ERROR, no solo en el status"
    )


# ------------------------------------- 7. alcance ausente/invalido: cerrado

@pytest.mark.parametrize("scope_id,scope_version,stages,motivo", [
    ("", "1.0.0", ("Code",), "scope_id vacio"),
    ("SCOPE-X", "", ("Code",), "scope_version vacio"),
    ("SCOPE-X", "1.0.0", (), "sin required_stages"),
])
def test_alcance_invalido_falla_cerrado(
    real_run_manager, scope_id, scope_version, stages, motivo,
):
    scope = RunScope(
        scope_id=scope_id, scope_version=scope_version, required_stages=stages,
    )
    with pytest.raises(InvalidScopeError):
        real_run_manager.create_run(scope=scope)


def test_alcance_con_etapa_inexistente_falla_cerrado(real_run_manager):
    scope = RunScope(
        scope_id="SCOPE-FANTASMA", scope_version="1.0.0",
        required_stages=("EtapaQueNoExiste",),
    )
    with pytest.raises(Exception):
        real_run_manager.create_run(scope=scope)


def test_alcance_desordenado_respecto_del_pipeline_falla_cerrado(real_run_manager):
    """El alcance puede omitir etapas, no reordenarlas."""
    scope = RunScope(
        scope_id="SCOPE-DESORDENADO", scope_version="1.0.0",
        required_stages=("Validation", "Code"),
    )
    with pytest.raises(InvalidScopeError):
        real_run_manager.create_run(scope=scope)


# ------------------------------------------- 8. evidencia requerida ausente

def test_evidencia_requerida_ausente_falla_cerrado(
    real_run_manager, registry, tmp_path,
):
    scope = RunScope(
        scope_id="SCOPE-EVIDENCIA", scope_version="1.0.0",
        required_stages=("Code", "Validation"),
        required_evidence_agents=("generator", "validator", "reviewer"),
    )
    run = real_run_manager.create_run(scope=scope)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.FAILED


# ------------------------- 9. nueva version no muta contrato historico

def test_nueva_version_de_alcance_no_muta_un_run_historico(
    real_run_manager, registry, tmp_path, spec,
):
    """DEC-SF-001 regla 6: un cambio posterior de alcance crea un contrato
    nuevo; no invalida retroactivamente un Run ya completado."""
    run_v1 = real_run_manager.create_run(scope=SCOPE_VALIDO)
    real_run_manager.advance_stage(run_v1, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run_v1, [
        ("Code", _generator_input(run_v1.run_id, tmp_path)),
        ("Validation", _validator_builder(run_v1.run_id, [{"dni": "1"}])),
    ])
    assert run_v1.status is RunStatus.COMPLETED

    # v2 exige mas. El Run v1 conserva su contrato y su veredicto.
    scope_v2 = RunScope(
        scope_id="SCOPE-DEC-SF-001", scope_version="2.0.0",
        required_stages=("Code", "Validation", "Review"),
    )
    assert scope_v2.scope_version != run_v1.scope.scope_version
    assert run_v1.scope.required_stages == ("Code", "Validation")
    assert run_v1.status is RunStatus.COMPLETED


# ------------------------------------- 10. COMPLETED distinto de APPROVED

def test_completed_no_es_approved(real_run_manager, registry, tmp_path):
    run = real_run_manager.create_run(scope=SCOPE_VALIDO)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    assert run.status is RunStatus.COMPLETED
    assert run.status is not RunStatus.APPROVED
    # APPROVED sigue siendo alcanzable solo por una transicion explicita.
    real_run_manager.transition(run, RunStatus.APPROVED)
    assert run.status is RunStatus.APPROVED


# ----------------------------- 11. execute_stage() sin alcance: sin cambios

def test_execute_stage_no_cambia_por_dec_sf_001(real_run_manager, registry, tmp_path):
    """`execute_stage()` queda fuera del alcance de la decision: sigue
    comportandose igual para un Run sin contrato declarado."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    coordinator = _coordinator(real_run_manager, registry)

    resultado = coordinator.execute_stage(
        run, _generator_input(run.run_id, tmp_path),
    )

    assert resultado is not None
    assert run.evidence, "execute_stage() debe seguir registrando evidencia"


# --------------------------- 12. persistencia preserva alcance y evidencia

def test_persistencia_preserva_alcance_version_y_tests(
    real_run_manager, registry, tmp_path,
):
    scope = RunScope(
        scope_id="SCOPE-PERSISTENCIA", scope_version="3.1.4",
        required_stages=("Code", "Validation"),
        required_tests=("INV-001",),
    )
    run = real_run_manager.create_run(scope=scope)
    real_run_manager.advance_stage(run, "Code")
    _coordinator(real_run_manager, registry).execute_pipeline(run, [
        ("Code", _generator_input(run.run_id, tmp_path)),
        ("Validation", _validator_builder(run.run_id, [{"dni": "1"}])),
    ])

    state_manager = StateManager(runs_dir=tmp_path / "runs")
    state_manager.save(run.to_dict())
    recuperado = Run.from_dict(state_manager.load(run.run_id))

    assert recuperado.scope is not None
    assert recuperado.scope.scope_id == "SCOPE-PERSISTENCIA"
    assert recuperado.scope.scope_version == "3.1.4"
    assert recuperado.executed_stages == ["Code", "Validation"]
    assert "INV-001" in recuperado.passed_tests
    assert recuperado.status is RunStatus.COMPLETED


def test_run_persistido_sin_alcance_sigue_cargando(real_run_manager, tmp_path):
    """Compatibilidad: un Run guardado ANTES de DEC-SF-001 no tiene las
    claves nuevas y debe cargar igual, sin alcance."""
    run = real_run_manager.create_run()
    d = run.to_dict()
    del d["scope"], d["executed_stages"], d["passed_tests"]

    recuperado = Run.from_dict(d)

    assert recuperado.scope is None
    assert recuperado.executed_stages == []
    assert recuperado.run_id == run.run_id


# ---------------------------------------- 14. independencia del ETL financiero

def test_run_scope_no_depende_del_etl_financiero():
    import kernel.run_scope as modulo

    fuente = Path(modulo.__file__).read_text(encoding="utf-8")
    for prohibido in ("engine", "scripts.market", "backend", "psycopg", "pandas"):
        assert prohibido not in fuente, (
            f"kernel/run_scope.py no puede depender del ETL financiero ({prohibido})"
        )


def test_etapas_ejecutadas_fuera_de_orden_fallan_cerrado():
    """La validaciÃ³n detecta orden real incorrecto, no compara la lista consigo misma."""
    from kernel.errors import StageSkippedError

    with pytest.raises(StageSkippedError):
        SCOPE_VALIDO.assert_no_stage_skipped(["Validation", "Code"])
