"""Append-only project-isolated execution records (Memory M1a)."""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.identifiers import UnsafeIdentifierError, assert_safe_identifier, safe_child_path
from memory.execution_record import CURRENT_SCHEMA_VERSION, ExecutionRecord
from memory.locking import MemoryLockTimeoutError, exclusive_file_lock
from memory.redaction import record_to_safe_dict, safe_index_entry


class MemoryConfigurationError(ValueError):
    """MEMORY_ROOT was not configured explicitly."""


class MemoryWriteError(OSError):
    """An atomic sidecar or durable index write failed."""


class DuplicateExecutionError(ValueError):
    """The execution ID already exists in the append-only history."""


@dataclass(frozen=True)
class MemoryRecordReadResult:
    records: tuple[ExecutionRecord, ...]
    skipped_malformed: int
    skipped_reasons: tuple[str, ...]


class ExecutionStore:
    """JSONL append-only index plus atomic sidecar records.

    Pass memory_root explicitly or set MEMORY_ROOT. No inferred default is
    used. Network filesystems have not been verified and are not guaranteed.
    """
    def __init__(
        self,
        memory_root: str | Path | None = None,
        *,
        lock_timeout_seconds: float = 5.0,
        replace_attempts: int = 5,
        replace_backoff_seconds: float = 0.025,
    ) -> None:
        configured = memory_root if memory_root is not None else os.environ.get("MEMORY_ROOT")
        if configured is None or not str(configured).strip():
            raise MemoryConfigurationError(
                "MEMORY_ROOT must be configured explicitly or passed to ExecutionStore"
            )
        if lock_timeout_seconds < 0 or replace_attempts < 1 or replace_backoff_seconds < 0:
            raise MemoryConfigurationError("invalid lock or replace retry configuration")
        self.memory_root = Path(configured).expanduser().resolve()
        self.lock_timeout_seconds = lock_timeout_seconds
        self.replace_attempts = replace_attempts
        self.replace_backoff_seconds = replace_backoff_seconds

    def _project_dir(self, project_id: str) -> Path:
        assert_safe_identifier(project_id, label="project_id")
        project_dir = safe_child_path(self.memory_root, project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "records").mkdir(exist_ok=True)
        return project_dir

    def _record_path(self, project_dir: Path, execution_id: str) -> Path:
        assert_safe_identifier(execution_id, label="execution_id")
        records_dir = project_dir / "records"
        path = safe_child_path(records_dir, f"{execution_id}.json")
        records_dir.mkdir(parents=True, exist_ok=True)
        return path

    def _atomic_write(self, destination: Path, content: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
        )
        temporary = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(self.replace_attempts):
                try:
                    os.replace(temporary, destination)
                    return
                except PermissionError as exc:
                    if attempt + 1 == self.replace_attempts:
                        raise MemoryWriteError(
                            f"atomic replace failed for {destination} after "
                            f"{self.replace_attempts} attempts; no non-atomic fallback was attempted"
                        ) from exc
                    time.sleep(self.replace_backoff_seconds * (attempt + 1))
            raise MemoryWriteError(f"atomic replace failed for {destination}")
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _read_index_rows(path: Path) -> tuple[list[dict[str, Any]], int, list[str]]:
        if not path.exists():
            return [], 0, []
        rows: list[dict[str, Any]] = []
        skipped = 0
        reasons: list[str] = []
        with path.open("rb") as handle:
            for line_no, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw.decode("utf-8"))
                    if not isinstance(row, dict):
                        raise ValueError("index row is not an object")
                    if row.get("schema_version") != CURRENT_SCHEMA_VERSION:
                        raise ValueError(f"unsupported schema_version {row.get('schema_version')!r}")
                    rows.append(row)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    skipped += 1
                    reasons.append(f"index line {line_no}: {exc}")
        return rows, skipped, reasons

    def append(self, record: ExecutionRecord) -> Path:
        if not isinstance(record, ExecutionRecord):
            raise TypeError("append expects ExecutionRecord")
        project_dir = self._project_dir(record.project_id)
        record_path = self._record_path(project_dir, record.execution_id)
        index_path = project_dir / "index.jsonl"
        lock_path = project_dir / "index.jsonl.lock"
        record_bytes = json.dumps(
            record_to_safe_dict(record), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        index_bytes = json.dumps(
            safe_index_entry(record, record_path.name), ensure_ascii=False, sort_keys=True
        ).encode("utf-8") + b"\n"

        # Lock protects duplicate detection, sidecar creation and index append.
        with exclusive_file_lock(lock_path, self.lock_timeout_seconds):
            rows, _, _ = self._read_index_rows(index_path)
            if any(row.get("execution_id") == record.execution_id for row in rows):
                raise DuplicateExecutionError(
                    f"execution_id {record.execution_id!r} already exists in {record.project_id!r}"
                )
            if record_path.exists():
                raise DuplicateExecutionError(f"sidecar already exists for {record.execution_id!r}")
            self._atomic_write(record_path, record_bytes)
            try:
                with index_path.open("ab") as handle:
                    handle.write(index_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                # Preserve the sidecar; never silently delete historical data.
                raise MemoryWriteError(
                    f"sidecar persisted but index append failed for {record.execution_id!r}"
                ) from exc
        return record_path

    def read_records(self, project_id: str) -> MemoryRecordReadResult:
        project_dir = self._project_dir(project_id)
        rows, skipped, reasons = self._read_index_rows(project_dir / "index.jsonl")
        records: list[ExecutionRecord] = []
        for row in rows:
            execution_id = row.get("execution_id")
            try:
                if row.get("project_id") != project_id:
                    raise ValueError("index project_id mismatch")
                assert_safe_identifier(execution_id, label="execution_id")
                expected = self._record_path(project_dir, execution_id)
                if row.get("record_filename") != expected.name:
                    raise ValueError("record filename does not match execution_id")
                raw = json.loads(expected.read_text(encoding="utf-8"))
                record = ExecutionRecord.from_mapping(raw)
                if record.project_id != project_id or record.execution_id != execution_id:
                    raise ValueError("sidecar identity does not match index")
                records.append(ExecutionRecord.from_mapping(record_to_safe_dict(record)))
            except (OSError, ValueError, TypeError, UnsafeIdentifierError) as exc:
                skipped += 1
                reasons.append(f"execution {execution_id!r}: {exc}")
        return MemoryRecordReadResult(tuple(records), skipped, tuple(reasons))

    def load(self, project_id: str, execution_id: str) -> ExecutionRecord | None:
        assert_safe_identifier(project_id, label="project_id")
        assert_safe_identifier(execution_id, label="execution_id")
        result = self.read_records(project_id)
        return next((item for item in result.records if item.execution_id == execution_id), None)


__all__ = [
    "DuplicateExecutionError", "ExecutionStore", "MemoryConfigurationError",
    "MemoryRecordReadResult", "MemoryWriteError", "MemoryLockTimeoutError",
]
