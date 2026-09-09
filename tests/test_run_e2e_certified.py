# Unit tests del entrypoint unico de la cadena E2E certificada.
# NO tocan base de datos: prueban los contratos de text/parsing del
# orquestador (run_id), del acta C11 y del publisher C12.
from pathlib import Path

import pytest

from scripts.engine.run_e2e_certified import (
    LOCK_KEY,
    _extract_run_id,
    _parse_publisher_result,
)


def test_lock_key_determinista():
    assert isinstance(LOCK_KEY, int)
    assert LOCK_KEY != 0
    assert abs(LOCK_KEY) < 2**63  # cabe en BIGINT de Postgres (pg_try_advisory_lock)


@pytest.mark.parametrize("linea,esperado", [
    ("[run] creado run E2E: 0123456789abcdef0123456789abcdef git=abc", "0123456789abcdef0123456789abcdef"),
    ("[run] reutilizando run E2E: fedcba9876543210fedcba9876543210", "fedcba9876543210fedcba9876543210"),
    ("run_id E2E: 11112222333344445555666677778888", "11112222333344445555666677778888"),
])
def test_extract_run_id(linea, esperado):
    assert _extract_run_id(linea, None) == esperado


def test_extract_run_id_fallback_al_hint():
    assert _extract_run_id("", "deadbeefdeadbeefdeadbeefdeadbeef") == "deadbeefdeadbeefdeadbeefdeadbeef"


def test_extract_run_id_nada():
    assert _extract_run_id("sin run id", None) is None


def test_parse_publisher_published():
    out = ('{\n'
           '  "ok": true,\n'
           '  "reason": "PUBLISHED",\n'
           '  "target": "engine_facts",\n'
           '  "rows": 81234,\n'
           '}')
    ok, detail = _parse_publisher_result(out)
    assert ok is True
    assert "PUBLISHED" in detail and "rows=81234" in detail


def test_parse_publisher_dry_run():
    out = '{"ok": true, "reason": "DRY_RUN_OK"}'
    ok, detail = _parse_publisher_result(out)
    assert ok is True
    assert detail.startswith("DRY_RUN_OK")


def test_parse_publisher_bloqueado():
    out = '{\n  "ok": false,\n  "reason": "BLOCK:NO_CERTIFICACION",\n}'
    ok, detail = _parse_publisher_result(out)
    assert ok is False
    assert detail.startswith("BLOCK:")


def test_parse_publisher_salida_no_parseable():
    ok, detail = _parse_publisher_result("traceback\nlinea1\n")
    assert ok is False
    assert detail == "salida no parseable"


def test_parse_publisher_vacio():
    ok, detail = _parse_publisher_result("")
    assert ok is False
    assert detail == "salida no parseable"