"""F-050 — S00, S01 y S02 deben cerrar su corrida SIEMPRE.

El defecto lo encontro el E2E de v1.0.1: dos fallos reales dejaron 3 corridas en
RUNNING. Las tres etapas usaban start_run()/finish_run() sin run_scope(), mientras
S03/S04/C3 ya usaban el mecanismo correcto desde F-031/F-040.

Estos tests atacan el `main()` REAL de cada etapa, no una simulacion, e inyectan
fallos en los puntos del contrato. Se mira la BASE, no el mensaje de error.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

ETAPAS = ["s00_smoke", "s01_identity", "s02_fetch_ypf"]
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


def modulo(nombre):
    import importlib
    return importlib.import_module(nombre)


def ultima(eng, pipeline):
    with eng.connect() as c:
        return c.execute(text(
            "SELECT status, finished_at FROM engine.runs WHERE pipeline_version=:p "
            " ORDER BY started_at DESC LIMIT 1"), {"p": pipeline}).first()


# ===========================================================================
# El contrato estructural: ninguna etapa cierra a mano
# ===========================================================================

@pytest.mark.parametrize("etapa", ETAPAS + ["s03_parse_ypf", "s04_normalize",
                                            "c3_cnv_fetch"])
def test_ninguna_etapa_abre_o_cierra_la_corrida_a_mano(etapa):
    """Un solo dueno del cierre. Dos fue lo que produjo F-049."""
    src = (REPO / "scripts" / "engine" / f"{etapa}.py").read_text(encoding="utf-8")
    assert "edb.start_run(" not in src, f"{etapa} abre la corrida a mano"
    assert "edb.finish_run(" not in src, f"{etapa} cierra la corrida a mano"
    assert "edb.run_scope(" in src, f"{etapa} no usa run_scope"


@pytest.mark.parametrize("etapa", ETAPAS)
def test_cada_etapa_avisa_de_huerfanas_al_arrancar(etapa):
    """F-040 dejo esta practica en C3; F-050 la extiende a las tres."""
    src = (REPO / "scripts" / "engine" / f"{etapa}.py").read_text(encoding="utf-8")
    assert "corridas_huerfanas" in src, f"{etapa} no revisa huerfanas al arrancar"


# ===========================================================================
# Inyeccion de fallos contra el main() REAL
# ===========================================================================

INYECCIONES = [
    # (etapa, funcion a romper, escenario del contrato)
    ("s00_smoke", "load_settings", "A1 fallo antes de abrir la corrida"),
    ("s01_identity", "load_settings", "A1 fallo antes de abrir la corrida"),
    ("s01_identity", "_correr", "A2 fallo durante el procesamiento"),
    ("s02_fetch_ypf", "_correr", "A2 fallo durante el procesamiento"),
    ("s00_smoke", "_correr", "A2 fallo durante el procesamiento"),
]


@pytest.mark.parametrize("etapa,funcion,escenario", INYECCIONES)
def test_un_fallo_deja_estado_terminal(eng, monkeypatch, etapa, funcion, escenario):
    m = modulo(etapa)
    if not hasattr(m, funcion):
        pytest.skip(f"{etapa} no tiene {funcion}")
    pipeline = m.PIPELINE_VERSION

    with eng.connect() as c:
        antes = c.execute(text("SELECT count(*) FROM engine.runs WHERE pipeline_version=:p"),
                          {"p": pipeline}).scalar()

    def explota(*a, **k):
        raise RuntimeError(f"fallo inyectado: {escenario}")

    monkeypatch.setattr(m, funcion, explota)
    monkeypatch.setattr(sys, "argv", [etapa])
    with pytest.raises((RuntimeError, SystemExit)):
        m.main()

    with eng.connect() as c:
        despues = c.execute(text("SELECT count(*) FROM engine.runs WHERE pipeline_version=:p"),
                            {"p": pipeline}).scalar()

    if funcion == "load_settings":
        # muere ANTES de abrir la corrida: no debe abrir ninguna
        assert despues == antes, f"{etapa} abrio una corrida antes de tener configuracion"
        return
    assert despues == antes + 1, f"{etapa} no registro la corrida que arranco"
    st, fin = ultima(eng, pipeline)
    assert st == "ABORTED", f"{escenario} en {etapa}: quedo {st}, no ABORTED"
    assert fin is not None, f"{escenario} en {etapa}: ABORTED sin finished_at"


@pytest.mark.parametrize("etapa", ETAPAS)
def test_systemexit_y_keyboardinterrupt_tambien_cierran(eng, monkeypatch, etapa):
    """S02 tenia una ruta `raise SystemExit` que no cerraba la corrida (L260)."""
    m = modulo(etapa)
    pipeline = m.PIPELINE_VERSION
    for exc in (SystemExit("BLOCK simulado"), KeyboardInterrupt()):
        def explota(*a, _e=exc, **k):
            raise _e
        monkeypatch.setattr(m, "_correr", explota)
        monkeypatch.setattr(sys, "argv", [etapa])
        with pytest.raises(type(exc)):
            m.main()
        st, fin = ultima(eng, pipeline)
        assert st == "ABORTED", f"{etapa} tras {type(exc).__name__}: quedo {st}"
        assert fin is not None


# ===========================================================================
# El invariante
# ===========================================================================

def test_ninguna_corrida_de_s00_s01_s02_queda_en_running(eng):
    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT pipeline_version, count(*) FROM engine.runs "
            " WHERE status='RUNNING' AND pipeline_version IN "
            "  ('s0-bootstrap-v1','s1-identity-v1','s2-fetch-v1') "
            " GROUP BY 1")).all()
    assert not filas, f"corridas de S00/S01/S02 en RUNNING: {filas}"


def test_todo_estado_es_terminal_o_vive(eng):
    with eng.connect() as c:
        malas = c.execute(text(
            "SELECT pipeline_version, status, count(*) FROM engine.runs "
            " WHERE status NOT IN :t AND status<>'RUNNING' GROUP BY 1,2"),
            {"t": TERMINALES}).all()
    assert not malas, f"estados desconocidos: {malas}"
