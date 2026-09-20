"""F-054 — la provenance de un emisor no puede apuntar a hechos de otro.

QUE PASO
S03 borraba las ocho tablas de `parsed` enteras y reiniciaba la secuencia de
`fact_id` en 1. Con un unico emisor era un staging correcto. Con dos, cada
corrida borraba la provenance del anterior Y REUTILIZABA sus ids, de modo que
los `source_fact_ids` que `derived.fact` ya tenia guardados pasaban a resolver
contra las filas de otra empresa. No quedaban colgados: devolvian una fila
ajena, en silencio.

POR QUE NINGUN GATE LO VIO
`C-S04-005` compara `derived.fact WHERE run_id = <corrida actual>` contra
`parsed.facts WHERE run_id = <S03 actual>`. Ambos lados acotados a la corrida en
curso: dentro de una corrida todo cierra. La corrupcion aparece en la SIGUIENTE.

DOS GARANTIAS, NO UNA
  G1  el borrado tiene alcance      DELETE ... WHERE cik = X
  G2  la secuencia no se reinicia   (se elimino el setval)

Hacen cosas distintas y estos tests las separan:
  sin G1 y sin G2 -> contaminacion (ids reutilizados por otro emisor)
  sin G1, con G2  -> punteros colgados: se pierde, no se mezcla
  con G1, sin G2  -> la PK rechaza el id repetido: falla RUIDOSA

Los tests de invariante corren contra la base de trabajo (5433). Los causales
usan un schema temporal propio y no tocan nada persistido.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

# El bloque de borrado de S03, citado literalmente. Si alguien lo cambia, estos
# tests dejan de reflejar el codigo y hay que actualizarlos a conciencia.
BORRADO_S03 = "DELETE FROM parsed.facts WHERE cik = %s"


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010: no se audita contra produccion")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    with eng.connect() as c:
        yield c


# ───────────────────────── invariantes del sistema ─────────────────────────

def test_universo_tiene_mas_de_un_emisor(conn):
    """Sin dos emisores, F-054 no se puede probar ni refutar."""
    n = conn.execute(text("SELECT count(DISTINCT cik) FROM parsed.facts")).scalar()
    if n < 2:
        pytest.skip(f"solo {n} emisor en parsed.facts: F-054 no es observable")
    assert n >= 2


def test_ningun_source_fact_id_resuelve_a_otro_emisor(conn):
    """El invariante central. Se verifican TODOS los elementos del array, no el primero."""
    filas = conn.execute(text("""
        SELECT d.cik,
               count(*) FILTER (WHERE p.cik IS NOT NULL AND p.cik <> d.cik) AS ajenos,
               count(*) AS punteros
          FROM derived.fact d
          CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          LEFT JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL
         GROUP BY d.cik HAVING count(*) FILTER (
                 WHERE p.cik IS NOT NULL AND p.cik <> d.cik) > 0""")).all()
    assert not filas, f"provenance contaminada: {[(f[0], f[1]) for f in filas]}"


def test_ningun_source_fact_id_queda_colgado(conn):
    """Un puntero a un fact_id inexistente es perdida de provenance, aunque no mezcle."""
    n = conn.execute(text("""
        SELECT count(*) FROM derived.fact d
         CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          LEFT JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND p.fact_id IS NULL""")).scalar()
    assert n == 0, f"{n} punteros de provenance no resuelven a ninguna fila de parsed"


def test_rangos_de_fact_id_no_se_solapan_entre_emisores(conn):
    """Consecuencia observable de G2: cada emisor ocupa un tramo propio."""
    r = conn.execute(text(
        "SELECT cik, min(fact_id), max(fact_id) FROM parsed.facts "
        " GROUP BY cik ORDER BY min(fact_id)")).all()
    for a, b in zip(r, r[1:]):
        assert a[2] < b[1], f"{a[0]}[{a[1]}-{a[2]}] se solapa con {b[0]}[{b[1]}-{b[2]}]"


def test_la_secuencia_de_fact_id_no_fue_reiniciada(conn):
    """G2 directa: si alguien reintroduce el setval, esto cae."""
    seq = conn.execute(text("SELECT last_value FROM parsed.facts_fact_id_seq")).scalar()
    mx = conn.execute(text("SELECT max(fact_id) FROM parsed.facts")).scalar()
    assert mx is None or seq >= mx, (
        f"la secuencia ({seq}) quedo por debajo del maximo fact_id ({mx}): "
        f"el proximo INSERT reutilizaria un id vivo")


def test_fact_id_es_unico(conn):
    n = conn.execute(text("SELECT count(*) FROM (SELECT fact_id FROM parsed.facts "
                          " GROUP BY fact_id HAVING count(*)>1) x")).scalar()
    assert n == 0, f"{n} fact_id designan mas de una fila"


def test_la_provenance_no_cruza_filings(conn):
    """Un hecho derivado no puede citar hechos de otro accession."""
    n = conn.execute(text("""
        SELECT count(*) FROM derived.fact d
         CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND p.accession_number <> d.accession_number""")).scalar()
    assert n == 0, f"{n} punteros citan un filing distinto del hecho derivado"


def test_la_provenance_no_cambia_de_concepto(conn):
    n = conn.execute(text("""
        SELECT count(*) FROM derived.fact d
         CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
          JOIN parsed.facts p ON p.fact_id = s.fid
         WHERE d.valid_to IS NULL AND p.qname <> d.qname""")).scalar()
    assert n == 0, f"{n} punteros citan un concepto distinto"


# ───────────────────── garantias, probadas causalmente ─────────────────────

@pytest.fixture
def escenario(eng):
    """Dos emisores en una tabla temporal con la misma forma que parsed.facts.

    Se usa un schema temporal propio: los tests causales no tocan nada
    persistido, y aun asi ejercitan el MISMO mecanismo (secuencia + PK + DELETE
    con predicado) que usa S03.
    """
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS f054_tmp CASCADE"))
        c.execute(text("CREATE SCHEMA f054_tmp"))
        c.execute(text("CREATE SEQUENCE f054_tmp.seq"))
        c.execute(text("""
            CREATE TABLE f054_tmp.facts (
              fact_id bigint PRIMARY KEY DEFAULT nextval('f054_tmp.seq'),
              cik text NOT NULL, valor text NOT NULL)"""))
        c.execute(text("CREATE TABLE f054_tmp.derived (cik text, source_fact_ids bigint[])"))
        # emisor A
        c.execute(text("INSERT INTO f054_tmp.facts (cik, valor) "
                       "SELECT 'AAA', 'a'||g FROM generate_series(1,5) g"))
        c.execute(text("INSERT INTO f054_tmp.derived "
                       "SELECT 'AAA', array_agg(fact_id) FROM f054_tmp.facts WHERE cik='AAA'"))
    yield eng
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS f054_tmp CASCADE"))


def _estado(c):
    return c.execute(text("""
        SELECT count(*) FILTER (WHERE f.cik IS NOT NULL AND f.cik <> d.cik),
               count(*) FILTER (WHERE f.fact_id IS NULL)
          FROM f054_tmp.derived d
          CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
          LEFT JOIN f054_tmp.facts f ON f.fact_id = s.fid""")).one()


def test_G1_el_borrado_con_alcance_no_toca_al_otro_emisor(escenario):
    """G1 sola: procesar BBB con DELETE ... WHERE cik deja intacto a AAA."""
    with escenario.begin() as c:
        c.execute(text("DELETE FROM f054_tmp.facts WHERE cik = 'BBB'"))
        c.execute(text("INSERT INTO f054_tmp.facts (cik, valor) "
                       "SELECT 'BBB', 'b'||g FROM generate_series(1,5) g"))
        ajenos, colgados = _estado(c)
    assert (ajenos, colgados) == (0, 0), (
        f"con G1 la provenance de AAA debe seguir intacta; "
        f"ajenos={ajenos} colgados={colgados}")


def test_sin_G1_ni_G2_reaparece_la_CONTAMINACION(escenario):
    """El defecto historico, reproducido: borrar todo + reiniciar la secuencia
    hace que los ids de AAA sean reasignados a BBB. Los punteros de AAA no
    quedan colgados: resuelven a filas de BBB."""
    with escenario.begin() as c:
        c.execute(text("DELETE FROM f054_tmp.facts"))                 # sin G1
        c.execute(text("SELECT setval('f054_tmp.seq', 1, false)"))    # sin G2
        c.execute(text("INSERT INTO f054_tmp.facts (cik, valor) "
                       "SELECT 'BBB', 'b'||g FROM generate_series(1,5) g"))
        ajenos, colgados = _estado(c)
    assert ajenos > 0, (
        "sin alcance en el borrado y con la secuencia reiniciada la contaminacion "
        "DEBE reaparecer; si no reaparece, el diagnostico de F-054 es incorrecto")
    assert colgados == 0, "los ids fueron reutilizados, no eliminados"


def test_sin_G1_pero_con_G2_hay_perdida_no_mezcla(escenario):
    """G2 sola degrada la falla: se pierde la provenance, pero no se mezcla.
    Es la diferencia entre un dato ausente y un dato equivocado."""
    with escenario.begin() as c:
        c.execute(text("DELETE FROM f054_tmp.facts"))                 # sin G1
        c.execute(text("INSERT INTO f054_tmp.facts (cik, valor) "     # con G2
                       "SELECT 'BBB', 'b'||g FROM generate_series(1,5) g"))
        ajenos, colgados = _estado(c)
    assert ajenos == 0, "con la secuencia intacta ningun id puede cambiar de duenio"
    assert colgados > 0, "los punteros de AAA deben quedar colgados"


def test_con_G1_pero_sin_G2_la_PK_rechaza_el_id_repetido(escenario):
    """La tercera combinacion: el borrado acotado deja vivas las filas de AAA,
    asi que reiniciar la secuencia hace chocar la clave primaria. El fallo es
    RUIDOSO, que es lo que corresponde."""
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with escenario.begin() as c:
            c.execute(text("DELETE FROM f054_tmp.facts WHERE cik = 'BBB'"))   # G1
            c.execute(text("SELECT setval('f054_tmp.seq', 1, false)"))        # sin G2
            c.execute(text("INSERT INTO f054_tmp.facts (cik, valor) "
                           "SELECT 'BBB', 'b'||g FROM generate_series(1,5) g"))


def test_el_borrado_de_S03_lleva_predicado_por_cik():
    """Guarda contra la regresion literal: si vuelve el `DELETE FROM parsed.facts`
    sin WHERE, este test cae antes de que nadie corra el pipeline."""
    src = (REPO / "scripts" / "engine" / "s03_parse_ypf.py").read_text(encoding="utf-8")
    assert BORRADO_S03 in src, "S03 ya no borra parsed.facts acotando por cik"
    assert "setval(pg_get_serial_sequence('parsed.facts','fact_id')" not in src, (
        "reaparecio el reinicio de la secuencia de fact_id: es la causa raiz de F-054")


def test_S03_elige_el_insumo_de_S02_filtrando_por_cik():
    """Sin el filtro, re-parsear A despues del fetch de B toma los archivos de B
    y los escribe bajo el CIK de A."""
    src = (REPO / "scripts" / "engine" / "s03_parse_ypf.py").read_text(encoding="utf-8")
    assert "def find_s02_input_run(engine, cik" in src
    assert "d.cik = :cik" in src, (
        "la seleccion de la corrida S02 no filtra por CIK: atribucion cruzada de entrada")
