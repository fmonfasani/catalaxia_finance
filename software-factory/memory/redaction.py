"""Allowlist serialization plus existing redaction as defense in depth."""
from __future__ import annotations

from typing import Any

from observability import redact_structure
from memory.execution_record import ExecutionRecord


def record_to_safe_dict(record: ExecutionRecord) -> dict[str, Any]:
    """Serialize only declared fields, then apply the existing key redactor.

    Free-text secret detection is not provided. M1a excludes raw prompts and
    arbitrary metadata; reference fields must contain references, not payloads.
    """
    return redact_structure(record.to_dict())


def safe_index_entry(record: ExecutionRecord, record_filename: str) -> dict[str, Any]:
    """Return the fixed, minimal index schema."""
    return redact_structure({
        "execution_id": record.execution_id,
        "project_id": record.project_id,
        "task_id": record.task_id,
        "task_hash": record.task_hash,
        "status": record.status,
        "repo": record.repo,
        "branch": record.branch,
        "sha": record.sha,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "schema_version": record.schema_version,
        "record_filename": record_filename,
    })
