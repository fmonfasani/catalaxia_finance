"""S04_normalize — tests unitarios de las reglas de normalizacion.

Las funciones de desempate, unidad y clave son PURAS: se prueban sin base.
Los casos no son inventados: salen de los datos reales de YPF medidos antes de
escribir el contrato (docs/architecture/S04_CONTRACT.md seccion 2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))

import s04_normalize as s04  # noqa: E402


def f(fact_id, valor=None, texto=None, decimals=None, nil=False):
    return {"fact_id": fact_id, "value_numeric": valor, "value_text": texto,
            "decimals": decimals, "is_nil": nil}


# ---------------------------------------------------------------------------
# T2 · desempate por precision
# ---------------------------------------------------------------------------

def test_rango_precision_ordena_inf_por_encima_de_todo():
    assert s04.rango_precision("INF") > s04.rango_precision("6")
    assert s04.rango_precision("6") > s04.rango_precision("2")
    assert s04.rango_precision("2") > s04.rango_precision(None)
    assert s04.rango_precision("-3") > s04.rango_precision(None)   # -3 es precision valida
    assert s04.rango_precision("basura") == s04.rango_precision(None)


def test_un_solo_candidato_es_unico():
    g, motivo = s04.elegir_ganador([f(1, 100, "100", "0")])
    assert motivo == "UNICO" and g["fact_id"] == 1


def test_duplicados_con_el_mismo_valor_son_identicos():
    g, motivo = s04.elegir_ganador([f(7, 100, "100", "0"), f(3, 100, "100", "0")])
    assert motivo == "IDENTICO"
    assert g["fact_id"] == 3, "con valores identicos gana el fact_id menor, no el orden"


def test_caso_real_ypf_applicabletaxrate_gana_la_mayor_precision():
    """0.30 (decimals=2) vs 0.3000 (decimals=INF): gana INF.

    Caso literal de parsed.facts, accession de YPF,
    tag=ApplicableTaxRate, context P01_01_2019To12_31_2019.
    """
    g, motivo = s04.elegir_ganador([
        f(100, 0.30, "0.30", "2"),
        f(101, 0.3000, "0.3000", "INF"),
    ])
    assert motivo == "POR_PRECISION"
    assert g["fact_id"] == 101 and g["decimals"] == "INF"


def test_caso_real_ypf_discountrate_gana_decimals_mayor():
    """0.1480 (decimals=4) vs 0.15 (decimals=2): gana 4."""
    g, motivo = s04.elegir_ganador([
        f(200, 0.15, "0.15", "2"),
        f(201, 0.1480, "0.1480", "4"),
    ])
    assert motivo == "POR_PRECISION"
    assert g["fact_id"] == 201


def test_el_orden_de_entrada_no_cambia_el_ganador():
    a, b = f(100, 0.30, "0.30", "2"), f(101, 0.3000, "0.3000", "INF")
    g1, m1 = s04.elegir_ganador([a, b])
    g2, m2 = s04.elegir_ganador([b, a])
    assert (g1["fact_id"], m1) == (g2["fact_id"], m2) == (101, "POR_PRECISION")


def test_empate_total_se_marca_y_no_se_resuelve_en_silencio():
    """Misma precision, misma longitud, valores distintos: hay que declararlo."""
    g, motivo = s04.elegir_ganador([f(9, 10, "10", "0"), f(4, 20, "20", "0")])
    assert motivo == "POR_FACT_ID", "un empate real debe quedar marcado, no oculto"
    assert g["fact_id"] == 4


def test_valores_de_texto_gana_el_mas_largo_a_igual_precision():
    g, motivo = s04.elegir_ganador([
        f(1, None, "abc", None), f(2, None, "abcdef", None)])
    assert motivo == "POR_PRECISION" and g["fact_id"] == 2


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("measure,esperado_moneda", [
    ("iso4217:ARS", "ARS"),
    ("iso4217:USD", "USD"),
    ("utr:MMBbls", None),        # unidad fisica: no es moneda
    ("xbrli:pure", None),
    ("pure", None),
])
def test_moneda_solo_sale_de_iso4217(measure, esperado_moneda):
    kind, med, cur = s04.normalizar_unidad("SIMPLE", measure, None, None)
    assert kind == "SIMPLE"
    assert med == measure
    assert cur == esperado_moneda


def test_unidad_dividida_conserva_ambos_lados():
    kind, med, cur = s04.normalizar_unidad(
        "DIVIDED", None, "iso4217:ARS", "xbrli:shares")
    assert kind == "DIVIDED"
    assert med == "iso4217:ARS/xbrli:shares"
    assert cur == "ARS", "en ARS por accion, la moneda es el numerador"


def test_sin_medida_no_se_inventa_unidad():
    assert s04.normalizar_unidad("SIMPLE", None, None, None) == (None, None, None)
    assert s04.normalizar_unidad("SIMPLE", "   ", None, None) == (None, None, None)


# ---------------------------------------------------------------------------
# fact_key: determinista, y sensible a cada componente
# ---------------------------------------------------------------------------

ARGS = ("E01ABC", "0001193125-24-000001", "ifrs-full:Revenue", "ctx1", "U1")


def test_fact_key_es_determinista():
    assert s04.fact_key(*ARGS) == s04.fact_key(*ARGS)
    assert len(s04.fact_key(*ARGS)) == 64


@pytest.mark.parametrize("i", range(5))
def test_fact_key_cambia_si_cambia_cualquier_componente(i):
    otros = list(ARGS)
    otros[i] = otros[i] + "X"
    assert s04.fact_key(*otros) != s04.fact_key(*ARGS)


def test_fact_key_trata_unidad_ausente_de_forma_estable():
    assert s04.fact_key("E", "A", "q", "c", None) == s04.fact_key("E", "A", "q", "c", "")


def test_fact_key_no_se_puede_confundir_por_concatenacion():
    """'ab|c' y 'a|bc' no deben colisionar: el separador es parte del contrato."""
    assert s04.fact_key("E", "A", "ab", "c", "U") != s04.fact_key("E", "A", "a", "bc", "U")


# ---------------------------------------------------------------------------
# El contrato de identidad
# ---------------------------------------------------------------------------

def test_la_clave_usa_entity_key_y_no_el_cik():
    """Dos entidades distintas con el mismo filing no comparten fact_key.

    Es la diferencia entre Identity v1 y el legacy: la clave es la entidad
    opaca, no el CIK.
    """
    a = s04.fact_key("E01AAA", "0001-24-1", "q", "c", "U")
    b = s04.fact_key("E01BBB", "0001-24-1", "q", "c", "U")
    assert a != b
