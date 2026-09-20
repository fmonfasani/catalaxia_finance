#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoría INDEPENDIENTE del contrato de autoridad CNV — solo lectura.

No importa `c3_cnv_fetch`. Reconstruye la decisión de elegibilidad con SQL
propio, escrito desde el contrato, y la compara contra lo que el implementador
afirma. Habla con PostgreSQL por `psql`.

NO escribe. NO ejecuta fetch. NO crea bases.

Uso:
    python scripts/engine/cnv_auth_audit.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "fase_cnv"
CONT = "catalaxia-engine-dev"
FETCHER = REPO / "scripts" / "engine" / "c3_cnv_fetch.py"


def psql(q: str, intentos: int = 15) -> list[list[str]]:
    ultimo = ""
    for _ in range(intentos):
        try:
            p = subprocess.run(
                ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "catalaxia",
                 "-t", "-A", "-F", "\x1f", "-c", q],
                capture_output=True, text=True, encoding="utf-8", timeout=45)
        except subprocess.TimeoutExpired:
            ultimo = "timeout (base bloqueada)"
            time.sleep(12)
            continue
        if p.returncode == 0:
            return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]
        ultimo = (p.stderr or "")[:200]
        time.sleep(12)
    raise SystemExit(f"psql bloqueado: {ultimo}")


