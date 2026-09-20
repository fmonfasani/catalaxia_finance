#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilidades comunes engine FX (AGENTE 02). Sin red aquí; sólo guardas + hashing + fechas.

- Sandbox: todo path de escritura debe vivir bajo research/fx_tikr_reverse/.
- RAW inmutable: write_raw_noreplace() jamás sobrescribe un archivo existente.
- Hash: sha256 sobre bytes crudos; se persiste en sidecar/meta, no se recalcula
  silenciosamente después.
"""
from __future__ import annotations

import hashlib
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]  # research/fx_tikr_reverse/
ENGINE_VERSION = "fx-engine@v1.0.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ENGINE_ROOT.parent.parent, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def assert_in_sandbox(p: Path | str) -> Path:
    """Falla cerrado si el path sale del sandbox. VERIFICADO POR TEST."""
    out = Path(p).resolve()
    root = ENGINE_ROOT.resolve()
    if out != root and root not in out.parents:
        raise SystemExit(f"REFUSADO: path fuera del sandbox ({out}); sólo {root}")
    return out


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def write_raw_noreplace(path: Path, content: bytes) -> dict:
    """Escribe RAW sólo si no existe. Si existe con distinto hash -> versiona.

    Retorna {action: CREATED|EXISTS_IDENTICAL|VERSIONED, sha256, path}.
    RAW inmutable: jamás UPDATE in place (REQ-FX-006 + reglas Catalaxia).
    """
    path = assert_in_sandbox(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    if path.exists():
        if sha256_file(path) == digest:
            return {"action": "EXISTS_IDENTICAL", "sha256": digest, "path": str(path)}
        alt = path.with_name(f"{path.stem}__retrieved-{utcnow_iso().replace(':','-')}{path.suffix}")
        alt.write_bytes(content)
        return {"action": "VERSIONED", "sha256": digest, "path": str(alt),
                "reason": "RAW existente con distinto contenido; no se sobrescribe"}
    path.write_bytes(content)
    return {"action": "CREATED", "sha256": digest, "path": str(path)}


def parse_iso_date(s: str) -> date:
    return date.fromisoformat(s)


def daterange(a: date, b: date):
    from datetime import timedelta
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)
