"""F-055 — un contexto no cambia de identidad porque cambie el orden del XML.

QUE PASO
SEC publica dos representaciones del mismo filing: el documento inline (`.htm`)
y la instancia extraida (`_htm.xml`). S03 parsea ambas. Las dos serializan la
lista de dimensiones del contexto en distinto ORDEN, y la comparacion era
`dimensions::text`, sensible al orden.

`contextos_deduplicados()` no se limita a reportar lo contradictorio: lo
DESCARTA. Un hecho cuyo contexto no entra en el mapa no llega a `derived.fact`.
Resultado: 3.562 contextos falsamente contradictorios y los hechos que los
usaban perdidos en silencio. En GGAL fueron 4.915 hechos.

LA REGLA
Una lista de dimensiones es un CONJUNTO, no una secuencia. Y una dimension
tipada guarda el fragmento XML crudo, que arrastra los `xmlns` vigentes en ese
punto del documento — distintos dentro de un XHTML que dentro de una instancia
XBRL. Se canoniza ordenando los elementos y quitando ese ruido.

DOS DIRECCIONES
Una canonizacion que absorbe de mas es peor que el defecto que vino a arreglar.
Estos tests atacan las dos: que lo equivalente se reconozca, y que lo distinto
siga distinguiendose.

Limite conocido: la comparacion no incluye `scheme` ni `identifier` del
contexto. Ver docs/review/F060_FINDING.md — registrado, no corregido.
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

# Se importa la canonizacion REAL del implementador: si alguien la revierte a
# `dimensions::text`, estos tests caen. Ese es el vinculo causal.
sys.path.insert(0, str(REPO / "scripts" / "engine"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "s04_bajo_prueba", REPO / "scripts" / "engine" / "s04_normalize.py")
_s04 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_s04)

SQL_CANON = _s04.SQL_CTX_CANONICO
TUPLA = "(start_date, end_date, instant_date, period_kind, dims_c, typed_c)::text"


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


def _conflictos(c, extra_where: str = "") -> int:
    return c.execute(text(f"""
        SELECT count(*) FROM (SELECT accession_number, context_id
          FROM ({SQL_CANON}) z {extra_where}
          GROUP BY 1,2 HAVING count(DISTINCT {TUPLA}) > 1) x""")).scalar()


# ───────────────────────── invariantes del sistema ─────────────────────────

def test_no_quedan_contextos_contradictorios(conn):
    """El estado que F-055 debe garantizar."""
    n = _conflictos(conn)
    assert n == 0, f"{n} contextos siguen declarandose contradictorios"


def test_la_comparacion_ingenua_marcaba_falsos_positivos(conn):
    """Si la comparacion ingenua no marcaba nada, la correccion no corrigio nada
    y estos tests no prueban lo que dicen probar."""
    ingenuos = conn.execute(text("""
        SELECT count(*) FROM (SELECT accession_number, context_id FROM parsed.contexts
          GROUP BY 1,2 HAVING count(DISTINCT (start_date,end_date,instant_date,
            period_kind,dimensions,typed_dimensions)::text) > 1) x""")).scalar()
    if ingenuos == 0:
        pytest.skip("no hay filings con doble representacion en la base actual")
    assert ingenuos > 0


def test_ningun_hecho_depende_de_un_contexto_descartable(conn):
    """La consecuencia de un contexto contradictorio es que sus hechos se pierden."""
    n = conn.execute(text(f"""
        SELECT count(*) FROM parsed.facts f
         WHERE (f.accession_number, f.context_id) IN (
           SELECT accession_number, context_id FROM ({SQL_CANON}) z
            GROUP BY 1,2 HAVING count(DISTINCT {TUPLA}) > 1)""")).scalar()
    assert n == 0, f"{n} hechos serian descartados por contexto contradictorio"


def test_conservacion_derived_es_un_hecho_por_grupo_canonico(conn):
    """El control central, y el que no depende de ningun conteo declarado por el
    pipeline: `derived.fact` debe tener exactamente un hecho por grupo
    (cik, accession, qname, context_id, unit_ref) de `parsed.facts`.

    Si la deduplicacion pierde algo, la diferencia deja de ser cero. Si duplica,
    tambien.
    """
    filas = conn.execute(text("""
        SELECT g.cik, g.n AS grupos, coalesce(d.n, 0) AS derivados
          FROM (SELECT cik, count(*) n FROM (
                  SELECT cik, accession_number, qname, context_id,
                         coalesce(unit_ref,'') u
                    FROM parsed.facts GROUP BY 1,2,3,4,5) x GROUP BY cik) g
          LEFT JOIN (SELECT cik, count(*) n FROM derived.fact
                      WHERE valid_to IS NULL GROUP BY cik) d USING (cik)""")).all()
    desvios = [(f[0], f[1], f[2]) for f in filas if f[1] != f[2]]
    assert not desvios, (
        "grupos canonicos de parsed != hechos en derived: "
        + "; ".join(f"{c}: {g} vs {d}" for c, g, d in desvios))


# ────────────────── la regla, atacada en las dos direcciones ──────────────────

@pytest.fixture
def ctx_tmp(eng):
    """Tabla temporal con la misma forma que `parsed.contexts`, sembrada con un
    contexto real de dos dimensiones tomado de la base."""
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS f055_tmp CASCADE"))
        c.execute(text("CREATE SCHEMA f055_tmp"))
        c.execute(text("""
            CREATE TABLE f055_tmp.contexts AS
            SELECT * FROM parsed.contexts
             WHERE jsonb_typeof(dimensions) = 'array'
               AND jsonb_array_length(dimensions) >= 2
               AND end_date IS NOT NULL
             LIMIT 1"""))
        n = c.execute(text("SELECT count(*) FROM f055_tmp.contexts")).scalar()
    if n == 0:
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS f055_tmp CASCADE"))
        pytest.skip("no hay contextos de duracion con >=2 dimensiones para atacar")
    yield eng
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS f055_tmp CASCADE"))


def _conflictos_tmp(c) -> int:
    sql = SQL_CANON.replace("FROM parsed.contexts", "FROM f055_tmp.contexts")
    return c.execute(text(f"""
        SELECT count(*) FROM (SELECT accession_number, context_id FROM ({sql}) z
          GROUP BY 1,2 HAVING count(DISTINCT {TUPLA}) > 1) x""")).scalar()


def test_permutar_el_orden_de_dimensiones_NO_genera_conflicto(ctx_tmp):
    """La direccion que F-055 vino a arreglar."""
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900000, run_id, entity_id, accession_number, context_id,
                   scheme, identifier, start_date, end_date, instant_date, period_kind,
                   (SELECT jsonb_agg(x ORDER BY x::text DESC)
                      FROM jsonb_array_elements(dimensions) x),
                   typed_dimensions, dim_count, has_typed,
                   source_file || '.permutado', source_hash
              FROM f055_tmp.contexts"""))
        n = _conflictos_tmp(c)
    assert n == 0, ("el mismo contexto con las dimensiones en otro orden se "
                    "declaro contradictorio: F-055 volvio")


