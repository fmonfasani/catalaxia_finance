"""Eval Model -- casos concretos que verifican COMPORTAMIENTO esperado, no
solo forma (Contract) ni una propiedad general (Invariant).

Distincion explicita (pedida por la Fase 5B):

  CONTRACT   -> ¿la estructura es valida?
  INVARIANT  -> ¿se mantiene una propiedad obligatoria?
  EVAL       -> ¿el comportamiento cumple lo esperado?

Un Eval tiene un `input` concreto, un `expected` concreto, y un
`evaluation_method` (una funcion que, dado el `input` y el contexto de
ejecucion, decide si el comportamiento observado coincide con `expected`).
Ejemplo real de esta fase: "dos altas con el mismo DNI deben producir
rechazo" -- eso no es una propiedad abstracta (Invariant) ni una forma
(Contract), es un caso de comportamiento concreto y ejecutable.

Vive en la raiz de `software-factory/`, mismo nivel que `contracts.py` e
`invariants.py` -- misma capa transversal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class EvalCheckResult:
    eval_id: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.eval_id, "status": "PASS" if self.passed else "FAIL",
               "detail": self.detail}


@dataclass(frozen=True)
class Eval:
    """`evaluation_method(input, context) -> EvalCheckResult` es la unica
    forma de saber si el comportamiento observado (en `context`, armado por
    quien invoca -- tipicamente el Validator) coincide con lo esperado. No
    hay ejecucion de agentes aca: un Eval EVALUA un comportamiento que ya
    ocurrio (el `context` ya trae el resultado real a comparar), no dispara
    uno nuevo."""
    eval_id: str
    version: str
    name: str
    description: str
    input: Any
    expected: Any
    evaluation_method: Callable[[Any, Any, dict[str, Any]], EvalCheckResult]
    scope: str = ""

    def run(self, context: dict[str, Any]) -> EvalCheckResult:
        return self.evaluation_method(self.input, self.expected, context)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_id": self.eval_id, "version": self.version, "name": self.name,
            "description": self.description, "scope": self.scope,
        }


class EvalRegistry:
    """Registra Evals y los ejecuta. No controla el pipeline -- no importa
    `kernel/` ni `coordinator/`, mismo patron que `InvariantRegistry`."""

    def __init__(self) -> None:
        self._evals: dict[str, Eval] = {}

    def register(self, eval_case: Eval) -> None:
        self._evals[eval_case.eval_id] = eval_case

    def get(self, eval_id: str) -> Eval:
        if eval_id not in self._evals:
            raise KeyError(f"Eval no registrado: {eval_id!r}; registrados: {self.list_ids()}")
        return self._evals[eval_id]

    def is_registered(self, eval_id: str) -> bool:
        return eval_id in self._evals

    def list_ids(self) -> list[str]:
        return sorted(self._evals)

    def applicable_to(self, scope: str) -> list[Eval]:
        return [e for e in self._evals.values() if e.scope == scope]

    def run_all(self, scope: str, context: dict[str, Any]) -> list[EvalCheckResult]:
        return [e.run(context) for e in sorted(
            self.applicable_to(scope), key=lambda e: e.eval_id,
        )]
