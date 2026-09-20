#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FASE 7 — mutación causal de la barrera VERIFIED de CNV.

Un test que sólo observa «fue rechazado» no prueba POR QUÉ. Esta fase revierte
la condición exacta y exige que el rechazo desaparezca.

POR QUE NO HACE FALTA UNA COPIA DE LA BASE
La barrera vive en `resolver_en_identity_v1()`, una función de LECTURA que
devuelve un veredicto. Mutarla y volver a preguntar no escribe nada: ni corrida,
ni fila, ni request HTTP. La copia descartable sería necesaria si la mutación
dejara correr el fetch, y aquí se corta antes a propósito.

La mutación se aplica a una COPIA del script. El original no se toca; se
verifica su hash antes y después.

Uso:
    python scripts/engine/cnv_negative_mutacion.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "outputs" / "docs" / "fase_cnv"
ORIG = REPO / "scripts" / "engine" / "c3_cnv_fetch.py"
MUT = REPO / "scripts" / "engine" / "_c3_mutado_tmp.py"

# La condición EXACTA que se revierte. Si este texto ya no está en el archivo,
# la mutación no se construye y la fase falla en vez de fingir.
CONDICION = '''    if r["cuit_status"] != "VERIFIED":
        return {"ok": False, "motivo": "CUIT_NO_VERIFICADO", **r,'''
NEUTRALIZADA = '''    if False:   # MUTACION: barrera VERIFIED desactivada
        return {"ok": False, "motivo": "CUIT_NO_VERIFICADO", **r,'''

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402


def cargar(path: Path, nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sha_antes = hashlib.sha256(ORIG.read_bytes()).hexdigest()
    src = ORIG.read_text(encoding="utf-8")
    res, ok_total = [], True

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {n:<50} {det}")
        res.append({"control": n, "ok": bool(cond), "detalle": str(det)[:300]})
        if not cond:
            ok_total = False

    print("FASE 7 — MUTACION CAUSAL DE LA BARRERA VERIFIED\n")
    print(f"  c3_cnv_fetch.py sha256 antes: {sha_antes[:16]}…")

    if CONDICION not in src:
        chk("M0 · se pudo construir la mutacion", False,
            "la condicion `cuit_status != VERIFIED` ya no esta en el codigo")
        return 1
    chk("M0 · se pudo construir la mutacion", True, "condicion localizada")

    eng = get_admin_engine(load_settings())

    # el caso de prueba: un CANDIDATE real, elegido por clave opaca
    with eng.connect() as c:
        from sqlalchemy import text
        fila = c.execute(text("""
            SELECT i.id_value, a.status::text, e.preferred_name
              FROM identity_v1.identifier i
              JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
              JOIN identity_v1.entity e ON e.entity_key=i.entity_key
             WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status <> 'VERIFIED'
             ORDER BY e.entity_key LIMIT 1""")).one()
    cuit, estado, nombre = fila
    print(f"  caso: {nombre[:40]} · CUIT {cuit} · estado {estado}\n")

    # ── control: con el codigo REAL ──
    real = cargar(ORIG, "c3_real")
    r0 = real.resolver_en_identity_v1(eng, cuit, None)
    chk("M1 · con el codigo real, el CANDIDATE es RECHAZADO",
        r0["ok"] is False and r0["motivo"] == "CUIT_NO_VERIFICADO",
        f"ok={r0['ok']} motivo={r0['motivo']}")

    bloqueo_real = True
    try:
        real.load_identity(eng, cuit=cuit)
        bloqueo_real = False
    except SystemExit as e:
        msj_real = str(e)[:120]
    chk("M2 · load_identity() corta con SystemExit", bloqueo_real,
        msj_real if bloqueo_real else "NO corto")

    # ── mutacion: se desactiva SOLO esa condicion ──
    MUT.write_text(src.replace(CONDICION, NEUTRALIZADA, 1), encoding="utf-8")
    mut = cargar(MUT, "c3_mutado")
    r1 = mut.resolver_en_identity_v1(eng, cuit, None)
    chk("M3 · revertida la barrera, el MISMO caso pasa a ACEPTADO",
        r1["ok"] is True and r1["motivo"] == "VERIFIED",
        f"ok={r1['ok']} motivo={r1['motivo']} cuit={r1.get('cuit')}")

    paso = False
    try:
        ident = mut.load_identity(eng, cuit=cuit)
        paso = True
    except SystemExit as e:
        ident = {"error": str(e)[:120]}
    chk("M4 · con la barrera revertida, load_identity() YA NO corta", paso,
        f"binding={ident.get('binding')} entity_key={ident.get('entity_key')}"
        if paso else str(ident))

    # ── la causa es el estado, no la empresa ──
    chk("M5 · el estado de la assertion es lo unico que cambio",
        r0["cuit"] == r1["cuit"] and r0["entity_key"] == r1["entity_key"]
        and r0["cuit_status"] == r1["cuit_status"] == estado,
        f"misma entidad, mismo CUIT, mismo status={estado}; sólo cambió si se exige")

    # ── restaurar ──
    MUT.unlink(missing_ok=True)
    sha_despues = hashlib.sha256(ORIG.read_bytes()).hexdigest()
    chk("M6 · el script original quedo intacto", sha_antes == sha_despues,
        f"{sha_antes[:16]}… == {sha_despues[:16]}…")
    chk("M7 · la copia mutada fue eliminada", not MUT.exists(), str(MUT.name))

    n = sum(1 for r in res if r["ok"])
    print(f"\n  {n}/{len(res)} controles OK")
    (OUT / "CNV_NEGATIVE_PILOT_20_MUTACION.json").write_text(json.dumps(
        {"ok": ok_total, "caso": {"cuit": cuit, "estado": estado, "empresa": nombre},
         "con_codigo_real": {"ok": r0["ok"], "motivo": r0["motivo"]},
         "con_barrera_revertida": {"ok": r1["ok"], "motivo": r1["motivo"]},
         "sha_original_antes": sha_antes, "sha_original_despues": sha_despues,
         "controles": res}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_cnv/CNV_NEGATIVE_PILOT_20_MUTACION.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