def test_duplicado_identico_NO_genera_conflicto(ctx_tmp):
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900001, run_id, entity_id, accession_number, context_id,
                   scheme, identifier, start_date, end_date, instant_date, period_kind,
                   dimensions, typed_dimensions, dim_count, has_typed,
                   source_file || '.copia', source_hash
              FROM f055_tmp.contexts"""))
        n = _conflictos_tmp(c)
    assert n == 0


def test_cambiar_un_miembro_de_dimension_SI_genera_conflicto(ctx_tmp):
    """La direccion opuesta: la canonizacion no debe absorber diferencias reales."""
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900002, run_id, entity_id, accession_number, context_id,
                   scheme, identifier, start_date, end_date, instant_date, period_kind,
                   jsonb_set(dimensions, '{0,member}', '"zz:MiembroFalso"'),
                   typed_dimensions, dim_count, has_typed,
                   source_file || '.miembro', source_hash
              FROM f055_tmp.contexts"""))
        n = _conflictos_tmp(c)
    assert n == 1, "un miembro de dimension distinto es un contexto distinto"


def test_cambiar_el_periodo_SI_genera_conflicto(ctx_tmp):
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900003, run_id, entity_id, accession_number, context_id,
                   scheme, identifier, start_date, end_date + INTERVAL '1 day',
                   instant_date, period_kind, dimensions, typed_dimensions,
                   dim_count, has_typed, source_file || '.periodo', source_hash
              FROM f055_tmp.contexts WHERE end_date IS NOT NULL"""))
        n = _conflictos_tmp(c)
    assert n == 1, "un periodo distinto es un contexto distinto"


def test_cambiar_duration_por_instant_SI_genera_conflicto(ctx_tmp):
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900004, run_id, entity_id, accession_number, context_id,
                   scheme, identifier, NULL, NULL, end_date, 'INSTANT',
                   dimensions, typed_dimensions, dim_count, has_typed,
                   source_file || '.instant', source_hash
              FROM f055_tmp.contexts WHERE end_date IS NOT NULL"""))
        n = _conflictos_tmp(c)
    assert n == 1, "un instante no es lo mismo que un periodo"


