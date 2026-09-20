"""Agent Contract -- forma minima comun a todo agente de la Factory.

Deliberadamente pequeño: FACTORY-SPEC.md Seccion 6 exige que Classifier,
Generator, Validator y Reviewer puedan implementarse "sin modificar
conceptualmente el Coordinator". Este contrato es la unica superficie que el
Coordinator conoce -- nunca importa una clase concreta de agente.

No depende de `kernel/` (evita un ciclo de imports: kernel es mas basico que
un agente) ni del ETL financiero.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    CLASSIFIER = "CLASSIFIER"
    GENERATOR = "GENERATOR"
    VALIDATOR = "VALIDATOR"
    REVIEWER = "REVIEWER"
    COORDINATOR = "COORDINATOR"


@dataclass(frozen=True)
class AgentMetadata:
    """Identidad y contrato declarado de un agente.

    `input_contract`/`output_contract` son descripciones (no un schema
    formal todavia -- FACTORY-SPEC.md no define uno; inventar uno aca seria
    una decision de arquitectura que le corresponde a la spec, no a este
    modulo). `enabled` es lo que el Registry consulta antes de dejar
    ejecutar al agente -- una forma minima de Guardrail (Seccion 11 de la
    spec), sin implementar el Guardrail completo todavia.
    """
    id: str
    name: str
    role: AgentRole
    input_contract: str
    output_contract: str
    enabled: bool = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AgentResult:
    """La evidencia minima de una ejecucion de agente (FACTORY-SPEC.md
    Seccion 12): agent_id, input, output, status, timestamp."""
    agent_id: str
    input: Any
    output: Any
    status: str  # "OK" | "ERROR" -- no PASS/WARNING/BLOCK todavia: eso es
                 # vocabulario de Validation (Fase 4), no de un Agent generico
    timestamp: str = field(default_factory=_now_iso)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "agent_id": self.agent_id,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "timestamp": self.timestamp,
        }


class BaseAgent(ABC):
    """Contrato que todo agente debe cumplir.

    `execute()` no debe lanzar excepciones por condiciones de negocio
    esperables (input vacio, input con forma incorrecta) -- debe devolver un
    AgentResult con status="ERROR". Reservar las excepciones para errores de
    programacion real (bug del propio agente), que el Coordinator no intenta
    manejar como un resultado de negocio.
    """

    metadata: AgentMetadata

    @abstractmethod
    def execute(self, input_data: Any) -> AgentResult:
        raise NotImplementedError
