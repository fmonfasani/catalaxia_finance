"""Tests F2 — publisher C12 en staging (solo DEV, schema staging)."""
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
import publisher as pub  # noqa: E402

RUN_CERT_FALLBACK = "0d9a298721e24ff09a4f118a331e41f2"  # historico (Paso 12/13)
TGT = "f2_demo"


def _run_cert(eng):
    """Run certificado mas reciente que aun tenga facts.

    Los facts convergen al ultimo escritor (ON CONFLICT); un run_id fijo
    queda huerfano tras re-runs. Resolver dinamicamente evita el treadmill.
    """
    with eng.connect() as c:
        rid = c.execute(text(
            "SELECT c.run_id FROM engine.certifications c "
            "WHERE c.veredicto='CERTIFICADA' AND EXISTS (SELECT 1 FROM "
            "derived.fact d WHERE d.run_id=c.run_id) "
            "ORDER BY c.generado_at DESC LIMIT 1")).scalar()
    return rid or RUN_CERT_FALLBACK


@pytest.fixture(scope="module")
def eng():
    return edb.get_engine(load_settings())


@pytest.fixture()
def clean(eng):
    with eng.begin() as c:
        pub.ensure_log_table(c)
        for t in ("f2_demo", "f2_demo2"):
            c.execute(text("DROP TABLE IF EXISTS staging.%s" % t))
            for r in c.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='staging' AND "
                    "(table_name LIKE 'f2_demo%%new%%' OR "
                    "table_name LIKE 'f2_demo%%prev%%' OR "
                    "table_name LIKE 'f2_demo%%bad%%' OR "
                    "table_name LIKE 'f2_demo2%%')")).all():
                c.execute(text("DROP TABLE IF EXISTS staging.%s" % r[0]))
        c.execute(text("DELETE FROM staging._publications "
                       "WHERE target LIKE 'f2_demo%%'"))
    yield


def _inp(eng, target=TGT, filt="WHERE run_id = :r", params=None, min_rows=1):
    run = _run_cert(eng)
    return pub.PublishInput(
        source_schema="derived", source_table="fact", target=target,
        run_id=run, pk_columns=["fact_key"],
        filter_sql=filt, filter_params=params or {"r": run},
        min_rows=min_rows)


def test_contract_rechaza_identificadores():
    with pytest.raises(ValueError):
        pub.check_target_name("public.screener")
    with pytest.raises(ValueError):
        pub.check_target_name("UPPER")
    with pytest.raises(ValueError):
        # la validación ocurre en build (no en el dataclass)
        pub.check_identifiers("derived", "fact; DROP")
    with pytest.raises(ValueError):
        pub.check_filter("DELETE FROM x")
    with pytest.raises(ValueError):
        pub.check_filter("SELECT 1; DROP TABLE y")


def test_gate_decide():
    assert pub.gate_decide(True, "CERTIFICADA") == (True, "ALLOW")
    assert pub.gate_decide(True, None)[0] is False
    assert pub.gate_decide(True, "NEGADA")[0] is False
    assert pub.gate_decide(False, "CERTIFICADA") == (False, "BLOCK:C10_NO_PASS")


def test_compare_schema_puro():
    ok, _ = pub.compare_schema([("a", "integer")], [("a", "integer")])
    assert ok
    ok, _ = pub.compare_schema([("a", "integer")], [("a", "text")])
    assert not ok
    ok, _ = pub.compare_schema([], [])
    assert not ok
    ok, _ = pub.never_empty(0, 1)
    assert not ok
    ok, _ = pub.never_empty(5, 100)
    assert not ok
    ok, _ = pub.never_empty(47930, 1)
    assert ok


def test_dry_run(eng, clean):
    res = pub.publish(_inp(eng), engine=eng, dry_run=True)
    assert res.ok and res.reason == "DRY_RUN_OK" and res.rows > 0
    with eng.connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": TGT}).scalar()
    assert n == 0  # dry-run no deja target


def test_publish_swap(eng, clean):
    res = pub.publish(_inp(eng), engine=eng)
    assert res.ok and res.reason == "PUBLISHED"
    assert res.c10_pass and res.certification_id
    assert res.cert_hash and res.swap_ts and res.provenance_id
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM staging.%s" % TGT)).scalar()
        assert n == res.rows > 0
        prov = c.execute(text(
            "SELECT run_id, input_hash, content_hash, c10_pass, "
            "certification_id FROM staging._publications WHERE id=:i"),
            {"i": res.provenance_id}).mappings().first()
        assert prov["run_id"] == _run_cert(eng) and prov["c10_pass"]
        assert prov["input_hash"] == res.input_hash


def test_idempotencia_contenido(eng, clean):
    r1 = pub.publish(_inp(eng), engine=eng)
    r2 = pub.publish(_inp(eng), engine=eng)
    assert r1.ok and r2.ok
    assert r1.content_hash == r2.content_hash
    assert r1.rows == r2.rows
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM staging.%s" % TGT)).scalar()
    assert n == r2.rows  # sin duplicados (swap, no append)


def test_rollback_restaura(eng, clean):
    run = _run_cert(eng)
    a = pub.publish(_inp(eng), engine=eng)
    b = pub.publish(_inp(eng, target="f2_demo",
                         filt="WHERE run_id = :r ORDER BY fact_key LIMIT 100",
                         params={"r": run}), engine=eng)
    assert b.rows == 100 and b.content_hash != a.content_hash
    rb = pub.rollback(TGT, engine=eng)
    assert rb.ok and rb.rows == a.rows
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM staging.%s" % TGT)).scalar()
        d = pub.content_digest(c, "staging", TGT, ["fact_key"])
    assert n == a.rows and d == a.content_hash


def test_bloqueo_sin_c10(eng, clean):
    run = _run_cert(eng)
    res = pub.publish(pub.PublishInput(
        "derived", "fact", TGT, "run-inexistente", ["fact_key"],
        "WHERE run_id = :r", {"r": run}), engine=eng)
    assert not res.ok and res.reason == "BLOCK:C10_NO_PASS"
    with eng.connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": TGT}).scalar()
    assert n == 0  # bloqueado antes del swap


def test_bloqueo_sin_c11(eng, clean, monkeypatch):
    monkeypatch.setattr(pub, "fetch_certification", lambda c, r: None)
    res = pub.publish(_inp(eng), engine=eng)
    assert not res.ok and res.reason == "BLOCK:C11_MISSING"


def test_bloqueo_c11_negada(eng, clean, monkeypatch):
    monkeypatch.setattr(
        pub, "fetch_certification",
        lambda c, r: {"certification_id": "x", "veredicto": "NEGADA",
                      "cert_hash": "y"})
    res = pub.publish(_inp(eng), engine=eng)
    assert not res.ok and "C11" in res.reason


def test_falla_input_y_vacio(eng, clean):
    res = pub.publish(pub.PublishInput(
        "derived", "tabla_que_no_existe", TGT, _run_cert(eng), ["fact_key"]),
        engine=eng)
    assert not res.ok and "fuente" in res.reason.lower()
    res = pub.publish(_inp(eng, filt="WHERE 1 = 0", params={}), engine=eng)
    assert not res.ok and "vacio" in res.reason


def test_rollback_sin_snapshot(eng, clean):
    res = pub.rollback("f2_demo2", engine=eng)
    assert not res.ok and res.reason == "BLOCK:NO_SNAPSHOT"
