"""Coordinator bridge for executing a bounded Factory pipeline in a Wapsell worktree.

The bridge wires the existing Coordinator/Generator/Validator pipeline to the
GitWorkspace adapter. It does not commit, push, merge, or deploy. Generated
files remain uncommitted in the task worktree for review.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from agents.claude_code import ClaudeCodeInput
from agents.command_validator import CommandValidatorInput
from agents.generator import GeneratorInput
from coordinator.coordinator import Coordinator
from integrations.git_workspace import GitWorkspace
from kernel.run_manager import Run


ValidationInputBuilder = Callable[
    [dict[str, Any] | None, dict[str, Any] | None], Any
]


class WapsellTaskRunner:
    """Run the existing Code -> Validation pipeline inside an isolated Wapsell worktree."""

    def __init__(self, workspace: GitWorkspace, coordinator: Coordinator) -> None:
        self.workspace = workspace
        self.coordinator = coordinator

    def execute(
        self,
        *,
        task_id: str,
        run: Run,
        generator_input: GeneratorInput,
        validation_input_builder: ValidationInputBuilder,
        base_ref: str = "main",
        allowed_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute Generator -> Validator and report whether changes are in scope.

        The caller supplies the validated Specification and the Validator input
        builder; this bridge does not invent requirements or validation rules.
        By default, only files below this run's generated workspace are allowed.
        """
        if run.run_id != generator_input.run_id:
            raise ValueError(
                "run.run_id debe coincidir con generator_input.run_id"
            )

        prepared = self.workspace.prepare(task_id, base_ref=base_ref)
        worktree = Path(prepared["worktree"])

        # GeneratorInput.output_dir currently acts as a base-directory hint:
        # GeneratorWorkspace derives its base from output_dir.parents[1], then
        # places the run's requirements/specification/generated files beneath
        # <worktree>/<run_id>/.
        output_hint = worktree / "task-output" / "generated.py"
        scoped_generator_input = replace(
            generator_input,
            authorized_context={
                **generator_input.authorized_context,
                "output_dir": output_hint,
            },
        )

        if run.current_stage != "Code":
            self.coordinator.run_manager.advance_stage(run, "Code")

        self.coordinator.execute_pipeline(
            run,
            [
                ("Code", scoped_generator_input),
                (
                    "Validation",
                    lambda artifact, evidence: validation_input_builder(
                        artifact, evidence
                    ),
                ),
            ],
        )

        changed_files = self.workspace.get_changed_files(task_id)
        patterns = allowed_patterns or [f"{run.run_id}/**"]
        violations = self.workspace.validate_changed_paths(task_id, patterns)
        context = self.workspace.get_project_context(task_id)

        return {
            "task_id": task_id,
            "run_id": run.run_id,
            "status": run.status.value,
            "worktree": str(worktree),
            "branch": prepared["branch"],
            "base_sha": prepared["base_sha"],
            "changed_files": changed_files,
            "allowed_patterns": patterns,
            "path_violations": violations,
            "delivery_eligible": run.status.value == "COMPLETED" and not violations,
            "push_performed": False,
            "merge_performed": False,
            "project_context": context,
        }

    def execute_claude_task(
        self,
        *,
        task_id: str,
        run: Run,
        requirement: str,
        validation_commands: tuple[tuple[str, ...], ...],
        allowed_patterns: list[str],
        base_ref: str = "main",
    ) -> dict[str, Any]:
        """Execute Claude Code -> real command validation in an isolated Wapsell worktree.

        The caller must register ClaudeCodeAgent as "generator" and
        CommandValidatorAgent as "validator" in the Coordinator registry.
        The task definition supplies explicit path scope and trusted validation
        commands; the coding agent cannot choose or modify those gates.
        """
        if not requirement.strip():
            raise ValueError("requirement no puede estar vacío")
        if not allowed_patterns:
            raise ValueError("allowed_patterns debe declarar el alcance explícito")
        if not validation_commands:
            raise ValueError("validation_commands debe incluir al menos un comando")

        prepared = self.workspace.prepare(task_id, base_ref=base_ref)
        worktree = Path(prepared["worktree"])
        if run.current_stage != "Code":
            self.coordinator.run_manager.advance_stage(run, "Code")

        code_input = ClaudeCodeInput(
            task_id=task_id,
            run_id=run.run_id,
            requirement=requirement,
            workspace=worktree,
            allowed_paths=tuple(allowed_patterns),
        )
        validator_input = lambda artifact, evidence: CommandValidatorInput(
            run_id=run.run_id,
            workspace=worktree,
            commands=validation_commands,
        )
        self.coordinator.execute_pipeline(
            run,
            [("Code", code_input), ("Validation", validator_input)],
        )

        changed_files = self.workspace.get_changed_files(task_id)
        violations = self.workspace.validate_changed_paths(task_id, allowed_patterns)
        context = self.workspace.get_project_context(task_id)
        delivery_eligible = (
            run.status.value == "COMPLETED"
            and bool(changed_files)
            and not violations
        )
        return {
            "task_id": task_id,
            "run_id": run.run_id,
            "status": run.status.value,
            "worktree": str(worktree),
            "branch": prepared["branch"],
            "base_sha": prepared["base_sha"],
            "changed_files": changed_files,
            "allowed_patterns": allowed_patterns,
            "path_violations": violations,
            "delivery_eligible": delivery_eligible,
            "push_performed": False,
            "merge_performed": False,
            "project_context": context,
        }