def uno(q):
    r = psql(q)
    return r[0][0] if r else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total, ev = [], True, {}

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'FALLA'} {n:<54} {det}")
        res.append({"control": n, "ok": bool(cond), "detalle": str(det)[:400]})
        if not cond:
            ok_total = False

    print("AUDITORIA INDEPENDIENTE — contrato de autoridad CNV\n")
    print("  psql directo · SQL propio · sin importar c3_cnv_fetch\n")

    # ═══ A · el codigo ya no decide por el estado de la assertion ═══
    print("A. el codigo")
    src = FETCHER.read_text(encoding="utf-8")
    chk("A1 · desaparecio max(a.status::text) de la elegibilidad",
        "max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)" not in src,
        "no aparece")
    for cond, etq in ((("AND i.is_authoritative"), "is_authoritative"),
                      (("AND i.status = 'ACTIVE'"), "status ACTIVE"),
                      (("AND i.valid_to IS NULL"), "valid_to vigente")):
        chk(f"A2 · la consulta filtra por {etq}", cond in src, "")
    chk("A3 · existen los motivos nuevos",
        "CUIT_NO_AUTORITATIVO" in src and '"AMBIGUO"' in src, "")

    # ═══ B · la decision, recalculada con SQL propio ═══
    print("\nB. elegibilidad recalculada de forma independiente")
    filas = psql("""
        WITH cuits AS (SELECT DISTINCT id_value FROM identity_v1.identifier
                        WHERE id_type='CUIT' AND valid_to IS NULL)
        SELECT c.id_value,
               (SELECT count(DISTINCT entity_key) FROM identity_v1.identifier
                 WHERE id_type='CUIT' AND id_value=c.id_value AND valid_to IS NULL),
               (SELECT count(*) FROM identity_v1.identifier
                 WHERE id_type='CUIT' AND id_value=c.id_value AND valid_to IS NULL
                   AND is_authoritative AND status='ACTIVE')
          FROM cuits c ORDER BY c.id_value""")
    elegibles, bloq_amb, bloq_auth = [], [], []
    for cuit, n_ent, n_auth in filas:
        if int(n_ent) > 1:
            bloq_amb.append(cuit)
        elif int(n_auth) == 1:
            elegibles.append(cuit)
        elif int(n_auth) > 1:
            bloq_amb.append(cuit)
        else:
            bloq_auth.append(cuit)
    print(f"  CUIT distintos vigentes        : {len(filas)}")
    print(f"  ELEGIBLES (1 autoritativo)     : {len(elegibles)}  {elegibles}")
    print(f"  bloqueados por AMBIGUO         : {len(bloq_amb)}  {bloq_amb}")
    print(f"  bloqueados por NO AUTORITATIVO : {len(bloq_auth)}")
    ev["elegibles"] = elegibles
    ev["bloqueados_ambiguo"] = bloq_amb
    ev["bloqueados_no_autoritativo"] = bloq_auth

    verif = [r[0] for r in psql("""
        SELECT DISTINCT i.id_value FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
         WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status='VERIFIED'
         ORDER BY 1""")]
    chk("B1 · los elegibles coinciden con los que tienen assertion VERIFIED",
        set(elegibles) == set(verif),
        f"elegibles={sorted(elegibles)} verificados={sorted(verif)}")
    chk("B2 · exactamente 3 elegibles", len(elegibles) == 3, f"{len(elegibles)}")

    # ═══ C · invariantes estructurales ═══
    print("\nC. invariantes")
    for etq, q in (
        ("C1 · VERIFIED sobre identificador NO autoritativo", """
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
             WHERE a.status='VERIFIED' AND NOT i.is_authoritative"""),
        ("C2 · autoritativo con assertion != VERIFIED", """
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
             WHERE i.is_authoritative AND a.status <> 'VERIFIED'"""),
        ("C3 · autoritativo vigente con status != ACTIVE", """
            SELECT count(*) FROM identity_v1.identifier
             WHERE is_authoritative AND valid_to IS NULL AND status <> 'ACTIVE'"""),
        ("C4 · >1 CUIT autoritativo vigente por entidad", """
            SELECT count(*) FROM (SELECT entity_key FROM identity_v1.identifier
             WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL
             GROUP BY entity_key HAVING count(*)>1) x"""),
    ):
        n = uno(q)
        chk(etq, n == "0", f"{n}")

    # ═══ D · atribucion de lo descargado ═══
    print("\nD. atribucion de los artefactos CNV")
    ajenos = uno("""
        SELECT count(*) FROM fetch_raw.cnv_artifact a
         WHERE NOT EXISTS (SELECT 1 FROM identity_v1.identifier i
                            WHERE i.id_type='CUIT' AND i.id_value=a.cuit
                              AND i.is_authoritative AND i.status='ACTIVE'
                              AND i.valid_to IS NULL)""")
    chk("D1 · todo artefacto pertenece a un CUIT hoy autoritativo", ajenos == "0",
        f"{ajenos} de CUIT no autoritativo")
    cuits_art = [r[0] for r in psql(
        "SELECT DISTINCT cuit FROM fetch_raw.cnv_artifact ORDER BY 1")]
    chk("D2 · los CUIT con artefactos son subconjunto de los elegibles",
        set(cuits_art) <= set(elegibles), f"{cuits_art}")
    sinprov = uno("""
        SELECT count(*) FROM fetch_raw.cnv_artifact
         WHERE sha256 IS NULL OR raw_path IS NULL OR cuit IS NULL
            OR entity_key IS NULL OR endpoint IS NULL""")
    chk("D3 · provenance completa en todos los artefactos", sinprov == "0", f"{sinprov}")
    huerf = uno("SELECT count(*) FROM engine.runs WHERE status='RUNNING'")
    chk("D4 · sin corridas RUNNING", huerf == "0", f"{huerf}")

    # ═══ E · Identity intacta ═══
    print("\nE. Identity no fue modificada por este ciclo")
    fp = uno("""
        SELECT (SELECT count(*) FROM identity_v1.entity)||'|'||
               (SELECT count(*) FROM identity_v1.identifier WHERE valid_to IS NULL)||'|'||
               (SELECT count(*) FROM identity_v1.assertion WHERE valid_to IS NULL)""")
    ev["fingerprint_identity"] = fp
    chk("E1 · huella de Identity (entities|identifiers|assertions)",
        fp == "525|574|608", fp)

    n_ok = sum(1 for r in res if r["ok"])
    print(f"\n  {n_ok}/{len(res)} controles OK")
    ev["controles"] = res
    ev["ok"] = ok_total
    (OUT / "CNV_AUTH_AUDIT.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_cnv/CNV_AUTH_AUDIT.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
