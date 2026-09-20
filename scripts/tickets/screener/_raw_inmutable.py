# -*- coding: utf-8 -*-
"""
R3 — RAW inmutable: archivar, nunca borrar
==========================================
RAW = data/raw/ es la verdad (filosofia P0-R3, principio 2). Regla absoluta:
ningun script borra un crudo. Cuando una nueva captura/version necesita
reemplazar el path principal de un RAW (p.ej. re-download por stale en
run_update.py), el archivo previo se MUDE a

    data/raw/_stale/<ts>/<razon>/<tipo>/<nombre>

conservando SHA256 y provenance en un sidecar JSON adyacente
(`<nombre>.meta.json`) y registrando la operacion en `ingesta_log`.

<tipo> es la capa que origina el crudo (companyfacts | submissions | ...):
evita colisiones de nombre entre capas (ambas usan CIK*/json).

Este modulo es el UNICO lugar que sabe archivar/restaurar un RAW. Quien
detecta la necesidad (run_update) llama a `archivar()`; no borra nada.

Contrato de archive (R3 — DEFINIR):
  - Operaciones prohibidas sobre data/raw/: unlink/os.remove/rmtree/truncate.
  - Operacion permitida para reemplazar un RAW: ARCHIVAR (mover a _stale con
    provenance) y luego escribir la version nueva en el path principal.
  - Retencion de _stale/ FUERA de esta ejecucion: no hay TTL (INV5).
  - Colision de nombre: nunca sobrescribe; agrega sufijo -1, -2...
  - Idempotencia: si el archivo no existe, archivar() es no-op (None).
  - Recuperacion: si la nueva captura falla, restaurar() copia de vuelta el
    RAW previo desde el archive (la copia archivada se conserva).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

STALE_DIR = "_stale"


def _ts():
    # timespec="seg" del contrato, pero sin ':' (invalido en rutas Windows).
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(":", "-")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def archivar(path, *, razon):
    """Mueve un archivo RAW a `_stale/<ts>/<razon>/` conservando el nombre.

    Idempotente: si `path` no existe (inedito o ya archivado) devuelve None.
    Colision: si el destino ya existe, agrega sufijo `-1`, `-2`, ... SIN
    sobrescribir. Nunca borra el archivo de origen: lo mueve.
    Devuelve dict de provenance (ver meta JSON junto al archivo archivado).
    """
    path = Path(path)
    if not path.is_file():
        return None
    raw_dir = path.parent.parent
    origen_rel = path.relative_to(raw_dir).as_posix()
    sha = sha256(path)
    size = path.stat().st_size
    ts = _ts()
    dst_dir = raw_dir / STALE_DIR / ts / razon / path.parent.name
    dst = dst_dir / path.name
    n = 1
    while dst.exists():                  # colision => nunca sobrescribir
        dst = dst_dir / f"{path.stem}-{n}{path.suffix}"
        n += 1
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dst))
    prov = {
        "evento": "archivado",
        "razon": razon,
        "nombre_original": path.name,
        "tipo": path.parent.name,       # companyfacts | submissions | ...
        "origen_rel": origen_rel,       # empresa/capa relativo a data/raw
        "raw_dir": str(raw_dir),
        "origen_abs": str(raw_dir / origen_rel),
        "ruta_archivado": str(dst),
        "sha256": sha,
        "bytes": size,
        "ts": ts,
    }
    dst.with_name(dst.name + ".meta.json").write_text(
        json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    return prov


def restaurar(prov):
    """Restaura un RAW archivado a su path principal.

    Copia (no mueve): la copia archivada sigue existiendo como evidencia.
    No sobrescribe si el path principal ya tiene la version nueva.
    Devuelve el path principal restaurado, o None si no hizo falta.
    """
    origen = Path(prov["origen_abs"])
    if origen.exists():
        return None
    origen.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prov["ruta_archivado"], origen)
    return origen


def registrar(con, cik, tipo, sha_previo, *, razon, evento="archivado", bytes_=None):
    """Registra el archivo/restauracion de un RAW en `ingesta_log` (sec_edgar).

    `hash` = sha256 del contenido preservado; `motivo` = R3:<evento>:<razon>.
    Append-only: una re-ejecucion agrega filas sin destruir las anteriores.
    Devuelve el id de fila o None si la tabla no esta disponible.
    """
    try:
        from _ingesta_log import crear
        crear(con)
    except Exception:
        return None
    try:
        cur = con.execute(
            """INSERT INTO ingesta_log
               (fuente, entidad, recurso, solicitado_at, respuesta, bytes,
                hash, sin_cambios, filas_nuevas, motivo)
               VALUES ('sec_edgar',?,?,?,NULL,?,?,0,NULL,?)""",
            (str(cik), tipo, _ts(), bytes_ or 0, sha_previo,
             f"R3:{evento}:{razon}"))
        con.commit()
        return cur.lastrowid
    except Exception:
        return None