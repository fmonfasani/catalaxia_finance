from __future__ import annotations

import sys
from pathlib import Path

from agents.command_validator import CommandValidatorAgent, CommandValidatorInput


def test_command_validator_returns_pass_with_execution_evidence(tmp_path: Path):
    agent = CommandValidatorAgent()
    result = agent.execute(CommandValidatorInput(
        run_id="run-001",
        workspace=tmp_path,
        commands=(("python", "-c", "print('checks passed')"),),
    ))

    assert result.status == "OK"
    assert result.output["result"] == "PASS"
    assert result.output["violations"] == []
    assert result.output["checks"][0]["status"] == "PASS"
    assert result.output["checks"][0]["exit_code"] == 0


def test_command_failure_returns_fail_not_false_success(tmp_path: Path):
    agent = CommandValidatorAgent()
    result = agent.execute(CommandValidatorInput(
        run_id="run-002",
        workspace=tmp_path,
        commands=(("python", "-c", "raise SystemExit(3)"),),
    ))

    assert result.status == "OK"
    assert result.output["result"] == "FAIL"
    assert result.output["violations"] == ["CMD-001"]
    assert result.output["checks"][0]["exit_code"] == 3


def test_unapproved_executable_is_rejected_without_execution(tmp_path: Path):
    agent = CommandValidatorAgent()
    result = agent.execute(CommandValidatorInput(
        run_id="run-003", workspace=tmp_path,
        commands=(("bash", "-c", "echo unsafe"),),
    ))

    assert result.status == "ERROR"
    assert result.output["error"] == "ejecutable_no_autorizado"


def test_empty_command_list_fails_closed(tmp_path: Path):
    agent = CommandValidatorAgent()
    result = agent.execute(CommandValidatorInput(
        run_id="run-004", workspace=tmp_path, commands=(),
    ))

    assert result.status == "ERROR"
    assert result.output["error"] == "commands_invalidos"
