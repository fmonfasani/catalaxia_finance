"""Run a real Wapsell task locally with an existing Claude Code login.

This entrypoint deliberately does not require ANTHROPIC_API_KEY, GitHub tokens,
or perform commits, pushes, PR creation, merges, or deployments. It leaves the
isolated task worktree in place for manual inspection.
"""
from __future__ import annotations

import argparse
import json
import shutil
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded Wapsell task locally; no GitHub delivery is performed."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path,
                        help="Path to an existing local clone of fmonfasani/otrarondamas")
    parser.add_argument("--workspaces-root", required=True, type=Path,
                        help="Directory where isolated task worktrees will be created")
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()

    if shutil.which("claude") is None:
        print("BLOCKED: no se encuentra el ejecutable 'claude' en PATH.", file=sys.stderr)
        return 3

    repository = args.repository.expanduser().resolve()
    if not repository.is_dir():
        print(f"BLOCKED: no existe el repositorio local: {repository}", file=sys.stderr)
        return 3

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=str(repository),
        text=True, capture_output=True, timeout=15, check=False, shell=False,
    )
    if remote.returncode != 0 or "github.com/fmonfasani/otrarondamas" not in remote.stdout.lower():
        print("BLOCKED: origin no corresponde a fmonfasani/otrarondamas.", file=sys.stderr)
        return 3

    config: dict[str, Any] = json.loads(args.config.read_text(encoding="utf-8"))
    allowed_patterns = list(config["allowed_patterns"])
    commands = tuple(tuple(command) for command in config["validation_commands"])
    required_tests = tuple(config["required_tests"])

    factory_spec = FactorySpecLoader().load()
    run_manager = RunManager(
        pipeline=factory_spec.pipeline,
        factory_version=factory_spec.version,
    )
    scope = RunScope(
        scope_id=f"SCOPE-{args.task_id}",
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
        worktrees_root=args.workspaces_root.expanduser().resolve(),
    )
    runner = WapsellTaskRunner(workspace, coordinator)

    try:
        report = runner.execute_claude_task(
            task_id=args.task_id,
            run=run,
            requirement=config["requirement"],
            validation_commands=commands,
            allowed_patterns=allowed_patterns,
            base_ref="main",
        )
    except Exception as exc:
        print(f"BLOCKED: ejecución de la fábrica falló: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2

    print(json.dumps({"report": report}, ensure_ascii=False, indent=2, default=str))
    print("\nLOCAL-ONLY: no se creó commit, no se hizo push ni se abrió un PR.")
    print("Inspeccioná el worktree informado en el reporte antes de decidir la entrega.")

    if not report["delivery_eligible"]:
        print("RESULTADO: BLOCKED; cambios no elegibles para entrega.", file=sys.stderr)
        return 2

    print("RESULTADO: VALIDATION PASSED; cambios disponibles para revisión manual.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
