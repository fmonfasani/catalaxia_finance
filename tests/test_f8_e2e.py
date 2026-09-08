"""Tests F8 — integracion E2E VALIDACION (C10) -> CERTIFICACION (C11) ->
PUBLICACION (C12) en staging. Solo DEV; C10/C11/C12 no tocan produccion.

Cadena oficial: run CERTIFICADA con facts -> dry-run (pasos build/schema/
volumen/PK/gate) -> publicacion atomica con swap -> provenance enlaza C12-C11.
Casos negativos: C10_NO_PASS, C11_MISSING, C11_NOT_CERTIFIED y volumen vacio.
Determinismo/idempotencia: C10 misma evidencia -> mismo veredicto; C11 re-run
-> mismo cert_hash (sin duplicar acta); C12 republicar -> mismo input_hash.
Sin efectos colaterales: la cadena no modifica facts/checkpoints/parsed.
"""
from __future__ import annotations

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
import c11_certificar as c11  # noqa: E402
import publisher as pub  # noqa: E402

CIK_YPF = "0000904851"
TICKER_YPF = "YPFD"
STAGES_SEC = ("S00_bootstrap", "S01_identity", "S02_fetch",
              "S03_parse", "S04_normalize")
TGT = "f8_e2e_test"


def _run_cert(eng):
    """Run CERTIFICADA mas reciente que aun tenga facts en derived.fact."""
    with eng.connect() as c:
        rid = c.execute(text(
            "SELECT c.run_id FROM engine.certifications c "
            "WHERE c.veredicto='CERTIFICADA' AND EXISTS (SELECT 1 FROM "
            "derived.fact d WHERE d.run_id=c.run_id) "
            "ORDER BY c.generado_at DESC LIMIT 1")).scalar()
    assert rid, "se requiere al menos un run CERTIFICADA con facts"
    return rid


def _facts_count(eng, run_id):
    with eng.connect() as c:
        return c.execute(text(
            "SELECT count(*) FROM derived.fact WHERE run_id=:r"),
            {"r": run_id}).scalar()


def _orphan_running(eng, run_id=None):
    sql = ("SELECT count(*) FROM engine.stage_runs sr WHERE state='RUNNING' "
           "AND sr.id = (SELECT max(id) FROM engine.stage_runs s2 "
           "WHERE s2.run_id=sr.run_id AND s2.stage_id=sr.stage_id)")
    with eng.connect() as c:
        if run_id:
            return c.execute(text(sql + " AND sr.run_id=:r"),
                             {"r": run_id}).scalar()
        return c.execute(text(sql)).scalar()


def _table_counts(eng):
    out = {}
    with eng.connect() as c:
        for t in ("engine.checkpoints", "parsed.facts", "derived.fact"):
            sch, tab = t.split(".")
            out[t] = c.execute(text(
                "SELECT count(*) FROM %s.%s" % (sch, tab))).scalar()
    return out


@pytest.fixture(scope="module")
def eng():
    return edb.get_engine(load_settings())


@pytest.fixture(scope="module")
def run(eng):
    return _run_cert(eng)


@pytest.fixture()
def clean(eng):
    with eng.begin() as c:
        pub.ensure_log_table(c)
        for t in ("f8_e2e_test", "f8_e2e_extra"):
            c.execute(text("DROP TABLE IF EXISTS staging.%s" % t))
            for r in c.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='staging' AND "
                    "(table_name LIKE 'f8_e2e%%new%%' OR "
                    "table_name LIKE 'f8_e2e%%prev%%' OR "
                    "table_name LIKE 'f8_e2e%%bad%%')")).all():
                c.execute(text("DROP TABLE IF EXISTS staging.%s" % r[0]))
            c.execute(text("DELETE FROM staging._publications "
                           "WHERE target LIKE 'f8_e2e%%'"))
    yield


def _inp(run, target=TGT, filt="WHERE run_id = :r", params=None,
         min_rows=1, claimed_run=None):
    return pub.PublishInput(
        source_schema="derived", source_table="fact", target=target,
        run_id=claimed_run or run, pk_columns=["fact_key"],
        filter_sql=filt, filter_params=params or {"r": run},
        min_rows=min_rows)


def test_A_c10_veredicto_no_bloquea(eng, run):
    """C10 sobre el run CERTIFICADA: nunca BLOCK en SEC; WARN de alcance ok."""
    with eng.connect() as conn:
        res = c10.evaluate(conn, [run], [CIK_YPF], [TICKER_YPF], scope="all")
    assert res["verdict"] in ("PASS", "WARN")
    by_id = {i["id"]: i["result"] for i in res["invariants"]}
    assert by_id["SEC_GATES"] in ("PASS", "WARN")
    assert by_id["PROVENANCE"] == "PASS"


def test_B_c11_acta_certificada(eng, run):
    acta = c11.certificar_run(eng, run)
    assert acta["veredicto"] == "CERTIFICADA"
    assert len(acta["cert_hash"]) == 64
    assert acta["stages_total"] == 5
    assert acta["stages_pass"] == 5
    assert acta["stages_block"] == 0


