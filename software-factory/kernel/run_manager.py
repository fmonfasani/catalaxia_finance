"""RunManager -- crea y controla el ciclo de vida de una ejecucion (Run).

Es el unico componente que decide "avanzar" un Run, y solo lo hace cuando
quien lo llama le da una condicion externa concreta (un estado destino, una
etapa). RunManager nunca le pregunta a un LLM "que hacemos ahora" -- ese es
exactamente el principio de FACTORY-SPEC.md Seccion 2.1 ("el sistema controla
al LLM"): en este Kernel todavia no hay ningun LLM invocado, a proposito
(Fase 2 no implementa Agents).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from kernel.errors import UnknownStageError
from kernel.events import Event, EventLogger
from kernel.pipeline_definition import PipelineDefinition
from kernel.run_scope import RunScope
from kernel.state_machine import RunStatus, StateMachine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Run:
    run_id: str
    factory_version: str
    status: RunStatus
    current_stage: str
    created_at: str
    updated_at: str
    events: list[Event] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    # Fase 3: rastro de que agente corrio y que produjo. `evidence` es el
    # historial completo (append-only, como `events`); `last_agent`/
    # `last_result` son un acceso directo al ultimo, sin recorrer la lista --
    # es lo que el pedido de Fase 3 llama "agent"/"result" en el estado del
    # Run.
    evidence: list[dict[str, Any]] = field(default_factory=list)
    last_agent: str | None = None
    last_result: dict[str, Any] | None = None
    # DEC-SF-001: el contrato de completitud contra el que se evalua este Run.
    # Se persiste con el Run (no solo en memoria) para que la regla 6 se pueda
    # sostener: una version posterior del alcance no reescribe el contrato con
    # el que un Run historico ya fue completado.
    scope: "RunScope | None" = None
    # Etapas efectivamente ejecutadas y tests que realmente pasaron, en este
    # Run. Son la evidencia contra la que se verifica el contrato -- no se
    # infieren de los steps que trajo el llamador (DEC-SF-001 regla 4).
    executed_stages: list[str] = field(default_factory=list)
    passed_tests: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "factory_version": self.factory_version,
            "status": self.status.value,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events": [e.to_dict() for e in self.events],
            "artifacts": self.artifacts,
            "evidence": self.evidence,
            "agent": self.last_agent,
            "result": self.last_result,
            "scope": self.scope.to_dict() if self.scope else None,
            "executed_stages": list(self.executed_stages),
            "passed_tests": list(self.passed_tests),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Run":
        # Reconstruye solo lo que el Kernel necesita para seguir operando el
        # Run (status/stage/timestamps); los events ya persistidos se
        # conservan como dicts crudos -- no hace falta revivirlos como
        # objetos Event para leer el historial.
        run = cls(
            run_id=d["run_id"],
            factory_version=d["factory_version"],
            status=RunStatus(d["status"]),
            current_stage=d["current_stage"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            artifacts=d.get("artifacts", []),
            evidence=d.get("evidence", []),
            last_agent=d.get("agent"),
            last_result=d.get("result"),
            # Compatibilidad hacia atras: un Run persistido ANTES de DEC-SF-001
            # no tiene estas claves. Se cargan como None/vacio en vez de fallar
            # -- la decision no invalida retroactivamente Runs historicos.
            scope=RunScope.from_dict(d["scope"]) if d.get("scope") else None,
            executed_stages=list(d.get("executed_stages", [])),
            passed_tests=list(d.get("passed_tests", [])),
        )
        run._raw_events = d.get("events", [])  # type: ignore[attr-defined]
        return run


class RunManager:
    """Orquesta Run + StateMachine + PipelineDefinition + EventLogger.

    No persiste nada por si mismo -- quien la usa decide cuando llamar a
    StateManager.save() con el resultado de to_dict(). Mantenerlos separados
    permite testear la logica de transiciones sin filesystem de por medio.
    """

    def __init__(self, pipeline: PipelineDefinition, factory_version: str):
        self.pipeline = pipeline
        self.factory_version = factory_version
        self.state_machine = StateMachine()
        self.event_logger = EventLogger()

    def create_run(self, scope: RunScope | None = None) -> Run:
        """Crea un Run. `scope` (DEC-SF-001, opcional) declara el contrato de
        completitud contra el que se evaluara.

        El default `None` preserva la firma previa: quien use `execute_stage()`
        o cree Runs sin alcance declarado sigue funcionando exactamente igual.
        Lo que DEC-SF-001 cambia es que `execute_pipeline()` ya no puede
        declarar COMPLETED sin un contrato -- no que crear un Run lo exija.

        El alcance se valida contra la `PipelineDefinition` real al crearse,
        no al terminar: un contrato malformado se rechaza antes de ejecutar
        nada (fail-closed).
        """
        if scope is not None:
            scope.validate_against(self.pipeline)
        run_id = str(uuid.uuid4())
        now = _now_iso()
        first_stage = self.pipeline.first_stage()
        run = Run(
            run_id=run_id,
            factory_version=self.factory_version,
            status=RunStatus.PENDING,
            current_stage=first_stage,
            created_at=now,
            updated_at=now,
            scope=scope,
        )
        run.events.append(self.event_logger.run_created(run_id, status=RunStatus.PENDING.value))
        return run

    def transition(self, run: Run, target: RunStatus, *, parent_event_id: str | None = None) -> Run:
        """Cambia `run.status` a `target` si la transicion es valida.

        Levanta InvalidTransitionError si no lo es -- y ese intento invalido
        queda igual registrado como evento ERROR antes de propagar la
        excepcion, para que quede trazable incluso lo que el Kernel rechazo
        (requisito: "mantener trazabilidad de eventos", tambien de los
        intentos invalidos, no solo de los que tuvieron exito).

        Fase 4A: ademas de STATE_CHANGED (Fase 2, sin cambios), emite el
        evento de "veredicto de Run" que corresponda cuando la transicion
        cruza un umbral semantico: PENDING->RUNNING es RUN_STARTED,
        ->APPROVED es RUN_COMPLETED, ->REJECTED es RUN_FAILED. Son eventos
        de OBSERVABILIDAD derivados de la transicion -- la transicion en si
        sigue siendo la unica fuente de verdad de `run.status` (Seccion
        "Audit vs Observability" de OBSERVABILITY.md: la Observabilidad
        registra lo ocurrido, no lo decide).

        `parent_event_id` (Fase 4A, opcional): quien orquesto esta
        transicion (tipicamente el COORDINATOR_STARTED de la llamada en
        curso). Sin esto, una transicion pedida por el Coordinator quedaria
        como una raiz suelta en el Trace en vez de un hijo de esa
        orquestacion -- exactamente el caso que
        `test_parent_event_id_permite_reconstruir_relaciones` verifica."""
        try:
            self.state_machine.assert_valid(run.status, target)
        except Exception as exc:
            run.events.append(self.event_logger.error(
                run.run_id, message=str(exc), stage=run.current_stage,
                status=run.status.value,
            ))
            run.updated_at = _now_iso()
            raise
        previous = run.status
        run.status = target
        run.updated_at = _now_iso()
        run.events.append(self.event_logger.state_changed(
            run.run_id, from_status=previous.value, to_status=target.value,
            stage=run.current_stage, parent_event_id=parent_event_id,
        ))
        if previous is RunStatus.PENDING and target is RunStatus.RUNNING:
            run.events.append(self.event_logger.run_started(
                run.run_id, stage=run.current_stage, parent_event_id=parent_event_id))
        if target is RunStatus.BLOCKED:
            run.events.append(self.event_logger.blocked(
                run.run_id, reason="transicion a BLOCKED sin motivo explicito",
                stage=run.current_stage, parent_event_id=parent_event_id,
            ))
        if target is RunStatus.APPROVED:
            run.events.append(self.event_logger.run_completed(
                run.run_id, stage=run.current_stage, parent_event_id=parent_event_id))
        if target is RunStatus.REJECTED:
            run.events.append(self.event_logger.run_failed(
                run.run_id, stage=run.current_stage, parent_event_id=parent_event_id))
        return run

    def emit(self, run: Run, event: Event) -> Run:
        """Punto unico por el que un componente EXTERNO al Kernel
        (Coordinator, y a futuro un Agent) agrega un evento al Run.

        El Coordinator nunca hace `run.events.append(...)` directo -- llama
        a `EventLogger` para CONSTRUIR el evento (Fase 4A agrego los
        builders `coordinator_started`, `agent_selected`, etc.) y a este
        metodo para REGISTRARLO. Mantiene una sola responsabilidad
        (RunManager posee `run.events`), evita que dos mecanismos distintos
        escriban al mismo lugar."""
        run.events.append(event)
        run.updated_at = _now_iso()
        return run

    def advance_stage(self, run: Run, target_stage: str, *,
                      parent_event_id: str | None = None) -> Run:
        """Mueve `run.current_stage` a `target_stage`. Requiere que la etapa
        exista en el Pipeline (Seccion 7) -- nunca se ejecuta una etapa
        inexistente (requisito explicito de validacion).

        `parent_event_id` (Fase 5C, opcional): igual que en `transition()`
        (Fase 4A), permite encadenar STAGE_COMPLETED/STAGE_STARTED al
        COORDINATOR_STARTED que orquesta un avance de etapa DENTRO de la
        misma orquestacion (`Coordinator.execute_pipeline()`) -- sin esto,
        un avance de etapa pedido a mitad de un pipeline de varias etapas
        quedaria como una raiz suelta en el Trace en vez de un hijo de esa
        orquestacion. Default `None` preserva el comportamiento exacto de
        todas las fases anteriores (que nunca pasaban este argumento)."""
        self.pipeline.assert_known(target_stage)
        previous_stage = run.current_stage
        run.events.append(self.event_logger.stage_completed(
            run.run_id, stage=previous_stage, status=run.status.value,
            parent_event_id=parent_event_id,
        ))
        run.current_stage = target_stage
        run.updated_at = _now_iso()
        run.events.append(self.event_logger.stage_started(
            run.run_id, stage=target_stage, status=run.status.value,
            parent_event_id=parent_event_id,
        ))
        return run

    def record_evidence(self, run: Run, *, agent_id: str, evidence: dict[str, Any],
                        parent_event_id: str | None = None,
                        artifact_id: str | None = None) -> Run:
        """Unico punto por el que algo externo (el Coordinator) le agrega
        evidencia a un Run. El Coordinator nunca hace `run.evidence.append`
        directo -- pasa siempre por aca, para que quede loggeado como evento
        y para que `last_agent`/`last_result` se mantengan consistentes con
        el ultimo elemento de `evidence` sin que el llamador tenga que
        acordarse de actualizar los tres a mano.

        `parent_event_id` (Fase 4A, opcional): permite encadenar este evento
        al COORDINATOR_STARTED que lo origino, para que un Trace pueda
        reconstruir la relacion sin inferencia.

        `artifact_id` (Fase 4B, opcional): si el agente produjo un Artifact,
        queda referenciado en este mismo evento -- Evidence y Artifact
        correlacionados sin un mecanismo aparte."""
        run.evidence.append(evidence)
        run.last_agent = agent_id
        run.last_result = evidence
        run.updated_at = _now_iso()
        run.events.append(self.event_logger.evidence_recorded(
            run.run_id, agent_id=agent_id, stage=run.current_stage,
            status=evidence.get("status", run.status.value), evidence=evidence,
            parent_event_id=parent_event_id, artifact_id=artifact_id,
        ))
        return run

    def record_artifact(self, run: Run, artifact: dict[str, Any]) -> Run:
        """Unico punto por el que se agrega un Artifact a `run.artifacts`
        (el placeholder que la Fase 2 ya declaraba, sin conectar). Como
        `record_evidence`, el Coordinator nunca hace
        `run.artifacts.append(...)` a mano."""
        run.artifacts.append(artifact)
        run.updated_at = _now_iso()
        return run
