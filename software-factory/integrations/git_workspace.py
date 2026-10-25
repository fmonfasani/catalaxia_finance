"""Isolated Git workspaces for Software Factory tasks.

This adapter intentionally does not push, merge, or modify the protected base
branch. It operates only on a local clone whose origin identifies the
explicitly allowlisted Wapsell repository.
"""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


ALLOWED_REPOSITORY = "fmonfasani/otrarondamas"
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class WorkspaceError(RuntimeError):
    """A workspace operation was rejected or failed safely."""


class GitWorkspace:
    """Create and inspect one isolated Git worktree per factory task.

    Args:
        repository_path: Existing local clone of the product repository.
        worktrees_root: Dedicated directory outside the clone for worktrees
            and manifests. It is created on demand.
        repository_full_name: GitHub owner/repository identity. Only Wapsell
            is accepted by default; changing this requires an explicit choice.
        command_timeout: Timeout for each Git subprocess.
    """

    def __init__(
        self,
        repository_path: str | Path,
        worktrees_root: str | Path,
        repository_full_name: str = ALLOWED_REPOSITORY,
        command_timeout: int = 30,
    ) -> None:
        self.repository = Path(repository_path).expanduser().resolve()
        self.root = Path(worktrees_root).expanduser().resolve()
        self.repository_full_name = repository_full_name
        self.command_timeout = command_timeout
        if repository_full_name != ALLOWED_REPOSITORY:
            raise WorkspaceError(
                f"Repositorio no autorizado: {repository_full_name!r}; "
                f"permitido: {ALLOWED_REPOSITORY!r}"
            )
        if self.root == self.repository or self.repository in self.root.parents:
            raise WorkspaceError(
                "worktrees_root debe estar fuera del checkout del producto"
            )
        if command_timeout <= 0:
            raise ValueError("command_timeout debe ser positivo")
        self._assert_repository_identity()

    def _run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(cwd or self.repository),
                text=True,
                capture_output=True,
                timeout=self.command_timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceError(f"No se pudo ejecutar git {args[0]}: {exc}") from exc
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise WorkspaceError(f"git {' '.join(args)} falló: {detail}")
        return result

    @staticmethod
    def _canonical_remote(remote: str) -> str:
        value = remote.strip()
        value = re.sub(r"^git@github\.com:", "https://github.com/", value)
        value = re.sub(r"\.git$", "", value)
        return value.rstrip("/").lower()

    def _assert_repository_identity(self) -> None:
        if not self.repository.is_dir():
            raise WorkspaceError(f"No existe el checkout: {self.repository}")
        inside = self._run(["rev-parse", "--is-inside-work-tree"], check=False)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            raise WorkspaceError(f"No es un checkout Git: {self.repository}")
        remote = self._run(["remote", "get-url", "origin"], check=False)
        if remote.returncode != 0:
            raise WorkspaceError("El checkout no tiene un remote origin verificable")
        canonical = self._canonical_remote(remote.stdout)
        expected = f"https://github.com/{self.repository_full_name}".lower()
        if canonical != expected:
            raise WorkspaceError(
                f"origin no coincide con el repositorio autorizado: {remote.stdout.strip()!r}"
            )

    @staticmethod
    def _validate_task_id(task_id: str) -> str:
        if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
            raise WorkspaceError(
                "task_id inválido: usar 1-64 caracteres alfanuméricos, '_' o '-'"
            )
        return task_id

    def _paths(self, task_id: str) -> tuple[Path, Path]:
        task_id = self._validate_task_id(task_id)
        worktree = (self.root / "worktrees" / task_id).resolve()
        manifest = (self.root / "manifests" / f"{task_id}.json").resolve()
        for candidate in (worktree, manifest):
            try:
                candidate.relative_to(self.root)
            except ValueError as exc:
                raise WorkspaceError("La ruta de la tarea escapa del root") from exc
        return worktree, manifest

    def prepare(self, task_id: str, base_ref: str = "main") -> dict[str, str]:
        """Create a task worktree and branch; fail closed if either already exists."""
        task_id = self._validate_task_id(task_id)
        worktree, manifest = self._paths(task_id)
        branch = f"sf/{task_id}"
        if worktree.exists() or manifest.exists():
            raise WorkspaceError(f"La tarea {task_id!r} ya tiene workspace o manifest")
        if base_ref.startswith("-") or not base_ref.strip():
            raise WorkspaceError("base_ref inválido")
        resolved = self._run(
            ["rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
            check=False,
        )
        if resolved.returncode != 0:
            raise WorkspaceError(f"base_ref no resuelve a un commit: {base_ref!r}")
        existing_branch = self._run(
            ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            check=False,
        )
        if existing_branch.returncode == 0:
            raise WorkspaceError(f"La rama {branch!r} ya existe; no se reutiliza")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        self._run(["worktree", "add", "-b", branch, str(worktree), resolved.stdout.strip()])
        data = {
            "task_id": task_id,
            "repository": self.repository_full_name,
            "base_ref": base_ref,
            "base_sha": resolved.stdout.strip(),
            "branch": branch,
            "worktree": str(worktree),
        }
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data

    def _load_task(self, task_id: str) -> tuple[dict[str, Any], Path]:
        worktree, manifest = self._paths(task_id)
        if not manifest.is_file() or not worktree.is_dir():
            raise WorkspaceError(f"No existe un workspace preparado para {task_id!r}")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceError(f"Manifest inválido para {task_id!r}") from exc
        if (
            data.get("task_id") != task_id
            or data.get("repository") != self.repository_full_name
            or Path(data.get("worktree", "")).resolve() != worktree
            or data.get("branch") != f"sf/{task_id}"
        ):
            raise WorkspaceError("El manifest no coincide con la identidad del workspace")
        return data, worktree

    def get_project_context(self, task_id: str) -> dict[str, Any]:
        """Return bounded repository/task metadata for agent context, not file contents."""
        data, worktree = self._load_task(task_id)
        head = self._run(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        status = self._run(["status", "--porcelain=v1"], cwd=worktree).stdout.splitlines()
        changed = self.get_changed_files(task_id)
        return {
            **data,
            "head_sha": head,
            "working_tree_status": status,
            "changed_files": changed,
            "push_performed": False,
            "merge_performed": False,
        }

    def get_changed_files(self, task_id: str) -> list[str]:
        """List committed, unstaged, staged, and untracked paths relative to the base."""
        data, worktree = self._load_task(task_id)
        base = data["base_sha"]
        commands = (
            ["diff", "--name-only", "--no-renames", f"{base}...HEAD"],
            ["diff", "--name-only", "--no-renames"],
            ["diff", "--cached", "--name-only", "--no-renames"],
            ["ls-files", "--others", "--exclude-standard"],
        )
        paths: set[str] = set()
        for command in commands:
            output = self._run(command, cwd=worktree).stdout
            paths.update(line for line in output.splitlines() if line)
        return sorted(paths)

    def validate_changed_paths(
        self, task_id: str, allowed_patterns: list[str]
    ) -> list[str]:
        """Return out-of-scope paths; an empty list means all paths are in scope."""
        violations: list[str] = []
        for path in self.get_changed_files(task_id):
            candidate = PurePosixPath(path)
            if candidate.is_absolute() or ".." in candidate.parts:
                violations.append(path)
                continue
            if not any(fnmatch.fnmatchcase(path, pattern) for pattern in allowed_patterns):
                violations.append(path)
        return violations

    def cleanup(self, task_id: str) -> None:
        """Remove only a verified task worktree, and only when its tree is clean."""
        data, worktree = self._load_task(task_id)
        status = self._run(["status", "--porcelain=v1"], cwd=worktree).stdout.strip()
        if status:
            raise WorkspaceError(
                f"No se limpia {task_id!r}: hay cambios sin guardar; preservados para revisión"
            )
        self._run(["worktree", "remove", str(worktree)])
        # Deliberately retain the branch and manifest for traceability/recovery.
        data["worktree_removed"] = True
        _, manifest = self._paths(task_id)
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
