"""Tests de seguridad del API (F10):
- autenticacion obligatoria por X-API-Key, fail-closed si API_KEY no esta configurada
- CORS con lista blanca, sin credenciales, sin eco arbitrario de Origin
- sin leak de detalles en respuestas 500
- salud: F10 y todos los endpoints no-DB que dependen del API.
Read-only: no escribe en base.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PASS = "test-key-123"
GOOD_ORIGIN = "https://app.example.com"
BAD_ORIGIN = "https://evil.example.net"


def _cargar(monkeypatch, api_key, cors=""):
    if api_key is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", api_key)
    monkeypatch.setenv("API_CORS_ORIGINS", cors)
    import api.main as m
    importlib.reload(m)
    return TestClient(m.app)


def test_sin_api_key_cierra_503(monkeypatch):
    c = _cargar(monkeypatch, None)
    r = c.get("/")
    assert r.status_code == 503
    assert r.json()["error"] == "api_key_not_configured"


def test_sin_header_api_key_401(monkeypatch):
    c = _cargar(monkeypatch, PASS)
    r = c.get("/")
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_api_key"


def test_api_key_incorrecta_401(monkeypatch):
    c = _cargar(monkeypatch, PASS)
    r = c.get("/", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


def test_api_key_correcta_200_health(monkeypatch):
    c = _cargar(monkeypatch, PASS)
    r = c.get("/", headers={"X-API-Key": PASS})
    assert r.status_code == 200
    assert r.json()["auth"] == "required"


def test_api_key_correcta_200_jobs_lista(monkeypatch):
    c = _cargar(monkeypatch, PASS)
    r = c.get("/v2/jobs", headers={"X-API-Key": PASS})
    assert r.status_code == 200
    assert "data" in r.json()


def test_escritura_jobs_requiere_key(monkeypatch):
    c = _cargar(monkeypatch, PASS)
    r = c.post("/v2/jobs/create")
    assert r.status_code == 401
    r = c.post("/v2/jobs/create", headers={"X-API-Key": PASS})
    assert r.status_code == 200


def test_cors_preflight_origen_permitido(monkeypatch):
    c = _cargar(monkeypatch, PASS, cors=GOOD_ORIGIN)
    r = c.options(
        "/",
        headers={
            "Origin": GOOD_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == GOOD_ORIGIN
    assert "true" != (r.headers.get("access-control-allow-credentials") or "")


def test_cors_preflight_origen_no_permitido(monkeypatch):
    c = _cargar(monkeypatch, PASS, cors=GOOD_ORIGIN)
    r = c.options(
        "/",
        headers={
            "Origin": BAD_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") is None


def test_error_handler_500_no_leakea_detalle(monkeypatch):
    """Handler global: respuesta generica sin tipo/detalle de la excepcion."""
    import api.main as m
    monkeypatch.setenv("API_KEY", PASS)
    monkeypatch.setenv("API_CORS_ORIGINS", GOOD_ORIGIN)
    importlib.reload(m)
    c = TestClient(m.app, raise_server_exceptions=False)

    @c.app.get("/boom")
    def boom():
        raise RuntimeError("secreto-interno-no-expuesto")

    r = c.get("/boom", headers={"X-API-Key": PASS})
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "internal_error"
    assert "secreto-interno-no-expuesto" not in str(body)
    assert "detalle" not in body
    assert "tipo" not in body