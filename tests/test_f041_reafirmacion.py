"""Banco adversario de F-041 (ciclo 9, fase F).

Contrato: docs/architecture/F041_CONTRACT.md

La regla que se ataca:

    No se reescribe el pasado para satisfacer un contrato nuevo.

El ataque mas peligroso no es inventar facts: es EDITAR una assertion historica
para agregarlos. La base lo permitia (F-042) y ese era el camino barato para
"cerrar" F-041. Los tests 7 y 8 existen por eso.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError, InternalError

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine, get_engine  # noqa: E402

import f041_reafirmacion as f041  # noqa: E402

RECHAZO_DE_LA_BASE = (IntegrityError, InternalError, DataError)


@pytest.fixture(scope="module")
def s():
    st = load_settings()
    if st.is_prod:
        pytest.skip("EXT-010")
    return st


@pytest.fixture(scope="module")
def eng(s):
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    """Todo se revierte. Nunca se toca una fila real."""
    with eng.connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()


def rechaza(conn, fn, garantia: str | None = None):
    sp = conn.begin_nested()
    try:
        fn()
        sp.rollback()
        return False
    except RECHAZO_DE_LA_BASE as e:
        sp.rollback()
        if garantia and garantia not in str(e):
            pytest.fail(f"rechazado, pero NO por {garantia}: {str(e)[:200]}")
        return True
    except Exception as e:
        sp.rollback()
        pytest.fail(f"el ataque fallo por un error del test, no por la garantia: "
                    f"{type(e).__name__}: {str(e)[:200]}")


def alguna_historica(conn) -> int:
    return conn.execute(text(
        "SELECT min(assertion_id) FROM identity_v1.assertion "
        " WHERE status='VERIFIED' AND valid_to IS NULL")).scalar()


# ===========================================================================
# 7 y 8 -- LOS QUE IMPORTAN: no se edita ni se borra el pasado
# ===========================================================================

def test_07_no_se_puede_modificar_provenance_historica(conn):
    """El camino barato para cerrar F-041. Debe estar cerrado."""
    aid = alguna_historica(conn)
    for campo, valor in (("source_facts", '{"agregado": "a mano"}'),
                         ("evidence", "otra cita"),
                         ("source_record", "otro registro"),
                         ("source_id", "GLEIF"),
                         ("resolved_by", "otro")):
        cast = "CAST(:v AS jsonb)" if campo == "source_facts" else ":v"
        assert rechaza(conn, lambda c=campo, v=valor, k=cast: conn.execute(text(
            f"UPDATE identity_v1.assertion SET {c} = {k} WHERE assertion_id = :a"),
            {"v": v, "a": aid}),
            garantia="los hechos afirmados son inmutables"), (
            f"se pudo editar `{campo}` de una assertion historica")


def test_08_no_se_puede_borrar_evidencia_historica(conn):
    aid = alguna_historica(conn)
    assert rechaza(conn, lambda: conn.execute(text(
        "UPDATE identity_v1.assertion SET source_facts = NULL WHERE assertion_id = "
        "(SELECT min(assertion_id) FROM identity_v1.assertion WHERE source_facts IS NOT NULL)")),
        garantia="inmutables")
    assert rechaza(conn, lambda: conn.execute(text(
        "DELETE FROM identity_v1.assertion WHERE assertion_id = :a"), {"a": aid}))


def test_08b_supersession_sigue_permitida(conn):
    """Tapar el hueco no puede romper el mecanismo legitimo."""
    aid = alguna_historica(conn)
    otra = conn.execute(text(
        "SELECT max(assertion_id) FROM identity_v1.assertion")).scalar()
    sp = conn.begin_nested()
    try:
        conn.execute(text(
            "UPDATE identity_v1.assertion SET valid_to = now(), superseded_by = :o "
            " WHERE assertion_id = :a"), {"o": otra, "a": aid})
    except Exception as e:
        sp.rollback()
        pytest.fail(f"el fix de F-042 rompio la supersession: {e}")
    sp.rollback()


# ===========================================================================
# 1-6 -- la evidencia estructurada no se acepta de cualquier forma
# ===========================================================================

def test_01_source_facts_incompleto_no_pasa_la_clasificacion(conn):
    """`clasificar` construye los facts desde el artefacto: no acepta parciales."""
    fila = {"identifier_id": 1, "entity_key": "E0", "cik": "0000320193",
            "id_status": "ACTIVE", "assertion_id": 1, "source_id": "SEC_REGISTRY",
            "source_record": "submissions/CIK0000320193.json", "method": "REGISTRY",
            "confidence": "AUTHORITATIVE", "a_status": "VERIFIED",
            "resolved_by": "p", "created_at": "x", "evidence": "e", "nombre": "Apple"}
    out = f041.clasificar(fila)
    assert out["clase"] == f041.CLASE_B
    for campo in ("cik", "sec_name", "artefacto", "sha256"):
        assert out["facts"].get(campo), f"falta el campo minimo {campo}"
    assert len(out["facts"]["sha256"]) == 64


def test_02_una_fuente_no_autoritativa_no_se_estructura(conn):
    fila = {"identifier_id": 1, "entity_key": "E0", "cik": "0000320193",
            "id_status": "ACTIVE", "assertion_id": 1, "source_id": "LEGACY_DIM_ENTITY",
            "source_record": "dim_entity#1", "method": "REGISTRY",
            "confidence": "CORROBORATING", "a_status": "VERIFIED",
            "resolved_by": "p", "created_at": "x", "evidence": "e", "nombre": "X"}
    out = f041.clasificar(fila)
    assert out["clase"] == f041.CLASE_C
    assert out["facts"] is None


def test_03_accession_inexistente_no_se_estructura(conn):
    """El 20-F que no esta en disco NO se estructura desde otra fuente."""
    fila = {"identifier_id": 1, "entity_key": "E0", "cik": "0000904851",
            "id_status": "ACTIVE", "assertion_id": 1, "source_id": "SEC_20F",
            "source_record": "0000000000-00-000000", "method": "REGULATORY_DOCUMENT",
            "confidence": "AUTHORITATIVE", "a_status": "VERIFIED",
            "resolved_by": "p", "created_at": "x", "evidence": "e", "nombre": "YPF"}
    out = f041.clasificar(fila)
    assert out["clase"] == f041.CLASE_C
    assert out["facts"] is None
    assert "nunca se archivo" in out["motivo"] or "No hay nada" in out["motivo"]


def test_04_el_20f_real_de_ypf_es_no_estructurable(conn):
    """Caso real: existe `index.json` pero NO declara el CIK.

    Estructurar desde ahi seria inferir: el CIK vive en la RUTA del directorio
    de SEC, no en el contenido del artefacto.
    """
    with get_engine(load_settings()).connect() as c:
        filas = f041.pendientes(c)
    ypf = [f for f in filas if f["source_id"] == "SEC_20F"]
    if not ypf:
        pytest.skip("ya no queda la assertion SEC_20F pendiente")
    out = f041.clasificar(ypf[0])
    assert out["clase"] == f041.CLASE_C
    assert out["facts"] is None
    # y la corroboracion por OTRA fuente se registra, pero no se usa
    corr = out.get("corroboracion_independiente")
    assert corr and corr["fuente"] == "SEC_REGISTRY"
    assert "cambiaria que la sostiene" in corr["nota"]


def test_05_un_cik_que_no_coincide_es_CONFLICTO_no_correccion(conn, tmp_path,
                                                              monkeypatch):
    """Si el artefacto contradice la assertion, se abre conflicto. No se 'corrige'."""
    falso = tmp_path / "submissions"
    falso.mkdir()
    (falso / "CIK0000320193.json").write_text(
        json.dumps({"cik": 999999, "name": "OTRA COSA"}), encoding="utf-8")
    monkeypatch.setattr(f041, "REPO", tmp_path.parent)
    (tmp_path.parent / "data" / "raw").mkdir(parents=True, exist_ok=True)
    destino = tmp_path.parent / "data" / "raw" / "submissions"
    if not destino.exists():
        destino.symlink_to(falso) if hasattr(destino, "symlink_to") else None
    if not destino.exists():
        pytest.skip("no se pudo montar el artefacto falso")
    out = f041.clasificar({"identifier_id": 1, "entity_key": "E0", "cik": "0000320193",
        "id_status": "ACTIVE", "assertion_id": 1, "source_id": "SEC_REGISTRY",
        "source_record": "x", "method": "REGISTRY", "confidence": "AUTHORITATIVE",
        "a_status": "VERIFIED", "resolved_by": "p", "created_at": "x",
        "evidence": "e", "nombre": "Apple"})
    assert out["clase"] == f041.CLASE_D
    assert out["facts"] is None


def test_06_el_sha256_corresponde_al_artefacto_declarado(conn):
    import hashlib
    fila = {"identifier_id": 1, "entity_key": "E0", "cik": "0000789019",
            "id_status": "ACTIVE", "assertion_id": 1, "source_id": "SEC_REGISTRY",
            "source_record": "submissions/CIK0000789019.json", "method": "REGISTRY",
            "confidence": "AUTHORITATIVE", "a_status": "VERIFIED",
            "resolved_by": "p", "created_at": "x", "evidence": "e", "nombre": "MSFT"}
    out = f041.clasificar(fila)
    p = REPO / out["facts"]["artefacto"]
    assert out["facts"]["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()


# ===========================================================================
# 9 -- no se promueve un CIK sin evidencia
# ===========================================================================

def test_09_no_se_promueve_un_cik_sin_evidencia(conn):
    k = conn.execute(text(
        "INSERT INTO identity_v1.entity (entity_key, preferred_name, country) "
        "VALUES ('E01M14ZZZZZZZZZZZZZZZZZZZZZ','Sin evidencia','US') "
        "RETURNING entity_key")).scalar_one()
    assert rechaza(conn, lambda: conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type, entity_key, method, "
        " confidence, status, source_id) VALUES "
        " ('ENTITY_IDENTIFIER',:k,'REGISTRY','AUTHORITATIVE','VERIFIED','SEC_REGISTRY')"),
        {"k": k}))


# ===========================================================================
# 10 -- idempotencia
# ===========================================================================

def test_10_la_clasificacion_es_determinista(conn):
    with get_engine(load_settings()).connect() as c:
        filas = f041.pendientes(c)
    a = [f041.clasificar(dict(f)) for f in filas]
    b = [f041.clasificar(dict(f)) for f in filas]
    assert [x["clase"] for x in a] == [x["clase"] for x in b]
    assert [x["facts"] for x in a] == [x["facts"] for x in b]


def test_10b_lo_ya_reafirmado_sale_del_universo(conn):
    """La condicion de entrada es `source_facts IS NULL`: re-correr no repite."""
    with get_engine(load_settings()).connect() as c:
        pend = f041.pendientes(c)
    for f in pend:
        assert f["assertion_id"] is not None
    con_facts = conn.execute(text("""
        SELECT count(*) FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
         WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL
           AND a.source_facts IS NOT NULL""")).scalar()
    ids = {f["assertion_id"] for f in pend}
    assert con_facts > 0
    assert len(ids) == len(pend), "el universo trae assertions repetidas"
