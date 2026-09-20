"""EventLogger -- registro de eventos de una ejecucion (Run).

Cada evento permite reconstruir que ocurrio sin inferencia (FACTORY-SPEC.md
Seccion 13, Audit). El Kernel no decide el CONTENIDO de negocio de un evento
(eso lo aportara, mas adelante, el Agent o el Coordinator que lo dispare) --
solo garantiza su forma minima y su orden de aparicion.

Fase 4A (observabilidad transversal): se EXTIENDE este mismo modulo -- no se
crea un `TraceEvent` paralelo. `Event` gana los campos de correlacion que la
observabilidad necesita (`component`, `component_id`, `parent_event_id`,
`input_reference`, `output_reference`), todos opcionales (default `None`)
para no romper ningun evento ya emitido por la Fase 2/3. `EventLogger` gana
metodos nuevos para los EventType nuevos -- los que ya existian
(`RUN_CREATED`, `STATE_CHANGED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `ERROR`,
`BLOCKED`, `EVIDENCE_RECORDED`) se REUSAN tal cual, no se duplican.

Decision explicita: "STAGE_BLOCKED"/"STAGE_FAILED" (pedidos en Fase 4A) NO se
agregan como EventType nuevos -- ya son representables con los existentes
`BLOCKED`/`ERROR` mas el campo `stage` que `Event` ya tenia desde la Fase 2.
Agregar un tipo nuevo para lo mismo violaria "no duplicar mecanismos".
"STATE_TRANSITION" tampoco se agrega -- es lo que `STATE_CHANGED` ya
representa, con otro nombre.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    RUN_CREATED = "RUN_CREATED"
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    STATE_CHANGED = "STATE_CHANGED"
    STAGE_STARTED = "STAGE_STARTED"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    COORDINATOR_STARTED = "COORDINATOR_STARTED"
    COORDINATOR_COMPLETED = "COORDINATOR_COMPLETED"
    AGENT_SELECTED = "AGENT_SELECTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


class Component(str, Enum):
    """Quien emitio el evento -- el eje "component" de correlacion pedido en
    Fase 4A. No es un Enum cerrado desde afuera (Coordinator/Agent pueden
    pasar cualquier string como `component_id`), pero estos tres son los
    unicos "component" (no component_id) que existen hoy."""
    KERNEL = "KERNEL"
    COORDINATOR = "COORDINATOR"
    AGENT = "AGENT"


@dataclass(frozen=True)
class Event:
    event_id: str
    run_id: str
    timestamp: str
    event_type: EventType
    stage: str | None
    status: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Fase 4A -- correlacion transversal. Todos opcionales: un evento de
    # Fase 2/3 reconstruido desde disco simplemente los trae en None.
    component: str | None = None
    component_id: str | None = None
    parent_event_id: str | None = None
    input_reference: str | None = None
    output_reference: str | None = None
    # Fase 4B -- un evento puede referenciar el Artifact que produjo/afecto.
    artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "stage": self.stage,
            "status": self.status,
            "metadata": self.metadata,
            "component": self.component,
            "component_id": self.component_id,
            "parent_event_id": self.parent_event_id,
            "input_reference": self.input_reference,
            "output_reference": self.output_reference,
            "artifact_id": self.artifact_id,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLogger:
    """Construye Events con forma consistente. No los persiste -- eso es
    StateManager, junto con el resto del Run. No decide el orden en que se
    emiten -- eso lo decide quien llama (RunManager, Coordinator)."""

    def _build(self, run_id: str, event_type: EventType, *, stage: str | None = None,
              status: str | None = None, metadata: dict[str, Any] | None = None,
              component: str | None = None, component_id: str | None = None,
              parent_event_id: str | None = None, input_reference: str | None = None,
              output_reference: str | None = None, artifact_id: str | None = None) -> Event:
        return Event(
            event_id=str(uuid.uuid4()),
            run_id=run_id,
            timestamp=_now_iso(),
            event_type=event_type,
            stage=stage,
            status=status,
            metadata=metadata or {},
            component=component,
            component_id=component_id,
            parent_event_id=parent_event_id,
            input_reference=input_reference,
            output_reference=output_reference,
            artifact_id=artifact_id,
        )

    # ------------------------------------------------------ Kernel (Fase 2)

    def run_created(self, run_id: str, *, status: str) -> Event:
        return self._build(run_id, EventType.RUN_CREATED, status=status,
                           component=Component.KERNEL.value)

    def run_started(self, run_id: str, *, stage: str, parent_event_id: str | None = None) -> Event:
        return self._build(run_id, EventType.RUN_STARTED, stage=stage,
                           status="RUNNING", component=Component.KERNEL.value,
                           parent_event_id=parent_event_id)

    def run_completed(self, run_id: str, *, stage: str, parent_event_id: str | None = None) -> Event:
        return self._build(run_id, EventType.RUN_COMPLETED, stage=stage,
                           status="APPROVED", component=Component.KERNEL.value,
                           parent_event_id=parent_event_id)

    def run_failed(self, run_id: str, *, stage: str, parent_event_id: str | None = None) -> Event:
        return self._build(run_id, EventType.RUN_FAILED, stage=stage,
                           status="REJECTED", component=Component.KERNEL.value,
                           parent_event_id=parent_event_id)

    def state_changed(self, run_id: str, *, from_status: str, to_status: str,
                      stage: str | None = None, parent_event_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.STATE_CHANGED, stage=stage, status=to_status,
            metadata={"from_status": from_status, "to_status": to_status},
            component=Component.KERNEL.value, parent_event_id=parent_event_id,
        )

    def stage_started(self, run_id: str, *, stage: str, status: str,
                      parent_event_id: str | None = None) -> Event:
        return self._build(run_id, EventType.STAGE_STARTED, stage=stage, status=status,
                           component=Component.KERNEL.value, parent_event_id=parent_event_id)

    def stage_completed(self, run_id: str, *, stage: str, status: str,
                        parent_event_id: str | None = None) -> Event:
        return self._build(run_id, EventType.STAGE_COMPLETED, stage=stage, status=status,
                           component=Component.KERNEL.value, parent_event_id=parent_event_id)

    def error(self, run_id: str, *, message: str, stage: str | None = None,
             status: str | None = None, component: str | None = None,
             parent_event_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.ERROR, stage=stage, status=status,
            metadata={"message": message},
            component=component or Component.KERNEL.value,
            parent_event_id=parent_event_id,
        )

    def blocked(self, run_id: str, *, reason: str, stage: str | None = None,
               parent_event_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.BLOCKED, stage=stage, status="BLOCKED",
            metadata={"reason": reason}, component=Component.KERNEL.value,
            parent_event_id=parent_event_id,
        )

    def evidence_recorded(self, run_id: str, *, agent_id: str, stage: str,
                          status: str, evidence: dict[str, Any],
                          parent_event_id: str | None = None,
                          artifact_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.EVIDENCE_RECORDED, stage=stage, status=status,
            metadata={"agent_id": agent_id, "evidence": evidence},
            component=Component.KERNEL.value, component_id=agent_id,
            parent_event_id=parent_event_id, artifact_id=artifact_id,
        )

    # ------------------------------------------------- Coordinator (Fase 4A)

    def coordinator_started(self, run_id: str, *, stage: str) -> Event:
        return self._build(run_id, EventType.COORDINATOR_STARTED, stage=stage,
                           status="RUNNING", component=Component.COORDINATOR.value)

    def coordinator_completed(self, run_id: str, *, stage: str, status: str,
                              parent_event_id: str | None = None) -> Event:
        return self._build(run_id, EventType.COORDINATOR_COMPLETED, stage=stage,
                           status=status, component=Component.COORDINATOR.value,
                           parent_event_id=parent_event_id)

    def agent_selected(self, run_id: str, *, stage: str, agent_id: str,
                       parent_event_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.AGENT_SELECTED, stage=stage, status=None,
            component=Component.COORDINATOR.value, component_id=agent_id,
            parent_event_id=parent_event_id,
            metadata={"reason": "unico agente autorizado por FACTORY-SPEC.md Seccion 7 para esta etapa"},
        )

    # -------------------------------------------------------- Agent (Fase 4A)

    def agent_started(self, run_id: str, *, stage: str, agent_id: str,
                      input_reference: str, parent_event_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.AGENT_STARTED, stage=stage, status="RUNNING",
            component=Component.AGENT.value, component_id=agent_id,
            input_reference=input_reference, parent_event_id=parent_event_id,
        )

    def agent_completed(self, run_id: str, *, stage: str, agent_id: str,
                        output_reference: str, parent_event_id: str | None = None,
                        artifact_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.AGENT_COMPLETED, stage=stage, status="OK",
            component=Component.AGENT.value, component_id=agent_id,
            output_reference=output_reference, parent_event_id=parent_event_id,
            artifact_id=artifact_id,
        )

    def agent_failed(self, run_id: str, *, stage: str, agent_id: str,
                     output_reference: str | None = None,
                     parent_event_id: str | None = None) -> Event:
        return self._build(
            run_id, EventType.AGENT_FAILED, stage=stage, status="ERROR",
            component=Component.AGENT.value, component_id=agent_id,
            output_reference=output_reference, parent_event_id=parent_event_id,
        )
