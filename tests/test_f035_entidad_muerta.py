"""F-035 — una entidad MERGED o DISSOLVED no adquiere identidad autoritativa.

El defecto se encontro con una escritura DIRECTA a la base, no desde Python.
Por eso estos tests atacan por las dos vias: la capa de dominio y el SQL crudo.
Si el fix solo funcionara en Python, el test de SQL directo lo delataria.

Politica documentada en IDENTITY_V1_SCHEMA.md seccion 8:
    ACTIVE / PROVISIONAL  -> pueden recibir identidad autoritativa
    MERGED / DISSOLVED    -> no
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

CIK_A, CIK_B, CIK_C = "0007777777", "0008888888", "0006666666"
LEI_A = "5493001KJTIIGC8Y1R12"
CUIT_A = "30546689979"


def ev(src="SEC_REGISTRY", rec="r"):
    return Evidence(src, rec, "cita reproducible para el test de F-035", "proc:test")


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
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


def entidad(conn, nombre="Prueba", estado="ACTIVE", destino=None):
    k = idv.create_entity(conn, nombre, "AR")
    if estado != "ACTIVE":
        conn.execute(text(
            "UPDATE identity_v1.entity SET entity_status=:s, merged_into_key=:d "
            " WHERE entity_key=:k"), {"s": estado, "d": destino, "k": k})
    return k


def assertion_ok(conn, ek, lref):
    """F-037: la fuente debe ser autoritativa PARA ESE TIPO, y declarar la
    evidencia estructurada que su clase exige."""
    tipo = lref.split(":", 1)[0]
    if tipo == "LEI":
        src, facts = "GLEIF", {"lei": lref.split(":")[-1]}
    elif tipo == "CUIT":
        src, facts = "SEC_20F", {"accession": "20-F/test", "seccion": "Item 4.A"}
    else:
        src, facts = "SEC_20F", {"accession": "20-F/test", "seccion": "Item 4.A"}
    return idv._insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=ek, left_ref=lref,
        right_ref=None, relationship="BELONGS_TO", method="REGULATORY_DOCUMENT",
        confidence="AUTHORITATIVE", status="VERIFIED",
        ev=Evidence(src, "20-F/test", "cita del test", "proc:test", facts=facts))


def insert_directo(conn, ek, id_type, ns, valor, autoritativo=True):
    """Escritura DIRECTA, sin pasar por la capa de dominio."""
    aid = assertion_ok(conn, ek, idv.ref(id_type, ns, valor))
    conn.execute(text(
        "INSERT INTO identity_v1.identifier "
        "(entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id) "
        "VALUES (:e,:t,:n,:v,:a,:aid)"),
        {"e": ek, "t": id_type, "n": ns, "v": valor, "a": autoritativo, "aid": aid})


def rechaza(conn, fn) -> str:
    sp = conn.begin_nested()
    try:
        fn()
    except Exception as e:                      # noqa: BLE001
        sp.rollback()
        return str(e)
    sp.rollback()
    raise AssertionError("se esperaba un rechazo y la base acepto")


# ===========================================================================
# EL CASO CRITICO — MERGED no adquiere identidad, por ninguna via
# ===========================================================================

@pytest.mark.parametrize("id_type,ns,valor", [
    ("CIK", "SEC", CIK_C),
    ("LEI", "GLEIF", LEI_A),
    ("CUIT", "AFIP", CUIT_A),
])
def test_merged_no_adquiere_identificador_autoritativo(conn, id_type, ns, valor):
    viva = entidad(conn, "Destino")
    muerta = entidad(conn, "Fusionada", "MERGED", viva)
    msg = rechaza(conn, lambda: insert_directo(conn, muerta, id_type, ns, valor))
    assert "MERGED" in msg and "no puede adquirir" in msg
    assert "Su identidad ya migro" in msg, "el mensaje debe decir donde afirmarlo"


def test_merged_si_puede_recibir_un_candidate(conn):
    """Una propuesta no es identidad: se admite como evidencia."""
    viva = entidad(conn, "Destino")
    muerta = entidad(conn, "Fusionada", "MERGED", viva)
    insert_directo(conn, muerta, "CUIT", "AFIP", CUIT_A, autoritativo=False)
    n = conn.execute(text(
        "SELECT count(*) FROM identity_v1.identifier WHERE entity_key=:k"),
        {"k": muerta}).scalar()
    assert n == 1


def test_dissolved_tampoco_adquiere_identidad(conn):
    k = entidad(conn, "Disuelta", "DISSOLVED")
    msg = rechaza(conn, lambda: insert_directo(conn, k, "CIK", "SEC", CIK_C))
    assert "DISSOLVED" in msg
    assert "conserva sus identificadores historicos" in msg


def test_el_fix_resiste_la_escritura_DIRECTA_a_la_base(conn):
    """Si el fix viviera solo en Python, este test lo delataria.

    Se reproduce exactamente la mutacion M7: INSERT crudo, sin la capa de
    dominio, que es como se encontro F-035.
    """
    viva = entidad(conn, "Destino")
    muerta = entidad(conn, "Fusionada", "MERGED", viva)
    aid = assertion_ok(conn, muerta, "CIK:SEC:" + CIK_C)
    msg = rechaza(conn, lambda: conn.execute(text(
        "INSERT INTO identity_v1.identifier "
        "(entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id) "
        "VALUES (:e,'CIK','SEC',:v,true,:a)"), {"e": muerta, "v": CIK_C, "a": aid}))
    assert "MERGED" in msg


def test_no_se_puede_activar_is_authoritative_por_UPDATE(conn):
    """La otra puerta: entrar como CANDIDATE y despues promoverse."""
    viva = entidad(conn, "Destino")
    muerta = entidad(conn, "Fusionada", "MERGED", viva)
    insert_directo(conn, muerta, "CIK", "SEC", CIK_C, autoritativo=False)
    msg = rechaza(conn, lambda: conn.execute(text(
        "UPDATE identity_v1.identifier SET is_authoritative=true WHERE entity_key=:k"),
        {"k": muerta}))
    assert "MERGED" in msg


# ===========================================================================
# La guarda simetrica — no se mata una entidad que sostiene identidad
# ===========================================================================

def test_no_se_fusiona_una_entidad_que_sostiene_identidad(conn):
    viva = entidad(conn, "Destino")
    k = entidad(conn, "Con identidad")
    insert_directo(conn, k, "CIK", "SEC", CIK_A)
    msg = rechaza(conn, lambda: conn.execute(text(
        "UPDATE identity_v1.entity SET entity_status='MERGED', merged_into_key=:d "
        " WHERE entity_key=:k"), {"d": viva, "k": k}))
    assert "sostiene" in msg and "no puede pasar a MERGED" in msg


def test_si_se_retira_la_identidad_la_fusion_procede(conn):
    """La guarda no bloquea la fusion legitima: indica el orden correcto."""
    viva = entidad(conn, "Destino")
    k = entidad(conn, "Con identidad")
    insert_directo(conn, k, "CIK", "SEC", CIK_A)
    conn.execute(text("UPDATE identity_v1.identifier SET valid_to=now() "
                      " WHERE entity_key=:k"), {"k": k})
    conn.execute(text("UPDATE identity_v1.entity SET entity_status='MERGED', "
                      " merged_into_key=:d WHERE entity_key=:k"), {"d": viva, "k": k})
    assert conn.execute(text(
        "SELECT entity_status FROM identity_v1.entity WHERE entity_key=:k"),
        {"k": k}).scalar() == "MERGED"


# ===========================================================================
# Lo que SI debe seguir funcionando
# ===========================================================================

def test_active_recibe_identidad_autoritativa(conn):
    k = entidad(conn, "Activa")
    r = idv.assert_identifier(conn, entity_key=k, id_type="CIK", id_namespace="SEC",
                              id_value=CIK_A, method="REGISTRY", evidence=ev())
    assert r.status == "VERIFIED" and r.is_authoritative


def test_provisional_puede_adquirir_identidad(conn):
    """Es su transicion esperada: existe sin identidad y la adquiere."""
    k = entidad(conn, "Provisional", "PROVISIONAL")
    r = idv.assert_identifier(conn, entity_key=k, id_type="CIK", id_namespace="SEC",
                              id_value=CIK_A, method="REGISTRY", evidence=ev())
    assert r.status == "VERIFIED" and r.is_authoritative


def test_conflicto_entre_dos_entidades_activas_sigue_rechazado(conn):
    a = entidad(conn, "A")
    b = entidad(conn, "B")
    insert_directo(conn, a, "CIK", "SEC", CIK_A)
    msg = rechaza(conn, lambda: insert_directo(conn, b, "CIK", "SEC", CIK_A))
    assert "ux_identifier_autoritativo_unico" in msg


def test_la_guarda_no_afecta_a_las_entidades_del_piloto(conn):
    """Regresion: ACTIVE con varios identificadores sigue funcionando."""
    k = entidad(conn, "Piloto")
    idv.assert_identifier(conn, entity_key=k, id_type="CIK", id_namespace="SEC",
                          id_value=CIK_A, method="REGISTRY", evidence=ev())
    idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                          id_value=LEI_A, method="REGISTRY", evidence=ev("GLEIF", "g"))
    rep = idv.resolution_report(conn, k)
    assert rep["cik"] == CIK_A and rep["lei"] == LEI_A


# ===========================================================================
# F-036 — un CUIT afirmado por GLEIF debe declarar la autoridad de registro
# ===========================================================================

def test_f036_cuit_via_gleif_sin_autoridad_declarada_es_rechazado(conn):
    """El ataque original: cita libre que afirma lo que GLEIF no dice."""
    k = entidad(conn, "GGAL de prueba")
    msg = rechaza(conn, lambda: conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,relationship,"
        " method,confidence,status,source_id,source_record,evidence,resolved_by) "
        "VALUES ('ENTITY_IDENTIFIER',:k,'CUIT:AFIP:30704962807','BELONGS_TO','REGISTRY',"
        " 'AUTHORITATIVE','VERIFIED','GLEIF','lei-records/x',"
        " 'GLEIF publica registeredAs 30-70496280-7 bajo RA000009','proc:atacante')"),
        {"k": k}))
    assert "ck_cuit_exige_evidencia_estructurada" in msg  # F-036 absorbido por F-037


@pytest.mark.parametrize("facts", [
    {"registeredAt": "RA999999", "registeredAs": None},      # el caso real de GGAL
    {"registeredAt": "RA999999", "registeredAs": "30-70496280-7"},
    {"registeredAt": None, "registeredAs": "30-70496280-7"},
    {"registeredAt": "RA000009", "registeredAs": None},
    {"registeredAt": "RA000009", "registeredAs": ""},
])
def test_f036_autoridad_que_no_asigna_cuit_es_rechazada(conn, facts):
    import json
    k = entidad(conn, "Prueba")
    msg = rechaza(conn, lambda: conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,relationship,"
        " method,confidence,status,source_id,source_record,evidence,resolved_by,source_facts) "
        "VALUES ('ENTITY_IDENTIFIER',:k,'CUIT:AFIP:30704962807','BELONGS_TO','REGISTRY',"
        " 'AUTHORITATIVE','VERIFIED','GLEIF','lei-records/x','cita','proc:x',"
        " CAST(:f AS JSONB))"), {"k": k, "f": json.dumps(facts)}))
    assert "ck_cuit_exige_evidencia_estructurada" in msg  # F-036 absorbido por F-037


@pytest.mark.parametrize("ra", ["RA000009", "RA000010"])
def test_f036_autoridad_valida_si_entra(conn, ra):
    """El pipeline legitimo no se rompe."""
    import json
    k = entidad(conn, "Prueba")
    conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,relationship,"
        " method,confidence,status,source_id,source_record,evidence,resolved_by,source_facts) "
        "VALUES ('ENTITY_IDENTIFIER',:k,'CUIT:AFIP:30546689979','BELONGS_TO','REGISTRY',"
        " 'AUTHORITATIVE','VERIFIED','GLEIF','lei-records/x','cita','proc:x',"
        " CAST(:f AS JSONB))"),
        {"k": k, "f": json.dumps({"registeredAt": ra, "registeredAs": "30-54668997-9"})})


def test_f036_el_pipeline_llena_los_facts(conn):
    """`link_cuit_desde_gleif` adjunta la autoridad estructurada."""
    k = entidad(conn, "TGSU2 de prueba")
    idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                          id_value="5299002TRC7IFQYSW596", method="REGISTRY",
                          evidence=ev("GLEIF", "g"))
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei="5299002TRC7IFQYSW596",
        gleif_record={"entity": {"registeredAt": {"id": "RA000010"},
                                 "registeredAs": "30-65786206-8"}},
        source_record="gleif:test", resolved_by="proc:gleif_fetch")
    assert r.status == "VERIFIED"
    facts = conn.execute(text(
        "SELECT source_facts FROM identity_v1.assertion WHERE assertion_id=:a"),
        {"a": r.assertion_id}).scalar()
    assert facts == {"registeredAt": "RA000010", "registeredAs": "30-65786206-8"}


def test_f036_gleif_sin_registeredAs_sigue_en_review(conn):
    """El caso real de GGAL: no se fuerza, queda en revision."""
    k = entidad(conn, "GGAL de prueba")
    idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                          id_value="5299008H3AXIXV5G3C23", method="REGISTRY",
                          evidence=ev("GLEIF", "g"))
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei="5299008H3AXIXV5G3C23",
        gleif_record={"entity": {"registeredAt": {"id": "RA999999"},
                                 "registeredAs": None}},
        source_record="gleif:test", resolved_by="proc:gleif_fetch")
    assert r.status == "REVIEW_REQUIRED"
    assert idv.resolution_report(conn, k)["cuit"] is None
