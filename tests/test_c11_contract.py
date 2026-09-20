"""Test de contrato — CAPA 11 CERTIFICACIÓN (R4).

`engine.certifications` como salida PRIMARIA; script `c11_certificar.py` como
único emisor. C11 LEE la evidencia de C10 (`engine.runs`+`engine.stage_runs`+
`engine.checkpoints`) y NO calcula, NO publica, NO modifica tablas de cálculo,
NO reutiliza el legado (`40_certificar`/`validar_suite`/`f6_sec`).

Mapeo NOT_CERTIFIED ⇔ NEGADA (veredictos del contrato: CERTIFICADA |
CERTIFICADA_CON_OBSERVACIONES | NEGADA).

Estos tests escriben corridas sintéticas de test que QUEDAN en la bitácora
(`engine.runs`/`stage_runs` no se borran: migración 016). Se identifican por
`pipeline_version='test-c11-contract'` y se cierran con estado terminal.
La infraestructura dev (PostgreSQL 127.0.0.1:5433) es la documentada en
R4_CAPA11_EVIDENCIA.md; NUNCA se ejecutan contra producción (EXT-010).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.report import StageReport  # noqa: E402
from engine.states import GateStatus, StageState  # noqa: E402
import c11_certificar  # noqa: E402

PIPELINE = "test-c11-contract"
SCRIPT = "scripts/engine/c11_certificar.py"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# plataforma
# ===========================================================================
@pytest.fixture(scope="module")
def s():
    st = load_settings()
    if st.is_prod:
        pytest.skip("EXT-010: no ejecutar contra produccion")
    return st


@pytest.fixture(scope="module")
def eng(s):
    e = edb.get_engine(s)
    # esquema al día por el runner ÚNICO (F-049): idempotente, solo aplica pendientes.
    edb.apply_migrations(e, settings=s)
    return e


# ===========================================================================
# helpers de evidencia C10 sintética (patrón idéntico al de s00_smoke)
# ===========================================================================
def checks_pass(*ids: str) -> list[dict]:
    return [{"id": c, "result": "PASS", "blocking": True, "detail": "ok"}
            for c in ids]


def checks_block(*ids: str) -> list[dict]:
    return [{"id": c, "result": "FAIL", "blocking": True, "detail": "bloquea"}
            for c in ids]


def checks_warn(*ids: str) -> list[dict]:
    return [{"id": c, "result": "FAIL", "blocking": False, "detail": "observa"}
            for c in ids]


def _registrar_etapa(eng, run_id: str, stage_id: str, gate: GateStatus,
                     checks: list[dict], checkpoint: bool = False) -> dict:
    """Transiciones + report final de una etapa, como lo hace s00..s04."""
    path = [StageState.READY, StageState.RUNNING, StageState.VALIDATING]
    if gate is GateStatus.BLOCK:
        path += [StageState.FAILED]
    else:
        path += [StageState.PASSED, StageState.CHECKPOINTED]

    cur = StageState.PLANNED
    for nxt in path:
        edb.record_stage_transition(eng, run_id, stage_id, cur, nxt)
        cur = nxt

    rejected = sum(1 for c in checks if c["result"] == "FAIL")
    report = StageReport(
        stage=stage_id,
        run_id=run_id,
        mode="FAST",
        started_at=_utc(),
        finished_at=_utc(),
        gate=gate,
        input_checkpoint_id="ROOT",
        input_rows=0,
        expected=len(checks),
        parsed=len(checks) - rejected,
        rejected=rejected,
        rejected_by_reason={c["id"]: 1 for c in checks if c["result"] == "FAIL"},
        hash_in=hashlib.sha256(b"ROOT").hexdigest(),
        hash_out=hashlib.sha256(json.dumps(checks, sort_keys=True).encode()).hexdigest(),
        gate_reasons=[c["detail"] for c in checks if c["result"] == "FAIL"],
        checks=checks,
        parser_version="test-c11",
        script="tests/test_c11_contract.py",
        git_commit=None,
    )
    report.validate()

    with eng.begin() as conn:
        conn.execute(
            text("UPDATE engine.stage_runs SET report = CAST(:r AS JSONB), "
                 "finished_at = now(), gate_status = :g "
                 "WHERE id = (SELECT max(id) FROM engine.stage_runs "
                 "             WHERE run_id=:run AND stage_id=:stage)"),
            {"r": report.to_json(), "g": gate.value,
             "run": run_id, "stage": stage_id},
        )
        if checkpoint and gate is GateStatus.PASS:
            # input_hash único por run: ux_checkpoints_reuse impide reinsertar
            ih = hashlib.sha256(run_id.encode()).hexdigest()
            conn.execute(
                text("INSERT INTO engine.checkpoints "
                     "(checkpoint_id, stage_id, run_id, input_hash, code_version, "
                     " contract_version, artifact_ref) "
                     "VALUES (:cid, :stage, :run, :ih, :cv, :ctv, :ref)"),
                {"cid": uuid.uuid4().hex, "stage": stage_id, "run": run_id,
                 "ih": ih,
                 "cv": "test-c11", "ctv": "engine-state-v1",
                 "ref": "state://engine.checkpoints"},
            )
    return report.to_dict()


def _cerrar(eng, s, status: str) -> str:
    run = edb.start_run(eng, s, PIPELINE)
    edb.finish_run(eng, run.run_id, status)
    return run.run_id


def _leer_acta(eng, run_id: str):
    with eng.connect() as c:
        return c.execute(text("SELECT * FROM engine.certifications WHERE run_id=:r"),
                         {"r": run_id}).mappings().first()


def _evidencia_actual(eng, run_id: str):
    with eng.connect() as c:
        run = c.execute(text("SELECT run_id, status, mode, pipeline_version, git_commit "
                             "  FROM engine.runs WHERE run_id=:r"),
                        {"r": run_id}).mappings().first()
        filas = c11_certificar._stages_final(c, run_id)
        cp = c11_certificar._checkpoints_ctx(c, run_id)
        presentes = [r[0] for r in c.execute(
            text("SELECT DISTINCT stage_id FROM engine.stage_runs "
                 " WHERE run_id=:r ORDER BY 1"), {"r": run_id}).all()]
    return dict(run), filas, cp, presentes


# ===========================================================================
# 1-2 · schema y migration registry (G1, G9)
# ===========================================================================
def test_migracion_034_registrada_por_el_runner(eng):
    with eng.connect() as c:
        ok = c.execute(text(
            "SELECT count(*) FROM engine.schema_migrations "
            " WHERE filename='engine/034_c11_certifications.sql'")).scalar()
    assert ok == 1, "el runner único (F-049) no registró engine/034"


def test_engine_certifications_existe(eng):
    with eng.connect() as c:
        assert c.execute(text("SELECT to_regclass('engine.certifications')")).scalar()
        cols = {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            " WHERE table_schema='engine' AND table_name='certifications'"))}
    minimo = {"certification_id", "run_id", "objeto", "veredicto", "cert_rule",
              "cert_hash", "pipeline_version", "stages_total", "evidence",
              "motivo", "generado_por", "generado_at"}
    assert minimo <= cols, f"faltan columnas: {minimo - cols}"


# ===========================================================================
# 3 · certificación de evidencia C10 válida
# ===========================================================================
def test_certifica_run_con_evidencia_c10_valida(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"), checkpoint=True)
    _registrar_etapa(eng, run_id, "S02_fetch", GateStatus.PASS,
                     checks_pass("C-S02-001", "C-S02-002"), checkpoint=True)

    acta = c11_certificar.certificar_run(eng, run_id)

    assert acta["veredicto"] == "CERTIFICADA"
    assert acta["stages_total"] == 2
    assert acta["stages_pass"] == 2
    assert acta["stages_block"] == 0 and acta["stages_insuf"] == 0
    row = _leer_acta(eng, run_id)
    assert row["veredicto"] == "CERTIFICADA"
    assert row["objeto"] == "RUN"


# ===========================================================================
# 4 · NOT_CERTIFIED (NEGADA) ante evidencia incompleta
# ===========================================================================
def test_evidencia_incompleta_es_NEGADA(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S03_parse", GateStatus.PASS,
                     checks_pass("C-S03-001"))
    edb.record_stage_transition(eng, run_id, "S04_normalize",
                                StageState.PLANNED, StageState.READY)

    acta = c11_certificar.certificar_run(eng, run_id)

    assert acta["veredicto"] == "NEGADA"
    assert "insuficiente" in (acta["motivo"] or "")
    assert acta["stages_insuf"] == 1


def test_sin_stage_runs_es_NEGADA(eng, s):
    run_id = _cerrar(eng, s, "OK")
    acta = c11_certificar.certificar_run(eng, run_id)
    assert acta["veredicto"] == "NEGADA"
    assert "sin stage_runs" in (acta["motivo"] or "")


def test_corrida_en_curso_o_abortada_no_certifica(eng, s):
    en_curso = edb.start_run(eng, s, PIPELINE)   # queda RUNNING (no se cierra)
    a = c11_certificar.certificar_run(eng, en_curso.run_id)
    assert a["veredicto"] == "NEGADA"
    edb.finish_run(eng, en_curso.run_id, "ABORTED")   # se cierra al final

    abortada = _cerrar(eng, s, "ABORTED")
    b = c11_certificar.certificar_run(eng, abortada)
    assert b["veredicto"] == "NEGADA"
    assert "abortada" in (b["motivo"] or "")


# ===========================================================================
# 5 · NOT_CERTIFIED (NEGADA) ante gate inválido (BLOCK)
# ===========================================================================
def test_gate_BLOCK_es_NEGADA(eng, s):
    run_id = _cerrar(eng, s, "BLOCKED")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"))
    _registrar_etapa(eng, run_id, "S02_fetch", GateStatus.BLOCK,
                     checks_block("C-S02-BLK"))

    acta = c11_certificar.certificar_run(eng, run_id)

    assert acta["veredicto"] == "NEGADA"
    assert "BLOCK" in (acta["motivo"] or "")
    assert acta["stages_block"] == 1


def test_warning_es_CERTIFICADA_CON_OBSERVACIONES(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S03_parse", GateStatus.PASS,
                     checks_pass("C-S03-001"))
    _registrar_etapa(eng, run_id, "S04_normalize", GateStatus.WARNING,
                     checks_warn("C-S04-W1"))
    acta = c11_certificar.certificar_run(eng, run_id)
    assert acta["veredicto"] == "CERTIFICADA_CON_OBSERVACIONES"
    assert acta["stages_warn"] == 1


def test_corrida_BLOCKED_sin_etapa_BLOCK_inconsistente(eng, s):
    run_id = _cerrar(eng, s, "BLOCKED")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"))
    acta = c11_certificar.certificar_run(eng, run_id)
    assert acta["veredicto"] == "NEGADA"
    assert "inconsistencia" in (acta["motivo"] or "")


# ===========================================================================
# 6, 7, 10 · cert_hash determinista, persistencia, re-ejecución idempotente
# ===========================================================================
def test_cert_hash_determinista_y_reejecucion_idempotente(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"), checkpoint=True)
    _registrar_etapa(eng, run_id, "S02_fetch", GateStatus.PASS,
                     checks_pass("C-S02-001"))

    acta1 = c11_certificar.certificar_run(eng, run_id)
    acta2 = c11_certificar.certificar_run(eng, run_id)

    assert acta1["cert_hash"] == acta2["cert_hash"] == acta1["cert_hash"]
    assert acta1["certification_id"] == acta2["certification_id"]
    # el acta re-leída debe ser JSON-serializable (INV3/INV5 artefacto)
    json.dumps(acta2)

    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM engine.certifications WHERE run_id=:r"),
                      {"r": run_id}).scalar()
    assert n == 1, "la re-ejecución duplicó el acta"

    row = _leer_acta(eng, run_id)
    assert row["cert_hash"] == acta1["cert_hash"]
    assert row["veredicto"] == acta1["veredicto"]

    # el cert_hash se reproduce a partir de la evidencia almacenada (INV3)
    run, filas, _, presentes = _evidencia_actual(eng, run_id)
    recomputado = c11_certificar.cert_hash("c11-rule-v1", run, filas, presentes)
    assert recomputado == row["cert_hash"]


# ===========================================================================
# 8 · run_id trazable (FK)
# ===========================================================================
def test_run_id_trazable_a_runs(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"))
    c11_certificar.certificar_run(eng, run_id)
    with eng.connect() as c:
        fk = c.execute(text(
            "SELECT count(*) FROM information_schema.table_constraints tc "
            " JOIN information_schema.referential_constraints rc "
            "   ON rc.constraint_name = tc.constraint_name "
            " WHERE tc.table_schema='engine' AND tc.table_name='certifications' "
            "   AND tc.constraint_type='FOREIGN KEY'")).scalar()
        fila = c.execute(text(
            "SELECT c.certification_id, r.status "
            "  FROM engine.certifications c JOIN engine.runs r ON r.run_id=c.run_id "
            " WHERE c.run_id=:r"), {"r": run_id}).one()
    assert fk > 0, "falta FK a engine.runs"
    assert fila[0] == f"c11-{run_id}"
    assert fila[1] == "OK"


# ===========================================================================
# 9 · provenance presente
# ===========================================================================
def test_provenance_presente(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"), checkpoint=True)
    c11_certificar.certificar_run(eng, run_id)
    row = _leer_acta(eng, run_id)
    assert row["generado_por"] == SCRIPT
    assert row["pipeline_version"] == PIPELINE
    ev = row["evidence"]
    assert isinstance(ev, list) and len(ev) == 1
    e = ev[0]
    assert e["stage_id"] == "S01_identity"
    assert re.fullmatch(r"[0-9a-f]{64}", e["report_sha256"])
    assert e["checkpoint"]["stage_id"] == "S01_identity"


# ===========================================================================
# 11-15 · side-effects, publicación, legado
# ===========================================================================
def _snapshot(eng):
    out = {}
    with eng.connect() as c:
        for tabla in ("engine.runs", "engine.stage_runs", "engine.checkpoints"):
            out[tabla] = c.execute(text(f"SELECT count(*) FROM {tabla}")).scalar()
        out["certif"] = c.execute(text(
            "SELECT count(*) FROM engine.certifications")).scalar()
    return out


def test_no_modifica_tablas_de_calculo(eng, s):
    run_id = _cerrar(eng, s, "OK")
    _registrar_etapa(eng, run_id, "S01_identity", GateStatus.PASS,
                     checks_pass("C-S01-001"))
    antes = _snapshot(eng)
    c11_certificar.certificar_run(eng, run_id)
    despues = _snapshot(eng)
    for tabla in ("engine.runs", "engine.stage_runs", "engine.checkpoints"):
        assert despues[tabla] == antes[tabla], f"C11 modificó {tabla}"
    assert despues["certif"] == antes["certif"] + 1


def test_no_publica():
    api_src = (REPO / "api" / "main.py").read_text(encoding="utf-8")
    src = (REPO / SCRIPT).read_text(encoding="utf-8")
    assert "certifications" not in api_src, "C12 no debe leer C11 todavía (R5)"
    for token in ("uvicorn", "FastAPI", "FastAPI(", "@app.get"):
        assert token.lower() not in src.lower().replace("__doc__", ""), \
            f"c11 no debe publicar (token {token})"


def test_no_depende_de_legado_ni_pilotos():
    src = (REPO / SCRIPT).read_text(encoding="utf-8")
    mig = (REPO / "migrations" / "engine" /
           "034_c11_certifications.sql").read_text(encoding="utf-8")
    # INV2 se mide sobre el CODIGO, no sobre el docstring (el docstring cita
    # los tokens prohibidos textualmente para documentar el invariante).
    doc = src.index('"""')
    codigo = src[src.index('"""', doc + 3) + 3:].lstrip("\n")
    prohibido = ("40_certificar", "certificacion_nueva",
                 "validar_suite", "screener_nivel", "f6_sec")
    for token in prohibido:
        assert token not in codigo and token not in mig, \
            f"C11 no puede acoplarse a {token} (INV2)"


