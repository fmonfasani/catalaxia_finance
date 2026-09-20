"""Catalogo de Contracts concretos de la Factory -- Classifier, Generator, y
los de Validator/Reviewer (definidos, NO implementados: esos dos agentes no
existen todavia como codigo; el Contract es la preparacion explicita para
cuando existan, pedida por la Fase 5A).

Separado de `contracts.py` a proposito: `contracts.py` es el MODELO generico
(`Contract`, `Schema`, `ContractRegistry`) y no debe conocer a Generator ni a
Classifier por nombre. Este modulo es el unico que instancia contratos
concretos -- si un contrato cambia de forma, se edita aca, nunca en el
modelo generico.

`build_default_registry()` es el punto de entrada que el Coordinator (o
quien lo construya) usa para obtener un `ContractRegistry` con todos los
contratos de esta fase ya cargados -- ningun Agent se registra a si mismo.
"""
from __future__ import annotations

from contracts import Contract, ContractRegistry, FieldRule, Schema

# ============================================================== Classifier

CLASSIFIER_INPUT = Contract(
    contract_id="CLASSIFIER_INPUT",
    version="1.0",
    producer="coordinator",
    consumer="classifier",
    input_schema=Schema(fields=(
        # El Classifier real (`agents/classifier.py`) recibe hoy un `str`
        # suelto, no un dict -- no se fuerza aqui una forma de dict que
        # cambiaria el comportamiento actual (regla explicita: "preservar
        # completamente el comportamiento existente"). Este Schema vacio
        # documenta esa realidad en vez de inventar una forma nueva; ver
        # CONTRACTS.md, seccion "Classifier: input no es un dict".
    )),
    output_schema=Schema(),  # el input del Classifier no se valida por Schema (ver arriba)
    preconditions=("input_data es un str no vacio",),
    postconditions=("output.category en {FEATURE, BUG, QUESTION}",),
    allowed_states=("PENDING", "RUNNING"),
    failure_conditions=("input_data vacio o no-str -> AgentResult(status=ERROR, output=None)",),
    evidence_requirements=("AgentResult registrado como evidence del Run",),
)

CLASSIFIER_OUTPUT = Contract(
    contract_id="CLASSIFIER_OUTPUT",
    version="1.0",
    producer="classifier",
    consumer="coordinator",
    input_schema=Schema(),
    output_schema=Schema(fields=(
        FieldRule("category", str, required=True),
        FieldRule("confidence", float, required=True),
        FieldRule("reason", str, required=True),
    )),
    preconditions=("el Classifier recibio un input_data valido",),
    postconditions=(
        "category en {FEATURE, BUG, QUESTION}",
        "0.0 <= confidence <= 1.0",
    ),
    allowed_states=("RUNNING",),
    failure_conditions=("ninguna -- un Classifier exitoso siempre produce esta forma",),
    evidence_requirements=("EVIDENCE_RECORDED con este output como evidence.output",),
)


# ================================================================ Generator

GENERATOR_INPUT = Contract(
    contract_id="GENERATOR_INPUT",
    version="1.0",
    producer="coordinator",
    consumer="generator",
    input_schema=Schema(fields=(
        # `GeneratorInput` es una dataclass, no un dict -- igual que con el
        # Classifier, no se fuerza una forma de dict inexistente. La
        # precondicion real ya la hace cumplir `agents/specification.py`
        # (`Specification.validar()`); este Contract la DOCUMENTA, no la
        # duplica en un segundo lugar.
    )),
    output_schema=Schema(),
    preconditions=(
        "requirement no vacio",
        "specification es una Specification y specification.validar() == []",
    ),
    allowed_states=("PENDING", "RUNNING"),
    failure_conditions=(
        "requirement vacio -> output.error == 'requirement_inexistente'",
        "specification invalida o ausente -> output.error == 'specification_invalida'",
        "error de filesystem -> output.error == 'filesystem_error'",
        "cualquier otra excepcion de generacion -> output.error == 'generation_failure'",
    ),
    evidence_requirements=("AgentResult registrado como evidence del Run",),
)

GENERATOR_OUTPUT = Contract(
    contract_id="GENERATOR_OUTPUT",
    version="1.0",
    producer="generator",
    consumer="coordinator",
    input_schema=Schema(),
    output_schema=Schema(fields=(
        FieldRule("artifact", dict, required=True),
        FieldRule("code_reference", str, required=True),
    )),
    preconditions=("el Generator recibio un GeneratorInput con Specification valida",),
    postconditions=(
        "artifact.artifact_id no vacio",
        "artifact.run_id == GeneratorInput.run_id",
        "code_reference apunta a un archivo que existe fisicamente",
    ),
    allowed_states=("RUNNING",),
    failure_conditions=("ninguna -- un Generator exitoso siempre produce esta forma",),
    evidence_requirements=(
        "EVIDENCE_RECORDED con este output como evidence.output",
        "un elemento en run.artifacts correlacionado via artifact.artifact_id",
    ),
)

