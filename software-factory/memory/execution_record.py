"""Allowlisted immutable execution-record contract for Memory M1a."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar

from kernel.identifiers import UnsafeIdentifierError, assert_safe_identifier

CURRENT_SCHEMA_VERSION = 1
ALLOWED_STATUSES = frozenset({"COMPLETED", "FAILED", "INTERRUPTED", "UNKNOWN"})


class ExecutionRecordError(ValueError):
    """Execution record does not satisfy the M1a contract."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_execution_id(run_id: str | None = None) -> str:
    """Reuse a safe run_id; otherwise generate a new UUID."""
    if isinstance(run_id, str):
        try:
            assert_safe_identifier(run_id, label="run_id")
            return run_id
        except UnsafeIdentifierError:
            pass
    return str(uuid.uuid4())


def task_fingerprint(task_text: str) -> str:
    """Hash task text without persisting the text itself."""
    if not isinstance(task_text, str) or not task_text.strip():
        raise ExecutionRecordError("task_text must be a non-empty string")
    return hashlib.sha256(task_text.encode("utf-8")).hexdigest()


def _required(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionRecordError(f"{name} must be a non-empty string")


def _timestamp(name: str, value: str | None, required: bool) -> None:
    if value is None:
        if required:
            raise ExecutionRecordError(f"{name} is required")
        return
    _required(name, value)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionRecordError(f"{name} must be ISO-8601") from exc


@dataclass(frozen=True)
class ExecutionRecord:
    """Explicit field allowlist; raw prompts and arbitrary payloads are excluded."""
    execution_id: str
    project_id: str
    task_id: str
    agent_id: str
    status: str
    repo: str
    branch: str
    sha: str
    started_at: str
    ended_at: str | None
    inputs_ref: str | None = None
    outputs_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    validation_ref: str | None = None
    findings_ref: str | None = None
    failure_ref: str | None = None
    task_hash: str | None = None
    factory_version: str = "unknown"
    contract_versions: tuple[str, ...] = ()
    schema_version: int = CURRENT_SCHEMA_VERSION

    ALLOWED_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "execution_id", "project_id", "task_id", "agent_id", "status",
        "repo", "branch", "sha", "started_at", "ended_at", "inputs_ref",
        "outputs_ref", "evidence_refs", "artifact_refs", "validation_ref",
        "findings_ref", "failure_ref", "task_hash", "factory_version",
        "contract_versions", "schema_version",
    })

    def __post_init__(self) -> None:
        for name in ("execution_id", "project_id"):
            _required(name, getattr(self, name))
            try:
                assert_safe_identifier(getattr(self, name), label=name)
            except UnsafeIdentifierError as exc:
                raise ExecutionRecordError(str(exc)) from exc
        for name in ("task_id", "agent_id", "repo", "branch", "sha", "factory_version"):
            _required(name, getattr(self, name))
        if self.status not in ALLOWED_STATUSES:
            raise ExecutionRecordError(f"invalid status: {self.status!r}")
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise ExecutionRecordError("schema_version must be an integer")
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise ExecutionRecordError(f"unsupported schema_version {self.schema_version!r}")
        _timestamp("started_at", self.started_at, True)
        _timestamp("ended_at", self.ended_at, False)
        if self.status in {"COMPLETED", "FAILED"} and self.ended_at is None:
            raise ExecutionRecordError(f"{self.status} requires ended_at")
        for name in ("evidence_refs", "artifact_refs", "contract_versions"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ExecutionRecordError(f"{name} must be a tuple of non-empty strings")
        for name in (
            "inputs_ref", "outputs_ref", "validation_ref", "findings_ref",
            "failure_ref", "task_hash",
        ):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ExecutionRecordError(f"{name} must be None or a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        # Explicit construction ensures fields added to the class are not
        # persisted until deliberately added to the allowlist and serializer.
        return {
            "execution_id": self.execution_id, "project_id": self.project_id,
            "task_id": self.task_id, "agent_id": self.agent_id, "status": self.status,
            "repo": self.repo, "branch": self.branch, "sha": self.sha,
            "started_at": self.started_at, "ended_at": self.ended_at,
            "inputs_ref": self.inputs_ref, "outputs_ref": self.outputs_ref,
            "evidence_refs": list(self.evidence_refs), "artifact_refs": list(self.artifact_refs),
            "validation_ref": self.validation_ref, "findings_ref": self.findings_ref,
            "failure_ref": self.failure_ref, "task_hash": self.task_hash,
            "factory_version": self.factory_version,
            "contract_versions": list(self.contract_versions),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ExecutionRecord":
        if not isinstance(value, dict):
            raise ExecutionRecordError("record must be a JSON object")
        version = value.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise ExecutionRecordError(f"unsupported schema_version {version!r}")
        fields = {key: value[key] for key in cls.ALLOWED_FIELDS if key in value}
        for name in ("evidence_refs", "artifact_refs", "contract_versions"):
            if isinstance(fields.get(name), list):
                fields[name] = tuple(fields[name])
        try:
            return cls(**fields)
        except TypeError as exc:
            raise ExecutionRecordError(f"invalid record fields: {exc}") from exc
