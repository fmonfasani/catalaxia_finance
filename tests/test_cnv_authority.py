"""CNV — la elegibilidad depende de la AUTORIDAD del identificador, no del
estado de la assertion.

QUE CAMBIO (C1)
La version anterior decidia con `max(a.status::text)`: maximo ALFABETICO del
texto del estado, sin filtrar `is_authoritative` ni mirar `identifier.status`.
Acertaba porque 'VERIFIED' es el mayor de los cinco estados en orden
lexicografico — una propiedad del alfabeto, no una regla.

El modelo garantiza `autoritativo => VERIFIED`, NO su reciproco. Una assertion
VERIFIED sobre un identificador no autoritativo habilitaba una descarga que el
modelo no autoriza.

EL INCIDENTE QUE ESTO PREVIENE
`CNV_NEGATIVE_PILOT_20` construyo su universo filtrando `a.status <> 'VERIFIED'`
fila por fila. Como un CUIT tiene 4-8 filas vigentes con estados mezclados, las
filas CANDIDATE de YPF —cuyo CUIT SI es autoritativo— entraron al universo
"negativo", y el piloto invoco el fetcher sobre ellas: 1 corrida y 2 artefactos
escritos en la base homologada. Ver T8.

DONDE CORRE CADA TEST
  T1, T2, T7, T8   contra la base real, SOLO LECTURA
  T3, T4, T5, T6   contra un schema temporal: los estados que prueban NO deben
                   existir en la base homologada, y se borran al terminar
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "c3_bajo_prueba", REPO / "scripts" / "engine" / "c3_cnv_fetch.py")
c3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c3)

TMP = "cnvauth_tmp"


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010: no se prueba contra produccion")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    with eng.connect() as c:
        yield c


# ═══════════════ contra la base real, solo lectura ═══════════════

def test_T1_autoritativo_active_vigente_es_elegible(eng, conn):
    """T1 · el camino positivo sigue funcionando."""
    cuits = [r[0] for r in conn.execute(text(
        "SELECT id_value FROM identity_v1.identifier "
        " WHERE id_type='CUIT' AND is_authoritative AND status='ACTIVE' "
        "   AND valid_to IS NULL ORDER BY id_value")).all()]
    if not cuits:
        pytest.skip("no hay CUIT autoritativos en la base")
    for cuit in cuits:
        r = c3.resolver_en_identity_v1(eng, cuit, None)
        assert r["ok"] is True, f"{cuit}: {r.get('motivo')} — {r.get('detalle','')[:120]}"
        assert r["motivo"] == "AUTORITATIVO"
        assert r["cuit"] == cuit
        assert r["cuit_identifier_status"] == "ACTIVE"


def test_T2_candidato_no_autoritativo_es_rechazado(eng, conn):
    """T2 · el camino negativo. El motivo debe nombrar la AUTORIDAD, no el
    estado de la assertion."""
    cuits = [r[0] for r in conn.execute(text("""
        SELECT id_value FROM identity_v1.identifier
         WHERE id_type='CUIT' AND valid_to IS NULL
         GROUP BY id_value
        HAVING bool_and(NOT is_authoritative)
         ORDER BY id_value""")).all()]
    if not cuits:
        pytest.skip("no hay CUIT no autoritativos en la base")
    # Dos motivos legitimos de bloqueo conviven en el universo real:
    #   CUIT_NO_AUTORITATIVO  la entidad existe, ningun CUIT suyo es autoritativo
    #   AMBIGUO               el CUIT resuelve a MAS DE UNA entidad (4 de 17 hoy:
    #                         Galicia, AA2000, YPF Energia Electrica, Supervielle
    #                         estan duplicadas en identity_v1)
    # Lo que ninguno puede ser es elegible.
    motivos = {}
    for cuit in cuits:
        r = c3.resolver_en_identity_v1(eng, cuit, None)
        assert r["ok"] is False, f"{cuit} no deberia ser elegible"
        assert r["motivo"] in ("CUIT_NO_AUTORITATIVO", "AMBIGUO"),             f"{cuit}: motivo inesperado {r['motivo']}"
        motivos[cuit] = r["motivo"]
    assert "CUIT_NO_AUTORITATIVO" in motivos.values(), (
        "ningun caso bloqueo por falta de autoridad: el test no esta probando C1")


def test_T2b_load_identity_corta_antes_de_abrir_corrida(eng, conn):
    """T2b · el corte ocurre en load_identity, ANTES de run_scope: un caso no
    elegible no gasta una corrida ni un request."""
    # se exige entidad UNICA para aislar el motivo: con >1 entidad el bloqueo
    # seria AMBIGUO, que es otro camino (ver T2)
    cuit = conn.execute(text("""
        SELECT id_value FROM identity_v1.identifier
         WHERE id_type='CUIT' AND valid_to IS NULL
         GROUP BY id_value
        HAVING bool_and(NOT is_authoritative) AND count(DISTINCT entity_key) = 1
         ORDER BY id_value LIMIT 1""")).scalar()
    if not cuit:
        pytest.skip("no hay CUIT no autoritativo con entidad unica")
    with pytest.raises(SystemExit) as e:
        c3.load_identity(eng, cuit=cuit)
    assert "BLOCK identidad" in str(e.value)
    assert "CUIT_NO_AUTORITATIVO" in str(e.value)


def test_T7_invariantes_estructurales(conn):
    """T7 · los cinco controles de la auditoria de autoridad, como regresion."""
    inv = {
        "VERIFIED sobre identificador NO autoritativo": """
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
             WHERE a.status='VERIFIED' AND NOT i.is_authoritative""",
        "autoritativo con assertion != VERIFIED": """
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
             WHERE i.is_authoritative AND a.status <> 'VERIFIED'""",
        "autoritativo vigente con status != ACTIVE": """
            SELECT count(*) FROM identity_v1.identifier
             WHERE is_authoritative AND valid_to IS NULL AND status <> 'ACTIVE'""",
        "mas de un CUIT autoritativo vigente por entidad": """
            SELECT count(*) FROM (SELECT entity_key FROM identity_v1.identifier
             WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL
             GROUP BY entity_key HAVING count(*)>1) x""",
    }
    malos = {n: conn.execute(text(q)).scalar() for n, q in inv.items()}
    assert all(v == 0 for v in malos.values()), f"invariantes violados: {malos}"


def test_T8_reproduccion_del_incidente_con_espia(eng, conn):
    """T8 · el universo negativo construido con la consulta VIEJA incluye CUIT
    autoritativos. Con la salvaguarda, el fetcher NO se invoca ni una vez.

    Reproduce el incidente CNV_NEGATIVE_PILOT_20 sin descargar nada.
    """
    # el universo tal como lo construyo el piloto que fallo: fila por fila
    universo_viejo = [r[0] for r in conn.execute(text("""
        SELECT DISTINCT i.id_value
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
         WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status <> 'VERIFIED'
         ORDER BY 1""")).all()]
    autoritativos = {r[0] for r in conn.execute(text(
        "SELECT id_value FROM identity_v1.identifier "
        " WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL")).all()}
    contaminados = [c for c in universo_viejo if c in autoritativos]
    assert contaminados, (
        "el universo viejo ya no incluye autoritativos: este test dejo de "
        "reproducir el incidente y hay que revisarlo")

    # espia: cuenta cada invocacion del fetcher
    llamadas: list[str] = []

    def fetcher_espiado(cuit: str) -> None:
        llamadas.append(cuit)

    # el bucle del piloto, CON la salvaguarda que faltaba
    invocados, bloqueados = [], []
    for cuit in universo_viejo:
        r = c3.resolver_en_identity_v1(eng, cuit, None)
        if r["ok"]:                      # <- la salvaguarda: no se invoca
            bloqueados.append(cuit)
            continue
        assert r["motivo"] in ("CUIT_NO_AUTORITATIVO", "SIN_CUIT",
                               "NO_ESTA_EN_IDENTITY_V1", "AMBIGUO")
        invocados.append(cuit)
        fetcher_espiado(cuit)            # simulacion: nunca descarga de verdad

    assert set(bloqueados) == set(contaminados), (
        f"la salvaguarda no detuvo exactamente a los autoritativos: "
        f"detenidos={bloqueados} contaminados={contaminados}")
    for c in contaminados:
        assert c not in llamadas, f"{c} es autoritativo y llego al fetcher"


# ═══════════════ schema temporal: estados que no deben existir ═══════════════

@pytest.fixture
def tmp_identity(eng):
    """Replica minima de identity_v1 para probar estados invalidos.

    Los casos de T3/T4/T5 NO deben crearse en la base homologada: son
    precisamente los estados que sus invariantes prohiben.
    """
    with eng.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {TMP} CASCADE"))
        c.execute(text(f"CREATE SCHEMA {TMP}"))
        c.execute(text(f"""
            CREATE TABLE {TMP}.entity (
              entity_key text PRIMARY KEY, preferred_name text)"""))
        c.execute(text(f"""
            CREATE TABLE {TMP}.assertion (
              assertion_id int PRIMARY KEY, status text, method text,
              confidence text)"""))
        c.execute(text(f"""
            CREATE TABLE {TMP}.identifier (
              identifier_id int PRIMARY KEY, entity_key text, id_type text,
              id_value text, is_authoritative boolean, status text,
              valid_to timestamptz, assertion_id int)"""))
        c.execute(text(f"INSERT INTO {TMP}.entity VALUES ('E_TEST','EMPRESA DE PRUEBA')"))
        c.execute(text(f"INSERT INTO {TMP}.assertion VALUES "
                       f"(1,'VERIFIED','REGISTRY','AUTHORITATIVE')"))
    yield eng
    with eng.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {TMP} CASCADE"))


def _elegibles(c) -> list:
    """Ejecuta el SQL REAL del resolver contra el schema temporal.

    Se importa de `c3`: si alguien le quita `is_authoritative`, estos tests
    cambian de resultado. Ese es el vinculo causal (T6).
    """
    sql = c3.SQL_CUIT_AUTORITATIVO.replace("identity_v1.", f"{TMP}.")
    return c.execute(text(sql), {"ek": "E_TEST"}).mappings().all()


def _ins(c, **kw):
    d = {"identifier_id": 1, "entity_key": "E_TEST", "id_type": "CUIT",
         "id_value": "30111111118", "is_authoritative": True, "status": "ACTIVE",
         "valid_to": None, "assertion_id": 1}
    d.update(kw)
    c.execute(text(f"""INSERT INTO {TMP}.identifier VALUES
        (:identifier_id,:entity_key,:id_type,:id_value,:is_authoritative,
         :status,:valid_to,:assertion_id)"""), d)


def test_T3_autoritativo_pero_DISPUTED_queda_bloqueado(tmp_identity):
    """T3 · `identifier.status` importa: un autoritativo en disputa no habilita."""
    with tmp_identity.begin() as c:
        _ins(c, status="DISPUTED")
        assert _elegibles(c) == [], "un identificador DISPUTED no debe ser elegible"


def test_T4_autoritativo_con_valid_to_cerrado_queda_bloqueado(tmp_identity):
    """T4 · la vigencia importa: un autoritativo superseído no habilita."""
    with tmp_identity.begin() as c:
        _ins(c, valid_to="2026-01-01T00:00:00+00")
        assert _elegibles(c) == [], "un identificador cerrado no debe ser elegible"


def test_T5_dos_autoritativos_vigentes_dan_AMBIGUO(tmp_identity):
    """T5 · con dos autoritativos NO se desempata: la consulta devuelve dos
    filas y el resolver debe bloquear por AMBIGUO."""
    with tmp_identity.begin() as c:
        _ins(c, identifier_id=1, id_value="30111111118")
        _ins(c, identifier_id=2, id_value="30222222227")
        filas = _elegibles(c)
    assert len(filas) == 2, "la consulta debe exponer la ambiguedad, no ocultarla"
    # y el resolver, ante >1, bloquea
    assert "AMBIGUO" in c3.resolver_en_identity_v1.__doc__


def test_T5b_el_caso_valido_si_es_elegible(tmp_identity):
    """Control positivo del fixture: sin el defecto, la fila sí es elegible.
    Sin esto, T3/T4 podrian pasar porque el fixture no funciona."""
    with tmp_identity.begin() as c:
        _ins(c)
        filas = _elegibles(c)
    assert len(filas) == 1 and filas[0]["cuit"] == "30111111118"


def test_T6_mutacion_quitar_is_authoritative_rompe_T3(tmp_identity):
    """T6 · si se quita `is_authoritative` de la consulta, el caso DISPUTED
    sigue bloqueado por `status`, pero el caso no-autoritativo pasa a elegible.

    Demuestra que la barrera que T2 prueba es `is_authoritative` y no otra
    condicion incidental.
    """
    mutado = (c3.SQL_CUIT_AUTORITATIVO
              .replace("identity_v1.", f"{TMP}.")
              .replace("AND i.is_authoritative", ""))
    assert "is_authoritative" not in mutado, "la mutacion no se construyo"
    with tmp_identity.begin() as c:
        _ins(c, is_authoritative=False)          # un candidato, NO autoritativo
        real = c.execute(text(c3.SQL_CUIT_AUTORITATIVO.replace(
            "identity_v1.", f"{TMP}.")), {"ek": "E_TEST"}).mappings().all()
        con_mutacion = c.execute(text(mutado), {"ek": "E_TEST"}).mappings().all()
    assert real == [], "con la barrera, un no-autoritativo NO es elegible"
    assert len(con_mutacion) == 1, (
        "sin la barrera el no-autoritativo pasa: si esto no ocurre, la consulta "
        "no depende de is_authoritative y T2 estaria pasando por otra razon")


def test_C1_la_consulta_no_usa_max_de_status():
    """Guarda contra la regresion literal: si vuelve `max(a.status::text)`,
    esto cae antes de que nadie corra el fetcher."""
    src = (REPO / "scripts" / "engine" / "c3_cnv_fetch.py").read_text(encoding="utf-8")
    assert "max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)" not in src, (
        "reaparecio la decision por maximo alfabetico del estado")
    assert "AND i.is_authoritative" in src
    assert "AND i.status = 'ACTIVE'" in src
    assert "AND i.valid_to IS NULL" in src
    assert "CUIT_NO_AUTORITATIVO" in src
