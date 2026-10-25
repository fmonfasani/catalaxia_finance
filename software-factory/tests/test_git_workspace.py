from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from integrations.git_workspace import GitWorkspace, WorkspaceError


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=path, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def product_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "product"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "factory-test@example.invalid")
    git(repo, "config", "user.name", "Factory Test")
    (repo / "README.md").write_text("# Wapsell\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    git(repo, "remote", "add", "origin", "https://github.com/fmonfasani/otrarondamas.git")
    return repo


def adapter(repo: Path, root: Path) -> GitWorkspace:
    return GitWorkspace(repo, root)


def test_prepare_creates_isolated_branch_and_worktree(product_repo: Path, tmp_path: Path) -> None:
    workspace = adapter(product_repo, tmp_path / "factory-workspaces")
    result = workspace.prepare("TASK-123")
    worktree = Path(result["worktree"])

    assert worktree.is_dir()
    assert git(worktree, "branch", "--show-current") == "sf/TASK-123"
    assert git(product_repo, "branch", "--show-current") == "main"
    assert result["repository"] == "fmonfasani/otrarondamas"
    assert not result.get("push_performed", False)


def test_reports_untracked_and_modified_paths(product_repo: Path, tmp_path: Path) -> None:
    workspace = adapter(product_repo, tmp_path / "factory-workspaces")
    result = workspace.prepare("TASK-124")
    worktree = Path(result["worktree"])
    (worktree / "README.md").write_text("# Wapsell changed\n", encoding="utf-8")
    (worktree / "new.py").write_text("pass\n", encoding="utf-8")

    assert workspace.get_changed_files("TASK-124") == ["README.md", "new.py"]
    assert workspace.validate_changed_paths("TASK-124", ["*.py"]) == ["README.md"]


def test_rejects_wrong_repository_identity(product_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="no autorizado"):
        GitWorkspace(product_repo, tmp_path / "workspaces", "someone/else")


@pytest.mark.parametrize("task_id", ["../escape", "a/b", "", ".", "x" * 65])
def test_rejects_unsafe_task_ids(product_repo: Path, tmp_path: Path, task_id: str) -> None:
    workspace = adapter(product_repo, tmp_path / "factory-workspaces")
    with pytest.raises(WorkspaceError, match="task_id inválido"):
        workspace.prepare(task_id)


def test_does_not_cleanup_dirty_worktree(product_repo: Path, tmp_path: Path) -> None:
    workspace = adapter(product_repo, tmp_path / "factory-workspaces")
    result = workspace.prepare("TASK-125")
    (Path(result["worktree"]) / "uncommitted.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="cambios sin guardar"):
        workspace.cleanup("TASK-125")

    assert (Path(result["worktree"]) / "uncommitted.txt").exists()


def test_context_marks_delivery_as_manual(product_repo: Path, tmp_path: Path) -> None:
    workspace = adapter(product_repo, tmp_path / "factory-workspaces")
    workspace.prepare("TASK-126")

    context = workspace.get_project_context("TASK-126")

    assert context["branch"] == "sf/TASK-126"
    assert context["push_performed"] is False
    assert context["merge_performed"] is False
    assert context["changed_files"] == []
