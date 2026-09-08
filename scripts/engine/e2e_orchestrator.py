#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E ORCHESTRATOR — Orquestación del pipeline SEC/EDGAR completo (S00→S04).

R4 — Opción A: un único run_id E2E que agrupa todas las etapas (S00–S04) como
stage_runs bajo el mismo run. Cada etapa se ejecuta como subprocess independiente,
pero todas escriben bajo el mismo run_id (propagado vía ENGINE_E2E_RUN_ID).

Responsabilidad primaria: EJECUTAR EL PIPELINE E2E.

NO modifica C11, checkpoints, validación ni otros contratos.

Uso:
    python scripts/engine/e2e_orchestrator.py [--mode FAST] [--run-id <existing>]

Output: run_id E2E o error. Exit 0 si todas las etapas PASS; exit 1 si alguna BLOCK/fail.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

STAGE_ID = "E2E_orchestrator"
PIPELINE_VERSION = "e2e-sec-edgar-v1"
SCRIPT = "scripts/engine/e2e_orchestrator.py"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Definición del pipeline: etapas en orden, con sus scripts.
STAGES = [
    ("S00_bootstrap", REPO_ROOT / "scripts" / "engine" / "s00_smoke.py", []),
    ("S01_identity", REPO_ROOT / "scripts" / "engine" / "s01_identity.py", []),
    ("S02_fetch", REPO_ROOT / "scripts" / "engine" / "s02_fetch_ypf.py", []),
    ("S03_parse", REPO_ROOT / "scripts" / "engine" / "s03_parse_ypf.py", []),
    ("S04_normalize", REPO_ROOT / "scripts" / "engine" / "s04_normalize.py", []),
]


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="e2e_orchestrator",
        description=__doc__,
    )
    ap.add_argument("--mode", default=None, help="modo FAST/FULL/AUDIT (default: de settings)")
    ap.add_argument("--run-id", default=None, help="reutilizar un run E2E existente (para re-ejecución)")
    ap.add_argument("--cik", default="0000904851",
                    help="CIK del emisor (default YPF Golden Case, 10 digitos)")
    ap.add_argument("--forms", default=None,
                    help="formularios S02 (default: del registro del emisor)")
    ap.add_argument("--min-xbrl", type=int, default=None,
                    help="umbral volumen S03 (default: del registro del emisor)")
    args = ap.parse_args()

    import issuers  # noqa: E402
    cik = (args.cik or "").zfill(10)
    spec = issuers.get_by_cik(cik)
    forms = args.forms or (",".join(spec["forms"]) if spec else None)
    min_xbrl = (args.min_xbrl if args.min_xbrl is not None
                else (spec["min_xbrl"] if spec else None))
    print(f"[emisor] cik={cik} issuer={spec['issuer_key'] if spec else 'desconocido'} "
          f"forms={forms} min_xbrl={min_xbrl}")
    extra_por_stage = {
        "s01_identity.py": ["--cik", cik],
        "s02_fetch_ypf.py": ["--cik", cik] + (["--forms", forms] if forms else []),
        "s03_parse_ypf.py": ["--cik", cik] + (
            ["--min-xbrl", str(min_xbrl)] if min_xbrl is not None else []),
    }

    settings = load_settings()
    if settings.is_prod:
        print("EXT-010: e2e_orchestrator no corre contra producción (puerto 5432).")
        return 2

    # Override de modo si se pasa --mode
    if args.mode:
        settings.mode = args.mode

    engine = edb.get_engine(settings)
    print(f"[config] target={settings.describe()} pipeline_version={PIPELINE_VERSION}")

    # Verificar precondiciones: migraciones, corridas huérfanas
    applied = edb.apply_migrations(engine, settings=settings)
    print(f"[migrations] aplicadas ahora: {applied or '(ninguna nueva)'}")

    huerfanas = edb.corridas_huerfanas(engine)
    if huerfanas:
        print(f"[error] hay {len(huerfanas)} corrida(s) huerfana(s) RUNNING >6h:")
        for h in huerfanas[:5]:
            print(f"   {h['run_id'][:12]} {h['pipeline_version']} hace {h['horas']}h")
        print("Resolverlas antes de continuar.")
        return 1

    # Crear o reutilizar run E2E
    if args.run_id:
        # Reutilizar run existente (re-ejecución): verificar que existe
        with engine.connect() as conn:
            existe = conn.execute(text(
                "SELECT count(*) FROM engine.runs WHERE run_id=:r"), {"r": args.run_id}).scalar()
        if not existe:
            print(f"[error] run_id {args.run_id} no existe en engine.runs")
            return 2
        run_id = args.run_id
        print(f"[run] reutilizando run E2E: {run_id}")
    else:
        # Crear run E2E nuevo
        run = edb.start_run(engine, settings, PIPELINE_VERSION)
        run_id = run.run_id
        print(f"[run] creado run E2E: {run_id} git={run.git_commit}")

    # El orquestador es el UNICO dueno del cierre del run E2E: las etapas en
    # modo E2E no cierran el run (run_scope con run_id no hace finish_run).
    # En `finally` se garantiza que el run quede terminal bajo cualquier
    # circunstancia (etapa BLOCK, excepcion, KeyboardInterrupt).
    exit_code = 0
    etapa_fallida: str | None = None
    try:
        # Encadenar etapas: cada una ejecuta como subprocess, propagando run_id
        print(f"\n--- inicio pipeline E2E ---")
        env = os.environ.copy()
        env["ENGINE_E2E_RUN_ID"] = run_id
        # Asegurar que la base de datos env vars se heredan
        if "ENGINE_DB_NAME" not in env:
            env["ENGINE_DB_NAME"] = settings.db_name
        if "ENGINE_DB_PORT" not in env:
            env["ENGINE_DB_PORT"] = str(settings.db_port)

        etapa_resultados: dict[str, dict] = {}
        for stage_id, script_path, args_extra in STAGES:
            print(f"\n>>> {stage_id}")
            print(f"    script: {script_path.name}")
            print(f"    run_id: {run_id}")

            cmd = ([sys.executable, str(script_path)] + args_extra
                   + extra_por_stage.get(script_path.name, []))
            try:
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=False,  # logs a stdout/stderr en vivo
                    timeout=3600,  # 1h por etapa
                )
                etapa_exit = result.returncode
            except subprocess.TimeoutExpired:
                print(f"    ERROR: timeout (>1h)")
                etapa_exit = 124
            except Exception as e:
                print(f"    ERROR: no se pudo ejecutar: {e}")
                etapa_exit = -1

            etapa_resultados[stage_id] = {
                "script": str(script_path),
                "exit_code": etapa_exit,
                "status": "PASS" if etapa_exit == 0 else "FAIL/BLOCK",
            }

            if etapa_exit != 0:
                print(f"    -> {stage_id} fallo con exit code {etapa_exit}")
                exit_code = 1
                etapa_fallida = stage_id
                break

            print(f"    -> {stage_id} OK (exit 0)")

        if exit_code == 0:
            print(f"\n--- fin pipeline E2E ---")
            print(f"Todas las etapas PASS")
            print(f"run_id E2E: {run_id}")

            # Resumen de etapas registradas
            print("\n--- stage_runs bajo este run_id ---")
            with engine.connect() as conn:
                stage_runs = conn.execute(
                    text("SELECT stage_id, state, gate_status FROM engine.stage_runs "
                         " WHERE run_id=:r ORDER BY stage_id"),
                    {"r": run_id},
                ).fetchall()
            for sr in stage_runs:
                print(f"   {sr[0]:20s} state={sr[1]:15s} gate={sr[2]}")
    finally:
        # Cierre garantizado del run E2E: terminal si no lo dejo una etapa.
        # Una etapa BLOCK deja el run en BLOCKED via su run_scope local (que
        # con run_id NO toca la base, solo el objeto), asi que aca se observa
        # el estado real: si una etapa fallo, el run va a ABORTED/BLOCKED.
        if exit_code != 0:
            # Una etapa fallo. Cerrar el run como ABORTED (o BLOCKED si la
            # etapa ya lo dejo asi en la base — no se sobrescribe el sentido).
            with engine.connect() as conn:
                estado = conn.execute(text(
                    "SELECT status FROM engine.runs WHERE run_id=:r"),
                    {"r": run_id}).scalar()
            if estado == "RUNNING":
                edb.finish_run(engine, run_id, "ABORTED")
            # Decisión R4/E2E: las etapas en modo E2E NO escriben checkpoints
            # individuales, asi que un run no-OK no deja checkpoints dangling
            # (F-031). No hay nada que limpiar aqui.
            print(f"\n--- pipeline abortado ---")
            print(f"Etapa fallida: {etapa_fallida}")
            print(f"Run E2E: {run_id} (estado final en la base: "
                  f"{conn_row_status(engine, run_id)})")
        else:
            edb.finish_run(engine, run_id, "OK")

    return exit_code


def conn_row_status(engine, run_id: str) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT status FROM engine.runs WHERE run_id=:r"),
                            {"r": run_id}).scalar()


if __name__ == "__main__":
    raise SystemExit(main())
