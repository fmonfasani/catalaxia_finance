#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE de F-049.

NO importa `f049_bench` ni el codigo que corrigio el defecto. Reconstruye desde
los archivos del release, `psql` directo, el catalogo de PostgreSQL y git.

El runner (`engine.db.apply_migrations`) SI se ejecuta -- es el objeto auditado,
no una herramienta del implementador: la pregunta es si el mecanismo oficial
funciona, y no hay forma de responderla sin invocarlo.

Responde las 7 preguntas del encargo.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "outputs" / "docs" / "homologacion"
DB = "v101_audit"


def psql(dbname: str, sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "catalaxia-engine-dev", "psql", "-U", "catalaxia",
         "-d", dbname, "-tAc", sql],
        capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    return (r.stdout or r.stderr).strip()


def main() -> int:
    resp, ok = {}, True

    def chk(n, cond, det=""):
        nonlocal ok
        print(f"  {'SI ' if cond else 'NO '} {n:<52} {det}")
        resp[n] = {"ok": bool(cond), "detalle": str(det)}
        if not cond:
            ok = False

    print("AUDITORIA INDEPENDIENTE · F-049\n")

    # ---- evidencia estatica, sin ejecutar nada -------------------------
    mig = sorted((REPO / "migrations" / "engine").glob("*.sql"))
    autoreg = [p.name for p in mig
               if "INSERT INTO engine.schema_migrations" in p.read_text(encoding="utf-8")]
    print(f"  archivos: {len(mig)} migraciones de engine")
    chk("3b. ninguna migracion se auto-registra", not autoreg, autoreg or "0")

    runner = (REPO / "engine" / "db.py").read_text(encoding="utf-8")
    n_ins = runner.count("INSERT INTO engine.schema_migrations")
    chk("3c. el runner es el unico escritor del registro", n_ins == 1,
        f"{n_ins} INSERT en engine/db.py")

    # ---- 1. instalacion desde cero ------------------------------------
    psql("postgres", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
    psql("postgres", f'CREATE DATABASE "{DB}"')
    psql(DB, "GRANT ALL ON DATABASE " + DB + " TO catalaxia_engine")
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'.');"
         "from engine.config import load_settings;"
         "from engine.db import get_admin_engine, apply_migrations;"
         "s=load_settings();"
         "print(len(apply_migrations(get_admin_engine(s), settings=s)))"],
        cwd=str(REPO), capture_output=True, text=True,
        env={**os.environ, "ENGINE_DB_NAME": DB})
    n1 = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else "ERROR"
    chk("1. el release se instala desde cero", n1 == str(len(mig)),
        f"{n1} migraciones (esperadas {len(mig)})")

    reg = psql(DB, "SELECT count(*) FROM engine.schema_migrations")
    dup = psql(DB, "SELECT count(*) FROM (SELECT filename FROM "
                   "engine.schema_migrations GROUP BY 1 HAVING count(*)>1) x")
    chk("3. registradas exactamente una vez", reg == str(len(mig)) and dup == "0",
        f"registradas={reg} duplicados={dup}")

    # ---- 2. repetible --------------------------------------------------
    r2 = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'.');"
         "from engine.config import load_settings;"
         "from engine.db import get_admin_engine, apply_migrations;"
         "s=load_settings();"
         "print(len(apply_migrations(get_admin_engine(s), settings=s)))"],
        cwd=str(REPO), capture_output=True, text=True,
        env={**os.environ, "ENGINE_DB_NAME": DB})
    n2 = (r2.stdout or "").strip().splitlines()[-1] if r2.stdout.strip() else "ERROR"
    chk("2. se puede repetir", n2 == "0", f"{n2} re-aplicadas")

    # ---- 5. determinismo: estructura == base homologada ---------------
    def estructura(d):
        return (psql(d, "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='identity_v1' "
                        "AND NOT t.tgisinternal AND t.tgenabled='O'"),
                psql(d, "SELECT count(*) FROM pg_constraint WHERE "
                        "connamespace='identity_v1'::regnamespace AND contype='c'"),
                psql(d, "SELECT count(*) FROM pg_indexes WHERE schemaname='identity_v1' "
                        "AND indexdef LIKE '%UNIQUE%'"),
                psql(d, "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema='identity_v1'"))
    nueva, homol = estructura(DB), estructura("catalaxia")
    chk("5. estado final determinista (== homologada)", nueva == homol,
        f"nueva={nueva} homologada={homol}")

    # ---- 4. rollback ---------------------------------------------------
    psql("postgres", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
    psql("postgres", f'CREATE DATABASE "{DB}"')
    psql(DB, "GRANT ALL ON DATABASE " + DB + " TO catalaxia_engine")
    rota = REPO / "outputs" / "_f049_audit"
    rota.mkdir(parents=True, exist_ok=True)
    for f in mig[:2]:
        (rota / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (rota / "998_rompe.sql").write_text("CREATE TABLE engine.aud_zzz (id int);\n"
                                        "SELECT 1/0;\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'.');"
         "from pathlib import Path;"
         "from engine.config import load_settings;"
         "from engine.db import get_admin_engine, apply_migrations;"
         "s=load_settings();"
         "apply_migrations(get_admin_engine(s), Path('outputs/_f049_audit'), settings=s)"],
        cwd=str(REPO), capture_output=True, text=True,
        env={**os.environ, "ENGINE_DB_NAME": DB})
    quedo = psql(DB, "SELECT to_regclass('engine.aud_zzz') IS NOT NULL")
    tabla = psql(DB, "SELECT to_regclass('engine.schema_migrations') IS NOT NULL")
    chk("4. un fallo produce rollback correcto", quedo != "t" and tabla != "t",
        f"objeto huerfano={quedo} tabla_registro={tabla}")
    for f in rota.iterdir():
        f.unlink()
    rota.rmdir()

    # ---- 6. base homologada intacta ------------------------------------
    h = psql("catalaxia",
             "SELECT (SELECT count(*) FROM identity_v1.entity)||'|'||"
             "(SELECT count(*) FROM identity_v1.assertion)||'|'||"
             "(SELECT count(*) FROM engine.schema_migrations)||'|'||"
             "(SELECT count(*) FROM engine.runs WHERE status='RUNNING')")
    chk("6. la base homologada no fue modificada", h == "525|614|29|0", h)

    # ---- 7. el tag contiene la correccion -------------------------------
    tag = subprocess.run(["git", "tag", "--points-at", "HEAD"], cwd=str(REPO),
                         capture_output=True, text=True).stdout.strip()
    en_tag = subprocess.run(
        ["git", "show", "v1.0.1:migrations/engine/008_identity_v1.sql"],
        cwd=str(REPO), capture_output=True, text=True).stdout
    chk("7. el tag v1.0.1 contiene la correccion",
        bool(en_tag) and "INSERT INTO engine.schema_migrations" not in en_tag,
        f"tag en HEAD: {tag or '(ninguno)'}")

    psql("postgres", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
    print("\n  (base descartable eliminada)")

    print(f"\n  F-049 = {'CLOSED' if ok else 'OPEN'}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit_f049.json").write_text(
        json.dumps({"veredicto": "CLOSED" if ok else "OPEN", "respuestas": resp},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/homologacion/audit_f049.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
