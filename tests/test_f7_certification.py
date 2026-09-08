"""Tests F7 — autoridad de certificacion C11 (lectura + certificaciones DEV
explicitas via la herramienta oficial; cero cambios de codigo/contrato)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
import c11_certificar as c11  # noqa: E402

YPF_RUN = "875b6d83364a4c0cafbee557be70a993"  # E2E YPF F4, evidencia completa
KO_RUN = "6e3cf30c85054c2baeaa6b362d5153f7"  # E2E KO F4, CERTIFICADA
BLOCKED_RUN = "cb2a7fd5de8d4b08a256e8088274335f"  # e2e S01-BLOCK, NEGADA


@pytest.fixture(scope="module")
def eng():
    return edb.get_engine(load_settings())


def _cert(eng, run_id):
    with eng.connect() as c:
        return c.execute(text(
            "SELECT * FROM engine.certifications WHERE run_id=:r "
            "ORDER BY generado_at DESC LIMIT 1"), {"r": run_id}).mappings().first()


def test_A_c10_pass_certificada(eng):
    row = _cert(eng, YPF_RUN)
    assert row is None or row["veredicto"] in ("CERTIFICADA",
                                               "CERTIFICADA_CON_OBSERVACIONES")


def test_K_nuevo_run_certifica(eng):
    before = _cert(eng, YPF_RUN)
    acta = c11.certificar_run(eng, YPF_RUN)
    assert acta["veredicto"] in ("CERTIFICADA", "CERTIFICADA_CON_OBSERVACIONES")
    row = _cert(eng, YPF_RUN)
    assert row["cert_hash"] == acta["cert_hash"]
    if before is None:
        assert row["veredicto"] == acta["veredicto"]


def test_C_c10_block_negada(eng):
    row = _cert(eng, BLOCKED_RUN)
    assert row and row["veredicto"] == "NEGADA" and row["motivo"]


def test_D_c10_ausente_negada():
    res = c11.evaluar_evidencia(
        {"run_id": "x", "status": "OK", "mode": "FAST",
         "pipeline_version": "e2e-sec-edgar-v1", "git_commit": "y"},
        [], {}, [])
    assert res["veredicto"] == "NEGADA"


def test_E_stage_pass_completo(eng):
    row = _cert(eng, KO_RUN)
    ev = row["evidence"] if isinstance(row["evidence"], list) else json.loads(
        row["evidence"])
    assert row["veredicto"] == "CERTIFICADA"
    assert {e["stage_id"] for e in ev} >= {"S00_bootstrap", "S01_identity",
                                          "S02_fetch", "S03_parse", "S04_normalize"}
    assert all(e["gate_status"] == "PASS" for e in ev)


def test_F_stage_incompleto(eng):
    row = _cert(eng, BLOCKED_RUN)
    ev = row["evidence"] if isinstance(row["evidence"], list) else json.loads(
        row["evidence"])
    assert {e["stage_id"] for e in ev} < {"S00_bootstrap", "S01_identity",
                                         "S02_fetch", "S03_parse", "S04_normalize"}


def test_G_evidencia_insuficiente():
    res = c11.evaluar_evidencia(
        {"run_id": "x", "status": "OK", "mode": "FAST",
         "pipeline_version": "e2e-sec-edgar-v1", "git_commit": "y"},
        [{"stage_id": "S00_bootstrap", "state": "CHECKPOINTED",
          "gate_status": "PASS", "result": "PASS", "reason": "",
          "report_sha256": "h", "check_count": 2, "expected": 2,
          "parsed": 2, "rejected": 0}], {}, ["S00_bootstrap"])
    assert res["veredicto"] == "NEGADA" and res["motivo"]


def test_H_evidencia_modificada_cambia_hash(eng):
    h1 = c11.cert_hash("c11-rule-v1",
                       {"run_id": "r", "pipeline_version": "p", "status": "OK"},
                       [{"stage_id": "S00_bootstrap", "state": "CHECKPOINTED",
                         "gate_status": "PASS", "report": {"a": 1}}],
                       ["S00_bootstrap"])
    h2 = c11.cert_hash("c11-rule-v1",
                       {"run_id": "r", "pipeline_version": "p", "status": "OK"},
                       [{"stage_id": "S00_bootstrap", "state": "CHECKPOINTED",
                         "gate_status": "BLOCK", "report": {"a": 1}}],
                       ["S00_bootstrap"])
    assert h1 != h2 and len(h1) == 64


def test_I_cert_hash_determinista():
    kw = dict(rule="c11-rule-v1",
              run={"run_id": "r", "pipeline_version": "p", "status": "OK"},
              filas=[{"stage_id": "S00_bootstrap", "state": "CHECKPOINTED",
                      "gate_status": "PASS", "report": {"a": 1}}],
              stage_ids_presentes=["S00_bootstrap"])
    assert c11.cert_hash(**kw) == c11.cert_hash(**kw)


def test_J_reevaluacion_misma_evidencia(eng):
    a1 = c11.certificar_run(eng, KO_RUN)
    a2 = c11.certificar_run(eng, KO_RUN)
    assert a1["cert_hash"] == a2["cert_hash"]
    assert a1["generado_at"] == a2["generado_at"]
    assert a1["veredicto"] == "CERTIFICADA"


def test_L_previa_negada_intacta(eng):
    before = _cert(eng, BLOCKED_RUN)
    c11.certificar_run(eng, BLOCKED_RUN)
    after = _cert(eng, BLOCKED_RUN)
    assert (before["cert_hash"], before["generado_at"], before["veredicto"]) == \
        (after["cert_hash"], after["generado_at"], after["veredicto"])
    assert after["veredicto"] == "NEGADA"


def test_M_previa_certificada_intacta(eng):
    before = _cert(eng, KO_RUN)
    c11.certificar_run(eng, KO_RUN)
    after = _cert(eng, KO_RUN)
    assert (before["cert_hash"], before["generado_at"]) == \
        (after["cert_hash"], after["generado_at"])


def test_N_sin_overwrite_historico(eng):
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM (SELECT run_id, count(*) "
                           "FROM engine.certifications GROUP BY run_id "
                           "HAVING count(*) > 1) x")).scalar()
    assert n == 0


def test_O_provenance_completa(eng):
    row = _cert(eng, KO_RUN)
    assert row["certification_id"] == "c11-%s" % KO_RUN
    assert row["run_id"] == KO_RUN and row["cert_hash"] and row["generado_por"]
    ev = row["evidence"] if isinstance(row["evidence"], list) else json.loads(
        row["evidence"])
    assert all("stage_id" in e and "gate_status" in e for e in ev)


def test_P_stages_declarados_consistentes(eng):
    row = _cert(eng, KO_RUN)
    with eng.connect() as c:
        decl = {r[0] for r in c.execute(text(
            "SELECT DISTINCT stage_id FROM engine.stage_runs "
            "WHERE run_id=:r"), {"r": KO_RUN})}
    ev = row["evidence"] if isinstance(row["evidence"], list) else json.loads(
        row["evidence"])
    assert {e["stage_id"] for e in ev} == decl


def test_Q_reglas_versiones_consistentes(eng):
    row = _cert(eng, KO_RUN)
    assert row["cert_rule"] == c11.DEFAULT_RULE
    with eng.connect() as c:
        pv = c.execute(text("SELECT pipeline_version FROM engine.runs "
                            "WHERE run_id=:r"), {"r": KO_RUN}).scalar()
    assert row["pipeline_version"] == pv


def _counts(eng):
    out = {}
    with eng.connect() as c:
        for t in ("engine.stage_runs", "engine.checkpoints", "parsed.facts",
                  "derived.fact", "public.market_price_daily"):
            sch, tab = t.split(".")
            out[t] = c.execute(text(
                "SELECT count(*) FROM %s.%s" % (sch, tab))).scalar()
    return out


def test_R_c11_no_modifica_c10(eng):
    src = (REPO / "scripts" / "engine" / "c11_certificar.py").read_text(
        encoding="utf-8")
    for tok in ("UPDATE engine.stage_runs", "DELETE FROM engine",
                "UPDATE engine.checkpoints", "UPDATE engine.runs"):
        assert tok not in src
    before = _counts(eng)
    c11.certificar_run(eng, KO_RUN)
    assert _counts(eng) == before


def test_S_c11_no_modifica_datos(eng):
    src = (REPO / "scripts" / "engine" / "c11_certificar.py").read_text(
        encoding="utf-8")
    for tok in ("parsed.", "derived.", "fetch_raw.", "market_",
                "identity.", "screener"):
        assert tok not in src, "C11 no toca datos: %s" % tok


def test_T_c11_no_publica(eng):
    src = (REPO / "scripts" / "engine" / "c11_certificar.py").read_text(
        encoding="utf-8")
    for tok in ("publisher", "sincronizar", "migrate", "FastAPI", "uvicorn",
                "screener_export"):
        assert tok not in src, "C11 no publica: %s" % tok


def test_B_warn_comportamiento_definido(eng):
    # WARN de alcance (CNV) no bloquea C11: el run YPF esta CERTIFICADA
    # aunque el scope completo C10 sea WARN. Politica explicita y probada.
    row = _cert(eng, YPF_RUN)
    assert row["veredicto"] in ("CERTIFICADA", "CERTIFICADA_CON_OBSERVACIONES")
