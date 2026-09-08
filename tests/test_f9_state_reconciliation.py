"""Tests F9 — reconciliacion de estados operacionales (solo lectura).

Contratos que estos tests protegen y que no estaban cubiertos:

1. TERMINALIDAD DEL RUN: toda corrida en `engine.runs` con status terminal
   (OK/BLOCKED/ABORTED/FAILED/ERROR) tiene `finished_at`; no existe un estado
   RUNNING colgado con `finished_at IS NULL` salvo que sea realmente vida
   (`corridas_huerfanas()` es quien la detecta al arrancar etapas).

2. SEMANTICA DEL RESIDUO DE ETAPA: si el ultimo evento de una (run,stage)
   quedo en RUNNING (residuo de aborto por `run_scope` que cierra solo el
   run), entonces NECESARIAMENTE:
     - el run en `engine.runs` es ABORTED (proceso muerto), y
     - la etapa no tiene gate_status, ni report, ni checkpoint, ni
       certificacion, ni publicacion asociada.
   El residuo es informativo y nunca porta evidencia: por eso ni C10 lo
   certifica (gates None -> NO_PASS) ni C12 lo publica. Cualquier residuo
   con gate/report/checkpoint/cert/publicacion seria una inconsistencia real.

3. NO CONTAMINACION: el residuo de etapa no puede estar vinculado a datos
   (derived.fact), certificaciones o publicaciones.

Read-only: no escribe en base; ejecutar cuando quiera.
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

TERMINALES = ("OK", "BLOCKED", "ABORTED", "FAILED", "ERROR")

LATEST_BY_STAGE = (
    "sr.id = (SELECT max(id) FROM engine.stage_runs s2 "
    "WHERE s2.run_id=sr.run_id AND s2.stage_id=sr.stage_id)")


@pytest.fixture(scope="module")
def eng():
    return edb.get_engine(load_settings())


def _residuo_stage(conn):
    """Filas stage_runs cuyo ultimo estado por (run,stage) es RUNNING."""
    return conn.execute(text(
        "SELECT sr.run_id, sr.stage_id FROM engine.stage_runs sr "
        "WHERE sr.state='RUNNING' AND " + LATEST_BY_STAGE)).fetchall()


def test_run_terminal_tiene_finished_at(eng):
    with eng.connect() as c:
        malas = c.execute(text(
            "SELECT run_id, status FROM engine.runs "
            "WHERE status IN :t AND finished_at IS NULL"),
            {"t": TERMINALES}).fetchall()
    assert not malas, f"runs terminales sin finished_at: {malas[:5]}"


def test_sin_estados_desconocidos(eng):
    with eng.connect() as c:
        malas = c.execute(text(
            "SELECT status, count(*) FROM engine.runs "
            "WHERE status NOT IN :t AND status <> 'RUNNING' "
            "GROUP BY 1"), {"t": TERMINALES}).fetchall()
    assert not malas, f"estados desconocidos en engine.runs: {malas}"


def test_residuo_stage_solo_de_runs_aborted(eng):
    """El residuo RUNNING de etapa solo puede pertenecer a un run ABORTED."""
    with eng.connect() as c:
        residuo = _residuo_stage(c)
        if not residuo:
            return
        anormales = c.execute(text(
            "SELECT DISTINCT sr.run_id, r.status "
            "FROM engine.stage_runs sr JOIN engine.runs r USING (run_id) "
            "WHERE sr.state='RUNNING' AND " + LATEST_BY_STAGE +
            " AND r.status <> 'ABORTED'")).fetchall()
    assert not anormales, (
        f"residuo de etapa en runs no-ABORTED (inconsistencia real): {anormales}")


def test_residuo_stage_sin_evidencia(eng):
    """Residuo nunca porta gate/report/checkpoint (imposible certificar)."""
    with eng.connect() as c:
        con_evidencia = c.execute(text(
            "SELECT sr.run_id, sr.stage_id FROM engine.stage_runs sr "
            "WHERE sr.state='RUNNING' AND " + LATEST_BY_STAGE +
            " AND (sr.gate_status IS NOT NULL OR sr.report IS NOT NULL)")).fetchall()
    assert not con_evidencia, (
        f"residuo con gate/report: {con_evidencia}")


def test_residuo_stage_sin_checkpoint_cert_ni_publicacion(eng):
    """El residuo no dejo checkpoint, acta ni publicacion (no contamina)."""
    with eng.connect() as c:
        residuo = _residuo_stage(c)
        if not residuo:
            return
        runs = [r[0] for r in residuo]
        cks = c.execute(text(
            "SELECT count(*) FROM engine.checkpoints WHERE run_id IN :rs"),
            {"rs": tuple(runs)}).scalar()
        certs = c.execute(text(
            "SELECT count(*) FROM engine.certifications WHERE run_id IN :rs"),
            {"rs": tuple(runs)}).scalar()
        pubs = c.execute(text(
            "SELECT count(*) FROM staging._publications WHERE run_id IN :rs"),
            {"rs": tuple(runs)}).scalar()
    assert (cks, certs, pubs) == (0, 0, 0), (
        f"residuo con checkpoint/cert/publicacion: ck={cks} cert={certs} pub={pubs}")


def test_residuo_stage_no_produce_facts(eng):
    """El residuo no dejo filas en derived.fact (sin provenance aportada)."""
    with eng.connect() as c:
        residuo = _residuo_stage(c)
        if not residuo:
            return
        runs = [r[0] for r in residuo]
        n = c.execute(text(
            "SELECT count(*) FROM derived.fact WHERE run_id IN :rs"),
            {"rs": tuple(runs)}).scalar()
    assert n == 0, f"facts atribuidos a residuo: {n}"