def test_no_toca_raw_ni_archivos_de_datos():
    src = (REPO / SCRIPT).read_text(encoding="utf-8")
    assert "data/raw" not in src
    assert "unlink" not in src and "os.remove" not in src  # RAW inmutable (R3)


def test_grant_de_la_tabla_no_permiten_reescribir(eng):
    """INV6 a nivel de rol: catalaxia_engine SELECT+INSERT, sin UPDATE/DELETE."""
    with eng.connect() as c:
        grants = {g[0] for g in c.execute(text(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            " WHERE table_schema='engine' AND table_name='certifications' "
            "   AND grantee='catalaxia_engine'"))}
    assert {"SELECT", "INSERT"} <= grants
    assert "UPDATE" not in grants and "DELETE" not in grants


def test_motivo_queda_registrado_para_no_limpia(eng, s):
    run_id = _cerrar(eng, s, "BLOCKED")
    _registrar_etapa(eng, run_id, "S02_fetch", GateStatus.BLOCK,
                     checks_block("C-S02-BLK"))
    c11_certificar.certificar_run(eng, run_id)
    row = _leer_acta(eng, run_id)
    assert row["veredicto"] == "NEGADA"
    assert row["motivo"]
    assert row["stages_block"] == 1


# =====================================================================
# M7 (FASE 1, Paso 12): s04 reporta via engine.report.StageReport.
# Tests sin DB: verifican contrato + preservación legacy sobre la
# función pura build_s04_report (M7 no toca normalización ni DDL).
# =====================================================================

