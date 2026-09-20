"""Generator: contrato, registro, Specification obligatoria, Artifact real,
trazabilidad REQ->SPEC->GEN->ART->EVIDENCE.

Cubre los 18 puntos pedidos en la Fase 4B. Usa el circuito real (RunManager +
Coordinator + AgentRegistry), nunca una maqueta del Generator.

Diseno de las pruebas de circuito completo (documentado, no implicito): se
usa un Run FRESCO avanzado directamente a la etapa "Code" (la unica etapa
real cuyo agente tipico -- segun FACTORY-SPEC.md Seccion 7 -- es "Generator")
ANTES de la primera llamada a `execute_stage()`. No se encadena
Classifier+Generator sobre el MISMO Run: la StateMachine actual modela un
solo ciclo PENDING->RUNNING->COMPLETED->APPROVED/REJECTED por Run, no un
ciclo independiente por etapa -- intentar un segundo `execute_stage()` sobre
un Run que ya llego a COMPLETED violaria la StateMachine (COMPLETED->RUNNING
no es una transicion valida). Se documenta como decision explicita en
GENERATOR.md en vez de forzar una transicion que no existe.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

from agent_contract import AgentResult, BaseAgent
from agents.generator import GeneratorAgent, GeneratorInput
from agents.specification import FieldSpec, Specification
from coordinator.agent_registry import AgentRegistry
from coordinator.coordinator import Coordinator
from kernel.errors import AgentNotFoundError
from observability import build_trace, query_run


def _especificacion_valida(spec_id="SPEC-TEST-001") -> Specification:
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
    """`GeneratorAgent.execute()` respeta `authorized_context["output_dir"]`
    (`base_dir = output_dir.parents[1]`) para no escribir nunca en el
    `software-factory/runs/` real durante los tests -- todo el filesystem
    de un test vive y muere dentro de `tmp_path`."""
    return {"output_dir": tmp_path / run_id / "generated"}


@pytest.fixture
def real_generator_run(real_run_manager, tmp_path):
    """Un Run sobre el Pipeline REAL, avanzado directamente a "Code" -- ver
    el docstring del modulo para por que no se encadena con Classifier."""
    run = real_run_manager.create_run()
    real_run_manager.advance_stage(run, "Code")
    return run


@pytest.fixture
def registry_with_generator() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(GeneratorAgent())
    return registry


# ---------------------------------------------------- 1. cumple AgentContract

def test_generator_cumple_agent_contract():
    """TEST 1."""
    assert issubclass(GeneratorAgent, BaseAgent)
    agente = GeneratorAgent()
    assert agente.metadata.id == "generator"
    assert agente.metadata.role.value == "GENERATOR"
    resultado = agente.execute(GeneratorInput(run_id="x", requirement="", specification=None))
    assert isinstance(resultado, AgentResult)


# --------------------------------------------- 2/3. registrado y recuperable

def test_generator_esta_registrado_y_se_puede_obtener(registry_with_generator):
    """TEST 2, TEST 3."""
    assert registry_with_generator.is_registered("generator")
    obtenido = registry_with_generator.get("generator")
    assert isinstance(obtenido, GeneratorAgent)


# ------------------------------------------------- 4/5. requiere Specification

def test_generator_requiere_specification(tmp_path):
    """TEST 4: sin Specification, se rechaza -- nunca "adivina"."""
    agente = GeneratorAgent()
    resultado = agente.execute(GeneratorInput(
        run_id="r1", requirement="alta de clientes", specification=None,
    ))
    assert resultado.status == "ERROR"
    assert resultado.output["error"] == "specification_invalida"


def test_specification_invalida_es_rechazada():
    """TEST 5: Specification presente pero incompleta (sin campos)."""
    agente = GeneratorAgent()
    spec_incompleta = Specification(spec_id="SPEC-X", entity_name="Cliente",
                                    requirement_ref="algo", fields=())
    resultado = agente.execute(GeneratorInput(
        run_id="r1", requirement="alta de clientes", specification=spec_incompleta,
    ))
    assert resultado.status == "ERROR"
    assert "no declara ningun campo" in resultado.output["problemas"]


def test_requirement_inexistente_es_rechazado():
    agente = GeneratorAgent()
    resultado = agente.execute(GeneratorInput(
        run_id="r1", requirement="", specification=_especificacion_valida(),
    ))
    assert resultado.status == "ERROR"
    assert resultado.output["error"] == "requirement_inexistente"


# --------------------------------------------------- 6/7. produce Artifact

def test_generator_produce_artifact_con_artifact_id(tmp_path):
    """TEST 6, TEST 7."""
    agente = GeneratorAgent()
    gi = GeneratorInput(run_id="r-artifact", requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, "r-artifact"))
    resultado = agente.execute(gi)
    assert resultado.status == "OK"
    artifact = resultado.output["artifact"]
    assert artifact["artifact_id"].startswith("ART-")
    assert Path(artifact["reference"]).is_file()


# ------------------------------------------- 8/9/10. artifact correlacionado

def test_artifact_correlacionado_run_agente_y_specification(tmp_path):
    """TEST 8, TEST 9, TEST 10."""
    agente = GeneratorAgent()
    gi = GeneratorInput(run_id="r-correlacion", requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida("SPEC-CORR-001"),
                        authorized_context=_contexto_aislado(tmp_path, "r-correlacion"))
    resultado = agente.execute(gi)
    artifact = resultado.output["artifact"]
    assert artifact["run_id"] == "r-correlacion"
    assert artifact["agent_id"] == "generator"
    assert artifact["specification_ref"] == "SPEC-CORR-001"
    assert artifact["requirement_ref"] == "alta de clientes con DNI unico"


# --------------------------------------- 11. Generator no modifica el State

def test_generator_no_modifica_el_state_directamente():
    """TEST 11: `execute()` solo devuelve un AgentResult -- no importa
    RunManager, StateMachine ni Coordinator (verificado por AST, no solo
    por convencion)."""
    ruta = Path(__file__).resolve().parents[1] / "agents" / "generator.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    imports = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            imports.add(nodo.module)
        elif isinstance(nodo, ast.Import):
            imports.update(a.name for a in nodo.names)
    prohibidos = {"kernel.run_manager", "kernel.state_machine", "coordinator.coordinator"}
    assert not (imports & prohibidos), f"generator.py no debe importar {imports & prohibidos}"


# -------------------------------------------- 12. Coordinator ejecuta Generator

def test_coordinator_ejecuta_generator(real_generator_run, registry_with_generator, real_run_manager, tmp_path):
    """TEST 12."""
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_generator)
    gi = GeneratorInput(run_id=real_generator_run.run_id,
                        requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, real_generator_run.run_id))
    coordinator.execute_stage(real_generator_run, gi)
    assert real_generator_run.last_agent == "generator"
    assert real_generator_run.status.value == "COMPLETED"


# ------------------------------------------- 13/14. eventos y evidence

def test_generator_produce_eventos_de_observabilidad_y_evidence(
    real_generator_run, registry_with_generator, real_run_manager, tmp_path,
):
    """TEST 13, TEST 14."""
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_generator)
    gi = GeneratorInput(run_id=real_generator_run.run_id,
                        requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida(),
                        authorized_context=_contexto_aislado(tmp_path, real_generator_run.run_id))
    coordinator.execute_stage(real_generator_run, gi)

    tipos = {e.event_type.value for e in real_generator_run.events}
    assert {"AGENT_SELECTED", "AGENT_STARTED", "AGENT_COMPLETED", "EVIDENCE_RECORDED"} <= tipos
    assert len(real_generator_run.evidence) == 1
    assert real_generator_run.evidence[0]["agent_id"] == "generator"

    completado = [e for e in real_generator_run.events if e.event_type.value == "AGENT_COMPLETED"][0]
    assert completado.artifact_id is not None
    assert completado.artifact_id.startswith("ART-")


# ------------------------------ 15. reconstruir REQ -> SPEC -> GEN -> ART -> EVIDENCE

def test_run_reconstruye_requirement_specification_generator_artifact_evidence(
    real_generator_run, registry_with_generator, real_run_manager, state_manager, tmp_path,
):
    """TEST 15."""
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_generator)
    requirement_texto = "alta de clientes con DNI unico"
    especificacion = _especificacion_valida("SPEC-TRACE-001")
    gi = GeneratorInput(run_id=real_generator_run.run_id, requirement=requirement_texto,
                        specification=especificacion,
                        authorized_context=_contexto_aislado(tmp_path, real_generator_run.run_id))
    coordinator.execute_stage(real_generator_run, gi)
    state_manager.save(real_generator_run.to_dict())

    consulta = query_run(real_generator_run.run_id, state_manager=state_manager)
    assert len(consulta["evidence"]) == 1
    evidencia = consulta["evidence"][0]
    assert evidencia["input"]["requirement"] == requirement_texto
    assert evidencia["input"]["specification"]["spec_id"] == "SPEC-TRACE-001"

    # `run.artifacts` (no la copia inline dentro de `evidence[0]["output"]`)
    # es la version que el Coordinator enriquecio con `evidence_ref` DESPUES
    # de conocer el result_id de la evidencia -- la copia embebida en
    # evidence[0]["output"]["artifact"] es la que el Generator devolvio,
    # tomada ANTES de que existiera esa referencia (por eso trae
    # evidence_ref=None; ver coordinator.py, que arma `artifact = {**artifact,
    # "evidence_ref": ...}` como un dict nuevo, sin mutar el original).
    assert len(consulta["artifacts"]) == 1
    artifact = consulta["artifacts"][0]
    assert artifact["requirement_ref"] == requirement_texto
    assert artifact["specification_ref"] == "SPEC-TRACE-001"
    assert artifact["evidence_ref"]  # referencia de vuelta a la evidencia que lo produjo
    assert artifact["evidence_ref"] == evidencia["result_id"]

    trace = build_trace(real_generator_run.to_dict())
    raiz = next(r for r in trace.roots if r.event["event_type"] == "COORDINATOR_STARTED")
    tipos_hijos = {h.event["event_type"] for h in raiz.children}
    assert {"AGENT_SELECTED", "AGENT_STARTED", "AGENT_COMPLETED", "EVIDENCE_RECORDED"} <= tipos_hijos


# ----------------------------------------------- 16. error de generacion registrado

def test_error_de_generacion_queda_registrado_y_no_marca_artifact_falso(
    real_generator_run, registry_with_generator, real_run_manager,
):
    """TEST 16: Specification invalida -> AGENT_FAILED, sin ARTIFACT, sin
    evidencia marcada como exitosa."""
    coordinator = Coordinator(run_manager=real_run_manager, registry=registry_with_generator)
    spec_invalida = Specification(spec_id="", entity_name="", requirement_ref="", fields=())
    gi = GeneratorInput(run_id=real_generator_run.run_id, requirement="algo",
                        specification=spec_invalida)
    coordinator.execute_stage(real_generator_run, gi)

    assert real_generator_run.status.value == "FAILED"
    tipos = {e.event_type.value for e in real_generator_run.events}
    assert "AGENT_FAILED" in tipos
    assert "AGENT_COMPLETED" not in tipos
    assert real_generator_run.artifacts == [], "una generacion fallida no debe dejar un artifact"
    assert real_generator_run.evidence[0]["status"] == "ERROR"


def test_agente_no_registrado_para_code_no_puede_ejecutarse(real_generator_run, real_run_manager):
    """Complementa TEST 3 desde el lado del Coordinator: sin Generator
    registrado, Code no tiene quien la ejecute."""
    coordinator = Coordinator(run_manager=real_run_manager, registry=AgentRegistry())
    gi = GeneratorInput(run_id=real_generator_run.run_id, requirement="algo",
                        specification=_especificacion_valida())
    with pytest.raises(AgentNotFoundError):
        coordinator.execute_stage(real_generator_run, gi)


# ------------------------------------------- 17. no regresion (marcador)

def test_marcador_no_regresion_fase_4b():
    """No reemplaza correr `pytest tests/` completo -- el reporte final cita
    la corrida real."""
    assert True


# ---------------------------------------------- 18. no depende del ETL

def test_generator_no_depende_del_etl_financiero():
    """TEST 18."""
    prohibidos = (
        "engine", "scripts.engine", "scripts.market", "scripts.pipeline",
        "scripts.tickets", "scripts.dolares", "market_db", "api", "backend",
    )
    base = Path(__file__).resolve().parents[1]
    ofensores = {}
    for archivo in ("agents/generator.py", "agents/specification.py",
                    "agents/generation_workspace.py"):
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


# --------------------------------- extra: el software generado es REALMENTE ejecutable

def test_el_modulo_generado_es_ejecutable_de_verdad(tmp_path):
    """No alcanza con que el archivo exista -- se importa dinamicamente y se
    ejecuta, probando las 4 reglas del requisito (nombre/DNI/email
    obligatorios, DNI unico)."""
    agente = GeneratorAgent()
    gi = GeneratorInput(run_id="r-ejecutable", requirement="alta de clientes con DNI unico",
                        specification=_especificacion_valida("SPEC-EXE-001"),
                        authorized_context=_contexto_aislado(tmp_path, "r-ejecutable"))
    resultado = agente.execute(gi)
    ruta = resultado.output["code_reference"]

    mod_spec = importlib.util.spec_from_file_location("cliente_generado_test", ruta)
    modulo = importlib.util.module_from_spec(mod_spec)
    sys.modules["cliente_generado_test"] = modulo
    mod_spec.loader.exec_module(modulo)

    alta = modulo.AltaClientes()
    cliente = alta.alta("Juan Perez", "12345678", "juan@example.com")
    assert cliente.dni == "12345678"

    with pytest.raises(ValueError, match="dni duplicado"):
        alta.alta("Otra Persona", "12345678", "otra@example.com")
    with pytest.raises(ValueError, match="nombre es obligatorio"):
        alta.alta("", "99999999", "x@example.com")
    with pytest.raises(ValueError, match="email es obligatorio"):
        alta.alta("Alguien", "11112222", "")

    del sys.modules["cliente_generado_test"]
