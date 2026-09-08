from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from engine import db as edb
from engine import identity as ident
from engine.config import load_settings
from engine.report import StageReport, utc_now_iso
from engine.states import GateStatus, StageState, assert_transition

STAGE_ID = "S01_identity"
PIPELINE_VERSION = "s1-identity-v1"
SCRIPT = "scripts/engine/s01_identity.py"


def check_unique_active_identity(engine) -> dict:
    with engine.connect() as conn:
        dup = conn.execute(
            text(
                """
                SELECT id_type, id_value, marketplace, count(DISTINCT entity_id) AS n
                  FROM identity.identifiers
                 WHERE status = 'ACTIVE'
                 GROUP BY id_type, id_value, marketplace
                HAVING count(DISTINCT entity_id) > 1
                """
            )
        ).all()
    return {"id": "C-S01-001", "result": "PASS" if not dup else "FAIL", "blocking": True,
            "detail": f"identidad canónica única por (tipo,valor,mercado): conflictos activos={len(dup)}"}


def check_disputes_routed(engine, expected_min: int) -> dict:
    with engine.connect() as conn:
        open_reviews = conn.execute(
            text("SELECT count(*) FROM identity.identifier_reviews WHERE status='OPEN'")
        ).scalar_one()
        disputed = conn.execute(
            text("SELECT count(*) FROM identity.identifiers WHERE status='DISPUTED'")
        ).scalar_one()
    ok = open_reviews >= expected_min
    return {"id": "C-S01-002", "result": "PASS" if ok else "FAIL", "blocking": True,
            "detail": (f"discrepancias fuera de identidad usable y en revisión manual "
                       f"(EXT-NEW-012): reviews abiertas={open_reviews}, identifiers DISPUTED={disputed}")}


def check_identity_vs_classification(engine) -> dict:
    with engine.connect() as conn:
        ticker_cols = conn.execute(
            text(
                """
                SELECT count(*) FROM information_schema.columns
                 WHERE table_schema='identity' AND table_name='entities'
                   AND column_name ILIKE '%ticker%'
                """
            )
        ).scalar_one()
        class_rows = conn.execute(
            text("SELECT count(*) FROM identity.classifications")
        ).scalar_one()
    ok = ticker_cols == 0
    return {"id": "C-S01-003", "result": "PASS" if ok else "FAIL", "blocking": True,
            "detail": (f"EXT-NEW-002: entities sin columnas de ticker ({ticker_cols}); "
                       f"classifications filas={class_rows}; tickers viven solo en identifiers")}


