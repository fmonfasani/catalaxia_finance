"""F13 — S03 no reemplaza parsed si el lote nuevo no reproduce lo previo.

QUE PASO (gap #5 de la matriz F9/F10)
S03 borraba `parsed.*` del CIK **antes** de conocer el resultado del parse y
commiteaba **antes** de evaluar los gates. Un re-parse vacio (S02 sin filings,
o filings sin hechos) dejaba el parsed del emisor en cero con
`derived.fact` vigente citando los `fact_id` borrados:

    ANTES  dangling=0 parsed_ko=90398 derived_ko=45113 punteros_ko=90398
    DESPUES dangling=90398 parsed_ko=0          (borrado S03 sin re-insercion)
    (verificado en DEV con rollback; `docs/review/24_PRE_F13_STATE.md`)

C10 lo convierte en BLOCK, pero solo detecta: no evita el dano.

LA GARANTIA (una sola, en el productor)
`decidir_reemplazo` (S03, capa PARSED): el borrado del parsed previo solo
procede si el lote nuevo reproduce TODOS los filings que ya tenian hechos.
Si no, no se toca nada (ni DELETE ni INSERT), la corrida BLOCKea con
C-S03-010 y el checkpoint no se actualiza: S04 sigue consumiendo el parsed
previo intacto y `derived.fact` sigue resolviendo.

ESTRUCTURA (igual que F-054)
- Tests puros de `decidir_reemplazo`: sin base.
- Guardas de codigo: la decision precede al borrado y el borrado esta bajo
  `if reemplazo_ok:`; C-S03-010 existe y es bloqueante.
- Tests causales en schema temporal propio (`f13_tmp`): no tocan nada
  persistido y ejercitan el MISMO mecanismo (DELETE con predicado por CIK +
  query de C10 adaptada por reemplazo de nombres, como F-055).
- Invariantes sobre el universo DEV real (5433): el lote fiel es aceptado
  (sin falsos BLOCK) y las accessions citadas por derived estan cubiertas
  por las previas que la guarda protege.
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
import s03_parse_ypf as s03  # noqa: E402

# La query de C10, citada literalmente. Si C10 cambia, este test debe
# actualizarse a conciencia: es la prueba de que C10 sigue detectando.
C10_NO_DANGLING = (
    "SELECT count(*) FROM derived.fact d "
    "CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid) "
    "LEFT JOIN parsed.facts p ON p.fact_id = s.fid "
    "WHERE d.valid_to IS NULL AND p.fact_id IS NULL"
)


def _batch(*accs_con_hechos, vacias=()):
    """Lote minimo para `decidir_reemplazo`: solo importan acc + facts_rows."""
    lote = [{"acc": a, "facts_rows": [object()]} for a in accs_con_hechos]
    lote += [{"acc": a, "facts_rows": []} for a in vacias]
    return lote


# ───────────────────────── funcion pura ─────────────────────────

def test_lote_vacio_con_previas_no_reemplaza():
    """El caso del incidente: re-parse vacio sobre parsed con hechos."""
    ok, faltantes, nuevos = s03.decidir_reemplazo({"A1", "A2"}, [])
    assert ok is False
    assert faltantes == ["A1", "A2"]
    assert nuevos == 0


def test_lote_parcial_no_reemplaza_e_indica_que_falta():
    ok, faltantes, nuevos = s03.decidir_reemplazo({"A1", "A2"}, _batch("A1"))
    assert ok is False
    assert faltantes == ["A2"]
    assert nuevos == 1


def test_filing_previo_sin_hechos_en_el_lote_no_reemplaza():
    """El accession esta en el lote pero su parse degrado a 0 hechos
    (outcome REJECTED): reemplazar destruiria su provenance igual."""
    ok, faltantes, nuevos = s03.decidir_reemplazo({"A1"}, _batch(vacias=("A1",)))
    assert ok is False
    assert faltantes == ["A1"]
    assert nuevos == 0


def test_lote_fiel_mas_filing_nuevo_si_reemplaza():
    ok, faltantes, nuevos = s03.decidir_reemplazo({"A1", "A2"}, _batch("A1", "A2", "A3"))
    assert ok is True
    assert faltantes == []
    assert nuevos == 3


def test_sin_previas_con_hechos_si_reemplaza():
    """Primer parse del emisor: nada que proteger."""
    ok, faltantes, nuevos = s03.decidir_reemplazo(set(), _batch("A1"))
    assert ok is True
    assert faltantes == []
    assert nuevos == 1


def test_sin_previas_y_lote_vacio_no_reemplaza():
    """Sin nada previo y sin nada nuevo no hay reemplazo valido
    (los gates de cobertura BLOCKean igual; esto solo evita escribir vacio)."""
    ok, faltantes, nuevos = s03.decidir_reemplazo(set(), [])
    assert ok is False
    assert faltantes == []
    assert nuevos == 0


def test_decision_determinista():
    """I-007: mismo input + mismo codigo -> misma decision."""
    args = ({"A1", "A2"}, _batch("A1", vacias=("A2",)))
    assert s03.decidir_reemplazo(*args) == s03.decidir_reemplazo(*args)


# ───────────────────────── guardas de codigo ─────────────────────────

def test_la_decision_precede_al_borrado_en_S03():
    """Si el DELETE volviera a correr antes de decidir, este test cae."""
    src = (REPO / "scripts" / "engine" / "s03_parse_ypf.py").read_text(encoding="utf-8")
    i_dec = src.index("reemplazo_ok, faltantes, facts_nuevos = decidir_reemplazo(")
    i_del = src.index("DELETE FROM parsed.facts WHERE cik = %s")
    assert i_dec < i_del, "el borrado debe ocurrir despues de decidir el reemplazo"
    assert "if reemplazo_ok:" in src, "el borrado/insercion debe estar bajo la guarda"


def test_el_borrado_sigue_acotado_por_cik():
    """F13 no relaja F-054: el alcance por CIK se mantiene."""
    src = (REPO / "scripts" / "engine" / "s03_parse_ypf.py").read_text(encoding="utf-8")
    assert "DELETE FROM parsed.facts WHERE cik = %s" in src
    assert "setval(pg_get_serial_sequence('parsed.facts','fact_id')" not in src


def test_C_S03_010_existe_y_es_bloqueante():
    src = (REPO / "scripts" / "engine" / "s03_parse_ypf.py").read_text(encoding="utf-8")
    i = src.index('"C-S03-010"')
    ventana = src[i:i + 400]
    assert '"blocking": True' in ventana
    assert "reemplazo_ok" in ventana


# ───────────────────── causales en schema temporal ─────────────────────

@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010: no se audita contra produccion")
    return get_admin_engine(s)


@pytest.fixture
def escenario(eng):
    """Emisor AAA con 2 filings y derived que los cita, en schema propio."""
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS f13_tmp CASCADE"))
        c.execute(text("CREATE SCHEMA f13_tmp"))
        c.execute(text("CREATE SEQUENCE f13_tmp.seq"))
        c.execute(text("""
            CREATE TABLE f13_tmp.facts (
              fact_id bigint PRIMARY KEY DEFAULT nextval('f13_tmp.seq'),
              cik text NOT NULL, accession_number text NOT NULL, valor text NOT NULL)"""))
        c.execute(text("""
            CREATE TABLE f13_tmp.derived (
              cik text NOT NULL, accession_number text NOT NULL,
              source_fact_ids bigint[] NOT NULL, valid_to timestamptz NULL)"""))
        c.execute(text("INSERT INTO f13_tmp.facts (cik, accession_number, valor) "
                       "SELECT 'AAA', 'A1', 'a'||g FROM generate_series(1,3) g"))
        c.execute(text("INSERT INTO f13_tmp.facts (cik, accession_number, valor) "
                       "SELECT 'AAA', 'A2', 'b'||g FROM generate_series(1,3) g"))
        c.execute(text("INSERT INTO f13_tmp.derived (cik, accession_number, source_fact_ids) "
                       "SELECT 'AAA', accession_number, array_agg(fact_id) "
                       "FROM f13_tmp.facts GROUP BY accession_number"))
    yield eng
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS f13_tmp CASCADE"))


def _dangling(c):
    q = C10_NO_DANGLING.replace("derived.fact", "f13_tmp.derived").replace(
        "parsed.facts", "f13_tmp.facts")
    return c.execute(text(q)).scalar()


def test_sin_guarda_el_reparse_vacio_cuelga_la_provenance(escenario):
    """El defecto historico, reproducido a escala: borrar sin re-insertar
    deja los punteros colgados y la query de C10 los cuenta (>0 = BLOCK)."""
    with escenario.begin() as c:
        c.execute(text("DELETE FROM f13_tmp.facts WHERE cik = 'AAA'"))
        n = _dangling(c)
    assert n == 6, f"los 6 punteros de AAA deben quedar colgados, dangling={n}"


def test_con_guarda_el_reparse_vacio_no_toca_nada(escenario):
    """Con F13: la guarda dice no, el caller no borra, todo sigue resolviendo."""
    with escenario.begin() as c:
        previas = {r[0] for r in c.execute(text(
            "SELECT DISTINCT accession_number FROM f13_tmp.facts WHERE cik='AAA'"))}
        ok, faltantes, _ = s03.decidir_reemplazo(previas, [])
        assert ok is False and sorted(faltantes) == ["A1", "A2"]
        if ok:  # noqa: SIM210 — el `if` documenta el contrato del caller (S03)
            c.execute(text("DELETE FROM f13_tmp.facts WHERE cik = 'AAA'"))
        n_facts = c.execute(text("SELECT count(*) FROM f13_tmp.facts")).scalar()
        n = _dangling(c)
    assert n_facts == 6, "sin reemplazo no se borra nada"
    assert n == 0, "la provenance sigue resolviendo"


def test_con_guarda_el_lote_fiel_si_reemplaza(escenario):
    """El camino normal no se bloquea: lote fiel -> guarda True -> replace."""
    with escenario.begin() as c:
        previas = {r[0] for r in c.execute(text(
            "SELECT DISTINCT accession_number FROM f13_tmp.facts WHERE cik='AAA'"))}
        ok, faltantes, nuevos = s03.decidir_reemplazo(
            previas, _batch("A1", "A2"))
        assert ok is True and faltantes == [] and nuevos == 2
        c.execute(text("DELETE FROM f13_tmp.facts WHERE cik = 'AAA'"))
        c.execute(text("INSERT INTO f13_tmp.facts (cik, accession_number, valor) "
                       "SELECT 'AAA', x.a, 'nuevo' FROM "
                       "(VALUES ('A1'),('A2')) AS x(a)"))
        n = _dangling(c)
    # los ids nuevos no coinciden con los citados: re-parse real regenera
    # derived via S04; lo que este test fija es que la guarda no estorba.
    assert n == 6


# ─────────────────── invariantes sobre el universo DEV ───────────────────

@pytest.fixture(scope="module")
def live(eng):
    with eng.connect() as c:
        yield c


def test_el_lote_fiel_al_universo_actual_es_aceptado(live):
    """Sin falsos BLOCK: reproducir exactamente las accessions con hechos
    de cada emisor siempre da guarda True (YPF 9, KO 17 accessions)."""
    filas = live.execute(text(
        "SELECT cik, accession_number FROM parsed.facts "
        "GROUP BY cik, accession_number")).all()
    assert filas, "universo DEV vacio: el invariante no es observable"
    por_cik: dict[str, set] = {}
    for cik, acc in filas:
        por_cik.setdefault(cik, set()).add(acc)
    for cik, previas in por_cik.items():
        lote = [{"acc": a, "facts_rows": [object()]} for a in sorted(previas)]
        ok, faltantes, nuevos = s03.decidir_reemplazo(previas, lote)
        assert ok is True, f"falso BLOCK para {cik}: faltantes={faltantes}"
        assert nuevos == len(previas)


def test_derived_solo_cita_filings_cubiertos_por_la_guarda(live):
    """Supuesto de cobertura de la guarda: toda accession citada por
    `derived.fact` vigente existe en `parsed.facts` del mismo CIK. Si esto
    fallara, la guarda F13 no bastaria."""
    filas = live.execute(text("""
        SELECT DISTINCT d.cik, d.accession_number
          FROM derived.fact d
          LEFT JOIN parsed.facts p
            ON p.cik = d.cik AND p.accession_number = d.accession_number
         WHERE d.valid_to IS NULL AND p.fact_id IS NULL""")).all()
    assert not filas, f"derived cita filings sin parsed: {filas[:5]}"


def test_no_dangling_en_el_universo_actual(live):
    """Medicion post-F13 con la query exacta de C10: debe seguir en 0."""
    n = live.execute(text(C10_NO_DANGLING)).scalar()
    assert n == 0, f"NO_DANGLING={n}: C10 debe BLOCKear"
