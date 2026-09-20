"""Validator -- evalua, no genera, no modifica, no decide arquitectura.

FACTORY-SPEC.md Seccion 6 (Validator): *"produce evidencia objetiva (tests,
chequeos estaticos, ejecucion real) de que un artefacto cumple sus Contracts
e Invariants... No puede corregir el artefacto que esta validando."* Esta
implementacion respeta eso al pie de la letra: `ValidatorAgent.execute()`
nunca escribe en `input_data.artifact` ni en el archivo que `code_reference`
apunta -- solo LEE (para los Evals que ejecutan el modulo generado) y
produce un `ValidationResult`.

Flujo interno exacto (pedido explicito de la Fase 5B):

    AGENT -> CONTRACT -> INVARIANTS -> EVALS -> VALIDATOR -> EVIDENCE

El Contract ya se verifico ANTES de que el Validator se ejecute (Fase 5A,
en el Coordinator) -- el Validator asume que si llego hasta aca, el output
del agente productor ya tiene forma valida. El Validator se concentra en lo
que un Contract no puede expresar: propiedades (Invariants) y comportamiento
(Evals).

Deliberadamente binario: PASS o FAIL. FACTORY-SPEC.md Seccion 6 tambien
menciona WARNING/BLOCK/NOT_CALCULABLE como vocabulario posible de Validation
en general (y `contracts_catalog.py::VALIDATOR_OUTPUT` documenta ese
vocabulario mas amplio para el Contract) -- pero la Fase 5B pide
explicitamente "no usar estados ambiguos como 'mas o menos correcto'" para
ESTE Validator concreto. Se resuelve sin contradecir el Contract (que solo
exige `result: str`, sin fijar los valores permitidos por Schema): esta
implementacion usa el subconjunto {PASS, FAIL}, mas estricto que el
vocabulario completo de la spec, documentado aca y en VALIDATOR.md en vez de
decidirlo en silencio.

Fase 5D (FINDING-04, INDEPENDENT-VERIFICATION-5C.md, LOW): un Eval (o un
Invariant) mal escrito puede levantar una excepcion real durante su
ejecucion (el reporte demostro un `AttributeError` de un Eval que ejecuta
codigo generado con una entidad inesperada). Antes de esta fase, esa
excepcion atravesaba `execute()` sin capturarse, violando la regla explicita
de `agent_contract.py` ("`execute()` no debe lanzar excepciones por
condiciones de negocio esperables -- debe devolver un AgentResult con
status=ERROR") y dejando el Run en RUNNING no-terminal (ni COMPLETED ni
FAILED) sin ningun evento que lo explique. Se corrige envolviendo la
ejecucion de Invariants/Evals en un `try` -- misma politica fail-safe que
`GeneratorAgent.execute()` ya aplica a sus propios errores de generacion:
la excepcion se convierte en `AgentResult(status="ERROR")`, nunca se
propaga. El Coordinator (sin cambios) trata eso igual que cualquier otro
`status="ERROR"`: `AGENT_FAILED` + `RunManager.transition(FAILED)` -- un
estado terminal seguro, nunca una falsa apariencia de exito.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent
from evals import EvalRegistry
from invariants import InvariantRegistry


@dataclass(frozen=True)
class ValidatorInput:
    """Lo que el Validator necesita para evaluar -- nunca "adivina" el
    contexto de ejecucion real (mismo principio que `GeneratorInput` con la
    Specification, Fase 4B): quien construye este input arma `context` con
    los datos concretos (p.ej. `code_reference`, `registros`) que los
    Invariants/Evals aplicables van a necesitar."""
    run_id: str
    scope: str                       # a que Invariants/Evals aplica (p.ej. "Generator")
    artifact: dict[str, Any] | None  # el Artifact a validar (o None si no hay)
    evidence: dict[str, Any] | None  # la evidencia que produjo ese Artifact
    context: dict[str, Any] = field(default_factory=dict)  # datos extra para Invariants/Evals
    invariant_registry: InvariantRegistry | None = None
    eval_registry: EvalRegistry | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Salida estructurada del Validator -- PASS o FAIL, nunca un estado
    ambiguo. `checks` lleva TODOS los resultados (Invariants + Evals,
    pasaron o no); `failures` es el subconjunto que fallo, con motivo."""
    status: str  # "PASS" | "FAIL"
    checks: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.status, "status": self.status,
            "checks": self.checks, "failures": self.failures,
            "violations": [f["id"] for f in self.failures],
            "evidence": self.evidence,
        }


