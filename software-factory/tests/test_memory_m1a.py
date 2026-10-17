"""M1a tests: records, project isolation, atomic writes and real process locking."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kernel.identifiers import UnsafeIdentifierError
from memory.execution_record import (
    CURRENT_SCHEMA_VERSION, ExecutionRecord, ExecutionRecordError,
    new_execution_id, task_fingerprint,
)
from memory.locking import MemoryLockTimeoutError, exclusive_file_lock
from memory.store import (
    DuplicateExecutionError, ExecutionStore, MemoryConfigurationError, MemoryWriteError,
)


def make_record(**overrides) -> ExecutionRecord:
    values = {
        "execution_id": "run-001", "project_id": "project-a",
        "task_id": "task-memory-m1a", "agent_id": "implementer",
        "status": "COMPLETED", "repo": "fmonfasani/catalaxia_finance",
        "branch": "feat/software-factory-memory-m1a",
        "sha": "acd5b9d7f865e8ec354e05db258d192d96ce1ee4",
        "started_at": "2026-10-17T09:00:00+00:00",
        "ended_at": "2026-10-17T10:00:00+00:00",
        "inputs_ref": "evidence:input-001", "outputs_ref": "artifact:output-001",
        "evidence_refs": ("evidence:001",), "artifact_refs": ("artifact:001",),
        "task_hash": task_fingerprint("implement execution memory"),
        "factory_version": "0.1.0", "contract_versions": ("artifact-shape:1",),
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    values.update(overrides)
    return ExecutionRecord(**values)


def test_round_trip_structural(tmp_path):
    store = ExecutionStore(tmp_path / "memory")
    original = make_record()
    store.append(original)
    result = store.read_records("project-a")
    assert result.skipped_malformed == 0
    assert result.records[0].to_dict() == original.to_dict()


def test_concurrent_processes_append_without_corruption(tmp_path):
    root = tmp_path / "shared-memory"
    factory_root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from memory.execution_record import ExecutionRecord
from memory.store import ExecutionStore
root, worker, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
store = ExecutionStore(root)
for i in range(count):
    store.append(ExecutionRecord(
        execution_id=f"worker-{worker}-{i}", project_id="concurrency-project",
        task_id=f"task-{worker}", agent_id="worker", status="COMPLETED",
        repo="owner/repo", branch="test", sha="0123456789abcdef",
        started_at="2026-10-17T09:00:00+00:00",
        ended_at="2026-10-17T09:00:01+00:00",
    ))
'''
    workers, per_worker = 6, 25
    env = os.environ.copy()
    old = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(factory_root) + (os.pathsep + old if old else "")
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(root), str(worker), str(per_worker)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for worker in range(workers)
    ]
    failures = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        if process.returncode:
            failures.append((process.returncode, stdout, stderr))
    assert failures == []
    index = root / "concurrency-project" / "index.jsonl"
    lines = index.read_bytes().splitlines()
    assert len(lines) == workers * per_worker
    assert all(isinstance(json.loads(line), dict) for line in lines)
    result = ExecutionStore(root).read_records("concurrency-project")
    assert len(result.records) == workers * per_worker
    assert result.skipped_malformed == 0


def test_atomic_replace_failure_preserves_previous_destination(tmp_path, monkeypatch):
    store = ExecutionStore(tmp_path / "memory", replace_attempts=1)
    destination = tmp_path / "memory" / "project-a" / "records" / "record.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"previous": true}', encoding="utf-8")
    def fail_replace(_source, _destination):
        raise PermissionError("simulated Windows open-reader lock")
    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(MemoryWriteError, match="atomic replace failed"):
        store._atomic_write(destination, b'{"new": true}')
    assert json.loads(destination.read_text(encoding="utf-8")) == {"previous": True}


def test_replace_reader_lock_never_uses_non_atomic_fallback(tmp_path, monkeypatch):
    store = ExecutionStore(tmp_path / "memory", replace_attempts=1)
    destination = tmp_path / "memory" / "project-a" / "records" / "record.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"old": 1}', encoding="utf-8")
    calls = []
    def fail_replace(source, target):
        calls.append((source, target))
        raise PermissionError("reader has file open")
    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(MemoryWriteError):
        store._atomic_write(destination, b'{"new": 2}')
    assert len(calls) == 1
    assert json.loads(destination.read_text(encoding="utf-8")) == {"old": 1}


def test_malformed_partial_and_future_schema_rows_are_skipped(tmp_path):
    store = ExecutionStore(tmp_path / "memory")
    store.append(make_record())
    index = tmp_path / "memory" / "project-a" / "index.jsonl"
    with index.open("ab") as handle:
        handle.write(b'{"broken":\n')
        handle.write(b'{"schema_version":999,"execution_id":"future"}\n')
    result = store.read_records("project-a")
    assert len(result.records) == 1
    assert result.skipped_malformed == 2
    assert any("schema_version" in reason for reason in result.skipped_reasons)


@pytest.mark.parametrize("project_id", ["../escape", "..", "", "a/b", "a\\b"])
def test_project_path_traversal_is_rejected(tmp_path, project_id):
    with pytest.raises((UnsafeIdentifierError, ExecutionRecordError)):
        make_record(project_id=project_id)


@pytest.mark.parametrize("execution_id", ["../escape", "..", "", "a/b", "a\\b"])
def test_execution_path_traversal_is_rejected(tmp_path, execution_id):
    with pytest.raises((UnsafeIdentifierError, ExecutionRecordError)):
        make_record(execution_id=execution_id)


def test_index_append_preserves_existing_prefix(tmp_path):
    store = ExecutionStore(tmp_path / "memory")
    store.append(make_record(execution_id="first"))
    index = tmp_path / "memory" / "project-a" / "index.jsonl"
    first_before = index.read_bytes().splitlines(keepends=True)[0]
    before_hash = hashlib.sha256(first_before).hexdigest()
    store.append(make_record(execution_id="second"))
    first_after = index.read_bytes().splitlines(keepends=True)[0]
    assert first_after == first_before
    assert hashlib.sha256(first_after).hexdigest() == before_hash


def test_safe_run_id_reuse_and_unsafe_fallback():
    assert new_execution_id("safe-run_01") == "safe-run_01"
    assert new_execution_id("../unsafe") != "../unsafe"
    assert len(new_execution_id("../unsafe")) == 36


def test_memory_root_and_required_metadata_are_explicit(monkeypatch):
    monkeypatch.delenv("MEMORY_ROOT", raising=False)
    with pytest.raises(MemoryConfigurationError):
        ExecutionStore()
    with pytest.raises(ExecutionRecordError):
        make_record(task_id="")


def test_open_execution_cannot_be_reported_as_completed():
    with pytest.raises(ExecutionRecordError):
        make_record(status="COMPLETED", ended_at=None)
    interrupted = make_record(status="INTERRUPTED", ended_at=None)
    assert interrupted.status == "INTERRUPTED"


def test_allowlist_prevents_unknown_fields_from_being_persisted(tmp_path):
    store = ExecutionStore(tmp_path / "memory")
    record = make_record()
    store.append(record)
    path = tmp_path / "memory" / "project-a" / "records" / "run-001.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["pat"] = "ghp_SHOULD_NOT_PERSIST"
    from memory.execution_record import ExecutionRecord as Record
    safe = Record.from_mapping(raw).to_dict()
    assert "pat" not in safe
    assert "ghp_SHOULD_NOT_PERSIST" not in json.dumps(safe)


def test_sensitive_key_redactor_is_reused():
    from observability import redact_structure
    result = redact_structure({"api_key": "sk-SECRET", "nested": [{"password": "secret"}]})
    assert result["api_key"].startswith("<REDACTED:sha256:")
    assert result["nested"][0]["password"].startswith("<REDACTED:sha256:")


def test_free_text_secret_limit_is_explicit():
    # The existing key-based redactor does not scan free text.
    from observability import redact_structure
    value = {"note": "my api key is sk-LEAK-999"}
    assert redact_structure(value) == value


def test_redaction_does_not_mutate_input():
    from observability import redact_structure
    value = {"nested": [{"api_key": "sk-SECRET"}]}
    before = json.loads(json.dumps(value))
    redact_structure(value)
    assert value == before


def test_lock_timeout_is_named(tmp_path):
    lock = tmp_path / "index.lock"
    with exclusive_file_lock(lock):
        with pytest.raises(MemoryLockTimeoutError):
            with exclusive_file_lock(lock, timeout_seconds=0):
                pass


def test_store_writes_under_explicit_root_not_legacy_runs(tmp_path):
    store = ExecutionStore(tmp_path / "memory")
    path = store.append(make_record())
    legacy_runs = Path(__file__).resolve().parents[1] / "runs"
    assert path.is_relative_to((tmp_path / "memory").resolve())
    assert path.parent != legacy_runs.resolve()


def test_duplicate_execution_id_is_rejected(tmp_path):
    store = ExecutionStore(tmp_path / "memory")
    store.append(make_record())
    with pytest.raises(DuplicateExecutionError):
        store.append(make_record())
