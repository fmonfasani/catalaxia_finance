"""F-001 — Market no puede escribir en produccion por accidente.

Antes de esto, cada script de Market abria `psycopg2.connect(...)` con
`DB_PORT` por defecto **5432**, que es produccion, y credenciales de escritura.
`python m2_fetch_engine.py` sin variables de entorno escribia en la base viva.
`m6_scale.py` escala a 584 instrumentos por esa misma via.

Se verifican las DOS barreras, por separado, porque cada una debe alcanzar sola:

  1. codigo        `market_db.connect()` es de solo lectura por defecto y
                   rechaza `write=True` contra 5432 sin habilitacion explicita
  2. privilegios   el rol `catalaxia_market_ro` tiene SELECT y nada mas, y sus
                   transacciones nacen `read_only`

Estos tests NO escriben nada: el unico camino que ejercitan es el que falla.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "market"))

import market_db  # noqa: E402


@pytest.fixture
def entorno_limpio(monkeypatch):
    """Aisla las variables que gobiernan la guarda."""
    for v in ("DB_PORT", "MARKET_ALLOW_PROD_WRITE", "DB_HOST", "DB_NAME"):
        monkeypatch.delenv(v, raising=False)
    yield monkeypatch


# ---------------------------------------------------------------------------
# BARRERA 1 — codigo
# ---------------------------------------------------------------------------

def test_el_default_es_produccion_y_por_eso_hace_falta_la_guarda(entorno_limpio):
    """El default historico apunta a 5432. La guarda existe justamente por eso."""
    entorno_limpio.setenv("DB_PORT", "5432")
    assert market_db.es_produccion() is True


def test_escribir_en_produccion_esta_bloqueado(entorno_limpio):
    entorno_limpio.setenv("DB_PORT", "5432")
    entorno_limpio.delenv("MARKET_ALLOW_PROD_WRITE", raising=False)
    with pytest.raises(market_db.MarketProdWriteBlocked) as e:
        market_db.connect(write=True)
    # el mensaje tiene que decir como proceder, no solo que fallo
    assert "MARKET_ALLOW_PROD_WRITE=1" in str(e.value)
    assert "5433" in str(e.value)


def test_exigir_dev_aborta_los_jobs_masivos_contra_produccion(entorno_limpio):
    """`m6_scale` (584 instrumentos) debe abortar antes de empezar."""
    entorno_limpio.setenv("DB_PORT", "5432")
    with pytest.raises(market_db.MarketProdWriteBlocked):
        market_db.exigir_dev("m6_scale --all")


def test_en_dev_la_escritura_no_esta_bloqueada(entorno_limpio):
    """La guarda protege produccion; no estorba en dev."""
    entorno_limpio.setenv("DB_PORT", "5433")
    assert market_db.es_produccion() is False
    market_db.exigir_dev("m6_scale --all")          # no levanta


def test_la_habilitacion_explicita_desbloquea(entorno_limpio):
    """Se puede escribir en prod, pero hay que decirlo. No es un accidente."""
    entorno_limpio.setenv("DB_PORT", "5432")
    entorno_limpio.setenv("MARKET_ALLOW_PROD_WRITE", "1")
    market_db.exigir_dev("carga deliberada")        # no levanta


def test_ningun_script_de_market_abre_su_propia_conexion():
    """La puerta es unica: si alguien vuelve a poner psycopg2.connect, falla."""
    culpables = []
    for py in (RAIZ / "scripts" / "market").glob("*.py"):
        if py.name == "market_db.py":
            continue
        if "psycopg2.connect" in py.read_text(encoding="utf-8"):
            culpables.append(py.name)
    assert not culpables, (
        f"estos scripts evaden la guarda F-001 con su propia conexion: {culpables}")


# ---------------------------------------------------------------------------
# BARRERA 2 — privilegios (requiere la base de produccion levantada)
# ---------------------------------------------------------------------------

@pytest.fixture
def conn_ro():
    os.environ.setdefault("DB_PORT", "5432")
    try:
        c = market_db.connect()
    except Exception as e:                       # noqa: BLE001
        pytest.skip(f"produccion no disponible: {type(e).__name__}: {e}")
    yield c
    c.close()


def test_el_rol_de_market_es_de_solo_lectura(conn_ro):
    with conn_ro.cursor() as cur:
        cur.execute("SELECT current_user, "
                    "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user)")
        usuario, superusuario = cur.fetchone()
    assert usuario == "catalaxia_market_ro"
    assert superusuario is False


def test_el_rol_de_market_no_puede_escribir_aunque_el_codigo_falle(conn_ro):
    """Si manana alguien se olvida de la guarda de codigo, la base igual frena."""
    import psycopg2
    for sentencia in (
        "INSERT INTO market_instruments (instrument_id, entity_id, ticker_canonico, "
        "instrument_type, currency) VALUES ('AUDIT','1','AUDIT','LOCAL','ARS')",
        "DELETE FROM market_price_daily WHERE false",
        "CREATE TABLE market_auditoria_prueba (x int)",
    ):
        with conn_ro.cursor() as cur:
            with pytest.raises(psycopg2.Error):
                cur.execute(sentencia)
        conn_ro.rollback()


def test_el_rol_de_market_si_puede_leer(conn_ro):
    with conn_ro.cursor() as cur:
        cur.execute("SELECT count(*) FROM market_instruments")
        assert cur.fetchone()[0] > 0