def test_C_c11_determinista_idempotente(eng, run):
    a1 = c11.certificar_run(eng, run)
    a2 = c11.certificar_run(eng, run)
    assert a1["cert_hash"] == a2["cert_hash"]
    with eng.connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM engine.certifications WHERE run_id=:r"),
            {"r": run}).scalar()
    assert n == 1  # acta unica por run (sin duplicados)


def test_D_gate_decide_puro():
    assert pub.gate_decide(True, "CERTIFICADA") == (True, "ALLOW")
    assert pub.gate_decide(False, "CERTIFICADA") == (False, "BLOCK:C10_NO_PASS")
    assert pub.gate_decide(True, None) == (False, "BLOCK:C11_MISSING")
    assert pub.gate_decide(True, "NEGADA") == (False, "BLOCK:C11_NOT_CERTIFIED")
    assert pub.gate_decide(True, "CERTIFICADA_CON_OBSERVACIONES") == \
        (False, "BLOCK:C11_NOT_CERTIFIED")


def test_E_dry_run_cadena_completa(eng, run, clean):
    facts = _facts_count(eng, run)
    res = pub.publish(_inp(run, min_rows=facts), engine=eng, dry_run=True)
    assert res.ok and res.reason == "DRY_RUN_OK"
    assert res.rows == facts > 0
    assert res.c10_pass is True
    assert res.certification_id == "c11-%s" % run
    assert res.cert_hash and len(res.cert_hash) == 64
    with eng.connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": TGT}).scalar()
    assert n == 0  # dry-run no deja target


def test_F_publish_swap_con_provenance(eng, run, clean):
    facts = _facts_count(eng, run)
    dry = pub.publish(_inp(run, min_rows=facts), engine=eng, dry_run=True)
    res = pub.publish(_inp(run, min_rows=facts), engine=eng)
    assert res.ok and res.reason == "PUBLISHED"
    assert res.input_hash == dry.input_hash  # mismo input -> mismo hash
    assert res.certification_id == "c11-%s" % run
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM staging.%s" % TGT)).scalar()
        prov = c.execute(text(
            "SELECT run_id, rows, c10_pass, certification_id, cert_hash, "
            "content_hash FROM staging._publications WHERE id=:i"),
            {"i": res.provenance_id}).mappings().first()
    assert n == res.rows == facts
    assert prov["run_id"] == run and prov["c10_pass"] is True
    assert prov["certification_id"] == "c11-%s" % run
    assert prov["cert_hash"] == res.cert_hash
    assert prov["content_hash"] == res.content_hash


def test_G_bloqueo_sin_c11(eng, run, clean, monkeypatch):
    monkeypatch.setattr(pub, "fetch_certification", lambda c, r: None)
    res = pub.publish(_inp(run), engine=eng)
    assert not res.ok and res.reason == "BLOCK:C11_MISSING"
    with eng.connect() as c:
        assert c.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": TGT}).scalar() == 0


def test_H_bloqueo_c10_no_pass(eng, run, clean):
    # Filas presentes (filter sobre el run real) pero run reclamado sin C10
    # PASS -> el gate detiene antes del swap.
    res = pub.publish(_inp(run, claimed_run="run-inexistente"), engine=eng)
    assert not res.ok and res.reason == "BLOCK:C10_NO_PASS"
    with eng.connect() as c:
        assert c.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": TGT}).scalar() == 0


def test_I_bloqueo_volumen_vacio(eng, run, clean):
    res = pub.publish(_inp(run, filt="WHERE 1 = 0", params={}), engine=eng)
    assert not res.ok and "vacio" in res.reason


def test_J_cadena_no_deja_hermanas(eng, run, clean):
    """La cadena no introduce etapas RUNNING huerfanas (F-009 en el alcance)."""
    assert _orphan_running(eng, run_id=run) == 0
    before = _orphan_running(eng)
    c11.certificar_run(eng, run)  # idempotente: no añade eventos
    pub.publish(_inp(run), engine=eng, dry_run=True)
    assert _orphan_running(eng) == before


def test_K_cadena_no_modifica_datos(eng, run, clean):
    before = _table_counts(eng)
    c11.certificar_run(eng, run)
    pub.publish(_inp(run), engine=eng, dry_run=True)
    assert _table_counts(eng) == before


def test_L_dos_mismo_input_mismo_hash_sin_duplicados(eng, run, clean):
    facts = _facts_count(eng, run)
    r1 = pub.publish(_inp(run, min_rows=facts), engine=eng)
    r2 = pub.publish(_inp(run, min_rows=facts), engine=eng)
    assert r1.ok and r2.ok
    assert r1.input_hash == r2.input_hash
    assert r1.content_hash == r2.content_hash
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM staging.%s" % TGT)).scalar()
    assert n == facts  # swap, no append: sin duplicados


def test_M_target_upper_rechazado(eng, run, clean):
    with pytest.raises(ValueError):
        pub.check_target_name("f8_negA")
    with pytest.raises(ValueError):
        pub.publish(_inp(run, target="f8_Upper"), engine=eng)