"""F-040 — C3 debe cerrar su corrida SIEMPRE, tambien cuando muere.

El defecto: `c3_cnv_fetch.py` abre la corrida con `edb.start_run()` y la cierra
con `edb.finish_run()` mas de 350 lineas despues. Cualquier excepcion en el
medio deja `engine.runs.status='RUNNING'` para siempre. Hoy pasó tres veces
seguidas (los tres fetch de CNV que murieron por F-039 o que mate a mano).

`run_scope()` existe justamente para esto y su docstring ya nombraba a c3 como
causa conocida de F-009. Nunca se migro.

Estos tests NO importan la logica del implementador para validar: inyectan
fallos en los tres tramos del ciclo de vida y miran la BASE.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.states import StageState  # noqa: E402

PIPELINE = "test-f040-lifecycle"
TERMINALES = ("OK", "BLOCKED", "ABORTED", "FAILED", "ERROR")


@pytest.fixture(scope="module")
def s():
    st = load_settings()
    if st.is_prod:
        pytest.skip("EXT-010")
    return st


@pytest.fixture(scope="module")
def eng(s):
    return edb.get_engine(s)


@pytest.fixture
def limpiar(eng):
    """NO borra: cierra.

    La primera version hacia DELETE sobre engine.runs/stage_runs y fallaba con
    `permission denied`. No era un bug del entorno: la migracion 016 le quita
    DELETE a `catalaxia_engine` sobre todo lo que registra QUE PASO, y estas
    corridas efectivamente pasaron. Borrarlas seria justo lo que el proyecto
    decidio impedir.

    Se cierran como ABORTED, que es la verdad: corrieron y no terminaron bien.
    Quedan marcadas por su pipeline_version sintetica.
    """
    yield
    with eng.connect() as c:
        huerfanas = [r[0] for r in c.execute(text(
            "SELECT run_id FROM engine.runs "
            " WHERE pipeline_version=:p AND status='RUNNING'"), {"p": PIPELINE})]
    for rid in huerfanas:
        edb.finish_run(eng, rid, "ABORTED")


def estado(eng, run_id: str):
    with eng.connect() as c:
        return c.execute(text(
            "SELECT status, finished_at FROM engine.runs WHERE run_id=:r"),
            {"r": run_id}).one()


# ===========================================================================
# A. REPRODUCCION del defecto: el patron viejo deja huerfanas
# ===========================================================================

def test_el_patron_viejo_deja_huerfana(eng, s, limpiar):
    """start_run + finish_run al final = una excepcion en medio deja RUNNING.

    Este test documenta el DEFECTO. Si algun dia falla, es que alguien hizo que
    start_run cierre solo -- y entonces F-040 se cerro por otra via.
    """
    run = edb.start_run(eng, s, PIPELINE)
    try:
        raise RuntimeError("el fetch murio a mitad, como paso hoy 3 veces")
    except RuntimeError:
        pass  # nadie cierra la corrida: exactamente lo que hace c3 hoy
    st, fin = estado(eng, run.run_id)
    assert st == "RUNNING" and fin is None, (
        "el defecto ya no se reproduce; revisar si F-040 se cerro por otra via")


# ===========================================================================
# B. run_scope cierra en los TRES tramos del ciclo de vida
# ===========================================================================

@pytest.mark.parametrize("tramo,donde", [
    ("antes del fetch", 0),
    ("durante el fetch", 1),
    ("despues del checkpoint", 2),
])
def test_run_scope_cierra_ante_fallo_en_cualquier_tramo(eng, s, limpiar, tramo, donde):
    run_id = None
    with pytest.raises(RuntimeError):
        with edb.run_scope(eng, s, PIPELINE) as run:
            run_id = run.run_id
            if donde == 0:
                raise RuntimeError(f"fallo {tramo}")
            edb.record_stage_transition(eng, run.run_id, "C3_CNV_FETCH",
                                        StageState.PLANNED, StageState.READY)
            if donde == 1:
                raise RuntimeError(f"fallo {tramo}")
            edb.record_stage_transition(eng, run.run_id, "C3_CNV_FETCH",
                                        StageState.READY, StageState.RUNNING)
            run.status = "OK"          # el cuerpo ya declaro exito...
            raise RuntimeError(f"fallo {tramo}")   # ...y aun asi muere

    st, fin = estado(eng, run_id)
    assert st == "ABORTED", f"fallo {tramo}: quedo {st}, no ABORTED"
    assert fin is not None, f"fallo {tramo}: ABORTED sin finished_at"


def test_un_status_declarado_no_sobrevive_a_una_excepcion(eng, s, limpiar):
    """El caso mas peligroso: el cuerpo puso OK y despues murio.

    Si `run_scope` respetara `run.status` en el camino de excepcion, una corrida
    muerta quedaria registrada como exitosa. Peor que una huerfana.
    """
    run_id = None
    with pytest.raises(ZeroDivisionError):
        with edb.run_scope(eng, s, PIPELINE) as run:
            run_id = run.run_id
            run.status = "OK"
            1 / 0
    assert estado(eng, run_id)[0] == "ABORTED"


def test_ejecucion_normal_queda_ok(eng, s, limpiar):
    with edb.run_scope(eng, s, PIPELINE) as run:
        run_id = run.run_id
    st, fin = estado(eng, run_id)
    assert st == "OK" and fin is not None


def test_el_cuerpo_puede_declarar_blocked(eng, s, limpiar):
    """Un gate BLOCK no es un crash: la corrida termina y lo declara."""
    with edb.run_scope(eng, s, PIPELINE) as run:
        run_id = run.run_id
        run.status = "BLOCKED"
    assert estado(eng, run_id)[0] == "BLOCKED"


def test_la_excepcion_se_propaga(eng, s, limpiar):
    """Cerrar la corrida no puede tragarse el error que la mato."""
    with pytest.raises(KeyError, match="clave"):
        with edb.run_scope(eng, s, PIPELINE):
            raise KeyError("clave")


def test_keyboardinterrupt_tambien_cierra(eng, s, limpiar):
    """Ctrl-C es como murio una de las tres huerfanas de hoy (timeout/kill).

    `run_scope` captura BaseException, no Exception: si capturara solo
    Exception, un SIGINT dejaria la corrida abierta -- que es justo el caso
    real que hay que cubrir.
    """
    run_id = None
    with pytest.raises(KeyboardInterrupt):
        with edb.run_scope(eng, s, PIPELINE) as run:
            run_id = run.run_id
            raise KeyboardInterrupt
    assert estado(eng, run_id)[0] == "ABORTED"


# ===========================================================================
# C. El invariante que importa
# ===========================================================================

def test_ninguna_corrida_de_c3_queda_en_running(eng):
    """Contra la base REAL: cero huerfanas de cnv-fetch.

    No se limita a las sinteticas: si C3 dejo huerfanas historicas y no se
    cerraron, esto falla.
    """
    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT run_id, started_at FROM engine.runs "
            " WHERE status='RUNNING' AND pipeline_version LIKE 'cnv-fetch%' "
            " ORDER BY started_at")).all()
    assert not filas, (
        f"{len(filas)} corridas de CNV en RUNNING sin proceso vivo: "
        f"{[r[0][:12] for r in filas]}")


def test_todo_estado_de_runs_es_terminal_o_esta_vivo(eng):
    """Invariante general del pipeline, no solo de C3."""
    with eng.connect() as c:
        malas = c.execute(text(
            "SELECT pipeline_version, count(*) FROM engine.runs "
            " WHERE status NOT IN :t AND status <> 'RUNNING' GROUP BY 1"),
            {"t": TERMINALES}).all()
    assert not malas, f"estados desconocidos en engine.runs: {malas}"


# ===========================================================================
# D. INTEGRACION: contra el main() REAL de c3_cnv_fetch, no una simulacion
# ===========================================================================

def _c3():
    sys.path.insert(0, str(REPO / "scripts" / "engine"))
    import c3_cnv_fetch
    return c3_cnv_fetch


@pytest.mark.parametrize("punto,funcion", [
    ("antes del fetch", "load_identity"),
    ("durante el fetch", "fetch_empresa"),
    ("despues del discovery", "_persist_inventory"),
])
def test_c3_real_cierra_su_corrida_cuando_muere(eng, monkeypatch, punto, funcion):
    """Se rompe el c3 de verdad en tres puntos y se mira la BASE.

    Es la prueba que importa: no verifica que `run_scope` funcione (eso ya lo
    cubren los tests de arriba), verifica que C3 lo USE.
    """
    c3 = _c3()
    if not hasattr(c3, funcion):
        pytest.skip(f"{funcion} no existe en c3_cnv_fetch")

    with eng.connect() as c:
        antes = c.execute(text(
            "SELECT count(*) FROM engine.runs WHERE pipeline_version=:p"),
            {"p": c3.PIPELINE_VERSION}).scalar()

    def explota(*a, **k):
        raise RuntimeError(f"fallo inyectado {punto}")
    monkeypatch.setattr(c3, funcion, explota)
    monkeypatch.setattr(sys, "argv", ["c3", "--cuit", "33650305499"])

    with pytest.raises(RuntimeError, match="fallo inyectado"):
        c3.main()

    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT status, finished_at FROM engine.runs "
            " WHERE pipeline_version=:p ORDER BY started_at DESC LIMIT 1"),
            {"p": c3.PIPELINE_VERSION}).one()
        despues = c.execute(text(
            "SELECT count(*) FROM engine.runs WHERE pipeline_version=:p"),
            {"p": c3.PIPELINE_VERSION}).scalar()

    if funcion == "load_identity":
        # muere ANTES de abrir la corrida: no debe abrir ninguna
        assert despues == antes, "abrio una corrida antes de tener identidad"
        return
    assert despues == antes + 1, "no registro la corrida que efectivamente arranco"
    assert filas[0] == "ABORTED", f"{punto}: quedo {filas[0]}, no ABORTED"
    assert filas[1] is not None, f"{punto}: ABORTED sin finished_at"