import s04_normalize  # noqa: E402


def _s04_inputs():
    s03 = {"checkpoint_id": "ck-s03-test", "run_id": "run-test-01"}
    stats = {"grupos": 10, "filas_entrada": 100, "desempates": {"a": 1},
             "sin_contexto": 6, "sin_entidad": 3, "sin_unidad": 2,
             "unidad_no_resuelta": 1}
    hechos = [{"entity_key": "e%d" % i, "accession_number": "acc",
               "is_dimensional": False} for i in range(90)]
    resumen = {"facts": 90}
    h2 = {"hash_out": "hout", "hash_spec": "spec-v1", "por_tabla": {}}
    checks = [{"id": "C-S04-001", "result": "PASS", "detail": "ok"}]
    return dict(s03=s03, stats=stats, hechos=hechos, resumen=resumen, h2=h2,
                checks=checks, fallidos=[])


def _s04_report(gate=GateStatus.PASS, **over):
    kw = _s04_inputs()
    kw.update(over)
    return s04_normalize.build_s04_report(
        stage="S04_normalize", run_id="run-test-01", mode="FAST",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        script="scripts/engine/s04_normalize.py",
        normalizer_version="s04_normalize_v1", git_commit="abc123",
        input_stage="S03_parse", gate=gate, **kw)