class ValidatorAgent(BaseAgent):
    metadata = AgentMetadata(
        id="validator",
        name="Validator",
        role=AgentRole.VALIDATOR,
        input_contract="ValidatorInput: {run_id, scope, artifact, evidence, context, "
                       "invariant_registry, eval_registry}",
        output_contract="dict: {result: PASS|FAIL, checks, failures, evidence} -- ver VALIDATOR.md",
    )

    def execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, ValidatorInput):
            return AgentResult(agent_id=self.metadata.id, input=input_data,
                               output=None, status="ERROR")

        if input_data.invariant_registry is None and input_data.eval_registry is None:
            return AgentResult(
                agent_id=self.metadata.id,
                input={"run_id": input_data.run_id, "scope": input_data.scope},
                output={"error": "sin_invariants_ni_evals",
                       "detail": "el Validator necesita al menos un InvariantRegistry o "
                                "EvalRegistry para tener algo que evaluar"},
                status="ERROR",
            )

        # Contexto que los checks (Invariant.check / Eval.evaluation_method)
        # reciben -- combina lo que el llamador arma explicitamente con
        # artifact/evidence, sin que el Validator interprete su contenido de
        # negocio (eso es responsabilidad de cada Invariant/Eval concreto).
        contexto: dict[str, Any] = {
            "artifact": input_data.artifact,
            "evidence": input_data.evidence,
            **input_data.context,
        }

        checks: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        try:
            if input_data.invariant_registry is not None:
                for resultado in input_data.invariant_registry.evaluate_all(input_data.scope, contexto):
                    checks.append(resultado.to_dict())
                    if not resultado.passed:
                        failures.append({"id": resultado.invariant_id, "type": "INVARIANT",
                                         "reason": resultado.detail})

            if input_data.eval_registry is not None:
                for resultado in input_data.eval_registry.run_all(input_data.scope, contexto):
                    checks.append(resultado.to_dict())
                    if not resultado.passed:
                        failures.append({"id": resultado.eval_id, "type": "EVAL",
                                         "reason": resultado.detail})
        except Exception as exc:  # noqa: BLE001 -- fail-safe: nunca dejar el Run en RUNNING
            # Cualquier excepcion real durante la ejecucion de un Invariant o
            # un Eval (p. ej. el modulo generado no tiene la forma que el
            # Eval asume) se convierte en un resultado terminal seguro --
            # nunca se propaga (violaria el contrato de BaseAgent.execute())
            # ni se interpreta como PASS por ausencia de error.
            return AgentResult(
                agent_id=self.metadata.id,
                input={"run_id": input_data.run_id, "scope": input_data.scope,
                      "artifact": input_data.artifact},
                output={"error": "validation_exception", "detail": str(exc),
                       "checks_completados_antes_de_la_excepcion": checks},
                status="ERROR",
            )

        status = "FAIL" if failures else "PASS"
        resultado = ValidationResult(
            status=status, checks=checks, failures=failures,
            evidence={"run_id": input_data.run_id, "scope": input_data.scope,
                     "artifact_id": (input_data.artifact or {}).get("artifact_id"),
                     "checks_evaluados": len(checks)},
        )

        return AgentResult(
            agent_id=self.metadata.id,
            input={"run_id": input_data.run_id, "scope": input_data.scope,
                  "artifact": input_data.artifact},
            output=resultado.to_dict(),
            status="OK",  # el Agent en si no "fallo" -- evaluo correctamente y devolvio FAIL
        )
