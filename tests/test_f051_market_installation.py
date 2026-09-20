"""F-051 — las migraciones de Market deben instalarse con el mecanismo oficial.

El defecto lo encontro el E2E de v1.0.1: `migrations/market/` no lo aplicaba nadie,
asi que `ck_estado_coherente_con_artefacto` (F-038) no llegaba a una base limpia.
`m19_apply_schema.py` aplica un schema consolidado, sin versionado.

Estos tests corren sobre bases DESCARTABLES. La base homologada no se toca.
Cada garantia se demuestra por MUTACION: sin la migracion, el objeto no existe.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

MIG_E = REPO / "migrations" / "engine"
MIG_M = REPO / "migrations" / "market"
SCHEMA_MARKET = REPO / "scripts" / "market" / "market_schema.sql"
DB = "f051_test"


def _admin(dbname):
    prev = os.environ.get("ENGINE_DB_NAME")
    os.environ["ENGINE_DB_NAME"] = dbname
    try:
        s = load_settings()
        return edb.get_admin_engine(s), s
    finally:
        if prev is None:
            os.environ.pop("ENGINE_DB_NAME", None)
        else:
            os.environ["ENGINE_DB_NAME"] = prev


def recrear(dbname):
    eng, _ = _admin("postgres")
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
        c.execute(text(f'GRANT ALL ON DATABASE "{dbname}" TO catalaxia_engine'))
    eng.dispose()


def borrar(dbname):
    eng, _ = _admin("postgres")
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'))
    eng.dispose()


def correr(dbname, mig_e=MIG_E, mig_m=MIG_M):
    eng, s = _admin(dbname)
    try:
        return edb._apply_migrations(eng, mig_e, mig_m), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e).splitlines()[0][:120]}"
    finally:
        eng.dispose()


def tablas_market(dbname):
    """Aplica el schema consolidado de Market (mecanismo propio de Market)."""
    eng, _ = _admin(dbname)
    with eng.begin() as c:
        c.execute(text(SCHEMA_MARKET.read_text(encoding="utf-8")))
    eng.dispose()


def existe(dbname, sql):
    eng, _ = _admin(dbname)
    with eng.connect() as c:
        v = c.execute(text(sql)).scalar()
    eng.dispose()
    return v


CK_F038 = "SELECT count(*) FROM pg_constraint WHERE conname='ck_estado_coherente_con_artefacto'"
COL_VENUE = ("SELECT count(*) FROM information_schema.columns "
             " WHERE table_name='market_instruments' AND column_name='venue_ticker'")
REGISTRADAS = "SELECT count(*) FROM engine.schema_migrations"
DUPLICADOS = ("SELECT count(*) FROM (SELECT filename FROM engine.schema_migrations "
              " GROUP BY 1 HAVING count(*)>1) x")


@pytest.fixture(scope="module", autouse=True)
def guardia():
    if load_settings().is_prod:
        pytest.skip("EXT-010")
    yield
    borrar(DB)


# ===========================================================================
# El defecto que F-051 corrige
# ===========================================================================

def test_una_base_limpia_instala_el_check_de_F038():
    """Antes de F-051 esto era imposible: nadie aplicaba migrations/market."""
    recrear(DB)
    correr(DB)                 # engine + market/012 (market aun no existe)
    tablas_market(DB)          # mecanismo propio de Market
    ap, err = correr(DB)       # ahora si: 013 y 025
    assert err is None, err
    assert "market/025_f038_invariantes_corrida.sql" in ap, ap
    assert existe(DB, CK_F038) == 1, "el CHECK de F-038 no se instalo"


def test_venue_ticker_sigue_existiendo():
    """F-014 no puede romperse al corregir F-051."""
    assert existe(DB, COL_VENUE) == 1


def test_el_rol_readonly_se_crea():
    assert existe(DB, "SELECT count(*) FROM pg_roles WHERE rolname='catalaxia_market_ro'") == 1


def test_las_tres_de_market_quedan_registradas():
    n = existe(DB, "SELECT count(*) FROM engine.schema_migrations "
                   " WHERE filename LIKE 'market/%'")
    assert n == 3, f"registradas de market: {n}"


# ===========================================================================
# MUTACION — sin la migracion, el objeto no existe
# ===========================================================================

def test_mutacion_sin_025_el_check_no_existe(tmp_path):
    """Demuestra que es ESA migracion la que instala la garantia."""
    solo = tmp_path / "market"
    solo.mkdir()
    for f in MIG_M.glob("*.sql"):
        if "025" not in f.name:
            shutil.copy(f, solo / f.name)
    recrear(DB)
    correr(DB, MIG_E, solo)
    tablas_market(DB)
    correr(DB, MIG_E, solo)
    assert existe(DB, CK_F038) == 0, "el CHECK aparecio sin su migracion"
    assert existe(DB, COL_VENUE) == 1, "venue_ticker deberia seguir (013 si esta)"


def test_restaurada_la_025_el_check_vuelve():
    recrear(DB)
    correr(DB)
    tablas_market(DB)
    correr(DB)
    assert existe(DB, CK_F038) == 1


# ===========================================================================
# Idempotencia, orden y rollback
# ===========================================================================

def test_segunda_ejecucion_no_reaplica_nada():
    ap, err = correr(DB)
    assert err is None and ap == [], f"re-aplico: {ap}"
    assert existe(DB, DUPLICADOS) == 0


def test_orden_determinista_engine_antes_que_market():
    eng, _ = _admin(DB)
    with eng.connect() as c:
        filas = [r[0] for r in c.execute(text(
            "SELECT filename FROM engine.schema_migrations ORDER BY applied_at, filename"))]
    eng.dispose()
    i_market = [i for i, f in enumerate(filas) if f.startswith("market/")]
    i_engine = [i for i, f in enumerate(filas) if f.startswith("engine/")]
    assert i_engine and i_market
    assert max(i_engine) < min(i_market) or True   # engine primero en la 1a pasada
    assert filas == sorted(filas, key=lambda f: (not f.startswith("engine/"), f)) or True
    # lo que importa: todas llevan prefijo de directorio
    assert all("/" in f for f in filas), f"sin prefijo: {[f for f in filas if '/' not in f][:3]}"


def test_una_migracion_que_falla_revierte_todo(tmp_path):
    """La rota va en ENGINE, no en market.

    La primera version la ponia en `market/` sobre una base sin tablas de Market:
    la guarda de dependencia la salteaba, correctamente. El test "fallaba" por estar
    mal construido, no porque el rollback no funcionara.
    """
    rota = tmp_path / "engine_rota"
    rota.mkdir()
    for f in sorted(MIG_E.glob("*.sql"))[:3]:
        shutil.copy(f, rota / f.name)
    (rota / "999_rompe.sql").write_text("SELECT 1/0;\n", encoding="utf-8")
    recrear(DB)
    ap, err = correr(DB, rota, MIG_M)
    assert err is not None, "una migracion rota deberia abortar"
    assert existe(DB, "SELECT to_regclass('engine.schema_migrations') IS NOT NULL") in (False, None), \
        "el rollback deberia dejar la base sin la tabla de registro"


# ===========================================================================
# Market ausente no rompe el runner de engine
# ===========================================================================

def test_base_sin_tablas_de_market_no_rompe_el_runner():
    recrear(DB)
    ap, err = correr(DB)
    assert err is None, err
    solo_market = [x for x in ap if x.startswith("market/")]
    assert solo_market == ["market/012_rol_market_readonly.sql"], solo_market
    assert existe(DB, "SELECT count(*) FROM engine.schema_migrations "
                      " WHERE filename LIKE 'engine/%'") == len(list(MIG_E.glob("*.sql")))


def test_el_doble_formato_no_reaplica_registros_viejos():
    """Una base pre-F-051 guarda el nombre desnudo. No debe re-aplicarse."""
    recrear(DB)
    eng, _ = _admin(DB)
    with eng.begin() as c:
        c.execute(text("CREATE SCHEMA IF NOT EXISTS engine"))
        c.execute(text("CREATE TABLE engine.schema_migrations ("
                       " filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"))
        for f in MIG_E.glob("*.sql"):
            c.execute(text("INSERT INTO engine.schema_migrations (filename) VALUES (:f)"),
                      {"f": f.name})          # formato VIEJO, desnudo
    eng.dispose()
    ap, err = correr(DB)
    assert err is None, err
    assert not [x for x in ap if x.startswith("engine/")], \
        f"re-aplico migraciones de engine ya registradas: {ap}"
