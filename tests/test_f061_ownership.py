"""F-061 — un ratio no puede consumir hechos que no pertenecen a la entidad.

QUE PASO
El ataque A7 del banco adversario clono `AssetsCurrent` y `LiabilitiesCurrent`
de AAPL (us-gaap) bajo el CIK de GGAL, re-etiquetados a `CurrentAssets` y
`CurrentLiabilities` (ifrs-full, coherentes con la taxonomia que GGAL declara)
y en ARS. GGAL, banco, no tenia ninguno de los dos: `current_ratio` daba
NO_CALCULABLE. Despues del ataque dio CALCULADO = 0.893293 -- el current_ratio
de Apple, digito por digito. Nada en la salida lo delataba.

DONDE SE PIERDE LA IDENTIDAD
`derived.fact` TIENE la columna `entity_key`, y la capa de ratios resuelve la
entidad con rigor (instrumento -> entity_key, o CIK con assertion VERIFIED).
Pero acto seguido descarta el `entity_key` y trae los hechos con

    WHERE valid_to IS NULL AND cik = :c

Es decir: la identidad, que llego como clave opaca respaldada por una
assertion, degrada a una igualdad de texto sobre una columna que cualquier
escritura puede fijar. Y `source_fact_ids` -- el puntero a la evidencia -- se
lee UNICAMENTE para imprimir la provenance (`evidencia_de`), nunca para
validar: esa funcion ni siquiera selecciona el `cik` de la fila apuntada.

LA GARANTIA QUE FALTA
Todo `fact_id` de `derived.fact.source_fact_ids` debe resolver a una fila de
`parsed.facts` DEL MISMO emisor y del mismo filing. Es una regla de pertenencia
basada en la provenance, no en nombres ni tickers: no menciona ninguna empresa.

La fila fabricada por A7 la viola de dos maneras independientes -- lleva el
`cik` de GGAL con los `source_fact_ids` de AAPL, y lleva `qname` ifrs-full
sobre punteros a filas us-gaap.

ESTADO DE ESTOS TESTS  ·  ACTUALIZADO EL DIA 3
Los dos que estaban en rojo -- el criterio de aceptacion de F-061 -- ahora
pasan. El fix: `scripts/engine/ratio_inputs.py` es el unico punto que arma el
WHERE de la seleccion de insumos, y ese WHERE lleva `GUARDA_PERTENENCIA`. Los
cuatro modulos de la capa de ratios lo usan; ninguno arma su propia consulta.

Se les quito el prefijo `f061_rojo` al pasar a verde: un test permanentemente
verde llamado "rojo" es una trampa para el que lo lea despues. El selector
`-k "not f061_rojo"` que se usaba mientras el hallazgo estaba abierto ya no
excluye nada, que es lo correcto.

`test_la_mutacion_sin_guarda_readmite_los_hechos_ajenos` es el vinculo causal:
quita la guarda de la consulta real y la contaminacion vuelve. Si ese test
dejara de fallar sin la guarda, seria senal de que la proteccion la esta dando
otra condicion y no la que decimos.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

TMP = "f061_tmp"

# ── EL INVARIANTE ────────────────────────────────────────────────────────────
# Esta es la regla que F-061 pide y que hoy no se aplica en ningun lado.
# Se declara aca una sola vez para que el fix la reutilice literalmente.
# Se importan del codigo vivo: el test no puede tener su propia copia de la
# regla, porque entonces probaria su copia y no la garantia.
from ratio_inputs import (GUARDA_PERTENENCIA, INVARIANTE_PERTENENCIA,  # noqa: E402
                          sql_insumos)

# Los cuatro modulos de la capa de ratios que traen insumos de `derived.fact`.
# Todos usan la misma seleccion, asi que todos heredan el mismo defecto.
MODULOS_RATIOS = ("screener_demo.py", "matriz_producto.py",
                  "e2e_producto.py", "ratios_inventario.py")


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010: no se audita contra produccion")
    return get_admin_engine(s)


COLUMNAS = "d.tag, d.report_period, d.currency, d.value_numeric"


def _sql_seleccion_real(*, con_guarda: bool = True) -> str:
    """La consulta de seleccion, construida por el codigo vivo.

    No se copia: la arma `ratio_inputs.sql_insumos`, el mismo punto que usan los
    cuatro modulos. Si alguien cambia esa funcion, el test cambia de resultado.
    Esa es la union causal entre el test y la garantia.

    Con `con_guarda=False` se le quita la clausula de pertenencia -- es la
    mutacion que demuestra que la proteccion viene de ahi y no de otro filtro.
    """
    import ratio_inputs

    sql = ratio_inputs.sql_insumos(
        COLUMNAS, derived=f"{TMP}.derived_fact", parsed=f"{TMP}.parsed_facts")
    if not con_guarda:
        guarda = ratio_inputs.GUARDA_PERTENENCIA.format(
            alias="d", parsed=f"{TMP}.parsed_facts")
        assert guarda in sql, "la guarda deberia estar presente para poder quitarla"
        sql = sql.replace(guarda, "")
    return sql


@pytest.fixture
def escenario(eng):
    """Reproduce A7 en un schema temporal. No toca nada persistido.

    Dos emisores. `CIK-A` es el donante (el rol de AAPL). `CIK-B` es la victima
    (el rol de GGAL): tiene un hecho legitimo propio y recibe dos hechos
    fabricados que llevan SU cik y SU entity_key pero los `source_fact_ids` del
    donante. Ningun nombre de empresa real interviene: la regla es de
    pertenencia, no de nombres.
    """
    with eng.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {TMP} CASCADE"))
        c.execute(text(f"CREATE SCHEMA {TMP}"))
        c.execute(text(f"""
            CREATE TABLE {TMP}.parsed_facts (
              fact_id bigint PRIMARY KEY,
              cik text NOT NULL, accession_number text NOT NULL,
              qname text NOT NULL, value_numeric numeric)"""))
        c.execute(text(f"""
            CREATE TABLE {TMP}.derived_fact (
              fact_key text PRIMARY KEY, entity_key text NOT NULL, cik text NOT NULL,
              accession_number text NOT NULL, form text, filing_date text,
              report_period text, qname text NOT NULL, namespace text, tag text NOT NULL,
              context_id text, period_kind text, end_date date, instant_date date,
              is_dimensional boolean NOT NULL DEFAULT false,
              unit_measure text, currency text, value_numeric numeric,
              is_numeric boolean NOT NULL DEFAULT true,
              source_fact_ids bigint[] NOT NULL,
              valid_to timestamptz)"""))

        # --- emisor A (donante) -------------------------------------------
        c.execute(text(f"""
            INSERT INTO {TMP}.parsed_facts VALUES
              (1,'CIK-A','ACC-A','us-gaap:AssetsCurrent',      152987000000),
              (2,'CIK-A','ACC-A','us-gaap:LiabilitiesCurrent', 171279000000),
              (3,'CIK-B','ACC-B','ifrs-full:Liabilities',       98765000000)"""))
        c.execute(text(f"""
            INSERT INTO {TMP}.derived_fact
              (fact_key, entity_key, cik, accession_number, report_period, qname,
               namespace, tag, instant_date, unit_measure, currency, value_numeric,
               source_fact_ids)
            VALUES
              ('A1','EK-A','CIK-A','ACC-A','2025-09-27','us-gaap:AssetsCurrent',
               'us-gaap','AssetsCurrent','2025-09-27','USD','USD',152987000000,'{{1}}'),
              ('A2','EK-A','CIK-A','ACC-A','2025-09-27','us-gaap:LiabilitiesCurrent',
               'us-gaap','LiabilitiesCurrent','2025-09-27','USD','USD',171279000000,'{{2}}')"""))

        # --- emisor B: un hecho legitimo propio ---------------------------
        c.execute(text(f"""
            INSERT INTO {TMP}.derived_fact
              (fact_key, entity_key, cik, accession_number, report_period, qname,
               namespace, tag, instant_date, unit_measure, currency, value_numeric,
               source_fact_ids)
            VALUES
              ('B1','EK-B','CIK-B','ACC-B','2025-12-31','ifrs-full:Liabilities',
               'ifrs-full','Liabilities','2025-12-31','ARS','ARS',98765000000,'{{3}}')"""))

        # --- EL ATAQUE: hechos de A insertados como si fueran de B --------
        # cik, entity_key y accession son los de B. Los punteros son los de A.
        c.execute(text(f"""
            INSERT INTO {TMP}.derived_fact
              (fact_key, entity_key, cik, accession_number, report_period, qname,
               namespace, tag, instant_date, unit_measure, currency, value_numeric,
               source_fact_ids)
            VALUES
              ('X1','EK-B','CIK-B','ACC-B','2025-12-31','ifrs-full:CurrentAssets',
               'ifrs-full','CurrentAssets','2025-12-31','ARS','ARS',152987000000,'{{1}}'),
              ('X2','EK-B','CIK-B','ACC-B','2025-12-31','ifrs-full:CurrentLiabilities',
               'ifrs-full','CurrentLiabilities','2025-12-31','ARS','ARS',171279000000,'{{2}}')"""))
    yield eng
    with eng.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {TMP} CASCADE"))


# ═════════════════════════════════════════════════════════ el detector ══════

def test_el_detector_encuentra_los_hechos_ajenos(escenario):
    """El invariante ve las dos filas fabricadas. Si no las viera, no serviria."""
    sql = INVARIANTE_PERTENENCIA.format(
        derived=f"{TMP}.derived_fact", parsed=f"{TMP}.parsed_facts")
    with escenario.connect() as c:
        n = c.execute(text(sql)).scalar_one()
    assert n == 2, f"el detector deberia marcar los 2 punteros ajenos, marco {n}"


def test_control_positivo_los_hechos_legitimos_no_se_marcan(escenario):
    """Sin este control, el detector podria pasar marcandolo TODO.

    Se corre el invariante restringido a las filas legitimas: debe dar 0.
    """
    sql = INVARIANTE_PERTENENCIA.format(
        derived=f"{TMP}.derived_fact", parsed=f"{TMP}.parsed_facts")
    sql += " AND d.fact_key IN ('A1','A2','B1')"
    with escenario.connect() as c:
        n = c.execute(text(sql)).scalar_one()
    assert n == 0, f"ninguna fila legitima debe marcarse, se marcaron {n}"


def test_la_mutacion_sin_guarda_readmite_los_hechos_ajenos(escenario):
    """MUTACION — quitar la guarda hace volver la contaminacion.

    Sin esto, el test de arriba podria estar pasando por otra condicion del
    WHERE (la moneda, el periodo, el filtro de dimensionalidad) y no por la
    garantia que dice probar.
    """
    with escenario.connect() as c:
        con = {r[0] for r in c.execute(text(_sql_seleccion_real()), {"c": "CIK-B"})}
        sin = {r[0] for r in c.execute(text(_sql_seleccion_real(con_guarda=False)),
                                       {"c": "CIK-B"})}
    assert con == {"Liabilities"}, f"con la guarda deberia quedar solo el propio: {con}"
    assert sin == {"Liabilities", "CurrentAssets", "CurrentLiabilities"}, (
        f"sin la guarda deberian volver los hechos ajenos; devolvio {sin}")


# ═════════════════════════════════════════ el estado de la base de hoy ══════

def test_la_base_de_trabajo_cumple_hoy_el_invariante(eng):
    """0 violaciones sobre los punteros vigentes: el invariante es adoptable
    sin backfill ni migracion de datos."""
    sql = INVARIANTE_PERTENENCIA.format(derived="derived.fact", parsed="parsed.facts")
    with eng.connect() as c:
        n = c.execute(text(sql)).scalar_one()
        punteros = c.execute(text(
            "SELECT sum(array_length(source_fact_ids,1)) FROM derived.fact "
            "WHERE valid_to IS NULL")).scalar_one()
    assert n == 0, f"{n} punteros ajenos sobre {punteros} vigentes"
    assert punteros and punteros > 100_000, (
        f"el control no vale si no hay volumen: solo {punteros} punteros")


# ═══════════════════════════════════ criterio de aceptacion (HOY ROJOS) ═════

def test_la_seleccion_rechaza_hechos_ajenos(escenario):
    """CRITERIO DE ACEPTACION DE F-061.

    ENTITY A facts + ENTITY B ratio calculation => DEBE FALLAR.

    Se corre la seleccion REAL pidiendo los insumos de B. Antes del fix devolvia
    los dos hechos de A porque solo filtraba por `cik`.
    """
    with escenario.connect() as c:
        tags = {r[0] for r in c.execute(text(_sql_seleccion_real()), {"c": "CIK-B"})}
    assert "Liabilities" in tags, "control: el hecho propio de B debe estar"
    assert tags == {"Liabilities"}, (
        f"la seleccion adopto hechos del emisor A bajo el cik de B: "
        f"{tags - {'Liabilities'}}")


def test_los_modulos_de_ratios_usan_la_seleccion_canonica():
    """CRITERIO DE ACEPTACION DE F-061 — alcance.

    Los cuatro modulos deben pedir sus insumos por `ratio_inputs.sql_insumos`.
    Ninguno puede armar su propio `FROM derived.fact ... WHERE cik = :c`: esa
    era la forma del defecto, repetida cuatro veces.
    """
    incumplen = []
    for nombre in MODULOS_RATIOS:
        src = (REPO / "scripts" / "engine" / nombre).read_text(encoding="utf-8")
        usa_canonica = "from ratio_inputs import sql_insumos" in src
        # una seleccion propia de insumos se reconoce por filtrar por :c
        propia = re.search(r"FROM derived\.fact\b(?![^;]*?sql_insumos)[^;]{0,400}?cik\s*=?\s*:c",
                           src, re.S)
        if not usa_canonica or propia:
            incumplen.append(nombre)
    assert not incumplen, (
        f"estos modulos no pasan por la seleccion canonica de ratio_inputs: {incumplen}")
