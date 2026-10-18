"""RunScope -- el contrato de completitud declarado de un Run (DEC-SF-001).

FACTORY-SPEC.md Seccion 7 declara 12 etapas conceptuales del pipeline SDD.
Un Run concreto no siempre ejecuta las 12: ejecuta el SUBCONJUNTO que su
alcance declarado exige. DEC-SF-001 fija la semantica:

    COMPLETED no significa "el llamador agoto la lista de pasos que trajo",
    significa "el Run satisfizo el contrato de ejecucion que declaro".

Por eso el contrato es un dato explicito, versionado e identificable -- no
una propiedad implicita de los `steps` que recibe `execute_pipeline()`. Sin
contrato declarado no hay forma de distinguir "termino" de "se quedo corto",
que es exactamente el agujero que DEC-SF-001 cierra.

Este modulo SOLO representa y verifica el contrato. No decide transiciones
(eso es StateMachine via RunManager), no conoce agentes y no lee Markdown
(eso es FactorySpecLoader). Las etapas declaradas se validan contra la
`PipelineDefinition` real, de modo que un alcance no puede inventar una
etapa que FACTORY-SPEC.md no declara, ni declararlas fuera del orden de la
Seccion 7.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.errors import (
    IncompleteScopeError,
    InvalidScopeError,
    StageSkippedError,
)
from kernel.pipeline_definition import PipelineDefinition


@dataclass(frozen=True)
class RunScope:
    """Alcance declarado de un Run: que etapas son obligatorias, que tests
    deben haber corrido y pasado, y que evidencia exige el contrato.

    `scope_id` + `scope_version` identifican el contrato (DEC-SF-001 regla 1).
    Una version nueva del alcance es un contrato NUEVO: no reescribe el de un
    Run ya completado contra su version anterior (regla 6) -- por eso el
    dataclass es `frozen` y el Run persiste la version con la que corrio.
    """

    scope_id: str
    scope_version: str
    required_stages: tuple[str, ...] = field(default_factory=tuple)
    required_tests: tuple[str, ...] = field(default_factory=tuple)
    required_evidence_agents: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "scope_version": self.scope_version,
            "required_stages": list(self.required_stages),
            "required_tests": list(self.required_tests),
            "required_evidence_agents": list(self.required_evidence_agents),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RunScope":
        return cls(
            scope_id=d["scope_id"],
            scope_version=d["scope_version"],
            required_stages=tuple(d.get("required_stages", ())),
            required_tests=tuple(d.get("required_tests", ())),
            required_evidence_agents=tuple(d.get("required_evidence_agents", ())),
        )

    def validate_against(self, pipeline: PipelineDefinition) -> None:
        """Fail-closed sobre el contrato mismo (DEC-SF-001: "fail closed
        cuando el contrato esta ausente, malformado o es inconsistente").

        Un alcance malformado NO es un alcance permisivo: es un error. Si se
        dejara pasar, un `scope_version` vacio daria un Run "completado"
        contra un contrato no identificable, que es justo lo que la decision
        prohibe.
        """
        if not self.scope_id or not self.scope_id.strip():
            raise InvalidScopeError(
                "scope_id vacio: el alcance de un Run debe ser identificable"
            )
        if not self.scope_version or not self.scope_version.strip():
            raise InvalidScopeError(
                f"scope_version vacio para {self.scope_id!r}: "
                "el alcance debe ser versionado"
            )
        if not self.required_stages:
            raise InvalidScopeError(
                f"{self.scope_id}@{self.scope_version} no declara required_stages: "
                "un Run sin etapas obligatorias no tiene contrato de "
                "completitud verificable"
            )

        for stage in self.required_stages:
            pipeline.assert_known(stage)

        # El alcance puede OMITIR etapas del modelo global de 12 (DEC-SF-001:
        # una etapa fuera del alcance no es obligatoria para ese Run), pero no
        # puede REORDENARLAS: dentro del alcance, el orden de la Seccion 7 manda.
        orden = pipeline.stage_names
        indices = [orden.index(s) for s in self.required_stages]
        if indices != sorted(indices):
            raise InvalidScopeError(
                f"{self.scope_id}@{self.scope_version} declara etapas fuera del "
                f"orden del Pipeline (Seccion 7): {list(self.required_stages)} "
                f"vs orden declarado {orden}"
            )

    def assert_steps_cover_scope(self, step_stages: list[str]) -> None:
        """Verifica ANTES de ejecutar que los pasos que trae el llamador
        cubren el alcance declarado (DEC-SF-001 regla 4: agotar los pasos del
        llamador no es evidencia de completitud).

        Se chequea antes y no solo al final para fallar temprano: si el
        pipeline ya no puede cubrir su alcance, no tiene sentido gastar una
        ejecucion de Agent para descubrirlo.
        """
        faltantes = [s for s in self.required_stages if s not in step_stages]
        if faltantes:
            raise IncompleteScopeError(
                scope_id=self.scope_id,
                scope_version=self.scope_version,
                missing_stages=faltantes,
            )

    def assert_completion(
        self,
        *,
        executed_stages: list[str],
        passed_tests: list[str],
        evidence_agents: list[str],
    ) -> None:
        """Verifica que el Run puede transicionar a COMPLETED.

        Las tres condiciones de DEC-SF-001 regla 3 que son verificables desde
        el Kernel: etapas obligatorias ejecutadas, tests requeridos realmente
        ejecutados y en PASS, y evidencia presente y trazable al Run.
        """
        faltantes = [s for s in self.required_stages if s not in executed_stages]
        if faltantes:
            raise IncompleteScopeError(
                scope_id=self.scope_id,
                scope_version=self.scope_version,
                missing_stages=faltantes,
            )

        tests_faltantes = [t for t in self.required_tests if t not in passed_tests]
        if tests_faltantes:
            raise IncompleteScopeError(
                scope_id=self.scope_id,
                scope_version=self.scope_version,
                missing_tests=tests_faltantes,
            )

        evidencia_faltante = [
            a for a in self.required_evidence_agents if a not in evidence_agents
        ]
        if evidencia_faltante:
            raise IncompleteScopeError(
                scope_id=self.scope_id,
                scope_version=self.scope_version,
                missing_evidence=evidencia_faltante,
            )

    def assert_no_stage_skipped(self, executed_stages: list[str]) -> None:
        """Dentro del alcance, las etapas obligatorias se ejecutan en el orden
        declarado. Reusa `StageSkippedError`, ya definido en `kernel/errors.py`
        por el trabajo local previo a esta slice.
        """
        ejecutadas = [s for s in executed_stages if s in self.required_stages]
        indices = {stage: index for index, stage in enumerate(self.required_stages)}
        for previous_stage, current_stage in zip(ejecutadas, ejecutadas[1:]):
            previous_index = indices[previous_stage]
            current_index = indices[current_stage]
            if current_index != previous_index + 1:
                expected_index = previous_index + 1
                expected_stage = (
                    self.required_stages[expected_index]
                    if expected_index < len(self.required_stages)
                    else self.required_stages[-1]
                )
                raise StageSkippedError(
                    from_stage=previous_stage,
                    target_stage=current_stage,
                    expected_stage=expected_stage,
                )
