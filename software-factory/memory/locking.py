"""Portable OS-backed inter-process locks for the JSONL index."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class MemoryLockTimeoutError(TimeoutError):
    """The memory index lock was not acquired before the configured timeout."""


def _try_lock(handle) -> bool:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def exclusive_file_lock(path: Path, timeout_seconds: float = 5.0) -> Iterator[None]:
    """Acquire a dedicated lock file; fail closed on timeout."""
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be >= 0")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + timeout_seconds
        while True:
            if _try_lock(handle):
                acquired = True
                break
            if time.monotonic() >= deadline:
                raise MemoryLockTimeoutError(
                    f"could not acquire lock {path} within {timeout_seconds:.3f}s"
                )
            time.sleep(min(0.025, max(0.001, deadline - time.monotonic())))
        yield
    finally:
        if acquired:
            _unlock(handle)
        handle.close()
