"""PipelineDefinition -- las etapas validas del pipeline SDD y su orden.

No hardcodea la lista de etapas: la recibe de `FactorySpecLoader`, que la lee
de la tabla de FACTORY-SPEC.md Seccion 7 ("Pipeline"). Este modulo solo sabe
representarla y validar contra ella -- no sabe leer Markdown ni conoce la
ruta del archivo (eso es responsabilidad de FactorySpecLoader).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from kernel.errors import UnknownStageError


@dataclass(frozen=True)
class PipelineStage:
    name: str
    transition_condition: str = ""
    typical_agents: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PipelineDefinition:
    stages: tuple[PipelineStage, ...] = field(default_factory=tuple)

    @property
    def stage_names(self) -> list[str]:
        return [s.name for s in self.stages]

    def is_known(self, stage_name: str) -> bool:
        return stage_name in self.stage_names

    def assert_known(self, stage_name: str) -> None:
        if not self.is_known(stage_name):
            raise UnknownStageError(stage_name, self.stage_names)

    def agents_for(self, stage_name: str) -> tuple[str, ...]:
        """Agentes tipicos que FACTORY-SPEC.md Seccion 7 declara para esta
        etapa (columna "Agent(s) tipico(s)" de la tabla real -- no una
        segunda copia mantenida a mano). El Coordinator usa esto para saber
        que agente esta autorizado a correr en la etapa actual de un Run."""
        self.assert_known(stage_name)
        for stage in self.stages:
            if stage.name == stage_name:
                return stage.typical_agents
        return ()

    def first_stage(self) -> str:
        if not self.stages:
            raise UnknownStageError("(pipeline vacio)", [])
        return self.stages[0].name

    def next_stage(self, current: str) -> str | None:
        """Etapa siguiente en el orden declarado, o None si `current` es la
        ultima. No representa una transicion de RunStatus (eso es
        StateMachine) -- representa avance dentro del Pipeline (Seccion 7)."""
        self.assert_known(current)
        names = self.stage_names
        idx = names.index(current)
        return names[idx + 1] if idx + 1 < len(names) else None
