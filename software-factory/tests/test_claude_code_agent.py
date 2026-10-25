from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from agents.claude_code import ClaudeCodeAgent, ClaudeCodeInput


def init_repo(path: Path) -> Path:
    path.mkdir()
    def git(*args: str) -> None:
        result = subprocess.run(
            ["git", *args], cwd=path, text=True, capture_output=True, check=False
        )
        assert result.returncode == 0, result.stderr
    git("init", "-b", "main")
    git("config", "user.email", "factory-test@example.invalid")
    git("config", "user.name", "Factory Test")
    (path / "README.md").write_text("# Test\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "initial")
    return path


def fake_command_that_writes(path_name: str) -> tuple[str, ...]:
    script = (
        "from pathlib import Path; "
        f"Path({path_name!r}).write_text('generated\\n', encoding='utf-8'); "
        "print('completed')"
    )
    return (sys.executable, "-c", script)


def test_agent_runs_inside_worktree_and_reports_scoped_changes(tmp_path: Path):
    repo = init_repo(tmp_path / "worktree")
    agent = ClaudeCodeAgent(command=fake_command_that_writes("src/generated.ts"))
    result = agent.execute(ClaudeCodeInput(
        task_id="MSG-001", run_id="run-001",
        requirement="Crear un archivo de prueba",
        workspace=repo, allowed_paths=("src/**",),
    ))

    assert result.status == "OK"
    assert result.output["changed_files"] == ["src/generated.ts"]
    assert result.output["path_violations"] == []
    assert result.output["delivery_eligible"] is True
    assert result.output["commit_performed"] is False
    assert (repo / "src/generated.ts").read_text(encoding="utf-8") == "generated\n"


def test_out_of_scope_change_blocks_delivery(tmp_path: Path):
    repo = init_repo(tmp_path / "worktree")
    agent = ClaudeCodeAgent(command=fake_command_that_writes("README.md"))
    result = agent.execute(ClaudeCodeInput(
        task_id="MSG-002", run_id="run-002",
        requirement="Crear un archivo de prueba",
        workspace=repo, allowed_paths=("src/**",),
    ))

    assert result.status == "ERROR"
    assert result.output["path_violations"] == ["README.md"]
    assert result.output["delivery_eligible"] is False


def test_empty_or_traversing_scope_is_rejected_before_execution(tmp_path: Path):
    repo = init_repo(tmp_path / "worktree")
    agent = ClaudeCodeAgent(command=fake_command_that_writes("src/generated.ts"))
    empty = agent.execute(ClaudeCodeInput("MSG-003", "run-003", "requerimiento", repo, ()))
    traversal = agent.execute(ClaudeCodeInput(
        "MSG-004", "run-004", "requerimiento", repo, ("../**",)
    ))

    assert empty.status == "ERROR"
    assert empty.output["error"] == "scope_invalido"
    assert traversal.status == "ERROR"
    assert traversal.output["error"] == "scope_invalido"


def test_invalid_input_and_empty_requirement_fail_closed():
    agent = ClaudeCodeAgent(command=("claude",))
    assert agent.execute({"requirement": "x"}).status == "ERROR"
    result = agent.execute(ClaudeCodeInput("MSG-005", "run-005", "  ", ".", ("src/**",)))
    assert result.status == "ERROR"
    assert result.output["error"] == "requirement_vacio"


def test_timeout_is_reported_as_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = init_repo(tmp_path / "worktree")
    agent = ClaudeCodeAgent(command=("claude",), timeout_seconds=1)
    real_run = subprocess.run

    def run_with_timeout(args, **kwargs):
        if args and args[0] == "claude":
            raise subprocess.TimeoutExpired(args, timeout=1)
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run_with_timeout)
    result = agent.execute(ClaudeCodeInput(
        "MSG-006", "run-006", "requerimiento", repo, ("src/**",)
    ))
    assert result.status == "ERROR"
    assert result.output["error"] == "claude_code_execution_failed"
