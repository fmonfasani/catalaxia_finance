"""StateMachine -- estados y transiciones validas de un Run.

Estados y transiciones derivados de FACTORY-SPEC.md Seccion 8:

    pending -> running -> { blocked | failed | completed }
    completed -> { approved | rejected }
    blocked -> running          (una vez resuelta la condicion de bloqueo)
    failed -> running            (reintento explicito, no automatico)
    rejected -> pending           (vuelve al inicio de su etapa)

FACTORY-SPEC.md escribe los nombres en minuscula (prosa); este Kernel los usa
en mayuscula (`RunStatus`), siguiendo la convencion ya establecida en el
repositorio para maquinas de estado (`engine/states.py::StageState`, tambien
`str, Enum` en mayuscula). Es una normalizacion de forma, no de significado --
`test_state_machine.py::test_estados_coinciden_con_lo_que_menciona_la_spec`
verifica que el conjunto de nombres (case-insensitive) coincide exactamente
con lo que FACTORY-SPEC.md Seccion 8 menciona; si alguna vez difieren, ese
test falla y reporta la contradiccion en vez de dejarla pasar en silencio.

`approved` es terminal (no tiene salidas): representa el veredicto final de
Validation+Review sobre un artefacto `completed`. El pedido de Fase 2 prohibe
explicitamente `COMPLETED -> RUNNING`; esa transicion no existe en el mapa de
abajo (COMPLETED solo sale hacia APPROVED/REJECTED).
"""
from __future__ import annotations

from enum import Enum

from kernel.errors import InvalidTransitionError


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.RUNNING},
    RunStatus.RUNNING: {RunStatus.BLOCKED, RunStatus.FAILED, RunStatus.COMPLETED},
    RunStatus.BLOCKED: {RunStatus.RUNNING},
    RunStatus.FAILED: {RunStatus.RUNNING},
    RunStatus.COMPLETED: {RunStatus.APPROVED, RunStatus.REJECTED},
    RunStatus.APPROVED: set(),
    RunStatus.REJECTED: {RunStatus.PENDING},
}


class StateMachine:
    """Sin estado propio: valida transiciones sobre el `RunStatus` que le pasan.

    No decide POR el Run cuando transicionar -- eso lo pide `RunManager`,
    que a su vez actua solo cuando tiene evidencia (un Agent que termino, un
    error real, una aprobacion humana). El propio LLM nunca llama a esta
    clase para "decidir" un estado: la llama el codigo, con un estado destino
    ya determinado por una condicion externa concreta.
    """

    def is_valid(self, current: RunStatus, target: RunStatus) -> bool:
        return target in TRANSITIONS[current]

    def assert_valid(self, current: RunStatus, target: RunStatus) -> None:
        if not self.is_valid(current, target):
            raise InvalidTransitionError(
                current.value, target.value,
                {s.value for s in TRANSITIONS[current]},
            )

    def allowed_from(self, current: RunStatus) -> set[RunStatus]:
        return set(TRANSITIONS[current])

    def is_terminal(self, status: RunStatus) -> bool:
        return len(TRANSITIONS[status]) == 0
