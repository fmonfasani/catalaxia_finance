#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-049 — banco adversario del mecanismo de migraciones.

Contrato: docs/architecture/MIGRATIONS_CONTRACT.md

Cada escenario verifica el ESTADO FINAL de la base, no la ausencia de excepcion.
Todo corre sobre bases DESCARTABLES; la base homologada no se toca.

Uso:
    python scripts/engine/f049_bench.py
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import apply_migrations, get_admin_engine  # noqa: E402

OUT = REPO / "outputs" / "docs" / "homologacion"
MIG = REPO / "migrations" / "engine"
MIG_MARKET = REPO / "migrations" / "market"
# F-051: el runner aplica engine + market. Sobre una base SIN tablas de Market,
# solo entra `market/012_rol_market_readonly.sql` (roles, no depende de tablas);
# 013 y 025 se saltean hasta que `m19_apply_schema.py` cree las tablas.
MARKET_SIN_TABLAS = 1
BASE = "v101_bench"


def admin_a(dbname: str):
    """Engine admin apuntando a `dbname`, sin tocar la config global."""
    prev = os.environ.get("ENGINE_DB_NAME")
    os.environ["ENGINE_DB_NAME"] = dbname
    try:
        return get_admin_engine(load_settings()), load_settings()
    finally:
        if prev is None:
            os.environ.pop("ENGINE_DB_NAME", None)
        else:
            os.environ["ENGINE_DB_NAME"] = prev


def recrear(dbname: str) -> None:
    eng, _ = admin_a("postgres")
    with eng.connect() as c:
        c.execution_options(isolation_level="AUTOCOMMIT")
        c = c.execution_options(isolation_level="AUTOCOMMIT")
        c.execute(text(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{dbname}"'))
        c.execute(text(f'GRANT ALL ON DATABASE "{dbname}" TO catalaxia_engine'))
    eng.dispose()


def estado(dbname: str) -> dict:
    eng, _ = admin_a(dbname)
    with eng.connect() as c:
        existe = c.execute(text(
            "SELECT to_regclass('engine.schema_migrations') IS NOT NULL")).scalar()
        if not existe:
            eng.dispose()
            return {"tabla": False, "registradas": 0, "duplicados": 0,
                    "tablas_identity": 0, "triggers": 0, "checks": 0}
        d = {
            "tabla": True,
            "registradas": c.execute(text(
                "SELECT count(*) FROM engine.schema_migrations")).scalar(),
            "duplicados": c.execute(text(
                "SELECT count(*) FROM (SELECT filename FROM engine.schema_migrations "
                " GROUP BY 1 HAVING count(*)>1) x")).scalar(),
            "tablas_identity": c.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                " WHERE table_schema='identity_v1'")).scalar(),
            "triggers": c.execute(text(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class cl ON cl.oid=t.tgrelid "
                " JOIN pg_namespace n ON n.oid=cl.relnamespace WHERE n.nspname='identity_v1' "
                "   AND NOT t.tgisinternal AND t.tgenabled='O'")).scalar(),
            "checks": c.execute(text(
                "SELECT count(*) FROM pg_constraint "
                " WHERE connamespace='identity_v1'::regnamespace AND contype='c'")).scalar(),
            "orden": [r[0] for r in c.execute(text(
                "SELECT filename FROM engine.schema_migrations ORDER BY applied_at, filename"))],
        }
    eng.dispose()
    return d


