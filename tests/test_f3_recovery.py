"""Tests F3 — snapshot/recovery R7.3 (solo DEV, schema staging)."""
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

RUN_CERT_FALLBACK = "0d9a298721e24ff09a4f118a331e41f2"  # historico
TGT = "f3_tgt"
PK = ["fact_key"]


def _run_cert(eng):
    """Run certificado mas reciente que aun tenga facts (anti-treadmill)."""
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
        for r in c.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='staging' AND table_name LIKE 'f3_tgt%%'")).all():
            c.execute(text("DROP TABLE IF EXISTS staging.%s" % r[0]))
        c.execute(text("DELETE FROM staging._publications "
                       "WHERE target LIKE 'f3_tgt%%'"))
    yield


def _inp(eng, target=TGT, limit=500):
    run = _run_cert(eng)
    return pub.PublishInput(
        source_schema="derived", source_table="fact", target=target,
        run_id=run, pk_columns=list(PK),
        filter_sql="WHERE run_id = '%s' ORDER BY fact_key LIMIT %d" % (run, limit))


def _digest(eng, table):
    with eng.connect() as c:
        return pub.content_digest(c, "staging", table, PK)


def _prev(eng, target=TGT):
    with eng.connect() as c:
        rows = [r[0] for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name LIKE :p "
            "ORDER BY table_name DESC"), {"p": target + "__prev__%"})]
    return rows[0] if rows else None


def _count(eng, table):
    with eng.connect() as c:
        return c.execute(
            text("SELECT count(*) FROM staging.%s" % table)).scalar()


def _publish_ab(eng):
    a = pub.publish(_inp(eng, limit=500), engine=eng)
    assert a.ok, a.reason
    b = pub.publish(_inp(eng, limit=100), engine=eng)
    assert b.ok, b.reason
    return a, b


def test_A_snapshot_valido(eng, clean):
    a, _ = _publish_ab(eng)
    p = _prev(eng)
    assert p is not None
    assert _count(eng, p) == a.rows == 500


def test_B_sin_snapshot_en_primera_publicacion(eng, clean):
    a = pub.publish(_inp(eng), engine=eng)
    assert a.ok and _prev(eng) is None  # estado normal: aún no hay snapshot


def test_H_rollback_sin_snapshot_bloquea(eng, clean):
    res = pub.rollback("f3_tgt_virgen", engine=eng)
    assert not res.ok and res.reason == "BLOCK:NO_SNAPSHOT"


def test_F_rollback_exitoso_y_provenance(eng, clean):
    a, b = _publish_ab(eng)
    prev = _prev(eng)
    rb = pub.rollback(TGT, engine=eng)
    assert rb.ok and rb.rows == a.rows
    assert _digest(eng, TGT) == a.content_hash  # K: hash exacto
    with eng.connect() as c:
        row = c.execute(text(
            "SELECT rolled_back, rolled_back_at, restored_snapshot, "
            "snapshot_hash, snapshot_rows FROM staging._publications "
            "WHERE target=:t ORDER BY id DESC LIMIT 1"),
            {"t": TGT}).mappings().first()
    assert row["rolled_back"] and row["rolled_back_at"]  # M
    assert row["restored_snapshot"] == prev
    assert row["snapshot_hash"] == a.content_hash  # K registrado
    assert row["snapshot_rows"] == a.rows  # L registrado
    assert rb.rows == row["snapshot_rows"]  # L verificado


def test_G_rollback_repetido_idempotente(eng, clean):
    _publish_ab(eng)
    r1 = pub.rollback(TGT, engine=eng)
    assert r1.ok
    r2 = pub.rollback(TGT, engine=eng)
    assert r2.ok and r2.reason == "NOOP_ALREADY_RESTORED"  # O: idempotente


def test_C_snapshot_vacio_bloquea(eng, clean):
    _, b = _publish_ab(eng)
    prev = _prev(eng)
    with eng.begin() as c:
        c.execute(text("DELETE FROM staging.%s" % prev))
    res = pub.rollback(TGT, engine=eng)
    assert not res.ok and res.reason == "BLOCK:EMPTY_SNAPSHOT"
    assert _count(eng, TGT) == b.rows  # N: target intacto, nunca vacío


def test_C2_schema_mismatch_bloquea(eng, clean):
    _, b = _publish_ab(eng)
    prev = _prev(eng)
    with eng.begin() as c:
        cols = [r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='staging' AND table_name=:t "
            "ORDER BY ordinal_position"), {"t": prev})]
        c.execute(text("ALTER TABLE staging.%s DROP COLUMN %s" % (prev, cols[-1])))
    res = pub.rollback(TGT, engine=eng)
    assert not res.ok and res.reason == "BLOCK:SNAPSHOT_SCHEMA_MISMATCH"
    assert _count(eng, TGT) == b.rows  # N


def test_E_conteo_incorrecto_bloquea(eng, clean):
    _, b = _publish_ab(eng)
    prev = _prev(eng)
    with eng.begin() as c:
        c.execute(text("DELETE FROM staging.%s WHERE ctid IN "
                       "(SELECT ctid FROM staging.%s LIMIT 1)" % (prev, prev)))
    res = pub.rollback(TGT, engine=eng)
    assert not res.ok and res.reason == "BLOCK:SNAPSHOT_COUNT_MISMATCH"
    assert _count(eng, TGT) == b.rows  # N


def test_D_hash_incorrecto_bloquea(eng, clean):
    _, b = _publish_ab(eng)
    prev = _prev(eng)
    with eng.begin() as c:
        valcol = c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='staging' AND table_name=:t "
            "AND data_type IN ('text','character varying') "
            "ORDER BY ordinal_position LIMIT 1"), {"t": prev}).scalar()
        c.execute(text(
            "UPDATE staging.%s SET %s = 'CORRUPTO-F3' WHERE ctid IN "
            "(SELECT ctid FROM staging.%s LIMIT 1)" % (prev, valcol, prev)))
    res = pub.rollback(TGT, engine=eng)
    assert not res.ok and res.reason == "BLOCK:SNAPSHOT_HASH_MISMATCH"
    assert _digest(eng, TGT) == b.content_hash  # N: B intacto bit a bit


def test_J_target_faltante_se_recupera(eng, clean):
    a, _ = _publish_ab(eng)
    with eng.begin() as c:
        c.execute(text("DROP TABLE staging.%s" % TGT))
    res = pub.rollback(TGT, engine=eng)
    assert res.ok and res.rows == a.rows
    assert _digest(eng, TGT) == a.content_hash  # K+L


def test_I_target_protegido(eng, clean):
    for bad in ("Public.x", "UPPER", "staging.otro", "x;DROP"):
        with pytest.raises(ValueError):
            pub.check_target_name(bad)
    with eng.connect() as c:
        stray = [r[0] for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema NOT IN "
            "('staging','derived','engine','fetch_raw','identity',"
            "'identity_v1','parsed','public','information_schema','pg_catalog')"))]
    assert stray == []


def test_O_publicacion_repetida_idempotente(eng, clean):
    r1 = pub.publish(_inp(eng), engine=eng)
    r2 = pub.publish(_inp(eng), engine=eng)
    assert r1.content_hash == r2.content_hash and r1.rows == r2.rows
    assert _count(eng, TGT) == r2.rows
