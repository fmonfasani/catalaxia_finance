"""Guardas: sandbox + stubs fail-closed (anti-producción, anti-oracle)."""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _run(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args],
                          capture_output=True, text=True)


def test_stubs_refuse_outside_sandbox():
    r = _run("fetch_bcra_a3500.py", "--from", "2020-01-01", "--to", "2020-03-31",
             "--out", "D:/Software Development/Porfolio/catalaxia-cedears-prod/data/x")
    assert r.returncode != 0 and "REFUSADO" in (r.stdout + r.stderr)


def test_stubs_fail_closed_without_data():
    r = _run("fetch_bcra_a3500.py", "--from", "2020-01-01", "--to", "2020-03-31")
    assert r.returncode != 0 and "NO IMPLEMENTADO" in (r.stdout + r.stderr)
    r = _run("tikr_fx_compare.py", "--benchmark", "x", "--out", "y")
    assert r.returncode != 0 and "UNKNOWN" in (r.stdout + r.stderr)
