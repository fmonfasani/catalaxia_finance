"""Tests F6 — sistema de validacion C10 (evaluador solo-lectura)."""
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
import c10_evaluate as c10  # noqa: E402

YPF = "0000904851"
KO = "0000021344"
BLOCKED_RUN = "cb2a7fd5de8d4b08a256e8088274335f"  # e2e S01-BLOCK (NEGADA)


@pytest.fixture(scope="module")
def eng():
    return edb.get_engine(load_settings())


def _pass_runs(eng, n=2):
    with eng.connect() as c:
        return [r[0] for r in c.execute(text(
            "SELECT run_id FROM engine.stage_runs "
            "WHERE stage_id='S04_normalize' AND gate_status='PASS' "
            "ORDER BY id DESC LIMIT :n"), {"n": n})]


def test_A_pass_completo(eng):
    for scope in ("sec", "market", "cross"):
        with eng.connect() as c:
            res = c10.evaluate(c, _pass_runs(eng), [YPF, KO],
                               ["YPFD", "KO"], scope=scope)
        assert res["verdict"] == "PASS", (scope, res)


def test_B_warn_scope_completo(eng):
    with eng.connect() as c:
        res = c10.evaluate(c, _pass_runs(eng), [YPF, KO],
                           ["YPFD", "KO"], scope="all")
    assert res["verdict"] == "WARN"
    ids = {i["id"]: i["result"] for i in res["invariants"]}
    assert ids["CNV_SCOPE"] == "WARN"
    assert all(v == "PASS" for k, v in ids.items() if k != "CNV_SCOPE")


def test_C_block_run_bloqueado(eng):
    with eng.connect() as c:
        res = c10.evaluate(c, [BLOCKED_RUN], [YPF, KO],
                           ["YPFD", "KO"], scope="sec")
    assert res["verdict"] == "BLOCK"


def test_D_identidad_invalida(eng):
    with eng.connect() as c:
        assert c10.inv_identity(c, ["9999999999"]).result == "BLOCK"
    with eng.connect() as c:
        res = c10.evaluate(c, _pass_runs(eng), ["9999999999"],
                           ["YPFD", "KO"], scope="sec")
    assert res["verdict"] == "BLOCK"


def test_E_provenance_incompleta(eng):
    with eng.connect() as c:
        res = c10.evaluate(c, _pass_runs(eng), ["9999999999"],
                           ["YPFD", "KO"], scope="sec")
    ids = {i["id"]: i["result"] for i in res["invariants"]}
    assert ids["PROVENANCE"] == "BLOCK"


def test_F_orphan_entity(eng):
    assert c10.decide_orphan({"k": 3}).result == "BLOCK"
    assert c10.decide_orphan({"k": 0}).result == "PASS"
    with eng.connect() as c:
        assert c10.inv_no_orphan_entity(c, [YPF, KO]).result == "PASS"


def test_G_orphan_bridge(eng):
    with eng.connect() as c:
        assert c10.inv_bridge(c, ["XXXX"]).result == "BLOCK"
        assert c10.inv_bridge(c, ["YPFD", "KO"]).result == "PASS"


def test_H_cross_source_mismatch():
    assert c10.decide_separation({"cik"}, set(), {"cik"}).result == "BLOCK"
    assert c10.decide_separation(set(), set(), {"cik"}).result == "PASS"


def test_I_stage_incompleto(eng):
    with eng.connect() as c:
        res = c10.evaluate(c, [BLOCKED_RUN], [YPF, KO],
                           ["YPFD", "KO"], scope="sec")
    sec = next(i for i in res["invariants"] if i["id"] == "SEC_GATES")
    assert sec["result"] == "BLOCK" and sec["evidence"]["runs"]


def test_J_stage_fail(eng):
    with eng.connect() as c:
        res = c10.evaluate(c, [BLOCKED_RUN], [YPF, KO],
                           ["YPFD", "KO"], scope="sec")
    ev = next(i for i in res["invariants"] if i["id"] == "SEC_GATES")
    assert ev["evidence"]["runs"][BLOCKED_RUN[:8]]["non_pass"]


def test_K_stage_warn_agregacion():
    P = lambda: c10.Invariant("X", "PASS")
    W = lambda: c10.Invariant("X", "WARN")
    B = lambda: c10.Invariant("X", "BLOCK")
    assert c10.aggregate([P(), P()]) == "PASS"
    assert c10.aggregate([P(), W()]) == "WARN"
    assert c10.aggregate([W(), B()]) == "BLOCK"


def test_L_determinismo(eng):
    outs = []
    for _ in range(2):
        with eng.connect() as c:
            r = c10.evaluate(c, _pass_runs(eng), [YPF, KO],
                             ["YPFD", "KO"], scope="sec")
            r.pop("evaluated_at", None)  # timestamp excluido por diseno
            outs.append(json.dumps(r, sort_keys=True))
    assert outs[0] == outs[1]


TABLES = ["engine.runs", "engine.stage_runs", "engine.checkpoints",
          "parsed.facts", "derived.fact", "public.market_price_daily",
          "staging._publications"]


def _counts(eng):
    out = {}
    with eng.connect() as c:
        for t in TABLES:
            sch, tab = t.split(".")
            try:
                out[t] = c.execute(text(
                    "SELECT count(*) FROM %s.%s" % (sch, tab))).scalar()
            except Exception:
                out[t] = None
    return out


def test_M_idempotencia_lectura(eng):
    before = _counts(eng)
    with eng.connect() as c:
        c10.evaluate(c, _pass_runs(eng), [YPF, KO], ["YPFD", "KO"],
                     scope="all")
    assert _counts(eng) == before


def test_N_c11_no_modificado(eng):
    src = (REPO / "scripts" / "engine" / "c10_evaluate.py").read_text(
        encoding="utf-8")
    for tok in ("engine.certifications", "certificar_run", "cert_hash =",
                "INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE",
                "CREATE TABLE", "ALTER TABLE"):
        assert tok not in src, "evaluador no escribe: %s" % tok


def test_O_c12_no_modificado(eng):
    src = (REPO / "scripts" / "engine" / "c10_evaluate.py").read_text(
        encoding="utf-8")
    for tok in ("publisher", "sincronizar", "migrate", "staging._publications",
                "screener_export", "swap"):
        assert tok not in src, "evaluador no toca C12: %s" % tok


def test_P_sin_escritura_datos(eng):
    test_M_idempotencia_lectura(eng)


def test_C10_pass_certificable(eng):
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT veredicto FROM engine.certifications c WHERE EXISTS "
            "(SELECT 1 FROM engine.stage_runs s WHERE s.run_id=c.run_id AND "
            "s.stage_id='S04_normalize' AND s.gate_status='PASS') "
            "ORDER BY generado_at DESC LIMIT 1")).first()
    assert row and row[0] == "CERTIFICADA"


def test_C10_block_no_certificable(eng):
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT veredicto, motivo FROM engine.certifications "
            "WHERE run_id=:r ORDER BY generado_at DESC LIMIT 1"),
            {"r": BLOCKED_RUN}).first()
    assert row and row[0] == "NEGADA" and row[1]
