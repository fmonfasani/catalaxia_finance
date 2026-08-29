"""Identity v1 — los 12 tests exigidos por el ciclo 4.

Cada test corre dentro de una transaccion que se revierte al terminar: el schema
identity_v1 queda vacio, los tests no dependen entre si y ninguno deja residuo.

Los datos son REALES y verificados en los ciclos 3C/3D/G4/G5:
  YPF    CIK 0000904851  CUIT 30546689979  LEI 5493003N7447U18U5U53
  CEPU   CIK 0001717161  CUIT 33650305499  LEI 2549005JLIWQ6B7VNR38
  GGAL   CIK 0001114700  CUIT 30704962807  LEI 5299008H3AXIXV5G3C23 (RA999999, registeredAs None)
  TGSU2  CIK 0000931427  CUIT 30657862068  LEI 5299002TRC7IFQYSW596 (RA000010, registeredAs 30-65786206-8)
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
from engine.identity_v1 import Evidence, UnknownEntity  # noqa: E402

YPF = dict(cik="0000904851", cuit="30546689979", lei="5493003N7447U18U5U53")
CEPU = dict(cik="0001717161", cuit="33650305499", lei="2549005JLIWQ6B7VNR38")
GGAL = dict(cik="0001114700", cuit="30704962807", lei="5299008H3AXIXV5G3C23")
TGSU2 = dict(cik="0000931427", cuit="30657862068", lei="5299002TRC7IFQYSW596")

# Registros GLEIF tal como los devolvio la API en el ciclo G4.
GLEIF_TGSU2 = {"attributes": {"entity": {
    "legalName": {"name": "TRANSPORTADORA DE GAS DEL SUR S.A."},
    "registeredAt": {"id": "RA000010"}, "registeredAs": "30-65786206-8"}}}
GLEIF_GGAL = {"attributes": {"entity": {
    "legalName": {"name": "GRUPO FINANCIERO GALICIA S.A."},
    "registeredAt": {"id": "RA999999"}, "registeredAs": None}}}
GLEIF_YPF = {"attributes": {"entity": {
    "legalName": {"name": "YPF SOCIEDAD ANONIMA"},
    "registeredAt": {"id": "RA000009"}, "registeredAs": "30-54668997-9"}}}


@pytest.fixture(scope="session")
def db_engine():
    """Motor ADMINISTRATIVO, solo para el arnes.

    F-025: la aplicacion corre como `catalaxia_engine`, que no puede desactivar
    triggers ni truncar. Limpiar el schema entre tests SI requiere privilegio,
    y es una operacion del arnes, no del sistema bajo prueba. El cuerpo de cada
    test corre con `session_replication_role = origin`, o sea con todas las
    guardas activas: lo unico privilegiado es la limpieza.

    Que la app NO pueda hacer esto se verifica aparte, en
    `test_13_el_rol_de_la_app_no_puede_evadir_las_guardas`.
    """
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010: no se testea contra el puerto de produccion")
    eng = get_admin_engine(s)
    with eng.connect() as c:
        if not c.execute(text(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name='identity_v1'"
        )).scalar():
            pytest.skip("falta aplicar migrations/engine/008_identity_v1.sql")
    return eng


@pytest.fixture
def conn(db_engine):
    """Conexion aislada: schema vacio al entrar, rollback garantizado al salir.

    El TRUNCATE corre DENTRO de la transaccion (en Postgres es transaccional),
    de modo que los tests ven un identity_v1 limpio aunque el piloto de 4
    emisores este sembrado, y al revertir el piloto queda intacto. Sin esto los
    identificadores reales del piloto colisionarian con los de los tests — que
    es justamente el comportamiento correcto del sistema, pero no lo que cada
    test quiere medir.
    """
    with db_engine.connect() as c:
        tx = c.begin()
        try:
            # Desde la migracion 009 el DELETE y el TRUNCATE sobre la procedencia
            # estan prohibidos por trigger. Para limpiar el schema DENTRO de la
            # transaccion del test se desactivan los triggers un instante y se
            # vuelven a activar ANTES del cuerpo: el test corre con TODAS las
            # guardas puestas. `SET LOCAL` muere con el rollback.
            c.execute(text("SET LOCAL session_replication_role = replica"))
            c.execute(text(
                "TRUNCATE identity_v1.instrument_symbol, identity_v1.instrument, "
                "identity_v1.identifier, identity_v1.review, identity_v1.conflict, "
                "identity_v1.assertion, identity_v1.entity RESTART IDENTITY CASCADE"))
            c.execute(text("SET LOCAL session_replication_role = origin"))
            assert c.execute(text("SELECT current_setting('session_replication_role')")
                             ).scalar() == "origin"
            yield c
        finally:
            tx.rollback()


# --- helpers ---------------------------------------------------------------

def falla(conn, fn) -> str:
    """Ejecuta `fn` esperando que la base la rechace y devuelve el mensaje.

    Corre dentro de un SAVEPOINT: el error de Postgres aborta el savepoint, no
    la transaccion del test, de modo que el test puede seguir verificando el
    estado despues del rechazo.
    """
    sp = conn.begin_nested()
    try:
        fn()
    except Exception as e:            # noqa: BLE001 - se inspecciona el mensaje
        sp.rollback()
        return str(e)
    sp.rollback()
    raise AssertionError("se esperaba un rechazo de la base y no hubo ninguno")


def sql(conn, q, **params):
    return lambda: conn.execute(text(q), params)


def ev_sec(record="0000904851-24-000012"):
    return Evidence("SEC_REGISTRY", record,
                    "company_tickers.json: cik_str asignado al registrante",
                    "proc:sec_registry_seed")


def ev_20f(record, quote, seccion="Item 4.A Identity of Directors and Officers"):
    """F-037: SEC_20F estableciendo un CUIT debe declarar accession y seccion.

    La base no puede saber si el documento dice lo que la assertion afirma; si
    puede exigir que la assertion diga DONDE lo dice, para que un tercero lo abra.
    """
    return Evidence("SEC_20F", record, quote, "proc:sec_20f_parser",
                    facts={"accession": record, "seccion": seccion})


def ev_instrumento(conn, entity_key, instrument_key):
    """Procedencia obligatoria de un instrumento (F-021)."""
    return idv._insert_assertion(
        conn, subject_type="ENTITY_INSTRUMENT", entity_key=entity_key,
        left_ref=f"INSTRUMENT:{instrument_key}", right_ref=None,
        relationship="BELONGS_TO", method="LEGACY_IMPORT", confidence="WEAK",
        status="CANDIDATE",
        ev=Evidence("MARKET_CATALOG", f"market_instruments:{instrument_key}",
                    f"el catalogo de Market asocia {instrument_key} a esta entidad",
                    "proc:test"))


def sembrar(conn, nombre, datos, *, cuit=False):
    """Entidad con CIK autoritativo; opcionalmente CUIT via 20-F."""
    k = idv.create_entity(conn, nombre, country="AR")
    r = idv.assert_identifier(conn, entity_key=k, id_type="CIK", id_namespace="SEC",
                              id_value=datos["cik"], method="REGISTRY", evidence=ev_sec())
    assert r.status == "VERIFIED"
    if cuit:
        r2 = idv.assert_identifier(
            conn, entity_key=k, id_type="CUIT", id_namespace="AFIP",
            id_value=datos["cuit"], method="REGULATORY_DOCUMENT",
            evidence=ev_20f(f"20-F/{datos['cik']}", f"C.U.I.T. {datos['cuit']}"))
        assert r2.status == "VERIFIED", r2.motivo
    return k


# ===========================================================================
# TEST 1 — YPF con sus identificadores correctos resuelve bien
# ===========================================================================
def test_01_ypf_resuelve_correctamente(conn):
    k = sembrar(conn, "YPF S.A.", YPF, cuit=True)
    idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                          id_value=YPF["lei"], method="REGISTRY",
                          evidence=Evidence("GLEIF", f"lei-records/{YPF['lei']}",
                                            "GLEIF LEI record, status ISSUED",
                                            "proc:gleif_fetch"))
    rep = idv.resolution_report(conn, k)
    assert rep["cik"] == YPF["cik"]
    assert rep["cuit"] == YPF["cuit"]
    assert rep["lei"] == YPF["lei"]
    assert rep["conflictos_abiertos"] == 0
    assert rep["reviews_abiertas"] == 0
    # cada identificador tiene evidencia citable, no una afirmacion narrativa
    for a in idv.trace(conn, k):
        assert a["evidence"] and a["source_record"] and a["resolved_by"]


# ===========================================================================
# TEST 2 — YPF + el CUIT de CEPU: el error historico, ahora imposible
# ===========================================================================
def test_02_ypf_con_cuit_de_cepu_es_rechazado(conn):
    k_cepu = sembrar(conn, "Central Puerto S.A.", CEPU, cuit=True)
    k_ypf = sembrar(conn, "YPF S.A.", YPF)

    r = idv.assert_identifier(
        conn, entity_key=k_ypf, id_type="CUIT", id_namespace="AFIP",
        id_value=CEPU["cuit"], method="REGULATORY_DOCUMENT",
        evidence=ev_20f("20-F/0000904851", "supuesta mencion de CUIT"))

    assert r.status == "REJECTED"
    assert r.conflict_id is not None
    assert r.detalle["entidad_actual"] == k_cepu
    # el CUIT sigue perteneciendo SOLO a Central Puerto
    assert idv.entity_of(conn, "CUIT", "AFIP", CEPU["cuit"]) == k_cepu
    assert idv.resolution_report(conn, k_ypf)["cuit"] is None
    # y el conflicto queda abierto, no se resuelve solo
    est = conn.execute(text("SELECT state FROM identity_v1.conflict WHERE conflict_id=:c"),
                       {"c": r.conflict_id}).scalar()
    assert est == "OPEN"


# ===========================================================================
# TEST 3 — GGAL con un CUIT de un tercero: rechazado
# ===========================================================================
def test_03_ggal_con_cuit_de_tercero_es_rechazado(conn):
    k_tgs = sembrar(conn, "Transportadora de Gas del Sur S.A.", TGSU2, cuit=True)
    k_ggal = sembrar(conn, "Grupo Financiero Galicia S.A.", GGAL)

    r = idv.assert_identifier(
        conn, entity_key=k_ggal, id_type="CUIT", id_namespace="AFIP",
        id_value=TGSU2["cuit"], method="REGISTRY",
        evidence=Evidence("GLEIF", "lei-records/x", "coincidencia por nombre", "proc:x"))
    assert r.status == "REJECTED"
    assert idv.entity_of(conn, "CUIT", "AFIP", TGSU2["cuit"]) == k_tgs

    # y un CUIT invalido tampoco entra, aunque nadie mas lo reclame
    r2 = idv.assert_identifier(
        conn, entity_key=k_ggal, id_type="CUIT", id_namespace="AFIP",
        id_value="30704962801", method="REGULATORY_DOCUMENT",
        evidence=ev_20f("20-F/0001114700", "digito verificador equivocado"))
    assert r2.status == "REJECTED"
    assert "verificador" in r2.motivo


# ===========================================================================
# TEST 4 — falta el CUIT: REVIEW_REQUIRED, jamas un CUIT inventado
# ===========================================================================
def test_04_cuit_faltante_queda_en_review(conn):
    k = sembrar(conn, "Grupo Financiero Galicia S.A.", GGAL)
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei=GGAL["lei"], gleif_record=GLEIF_GGAL,
        source_record=f"gleif:lei-records/{GGAL['lei']}", resolved_by="proc:gleif_fetch")

    assert r.status == "REVIEW_REQUIRED"
    assert r.review_id is not None
    assert idv.resolution_report(conn, k)["cuit"] is None
    assert idv.resolution_report(conn, k)["reviews_abiertas"] == 1
    # el motivo dice por que, no "no se pudo"
    assert "RA999999" in r.motivo or "no asigna CUIT" in r.motivo


# ===========================================================================
# TEST 5 — dos fuentes con CIK distinto: REVIEW_REQUIRED, no "gana la ultima"
# ===========================================================================
def test_05_cik_contradictorio_queda_en_review(conn):
    k = sembrar(conn, "YPF S.A.", YPF)
    r = idv.assert_identifier(
        conn, entity_key=k, id_type="CIK", id_namespace="SEC",
        id_value=CEPU["cik"], method="REGISTRY",
        evidence=Evidence("LEGACY_DIM_ENTITY", "sqlite:dim_entity",
                          "fila legacy sin autor", "proc:legacy_import"))
    # LEGACY es CORROBORATING: ni siquiera llega a disputar el CIK vigente
    assert r.status == "CANDIDATE"
    assert r.is_authoritative is False
    assert idv.resolution_report(conn, k)["cik"] == YPF["cik"]

    # ahora una fuente que SI es autoritativa para CIK y contradice
    r2 = idv.assert_identifier(
        conn, entity_key=k, id_type="CIK", id_namespace="SEC",
        id_value=CEPU["cik"], method="REGISTRY", evidence=ev_sec("submissions/otro"))
    assert r2.status == "REVIEW_REQUIRED"
    assert r2.conflict_id is not None and r2.review_id is not None
    assert r2.detalle == {"vigente": YPF["cik"], "propuesto": CEPU["cik"]}
    # el vigente NO fue pisado
    assert idv.resolution_report(conn, k)["cik"] == YPF["cik"]


# ===========================================================================
# TEST 6 — GLEIF LEI -> CUIT valido (TGSU2, RA000010)
# ===========================================================================
def test_06_gleif_lei_a_cuit_valido(conn):
    cuit, motivo = idv.cuit_desde_gleif(GLEIF_TGSU2)
    assert cuit == TGSU2["cuit"]
    assert "RA000010" in motivo

    k = idv.create_entity(conn, "Transportadora de Gas del Sur S.A.", "AR")
    idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                          id_value=TGSU2["lei"], method="REGISTRY",
                          evidence=Evidence("GLEIF", f"lei-records/{TGSU2['lei']}",
                                            "GLEIF LEI record", "proc:gleif_fetch"))
    # entidad anclada en LEI (sin CIK): la cadena LEI -> CUIT es directa
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei=TGSU2["lei"], gleif_record=GLEIF_TGSU2,
        source_record=f"gleif:lei-records/{TGSU2['lei']}", resolved_by="proc:gleif_fetch")
    assert r.status == "VERIFIED"
    assert r.is_authoritative is True
    assert idv.resolution_report(conn, k)["cuit"] == TGSU2["cuit"]


# ===========================================================================
# TEST 7 — GLEIF LEI -> CUIT SIN puente CIK<->LEI: no se auto-verifica (G5)
# ===========================================================================
def test_07_sin_puente_cik_lei_no_hay_verificacion_automatica(conn):
    k = sembrar(conn, "YPF S.A.", YPF)          # anclada en CIK
    idv.assert_identifier(conn, entity_key=k, id_type="LEI", id_namespace="GLEIF",
                          id_value=YPF["lei"], method="REGISTRY",
                          evidence=Evidence("GLEIF", f"lei-records/{YPF['lei']}",
                                            "GLEIF LEI record", "proc:gleif_fetch"))
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei=YPF["lei"], gleif_record=GLEIF_YPF,
        source_record=f"gleif:lei-records/{YPF['lei']}", resolved_by="proc:gleif_fetch")

    assert r.status == "REVIEW_REQUIRED"        # el CUIT existe, la cadena no
    assert r.detalle["cuit"] == YPF["cuit"]
    assert idv.resolution_report(conn, k)["cuit"] is None

    # con el puente humano registrado, la misma llamada si consolida
    idv.assert_bridge(
        conn, left_ref_=idv.ref("CIK", "SEC", YPF["cik"]),
        right_ref_=idv.ref("LEI", "GLEIF", YPF["lei"]), method="HUMAN_DECISION",
        evidence=Evidence("HUMAN", "docs/architecture/IDENTITY_DECISION_RECORD.md#G5",
                          "20-F 2023 de YPF (CIK 0000904851) y el LEI record de "
                          "GLEIF declaran el mismo domicilio legal y la misma "
                          "denominacion social; verificado manualmente.",
                          "fmonfasani", reason="cierre de la arista CIK<->LEI (G5)"))
    r2 = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei=YPF["lei"], gleif_record=GLEIF_YPF,
        source_record=f"gleif:lei-records/{YPF['lei']}", resolved_by="proc:gleif_fetch")
    assert r2.status == "VERIFIED"
    assert idv.resolution_report(conn, k)["cuit"] == YPF["cuit"]


# ===========================================================================
# TEST 8 — un ticker no crea entidad ni instrumento
# ===========================================================================
def test_08_ticker_no_crea_entidad(conn):
    with pytest.raises(UnknownEntity):
        idv.link_symbol(conn, instrument_key="NYSE:YPF", id_namespace="US", symbol="YPF")
    assert conn.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar() == 0
    assert conn.execute(text("SELECT count(*) FROM identity_v1.instrument")).scalar() == 0

    # y afirmarlo como identificador jamas lo vuelve autoritativo
    k = sembrar(conn, "YPF S.A.", YPF)
    r = idv.assert_identifier(
        conn, entity_key=k, id_type="TICKER", id_namespace="US", id_value="YPF",
        method="REGISTRY", evidence=ev_sec())
    assert r.status == "CANDIDATE"
    assert r.is_authoritative is False


# ===========================================================================
# TEST 9 — TICKER/US y TICKER/BYMA son espacios distintos
# ===========================================================================
def test_09_namespaces_de_ticker_no_se_mezclan(conn):
    k_ypf = sembrar(conn, "YPF S.A.", YPF)
    k_otra = idv.create_entity(conn, "Otra emisora local", "AR")

    idv.assert_identifier(conn, entity_key=k_ypf, id_type="TICKER", id_namespace="US",
                          id_value="YPF", method="REGISTRY", evidence=ev_sec())
    idv.assert_identifier(conn, entity_key=k_otra, id_type="TICKER", id_namespace="BYMA",
                          id_value="YPF", method="REGISTRY",
                          evidence=Evidence("DERIVED_RULE", "byma:listado",
                                            "simbolo del panel local", "proc:byma"))
    filas = conn.execute(text(
        "SELECT id_namespace, entity_key FROM identity_v1.identifier "
        " WHERE id_type='TICKER' AND id_value='YPF' ORDER BY id_namespace")).fetchall()
    assert len(filas) == 2
    assert dict(filas) == {"BYMA": k_otra, "US": k_ypf}

    # a nivel instrumento, el mismo simbolo en namespaces distintos convive
    idv.register_instrument(conn, entity_key=k_ypf, instrument_key="NYSE:YPF",
                            instrument_type="ADR", exchange="NYSE", currency="USD",
                            ratio_underlying=1,
                            assertion_id=ev_instrumento(conn, k_ypf, "NYSE:YPF"))
    idv.register_instrument(conn, entity_key=k_otra, instrument_key="BYMA:YPF",
                            instrument_type="EQUITY", exchange="BYMA", currency="ARS",
                            assertion_id=ev_instrumento(conn, k_otra, "BYMA:YPF"))
    idv.link_symbol(conn, instrument_key="NYSE:YPF", id_namespace="US", symbol="YPF")
    idv.link_symbol(conn, instrument_key="BYMA:YPF", id_namespace="BYMA", symbol="YPF")

    # pero DENTRO de un namespace el simbolo vigente es unico
    msg = falla(conn, lambda: idv.link_symbol(
        conn, instrument_key="BYMA:YPF", id_namespace="US", symbol="YPF"))
    assert "ux_symbol_vigente" in msg


# ===========================================================================
# TEST 10 — la resolucion humana deja provenance completa
# ===========================================================================
def test_10_resolucion_humana_deja_provenance(conn):
    k = sembrar(conn, "Grupo Financiero Galicia S.A.", GGAL)
    r = idv.link_cuit_desde_gleif(
        conn, entity_key=k, lei=GGAL["lei"], gleif_record=GLEIF_GGAL,
        source_record=f"gleif:lei-records/{GGAL['lei']}", resolved_by="proc:gleif_fetch")
    assert r.status == "REVIEW_REQUIRED"

    res = idv.resolve_review(
        conn, r.review_id, reviewer="fmonfasani", decision="ACCEPT",
        reason=("constancia de inscripcion AFIP consultada manualmente el "
                "2026-08-25: CUIT 30-70496280-7 corresponde a GRUPO FINANCIERO "
                "GALICIA S.A., misma denominacion social del LEI record"),
        aplicar=dict(entity_key=k, id_type="CUIT", id_namespace="AFIP",
                     id_value=GGAL["cuit"]))
    assert res.status == "VERIFIED"
    assert idv.resolution_report(conn, k)["cuit"] == GGAL["cuit"]
    assert idv.resolution_report(conn, k)["reviews_abiertas"] == 0

    rev = conn.execute(text(
        "SELECT status, reviewer, decision, decision_reason, resolved_at, "
        "       resolution_assertion_id FROM identity_v1.review WHERE review_id=:r"),
        {"r": r.review_id}).mappings().one()
    assert rev["status"] == "RESOLVED"
    assert rev["reviewer"] == "fmonfasani"
    assert rev["decision_reason"] and rev["resolved_at"] and rev["resolution_assertion_id"]

    a = conn.execute(text(
        "SELECT method, confidence, resolved_by, resolution_reason, evidence "
        "  FROM identity_v1.assertion WHERE assertion_id=:a"),
        {"a": rev["resolution_assertion_id"]}).mappings().one()
    assert a["method"] == "HUMAN_DECISION"
    assert a["resolved_by"] == "fmonfasani"
    assert a["resolution_reason"] and a["evidence"]

    # no se puede cerrar dos veces ni cerrar sin revisor
    with pytest.raises(idv.IdentityError):
        idv.resolve_review(conn, r.review_id, reviewer="x", decision="ACCEPT", reason="y")
    msg = falla(conn, sql(conn,
        "INSERT INTO identity_v1.review (candidate_identifiers, reason, status) "
        "VALUES ('{}'::jsonb, 'sin revisor', 'RESOLVED')"))
    assert "ck_cierre_exige_reviewer" in msg


# ===========================================================================
# TEST 11 — una assertion historica sigue siendo auditable e inmutable
# ===========================================================================
def test_11_assertion_historica_es_inmutable_y_auditable(conn):
    k = sembrar(conn, "YPF S.A.", YPF, cuit=True)
    vieja = conn.execute(text(
        "SELECT assertion_id FROM identity_v1.assertion "
        " WHERE entity_key=:k AND left_ref LIKE 'CUIT%' ORDER BY assertion_id"),
        {"k": k}).scalar()

    nueva = idv._insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=k,
        left_ref=idv.ref("CUIT", "AFIP", YPF["cuit"]), right_ref=None,
        relationship="BELONGS_TO", method="REGISTRY", confidence="AUTHORITATIVE",
        status="VERIFIED",
        # F-036: una afirmacion de CUIT via GLEIF debe declarar la autoridad de
        # registro de forma ESTRUCTURADA, no solo mencionarla en la cita.
        ev=Evidence("GLEIF", f"lei-records/{YPF['lei']}",
                    "registeredAs 30-54668997-9 (RA000009 AFIP)", "proc:gleif_fetch",
                    facts={"registeredAt": "RA000009",
                           "registeredAs": "30-54668997-9"}))
    idv.supersede_assertion(conn, vieja, nueva=nueva)

    fila = conn.execute(text(
        "SELECT status, evidence, valid_to, superseded_by FROM identity_v1.assertion "
        " WHERE assertion_id=:a"), {"a": vieja}).mappings().one()
    assert fila["valid_to"] is not None           # cerrada
    assert fila["superseded_by"] == nueva         # encadenada
    assert fila["evidence"]                       # AUDITABLE: la cita sobrevive

    # ya no se puede reescribir el pasado
    msg = falla(conn, sql(conn, "UPDATE identity_v1.assertion SET evidence='otra cosa' "
                                " WHERE assertion_id=:a", a=vieja))
    assert "inmutable" in msg
    # ni cambiarle el estado para que "deje de haber pasado"
    msg = falla(conn, sql(conn, "UPDATE identity_v1.assertion SET status='REJECTED', "
                                "superseded_by=NULL WHERE assertion_id=:a", a=vieja))
    assert "inmutable" in msg
    # la cita sigue intacta despues de los intentos
    assert conn.execute(text("SELECT evidence FROM identity_v1.assertion "
                             " WHERE assertion_id=:a"), {"a": vieja}).scalar()

    # F-015: tampoco se toca una assertion VIGENTE. Antes esto se aceptaba.
    viva = conn.execute(text(
        "SELECT assertion_id FROM identity_v1.assertion "
        " WHERE entity_key=:k AND status='VERIFIED' AND valid_to IS NULL LIMIT 1"),
        {"k": k}).scalar()
    for campo, valor in (("evidence", "'reescrita'"), ("status", "'REJECTED'"),
                         ("source_id", "'GLEIF'"), ("resolved_by", "'otro'")):
        msg = falla(conn, sql(conn, f"UPDATE identity_v1.assertion SET {campo}={valor} "
                                    " WHERE assertion_id=:a", a=viva))
        assert "inmutables" in msg, f"{campo} pudo modificarse en una assertion vigente"
    # reapuntar la assertion a OTRA entidad (con un entity_key realmente distinto)
    k2 = sembrar(conn, "Central Puerto S.A.", CEPU)
    assert k2 != k
    msg = falla(conn, sql(conn, "UPDATE identity_v1.assertion SET entity_key=:e "
                                " WHERE assertion_id=:a", a=viva, e=k2))
    assert "inmutables" in msg

    # F-017: la procedencia y la gobernanza no se borran, en ningun estado
    otra = conn.execute(text(
        "SELECT assertion_id FROM identity_v1.assertion WHERE entity_key=:k"),
        {"k": k2}).scalar()
    for q, params in (
        ("DELETE FROM identity_v1.assertion WHERE assertion_id=:a", {"a": otra}),
        ("DELETE FROM identity_v1.assertion WHERE assertion_id=:a", {"a": vieja}),
        ("DELETE FROM identity_v1.identifier WHERE entity_key=:k", {"k": k2}),
    ):
        assert "prohibido" in falla(conn, sql(conn, q, **params))
    rid = idv.open_review(conn, entity_key=k2, candidatos={}, reason="prueba de borrado")
    assert "prohibido" in falla(conn, sql(
        conn, "DELETE FROM identity_v1.review WHERE review_id=:r", r=rid))


# ===========================================================================
# TEST 12 — un identificador autoritativo duplicado es rechazado por la base
# ===========================================================================
def test_12_identificador_autoritativo_duplicado_lo_rechaza_la_base(conn):
    """Sin pasar por la capa de dominio: la garantia vive en el schema."""
    k1 = sembrar(conn, "YPF S.A.", YPF, cuit=True)
    k2 = idv.create_entity(conn, "Impostora S.A.", "AR")
    aid = idv._insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=k2,
        left_ref=idv.ref("CUIT", "AFIP", YPF["cuit"]), right_ref=None,
        relationship="BELONGS_TO", method="REGISTRY", confidence="AUTHORITATIVE",
        status="VERIFIED", ev=ev_20f("20-F/falso", "cita fabricada"))

    INS = ("INSERT INTO identity_v1.identifier "
           "(entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id) "
           "VALUES (:e, :t, :n, :v, true, :a)")

    msg = falla(conn, sql(conn, INS, e=k2, t="CUIT", n="AFIP", v=YPF["cuit"], a=aid))
    assert "ux_identifier_autoritativo_unico" in msg
    assert idv.entity_of(conn, "CUIT", "AFIP", YPF["cuit"]) == k1

    # y un identificador autoritativo sin assertion VERIFIED tampoco entra
    k3 = idv.create_entity(conn, "Otra S.A.", "AR")
    aid2 = idv._insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=k3,
        left_ref=idv.ref("CUIT", "AFIP", TGSU2["cuit"]), right_ref=None,
        relationship="BELONGS_TO", method="CROSS_REFERENCE", confidence="WEAK",
        status="CANDIDATE", ev=None)
    msg = falla(conn, sql(conn, INS, e=k3, t="CUIT", n="AFIP", v=TGSU2["cuit"], a=aid2))
    assert "no puede ser autoritativo" in msg

    # El ticker no es identidad juridica, y ahora hay DOS barreras.
    # F-037 agrego una anterior y mas general: `SEC_REGISTRY` es autoritativa
    # para CIK y no para TICKER, asi que la assertion ni siquiera se crea.
    # Antes de F-037 la unica barrera era `ck_ticker_no_autoritativo`, sobre el
    # identifier. Se verifica que ALGUNA de las dos lo rechace.
    msg = falla(conn, lambda: idv._insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=k1,
        left_ref=idv.ref("TICKER", "US", "YPF"), right_ref=None,
        relationship="BELONGS_TO", method="REGISTRY", confidence="AUTHORITATIVE",
        status="VERIFIED", ev=ev_sec()))
    assert "NO para TICKER" in msg, "la fuente no es autoritativa para TICKER"

    # y si la assertion existiera igual, el CHECK sobre el identifier sigue ahi
    aid3 = idv._insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=k1,
        left_ref=idv.ref("TICKER", "US", "YPF"), right_ref=None,
        relationship="BELONGS_TO", method="REGISTRY", confidence="WEAK",
        status="CANDIDATE", ev=ev_sec())
    msg = falla(conn, sql(conn, INS, e=k1, t="TICKER", n="US", v="YPF", a=aid3))
    assert "ck_ticker_no_autoritativo" in msg or "no puede ser autoritativo" in msg


# ===========================================================================
# TEST 13 — F-025: el rol de la APLICACION no puede evadir ninguna guarda
# ===========================================================================
def test_13_el_rol_de_la_app_no_puede_evadir_las_guardas():
    """Las garantias de F-015 y F-017 son TRIGGERS, y un superusuario los apaga.

    Este test no usa el fixture `conn` (que es administrativo a proposito):
    abre una conexion con las credenciales REALES de la aplicacion y verifica
    que por esa via no exista camino de escape.
    """
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    app = get_engine(s)                      # rol de la aplicacion, no admin

    with app.connect() as c:
        c.begin()
        assert c.execute(text("SELECT current_user")).scalar() != s.admin_user
        assert c.execute(text(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar() is False

        for descripcion, q in (
            ("desactivar los triggers", "SET session_replication_role = replica"),
            ("borrar procedencia",      "DELETE FROM identity_v1.assertion "
                                        "WHERE assertion_id = "
                                        "(SELECT min(assertion_id) FROM identity_v1.assertion)"),
            ("truncar procedencia",     "TRUNCATE identity_v1.assertion CASCADE"),
            ("borrar una review",       "DELETE FROM identity_v1.review"),
            ("borrar un identifier",    "DELETE FROM identity_v1.identifier"),
            ("agregar una fuente",      "INSERT INTO identity_v1.source "
                                        "(source_id, descripcion, authority_level) "
                                        "VALUES ('INVENTADA','x','AUTHORITATIVE')"),
        ):
            pudo = False
            sp = c.begin_nested()
            try:
                c.execute(text(q))
                pudo = True
            except Exception:            # noqa: BLE001 - se espera el rechazo
                pass
            finally:
                sp.rollback()
            assert not pudo, (
                f"el rol de la aplicacion PUDO {descripcion}: F-025 sigue abierto")

    # y sin embargo puede hacer su trabajo
    with app.connect() as c:
        tx = c.begin()
        k = idv.create_entity(c, "prueba de permisos del rol de la app", "AR")
        # CIK deliberadamente libre: el piloto de backfill ocupo 0000320193
        # (Apple) y este test empezo a fallar con REJECTED — que era el
        # comportamiento CORRECTO del sistema. El test dependia del estado de
        # la base; ahora usa un CIK que ninguna carga reclama.
        assert idv.assert_identifier(
            c, entity_key=k, id_type="CIK", id_namespace="SEC",
            id_value="0009999999", method="REGISTRY",
            evidence=ev_sec("submissions/CIK0009999999.json")).status == "VERIFIED"
        tx.rollback()
