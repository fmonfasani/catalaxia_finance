# Software Factory Memory — M1a

## Scope

M1a provides project-isolated execution records. It does not integrate with
Kernel/Coordinator, retrieve prior context, or automatically create records
during pipeline execution. Those are separate slices (M1b/M1d) requiring
separate authorization.

## Configuration

Set `MEMORY_ROOT` explicitly or pass `memory_root=...` to
`ExecutionStore`. If neither is supplied, initialization fails. There is no
inferred default. Local filesystem locking is implemented; SMB/NFS semantics
and network filesystems are not verified by this slice.

## Layout

```text
<MEMORY_ROOT>/<project_id>/
  index.jsonl
  index.jsonl.lock
  records/<execution_id>.json
```

The JSONL index is append-only. Every append takes a dedicated lock:
`msvcrt.locking` on Windows and `fcntl.flock` on POSIX. Lock timeout fails
explicitly. Sidecars are written to a temporary file in the same directory,
flushed and fsynced, then atomically replaced. Windows `PermissionError`
receives bounded retries; no non-atomic fallback is used.

## Record and security guarantees

Only fields declared by `ExecutionRecord` are serialized. Raw prompts,
arbitrary payloads and free-form metadata are excluded. References must be
references to artifacts/evidence, not their contents. The existing
`observability.redact_structure` is reused as defense in depth.

This is not a general secret scanner. Key-based redaction does not detect a
secret embedded in arbitrary free text. The existing truncated SHA-256
redaction marker is correlatable. These limitations are not security guarantees.

`COMPLETED` and `FAILED` records require `ended_at`; an open execution must
not be represented as success. M1a cannot detect process death or automatically
close runs; lifecycle integration is future M1d work.

Malformed, partial and future-schema index rows are skipped and counted in
`MemoryRecordReadResult.skipped_malformed`, with reasons available for
diagnosis. Historical traces are not read, modified, migrated or deleted.

## Validation status

The M1a test suite is authored but has not been executed by this GitHub-based
editing session. The repository's own pre-change test baseline, Windows
multiprocess lock behavior, and Windows open-reader replacement behavior must
be verified in an execution environment before Gate review. No CI or runtime
pass is claimed.
