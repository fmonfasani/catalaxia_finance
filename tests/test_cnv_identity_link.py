"""CNV -> Identity v1 · validacion independiente del primer cruce transversal.

Estos tests NO verifican que el cruce "funcione". Verifican que el cruce no
mienta: que lo derivado quede marcado como derivado, que nada se promueva solo,
y que ningun CUIT aparezca de la nada.

El resultado del cruce es que las 9.305 presentaciones de la CNV se atribuyen a
Central Puerto por el **CIK embebido en la clave legacy** `CIK:0001717161`, no
por CUIT. Esa distincion es todo el punto: la atribucion es valida y trazable,
pero NO demuestra el CUIT.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine import identity_v1 as idv  # noqa: E402

import c3_identity_link as link  # noqa: E402


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    return get_engine(s)


@pytest.fixture(scope="module")
def poblacion(eng):
    with eng.connect() as c:
        filas = link.poblacion_cnv(c)
    if not filas:
        pytest.skip("no hay presentaciones CNV materializadas")
    return filas


# ---------------------------------------------------------------------------
# Lo derivado se declara derivado
# ---------------------------------------------------------------------------

def test_toda_atribucion_cnv_es_candidate_y_no_autoritativa(eng):
    """Un vinculo CNV nunca puede volverse identidad juridica."""
    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT i.id_value, i.is_authoritative, a.status, a.confidence, "
            "       a.source_id, a.method "
            "  FROM identity_v1.identifier i "
            "  JOIN identity_v1.assertion a USING (assertion_id) "
            " WHERE i.id_type = 'CNV_ENTITY_ID'")).mappings().all()
    assert filas, "el cruce no dejo ningun vinculo CNV"
    for f in filas:
        assert f["is_authoritative"] is False, f"vinculo CNV autoritativo: {dict(f)}"
        assert f["status"] == "CANDIDATE", f"esperado CANDIDATE, hay {f['status']}"
        assert f["confidence"] == "WEAK", f"esperado WEAK, hay {f['confidence']}"


def test_cnv_portal_sigue_siendo_discovery_only(eng):
    """CNV no declara el CUIT del emisor, solo el del auditor (ciclo 3D)."""
    with eng.connect() as c:
        nivel, para = c.execute(text(
            "SELECT authority_level, COALESCE(authoritative_for,'{}') "
            "  FROM identity_v1.source WHERE source_id='CNV_PORTAL'")).one()
    assert nivel == "DISCOVERY_ONLY"
    assert list(para) == []


# ---------------------------------------------------------------------------
# Nada se promueve solo
# ---------------------------------------------------------------------------

def test_ningun_bridge_quedo_verificado_sin_ratificacion_humana(eng):
    """Ratificar es un acto humano. El cruce no lo hace por nadie.

    Antes exigia `count == 0`: era el estado mientras no habia ratificaciones,
    no el contrato. Desde el ciclo 6 hay 3 bridges VERIFIED, ratificados por
    Federico. Lo que el contrato exige es que TODO bridge VERIFIED venga de una
    persona, con evidencia de ambos extremos y motivo escrito.
    """
    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT left_ref, right_ref, method, confidence, resolved_by, "
            "       resolution_reason, evidence FROM identity_v1.assertion "
            " WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED'")).mappings().all()
    for f in filas:
        assert f["method"] == "HUMAN_DECISION", (
            f"bridge VERIFIED sin decision humana: {f['left_ref']} ({f['method']})")
        assert f["resolved_by"] and not f["resolved_by"].startswith("proc:"), (
            f"bridge firmado por un proceso: {f['resolved_by']}")
        assert f["resolution_reason"], "bridge sin motivo declarado"
        assert "[CIK" in (f["evidence"] or "") and "[LEI" in (f["evidence"] or ""), (
            f"bridge sin evidencia de AMBOS extremos: {f['left_ref']}")


def test_ningun_cuit_fue_inventado(eng):
    """Todo CUIT autoritativo llega por una cadena demostrada, no inventado.

    Este test medía antes `count(cuit) == 0`, que era el ESTADO de la base
    mientras no habia ratificaciones — no el contrato. Tras la ratificacion
    humana de YPF, CEPU y TGSU2 (ciclo 6) hay 3 CUIT legitimos. Lo que el
    contrato exige no es que no haya CUIT: es que cada uno tenga fuente
    autoritativa, evidencia estructurada y, si la entidad esta anclada en CIK,
    un bridge CIK<->LEI ratificado por una persona.
    """
    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT v.cik, v.lei, v.cuit, a.source_id, a.source_facts "
            "  FROM identity_v1.v_entity_resolution v "
            "  JOIN identity_v1.identifier i ON i.entity_key=v.entity_key "
            "   AND i.id_type='CUIT' AND i.is_authoritative AND i.valid_to IS NULL "
            "  JOIN identity_v1.assertion a USING (assertion_id)")).mappings().all()
        for f in filas:
            assert f["source_id"] in ("GLEIF", "SEC_20F", "AFIP", "HUMAN"), (
                f"CUIT desde una fuente no autoritativa: {f['source_id']}")
            assert f["source_facts"], f"CUIT sin evidencia estructurada: {dict(f)}"
            if f["cik"] and f["lei"]:
                br = c.execute(text(
                    "SELECT resolved_by FROM identity_v1.assertion "
                    " WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED' "
                    "   AND left_ref='CIK:SEC:'||:c AND right_ref='LEI:GLEIF:'||:l"),
                    {"c": f["cik"], "l": f["lei"]}).scalar()
                assert br, f"CUIT via LEI sin bridge ratificado: CIK {f['cik']}"
                assert not br.startswith("proc:"), f"bridge firmado por un proceso: {br}"
        # y lo que NO se pudo demostrar sigue declarado
        assert c.execute(text(
            "SELECT count(*) FROM identity_v1.review WHERE status='OPEN'")).scalar() > 0


def test_no_hay_decisiones_humanas_escritas_por_un_proceso(eng):
    """Una decision humana la firma una persona, nunca un proceso.

    Antes este test exigia `count == 0`, que era el estado mientras no habia
    ratificaciones. El contrato no prohibe las decisiones humanas: prohibe que
    un proceso las firme (F-016).
    """
    with eng.connect() as c:
        firmantes = [r[0] for r in c.execute(text(
            "SELECT DISTINCT resolved_by FROM identity_v1.assertion "
            " WHERE method='HUMAN_DECISION'"))]
    culpables = [f for f in firmantes if not f or f.startswith("proc:")]
    assert not culpables, f"decisiones humanas firmadas por un proceso: {culpables}"


# ---------------------------------------------------------------------------
# El cruce es correcto y reproducible
# ---------------------------------------------------------------------------

def test_la_via_declarada_coincide_con_la_evidencia(eng, poblacion):
    """Si dice CIK_EN_CLAVE_LEGACY, el CIK tiene que estar realmente ahi."""
    with eng.connect() as c:
        for f in poblacion:
            r = link.resolver(c, f)
            if r["via"] != "CIK_EN_CLAVE_LEGACY":
                continue
            m = link.RE_CIK_EN_CLAVE_LEGACY.search(f["entity_key_legacy"])
            assert m, "se declaro CIK_EN_CLAVE_LEGACY sin CIK en la clave"
            cik = m.group(1).zfill(10)
            # el CIK debe resolver a la MISMA entidad que devolvio el resolver
            assert idv.entity_of(c, "CIK", "SEC", cik) == r["entity_key"]
            # y ese CIK debe ser autoritativo, no un candidato cualquiera
            assert c.execute(text(
                "SELECT is_authoritative FROM identity_v1.identifier "
                " WHERE id_type='CIK' AND id_value=:v AND valid_to IS NULL"),
                {"v": cik}).scalar() is True


def test_una_via_debil_no_se_disfraza_de_fuerte(eng, poblacion):
    """CUIT_AUTORITATIVO solo se declara si el CUIT realmente lo es."""
    with eng.connect() as c:
        for f in poblacion:
            r = link.resolver(c, f)
            if r["via"] == "CUIT_AUTORITATIVO":
                assert idv.entity_of(c, "CUIT", "AFIP", f["cuit"]) == r["entity_key"]
            else:
                assert idv.entity_of(c, "CUIT", "AFIP", f["cuit"]) is None, (
                    "el CUIT era autoritativo y el resolver eligio una via mas debil")


def test_el_resolver_es_idempotente_y_no_crea_entidades(eng, poblacion):
    with eng.connect() as c:
        antes = c.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar()
        primera = [link.resolver(c, f) for f in poblacion]
        segunda = [link.resolver(c, f) for f in poblacion]
        despues = c.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar()
    assert primera == segunda, "el resolver no es determinista"
    assert antes == despues, "el resolver creo entidades: un CUIT no crea identidad"


def test_toda_presentacion_atribuida_apunta_a_una_entidad_real(eng, poblacion):
    with eng.connect() as c:
        for f in poblacion:
            r = link.resolver(c, f)
            if not r["entity_key"]:
                continue
            assert c.execute(text(
                "SELECT 1 FROM identity_v1.entity WHERE entity_key=:k"),
                {"k": r["entity_key"]}).scalar(), f"entity_key fantasma: {r}"


def test_el_cruce_no_modifica_cnv(eng, poblacion):
    """Identity v1 lee CNV. No lo toca."""
    with eng.connect() as c:
        antes = c.execute(text("SELECT count(*) FROM fetch_raw.cnv_presentation")).scalar()
        for f in poblacion:
            link.resolver(c, f)
        assert c.execute(text(
            "SELECT count(*) FROM fetch_raw.cnv_presentation")).scalar() == antes