# El Artifact en si (no un intercambio Agent<->Coordinator, sino la forma que
# `observability.Artifact` ya declara) -- registrado tambien como Contract
# para que `ContractRegistry` sea la unica fuente de "formas verificables"
# de la Factory, sin un segundo mecanismo de verificacion de Artifact aparte.
ARTIFACT_SHAPE = Contract(
    contract_id="ARTIFACT_SHAPE",
    version="1.0",
    producer="generator",
    consumer="coordinator",
    input_schema=Schema(),
    output_schema=Schema(fields=(
        FieldRule("artifact_id", str, required=True),
        FieldRule("run_id", str, required=True),
        FieldRule("stage", str, required=True),
        FieldRule("agent_id", str, required=True),
        FieldRule("type", str, required=True),
        FieldRule("reference", str, required=True),
        FieldRule("created_at", str, required=True),
    )),
    postconditions=("reference apunta a un path dentro de software-factory/runs/<run_id>/",),
    evidence_requirements=("correlacionado con un elemento de run.evidence via evidence_ref",),
)


# ================================================ Validator (NO implementado)

VALIDATOR_INPUT = Contract(
    contract_id="VALIDATOR_INPUT",
    version="1.0",
    producer="coordinator",
    consumer="validator",
    input_schema=Schema(fields=(
        FieldRule("artifact", dict, required=True),
        FieldRule("specification", dict, required=True),
        FieldRule("contracts", list, required=False),
        FieldRule("invariants", list, required=False),
        FieldRule("relevant_evidence", list, required=False),
    )),
    output_schema=Schema(),
    preconditions=("existe un artifact con status COMPLETED a validar",),
    allowed_states=("RUNNING",),
    failure_conditions=("artifact ausente o inexistente -> rechazo, nunca PASS por omision",),
    evidence_requirements=("evidencia objetiva -- FACTORY-SPEC.md Seccion 6 (Validator)",),
)

VALIDATOR_OUTPUT = Contract(
    contract_id="VALIDATOR_OUTPUT",
    version="1.0",
    producer="validator",
    consumer="coordinator",
    input_schema=Schema(),
    output_schema=Schema(fields=(
        FieldRule("result", str, required=True),  # PASS | WARNING | BLOCK | NOT_CALCULABLE
        FieldRule("violations", list, required=True),
        FieldRule("evidence", dict, required=True),
        FieldRule("details", str, required=False),
    )),
    postconditions=(
        "result en {PASS, WARNING, BLOCK, NOT_CALCULABLE} "
        "(FACTORY-SPEC.md Seccion 6 -- nunca una aprobacion implicita por ausencia de error)",
    ),
    allowed_states=("RUNNING",),
    failure_conditions=("result == BLOCK -> el Run no puede avanzar a Review",),
    evidence_requirements=("violations vacio es obligatorio para result == PASS",),
)


# ================================================= Reviewer (NO implementado)

REVIEWER_INPUT = Contract(
    contract_id="REVIEWER_INPUT",
    version="1.0",
    producer="coordinator",
    consumer="reviewer",
    input_schema=Schema(fields=(
        FieldRule("requirement", str, required=True),
        FieldRule("specification", dict, required=True),
        FieldRule("artifact", dict, required=True),
        FieldRule("validation_result", dict, required=True),
        FieldRule("evidence", list, required=False),
    )),
    output_schema=Schema(),
    preconditions=("validation_result.result != BLOCK",),
    allowed_states=("RUNNING",),
    failure_conditions=("validation_result ausente -> rechazo (Review nunca sustituye a Validation)",),
    evidence_requirements=("FACTORY-SPEC.md Seccion 6 (Reviewer)",),
)

REVIEWER_OUTPUT = Contract(
    contract_id="REVIEWER_OUTPUT",
    version="1.0",
    producer="reviewer",
    consumer="coordinator",
    input_schema=Schema(),
    output_schema=Schema(fields=(
        FieldRule("result", str, required=True),  # PASS | FAIL
        FieldRule("findings", list, required=True),
        FieldRule("evidence", dict, required=True),
        FieldRule("recommendation", str, required=False),
    )),
    postconditions=(
        "un result == FAIL siempre requiere al menos un elemento en findings "
        "(nunca un rechazo sin motivo -- FACTORY-SPEC.md Seccion 7: "
        "'Aprobacion explicita, con motivo, nunca silenciosa')",
    ),
    allowed_states=("RUNNING",),
    failure_conditions=("result == FAIL -> el Run no puede llegar a Delivery",),
    evidence_requirements=("un Review favorable nunca compensa una Validation fallida",),
)


ALL_CONTRACTS: tuple[Contract, ...] = (
    CLASSIFIER_INPUT, CLASSIFIER_OUTPUT,
    GENERATOR_INPUT, GENERATOR_OUTPUT, ARTIFACT_SHAPE,
    VALIDATOR_INPUT, VALIDATOR_OUTPUT,
    REVIEWER_INPUT, REVIEWER_OUTPUT,
)


def build_default_registry() -> ContractRegistry:
    """Un `ContractRegistry` con todos los contratos de esta fase ya
    registrados -- el punto de entrada que usa el Coordinator (via
    `coordinator/coordinator.py::Coordinator.__init__`, parametro opcional)
    para no tener que registrar cada contrato a mano."""
    registry = ContractRegistry()
    for contrato in ALL_CONTRACTS:
        registry.register(contrato)
    return registry
