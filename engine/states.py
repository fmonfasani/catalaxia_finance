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


class GateStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


TRANSITIONS: dict[StageState, set[StageState]] = {
    StageState.PLANNED: {StageState.READY},
    StageState.READY: {StageState.RUNNING},
    StageState.RUNNING: {StageState.VALIDATING},
    StageState.VALIDATING: {StageState.PASSED, StageState.FAILED},
    StageState.FAILED: {StageState.FIXING},
    StageState.FIXING: {StageState.RERUNNING},
    StageState.RERUNNING: {StageState.VALIDATING},
    StageState.PASSED: {StageState.CHECKPOINTED},
    StageState.CHECKPOINTED: {StageState.CERTIFIED},
    StageState.CERTIFIED: set(),
}


def assert_transition(current: StageState, target: StageState) -> None:
    allowed = TRANSITIONS[current]
    if target not in allowed:
        raise ValueError(f"Transicion invalida {current.value} -> {target.value}; permitidas: {[s.value for s in allowed]}")