def correr(dbname: str, mig_dir: Path = MIG):
    eng, s = admin_a(dbname)
    try:
        return apply_migrations(eng, mig_dir, settings=s), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e).splitlines()[0][:110]}"
    finally:
        eng.dispose()


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    n_eng = len(list(MIG.glob('*.sql')))
    n_mig = n_eng + MARKET_SIN_TABLAS   # lo que el runner aplica sobre base vacia
    res, ok_total = [], True

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK    ' if cond else 'FALLA '} {n:<48} {det}")
        res.append({"escenario": n, "ok": bool(cond), "detalle": str(det)})
        if not cond:
            ok_total = False

    print(f"F-049 · BANCO ADVERSARIO DE MIGRACIONES  ({n_mig} migraciones)\n")

    # 1 -------------------------------------------------------------
    recrear(BASE)
    ap, err = correr(BASE)
    e = estado(BASE)
    chk("1. instalacion desde DB vacia", err is None and ap and len(ap) == n_mig,
        err or f"{len(ap or [])} aplicadas")
    chk("   ...estado final completo",
        e["registradas"] == n_mig and e["tablas_identity"] == 9 and e["triggers"] == 15,
        f"reg={e['registradas']} tablas={e['tablas_identity']} trg={e['triggers']}")

    # 2 -------------------------------------------------------------
    ap2, err2 = correr(BASE)
    e2 = estado(BASE)
    chk("2. instalacion repetida (idempotente)",
        err2 is None and ap2 == [] and e2["registradas"] == n_mig,
        f"aplicadas={len(ap2 or [])} reg={e2['registradas']}")

    # 3 -------------------------------------------------------------
    chk("3. migracion ya registrada se saltea", ap2 == [], f"{len(ap2 or [])} re-aplicadas")

    # 8 -------------------------------------------------------------
    chk("8. sin duplicados en schema_migrations", e2["duplicados"] == 0, e2["duplicados"])

    # 9 -------------------------------------------------------------
    esperado = ([f"engine/{p.name}" for p in sorted(MIG.glob("*.sql"))]
                + ["market/012_rol_market_readonly.sql"])
    chk("9. orden determinista: engine, luego market",
        e2["orden"] == esperado,
        f"{len(e2['orden'])} en orden engine->market")

    # 10 ------------------------------------------------------------
    eng, _ = admin_a(BASE)
    with eng.begin() as c:
        c.execute(text("DELETE FROM engine.schema_migrations "
                       " WHERE filename LIKE '%031_f044_politica_estructural_cik_lei.sql'"))
    eng.dispose()
    ap3, err3 = correr(BASE)
    chk("10. detecta y re-aplica la faltante",
        err3 is None and ap3 == ["engine/031_f044_politica_estructural_cik_lei.sql"],
        err3 or f"{ap3}")
    chk("    ...sin duplicar", estado(BASE)["duplicados"] == 0)

    # 4 -------------------------------------------------------------
    recrear(BASE)
    eng, _ = admin_a(BASE)
    with eng.begin() as c:   # aplica 008 A MANO, como se hacia historicamente
        c.execute(text("CREATE SCHEMA IF NOT EXISTS engine"))
        c.execute(text("CREATE TABLE IF NOT EXISTS engine.schema_migrations ("
                       " filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"))
    eng.dispose()
    ap4, err4 = correr(BASE)
    e4 = estado(BASE)
    chk("4. base con schema_migrations preexistente",
        err4 is None and len(ap4 or []) == n_mig and e4["duplicados"] == 0,
        err4 or f"{len(ap4 or [])} aplicadas")

    # 5 y 6 ---------------------------------------------------------
    recrear(BASE)
    rota = REPO / "outputs" / "_f049_rota"
    rota.mkdir(parents=True, exist_ok=True)
    for f in sorted(MIG.glob("*.sql"))[:3]:
        (rota / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (rota / "999_falla.sql").write_text(
        "CREATE TABLE engine.zzz_prueba (id int);\nSELECT 1/0;\n", encoding="utf-8")
    ap5, err5 = correr(BASE, rota)
    e5 = estado(BASE)
    chk("5. una migracion que falla aborta", err5 is not None, (err5 or "")[:60])
    chk("6. rollback: no queda NADA aplicado",
        not e5["tabla"] or e5["registradas"] == 0,
        f"tabla={e5['tabla']} registradas={e5['registradas']}")
    eng, _ = admin_a(BASE)
    with eng.connect() as c:
        huerfana = c.execute(text("SELECT to_regclass('engine.zzz_prueba') IS NOT NULL")).scalar()
    eng.dispose()
    chk("   ...ni objetos huerfanos de la fallida", not huerfana, f"zzz_prueba existe={huerfana}")
    for f in rota.iterdir():
        f.unlink()
    rota.rmdir()

    # 7 -------------------------------------------------------------
    recrear(BASE)
    ap7, err7 = correr(BASE)
    e7 = estado(BASE)
    chk(f"7. aplicacion completa de las {n_mig}",
        err7 is None and len(ap7 or []) == n_mig and e7["registradas"] == n_mig,
        f"{len(ap7 or [])}/{n_mig}")

    # mecanismo individual: NO soportado, y se verifica que no lo esta ----
    eng, _ = admin_a(BASE)
    with eng.connect() as c:
        autoreg = sum(1 for p in MIG.glob("*.sql")
                      if "INSERT INTO engine.schema_migrations" in p.read_text(encoding="utf-8"))
    eng.dispose()
    chk("psql -f: ninguna migracion se auto-registra", autoreg == 0,
        f"{autoreg} con auto-registro")

    recrear(BASE)   # queda limpia; se elimina abajo
    eng, _ = admin_a("postgres")
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{BASE}" WITH (FORCE)'))
    eng.dispose()
    print("\n  (bases descartables eliminadas)")

    print(f"\n  {sum(1 for r in res if r['ok'])}/{len(res)} escenarios OK")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f049_bench.json").write_text(
        json.dumps({"ok": ok_total, "escenarios": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/homologacion/f049_bench.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
