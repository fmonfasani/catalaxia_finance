#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RUN_E2E_CERTIFIED — entrypoint UNICO del runtime productivo del engine (F12).

Cadena oficial (ADR `docs/review/26_F12_ARCHITECTURE_DECISION.md`, seccion
"Execution chain" y "Acceptance criteria" AC-1):

    S00 → S04 (e2e_orchestrator.py) → ratio_engine → C10 → C11 → C12
                                                        (publisher, staging)

con ABORT-ON-FAIL: si un eslabon no da PASS / CERTIFICADA / ALLOW, la cadena
se detiene y el run E2E queda en estado terminal recuperable (F10/F13).

Lo que este entrypoint agrega y NO existia antes (AC-1/AC-2/AC-3/AC-4):

  * LOCK (AC-4): advisory lock de PostgreSQL contra corridas cron superpuestas.
    La clave es un entero determinista (no un archivo): vale en cualquier host
    y en cualquier contenedor que comparta la base — dos cron de dos VPS no
    pueden pisarse.
  * MIGRATIONS: aplica migraciones pendientes por la via administrativa
    (F-025) antes de la cadena, para que una base limpia arranque a la primera.
  * REPORT: artefacto JSON por corrida en `<json-out>/e2e_<run_id>.json`.

Uso:
    python scripts/engine/run_e2e_certified.py [--mode FAST] [--cik 0000904851]
        [--tickers YPFD] [--scope sec] [--run-id <hex>]
        [--no-lock] [--no-ratios] [--dry-run]
        [--publish-source derived.fact] [--publish-target engine_facts]
        [--publish-pk fact_key] [--json-out outputs/e2e]

Exit codes:
    0  cadena completa PASS/CERTIFICADA/ALLOW (o C12_SKIPPED declarado)
    1  cadena abortada: BLOCK / NEGADA / NOT_PUBLISHED / migrations
    2  error de uso o EXT-010 (destino prod sin ENGINE_ALLOW_PROD=1)
    3  lock ocupado: ya corre otra instancia de la cadena
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "engine"))

# El docstring y el output de la cadena llevan no-ASCII (es, flechas). En
# consolas heredadas (cp1252/cp850) `--help` y los prints reventaban con
# UnicodeEncodeError. Fijar UTF-8 temprano evita depender de la locale.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

PIPELINE_VERSION = "e2e-certificado-v1"
ENTRYPOINT = "scripts/engine/run_e2e_certified.py"

LOCK_KEY = int.from_bytes(hashlib.sha256(b"catalaxia-engine-e2e-v1").digest()[:8],
                          "little", signed=True)

RE_RUN_NEW = re.compile(r"\[run\] creado run E2E: ([0-9a-f]{32})")
RE_RUN_PASS = re.compile(r"run_id E2E: ([0-9a-f]{32})")
RE_RUN_REUSE = re.compile(r"reutilizando run E2E: ([0-9a-f]{32})")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], label: str, mode: str | None = None) -> dict:
    """Ejecuta un eslabon de la cadena; captura texto para analisis/gates.

    stdout/stderr se reimprimen en vivo al terminar (los sub-procesos del
    engine no van por TTY). Los hijos heredan PYTHONUTF8=1: sus prints en
    UTF-8 no pisan la locale de la consola (cp1252) y el codificador que usa
    el padre los lee sin re-encoding. `mode` se propaga por env (ENGINE_MODE)
    porque `Settings` es frozen: mutarlo en el padre no alcanza — cada etapa
    relee load_settings() desde su propio env.
    """
    print(f"\n================  {label}  ================")
    print(f"  $ {' '.join(cmd)}")
    env = {**os.environ, "PYTHONUTF8": "1"}
    if mode:
        env["ENGINE_MODE"] = mode
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=3600, encoding="utf-8", errors="replace",
                              env=env)
    except subprocess.TimeoutExpired:
        print("  ERROR: timeout (>1h)")
        return {"exit_code": 124, "stdout": "", "stderr": "timeout"}
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR: no se pudo ejecutar ({e})")
        return {"exit_code": -1, "stdout": "", "stderr": str(e)}
    if proc.stdout:
        print("  -- stdout --")
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        print("  -- stderr --")
        sys.stdout.write(proc.stderr)
    print(f"  -> exit {proc.returncode}")
    return {"exit_code": proc.returncode, "stdout": proc.stdout,
            "stderr": proc.stderr}