def test_agregar_una_dimension_SI_genera_conflicto(ctx_tmp):
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900005, run_id, entity_id, accession_number, context_id,
                   scheme, identifier, start_date, end_date, instant_date, period_kind,
                   dimensions || '[{"typed": false, "member": "zz:Extra",
                     "container": "segment", "dimension": "zz:EjeExtra"}]'::jsonb,
                   typed_dimensions, dim_count + 1, has_typed,
                   source_file || '.extra', source_hash
              FROM f055_tmp.contexts"""))
        n = _conflictos_tmp(c)
    assert n == 1, "un conjunto de dimensiones mas grande es otro contexto"


@pytest.mark.xfail(reason="F-060: la comparacion no incluye scheme ni identifier. "
                          "Registrado en docs/review/F060_FINDING.md, sin corregir.",
                   strict=True)
def test_cambiar_la_entidad_SI_deberia_generar_conflicto(ctx_tmp):
    """Documenta el limite conocido de la regla, con su numero de finding.

    `strict=True`: si alguien corrige F-056, este test pasa a XPASS y FALLA, que
    es la senal para quitarlo de la lista de deuda en vez de dejarlo mintiendo.
    """
    with ctx_tmp.begin() as c:
        c.execute(text("""
            INSERT INTO f055_tmp.contexts
            SELECT ctx_id + 900006, run_id, entity_id, accession_number, context_id,
                   scheme, '0000000000', start_date, end_date, instant_date, period_kind,
                   dimensions, typed_dimensions, dim_count, has_typed,
                   source_file || '.entidad', source_hash
              FROM f055_tmp.contexts"""))
        n = _conflictos_tmp(c)
    assert n == 1, "un contexto de otra entidad no es el mismo contexto"


def test_la_canonizacion_sigue_presente_en_el_codigo():
    """Guarda contra la regresion literal."""
    src = (REPO / "scripts" / "engine" / "s04_normalize.py").read_text(encoding="utf-8")
    assert "SQL_CTX_CANONICO" in src
    assert "jsonb_agg(e ORDER BY e::text)" in src, (
        "desaparecio el ordenamiento de dimensiones: F-055 vuelve")
    assert "xmlns" in src, (
        "desaparecio la limpieza de namespaces del fragmento tipado")
    assert "dimensions, typed_dimensions)::text) AS variantes" not in src, (
        "reaparecio la comparacion ingenua en contextos_deduplicados")