def check_golden_ypf(engine, resolution: dict) -> dict:
    problems: list[str] = []
    if not resolution.get("present"):
        return {"id": "C-S01-004", "result": "FAIL", "blocking": True,
                "detail": "entidad YPF CIK:0000904851 ausente"}
    if resolution["legal_name"] != "YPF SOCIEDAD ANONIMA":
        problems.append(f"legal_name inesperado: {resolution['legal_name']}")
    have = {(i["id_type"], i["id_value"], i["marketplace"]) for i in resolution["identifiers"]
            if i["status"] == "ACTIVE"}
    required = {
        ("CIK", "0000904851", "SEC"),
        ("TICKER", "YPF", "US"),
        ("YF_SYMBOL", "YPF", "yahoo"),
        ("TICKER", "YPFD", "BYMA"),
        ("YF_SYMBOL", "YPFD.BA", "yahoo"),
    }
    missing = sorted(required - have)
    if missing:
        problems.append(f"identificadores faltantes: {missing}")
    with engine.connect() as conn:
        stale = conn.execute(
            text(
                """
                SELECT count(*) FROM identity.identifier_reviews
                 WHERE status='OPEN' AND reason ILIKE '%1104659%'
                """
            )
        ).scalar_one()
    if stale < 1:
        problems.append("conflicto legacy CIK 1104659 no quedó registrado en revisión manual")
    return {"id": "C-S01-004", "result": "PASS" if not problems else "FAIL", "blocking": True,
            "detail": "; ".join(problems) or (
                "YPF única con CIK 0000904851, nombre exacto, YPF/US + YPFD/BYMA + símbolos yahoo activos, "
                "conflicto 1104659 en cola de revisión")}


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

    prev: StageState | None = None
    cur = StageState.PLANNED
    for nxt in (StageState.READY, StageState.RUNNING):
        assert_transition(cur, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=prev, new_state=nxt)
        prev, cur = cur, nxt

    stats_sec = ident.seed_from_sec_catalog(engine, run.run_id)
    print(f"[seed] entidades nuevas={stats_sec.entities} identificadores nuevos={stats_sec.identifiers} "
          f"yf_symbols nuevos={stats_sec.yf_symbols}")
    stats_link = ident.cross_check_legacy_and_link_byma(engine, run.run_id)
    print(f"[links] BYMA nuevos={stats_link.byma_links} YF .BA nuevos={stats_link.yf_symbols} "
          f"conflictos legacy={len(stats_link.conflicts)}")
    stats_manual = ident.apply_manual_resolutions(engine, run.run_id)
    print(f"[manual] resoluciones aplicadas: identifiers nuevos={stats_manual.identifiers} "
          f"yf nuevos={stats_manual.yf_symbols} problemas={len(stats_manual.conflicts)}")

    resolution = ident.resolve_golden_ypf(engine)

    checks = [
        check_unique_active_identity(engine),
        check_disputes_routed(engine, expected_min=len(stats_link.conflicts)),
        check_identity_vs_classification(engine),
        check_golden_ypf(engine, resolution),
    ]
    blocked = [c for c in checks if c["result"] == "FAIL" and c.get("blocking")]
    gate = GateStatus.BLOCK if blocked else GateStatus.PASS

    assert_transition(cur, StageState.VALIDATING)
    edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cur,
                                new_state=StageState.VALIDATING)
    end_state_path = [StageState.FAILED] if gate is GateStatus.BLOCK else \
        [StageState.PASSED, StageState.CHECKPOINTED]
    state_cursor = StageState.VALIDATING
    for nxt in end_state_path:
        assert_transition(state_cursor, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=state_cursor,
                                    new_state=nxt,
                                    gate_status=gate if nxt == end_state_path[-1] else None,
                                    gate_reasons=[c["detail"] for c in blocked])
        state_cursor = nxt

    report = StageReport(
        stage=STAGE_ID,
        run_id=run.run_id,
        mode=settings.mode,
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
        gate=gate,
        input_checkpoint_id="ROOT",
        input_rows=stats_sec.entities,
        expected=4,
        parsed=sum(1 for c in checks if c["result"] == "PASS"),
        rejected=len(blocked),
        rejected_by_reason={c["id"]: 1 for c in blocked},
        hash_in=ident.catalog_sha256(ident.load_sec_catalog(engine)),
        hash_out=hashlib.sha256(json.dumps(checks, sort_keys=True).encode()).hexdigest(),
        gate_reasons=[c["detail"] for c in blocked],
        checks=checks,
        parser_version="sec_company_tickers:v1",
        script=SCRIPT,
        git_commit=run.git_commit,
    )
    report.validate()

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE engine.stage_runs SET report = CAST(:r AS JSONB), finished_at = now(), "
                 "gate_status = :g WHERE id = (SELECT max(id) FROM engine.stage_runs "
                 "WHERE run_id=:run AND stage_id=:stage)"),
            {"r": report.to_json(), "g": gate.value, "run": run.run_id, "stage": STAGE_ID},
        )
        if gate is not GateStatus.BLOCK:
            conn.execute(
                text("INSERT INTO engine.checkpoints "
                     "(checkpoint_id, stage_id, run_id, input_hash, code_version, contract_version, artifact_ref) "
                     "VALUES (:cid, :stage, :run, :ih, :cv, :ctv, :ref)"),
                {"cid": uuid.uuid4().hex, "stage": STAGE_ID, "run": run.run_id,
                 "ih": report.hash_in, "cv": PIPELINE_VERSION, "ctv": "identity-v1",
                 "ref": "pg://identity.entities"},
            )

    run.status = "OK" if gate is not GateStatus.BLOCK else "BLOCKED"

    print(json.dumps(resolution, indent=2, ensure_ascii=False))
    print("--- conciliacion ---")
    print(f"checks_expected = {report.expected}")
    print(f"checks_pass     = {report.parsed}")
    print(f"checks_rejected = {report.rejected} {report.rejected_by_reason}")
    print(f"gate            = {gate.value}")
    return 0 if gate is not GateStatus.BLOCK else 1


if __name__ == "__main__":
    raise SystemExit(main())
