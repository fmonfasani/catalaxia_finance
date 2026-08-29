#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-044 — banco adversario de la politica de autoridad.

Los 15 ataques del encargo, cada uno:
  * desde entidad limpia;
  * en transaccion reversible;
  * con la garantia EXACTA que lo rechaza identificada por nombre.

Se corre en dos estados del mundo:
  ESTADO 1  politica intacta        (rol catalaxia_engine)
  ESTADO 2  politica ADULTERADA     (adulterada por owner, escritura por engine)

Un ataque rechazado por otra barrera NO cuenta como prueba de F-044.

Uso:
    python scripts/engine/f044_bench.py
    python scripts/engine/f044_bench.py --json
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine, get_engine  # noqa: E402

OUT = REPO / "outputs" / "docs" / "homologacion"
K = "E01M15QQQQQQQQQQQQQQQQQQQQQ"
K2 = "E01M15RRRRRRRRRRRRRRRRRRRRR"
CUIT_L = "30999999995"
CIK_L, CIK_L2 = "0009999901", "0009999902"
LEI_L = "5493001KJTIIGC8Y1R12"
FACTS_G = '{"registeredAt": "RA000009", "registeredAs": "x"}'


def barrera(e) -> str:
    d = getattr(getattr(e, "orig", None), "diag", None)
    if d is None:
        return type(e).__name__
    if getattr(d, "constraint_name", None):
        return d.constraint_name
    m = getattr(d, "message_primary", "") or ""
    for a, n in (
        ("F-045: la assertion % no declara", "F045:left_ref_obligatorio"),
        ("no declara que identificador establece", "F045:left_ref_obligatorio"),
        ("tipo declarado distinto del real", "F045:left_ref_coincide"),
        ("La provenance no se presta", "F045:misma_entidad"),
        ("afirma sobre la entidad", "F045:misma_entidad"),
        ("F-045: la fuente", "F045:fuente_en_punto_de_uso"),
        ("no puede establecer el identificador", "tg_fuente_autoritativa_para_el_tipo"),
        ("es autoritativa para", "tg_fuente_autoritativa_para_el_tipo"),
        ("no puede ser autoritativo", "tg_identifier_autoritativo"),
        ("los hechos afirmados son inmutables", "tg_assertion_inmutable"),
        ("DELETE prohibido", "tg_no_borrar"),
        ("permission denied", "GRANT_de_columna"),
    ):
        if a in m:
            return n
    return f"RAISE:{m[:52]}"


# (id, descripcion, garantia_esperada, source_id, left_ref, tipo, ns, valor, facts, dueno_assertion)
ATAQUES = [
    ("T1", "fuente incorrecta -> CIK", "ck_politica_estructural_cik_lei",
     "LEGACY_DIM_ENTITY", f"CIK:SEC:{CIK_L}", "CIK", "SEC", CIK_L, '{"cik_str":1}', K),
    ("T2", "fuente incorrecta -> LEI", "ck_politica_estructural_cik_lei",
     "DERIVED_RULE", f"LEI:GLEIF:{LEI_L}", "LEI", "GLEIF", LEI_L, '{"lei":"x"}', K),
    ("T3", "fuente incorrecta -> CUIT", "ck_cuit_exige_evidencia_estructurada",
     "CNV_PORTAL", f"CUIT:AFIP:{CUIT_L}", "CUIT", "AFIP", CUIT_L, FACTS_G, K),
    ("T7", "left_ref NULL", "F045:left_ref_obligatorio",
     "SEC_REGISTRY", None, "CIK", "SEC", CIK_L, '{"cik_str":1}', K),
    ("T8", "left_ref con tipo incorrecto", "F045:left_ref_coincide",
     "SEC_REGISTRY", f"CIK:SEC:{CIK_L}", "CUIT", "AFIP", CUIT_L, '{"cik_str":1}', K),
    ("T9", "left_ref apuntando a otro identifier", "F045:left_ref_coincide",
     "SEC_REGISTRY", f"CIK:SEC:{CIK_L2}", "CIK", "SEC", CIK_L, '{"cik_str":1}', K),
    ("T10", "entity_key diferente", "F045:misma_entidad",
     "SEC_REGISTRY", f"CIK:SEC:{CIK_L}", "CIK", "SEC", CIK_L, '{"cik_str":1}', K2),
]


# Con politica INTACTA la primera barrera es el trigger; con politica
# ADULTERADA el trigger queda convencido y tiene que actuar el CHECK. Declarar
# una sola garantia esperada para ambos estados seria reportar una por otra.
ESPERADA_INTACTA = {"T1": "tg_fuente_autoritativa_para_el_tipo",
                    "T2": "tg_fuente_autoritativa_para_el_tipo",
                    "T3": "tg_fuente_autoritativa_para_el_tipo"}


def corre(conn, a, adulterada):
    aid, desc, esp, src, lr, tipo, ns, val, facts, dueno = a
    if not adulterada:
        esp = ESPERADA_INTACTA.get(aid, esp)
    sp = conn.begin_nested()
    try:
        n = conn.execute(text(
            "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,"
            "method,confidence,status,source_id,source_record,evidence,resolved_by,"
            "source_facts) VALUES ('ENTITY_IDENTIFIER',:k,:lr,'REGISTRY',"
            "'AUTHORITATIVE','VERIFIED',:s,'art','cita del ataque','proc:f044_bench',"
            "CAST(:f AS jsonb)) RETURNING assertion_id"),
            {"k": dueno, "lr": lr, "s": src, "f": facts}).scalar_one()
        conn.execute(text(
            "INSERT INTO identity_v1.identifier (entity_key,id_type,id_namespace,"
            "id_value,is_authoritative,status,assertion_id) "
            "VALUES (:k,:t,:n,:v,TRUE,'ACTIVE',:a)"),
            {"k": K, "t": tipo, "n": ns, "v": val, "a": n})
        sp.rollback()
        return {"id": aid, "ataque": desc, "politica": "adulterada" if adulterada
                else "intacta", "esperada": esp, "real": None,
                "resultado": "ENTRO", "veredicto": "BYPASS"}
    except Exception as e:
        sp.rollback()
        b = barrera(e)
        return {"id": aid, "ataque": desc, "politica": "adulterada" if adulterada
                else "intacta", "esperada": esp, "real": b,
                "resultado": "RECHAZADO",
                "veredicto": "OK" if b == esp else "OTRA_BARRERA"}


