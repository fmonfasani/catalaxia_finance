from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from engine.config import REPO_ROOT, Settings, load_settings
from engine.states import GateStatus, StageState

MIGRATIONS_DIR = REPO_ROOT / "migrations" / "engine"


def _statement_timeout_ms() -> int:
    return int(os.environ.get("ENGINE_STATEMENT_TIMEOUT_MS", "120000"))


def get_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.url,
        pool_pre_ping=True,
        future=True,
        connect_args={
            "connect_timeout": 5,
            "application_name": "catalaxia-engine",
            # F-028: tras un replace-all de 67k filas las estadisticas del
            # planner quedan viejas y las validaciones de S03 se pasan de los
            # 120 s por defecto. Configurable para no tener que elegir entre
            # enmascarar el problema y no poder correr la etapa.
            "options": f"-c statement_timeout={_statement_timeout_ms()}",
        },
    )


def get_admin_engine(settings: Settings) -> Engine:
    """Conexion privilegiada para DDL. F-025: la app no es superusuario."""
    return create_engine(
        settings.admin_url,
        pool_pre_ping=True,
        future=True,
        connect_args={"connect_timeout": 5, "application_name": "catalaxia-engine-admin"},
    )


def apply_migrations(engine: Engine, migrations_dir: Path = MIGRATIONS_DIR,
                     settings: Settings | None = None) -> list[str]:
    """Aplica las migraciones pendientes. SIEMPRE por la via administrativa.

    F-025 dejo a la aplicacion corriendo como `catalaxia_engine`, que no es
    superusuario y no puede hacer DDL — es justamente el punto. Pero
    `apply_migrations` seguia usando el engine de la aplicacion, asi que S03
    moria al arrancar con `permission denied for database catalaxia`. Defecto
    introducido al cerrar F-025 y detectado al re-correr S03 (F-027).

    Aplicar DDL es una operacion administrativa por definicion: se abre una
    conexion privilegiada propia. El `engine` que se recibe se conserva por
    compatibilidad de firma y para leer la configuracion del destino.
    """
    admin = get_admin_engine(settings or load_settings())
    try:
        return _apply_migrations(admin, migrations_dir)
    finally:
        admin.dispose()


def _apply_migrations(engine: Engine, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
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


@contextmanager
def run_scope(engine: Engine, settings: Settings, pipeline_version: str):
    """Corrida con cierre GARANTIZADO. Obligatorio para S04 en adelante.

    F-009 (causa raiz): en s03/c3 las transiciones PASSED y CHECKPOINTED se
    registran ANTES del bloque que persiste el report y ANTES de `finish_run`.
    Dos corridas murieron en ese tramo y quedaron en RUNNING para siempre, con
    el estado de ETAPA adelantado respecto del estado de CORRIDA. Otras cinco
    murieron en el arranque y tampoco se cerraron.

    Aca el cierre va en `finally`: si el cuerpo levanta, la corrida queda
    ABORTED con su motivo; si sale limpio, queda con el status que el cuerpo
    haya fijado via `handle.status`, o OK por defecto.

        with run_scope(engine, settings, PIPELINE_VERSION) as run:
            ...
            run.status = "BLOCKED" if gate is GateStatus.BLOCK else "OK"
    """
    run = start_run(engine, settings, pipeline_version)
    run.status = None
    try:
        yield run
    except BaseException as e:
        try:
            finish_run(engine, run.run_id, "ABORTED")
        finally:
            raise e
    else:
        finish_run(engine, run.run_id, run.status or "OK")


def corridas_huerfanas(engine: Engine, horas: float = 6.0) -> list[dict]:
    """Corridas en RUNNING sin actividad reciente y sin proceso vivo.

    Se llama al ARRANCAR una etapa: si el pipeline dejo huerfanas, hay que
    verlo antes de generar mas, no 20 horas despues.
    """
    with engine.begin() as conn:
        vivas = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT application_name FROM pg_stat_activity "
            " WHERE datname = current_database() AND pid <> pg_backend_pid()"))}
        filas = conn.execute(text(
            """
            SELECT r.run_id, r.mode, r.pipeline_version, r.started_at,
                   round(EXTRACT(epoch FROM (now() - r.started_at)) / 3600, 1) AS horas,
                   (SELECT max(s.started_at) FROM engine.stage_runs s
                     WHERE s.run_id = r.run_id) AS ultima_etapa,
                   (SELECT count(*) FROM engine.stage_runs s
                     WHERE s.run_id = r.run_id AND s.report IS NOT NULL) AS con_report
              FROM engine.runs r
             WHERE r.status = 'RUNNING'
               AND r.started_at < now() - (:h * INTERVAL '1 hour')
             ORDER BY r.started_at
            """), {"h": horas}).mappings().all()
    return [dict(f) | {"hay_sesiones_activas": bool(vivas)} for f in filas]


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
