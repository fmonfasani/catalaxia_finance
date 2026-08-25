from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from engine.states import GateStatus


@dataclass
class StageReport:
    stage: str
    run_id: str
    mode: str
    started_at: str
    finished_at: str
    gate: GateStatus
    input_checkpoint_id: str | None
    input_rows: int
    expected: int
    parsed: int
    rejected: int
    rejected_by_reason: dict[str, int] = field(default_factory=dict)
    hash_in: str | None = None
    hash_out: str | None = None
    gate_reasons: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    nulls_count: int = 0
    nulls_by_reason: dict[str, int] = field(default_factory=dict)
    parser_version: str | None = None
    script: str | None = None
    git_commit: str | None = None

    REQUIRED_TEXT = (
        "stage", "run_id", "mode", "started_at", "finished_at",
        "input_checkpoint_id", "input_rows", "expected", "parsed", "rejected",
        "hash_in", "hash_out", "parser_version", "script",
    )

    def validate(self) -> None:
        missing = [name for name in self.REQUIRED_TEXT if getattr(self, name) in (None, "")]
        if missing:
            raise ValueError(f"Reporte incompleto, campos obligatorios ausentes: {missing}")
        if not self.checks:
            raise ValueError("Reporte sin checks: 'termino sin excepcion' nunca es PASS (norma del proyecto)")
        if self.gate is GateStatus.PASS:
            failed_blocks = [c for c in self.checks if c.get("result") == "FAIL" and c.get("blocking")]
            if failed_blocks:
                raise ValueError(f"Gate PASS con checks bloqueantes fallidos: {[c['id'] for c in failed_blocks]}")
        if self.expected != self.parsed + self.rejected:
            raise ValueError(
                f"Conciliacion invalida: expected({self.expected}) != parsed({self.parsed}) + rejected({self.rejected})"
            )

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "run_id": self.run_id,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "input": {"checkpoint_id": self.input_checkpoint_id, "rows": self.input_rows},
            "coverage": {
                "expected": self.expected,
                "parsed": self.parsed,
                "rejected": self.rejected,
                "by_reason": self.rejected_by_reason,
            },
            "integrity": {"hash_in": self.hash_in, "hash_out": self.hash_out},
            "gate": {"status": self.gate.value, "reasons": self.gate_reasons, "checks": self.checks},
            "nulls": {"count": self.nulls_count, "by_null_reason": self.nulls_by_reason},
            "code": {
                "git_commit": self.git_commit,
                "parser_version": self.parser_version,
                "script": self.script,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
