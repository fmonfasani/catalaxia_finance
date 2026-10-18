"""Errores del Factory Kernel.

Cada error corresponde a una regla de FACTORY-SPEC.md que el Kernel hace
cumplir. No son errores genericos: nombrar el error nombra la regla violada.
"""
from __future__ import annotations


class KernelError(Exception):
    """Base de todos los errores del Kernel."""


class SpecLoadError(KernelError):
    """FACTORY-SPEC.md no existe, no se puede leer, o no tiene la estructura
    minima exigida (ver FactorySpecLoader.validate)."""


class SpecContradictionError(KernelError):
    """El codigo del Kernel y FACTORY-SPEC.md se contradicen.

    Regla explicita del pedido de Fase 2: ante una contradiccion, el Kernel
    se detiene y reporta -- nunca la resuelve arbitrariamente.
    """


class InvalidTransitionError(KernelError):
    """Se intento una transicion de estado no permitida."""

    def __init__(self, current: str, target: str, allowed: set[str]):
        self.current = current
        self.target = target
        self.allowed = allowed
        super().__init__(
            f"Transicion invalida {current} -> {target}; "
            f"permitidas desde {current}: {sorted(allowed) or '(ninguna, estado terminal)'}"
        )


class UnknownStageError(KernelError):
    """Se referencio una etapa del pipeline que no existe en FACTORY-SPEC.md."""

    def __init__(self, stage: str, known: list[str]):
        self.stage = stage
        self.known = known
        super().__init__(f"Etapa desconocida {stage!r}; etapas validas: {known}")


class RunNotFoundError(KernelError):
    """Se referencio un run_id que StateManager no tiene persistido."""


class AgentNotFoundError(KernelError):
    """Se referencio un agent_id que el Agent Registry no tiene registrado."""

    def __init__(self, agent_id: str, known: list[str]):
        self.agent_id = agent_id
        self.known = known
        super().__init__(f"Agente no registrado: {agent_id!r}; registrados: {known}")


class AgentDisabledError(KernelError):
    """El agente existe en el Registry pero esta deshabilitado (enabled=False)."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agente {agent_id!r} esta deshabilitado")


class NoAgentAuthorizedError(KernelError):
    """FACTORY-SPEC.md no declara ningun agente tipico para esta etapa del
    Pipeline -- el Coordinator no puede inventar uno."""

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(
            f"FACTORY-SPEC.md no declara un agente tipico para la etapa {stage!r}; "
            f"el Coordinator no puede decidir por si solo que agente correr"
        )


class StageSkippedError(KernelError):
    """Se intento saltear una o mas etapas obligatorias del Pipeline."""

    def __init__(self, from_stage: str, target_stage: str, expected_stage: str | None = None):
        self.from_stage = from_stage
        self.target_stage = target_stage
        self.expected_stage = expected_stage
        msg = f"Salto de etapa invalido: de {from_stage!r} a {target_stage!r}"
        if expected_stage:
            msg += f" (etapa siguiente esperada: {expected_stage!r})"
        super().__init__(msg)


class PipelineIncompleteError(KernelError):
    """El pipeline finalizo sin ejecutar todas las etapas requeridas para completar el Run."""

    def __init__(self, reached_stage: str, final_stage: str):
        self.reached_stage = reached_stage
        self.final_stage = final_stage
        super().__init__(
            f"Pipeline incompleto: finalizo en {reached_stage!r} pero la definicion "
            f"exige alcanzar {final_stage!r}. Las etapas intermedias o finales no pueden "
            f"saltearse silenciosamente para representar el Run como COMPLETED."
        )


class PersistenceError(KernelError):
    """Fallo en la persistencia del Run en StateManager."""


class InvalidScopeError(KernelError):
    """El alcance declarado de un Run esta ausente, vacio o es inconsistente.

    DEC-SF-001 exige fail-closed: un contrato de completitud que no se puede
    identificar o verificar no habilita COMPLETED, lo bloquea.
    """


class IncompleteScopeError(KernelError):
    """El Run no satisfizo el contrato de completitud que declaro (DEC-SF-001).

    Distinto de `PipelineIncompleteError`, que habla del modelo global de 12
    etapas: este habla del ALCANCE DECLARADO de un Run concreto, que puede ser
    un subconjunto legitimo de esas 12.
    """

    def __init__(
        self,
        scope_id: str,
        scope_version: str,
        missing_stages: list[str] | None = None,
        missing_tests: list[str] | None = None,
        missing_evidence: list[str] | None = None,
    ):
        self.scope_id = scope_id
        self.scope_version = scope_version
        self.missing_stages = missing_stages or []
        self.missing_tests = missing_tests or []
        self.missing_evidence = missing_evidence or []
        partes = []
        if self.missing_stages:
            partes.append(f"etapas obligatorias no ejecutadas: {self.missing_stages}")
        if self.missing_tests:
            partes.append(f"tests requeridos sin PASS: {self.missing_tests}")
        if self.missing_evidence:
            partes.append(f"evidencia requerida ausente: {self.missing_evidence}")
        super().__init__(
            f"Run no satisface su contrato de completitud "
            f"{scope_id}@{scope_version}: {'; '.join(partes)}. "
            f"No puede transicionar a COMPLETED."
        )
