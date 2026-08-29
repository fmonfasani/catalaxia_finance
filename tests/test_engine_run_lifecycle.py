"""F-009 — toda corrida termina con estado terminal.

Siete corridas quedaron en RUNNING para siempre: cinco murieron en el arranque
y dos murieron entre validar y persistir, con el estado de ETAPA adelantado
respecto del estado de CORRIDA (llegaron a CHECKPOINTED sin report ni
finish_run). Sin estado terminal no se puede saber que corrida produjo que
artefacto, que es la precondicion para habilitar S04.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.config import load_settings  # noqa: E402
from engine.db import corridas_huerfanas, get_engine, run_scope  # noqa: E402

TERMINALES = {"OK", "ABORTED", "BLOCKED"}


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010")
    return get_engine(s)


def test_no_quedan_corridas_sin_estado_terminal(eng):
    with eng.connect() as c:
        filas = c.execute(text(
            "SELECT run_id, status, started_at FROM engine.runs "
            " WHERE status NOT IN ('OK','ABORTED','BLOCKED') OR finished_at IS NULL"
        )).mappings().all()
    assert not filas, f"corridas sin estado terminal: {[dict(f) for f in filas]}"


def test_todo_status_es_terminal_conocido(eng):
    with eng.connect() as c:
        estados = {r[0] for r in c.execute(text("SELECT DISTINCT status FROM engine.runs"))}
    assert estados <= TERMINALES, f"estados inesperados: {estados - TERMINALES}"


def test_no_hay_corridas_huerfanas(eng):
    huerfanas = corridas_huerfanas(eng, horas=6.0)
    assert not huerfanas, f"corridas huerfanas: {huerfanas}"


def test_run_scope_cierra_aunque_el_cuerpo_explote(eng):
    """La garantia que faltaba: el cierre va en `finally`."""
    s = load_settings()
    capturado = {}

    class Explota(RuntimeError):
        pass

    with pytest.raises(Explota):
        with run_scope(eng, s, "test-lifecycle") as run:
            capturado["run_id"] = run.run_id
            with eng.connect() as c:
                assert c.execute(text("SELECT status FROM engine.runs WHERE run_id=:r"),
                                 {"r": run.run_id}).scalar() == "RUNNING"
            raise Explota("el proceso muere aca, como murieron las 7")

    with eng.connect() as c:
        fila = c.execute(text(
            "SELECT status, finished_at FROM engine.runs WHERE run_id=:r"),
            {"r": capturado["run_id"]}).first()
    assert fila[0] == "ABORTED", "run_scope no cerro la corrida que exploto"
    assert fila[1] is not None


def test_run_scope_respeta_el_status_que_fija_el_cuerpo(eng):
    s = load_settings()
    with run_scope(eng, s, "test-lifecycle") as run:
        rid = run.run_id
        run.status = "BLOCKED"
    with eng.connect() as c:
        assert c.execute(text("SELECT status FROM engine.runs WHERE run_id=:r"),
                         {"r": rid}).scalar() == "BLOCKED"


# ===========================================================================
# F-031 — S03 usa run_scope, igual que S04
# ===========================================================================
def test_f031_s03_no_tiene_finish_run_suelto():
    """El cierre no puede depender de llegar a la ultima linea.

    S03 llamaba `finish_run` al final de main(). Cinco excepciones distintas en
    la serie de F-026/F-028 (permisos de DDL, de DELETE, de secuencia,
    statement_timeout, ANALYZE salteado) dejaron ocho corridas en RUNNING.
    """
    src = (Path(__file__).resolve().parents[1] /
           "scripts" / "engine" / "s03_parse_ypf.py").read_text(encoding="utf-8")
    assert "edb.finish_run(" not in src, (
        "S03 volvio a cerrar la corrida a mano; el cierre va en run_scope")
    assert "with edb.run_scope(" in src, "S03 no usa run_scope"
    assert "edb.start_run(" not in src, "S03 abre la corrida fuera de run_scope"


def test_f031_todas_las_etapas_usan_el_mismo_patron():
    base = Path(__file__).resolve().parents[1] / "scripts" / "engine"
    for script in ("s03_parse_ypf.py", "s04_normalize.py"):
        src = (base / script).read_text(encoding="utf-8")
        assert "with edb.run_scope(" in src, f"{script} no usa run_scope"
        assert "edb.corridas_huerfanas(" in src, f"{script} no chequea huerfanas al arrancar"


def test_f031_ningun_checkpoint_apunta_a_una_corrida_no_OK(eng):
    """Un checkpoint es una promesa: su corrida tiene que haber terminado bien."""
    with eng.connect() as c:
        malos = c.execute(text(
            "SELECT c.stage_id, c.checkpoint_id, r.status "
            "  FROM engine.checkpoints c JOIN engine.runs r ON r.run_id = c.run_id "
            " WHERE r.status <> 'OK'")).mappings().all()
    assert not malos, f"checkpoints sobre corridas no-OK: {[dict(m) for m in malos]}"
