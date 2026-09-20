"""Invariant Model -- propiedades que DEBEN sostenerse siempre, no solo al
final de una etapa (FACTORY-SPEC.md Seccion 11, Governance: *"Invariants:
propiedades que deben sostenerse siempre, no solo al final de una etapa"*).

Distinto de un Contract (`contracts.py`): un Contract verifica FORMA (¿tiene
`code_reference`? ¿es `str`?). Un Invariant verifica una PROPIEDAD sobre el
contenido/comportamiento de lo que un Contract ya aprobo como bien formado --
p. ej. "el DNI es unico entre los registros ya dados de alta", algo que
ninguna forma de dict puede expresar por si sola.

Vive en la raiz de `software-factory/` junto a `contracts.py` y
`observability.py` -- misma capa transversal, mismo motivo: ni el Kernel ni
el Coordinator ni ningun Agent conocen este modulo (lo consume el Validator,
que si depende de el).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Severity(str, Enum):
    """Que tan grave es que este Invariant se rompa. No decide por si sola
    el resultado del Validator (eso es logica del Validator, no del
    Invariant) -- es metadata que un Validator puede usar para distinguir
    "esto bloquea el avance" de "esto es una advertencia"."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"


@dataclass(frozen=True)
class InvariantCheckResult:
    """Resultado de evaluar UN Invariant sobre un contexto concreto."""
    invariant_id: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.invariant_id, "status": "PASS" if self.passed else "FAIL",
               "detail": self.detail}


@dataclass(frozen=True)
class Invariant:
    """Una propiedad obligatoria, expresada como una funcion `check(context)
    -> InvariantCheckResult` -- no una clase por Invariant (eso obligaria a
    subclasificar por cada propiedad nueva); una funcion pura alcanza,
    siguiendo el mismo patron que `agents/classifier.py::classify()`
    (funcion determinista, sin estado, facil de testear).

    `scope` documenta a que se aplica este Invariant (p. ej. "Generator",
    "Run") -- el InvariantRegistry lo usa para saber cuales son "aplicables"
    a un contexto dado, sin que el Invariant necesite conocer al Coordinator
    ni al Validator.
    """
    invariant_id: str
    version: str
    name: str
    description: str
    severity: Severity
    scope: str
    check: Callable[[dict[str, Any]], InvariantCheckResult]

    def evaluate(self, context: dict[str, Any]) -> InvariantCheckResult:
        return self.check(context)

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant_id": self.invariant_id, "version": self.version,
            "name": self.name, "description": self.description,
            "severity": self.severity.value, "scope": self.scope,
        }


class InvariantRegistry:
    """Registra Invariants y ejecuta los aplicables a un `scope`. No muta
    ningun State (no importa `kernel/`), no ejecuta ningun Agent (no importa
    `coordinator/` ni `agent_contract.py`) -- solo conoce `Invariant` y un
    `context: dict` que quien la llama arma."""

    def __init__(self) -> None:
        self._invariants: dict[str, Invariant] = {}

    def register(self, invariant: Invariant) -> None:
        self._invariants[invariant.invariant_id] = invariant

    def get(self, invariant_id: str) -> Invariant:
        if invariant_id not in self._invariants:
            raise KeyError(f"Invariant no registrado: {invariant_id!r}; "
                           f"registrados: {self.list_ids()}")
        return self._invariants[invariant_id]

    def is_registered(self, invariant_id: str) -> bool:
        return invariant_id in self._invariants

    def list_ids(self) -> list[str]:
        return sorted(self._invariants)

    def applicable_to(self, scope: str) -> list[Invariant]:
        return [inv for inv in self._invariants.values() if inv.scope == scope]

    def evaluate_all(self, scope: str, context: dict[str, Any]) -> list[InvariantCheckResult]:
        """Ejecuta TODOS los Invariants aplicables a `scope` sobre `context`,
        en orden de `invariant_id` (determinista). No decide que hacer con
        los resultados -- eso es el Validator."""
        return [inv.evaluate(context) for inv in sorted(
            self.applicable_to(scope), key=lambda i: i.invariant_id,
        )]
