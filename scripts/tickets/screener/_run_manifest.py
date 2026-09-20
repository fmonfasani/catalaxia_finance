# -*- coding: utf-8 -*-
"""
_run_manifest -- una ficha por corrida de run_all
=================================================
QUE RESUELVE
  Hasta hoy una corrida dejaba dos huellas desconectadas: el log de texto
  (data/logs/runall_*.log) y los cambios en la DB. Nada ataba "esta corrida"
  con "este estado del codigo" y "estos inputs". El contrato tecnico (G4) pide
  un run_manifest: version de codigo, argumentos, resultados por stage y hash
  de los inputs criticos, en un archivo chico y reutilizable.

QUE ESCRIBE
  data/logs/runs/<run_id>.manifest.json con:

    run_id         timestamp de inicio de la corrida (YYYYMMDD_HHMMSS)
    started/finished/duration_s
    git_sha        HEAD corto del repo al momento de correr (None si no hay git)
    python         version del interprete
    args           flags con que se invoco run_all
    results        (stage, status, segundos) por paso
    totales        n_ok / n_fail / n_skip
    db             tamano y mtime de screener.db al terminar
    snapshot_byma  sha256 de data/snapshot_byma.json (pre-run guard), si existe
    logfile        log de texto asociado

NO ES UN CHECKPOINT DE DATOS
  No copia datos ni reemplaza snapshots: es la etiqueta de la corrida. Si este
  modulo falla, run_all sigue (el manifiesto se pierde, no la corrida).
"""
from __future__ import annotations
import hashlib
import json
import platform
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path("data") / "logs" / "runs"


def _git_sha(root):
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=str(root), capture_output=True, text=True,
                           timeout=10)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except Exception:
        return None


def _sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def escribir(root, *, started_iso, finished_iso, duration_s, args, results,
             n_ok, n_fail, n_skip, logfile=None):
    """Escribe el manifest de la corrida. Devuelve el Path escrito."""
    root = Path(root)
    run_id = str(started_iso).replace("-", "").replace(":", "").replace("T", "_")
    out = root / RUNS_DIR
    out.mkdir(parents=True, exist_ok=True)

    db = root / "data" / "screener.db"
    # guard pre-run: snapshots baseline en data/backups/ (se toma el mas nuevo)
    backups = sorted((root / "data" / "backups").glob("snapshot_byma_baseline_*.json")) \
        if (root / "data" / "backups").exists() else []
    snap = backups[-1] if backups else None

    m = {
        "run_id": run_id,
        "started": started_iso,
        "finished": finished_iso,
        "duration_s": round(duration_s, 1),
        "git_sha": _git_sha(root),
        "python": platform.python_version(),
        "args": {k: (v if v is not None else False) for k, v in args.items()},
        "results": [list(r) for r in results],
        "totales": {"ok": n_ok, "fail": n_fail, "skip": n_skip},
        "db": ({"bytes": db.stat().st_size,
                "mtime": datetime.fromtimestamp(db.stat().st_mtime).isoformat(
                    timespec="seconds")} if db.exists() else None),
        "snapshot_byma": ({"file": snap.name, "sha256": _sha256_file(snap)}
                          if snap else None),
        "logfile": logfile,
    }
    p = out / f"{run_id}.manifest.json"
    p.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