def por_update(conn):
    """T12 -- esquivar la garantia por UPDATE. T11 -- promover CANDIDATE."""
    r = []
    for aid, nom, sql in (
        ("T11", "CANDIDATE -> VERIFIED por UPDATE",
         "UPDATE identity_v1.assertion SET status='VERIFIED' WHERE status='CANDIDATE' "
         "AND assertion_id=(SELECT min(assertion_id) FROM identity_v1.assertion WHERE status='CANDIDATE')"),
        ("T11b", "promover identifier CANDIDATE a autoritativo",
         "UPDATE identity_v1.identifier SET is_authoritative=TRUE WHERE identifier_id="
         "(SELECT min(identifier_id) FROM identity_v1.identifier WHERE NOT is_authoritative AND valid_to IS NULL)"),
        ("T12", "cambiar source_id de una assertion VERIFIED",
         "UPDATE identity_v1.assertion SET source_id='LEGACY_DIM_ENTITY' WHERE assertion_id=1"),
        ("T12b", "cambiar left_ref para esquivar el CHECK",
         "UPDATE identity_v1.assertion SET left_ref='LEI:GLEIF:x' WHERE assertion_id=1"),
        ("T15", "borrar provenance",
         "DELETE FROM identity_v1.assertion WHERE assertion_id=1"),
    ):
        sp = conn.begin_nested()
        try:
            conn.execute(text(sql))
            sp.rollback()
            r.append({"id": aid, "ataque": nom, "resultado": "ENTRO",
                      "real": None, "veredicto": "BYPASS"})
        except Exception as e:
            sp.rollback()
            r.append({"id": aid, "ataque": nom, "resultado": "RECHAZADO",
                      "real": barrera(e), "veredicto": "OK"})
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    todos = []

    for adulterada in (False, True):
        # ESTADO 2 exige que el owner adultere la politica ANTES de que escriba
        # el rol operativo. Se hace en la MISMA transaccion, revertida.
        eng = get_admin_engine(s) if adulterada else get_engine(s)
        etiqueta = ("ESTADO 2: politica ADULTERADA (owner), escritura del mismo rol"
                    if adulterada else
                    "ESTADO 1: politica intacta, rol catalaxia_engine")
        if not args.json:
            print(f"\n{etiqueta}")
            print("  " + "-" * 88)
        with eng.connect() as conn:
            tx = conn.begin()
            try:
                if adulterada:
                    conn.execute(text(
                        "UPDATE identity_v1.source SET authority_level='AUTHORITATIVE', "
                        " authoritative_for=ARRAY['CIK','LEI','CUIT'] "
                        " WHERE source_id IN ('LEGACY_DIM_ENTITY','CNV_PORTAL','DERIVED_RULE')"))
                for k, n in ((K, "Limpia F044"), (K2, "Otra F044")):
                    conn.execute(text(
                        "INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                        "country,entity_status) VALUES (:k,:n,'AR','ACTIVE')"),
                        {"k": k, "n": n})
                for a in ATAQUES:
                    r = corre(conn, a, adulterada)
                    todos.append(r)
                    if not args.json:
                        marca = {"OK": "OK    ", "BYPASS": "BYPASS",
                                 "OTRA_BARRERA": "OTRA  "}[r["veredicto"]]
                        print(f"  {marca} {r['id']:<5} {r['ataque']:<38} "
                              f"<- {r['real'] or 'NINGUNA (entro)'}")
                if not adulterada:
                    for r in por_update(conn):
                        r["politica"] = "intacta"
                        todos.append(r)
                        if not args.json:
                            marca = "OK    " if r["veredicto"] == "OK" else "BYPASS"
                            print(f"  {marca} {r['id']:<5} {r['ataque']:<38} "
                                  f"<- {r['real'] or 'NINGUNA (entro)'}")
            finally:
                tx.rollback()

    byp = [r for r in todos if r["veredicto"] == "BYPASS"]
    otra = [r for r in todos if r["veredicto"] == "OTRA_BARRERA"]
    ok = [r for r in todos if r["veredicto"] == "OK"]
    if not args.json:
        print(f"\n  OK={len(ok)}  BYPASS={len(byp)}  OTRA_BARRERA={len(otra)}")
        for r in byp:
            print(f"    BYPASS  {r['id']} ({r['politica']}) {r['ataque']}")
        for r in otra:
            print(f"    OTRA    {r['id']} ({r['politica']}) esperada={r['esperada']} "
                  f"real={r['real']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f044_bench.json").write_text(
        json.dumps({"ok": len(ok), "bypass": len(byp), "otra": len(otra),
                    "ataques": todos}, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps({"ok": len(ok), "bypass": len(byp), "otra": len(otra)}))
    else:
        print("  evidencia -> outputs/docs/homologacion/f044_bench.json")
    return 1 if (byp or otra) else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
