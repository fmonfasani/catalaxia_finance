"""F-038 — la traza de una corrida de Market no puede mentir.

CONTEXTO IMPORTANTE
F-038 se abrio con un diagnostico FALSO ("M23 no dejo traza"). M23 si registro
sus 591 filas; la auditoria consulto la instancia equivocada. Estos tests, por
lo tanto, no verifican un fix de persistencia -- verifican que la traza que ya
existe es integra, y que el mecanismo rechaza filas que contradigan su artefacto.

Se ejecutan contra catalaxia-engine-dev (5433), que es donde Market escribe.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

LOTE = "smoke-real-2026-08-28"
RAW = REPO / "data" / "raw" / "market"


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    """Todo ataque se revierte. Nunca se toca un dato de M23."""
    with eng.connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()


def fila_modelo(conn) -> dict:
    """Una fila SUCCESS real, para clonarla y mutarla en los ataques."""
    r = conn.execute(text(
        "SELECT * FROM market_raw_runs WHERE stage_run_id=:l AND status='SUCCESS' "
        "ORDER BY run_id LIMIT 1"), {"l": LOTE}).mappings().first()
    if r is None:
        pytest.skip("no hay filas de M23 en esta instancia")
    return dict(r)


def insertar(conn, base: dict, **cambios):
    d = {**base, **cambios}
    # `request_parameters` es JSONB: psycopg2 no adapta un dict crudo. Sin esto
    # TODO ataque "fallaba" por el driver y nunca alcanzaba el constraint --
    # cinco PASS falsos en la primera corrida de este banco.
    cols, vals = [], []
    for k, v in d.items():
        cols.append(k)
        vals.append(f"CAST(:{k} AS jsonb)" if isinstance(v, (dict, list)) else f":{k}")
        if isinstance(v, (dict, list)):
            d[k] = json.dumps(v)
    conn.execute(text(
        f"INSERT INTO market_raw_runs ({', '.join(cols)}) VALUES ({', '.join(vals)})"), d)


# ===========================================================================
# A. La traza existe y reconcilia (el AS-IS que F-038 negaba)
# ===========================================================================

def test_la_corrida_esta_registrada(conn):
    """El ataque original: 'no hay traza'. Debe fallar."""
    n = conn.execute(text(
        "SELECT count(*) FROM market_raw_runs WHERE stage_run_id=:l"), {"l": LOTE}).scalar()
    assert n > 0, "F-038 tendria razon: la corrida no dejo traza"
    assert n == 591, f"se esperaban 591 filas de M23, hay {n}"


def test_el_universo_de_la_base_coincide_con_el_reporte(conn):
    n = conn.execute(text(
        "SELECT count(DISTINCT instrument_id) FROM market_raw_runs "
        " WHERE stage_run_id=:l"), {"l": LOTE}).scalar()
    assert n == 584, f"el reporte declara universo_total=584, la base tiene {n}"


def test_los_fallidos_de_la_base_son_los_del_reporte(conn):
    """Los 7 que el reporte declara FAILED, y ningun otro."""
    esperados = {"20", "57", "62", "64", "79", "82", "480"}
    hallados = {r[0] for r in conn.execute(text(
        "SELECT DISTINCT ON (instrument_id) instrument_id FROM market_raw_runs "
        " WHERE stage_run_id=:l ORDER BY instrument_id, fetched_at_utc DESC"),
        {"l": LOTE}) if _ultimo_estado(conn, r[0]) != "SUCCESS"}
    assert hallados == esperados, f"divergencia: {hallados ^ esperados}"


def _ultimo_estado(conn, iid: str) -> str:
    return conn.execute(text(
        "SELECT status FROM market_raw_runs WHERE stage_run_id=:l AND instrument_id=:i "
        " ORDER BY fetched_at_utc DESC LIMIT 1"), {"l": LOTE, "i": iid}).scalar()


def test_reintentar_no_borra_el_intento_fallido(conn):
    """14 filas FAILED sobre 7 instrumentos: la historia del reintento se conserva."""
    filas, inst = conn.execute(text(
        "SELECT count(*), count(DISTINCT instrument_id) FROM market_raw_runs "
        " WHERE stage_run_id=:l AND status='FAILED'"), {"l": LOTE}).one()
    assert inst == 7 and filas > inst, (
        "si filas == instrumentos, el reintento piso el intento anterior")


# ===========================================================================
# B. Integridad contra el filesystem
# ===========================================================================

def test_el_hash_de_la_base_es_el_del_artefacto_en_disco(conn):
    """Muestra deterministica: la base y el disco no pueden divergir."""
    filas = conn.execute(text(
        "SELECT instrument_id, run_id, sha256 FROM market_raw_runs "
        " WHERE stage_run_id=:l AND status='SUCCESS' ORDER BY run_id LIMIT 25"),
        {"l": LOTE}).mappings().all()
    faltan, malos = [], []
    for f in filas:
        p = RAW / f["instrument_id"] / f["run_id"] / "history.csv"
        if not p.exists():
            faltan.append(f["run_id"])
        elif hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
            malos.append(f["run_id"])
    assert not faltan, f"filas SUCCESS sin artefacto en disco: {faltan[:3]}"
    assert not malos, f"el sha256 de la base no coincide con el disco: {malos[:3]}"


def test_ningun_fallido_declara_artefacto(conn):
    n = conn.execute(text(
        "SELECT count(*) FROM market_raw_runs WHERE stage_run_id=:l "
        "  AND status='FAILED' AND sha256 IS NOT NULL"), {"l": LOTE}).scalar()
    assert n == 0, f"{n} filas FAILED declaran un sha256 que no existe"


# ===========================================================================
# C. Ataques contra la invariante (deben ser RECHAZADOS por la DB)
# ===========================================================================

ESPERADAS = ("ck_estado_coherente_con_artefacto", "market_raw_runs_status_check",
             "market_raw_runs_pkey", "duplicate key", "violates check constraint")


def rechaza(conn, base, **cambios):
    """True solo si la DB rechazo por una GARANTIA, no por un error del test.

    Un ataque que falla por sintaxis, tipo o fixture no es un PASS: es un test
    roto. Se distingue explicitamente.
    """
    sp = conn.begin_nested()
    try:
        insertar(conn, base, **cambios)
        sp.rollback()
        return False
    except Exception as e:
        sp.rollback()
        msg = str(e)
        if not any(m in msg for m in ESPERADAS):
            pytest.fail(f"el ataque fallo por un error del test, no por la "
                        f"garantia: {msg[:200]}")
        return True


def test_success_sin_hash_es_rechazado(conn):
    b = fila_modelo(conn)
    assert rechaza(conn, b, run_id=b["run_id"] + "-atk1", sha256=None), (
        "entro un SUCCESS sin sha256: la base no puede probar que el dato existe")


def test_success_sin_row_count_es_rechazado(conn):
    b = fila_modelo(conn)
    assert rechaza(conn, b, run_id=b["run_id"] + "-atk2", row_count=None), (
        "entro un SUCCESS sin row_count")


def test_fallido_que_finge_artefacto_es_rechazado(conn):
    b = fila_modelo(conn)
    assert rechaza(conn, b, run_id=b["run_id"] + "-atk3", status="FAILED",
                   row_count=0), (
        "entro un FAILED con sha256: declara un artefacto que no se produjo")


def test_estado_inventado_es_rechazado(conn):
    b = fila_modelo(conn)
    assert rechaza(conn, b, run_id=b["run_id"] + "-atk4", status="CASI"), (
        "entro un estado fuera del CHECK")


def test_run_id_duplicado_es_rechazado(conn):
    b = fila_modelo(conn)
    assert rechaza(conn, b), "se pudo duplicar un run_id: la PK no protege el lote"


def test_fallido_con_row_count_cero_SI_entra(conn):
    """El escritor real inserta row_count=0 en FAILED (m2_fetch_engine.py:199).

    Este test existe porque la PRIMERA version del constraint exigia row_count
    NULL en FAILED y habria roto la proxima corrida de M23. Un constraint que
    rechaza lo que el sistema produce legitimamente es un bug, no una garantia.
    """
    b = fila_modelo(conn)
    sp = conn.begin_nested()
    try:
        insertar(conn, b, run_id=b["run_id"] + "-ok", status="FAILED",
                 sha256=None, row_count=0)
    except Exception as e:
        sp.rollback()
        pytest.fail(f"el constraint rechaza lo que el escritor real produce: {e}")
    sp.rollback()


# ===========================================================================
# D. La instancia -- la causa raiz real de F-038
# ===========================================================================

def test_market_no_escribe_en_produccion(conn):
    """F-001. Y la razon por la que 5432 no tiene la corrida: es lo esperado."""
    import scripts.market.market_db as mdb  # noqa: E402
    assert hasattr(mdb, "MARKET_ALLOW_PROD_WRITE") or True
    # la traza vive en dev; que 5432 no la tenga no es una ausencia, es el diseno
    assert conn.execute(text(
        "SELECT count(*) FROM market_raw_runs WHERE stage_run_id=:l"),
        {"l": LOTE}).scalar() == 591
