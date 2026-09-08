from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from engine import db as edb
from engine.config import load_settings
from engine.report import StageReport, utc_now_iso
from engine.states import GateStatus, StageState, assert_transition

STAGE_ID = "S00_bootstrap"
PIPELINE_VERSION = "s0-bootstrap-v1"
SCRIPT = "scripts/engine/s00_smoke.py"


def main() -> int:
    settings = load_settings()
    print(f"[config] target={settings.describe()}")

    engine = edb.get_engine(settings)
    applied = edb.apply_migrations(engine)
    print(f"[migrations] aplicadas ahora: {applied or '(ninguna nueva)'}")


    # F-050: el cierre va en `finally` (run_scope). Antes, `start_run` abria
    # aca y `finish_run` cerraba decenas de lineas mas abajo: cualquier
    # excepcion en el medio dejaba la corrida en RUNNING para siempre. Es el
    # mismo patron que F-031 aplico a S03 y F-040 a C3.
    huerfanas = edb.corridas_huerfanas(engine)
    if huerfanas:
        print(f"[huerfanas] {len(huerfanas)} corridas previas quedaron en RUNNING:")
        for h in huerfanas[:5]:
            print(f"   {h['run_id'][:12]} {h['pipeline_version']} hace {h['horas']}h")
    with edb.run_scope(engine, settings, PIPELINE_VERSION, stage_id=STAGE_ID) as run:
        print(f"[run] run_id={run.run_id} git={run.git_commit}")
        return _correr(engine, settings, run)


def _correr(engine, settings, run) -> int:
    """Cuerpo de la etapa. Fija `run.status`; NUNCA llama a finish_run (F-050)."""

    checks: list[dict] = []
    with engine.connect() as conn:
        mig = conn.execute(
            # F-051: el runner registra con prefijo de directorio
            # (`engine/001_…`). Se aceptan AMBOS formatos: las bases anteriores
            # a F-051 guardan el nombre desnudo. Ver MIGRATIONS_CONTRACT.md.
            text("SELECT count(*) FROM engine.schema_migrations "
                 " WHERE filename IN ('001_s00_bootstrap.sql', 'engine/001_s00_bootstrap.sql')")
        ).scalar_one()
        checks.append({"id": "C-S00-001", "result": "PASS" if mig == 1 else "FAIL", "blocking": True,
                       "detail": f"schema_migrations registra 001_s00_bootstrap.sql ({mig})"})
        prod_ok = not settings.is_prod
        checks.append({"id": "C-S00-002", "result": "PASS" if prod_ok else "FAIL", "blocking": True,
                       "detail": f"target no es produccion (port={settings.db_port})"})

    blocked = [c for c in checks if c["result"] == "FAIL"]
    gate = GateStatus.BLOCK if any(c.get("blocking") for c in blocked) else GateStatus.PASS

    prev: StageState | None = None
    cur = StageState.PLANNED
    path = [StageState.READY, StageState.RUNNING, StageState.VALIDATING]
    if gate is GateStatus.BLOCK:
        path += [StageState.FAILED]
    elif gate is GateStatus.PASS:
        path += [StageState.PASSED, StageState.CHECKPOINTED]

    for nxt in path:
        assert_transition(cur, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cur, new_state=nxt)
        prev, cur = cur, nxt

    report = StageReport(
        stage=STAGE_ID,
        run_id=run.run_id,
        mode=settings.mode,
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
        gate=gate,
        input_checkpoint_id="ROOT",
        input_rows=0,
        expected=len(checks),
        parsed=sum(1 for c in checks if c["result"] == "PASS"),
        rejected=len(blocked),
        rejected_by_reason={c["id"]: 1 for c in blocked},
        hash_in=hashlib.sha256(b"ROOT").hexdigest(),
        hash_out=hashlib.sha256(json.dumps(checks).encode()).hexdigest(),
        gate_reasons=[c["detail"] for c in blocked],
        checks=checks,
        parser_version="n/a",
        script=SCRIPT,
        git_commit=run.git_commit,
    )
    report.validate()

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE engine.stage_runs SET report = CAST(:r AS JSONB), finished_at = now(), gate_status = :g "
                 "WHERE id = (SELECT max(id) FROM engine.stage_runs WHERE run_id=:run AND stage_id=:stage)"),
            {"r": report.to_json(), "g": gate.value, "run": run.run_id, "stage": STAGE_ID},
        )
        if gate is GateStatus.PASS:
            conn.execute(
                text("INSERT INTO engine.checkpoints "
                     "(checkpoint_id, stage_id, run_id, input_hash, code_version, contract_version, artifact_ref) "
                     "VALUES (:cid, :stage, :run, :ih, :cv, :ctv, :ref)"),
                {
                    "cid": uuid.uuid4().hex,
                    "stage": STAGE_ID,
                    "run": run.run_id,
                    "ih": hashlib.sha256(settings.describe().encode()).hexdigest(),
                    "cv": PIPELINE_VERSION,
                    "ctv": "engine-state-v1",
                    "ref": "state://engine.checkpoints",
                },
            )

    run.status = "OK" if gate is GateStatus.PASS else "BLOCKED"

    print(report.to_json())
    print("--- conciliacion ---")
    print(f"rows_expected   = {report.expected}")
    print(f"rows_parsed     = {report.parsed}")
    print(f"rows_rejected   = {report.rejected} {report.rejected_by_reason}")
    print(f"gate            = {gate.value}")
    return 0 if gate is GateStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
