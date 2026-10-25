"""Run one reviewed, bounded Wapsell task and open a PR only after validation passes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agents.claude_code import ClaudeCodeAgent
from agents.command_validator import CommandValidatorAgent
from contracts_catalog import build_default_registry
from coordinator.agent_registry import AgentRegistry
from coordinator.coordinator import Coordinator
from integrations.git_workspace import GitWorkspace
from integrations.wapsell_task_runner import WapsellTaskRunner
from kernel.factory_spec_loader import FactorySpecLoader
from kernel.run_manager import RunManager
from kernel.run_scope import RunScope


def run_command(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args, cwd=str(cwd), text=True, capture_output=True,
        timeout=120, check=False, shell=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Comando falló ({args[0]}): {detail[-4000:]}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--workspaces-root", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("BLOCKED: falta el secreto ANTHROPIC_API_KEY", file=sys.stderr)
        return 3
    if not os.environ.get("WAPSELL_GITHUB_TOKEN") or not os.environ.get("GH_TOKEN"):
        print("BLOCKED: falta WAPSELL_GITHUB_TOKEN/GH_TOKEN", file=sys.stderr)
        return 3

    config: dict[str, Any] = json.loads(args.config.read_text(encoding="utf-8"))
    repository = args.repository.resolve()
    task_id = args.task_id
    allowed_patterns = list(config["allowed_patterns"])
    commands = tuple(tuple(command) for command in config["validation_commands"])
    required_tests = tuple(config["required_tests"])

    factory_spec = FactorySpecLoader().load()
    run_manager = RunManager(
        pipeline=factory_spec.pipeline,
        factory_version=factory_spec.version,
    )
    scope = RunScope(
        scope_id=f"SCOPE-{task_id}",
        scope_version="1.0.0",
        required_stages=("Code", "Validation"),
        required_tests=required_tests,
        required_evidence_agents=("generator", "validator"),
    )
    run = run_manager.create_run(scope=scope)
    run_manager.advance_stage(run, "Code")

    registry = AgentRegistry()
    registry.register(ClaudeCodeAgent(timeout_seconds=1200))
    registry.register(CommandValidatorAgent())
    coordinator = Coordinator(
        run_manager=run_manager,
        registry=registry,
        contract_registry=build_default_registry(),
    )
    workspace = GitWorkspace(
        repository_path=repository,
        worktrees_root=args.workspaces_root,
    )
    runner = WapsellTaskRunner(workspace, coordinator)
    report = runner.execute_claude_task(
        task_id=task_id,
        run=run,
        requirement=config["requirement"],
        validation_commands=commands,
        allowed_patterns=allowed_patterns,
        base_ref="main",
    )
    print(json.dumps({"report": report}, ensure_ascii=False, indent=2, default=str))

    if not report["delivery_eligible"]:
        print("BLOCKED: la tarea no superó las condiciones de entrega; no se publica.", file=sys.stderr)
        return 2

    worktree = Path(report["worktree"]).resolve()
    changed_files = report["changed_files"]
    if not changed_files or report["path_violations"]:
        print("BLOCKED: diff vacío o rutas fuera del alcance.", file=sys.stderr)
        return 2

    run_command(["git", "add", "--", *changed_files], worktree)
    run_command(["git", "diff", "--cached", "--check"], worktree)
    staged = run_command(["git", "diff", "--cached", "--name-only"], worktree).splitlines()
    if sorted(staged) != sorted(changed_files):
        print("BLOCKED: el contenido staged no coincide con el diff validado.", file=sys.stderr)
        return 2

    run_command([
        "git", "-c", "user.name=Software Factory",
        "-c", "user.email=software-factory@users.noreply.github.com",
        "commit", "-m", config["commit_message"],
    ], worktree)
    run_command(["git", "push", "-u", "origin", report["branch"]], worktree)

    validation_list = "\n".join(f"- `{' '.join(command)}`" for command in commands)
    changed_list = "\n".join(f"- `{path}`" for path in changed_files)
    body = (
        "## Automated task report\n\n"
        f"- Task: `{task_id}`\n"
        f"- Factory run: `{run.run_id}`\n"
        f"- Base SHA: `{report['base_sha']}`\n"
        f"- Run status: `{report['status']}`\n"
        "- Path policy: passed; only allowlisted paths were changed.\n"
        "- Agent commits/pushes: none; delivery performed by the trusted runner after validation.\n"
        "- Merge/deploy: not performed.\n\n"
        "### Changed files\n" + changed_list + "\n\n"
        "### Validation commands\n" + validation_list + "\n\n"
        "The Software Factory opened this PR only after the required Code and Validation stages completed."
    )
    pr_url = run_command([
        "gh", "pr", "create",
        "--base", "main",
        "--head", report["branch"],
        "--title", config["title"],
        "--body", body,
    ], worktree)
    print(json.dumps({
        "task_id": task_id,
        "pull_request": pr_url,
        "changed_files": changed_files,
        "status": report["status"],
        "delivery_eligible": True,
        "merge_performed": False,
        "deploy_performed": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
