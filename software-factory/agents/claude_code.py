"""Claude Code CLI adapter for bounded, isolated code-generation tasks.

This adapter does not commit, push, merge, deploy, or certify its own output.
It executes only inside a caller-provided Git worktree and reports path-policy
violations so the coordinator can fail closed before delivery.
"""
from __future__ import annotations

import fnmatch
import json
import subprocess
from datetime import datetime, timezone
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent


@dataclass(frozen=True)
class ClaudeCodeInput:
    task_id: str
    run_id: str
    requirement: str
    workspace: str | Path
    allowed_paths: tuple[str, ...]


class ClaudeCodeAgent(BaseAgent):
    """Invoke Claude Code in print mode with file tools only.

    The caller must prepare an isolated worktree first. The agent intentionally
    has no Bash/Web tools; build and test commands belong to the Validator.
    Path checks are repeated after execution because prompt instructions alone
    are not a security boundary.
    """

    metadata = AgentMetadata(
        id="generator",
        name="Claude Code Generator",
        role=AgentRole.GENERATOR,
        input_contract="ClaudeCodeInput: {task_id, run_id, requirement, workspace, allowed_paths}",
        output_contract="dict: {changed_files, path_violations, exit_code, delivery_eligible}",
    )

    def __init__(
        self,
        command: Sequence[str] = ("claude",),
        timeout_seconds: int = 900,
    ) -> None:
        if not command or any(not part for part in command):
            raise ValueError("command debe contener el ejecutable y sus argumentos")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo")
        self.command = tuple(command)
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _validate_patterns(patterns: tuple[str, ...]) -> list[str]:
        if not patterns:
            return ["allowed_paths vacío: se rechaza el cambio por defecto"]
        problems = []
        for pattern in patterns:
            path = PurePosixPath(pattern)
            if path.is_absolute() or ".." in path.parts or not pattern.strip():
                problems.append(f"patrón de ruta inválido: {pattern!r}")
        return problems

    @staticmethod
    def _changed_files(workspace: Path) -> list[str]:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=str(workspace),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
            shell=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"git status falló: {detail}")
        paths = set()
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[-1]
            paths.add(path.replace("\\", "/"))
        return sorted(paths)

    def execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, ClaudeCodeInput):
            return AgentResult(
                agent_id=self.metadata.id, input=input_data,
                output={"error": "input_invalido"}, status="ERROR",
            )
        if not input_data.requirement.strip():
            return AgentResult(
                agent_id=self.metadata.id,
                input={"task_id": input_data.task_id, "run_id": input_data.run_id},
                output={"error": "requirement_vacio"}, status="ERROR",
            )

        pattern_errors = self._validate_patterns(input_data.allowed_paths)
        if pattern_errors:
            return AgentResult(
                agent_id=self.metadata.id,
                input={"task_id": input_data.task_id, "run_id": input_data.run_id},
                output={"error": "scope_invalido", "details": pattern_errors},
                status="ERROR",
            )

        workspace = Path(input_data.workspace).expanduser().resolve()
        if not workspace.is_dir():
            return AgentResult(
                agent_id=self.metadata.id,
                input={"task_id": input_data.task_id, "run_id": input_data.run_id},
                output={"error": "workspace_inexistente"}, status="ERROR",
            )

        try:
            check = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(workspace), text=True, capture_output=True,
                timeout=30, check=False, shell=False,
            )
            if check.returncode != 0 or check.stdout.strip() != "true":
                raise RuntimeError("workspace no es un checkout Git")
            prompt = (
                "Implementá únicamente este requerimiento en el repositorio actual.\n"
                f"TAREA: {input_data.task_id}\nRUN: {input_data.run_id}\n"
                f"REQUERIMIENTO:\n{input_data.requirement}\n"
                f"RUTAS AUTORIZADAS: {', '.join(input_data.allowed_paths)}\n"
                "Reglas obligatorias: inspeccioná el código existente antes de editar; "
                "cambiá solo archivos que coincidan con las rutas autorizadas; "
                "no inventes requisitos ni modifiques contratos no mencionados; "
                "no ejecutes comandos; no crees commits, no hagas push, merge ni deploy. "
                "Si el requerimiento no es implementable con la información disponible, "
                "no adivines: explicá el bloqueo sin modificar archivos."
            )
            command = [
                *self.command, "-p", prompt,
                "--output-format", "json",
                "--permission-mode", "acceptEdits",
                "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep",
            ]
            result = subprocess.run(
                command, cwd=str(workspace), text=True, capture_output=True,
                timeout=self.timeout_seconds, check=False, shell=False,
            )
            changed_files = self._changed_files(workspace)
            violations = [
                path for path in changed_files
                if not any(fnmatch.fnmatchcase(path, pattern) for pattern in input_data.allowed_paths)
            ]
            parsed_output: Any = None
            if result.stdout.strip():
                try:
                    parsed_output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    parsed_output = result.stdout[-4000:]
            eligible = result.returncode == 0 and not violations and bool(changed_files)
            artifact = None
            code_reference = ", ".join(changed_files)
            if changed_files:
                artifact = {
                    "artifact_id": f"ART-{uuid4().hex[:12]}",
                    "run_id": input_data.run_id,
                    "stage": "Code",
                    "agent_id": self.metadata.id,
                    "type": "source_changes",
                    "reference": code_reference,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "parent_artifact_id": None,
                    "requirement_ref": input_data.requirement,
                    "specification_ref": input_data.task_id,
                    "evidence_ref": None,
                }
            output = {
                "artifact": artifact,
                "code_reference": code_reference,
                "task_id": input_data.task_id,
                "run_id": input_data.run_id,
                "changed_files": changed_files,
                "allowed_paths": list(input_data.allowed_paths),
                "path_violations": violations,
                "exit_code": result.returncode,
                "agent_output": parsed_output,
                "stderr_tail": result.stderr[-2000:],
                "delivery_eligible": eligible,
                "commit_performed": False,
                "push_performed": False,
                "merge_performed": False,
                "deploy_performed": False,
            }
            status = "OK" if eligible else "ERROR"
            return AgentResult(
                agent_id=self.metadata.id,
                input={
                    "task_id": input_data.task_id,
                    "run_id": input_data.run_id,
                    "requirement": input_data.requirement,
                    "allowed_paths": list(input_data.allowed_paths),
                },
                output=output, status=status,
            )
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            return AgentResult(
                agent_id=self.metadata.id,
                input={"task_id": input_data.task_id, "run_id": input_data.run_id},
                output={"error": "claude_code_execution_failed", "detail": str(exc)},
                status="ERROR",
            )
