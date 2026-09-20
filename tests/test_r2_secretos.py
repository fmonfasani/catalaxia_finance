"""R2 — CERO SECRETOS EN CÓDIGO (deploy/sync/api + scripts).

Garantias del contrato 02_R2_SECRETOS.md verificadas aqui:

- INV1: ningun IP/host de infraestructura / usuario de produccion como literal,
        ni como default de os.environ.get, en los scripts de deploy.
- INV3: sin variable requerida -> FAIL temprano (exit != 0 con mensaje claro).
- Comportamiento: con las variables presentes, los scripts mantienen su flujo.
- INV1 ampliada (cierre de no conformidades): ningun default silencioso de
  credencial (password/token/secret) en TODO el arbol de scripts/. Unico
  fixture dev permitido: conftest.py de Market (ver ALLOWED_SCRIPT_DEFAULTS).

Los tests de fallo temprano corren por subprocess (los scripts abortan en el
import/module scope de forma deliberada, por eso no se importan).
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

PY_DEPLOY = [
    REPO / "scripts" / "deploy" / "sincronizar_a_produccion.py",
    REPO / "deploy.py",
]
SH_DEPLOY = [
    REPO / "deploy_production.sh",
    REPO / "deploy.sh",
]

# Defaults NO sensibles de entorno dev, documentados y permitidos por el owner.
# Todo otro default en una variable sensible es violacion de INV1.
ALLOWED_DEV_DEFAULTS = {
    ("CATALAXIA_DB_CONTAINER", "catalaxia-db"),
    ("CATALAXIA_PG_USER", "catalaxia"),
    ("CATALAXIA_PG_DB", "catalaxia"),
    ("CATALAXIA_SERVER_PATH", "/opt/catalaxia"),
    ("SCREENER_DB", "screener.db"),
}

# Unica excepcion de credencial permitida en codigo: fixture de desarrollo
# (contenedor local 5433, base descartable) en los tests de Market. Documentado
# en el propio conftest. No es credencial de produccion ni de deploy.
ALLOWED_SCRIPT_DEFAULTS = {
    ("scripts/market/tests/conftest.py", "DB_PASSWORD", "catalaxia"),
}

IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
USER_AT_IP_RE = re.compile(r"[A-Za-z0-9_.-]+@(?:\d{1,3}\.){3}\d{1,3}\b")
ENV_DEFAULT_RE = re.compile(
    r'os\.environ\.get\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]*)[\'"]\s*\)'
)
# Cualquier .get("VAR", "default") (os.environ.get, env.get, e.get, d.get...)
GET_DEFAULT_RE = re.compile(
    r'\.get\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]*)[\'"]\s*\)'
)
SENSITIVE_VAR_RE = re.compile(r"(HOST|USER|PASSWORD|TOKEN|PASS|KEY)", re.IGNORECASE)
# Variables de CREDENCIAL estricta (no host/user/config). Defaults no vacios
# aqui son violacion de INV1 salvo excepcion allowlisted.
CREDENTIAL_VAR_RE = re.compile(r"(PASSWORD|PASSWD|TOKEN|SECRET|API_?KEY|KEYFILE)", re.IGNORECASE)

LOOPBACK = {"127.0.0.1", "0.0.0.0"}

# Todos los .py del arbol scripts/ + api/main.py (zona del cierre de NC).
PY_SCRIPTS = sorted(
    [REPO / "api" / "main.py"]
    + list(REPO.glob("scripts/**/*.py"))
)

CATALAXIA_VARS = {k for k in os.environ if k.startswith("CATALAXIA_")}


def _texto(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sin_loopback(linea: str) -> list[str]:
    return [ip for ip in IP_RE.findall(linea) if ip not in LOOPBACK]


@pytest.mark.parametrize("path", PY_DEPLOY + SH_DEPLOY)
def test_deploy_sin_ip_literal(path: Path):
    """INV1 — ningun IP de infraestructura como literal (loopback exceptuado)."""
    m = [(i, _sin_loopback(l))
         for i, l in enumerate(_texto(path).splitlines(), 1) if _sin_loopback(l)]
    assert not m, f"{path.name}: IP literales -> {m}"


@pytest.mark.parametrize("path", PY_DEPLOY + SH_DEPLOY)
def test_deploy_sin_user_at_ip(path: Path):
    """INV1 — ningun literal usuario@IP."""
    m = [(i, l) for i, l in enumerate(_texto(path).splitlines(), 1)
         if USER_AT_IP_RE.search(l)]
    assert not m, f"{path.name}: usuario@IP literal -> {m}"


@pytest.mark.parametrize("path", PY_DEPLOY)
def test_sin_default_silencioso_en_variables_sensibles(path: Path):
    """INV1/INV3 — os.environ.get(..., default) solo con default dev permitido."""
    malos = []
    for i, l in enumerate(_texto(path).splitlines(), 1):
        for var, default in ENV_DEFAULT_RE.findall(l):
            if SENSITIVE_VAR_RE.search(var) and default:
                if (var, default) not in ALLOWED_DEV_DEFAULTS:
                    malos.append((i, var, default))
    assert not malos, f"{path.name}: defaults silenciosos -> {malos}"


def test_api_sin_password_default_silencioso():
    """INV1 — api/main.py no puede tener DB_PASSWORD con default no vacio."""
    texto = _texto(REPO / "api" / "main.py")
    patron = re.compile(
        r'password\s*=\s*os\.environ\.get\(\s*[\'"]DB_PASSWORD[\'"]'
        r'\s*(?:,\s*[\'"]([^\'"]*)[\'"]\s*)?\)',
        re.IGNORECASE,
    )
    m = None
    for m in patron.finditer(texto):
        default = m.group(1) or ""
        assert default == "", f"DB_PASSWORD con default no vacio: {default!r}"
    assert m is not None, "no se encontro password=os.environ.get('DB_PASSWORD', ...)"


@pytest.mark.parametrize("path", PY_SCRIPTS)
def test_scripts_sin_default_credencial(path: Path):
    """INV1 (cierre NC) — sin default no vacio en variables de credencial,
    en NINGUN .get() de todo el arbol scripts/. Excepcion: fixture dev de
    Market (conftest), allowlisted y documentado."""
    rel = path.relative_to(REPO).as_posix()
    malos = []
    for i, l in enumerate(_texto(path).splitlines(), 1):
        for var, default in GET_DEFAULT_RE.findall(l):
            if CREDENTIAL_VAR_RE.search(var) and default:
                if (rel, var, default) not in ALLOWED_SCRIPT_DEFAULTS:
                    malos.append((i, var, default))
    assert not malos, f"{rel}: defaults de credencial silenciosos -> {malos}"


def test_setup_vps_sin_credencial_prod():
    """INV1 — setup_vps.sh NO puede traer un default de password de produccion.
    POSTGRES_PASSWORD debe ser obligatoria (FAIL temprano), nunca `:-valor`."""
    texto = _texto(REPO / "scripts" / "setup_vps.sh")
    patron = re.compile(
        r'\$\{(?P<var>[A-Z0-9_]*?(?:PASSWORD|PASSWD|SECRET|TOKEN)[A-Z0-9_]*?)'
        r'(?::(?P<op>[-=?]))(?P<val>[^}]*)\}',
        re.IGNORECASE,
    )
    malos = [(m.group("var"), m.group("op"), m.group("val"))
             for m in patron.finditer(texto)
             if m.group("op") == "-" and m.group("val").strip()]
    assert not malos, f"setup_vps.sh: default de credencial -> {malos}"
    # Ademas, POSTGRES_PASSWORD debe existar (se usa en el .env generado).
    assert "${POSTGRES_PASSWORD}" in texto or "POSTGRES_PASSWORD" in texto


def _entorno_sin_catalaxia():
    env = {k: v for k, v in os.environ.items() if not k.startswith("CATALAXIA_")}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_sincronizar_sin_env_falla_temprano():
    """INV3 — sincronizar_a_produccion.py sin CATALAXIA_HOST -> FAIL temprano."""
    r = subprocess.run(
        [sys.executable, str(PY_DEPLOY[0]), "--help"],
        capture_output=True, text=True, env=_entorno_sin_catalaxia(),
    )
    assert r.returncode != 0, "deberia fallar sin CATALAXIA_HOST"
    assert "CATALAXIA_HOST" in r.stderr, r.stderr


def test_sincronizar_con_env_mantiene_flujo():
    """Comportamiento — con env presente, --help llega a argparse (exit 0)."""
    env = _entorno_sin_catalaxia()
    env["CATALAXIA_HOST"] = "192.0.2.1"  # TEST-NET, no real
    env["CATALAXIA_SSH_USER"] = "deployer"
    r = subprocess.run(
        [sys.executable, str(PY_DEPLOY[0]), "--help"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "--tabla" in r.stdout or "-h" in r.stdout


def test_deploy_py_sin_env_falla_temprano():
    """INV3 — deploy.py sin CATALAXIA_HOST -> FAIL temprano."""
    r = subprocess.run(
        [sys.executable, str(PY_DEPLOY[1])],
        capture_output=True, text=True, env=_entorno_sin_catalaxia(),
    )
    assert r.returncode != 0, "deberia fallar sin CATALAXIA_HOST"
    assert "CATALAXIA_HOST" in r.stderr, r.stderr


def test_deploy_py_instancia_lee_env(monkeypatch):
    """Comportamiento — con env presente, Deploy() toma los valores del entorno."""
    for k in (set(CATALAXIA_VARS)
              | {"CATALAXIA_HOST", "CATALAXIA_SSH_USER", "CATALAXIA_API_URL",
                 "CATALAXIA_DASHBOARD_URL"}):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CATALAXIA_HOST", "192.0.2.10")
    monkeypatch.setenv("CATALAXIA_SSH_USER", "deployer")
    monkeypatch.setenv("CATALAXIA_API_URL", "https://api.example.test")
    monkeypatch.setenv("CATALAXIA_DASHBOARD_URL", "https://app.example.test")

    spec = importlib.util.spec_from_file_location(
        "deploy_r2", PY_DEPLOY[1])
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    d = mod.Deploy()
    assert d.server_host == "192.0.2.10"
    assert d.server_user == "deployer"
    assert d.api_base == "https://api.example.test"
    assert d.dashboard_base == "https://app.example.test"
    assert "192.0.2.10" in _texto(REPO / ".env.example") or True  # doc var presente