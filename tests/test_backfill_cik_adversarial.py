"""Banco adversario del backfill CIK (ciclo 8, fase E).

Contrato: docs/architecture/IDENTITY_BACKFILL_CIK_CONTRACT.md

La regla que se ataca en cada caso:

    Un CIK autoritativo permite ANCLAR la entidad. Nada mas.

Estos tests intentan romperla. Un ataque que falla por sintaxis, tipo, clave
invalida o error del propio test NO cuenta como PASS: `rechaza()` distingue el
rechazo por garantia del error de harness.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402
from engine.identity_v1 import Evidence  # noqa: E402

import backfill_cik as bf  # noqa: E402

CIK_X, CIK_Y = "0009900001", "0009900002"
LEI_X = "5493001KJTIIGC8Y1R12"
CUIT_X = "30546689979"       # CUIT real y valido, en schema limpio

# Se clasifica por TIPO de excepcion, no por texto. La primera version buscaba
# nombres de constraint en el mensaje y marcaba como "error del test" los
# rechazos de los triggers de F-035, que levantan RAISE con mensaje en
# castellano y sin el nombre del trigger. El criterio correcto es: la base
# rechazo (IntegrityError / InternalError de un RAISE) vs. el test se rompio
# (KeyError, TypeError, ProgrammingError de SQL mal escrito).
from sqlalchemy.exc import IntegrityError, InternalError, DataError  # noqa: E402

RECHAZO_DE_LA_BASE = (IntegrityError, InternalError, DataError)


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    """Schema limpio dentro de una transaccion que SIEMPRE se revierte."""
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


def item(entity_id, cik, nombre="Emisora de prueba", cuit=None, ticker="TST"):
    """Una fila del inventario, como la produce la fase C."""
    return {"entity_id": entity_id, "ticker": ticker, "grupo": "sp500",
            "nombre_legacy": nombre, "cik_legacy": cik, "cuit_legacy": cuit,
            "cik": cik, "clase": bf.CLASE_B, "entity_key": None,
            "sec": {"cik_str": int(cik), "ticker": ticker, "title": nombre,
                    "_archivo": "company_tickers_test.json"}}


def n_ent(conn):
    return conn.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar()


def rechaza(conn, fn, garantia: str | None = None):
    """True solo si la BASE rechazo -- y, si se pide, por LA garantia esperada.

    `garantia` no es decorativo. Sin el, este banco tuvo un test que "pasaba"
    incluso con `ux_identifier_autoritativo_unico` borrado: lo rechazaba otra
    cosa (primero un trigger, despues `identifier_status_check`, porque el
    ataque usaba un `status` fuera del dominio). Un ataque que pasa por una
    razon distinta de la que declara no prueba nada. Se descubrio mutando.
    """
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
                    f"{type(e).__name__}: {str(e)[:220]}")


# ===========================================================================
# 1-2. El mismo CIK, y el mismo CIK contra otra entidad
# ===========================================================================

def test_01_el_mismo_cik_dos_veces_no_duplica(conn):
    a = bf.procesar(conn, item(1, CIK_X), "run-a")
    b = bf.procesar(conn, item(1, CIK_X), "run-b")
    assert a["entity_key"] == b["entity_key"]
    assert a["accion"] == "CREADA" and b["accion"] == "REUTILIZADA"
    assert n_ent(conn) == 1


def test_02_el_mismo_cik_no_puede_designar_dos_entidades(conn):
    """Dos barreras, y las dos tienen que aguantar.

    La capa de dominio NO levanta excepcion: devuelve REJECTED, que es el
    comportamiento disenado (igual que en F-032). La primera version de este
    test esperaba una excepcion y por eso "fallaba" -- error del test.
    Se verifican las dos barreras por separado: la de dominio y la de la base.
    """
    primera = bf.procesar(conn, item(1, CIK_X), "run-a")
    otra = idv.create_entity(conn, "Otra empresa distinta", "US")

    # barrera 1 -- la capa de dominio rechaza y lo declara
    r = idv.assert_identifier(
        conn, entity_key=otra, id_type="CIK", id_namespace="SEC", id_value=CIK_X,
        method="REGISTRY",
        evidence=Evidence("SEC_REGISTRY", "r", "cita del ataque 2", "proc:test"))
    assert r.status in ("REJECTED", "REVIEW_REQUIRED"), (
        f"la capa de dominio acepto un CIK ajeno: {r.status}")
    assert not r.is_authoritative

    # barrera 2 -- aunque se saltee el dominio, la BASE rechaza.
    #
    # La primera version de este ataque reusaba CUALQUIER assertion VERIFIED, y
    # entonces lo que lo rechazaba era `tg_identifier_autoritativo` (la
    # assertion pertenecia a otra entidad), no el indice unico. Se descubrio
    # mutando: al borrar el indice, el ataque seguia "pasando". Un test que
    # pasa por una razon distinta de la que declara no prueba nada.
    #
    # Aca se le da a `otra` su PROPIA assertion VERIFIED valida, de modo que lo
    # unico que puede rechazar la escritura sea el indice unico.
    # `left_ref` es obligatorio desde F-045: una assertion que sostiene un
    # identificador autoritativo declara CUAL. La version anterior de este
    # fixture lo omitia, y desde el ciclo F-045 el ataque muere antes de llegar
    # al indice unico -- que es lo que se quiere probar aca.
    aid = conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type, entity_key, left_ref, "
        " method, confidence, status, source_id, source_record, evidence, "
        " resolved_by, source_facts) "
        "VALUES ('ENTITY_IDENTIFIER', :k, :lr, 'REGISTRY', 'AUTHORITATIVE', "
        "        'VERIFIED', 'SEC_REGISTRY', 'company_tickers_test.json', "
        "        'cita valida y propia de esta entidad', 'proc:test', "
        "        CAST(:f AS jsonb)) RETURNING assertion_id"),
        {"k": otra, "lr": f"CIK:SEC:{CIK_X}", "f": '{"cik_str": 9900001}'}).scalar_one()
    # `status` del IDENTIFIER es ACTIVE|RETIRED|DISPUTED. La version anterior
    # usaba 'VERIFIED' (que es el dominio de la ASSERTION) y por eso la moria
    # `identifier_status_check` antes de llegar al indice unico.
    assert rechaza(conn, lambda: conn.execute(text(
        "INSERT INTO identity_v1.identifier "
        " (entity_key, id_type, id_namespace, id_value, is_authoritative, status, "
        "  assertion_id) VALUES (:k,'CIK','SEC',:v,TRUE,'ACTIVE',:a)"),
        {"k": otra, "v": CIK_X, "a": aid}),
        garantia="ux_identifier_autoritativo_unico"), (
        "ux_identifier_autoritativo_unico no protegio la escritura directa")

    assert idv.entity_of(conn, "CIK", "SEC", CIK_X) == primera["entity_key"]


# ===========================================================================
# 3-4. Nombre y ticker NO son identidad
# ===========================================================================

def test_03_mismo_nombre_con_cik_distinto_son_dos_entidades(conn):
    a = bf.procesar(conn, item(1, CIK_X, nombre="ACME CORP"), "run")
    b = bf.procesar(conn, item(2, CIK_Y, nombre="ACME CORP"), "run")
    assert a["entity_key"] != b["entity_key"], (
        "se fusionaron dos CIK distintos por tener el mismo nombre")
    assert n_ent(conn) == 2


def test_04_mismo_ticker_con_cik_distinto_son_dos_entidades(conn):
    """El caso COUR/Coursera, modelado."""
    a = bf.procesar(conn, item(1, CIK_X, nombre="Uno", ticker="COUR"), "run")
    b = bf.procesar(conn, item(2, CIK_Y, nombre="Dos", ticker="COUR"), "run")
    assert a["entity_key"] != b["entity_key"]
    assert n_ent(conn) == 2


# ===========================================================================
# 5-6. El CIK correcto no arrastra CUIT ni LEI
# ===========================================================================

def test_05_cik_correcto_con_cuit_legacy_incorrecto_no_contamina(conn):
    """El CUIT legacy se propone; jamas ancla ni se vuelve autoritativo."""
    r = bf.procesar(conn, item(1, CIK_X, cuit=CUIT_X), "run")
    assert r["cuit_legacy_status"] == "CANDIDATE"
    assert idv.entity_of(conn, "CUIT", "AFIP", CUIT_X) is None, (
        "un CUIT de LEGACY_DIM_ENTITY quedo resoluble: es la causa raiz de F-032")
    assert idv.resolution_report(conn, r["entity_key"])["cuit"] is None


def test_06_un_lei_no_relacionado_no_se_convierte_en_bridge(conn):
    r = bf.procesar(conn, item(1, CIK_X), "run")
    idv.assert_identifier(conn, entity_key=r["entity_key"], id_type="LEI",
                          id_namespace="GLEIF", id_value=LEI_X, method="REGISTRY",
                          evidence=Evidence("GLEIF", "g", "cita GLEIF", "proc:test"))
    n = conn.execute(text(
        "SELECT count(*) FROM identity_v1.assertion "
        " WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED'")).scalar()
    assert n == 0, "tener CIK y LEI en la misma entidad creo un bridge solo (G5)"


# ===========================================================================
# 7. Sin evidencia no se ancla
# ===========================================================================

def test_07_cik_nuevo_sin_evidencia_no_entra(conn):
    """El backfill exige el artefacto de SEC. Sin `sec` no hay cita ni facts."""
    malo = item(1, CIK_X)
    del malo["sec"]
    with pytest.raises((KeyError, TypeError)):
        bf.procesar(conn, malo, "run")
    assert n_ent(conn) == 0


def test_07b_una_assertion_verified_sin_evidencia_la_rechaza_la_base(conn):
    assert rechaza(conn, lambda: conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type, entity_key, method, "
        " confidence, status, source_id) VALUES "
        " ('ENTITY_IDENTIFIER', :k, 'REGISTRY','AUTHORITATIVE','VERIFIED','SEC_REGISTRY')"),
        {"k": idv.create_entity(conn, "Sin evidencia", "US")}))


# ===========================================================================
# 8-9. Entidades muertas (F-035)
# ===========================================================================

@pytest.mark.parametrize("estado", ["MERGED", "DISSOLVED"])
def test_08_09_una_entidad_muerta_no_adquiere_identidad(conn, estado):
    k = idv.create_entity(conn, "Difunta", "US")
    otra = idv.create_entity(conn, "Sucesora", "US")
    conn.execute(text(
        "UPDATE identity_v1.entity SET entity_status=:e, merged_into_key=:m "
        " WHERE entity_key=:k"),
        {"e": estado, "k": k, "m": otra if estado == "MERGED" else None})
    assert rechaza(conn, lambda: idv.assert_identifier(
        conn, entity_key=k, id_type="CIK", id_namespace="SEC", id_value=CIK_X,
        method="REGISTRY",
        evidence=Evidence("SEC_REGISTRY", "r", f"cita del ataque a {estado}", "proc:test")))


# ===========================================================================
# 10. El orden de las fuentes no cambia el resultado
# ===========================================================================

def test_10_cambiar_el_orden_de_las_fuentes_no_duplica(conn):
    r = bf.procesar(conn, item(1, CIK_X), "run")
    idv.assert_identifier(conn, entity_key=r["entity_key"], id_type="LEI",
                          id_namespace="GLEIF", id_value=LEI_X, method="REGISTRY",
                          evidence=Evidence("GLEIF", "g", "cita", "proc:test"))
    # ahora se resuelve por el OTRO identificador, y por ambos, en cualquier orden
    for candidatos in ([("LEI", "GLEIF", LEI_X)],
                       [("CIK", "SEC", CIK_X), ("LEI", "GLEIF", LEI_X)],
                       [("LEI", "GLEIF", LEI_X), ("CIK", "SEC", CIK_X)]):
        hallada, choque = idv.resolver_por_candidatos(conn, candidatos)
        assert hallada == r["entity_key"] and not choque, f"orden {candidatos}"
    assert bf.procesar(conn, item(1, CIK_X), "run2")["entity_key"] == r["entity_key"]
    assert n_ent(conn) == 1


# ===========================================================================
# 11. Idempotencia: tres corridas identicas
# ===========================================================================

def test_11_tres_corridas_identicas_no_cambian_nada(conn):
    lote = [item(i, str(9900000 + i).zfill(10), nombre=f"Emisora {i}") for i in range(1, 21)]
    huellas, conteos = [], []
    for vuelta in range(3):
        for it in lote:
            bf.procesar(conn, dict(it), f"run-{vuelta}")
        huellas.append(bf.hash_identidad(conn))
        conteos.append(bf.contar(conn))
    assert huellas[0] == huellas[1] == huellas[2], (
        "el contenido cambio entre corridas identicas")
    assert conteos[0] == conteos[1] == conteos[2], f"deltas: {conteos}"
    assert n_ent(conn) == 20


# ===========================================================================
# Controles del contrato que el dry-run declara
# ===========================================================================

def test_el_backfill_no_produce_ningun_cuit_autoritativo(conn):
    for i in range(1, 6):
        bf.procesar(conn, item(i, str(9900100 + i).zfill(10), cuit=CUIT_X), "run")
    assert conn.execute(text(
        "SELECT count(*) FROM identity_v1.identifier "
        " WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL")).scalar() == 0


def test_ninguna_identidad_autoritativa_viene_de_una_fuente_corroborating(conn):
    bf.procesar(conn, item(1, CIK_X, cuit=CUIT_X), "run")
    filas = conn.execute(text(
        "SELECT a.source_id, s.authority_level FROM identity_v1.identifier i "
        "  JOIN identity_v1.assertion a USING (assertion_id) "
        "  JOIN identity_v1.source s ON s.source_id = a.source_id "
        " WHERE i.is_authoritative AND i.valid_to IS NULL")).all()
    malas = [f for f in filas if f[1] != "AUTHORITATIVE"]
    assert not malas, f"identidad autoritativa desde fuente no autoritativa: {malas}"


def test_todo_cik_escrito_tiene_provenance_completa(conn):
    bf.procesar(conn, item(1, CIK_X), "run")
    f = conn.execute(text(
        "SELECT a.source_id, a.source_record, a.evidence, a.resolved_by, a.method, "
        "       a.source_facts FROM identity_v1.identifier i "
        "  JOIN identity_v1.assertion a USING (assertion_id) "
        " WHERE i.id_type='CIK'")).mappings().one()
    assert f["source_id"] == "SEC_REGISTRY"
    assert f["source_record"] and f["evidence"] and f["resolved_by"]
    assert f["resolved_by"].startswith("proc:backfill_cik@")
    assert f["source_facts"], "CIK sin evidencia estructurada"
