"""EventLogger en aislamiento (sin pasar por RunManager)."""
from __future__ import annotations

from kernel.events import EventLogger, EventType


def test_evento_tiene_forma_minima_exigida():
    logger = EventLogger()
    ev = logger.run_created("run-abc", status="PENDING")
    d = ev.to_dict()
    for campo in ("event_id", "run_id", "timestamp", "event_type", "stage", "status", "metadata"):
        assert campo in d
    assert d["run_id"] == "run-abc"
    assert d["event_type"] == "RUN_CREATED"


def test_cada_evento_tiene_un_id_distinto():
    logger = EventLogger()
    a = logger.error("run-abc", message="x")
    b = logger.error("run-abc", message="x")
    assert a.event_id != b.event_id


def test_tipos_de_evento_cubren_lo_minimo_pedido():
    tipos = {t.value for t in EventType}
    minimos = {"RUN_CREATED", "STATE_CHANGED", "STAGE_STARTED", "STAGE_COMPLETED", "ERROR", "BLOCKED"}
    assert minimos <= tipos
