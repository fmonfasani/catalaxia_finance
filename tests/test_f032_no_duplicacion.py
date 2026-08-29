"""F-032 — el mismo insumo, ejecutado N veces, no crea entidades nuevas.

El defecto: tres corridas del backfill dejaron TRES copias de cada emisora
argentina sin CIK. La causa no fue un bug de escritura sino una contradiccion
entre el contrato y la implementacion: se anclaba la entidad en un identificador
(el CUIT via LEGACY_DIM_ENTITY) que la propia politica de fuentes nunca deja
llegar a autoritativo, de modo que la corrida siguiente no la encontraba.

Estos tests intentan ROMPER la correccion, no confirmarla.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine, get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

# identificadores deliberadamente libres: no colisionan con el piloto
CIK_A, CIK_B = "0007777777", "0008888888"
LEI_A = "5493001KJTIIGC8Y1R12"
CUIT_A = "30546689979"          # CUIT real y valido (YPF), usado en schema limpio


def ev(src="SEC_REGISTRY", rec="r", facts=None):
    return Evidence(src, rec, "cita reproducible para el test de F-032", "proc:test",
                    facts=facts)


def ev_cuit(rec="20-F/test"):
    """F-037: SEC_20F estableciendo un CUIT declara accession y seccion."""
    return Evidence("SEC_20F", rec, "cita del test", "proc:test",
                    facts={"accession": rec, "seccion": "Item 4.A"})


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    """Schema limpio dentro de la transaccion; se revierte siempre."""
    with eng.connect() as c:
        tx = c.begin()
        try:
            c.execute(text("SET LOCAL session_replication_role = replica"))
            c.execute(text(
                "TRUNCATE identity_v1.instrument_symbol, identity_v1.instrument, "
                "identity_v1.identifier, identity_v1.review, identity_v1.conflict, "
                "identity_v1.assertion, identity_v1.entity RESTART IDENTITY CASCADE"))
            c.execute(text("SET LOCAL session_replication_role = origin"))
            yield c
        finally:
            tx.rollback()


def n_entidades(conn) -> int:
    return conn.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar()


def sembrar(conn, cik=CIK_A, lei=None):
    key, _ = idv.resolve_or_create_entity(
        conn, preferred_name="Emisora de prueba", id_type="CIK",
        id_namespace="SEC", id_value=cik, country="AR")
    idv.assert_identifier(conn, entity_key=key, id_type="CIK", id_namespace="SEC",
                          id_value=cik, method="REGISTRY", evidence=ev())
    if lei:
        idv.assert_identifier(conn, entity_key=key, id_type="LEI", id_namespace="GLEIF",
                              id_value=lei, method="REGISTRY", evidence=ev("GLEIF", "g"))
    return key


# ===========================================================================
# ACCEPTANCE PRINCIPAL — N ejecuciones no hacen crecer el universo
# ===========================================================================

@pytest.mark.parametrize("veces", [2, 3, 5])
def test_n_ejecuciones_no_crean_entidades_nuevas(conn, veces):
    claves = set()
    for _ in range(veces):
        k, _ = idv.resolve_or_create_entity(
            conn, preferred_name="Emisora de prueba", id_type="CIK",
            id_namespace="SEC", id_value=CIK_A, country="AR")
        idv.assert_identifier(conn, entity_key=k, id_type="CIK", id_namespace="SEC",
                              id_value=CIK_A, method="REGISTRY", evidence=ev())
        claves.add(k)
    assert len(claves) == 1, f"{veces} ejecuciones produjeron {len(claves)} entity_key"
    assert n_entidades(conn) == 1


def test_n_ejecuciones_no_duplican_identificadores(conn):
    for _ in range(3):
        k = sembrar(conn, lei=LEI_A)
    n = conn.execute(text(
        "SELECT count(*) FROM identity_v1.identifier "
        " WHERE is_authoritative AND valid_to IS NULL")).scalar()
    assert n == 2, f"esperados 2 autoritativos (CIK+LEI), hay {n}"


def test_n_ejecuciones_no_duplican_bridges(conn):
    k = sembrar(conn, lei=LEI_A)
    for _ in range(3):
        idv.assert_bridge(conn, left_ref_=idv.ref("CIK", "SEC", CIK_A),
                          right_ref_=idv.ref("LEI", "GLEIF", LEI_A),
                          method="CROSS_REFERENCE",
                          evidence=Evidence("GLEIF", "g", "propuesta automatica",
                                            "proc:test"))
    n = conn.execute(text(
        "SELECT count(*) FROM identity_v1.assertion "
        " WHERE subject_type='IDENTIFIER_BRIDGE' AND valid_to IS NULL")).scalar()
    assert n == 1, f"3 propuestas del mismo bridge dejaron {n} assertions"


# ===========================================================================
# El caso EXACTO que produjo F-032
# ===========================================================================

def test_f032_ancla_que_nunca_llega_a_autoritativa_no_duplica(conn):
    """El CUIT via LEGACY es CORROBORATING: nunca autoritativo.

    Anclar ahi era la causa raiz. Se verifica que resolver por ese identificador
    NO lo encuentra (porque no es autoritativo) — y por eso el backfill NO debe
    crear la entidad, sino declararla sin ancla.
    """
    k = idv.create_entity(conn, "Argentina sin CIK", "AR")
    r = idv.assert_identifier(
        conn, entity_key=k, id_type="CUIT", id_namespace="AFIP", id_value=CUIT_A,
        method="REGISTRY",
        evidence=Evidence("LEGACY_DIM_ENTITY", "sqlite:dim_entity#1",
                          "fila legacy sin autor", "proc:legacy_import"))
    assert r.status == "CANDIDATE" and not r.is_authoritative
    # la consecuencia: no es resoluble por ese identificador
    assert idv.entity_of(conn, "CUIT", "AFIP", CUIT_A) is None
    hallada, choque = idv.resolver_por_candidatos(conn, [("CUIT", "AFIP", CUIT_A)])
    assert hallada is None and not choque, (
        "si esto resolviera, el backfill anclaria en un identificador no autoritativo")


# ===========================================================================
# Resolucion por CUALQUIERA de los identificadores (orden de fuentes)
# ===========================================================================

def test_resuelve_por_otro_identificador_de_la_misma_entidad(conn):
    """Cambiar el orden de las fuentes no puede duplicar."""
    k = sembrar(conn, lei=LEI_A)
    hallada, choque = idv.resolver_por_candidatos(
        conn, [("LEI", "GLEIF", LEI_A)])          # se busca por el OTRO identificador
    assert hallada == k and not choque
    hallada2, _ = idv.resolver_por_candidatos(
        conn, [("CIK", "SEC", CIK_A), ("LEI", "GLEIF", LEI_A)])
    assert hallada2 == k
    assert n_entidades(conn) == 1


def test_cik_existente_mas_lei_diferente_no_duplica(conn):
    k = sembrar(conn, lei=LEI_A)
    otro_lei = "5299002TRC7IFQYSW596"
    r = idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                              id_value=otro_lei, method="REGISTRY", evidence=ev("GLEIF", "g2"))
    assert r.status == "REVIEW_REQUIRED", "un segundo LEI debe ir a revision, no pisar"
    assert idv.resolution_report(conn, k)["lei"] == LEI_A, "el LEI vigente no se piso"
    assert n_entidades(conn) == 1


def test_cuit_existente_con_cik_diferente_es_conflicto_no_fusion(conn):
    """Dos identificadores que apuntan a entidades distintas NO se fusionan."""
    k1 = sembrar(conn, cik=CIK_A)
    k2 = sembrar(conn, cik=CIK_B)
    idv.assert_identifier(conn, entity_key=k2, id_type="LEI", id_namespace="GLEIF",
                          id_value=LEI_A, method="REGISTRY", evidence=ev("GLEIF", "g"))
    hallada, choque = idv.resolver_por_candidatos(
        conn, [("CIK", "SEC", CIK_A), ("LEI", "GLEIF", LEI_A)])
    assert hallada is None, "no debe elegir una de las dos por su cuenta"
    assert len(choque) == 2, f"debe reportar el choque, no fusionar: {choque}"


def test_dos_candidatos_para_la_misma_entidad_resuelven_a_una(conn):
    k = sembrar(conn, lei=LEI_A)
    hallada, choque = idv.resolver_por_candidatos(
        conn, [("CIK", "SEC", CIK_A), ("LEI", "GLEIF", LEI_A), ("CUIT", "AFIP", CUIT_A)])
    assert hallada == k and not choque


def test_candidato_con_formato_invalido_no_rompe_la_resolucion(conn):
    k = sembrar(conn)
    hallada, _ = idv.resolver_por_candidatos(
        conn, [("CUIT", "AFIP", "no-es-un-cuit"), ("CIK", "SEC", CIK_A)])
    assert hallada == k


# ===========================================================================
# Contaminacion y provenance
# ===========================================================================

def test_cuit_de_cepu_atribuido_a_ypf_sigue_rechazado(conn):
    ypf = sembrar(conn, cik="0000904851")
    cepu = sembrar(conn, cik="0001717161")
    idv.assert_identifier(conn, entity_key=cepu, id_type="CUIT", id_namespace="AFIP",
                          id_value="33650305499", method="REGULATORY_DOCUMENT",
                          evidence=ev_cuit("20-F/cepu"))
    r = idv.assert_identifier(conn, entity_key=ypf, id_type="CUIT", id_namespace="AFIP",
                              id_value="33650305499", method="REGULATORY_DOCUMENT",
                              evidence=ev_cuit("20-F/ypf"))
    assert r.status == "REJECTED"
    assert idv.entity_of(conn, "CUIT", "AFIP", "33650305499") == cepu


def test_cik_lei_sin_bridge_no_produce_cuit_autoritativo(conn):
    k = sembrar(conn, lei=LEI_A)
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei=LEI_A,
        gleif_record={"entity": {"registeredAt": {"id": "RA000009"},
                                 "registeredAs": "30-54668997-9"}},
        source_record="gleif:test", resolved_by="proc:test")
    assert r.status == "REVIEW_REQUIRED"
    assert idv.resolution_report(conn, k)["cuit"] is None


def test_provenance_incompleta_no_entra(conn):
    k = sembrar(conn)
    sp = conn.begin_nested()
    try:
        conn.execute(text(
            "INSERT INTO identity_v1.assertion (subject_type, entity_key, method, "
            " confidence, status, source_id) "
            "VALUES ('ENTITY_IDENTIFIER', :k, 'REGISTRY','AUTHORITATIVE','VERIFIED','SEC_20F')"),
            {"k": k})
        sp.rollback()
        raise AssertionError("una assertion VERIFIED sin evidencia entro")
    except AssertionError:
        raise
    except Exception:
        sp.rollback()


def test_sin_identificador_autoritativo_la_entidad_no_resuelve(conn):
    k = idv.create_entity(conn, "Sin ancla", "AR")
    rep = idv.resolution_report(conn, k)
    assert rep["cik"] is None and rep["cuit"] is None and rep["lei"] is None
    assert rep["n_autoritativos"] == 0
