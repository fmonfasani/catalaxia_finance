#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE del backfill CIK (ciclo 8, fase H).

No importa `backfill_cik`. No usa sus funciones, sus conteos ni su reporte.
Reconstruye todo desde PostgreSQL, desde los artefactos primarios de SEC y
desde el sqlite legacy, y compara.

Uso:
    python scripts/engine/audit_backfill_cik.py
"""
from __future__ import annotations

import io
import json
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

OUT = REPO / "outputs" / "docs" / "fase_identity"


def sec_declara(cik: str) -> dict | None:
    """¿SEC declara este CIK? Se lee el artefacto, no la base."""
    p = REPO / "data" / "raw" / "submissions" / f"CIK{cik}.json"
    if p.exists():
        s = json.load(open(p, encoding="utf-8"))
        return {"via": "submissions", "name": s.get("name"), "tickers": s.get("tickers")}
    for f in sorted((REPO / "data" / "raw" / "catalogo_edgar").glob("company_tickers*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for e in (d.values() if isinstance(d, dict) else d):
            if str(e.get("cik_str", "")).zfill(10) == cik:
                return {"via": "company_tickers", "name": e.get("title"),
                        "tickers": [e.get("ticker")]}
    return None


def legacy() -> list[dict]:
    c = sqlite3.connect("file:" + str(REPO / "data" / "screener.db") + "?mode=ro", uri=True)
    filas = c.execute("SELECT entity_id, ticker_canonico, grupo, cuit, cik, nombre "
                      "FROM dim_entity").fetchall()
    c.close()
    return [dict(zip(("entity_id", "ticker", "grupo", "cuit", "cik", "nombre"), r))
            for r in filas]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = edb.get_engine(s)
    hallazgos, ctrl = [], {}

    def check(nombre, ok, detalle=""):
        ctrl[nombre] = {"ok": bool(ok), "detalle": str(detalle)}
        print(f"    {'OK     ' if ok else 'FALLA  '} {nombre:<44} {detalle}")
        if not ok:
            hallazgos.append(f"{nombre}: {detalle}")

    print(f"AUDITORIA INDEPENDIENTE · BACKFILL CIK · {s.describe()}\n")

    with eng.connect() as conn:
        # ---------- 1. CONTEOS reconstruidos, no leidos del reporte --------
        n_ent = conn.execute(text("SELECT count(*) FROM identity_v1.entity")).scalar()
        ciks = conn.execute(text(
            "SELECT id_value, entity_key FROM identity_v1.identifier "
            " WHERE id_type='CIK' AND id_namespace='SEC' AND is_authoritative "
            "   AND valid_to IS NULL")).all()
        print(f"  entidades={n_ent}   CIK autoritativos={len(ciks)}\n")
        print("  controles")

        # ---------- 2. DUPLICADOS -----------------------------------------
        dup_cik = [v for v, n in Counter(c[0] for c in ciks).items() if n > 1]
        check("ningun CIK designa dos entidades", not dup_cik, dup_cik[:5])
        dup_ent = [k for k, n in Counter(c[1] for c in ciks).items() if n > 1]
        check("ninguna entidad tiene dos CIK autoritativos", not dup_ent, dup_ent[:5])

        # ---------- 3. TODO CIK ESCRITO LO DECLARA SEC ---------------------
        muestra = random.Random(20260828).sample(ciks, min(40, len(ciks)))
        sin_sec = [c[0] for c in muestra if sec_declara(c[0]) is None]
        check("muestra aleatoria (40): SEC declara cada CIK", not sin_sec, sin_sec[:5])

        # ---------- 4. PROVENANCE ------------------------------------------
        incompletas = conn.execute(text("""
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a USING (assertion_id)
             WHERE i.is_authoritative AND i.valid_to IS NULL
               AND (a.source_id IS NULL OR a.source_record IS NULL
                    OR a.evidence IS NULL OR a.resolved_by IS NULL
                    OR a.status <> 'VERIFIED')""")).scalar()
        check("todo identificador autoritativo tiene provenance", incompletas == 0,
              f"{incompletas} incompletas")

        # El contrato obliga al BACKFILL a escribir evidencia estructurada.
        # Se mide lo que el backfill escribio, separado de lo preexistente:
        # mezclarlos hacia fallar el control por 7 filas de ciclos anteriores.
        sin_facts_bf = conn.execute(text("""
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a USING (assertion_id)
             WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL
               AND a.resolved_by LIKE 'proc:backfill_cik%'
               AND a.source_facts IS NULL""")).scalar()
        check("todo CIK escrito por el backfill trae evidencia estructurada",
              sin_facts_bf == 0, f"{sin_facts_bf} sin facts")

        previos = conn.execute(text("""
            SELECT a.resolved_by, count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a USING (assertion_id)
             WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL
               AND a.source_facts IS NULL GROUP BY 1""")).all()
        ctrl["cik_previos_sin_facts"] = {"ok": True, "detalle": str(previos)}
        if previos:
            print(f"    HALLAZGO {sum(n for _, n in previos)} CIK autoritativos de ciclos "
                  f"ANTERIORES sin source_facts: {previos}  -> F-041")

        # ---------- 5. AUTORIDAD -------------------------------------------
        no_aut = conn.execute(text("""
            SELECT DISTINCT a.source_id FROM identity_v1.identifier i
              JOIN identity_v1.assertion a USING (assertion_id)
              JOIN identity_v1.source src ON src.source_id = a.source_id
             WHERE i.is_authoritative AND i.valid_to IS NULL
               AND src.authority_level <> 'AUTHORITATIVE'""")).scalars().all()
        check("ninguna identidad autoritativa desde fuente no autoritativa",
              not no_aut, no_aut)

        fuera = conn.execute(text("""
            SELECT DISTINCT i.id_type, a.source_id FROM identity_v1.identifier i
              JOIN identity_v1.assertion a USING (assertion_id)
              JOIN identity_v1.source src ON src.source_id = a.source_id
             WHERE i.is_authoritative AND i.valid_to IS NULL
               AND NOT (i.id_type = ANY(COALESCE(src.authoritative_for, '{}')))""")).all()
        check("ninguna fuente estableció un tipo para el que no es autoritativa",
              not fuera, fuera[:5])

        # ---------- 6. EL BACKFILL NO CREO CUIT NI BRIDGES -----------------
        cuit_aut = conn.execute(text(
            "SELECT count(*) FROM identity_v1.identifier "
            " WHERE id_type='CUIT' AND is_authoritative AND valid_to IS NULL")).scalar()
        check("CUIT autoritativos siguen siendo los 3 ratificados", cuit_aut == 3,
              f"{cuit_aut}")

        cuit_backfill = conn.execute(text("""
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.assertion a USING (assertion_id)
             WHERE i.id_type='CUIT' AND i.is_authoritative AND i.valid_to IS NULL
               AND a.resolved_by LIKE 'proc:backfill_cik%'""")).scalar()
        check("el backfill no firmo ningun CUIT autoritativo", cuit_backfill == 0,
              f"{cuit_backfill}")

        br = conn.execute(text("""
            SELECT count(*) FROM identity_v1.assertion
             WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED'
               AND (method <> 'HUMAN_DECISION' OR resolved_by LIKE 'proc:%')""")).scalar()
        check("ningun bridge VERIFIED lo firmo un proceso", br == 0, f"{br}")

        # ---------- 7. FUSIONES INDEBIDAS ----------------------------------
        nombres = conn.execute(text("""
            SELECT lower(e.preferred_name), count(DISTINCT e.entity_key)
              FROM identity_v1.entity e GROUP BY 1 HAVING count(DISTINCT e.entity_key) > 1
             ORDER BY 2 DESC LIMIT 5""")).all()
        # dos entidades con el mismo nombre NO es un error: es lo correcto si
        # sus CIK difieren. El error seria lo contrario -- una sola entidad
        # para dos CIK, que ya se verifico arriba.
        ctrl["nombres_repetidos_ok"] = {"ok": True, "detalle": str(nombres[:3])}
        print(f"    nota    nombres repetidos (esperable): {len(nombres)}")

        # ---------- 8. INTEGRIDAD REFERENCIAL ------------------------------
        huerf = conn.execute(text(
            "SELECT count(*) FROM identity_v1.identifier i "
            " WHERE NOT EXISTS (SELECT 1 FROM identity_v1.entity e "
            "                    WHERE e.entity_key = i.entity_key)")).scalar()
        check("ningun identificador apunta a entidad inexistente", huerf == 0, f"{huerf}")

        muertas = conn.execute(text("""
            SELECT count(*) FROM identity_v1.identifier i
              JOIN identity_v1.entity e USING (entity_key)
             WHERE i.is_authoritative AND i.valid_to IS NULL
               AND e.entity_status IN ('MERGED','DISSOLVED')""")).scalar()
        check("ninguna entidad muerta tiene identidad autoritativa", muertas == 0,
              f"{muertas}")

        # ---------- 9. COBERTURA vs el LEGACY ------------------------------
        leg = legacy()
        esperados = set()
        for f in leg:
            v = str(f["cik"] or "").strip()
            if v.isdigit() and sec_declara(v.zfill(10)):
                esperados.add(v.zfill(10))
        en_db = {c[0] for c in ciks}
        faltan = esperados - en_db
        check("todo CIK legacy verificable quedo anclado", not faltan,
              f"faltan {len(faltan)}: {sorted(faltan)[:5]}")

        # ---------- 10. MUESTRA ADVERSARIAL --------------------------------
        print("\n  muestra adversarial")
        adversarios = {
            "0000034088": "EXXON -- CIK que el catalogo actual NO lista",
            "0000712515": "ELECTRONIC ARTS -- idem",
            "0001347426": "BMA -- su CIK venia en la columna `cuit` (F-024)",
            "0000904851": "YPF -- ya tenia CUIT ratificado antes del backfill",
            "0001717161": "CEPU -- idem",
        }
        for cik, por_que in adversarios.items():
            fila = conn.execute(text("""
                SELECT e.entity_key, e.preferred_name, a.resolved_by,
                       (SELECT count(*) FROM identity_v1.identifier x
                         WHERE x.entity_key=e.entity_key AND x.id_type='CUIT'
                           AND x.is_authoritative AND x.valid_to IS NULL) cuit
                  FROM identity_v1.identifier i
                  JOIN identity_v1.entity e USING (entity_key)
                  JOIN identity_v1.assertion a USING (assertion_id)
                 WHERE i.id_type='CIK' AND i.id_value=:c AND i.is_authoritative
                   AND i.valid_to IS NULL"""), {"c": cik}).mappings().first()
            estado = ("ANCLADO cuit={} por {}".format(fila["cuit"], fila["resolved_by"][:28])
                      if fila else "NO ANCLADO")
            print(f"    {cik}  {estado:<52} {por_que}")
            ctrl[f"adversarial_{cik}"] = {"ok": bool(fila), "detalle": estado}

        # ---------- 11. IDEMPOTENCIA -- corridas y crecimiento -------------
        corridas = conn.execute(text(
            "SELECT status, count(*) FROM engine.runs "
            " WHERE pipeline_version='identity-backfill-cik-v1' GROUP BY 1")).all()
        run_ok = dict(corridas).get("OK", 0)
        check("hay >=2 corridas OK del backfill (idempotencia real)", run_ok >= 2,
              str(dict(corridas)))
        check("cero corridas RUNNING en toda la base",
              conn.execute(text("SELECT count(*) FROM engine.runs "
                                "WHERE status='RUNNING'")).scalar() == 0)

        # una entidad por CIK: si N corridas duplicaran, esto crece
        sin_cik = conn.execute(text(
            "SELECT count(*) FROM identity_v1.entity e WHERE NOT EXISTS "
            "(SELECT 1 FROM identity_v1.identifier i WHERE i.entity_key=e.entity_key "
            "  AND i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL)")).scalar()
        check("entidades == CIK autoritativos + entidades sin CIK",
              n_ent == len(ciks) + sin_cik,
              f"{n_ent} = {len(ciks)} con CIK + {sin_cik} sin CIK")

    veredicto = "PASS" if not hallazgos else "BLOCKED"
    print(f"\n  VEREDICTO: {veredicto}")
    for h in hallazgos:
        print(f"    - {h}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit_backfill_cik.json").write_text(
        json.dumps({"veredicto": veredicto, "controles": ctrl, "hallazgos": hallazgos},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  evidencia -> outputs/docs/fase_identity/audit_backfill_cik.json")
    return 0 if veredicto == "PASS" else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