def test_m7_s04_usa_stagereport():
    src = (REPO / "scripts" / "engine" / "s04_normalize.py").read_text(
        encoding="utf-8")
    assert "from engine.report import StageReport" in src
    assert "build_s04_report" in src


def test_m7_reporte_valido_y_equivalente():
    rep = _s04_report()
    # 1-2. StageReport válido (validate no lanzó) + JSON válido.
    assert rep["stage"] == "S04_normalize"
    json.dumps(rep, ensure_ascii=False)
    # 3. contenido legacy preservado (claves pre-M7 s04 dict).
    assert rep["code"]["parser_version"] == "s04_normalize_v1"
    assert rep["code"]["normalizer_version"] == "s04_normalize_v1"
    assert rep["code"]["script"] == "scripts/engine/s04_normalize.py"
    assert rep["code"]["git_commit"] == "abc123"
    assert rep["coverage_detail"] == {
        "grupos": 10, "emitidos": 90, "sin_contexto": 6, "sin_entidad": 3,
        "sin_unidad": 2, "unidad_no_resuelta": 1, "desempates": {"a": 1}}
    assert rep["coverage"] == {"expected": 100, "parsed": 90,
                               "rejected": 10, "by_reason": {}}
    assert rep["integrity"]["hash_out"] == "hout"
    assert rep["integrity"]["hash_spec"] == "spec-v1"
    assert rep["input"] == {"checkpoint_id": "ck-s03-test", "rows": 100,
                            "stage": "S03_parse", "run_id": "run-test-01"}
    assert rep["nulls"] == {"count": 9, "by_null_reason": {
        "sin_contexto": 6, "sin_entidad": 3}}
    # 6-7. consumible por C10/C11 (gate + checks intactos).
    assert rep["gate"]["status"] == "PASS"
    assert rep["gate"]["checks"] == [{"id": "C-S04-001", "result": "PASS"}]
    assert rep["gate"]["reasons"] == []
    # 8. sin cambio semántico: ninguna clave legacy perdida.
    assert {"stage", "run_id", "mode", "started_at", "finished_at", "code",
            "input", "coverage", "integrity", "nulls", "gate"} <= set(rep)


def test_m7_gate_block_con_reasons():
    rep = _s04_report(
        gate=GateStatus.BLOCK,
        fallidos=[{"id": "C-S04-004", "result": "FAIL",
                   "detail": "sin entidad"}])
    assert rep["gate"]["status"] == "BLOCK"
    assert rep["gate"]["reasons"] == ["sin entidad"]


def test_m7_pass_sin_checks_falla_validacion():
    # Borde documentado M7: la norma ('termino sin excepcion' nunca es PASS)
    # ahora se impone en s04; antes persistía PASS sin checks.
    with pytest.raises(ValueError):
        _s04_report(checks=[])