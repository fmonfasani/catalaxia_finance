"""Test de integración del mecanismo E2E sin ejecutar el pipeline real.

Verifica que:
1. El orquestador propaga ENGINE_E2E_RUN_ID a los subprocesos.
2. Una etapa con la env var escribe stage_runs bajo el run E2E (y no crea run propio).
3. El run E2E queda cerrado por el orquestador.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402


@pytest.fixture(scope="module")
def s():
    st = load_settings()
    if st.is_prod:
        pytest.skip("EXT-010")
    return st


@pytest.fixture(scope="module")
def eng(s):
    return edb.get_engine(s)


@pytest.mark.parametrize("etapa_env", [
    "s00_smoke",
])
def test_etapa_con_env_escribe_bajo_run_e2e(eng, s, etapa_env):
    """S00 con ENGINE_E2E_RUN_ID escribe stage_run bajo el run E2E, sin crear run propio."""
    run = edb.start_run(eng, s, "e2e-sec-edgar-v1")
    run_id = run.run_id
    try:
        # Ejecutar la etapa real en subproceso con la env var
        import subprocess
        import sys as _sys
        env = dict(os.environ)
        env["ENGINE_E2E_RUN_ID"] = run_id
        env["ENGINE_DB_NAME"] = "catalaxia"
        env["ENGINE_DB_PORT"] = "5433"
        script = REPO / "scripts" / "engine" / f"{etapa_env}.py"
        result = subprocess.run([_sys.executable, str(script)], env=env, capture_output=True, timeout=120)

        # La etapa corre y escribe stage_run bajo el run E2E
        with eng.connect() as c:
            stage_runs = c.execute(text(
                "SELECT count(*) FROM engine.stage_runs WHERE run_id=:r"), {"r": run_id}).scalar()
            runs_propios = c.execute(text(
                "SELECT count(*) FROM engine.runs WHERE run_id=:r"), {"r": run_id}).scalar()
            # Decisión R4/E2E: en modo E2E S00 NO escribe checkpoint individual.
            checkpoint_s00 = c.execute(text(
                "SELECT count(*) FROM engine.checkpoints WHERE run_id=:r AND stage_id='S00_bootstrap'"),
                {"r": run_id}).scalar()

        assert stage_runs > 0, "S00 no escribió stage_runs bajo el run E2E"
        assert runs_propios == 1, "S00 creó un run propio en lugar de usar el E2E"
        assert checkpoint_s00 == 0, "en modo E2E S00 no debe escribir checkpoint (F-031)"
    finally:
        # Cerrar el run E2E como haría el orquestador (siempre, incluso si el assert falla)
        edb.finish_run(eng, run_id, "OK")


def test_etapa_sin_env_crea_run_propio(eng, s):
    """S00 sin ENGINE_E2E_RUN_ID crea su propio run (comportamiento individual)."""
    import subprocess
    import sys as _sys

    with eng.connect() as c:
        antes = c.execute(text(
            "SELECT count(*) FROM engine.runs WHERE pipeline_version='s0-bootstrap-v1'"
        )).scalar()

    env = dict(os.environ)
    env.pop("ENGINE_E2E_RUN_ID", None)
    env["ENGINE_DB_NAME"] = "catalaxia"
    env["ENGINE_DB_PORT"] = "5433"
    script = REPO / "scripts" / "engine" / "s00_smoke.py"
    result = subprocess.run([_sys.executable, str(script)], env=env, capture_output=True, timeout=120)
    assert result.returncode == 0, f"S00 individual falló: {result.stdout.decode()[-500:]}"

    with eng.connect() as c:
        despues = c.execute(text(
            "SELECT count(*) FROM engine.runs WHERE pipeline_version='s0-bootstrap-v1'"
        )).scalar()

    assert despues == antes + 1, "S00 sin env no creó un run propio nuevo"