def _extract_run_id(stdout: str, run_id_hint: str | None) -> str | None:
    """Extrae el run_id E2E del stdout del orquestador (o exige el hint)."""
    for rx in (RE_RUN_REUSE, RE_RUN_NEW, RE_RUN_PASS):
        m = rx.search(stdout or "")
        if m:
            return m.group(1)
    return run_id_hint


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_publisher_result(stdout: str) -> tuple[bool, str]:
    """Interpreta el JSON que pisa publisher.py (PublishResult.__dict__).

    El dict se imprime con indent=2, asi que `ok`/`reason`/`rows` estan en
    lineas propias. Devuelve (ok, detalle). Sin marcar "NOT_PUBLISHED" si no
    hay `"ok"` parseable desde la salida.
    """
    out = stdout or ""
    m_ok = re.search(r'"ok"\s*:\s*(true|false)', out)
    if not m_ok:
        return False, "salida no parseable"
    ok = m_ok.group(1) == "true"
    m_reason = re.search(r'"reason"\s*:\s*"([^"]*)"', out)
    m_rows = re.search(r'"rows"\s*:\s*(\d+)', out)
    detail = (m_reason.group(1) if m_reason else "?") \
        + ((" rows=" + m_rows.group(1)) if m_rows else "")
    return ok, detail


def try_lock(engine) -> tuple[bool, object]:
    """Advisory lock no bloqueante. Devuelve (ok, conn_a_retener)."""
    conn = engine.connect()
    try:
        got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"),
                           {"k": LOCK_KEY}).scalar()
    except Exception:
        conn.close()
        raise
    if not got:
        conn.close()
        return False, None
    return True, conn


