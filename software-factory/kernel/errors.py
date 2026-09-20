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
