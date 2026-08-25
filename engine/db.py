from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from engine.config import REPO_ROOT, Settings
from engine.states import GateStatus, StageState

MIGRATIONS_DIR = REPO_ROOT / "migrations" / "engine"


def get_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.url,
        pool_pre_ping=True,
        future=True,
        connect_args={
            "connect_timeout": 5,
            "application_name": "catalaxia-engine",
            "options": "-c statement_timeout=120000",
        },
    )


def apply_migrations(engine: Engine, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    applied: list[str] = []
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS engine"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS engine.schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        done = {r[0] for r in conn.execute(text("SELECT filename FROM engine.schema_migrations"))}
        if migrations_dir.exists():
            for sql_file in sorted(migrations_dir.glob("*.sql")):
                if sql_file.name in done:
                    continue
                conn.execute(text(sql_file.read_text(encoding="utf-8")))
                conn.execute(
                    text("INSERT INTO engine.schema_migrations (filename) VALUES (:f)"),
                    {"f": sql_file.name},
                )
                applied.append(sql_file.name)
    return applied


def git_commit(repo_root: Path = REPO_ROOT) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True
        ).strip()
    except Exception:
        return None


@dataclass
class RunHandle:
    run_id: str
    mode: str
    pipeline_version: str
    git_commit: str | None


def start_run(engine: Engine, settings: Settings, pipeline_version: str) -> RunHandle:
    run = RunHandle(
        run_id=uuid.uuid4().hex,
        mode=settings.mode,
        pipeline_version=pipeline_version,
        git_commit=git_commit(),
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO engine.runs (run_id, mode, status, git_commit, pipeline_version)
                VALUES (:run_id, :mode, 'RUNNING', :git_commit, :pv)
                """
            ),
            {"run_id": run.run_id, "mode": run.mode, "git_commit": run.git_commit, "pv": run.pipeline_version},
        )
    return run


def finish_run(engine: Engine, run_id: str, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE engine.runs
                   SET status = :status, finished_at = now()
                 WHERE run_id = :run_id
                """
            ),
            {"status": status, "run_id": run_id},
        )


def record_stage_transition(
    engine: Engine,
    run_id: str,
    stage_id: str,
    prev_state: StageState | None,
    new_state: StageState,
    gate_status: GateStatus | None = None,
    gate_reasons: list[str] | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO engine.stage_runs
                    (run_id, stage_id, state, prev_state, gate_status, gate_reasons)
                VALUES
                    (:run_id, :stage_id, :state, :prev_state, :gate_status,
                     CAST(:gate_reasons AS JSONB))
                """
            ),
            {
                "run_id": run_id,
                "stage_id": stage_id,
                "state": new_state.value,
                "prev_state": prev_state.value if prev_state else None,
                "gate_status": gate_status.value if gate_status else None,
                "gate_reasons": json.dumps(gate_reasons or []),
            },
        )