def unlock(conn) -> None:
    if conn is None:
        return
    try:
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    except Exception:  # noqa: BLE001 — la sesion va a cerrar igual
        pass
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def bootstrap_role_login(settings) -> bool:
    """F-025: asigna LOGIN + password al rol de aplicacion via administrador.

    Migracion 011 creo `catalaxia_engine` NOLOGIN (la password se asigna
    aparte). Para que una base limpia arranque sin pasos manuales, este
    bootstrap corre SIEMPRE al inicio de la cadena por la via administrativa
    (misma que usa apply_migrations). Idempotente: re-altera la password con
    el valor de configuracion y deja habilitado el LOGIN que ya dejo la
    migracion 035. El secreto viaja por parametro, nunca por SQL texto ni
    logs.
    """
    if settings.db_user != "catalaxia_engine":
        return True
    admin = edb.get_admin_engine(settings)
    try:
        with admin.begin() as conn:
            conn.execute(
                text("ALTER ROLE catalaxia_engine WITH LOGIN PASSWORD :pwd"),
                {"pwd": settings.db_password},
            )
    except Exception as e:  # noqa: BLE001
        print(f"[bootstrap] no se pudo ajustar la password del rol: {e}")
        return False
    finally:
        admin.dispose()
    return True


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_e2e_certified", description=__doc__)
    ap.add_argument("--mode", default=None, help="FAST/FULL/AUDIT (def: settings)")
    ap.add_argument("--cik", default="0000904851",
                    help="CIK del emisor SEC (default YPF Golden Case)")
    ap.add_argument("--tickers", default="YPFD", help="tickers market (C10)")
    ap.add_argument("--scope", default="sec", choices=["sec", "market", "cross",
                                                       "cnv", "all"],
                    help="scope de C10 (default sec: invariantes SEC)")
    ap.add_argument("--run-id", default=None,
                    help="reutilizar un run E2E existente")
    ap.add_argument("--no-lock", action="store_true",
                    help="omitir advisory lock (tests/manual)")
    ap.add_argument("--no-ratios", action="store_true",
                    help="omitir ratio_engine de la cadena")
    ap.add_argument("--dry-run", action="store_true",
                    help="C12: dry-run (build+validate, sin swap)")
    ap.add_argument("--publish-source", default=None,
                    help="C12: schema.tabla origen (deferido por negocio)")
    ap.add_argument("--publish-target", default="engine_facts",
                    help="C12: nombre logico en staging")
    ap.add_argument("--publish-pk", default="fact_key",
                    help="C12: columnas PK separadas por coma")
    ap.add_argument("--json-out", default=None, help="directorio del report")
    args = ap.parse_args()

    json_out = Path(args.json_out or (REPO_ROOT / "outputs" / "e2e"))
    json_out.mkdir(parents=True, exist_ok=True)

    try:
        settings = load_settings()
    except RuntimeError as e:
        print(f"EXT-010: {e}")
        return 2

    if args.mode:
        settings = replace(settings, mode=args.mode)
    if settings.mode not in {"FAST", "FULL", "AUDIT"}:
        print(f"[error] mode invalido: {settings.mode}")
        return 2

    robj = args.run_id
    steps: list[dict] = []
    started = utc_now_iso()
    print(f"[config] target={settings.describe()} chain={PIPELINE_VERSION}")
    print(f"[lock]   key={LOCK_KEY} enabled={not args.no_lock}")

    # ── 0. Migraciones (F-025: via administrativa) ─────────────────────────
    try:
        applied = edb.apply_migrations(edb.get_admin_engine(settings),
                                       settings=settings)
        print(f"[migrations] aplicadas ahora: {applied or '(ninguna nueva)'}")
    except Exception as e:  # noqa: BLE001
        print(f"[error] no se pudieron aplicar migraciones: {e}")
        return 1

    # ── 0.25 Bootstrap del rol de aplicacion (F-025, base limpia) ──────────
    try:
        if not bootstrap_role_login(settings):
            return 1
        print("[bootstrap] rol de aplicacion con LOGIN/password lista")
    except Exception as e:  # noqa: BLE001
        print(f"[error] bootstrap del rol fallo: {e}")
        return 1

    # ── 0.5 Lock de corrida superpuesta (AC-4) ─────────────────────────────
    conn_lock = None
    if not args.no_lock:
        engine = edb.get_engine(settings)
        ok, conn_lock = try_lock(engine)
        if not ok:
            print("[lock] OCUPADO: otra instancia de la cadena esta corriendo. "
                  "Aborto (exit 3).")
            return 3
        print("[lock] adquirido")

    try:
        # ── 1. S00 → S04 (e2e_orchestrator) ────────────────────────────────
        # No se pasa --mode al orquestador: su `settings.mode = args.mode`
        # revienta con Settings frozen (Settings es dataclass frozen). El modo
        # viaja por ENGINE_MODE en el env y las etapas lo releen ellas mismas.
        cmd = [sys.executable, str(REPO_ROOT / "scripts" / "engine"
                                   / "e2e_orchestrator.py")]
        cmd += ["--cik", args.cik]
        if args.run_id:
            cmd += ["--run-id", args.run_id]
        r = _run(cmd, "S00→S04 · e2e_orchestrator", mode=settings.mode)
        steps.append({"step_id": "S00_S04", "script": "e2e_orchestrator.py",
                      "exit_code": r["exit_code"],
                      "ok": r["exit_code"] == 0})
        if r["exit_code"] != 0:
            return _finalize(steps, started, settings, json_out, errors="S00→S04 fallo")

        run_id = _extract_run_id(r["stdout"], args.run_id)
        if not run_id:
            print("[error] no se pudo determinar el run_id E2E del orquestador")
            return _finalize(steps, started, settings, json_out, errors="run_id no identifiable")
        print(f"[run] run_id E2E = {run_id}")

        # ── 2. ratio_engine (topologia ADR: S04 → ratio_engine → C10) ─────
        if not args.no_ratios:
            cmd = [sys.executable,
                   str(REPO_ROOT / "scripts" / "engine" / "ratio_engine.py"),
                   "--persist", "--cik", args.cik]
            r = _run(cmd, "ratio_engine · derivados", mode=settings.mode)
            steps.append({"step_id": "RATIO", "script": "ratio_engine.py",
                          "exit_code": r["exit_code"], "ok": r["exit_code"] == 0})
            if r["exit_code"] != 0:
                return _finalize(steps, started, settings, json_out,
                                 errors="ratio_engine fallo")
        else:
            steps.append({"step_id": "RATIO", "script": "ratio_engine.py",
                          "exit_code": 0, "ok": True, "skipped": True})

        # ── 3. C10 (validacion, solo lectura) ──────────────────────────────
        c10_path = json_out / f"c10_{run_id}.json"
        c10_scope = args.scope
        cmd = [sys.executable,
               str(REPO_ROOT / "scripts" / "engine" / "c10_evaluate.py"),
               "--sec-runs", run_id, "--ciks", args.cik,
               "--tickers", args.tickers, "--scope", c10_scope,
               "--json-out", str(c10_path)]
        r = _run(cmd, "C10 · validacion", mode=settings.mode)
        c10_veredicto = "NO_DETERMINABLE"
        if c10_path.exists():
            try:
                c10_veredicto = _read_json(c10_path).get("verdict", "NO_DETERMINABLE")
            except Exception:  # noqa: BLE001
                pass
        steps.append({"step_id": "C10", "script": "c10_evaluate.py",
                      "exit_code": r["exit_code"], "verdict": c10_veredicto,
                      "ok": (r["exit_code"] == 0
                             and c10_veredicto in ("PASS", "WARN"))})
        if c10_veredicto == "BLOCK" or c10_veredicto not in ("PASS", "WARN") \
                or r["exit_code"] != 0:
            return _finalize(steps, started, settings, json_out,
                             errors=f"C10 BLOCK ({c10_veredicto})")

        # ── 4. C11 (certificacion, invariantes R4) ─────────────────────────
        cmd = [sys.executable,
               str(REPO_ROOT / "scripts" / "engine" / "c11_certificar.py"),
               "--run-id", run_id, "--json-output", str(json_out)]
        r = _run(cmd, "C11 · certificacion", mode=settings.mode)
        c11_veredicto = "NO_DETERMINABLE"
        c11_acta = json_out / f"certificacion_c11_{run_id}.json"
        if c11_acta.exists():
            try:
                c11_veredicto = _read_json(c11_acta).get("veredicto",
                                                          "NO_DETERMINABLE")
            except Exception:  # noqa: BLE001
                pass
        steps.append({"step_id": "C11", "script": "c11_certificar.py",
                      "exit_code": r["exit_code"], "verdict": c11_veredicto,
                      "ok": c11_veredicto == "CERTIFICADA"})
        if c11_veredicto != "CERTIFICADA":
            return _finalize(steps, started, settings, json_out,
                             errors=f"C11 {c11_veredicto}")

        # ── 5. C12 (publisher → staging) ───────────────────────────────────
        publish_source = args.publish_source or os.environ.get(
            "ENGINE_PUBLISH_SOURCE", "").strip() or None
        if publish_source is None:
            print("[C12] SKIPPED: sin ENGINE_PUBLISH_SOURCE. La cadena "
                  "S00→C11 quedo verificada; la publicacion se habilita al "
                  "definir el destino por negocio (ADR: decision de "
                  "integracion, no resuelta).")
            steps.append({"step_id": "C12", "script": "publisher.py",
                          "exit_code": 0, "ok": True, "skipped": True})
            return _finalize(steps, started, settings, json_out, publish_skip=True)

        dry_run = args.dry_run or os.environ.get("ENGINE_PUBLISH_DRY_RUN", "1") == "1"
        target = args.publish_target or os.environ.get("ENGINE_PUBLISH_TARGET",
                                                       "engine_facts")
        pk = args.publish_pk or os.environ.get("ENGINE_PUBLISH_PK", "fact_key")
        filt = os.environ.get("ENGINE_PUBLISH_FILTER", "").strip()
        cmd = [sys.executable,
               str(REPO_ROOT / "scripts" / "engine" / "publisher.py"),
               "--source", publish_source, "--target", target,
               "--run-id", run_id, "--pk", pk]
        if filt:
            cmd += ["--filter", filt]
        elif dry_run is not None:  # filtro por run: solo el run de esta cadena
            cmd += ["--filter", f"WHERE run_id = '{run_id}'"]
        if dry_run:
            cmd += ["--dry-run"]
        r = _run(cmd, "C12 · publicacion (staging)", mode=settings.mode)
        ok_pub, detail = _parse_publisher_result(r["stdout"])
        steps.append({"step_id": "C12", "script": "publisher.py",
                      "exit_code": r["exit_code"], "ok": ok_pub, "detail": detail})
        if not ok_pub:
            return _finalize(steps, started, settings, json_out,
                             errors=f"C12 {detail}")

    finally:
        if not args.no_lock and conn_lock is not None:
            unlock(conn_lock)

    return _finalize(steps, started, settings, json_out)


def _finalize(steps: list[dict], started: str, settings, json_out: Path,
              errors: str | None = None, publish_skip: bool = False) -> int:
    """Escribe el report JSON y devuelve el exit code de la cadena."""
    finished = utc_now_iso()
    ok_all = (errors is None)
    status = "PASS" if ok_all else "BLOQUEADO"
    report = {
        "entrypoint": ENTRYPOINT,
        "pipeline_version": PIPELINE_VERSION,
        "target": settings.describe(),
        "started_at": started,
        "finished_at": finished,
        "status": status,
        "errors": errors,
        "publish_skipped": publish_skip,
        "steps": steps,
    }
    name = f"e2e_{report['started_at'][:19].replace(':', '')}.json"
    path = json_out / name
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print("\n================  RESUMEN  ================")
    for s in steps:
        estado = "OK" if s.get("ok") else ("SKIP" if s.get("skipped") else "FAIL")
        detalle = s.get("verdict") or s.get("detail") or ""
        print(f"  {s['step_id']:<6} {estado:<4} {s['script']:<22} {detalle}")
    print(f"  STATUS = {status}")
    if errors:
        print(f"  ERROR: {errors}")
    print(f"  REPORT: {path}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())