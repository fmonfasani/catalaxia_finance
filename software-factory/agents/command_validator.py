"""Command-based validator for real product repositories.

Commands are supplied by the trusted task definition, never by the coding
agent. Execution uses argv with shell=False, an executable allowlist, per-step
timeouts, and structured PASS/FAIL evidence.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent


@dataclass(frozen=True)
class CommandValidatorInput:
    run_id: str
    workspace: str | Path
    commands: tuple[tuple[str, ...], ...]
    timeout_seconds: int = 600


class CommandValidatorAgent(BaseAgent):
    metadata = AgentMetadata(
        id="validator",
        name="Command Validator",
        role=AgentRole.VALIDATOR,
        input_contract="CommandValidatorInput: {run_id, workspace, commands, timeout_seconds}",
        output_contract="dict: {result: PASS|FAIL, violations, evidence, details}",
    )

    ALLOWED_EXECUTABLES = frozenset({"npm", "npx", "python", "python3", "pytest"})

    def execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, CommandValidatorInput):
            return AgentResult(self.metadata.id, input_data, {"error": "input_invalido"}, "ERROR")
        if not input_data.commands or any(not cmd or not cmd[0] for cmd in input_data.commands):
            return AgentResult(
                self.metadata.id,
                {"run_id": input_data.run_id},
                {"error": "commands_invalidos", "detail": "Se requiere al menos un comando"},
                "ERROR",
            )
        if input_data.timeout_seconds <= 0:
            return AgentResult(
                self.metadata.id, {"run_id": input_data.run_id},
                {"error": "timeout_invalido"}, "ERROR",
            )
        for command in input_data.commands:
            if command[0] not in self.ALLOWED_EXECUTABLES:
                return AgentResult(
                    self.metadata.id, {"run_id": input_data.run_id},
                    {"error": "ejecutable_no_autorizado", "executable": command[0]},
                    "ERROR",
                )

        workspace = Path(input_data.workspace).expanduser().resolve()
        if not workspace.is_dir():
            return AgentResult(
                self.metadata.id, {"run_id": input_data.run_id},
                {"error": "workspace_inexistente"}, "ERROR",
            )

        checks: list[dict[str, Any]] = []
        violations: list[str] = []
        try:
            for index, command in enumerate(input_data.commands, start=1):
                try:
                    result = subprocess.run(
                        list(command), cwd=str(workspace), text=True,
                        capture_output=True, timeout=input_data.timeout_seconds,
                        check=False, shell=False,
                    )
                    passed = result.returncode == 0
                    check = {
                        "id": f"CMD-{index:03d}",
                        "command": list(command),
                        "status": "PASS" if passed else "FAIL",
                        "exit_code": result.returncode,
                        "stdout_tail": result.stdout[-3000:],
                        "stderr_tail": result.stderr[-3000:],
                    }
                except (OSError, subprocess.TimeoutExpired) as exc:
                    passed = False
                    check = {
                        "id": f"CMD-{index:03d}",
                        "command": list(command),
                        "status": "FAIL",
                        "error": str(exc),
                    }
                checks.append(check)
                if not passed:
                    violations.append(check["id"])
                    break  # fail fast: do not run later commands after a failed gate

            verdict = "FAIL" if violations else "PASS"
            return AgentResult(
                agent_id=self.metadata.id,
                input={
                    "run_id": input_data.run_id,
                    "workspace": str(workspace),
                    "commands": [list(command) for command in input_data.commands],
                },
                output={
                    "result": verdict,
                    "violations": violations,
                    "evidence": {
                        "run_id": input_data.run_id,
                        "checks_executed": len(checks),
                        "workspace": str(workspace),
                    },
                    "checks": checks,
                    "details": "Todos los comandos finalizaron con código 0" if not violations
                               else f"Falló la validación: {', '.join(violations)}",
                },
                status="OK",
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResult(
                agent_id=self.metadata.id, input={"run_id": input_data.run_id},
                output={"error": "validation_execution_failed", "detail": str(exc)},
                status="ERROR",
            )
