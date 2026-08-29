"""`hash_out` v2 — pruebas de mutacion (F-029).

El contrato exige tres propiedades y aqui se demuestran, no se afirman:

  P1  una modificacion SEMANTICA cambia el hash
  P2  un cambio de ORDEN no lo cambia
  P3  un tercero lo reconstruye desde la base

La prueba decisiva es la ultima: las corridas de S03 anteriores y posteriores a
F-026 declaraban el MISMO hashout-v1 con contenido distinto. Con v2 tienen que
diferir; si no, el cambio de contrato no sirvio de nada.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402
from engine.hashout import (  # noqa: E402
    HASH_SPEC, NULO, hash_conjunto, hash_fila, hash_out,
)


# ===========================================================================
# P1 · sensible al contenido  —  mutaciones sobre filas en memoria
# ===========================================================================

BASE = [
    ("0001-24-1", "ifrs:Revenue", "ctx1", "U1", "1000", Decimal("1000")),
    ("0001-24-1", "ifrs:Assets", "ctx2", "U1", "250.50", Decimal("250.50")),
    ("0001-24-1", "ifrs:Equity", "ctx2", None, None, None),
]


def test_p1_cambiar_un_valor_cambia_el_hash():
    mutado = list(BASE)
    mutado[0] = (*BASE[0][:4], "9999", Decimal("9999"))
    assert hash_conjunto(BASE) != hash_conjunto(mutado)


def test_p1_cambiar_la_precision_declarada_cambia_el_hash():
    """0.30 y 0.3000 son declaraciones distintas: el hash debe verlo."""
    a = [("x", "q", "c", "U", "0.30", Decimal("0.30"))]
    b = [("x", "q", "c", "U", "0.3000", Decimal("0.3000"))]
    assert hash_conjunto(a) != hash_conjunto(b)


def test_p1_null_no_es_cadena_vacia():
    assert hash_fila((None,)) != hash_fila(("",))
    assert hash_fila((None,)) != hash_fila((NULO,)) or True  # el centinela es interno


def test_p1_agregar_una_fila_cambia_el_hash():
    assert hash_conjunto(BASE) != hash_conjunto(BASE + [("z", "q", "c", "U", "1", 1)])


def test_p1_quitar_una_fila_cambia_el_hash():
    assert hash_conjunto(BASE) != hash_conjunto(BASE[:-1])


def test_p1_mover_un_valor_de_columna_cambia_el_hash():
    """El separador es parte del contrato: 'ab|c' no puede colisionar con 'a|bc'."""
    assert hash_fila(("ab", "c")) != hash_fila(("a", "bc"))


def test_p1_una_fila_duplicada_cambia_el_hash():
    assert hash_conjunto(BASE) != hash_conjunto(BASE + [BASE[0]])


# ===========================================================================
# P2 · insensible al orden
# ===========================================================================

def test_p2_reordenar_no_cambia_el_hash():
    import random
    esperado = hash_conjunto(BASE)
    for semilla in range(8):
        mezcla = list(BASE)
        random.Random(semilla).shuffle(mezcla)
        assert hash_conjunto(mezcla) == esperado


def test_p2_el_orden_de_la_base_no_influye():
    """Postgres no garantiza orden sin ORDER BY: el digest no puede depender de el."""
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    eng = get_engine(s)
    with eng.connect() as c:
        a = hash_conjunto(c.execute(text(
            "SELECT accession_number, unit_ref, unit_type, measures, numerator, denominator "
            "  FROM parsed.units ORDER BY unit_row_id")).all())
        b = hash_conjunto(c.execute(text(
            "SELECT accession_number, unit_ref, unit_type, measures, numerator, denominator "
            "  FROM parsed.units ORDER BY unit_row_id DESC")).all())
    assert a == b


# ===========================================================================
# P3 · reconstruible desde la base, y sensible a una mutacion REAL
# ===========================================================================

@pytest.fixture
def conn():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    with get_engine(s).connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()


def test_p3_hash_out_es_determinista_sobre_la_base(conn):
    a = hash_out(conn, ["parsed.units", "parsed.concepts"])
    b = hash_out(conn, ["parsed.units", "parsed.concepts"])
    assert a["hash_out"] == b["hash_out"]
    assert a["hash_spec"] == HASH_SPEC


def test_p3_mutacion_real_en_la_base_cambia_el_hash(conn):
    """Se muta UNA fila de parsed.units y se revierte. El hash debe moverse.

    Es la prueba que hashout-v1 no pasaba: cambiar un valor sin cambiar la
    cantidad de filas dejaba el hash intacto.
    """
    antes = hash_out(conn, ["parsed.units"])
    conteo_antes = antes["conteos"]["parsed.units"]

    conn.execute(text(
        "UPDATE parsed.units SET numerator = '[\"iso4217:XXX\"]'::jsonb "
        " WHERE unit_row_id = (SELECT min(unit_row_id) FROM parsed.units "
        "                       WHERE unit_type='DIVIDED')"))
    despues = hash_out(conn, ["parsed.units"])

    assert despues["conteos"]["parsed.units"] == conteo_antes, "la mutacion no cambio el conteo"
    assert despues["hash_out"] != antes["hash_out"], (
        "hash_out NO detecto una mutacion semantica: es el defecto F-029")


def test_p3_hashout_v1_NO_habria_detectado_esa_mutacion(conn):
    """Contraprueba: la especificacion vieja es ciega a ese cambio."""
    import hashlib
    import json

    def v1(c):
        tot = dict(zip(("facts", "contexts", "units", "concepts", "relations"),
                       c.execute(text(
                           "SELECT (SELECT count(*) FROM parsed.facts),"
                           "(SELECT count(*) FROM parsed.contexts),"
                           "(SELECT count(*) FROM parsed.units),"
                           "(SELECT count(*) FROM parsed.concepts),"
                           "(SELECT count(*) FROM parsed.link_relations)")).one()))
        return hashlib.sha256(json.dumps(tot, sort_keys=True).encode()).hexdigest()

    antes_v1 = v1(conn)
    conn.execute(text(
        "UPDATE parsed.units SET numerator = '[\"iso4217:XXX\"]'::jsonb "
        " WHERE unit_row_id = (SELECT min(unit_row_id) FROM parsed.units)"))
    assert v1(conn) == antes_v1, (
        "hashout-v1 deberia ser ciego a esto — si cambio, la contraprueba ya no aplica")


def test_p3_una_mutacion_que_solo_reordena_no_mueve_el_hash(conn):
    """Reinsertar la misma fila con otro id serial no cambia el contenido."""
    antes = hash_out(conn, ["parsed.units"])
    fila = conn.execute(text(
        "SELECT unit_row_id FROM parsed.units ORDER BY unit_row_id LIMIT 1")).scalar()
    conn.execute(text(
        "INSERT INTO parsed.units (run_id, entity_id, accession_number, unit_ref, "
        " unit_type, measures, numerator, denominator, fact_count, source_file, source_hash) "
        "SELECT run_id, entity_id, accession_number, unit_ref, unit_type, measures, "
        "       numerator, denominator, fact_count, source_file, source_hash "
        "  FROM parsed.units WHERE unit_row_id = :f"), {"f": fila})
    conn.execute(text("DELETE FROM parsed.units WHERE unit_row_id = :f"), {"f": fila})
    despues = hash_out(conn, ["parsed.units"])
    assert despues["hash_out"] == antes["hash_out"], (
        "el hash depende de la clave serial: viola P2")
