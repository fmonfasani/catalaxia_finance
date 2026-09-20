"""Contract Model -- forma verificable mecanicamente de un intercambio entre
dos partes de la Factory (Coordinator<->Agent, Agent->Artifact, etc.).

FACTORY-SPEC.md Seccion 11 (Governance) define el concepto exacto que este
modulo implementa: *"Contracts: forma verificable de una Specification. No
ambiguos, no aspiracionales -- si algo no puede verificarse mecanicamente, no
es un Contract, es una guia."* Antes de esta fase, lo mas cercano a un
contrato eran `AgentMetadata.input_contract`/`output_contract`
(`agent_contract.py`) -- dos strings de PROSA, documentacion, nunca
verificados por codigo. Este modulo no reemplaza esos campos (siguen
existiendo, siguen siendo la descripcion humana): agrega la contraparte
MACHINE-READABLE que faltaba.

No se crea un mecanismo paralelo de identidad de agente ni de evidencia:
`Contract` referencia `producer`/`consumer` como los mismos `agent_id`
string que ya usa `AgentRegistry`, y `ContractRegistry` vive al mismo nivel
que `observability.py` (raiz de `software-factory/`) -- transversal, no
acoplado a `agents/`, `kernel/` ni `coordinator/`, exactamente igual que la
observabilidad de la Fase 4A.

Alcance deliberadamente minimo (Fase 5A): un contrato valida la FORMA de un
dict (campos requeridos + tipo de cada uno) -- no es un motor de JSON Schema
completo (sin `anyOf`, sin validacion anidada recursiva mas alla de
"is instance of dict/list/str/..."). Si una fase futura necesita mas
expresividad, se extiende este modelo -- no se reemplaza.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ContractViolationError(Exception):
    """Un input o output no cumple la forma declarada por un Contract.

    Analoga a `kernel.errors.InvalidTransitionError`: nombra la regla
    violada, no un error generico. El Coordinator la deja propagar (mismo
    patron que usa con `InvalidTransitionError`) en vez de silenciarla --
    un output incompatible con su Contract es una condicion de programa,
    no un resultado de negocio que el Agent ya debio haber manejado."""

    def __init__(self, contract_id: str, errores: list[str]):
        self.contract_id = contract_id
        self.errores = errores
        super().__init__(f"Contract {contract_id!r} violado: {errores}")


@dataclass(frozen=True)
class FieldRule:
    """Una regla de forma sobre un campo de un dict: nombre, tipo(s)
    aceptados, si es obligatorio. Deliberadamente chico -- el mismo espiritu
    de `agents/specification.py::FieldSpec` (un set pequeno de tipos, no un
    sistema de tipos general), aplicado ahora a I/O de agentes en vez de a
    entidades de dominio generadas."""
    name: str
    type: type | tuple[type, ...]
    required: bool = True

    def type_name(self) -> str:
        if isinstance(self.type, tuple):
            return " | ".join(t.__name__ for t in self.type)
        return self.type.__name__


@dataclass(frozen=True)
class Schema:
    """Forma verificable de un dict: que campos deben/pueden estar, y de que
    tipo. No es un schema JSON generico (no anida sub-schemas) -- alcanza
    para las formas planas que Classifier/Generator ya producen hoy."""
    fields: tuple[FieldRule, ...] = field(default_factory=tuple)

    def validate(self, value: Any) -> list[str]:
        """Devuelve una lista de problemas -- vacia si `value` cumple el
        Schema. No corrige nada, no completa nada en silencio (mismo
        contrato que `Specification.validar()`)."""
        if not isinstance(value, dict):
            return [f"se esperaba un dict, se recibio {type(value).__name__}"]
        problemas = []
        for regla in self.fields:
            if regla.name not in value:
                if regla.required:
                    problemas.append(f"falta el campo obligatorio {regla.name!r}")
                continue
            if not isinstance(value[regla.name], regla.type):
                problemas.append(
                    f"el campo {regla.name!r} debe ser {regla.type_name()}, "
                    f"es {type(value[regla.name]).__name__}"
                )
        return problemas

    def is_valid(self, value: Any) -> bool:
        return not self.validate(value)


@dataclass(frozen=True)
class Contract:
    """Contrato entre un `producer` y un `consumer` (ids de agente/componente,
    los mismos strings que ya usa `AgentRegistry`/`AgentMetadata.id`) sobre
    la forma de un intercambio.

    Deliberadamente generico: no conoce a Generator ni a Classifier por
    nombre -- cualquier agente futuro (Validator, Reviewer) se describe con
    la misma clase, sin herencia ni casos especiales.
    """
    contract_id: str
    version: str
    producer: str
    consumer: str
    input_schema: Schema
    output_schema: Schema
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    postconditions: tuple[str, ...] = field(default_factory=tuple)
    allowed_states: tuple[str, ...] = field(default_factory=tuple)
    failure_conditions: tuple[str, ...] = field(default_factory=tuple)
    evidence_requirements: tuple[str, ...] = field(default_factory=tuple)

    def validate_input(self, value: Any) -> list[str]:
        return self.input_schema.validate(value)

    def validate_output(self, value: Any) -> list[str]:
        return self.output_schema.validate(value)

    def assert_output_valid(self, value: Any) -> None:
        """Como `validate_output()`, pero levanta `ContractViolationError` si
        hay problemas -- lo que el Coordinator llama antes de aceptar el
        resultado de un Agent (ver `coordinator/coordinator.py`)."""
        problemas = self.validate_output(value)
        if problemas:
            raise ContractViolationError(self.contract_id, problemas)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "producer": self.producer,
            "consumer": self.consumer,
            "input_fields": [
                {"name": r.name, "type": r.type_name(), "required": r.required}
                for r in self.input_schema.fields
            ],
            "output_fields": [
                {"name": r.name, "type": r.type_name(), "required": r.required}
                for r in self.output_schema.fields
            ],
            "preconditions": list(self.preconditions),
            "postconditions": list(self.postconditions),
            "allowed_states": list(self.allowed_states),
            "failure_conditions": list(self.failure_conditions),
            "evidence_requirements": list(self.evidence_requirements),
        }


class ContractNotFoundError(Exception):
    """Se referencio un contract_id (opcionalmente + version) que el
    ContractRegistry no tiene registrado."""

    def __init__(self, contract_id: str, version: str | None, known: list[str]):
        self.contract_id = contract_id
        self.version = version
        self.known = known
        etiqueta = f"{contract_id}@{version}" if version else contract_id
        super().__init__(f"Contract no registrado: {etiqueta!r}; registrados: {known}")


class ContractRegistry:
    """Registra Contracts y los expone por id (+ version opcional). No valida
    nada por si mismo mas alla de existencia -- la validacion de forma vive
    en `Contract`/`Schema`. Mismo patron que `AgentRegistry`: registrar,
    obtener, listar -- nada de logica de negocio ni de pipeline aca."""

    def __init__(self) -> None:
        self._contracts: dict[str, dict[str, Contract]] = {}

    def register(self, contract: Contract) -> None:
        self._contracts.setdefault(contract.contract_id, {})[contract.version] = contract

    def get(self, contract_id: str, version: str | None = None) -> Contract:
        versiones = self._contracts.get(contract_id)
        if not versiones:
            raise ContractNotFoundError(contract_id, version, self.list_ids())
        if version is None:
            # sin version explicita: la mas alta por orden de tupla de enteros,
            # no por orden lexicografico ("10.0" no debe perder contra "9.0")
            version = max(versiones, key=_version_key)
        contrato = versiones.get(version)
        if contrato is None:
            raise ContractNotFoundError(contract_id, version, sorted(versiones))
        return contrato

    def is_registered(self, contract_id: str, version: str | None = None) -> bool:
        versiones = self._contracts.get(contract_id)
        if not versiones:
            return False
        return version is None or version in versiones

    def list_ids(self) -> list[str]:
        return sorted(self._contracts)

    def versions_for(self, contract_id: str) -> list[str]:
        return sorted(self._contracts.get(contract_id, {}), key=_version_key)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)
