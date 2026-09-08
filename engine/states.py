from __future__ import annotations

from enum import Enum


class StageState(str, Enum):
    PLANNED = "PLANNED"
    READY = "READY"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    FAILED = "FAILED"
    FIXING = "FIXING"
    RERUNNING = "RERUNNING"
    PASSED = "PASSED"
    CHECKPOINTED = "CHECKPOINTED"
    CERTIFIED = "CERTIFIED"
    # F10: el run padre murio (excepcion) mientras la etapa no tenia evidencia
    # propia todavia. NO es FAILED (FAILED implica que un gate corrio y hay un
    # StageReport). Terminal: nada sale de ABORTED (ver TRANSITIONS).
    ABORTED = "ABORTED"


class GateStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


# F10: ABORTED es alcanzable desde todo estado SIN evidencia propia todavia
# (nada de report/checkpoint/certificacion detras). PASSED/CHECKPOINTED/
# CERTIFIED nunca transicionan a ABORTED: ya tienen evidencia durable y un
# aborto de codigo no relacionado, mas tarde en el mismo run_scope, no puede
# retroactivamente borrarla. FAILED tampoco: FAILED YA es evidencia (goal un
# gate corrio y produjo un StageReport); no se mezcla con "murio sin decir
# nada". FIXING/RERUNNING si pueden abortar: ese intento puntual de reintento
# no dejo su propia evidencia, aunque el FAILED original (fila previa,
# inmutable) siga intacto en el historial.
TRANSITIONS: dict[StageState, set[StageState]] = {
    StageState.PLANNED: {StageState.READY, StageState.ABORTED},
    StageState.READY: {StageState.RUNNING, StageState.ABORTED},
    StageState.RUNNING: {StageState.VALIDATING, StageState.ABORTED},
    StageState.VALIDATING: {StageState.PASSED, StageState.FAILED, StageState.ABORTED},
    StageState.FAILED: {StageState.FIXING},
    StageState.FIXING: {StageState.RERUNNING, StageState.ABORTED},
    StageState.RERUNNING: {StageState.VALIDATING, StageState.ABORTED},
    StageState.PASSED: {StageState.CHECKPOINTED},
    StageState.CHECKPOINTED: {StageState.CERTIFIED},
    StageState.CERTIFIED: set(),
    StageState.ABORTED: set(),
}


def assert_transition(current: StageState, target: StageState) -> None:
    allowed = TRANSITIONS[current]
    if target not in allowed:
        raise ValueError(f"Transicion invalida {current.value} -> {target.value}; permitidas: {[s.value for s in allowed]}")
