"""Tests F5 — E2E multifuent SEC+Market (CNV documentada, sin ejecucion nueva).

Requiere PG DEV con market_* aplicado (m19) y corridas F4 (YPF/KO).
Todo read-only salvo J (re-runs acotados m1/m2 KO, idempotentes por diseno).
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

YPF = "0000904851"
KO = "0000021344"
KO_KEY = "E01M1W68XDCYY7AS1STHXKH084Z"
DB = str(REPO / "data" / os.environ.get("SCREENER_DB", "screener.db"))


@pytest.fixture(scope="module")
def eng():
    return edb.get_engine(load_settings())


def _lite():
    return sqlite3.connect("file:%s?mode=ro" % DB, uri=True)


def test_A_sec_permanece_pass(eng):
    with eng.connect() as c:
        for cik in (YPF, KO):
            g = c.execute(text(
                "SELECT gate_status FROM engine.stage_runs "
                "WHERE stage_id='S04_normalize' AND run_id IN ("
                "SELECT run_id FROM engine.runs) AND EXISTS (SELECT 1 FROM "
                "derived.fact d WHERE d.cik=:k AND d.run_id="
                "engine.stage_runs.run_id) "
                "ORDER BY id DESC LIMIT 1"), {"k": cik}).scalar()
            assert g == "PASS", cik


def test_B_cnv_estado_real():
    con = _lite()
    assert con.execute("SELECT count(*) FROM cnv_estados_v2").fetchone()[0] > 0
    assert con.execute("SELECT count(*) FROM empresas").fetchone()[0] > 0
    con.close()


def test_C_market_estado_real(eng):
    with eng.connect() as c:
        ni = c.execute(text("SELECT count(*) FROM market_instruments")).scalar()
        np_ = c.execute(text(
            "SELECT count(*) FROM market_price_daily "
            "WHERE instrument_id IN (SELECT instrument_id FROM "
            "market_instruments WHERE ticker_canonico IN ('YPF','KO'))")).scalar()
    assert ni > 0 and np_ > 0


def test_D_identidad_sin_contaminacion(eng):
    with eng.connect() as c:
        for k in (YPF, KO):
            n0 = c.execute(text("SELECT count(DISTINCT entity_id) FROM "
                                "identity.identifiers WHERE id_value=:k "
                                "AND id_type='CIK'"), {"k": k}).scalar()
            n1 = c.execute(text("SELECT count(*) FROM identity_v1.entity "
                                "WHERE entity_key IN (SELECT entity_key FROM "
                                "identity_v1.identifier WHERE id_value=:k)"),
                           {"k": k}).scalar()
            assert n0 == 1 and n1 >= 1, k


def test_E_issuer_instrument_price_separados(eng):
    def cols(schema, t):
        with eng.connect() as c:
            return {r[0] for r in c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name=:t"),
                {"s": schema, "t": t})}
    mi, mpd = cols("public", "market_instruments"), cols("public", "market_price_daily")
    df = cols("derived", "fact")
    # issuer vive en dim_entity/identity (cik), no en market ni mezclado
    assert "cik" not in mi and "entity_key" not in mi
    assert "cik" not in mpd and "entity_key" not in mpd
    assert "cik" in df and "instrument_id" not in df and "close" not in df
    con = _lite()
    de = [r[1] for r in con.execute("PRAGMA table_info(dim_entity)").fetchall()]
    di = [r[1] for r in con.execute("PRAGMA table_info(dim_instrument)").fetchall()]
    assert "cik" in de and "cuit" in de
    assert "cik" not in di  # instrumento no conoce emisor directo
    con.close()


def test_F_provenance_completa(eng):
    with eng.connect() as c:
        bad = c.execute(text(
            "SELECT count(*) FROM market_price_daily "
            "WHERE source_run_id IS NULL OR source_hash IS NULL")).scalar()
        tot = c.execute(text("SELECT count(*) FROM market_price_daily")).scalar()
        sfx = c.execute(text("SELECT count(*) FROM derived.fact "
                             "WHERE source_fact_ids IS NULL")).scalar()
    assert tot > 0 and bad == 0 and sfx == 0


def test_G_bridge_valido(eng):
    # identity(CIK) -> dim_entity(cik->entity_id) -> dim_instrument ->
    # market_instruments(ticker_canonico) -> prices. Cada salto no vacio.
    with eng.connect() as c:
        v0 = c.execute(text("SELECT count(*) FROM identity.identifiers "
                            "WHERE id_value=:k AND id_type='CIK'"),
                       {"k": YPF}).scalar()
        mi = c.execute(text("SELECT count(*) FROM market_instruments "
                            "WHERE ticker_canonico IN ('YPF','YPFD','KO')")).scalar()
        px = c.execute(text("SELECT count(*) FROM market_price_daily "
                            "WHERE instrument_id IN (SELECT instrument_id FROM "
                            "market_instruments "
                            "WHERE ticker_canonico IN ('YPF','YPFD','KO'))")).scalar()
    con = _lite()
    de = con.execute("SELECT entity_id FROM dim_entity WHERE cik=?",
                     (YPF,)).fetchall()
    di = con.execute("SELECT count(*) FROM dim_instrument WHERE entity_id IN "
                     "(SELECT entity_id FROM dim_entity WHERE cik=?)",
                     (YPF,)).fetchone()[0]
    con.close()
    assert v0 > 0 and de and di > 0 and mi >= 3 and px > 0


def test_H_bridge_invalido_no_escribe(eng):
    from engine import identity as ident
    with eng.connect() as c:
        before = c.execute(text(
            "SELECT count(*) FROM identity.identifiers")).scalar()
    assert ident.resolve_por_cik(eng, "9999999999") == {"present": False}
    with eng.connect() as c:
        after = c.execute(text(
            "SELECT count(*) FROM identity.identifiers")).scalar()
    assert before == after  # REVIEW sin escritura


def test_I_source_isolation(eng):
    with eng.connect() as c:
        sec_cols = {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='market_price_daily'"))}
        assert "run_id" not in sec_cols and "cik" not in sec_cols
        n = c.execute(text("SELECT count(*) FROM derived.fact "
                           "WHERE cik=:k"), {"k": KO}).scalar()
    assert n > 0


def test_J_idempotencia_market(eng):
    def snap():
        with eng.connect() as c:
            return (c.execute(text("SELECT count(*) FROM market_instruments")).scalar(),
                    c.execute(text("SELECT max(close) FROM market_price_daily "
                                   "WHERE instrument_id IN (SELECT instrument_id FROM "
                                   "market_instruments WHERE ticker_canonico='KO')")).scalar())
    before = snap()
    for script, args in (("m1_symbol_mapping.py", []),
                         ("m2_fetch_engine.py", ["--instruments", "KO"])):
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "market" / script),
                            *args], capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, (script, r.stderr[-800:])
    after = snap()
    assert before == after


def test_K_sin_duplicate_instrument(eng):
    # El mismo canonico en dos venues (YPFD/BUE+YPFD vs YPFD/NYSE+YPF) son
    # DOS instrumentos: la unicidad real es (canonico, exchange).
    with eng.connect() as c:
        d = c.execute(text("SELECT count(*) - count(DISTINCT (ticker_canonico, "
                           "exchange)) FROM market_instruments")).scalar()
        dual = c.execute(text("SELECT count(DISTINCT ticker_canonico) FROM "
                              "market_instruments GROUP BY ticker_canonico "
                              "HAVING count(*) > 1")).all()
    assert d == 0 and len(dual) > 0  # dual-listing existe y esta modelado


def test_L_sin_duplicate_issuer(eng):
    con = _lite()
    d = con.execute("SELECT count(*) - count(DISTINCT cik) FROM dim_entity "
                    "WHERE cik IS NOT NULL").fetchone()[0]
    con.close()
    assert d == 0


def test_M_sin_orphan_bridge(eng):
    with eng.connect() as c:
        orph_px = c.execute(text("SELECT count(*) FROM market_price_daily p "
                                 "WHERE NOT EXISTS (SELECT 1 FROM "
                                 "market_instruments i WHERE i.instrument_id="
                                 "p.instrument_id)")).scalar()
        orph_mp = c.execute(text("SELECT count(*) FROM market_symbol_mappings m "
                                 "WHERE NOT EXISTS (SELECT 1 FROM "
                                 "market_instruments i WHERE i.instrument_id="
                                 "m.instrument_id)")).scalar()
    assert orph_px == 0 and orph_mp == 0
    con = _lite()
    orph_di = con.execute("SELECT count(*) FROM dim_instrument di WHERE NOT "
                          "EXISTS (SELECT 1 FROM dim_entity de WHERE "
                          "de.entity_id=di.entity_id)").fetchone()[0]
    con.close()
    assert orph_di == 0


def test_N_sin_cross_source_overwrite(eng):
    import json as _j
    with eng.connect() as c:
        fy = c.execute(text("SELECT count(*) FROM derived.fact WHERE cik=:k"),
                       {"k": YPF}).scalar()
        rep = c.execute(text(
            "SELECT report FROM engine.stage_runs WHERE stage_id='S04_normalize' "
            "AND run_id IN (SELECT run_id FROM engine.runs) AND EXISTS "
            "(SELECT 1 FROM derived.fact d WHERE d.cik=:k AND "
            "d.run_id=engine.stage_runs.run_id) "
            "ORDER BY id DESC LIMIT 1"), {"k": YPF}).scalar()
        rep = _j.loads(rep) if isinstance(rep, str) else rep
        my = [tuple(r) for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name LIKE 'market\\_%' "
            "ESCAPE '\\' ORDER BY 1")).all()]
    assert fy == rep["coverage"]["parsed"] and len(my) == 10
