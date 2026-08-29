#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE de F-045 (fase H).

NO importa `f045_bench` ni la capa de dominio. Reconstruye las garantias desde
`pg_trigger`, `pg_constraint` y `information_schema.column_privileges`, y ataca
PostgreSQL con `catalaxia_engine` usando SQL propio.

Responde las 6 preguntas del encargo con evidencia, no con confianza.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_engine  # noqa: E402

OUT = REPO / "outputs" / "docs" / "homologacion"
EA = "E01M15HHHHHHHHHHHHHHHHHHHHH"
EB = "E01M15JJJJJJJJJJJJJJJJJJJJJ"
CUIT_L = "30999999995"
CIK_L = "0009999995"


def intenta(conn, sql, p=None):
    """Devuelve (entro, mensaje). Sin interpretar: el mensaje crudo."""
    sp = conn.begin_nested()
    try:
        r = conn.execute(text(sql), p or {})
        v = r.scalar() if r.returns_rows else None
        sp.rollback()
        return True, f"ACEPTADO (ret={v})"
    except Exception as e:
        sp.rollback()
        return False, str(e).split("\n")[0][:140]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_engine(s)     # rol operativo, no admin
    resp, hallazgos = {}, []

    print(f"AUDITORIA INDEPENDIENTE · F-045 · {s.describe()}\n")

    with eng.connect() as conn:
        # la lectura del catalogo hace autobegin: la transaccion se abre antes
        tx = conn.begin()
        # ---------- reconstruccion de las garantias desde el catalogo ------
        print("  garantias declaradas en el catalogo de PostgreSQL")
        trg = [r[0] for r in conn.execute(text(
            "SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            " JOIN pg_namespace n ON n.oid=c.relnamespace "
            " WHERE n.nspname='identity_v1' AND NOT t.tgisinternal "
            "   AND t.tgenabled='O' ORDER BY 1"))]
        for t in trg:
            print(f"    trigger  {t}")
        priv = conn.execute(text(
            "SELECT table_name, string_agg(column_name, ',' ORDER BY column_name) "
            "  FROM information_schema.column_privileges "
            " WHERE grantee='catalaxia_engine' AND table_schema='identity_v1' "
            "   AND privilege_type='UPDATE' AND table_name IN ('assertion','identifier') "
            " GROUP BY 1 ORDER BY 1")).all()
        for t, c in priv:
            print(f"    UPDATE   {t}: ({c})")
        resp["triggers_activos"] = trg
        resp["grants_update"] = {t: c for t, c in priv}

        try:
            for k, n in ((EA, "Auditoria A"), (EB, "Auditoria B")):
                conn.execute(text(
                    "INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                    "country,entity_status) VALUES (:k,:n,'AR','ACTIVE')"),
                    {"k": k, "n": n})

            def assertion(src, left_ref, dueno=EA, facts=None, status="VERIFIED",
                          method="REGISTRY"):
                sp = conn.begin_nested()
                try:
                    a = conn.execute(text(
                        "INSERT INTO identity_v1.assertion (subject_type,entity_key,"
                        "left_ref,method,confidence,status,source_id,source_record,"
                        "evidence,resolved_by,source_facts) VALUES "
                        "('ENTITY_IDENTIFIER',:k,:lr,:m,'AUTHORITATIVE',:st,:s,"
                        "'artefacto','cita de la auditoria','proc:audit_f045',"
                        "CAST(:f AS jsonb)) RETURNING assertion_id"),
                        {"k": dueno, "lr": left_ref, "s": src, "f": facts,
                         "st": status, "m": method}).scalar_one()
                    sp.commit()
                    return a, None
                except Exception as e:
                    sp.rollback()
                    return None, str(e).split("\n")[0][:140]

            def ancla(a_id, tipo, ns, val, dueno=EA):
                return intenta(conn,
                    "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                    "id_namespace,id_value,is_authoritative,status,assertion_id) "
                    "VALUES (:k,:t,:n,:v,TRUE,'ACTIVE',:a)",
                    {"k": dueno, "t": tipo, "n": ns, "v": val, "a": a_id})

            print("\n  las 6 preguntas\n")

            # 1 ---------------------------------------------------------
            caminos = []
            for src in ("LEGACY_DIM_ENTITY", "DERIVED_RULE", "CNV_PORTAL",
                        "SEC_REGISTRY", "GLEIF"):
                for lr in (None, f"CUIT:AFIP:{CUIT_L}"):
                    a, err = assertion(src, lr, facts=None)
                    if a is None:
                        caminos.append((src, lr, False, f"assertion: {err}"))
                        continue
                    entro, msg = ancla(a, "CUIT", "AFIP", CUIT_L)
                    caminos.append((src, lr, entro, msg))
            abiertos = [c for c in caminos if c[2]]
            resp["1_inventar_cuit"] = {"caminos_probados": len(caminos),
                                       "abiertos": len(abiertos),
                                       "detalle": [list(c) for c in caminos]}
            print(f"  1. ¿Puede inventar CUIT?            "
                  f"{'SI -- ' + str(len(abiertos)) + ' caminos' if abiertos else 'NO'}"
                  f"  ({len(caminos)} caminos probados)")
            if abiertos:
                hallazgos.append(f"inventar CUIT: {abiertos}")

            # 2 ---------------------------------------------------------
            a, err = assertion("SEC_20F", f"CIK:SEC:{CIK_L}",
                               facts='{"accession":"x","seccion":"Item 4.A"}')
            entro, msg = (ancla(a, "CUIT", "AFIP", CUIT_L) if a else (False, err))
            resp["2_cik_a_cuit"] = {"entro": entro, "mensaje": msg}
            print(f"  2. ¿Puede transformar CIK en CUIT?  {'SI' if entro else 'NO'}")
            print(f"       {msg[:118]}")
            if entro:
                hallazgos.append("transformar CIK en CUIT")

            # 3 ---------------------------------------------------------
            a, err = assertion("LEGACY_DIM_ENTITY", f"CIK:SEC:{CIK_L}")
            entro, msg = (ancla(a, "CIK", "SEC", CIK_L) if a else (False, err))
            resp["3_corroborating_establece"] = {"entro": entro, "mensaje": msg}
            print(f"  3. ¿CORROBORATING establece?        {'SI' if entro else 'NO'}")
            print(f"       {msg[:118]}")
            if entro:
                hallazgos.append("CORROBORATING establece identidad")

            # 4 ---------------------------------------------------------
            a, err = assertion("GLEIF", None,
                               facts='{"registeredAt":"RA000009","registeredAs":"x"}')
            entro, msg = (ancla(a, "CUIT", "AFIP", CUIT_L) if a else (False, err))
            resp["4_left_ref_null"] = {"entro": entro, "mensaje": msg}
            print(f"  4. ¿Puede omitir el tipo (NULL)?    {'SI' if entro else 'NO'}")
            print(f"       {msg[:118]}")
            if entro:
                hallazgos.append("omitir el tipo con left_ref NULL")

            # 5 ---------------------------------------------------------
            ups = {}
            for nom, sql in (
                ("identifier.id_type", "UPDATE identity_v1.identifier SET id_type='CUIT' WHERE identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier)"),
                ("identifier.id_value", "UPDATE identity_v1.identifier SET id_value='X' WHERE identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier)"),
                ("identifier.assertion_id", "UPDATE identity_v1.identifier SET assertion_id=1 WHERE identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier)"),
                ("identifier.is_authoritative", "UPDATE identity_v1.identifier SET is_authoritative=TRUE WHERE identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier WHERE NOT is_authoritative)"),
                ("assertion.left_ref", "UPDATE identity_v1.assertion SET left_ref='CUIT:AFIP:1' WHERE assertion_id=1"),
                ("assertion.source_id", "UPDATE identity_v1.assertion SET source_id='AFIP' WHERE assertion_id=1"),
            ):
                e, m = intenta(conn, sql)
                ups[nom] = {"entro": e, "mensaje": m}
            abiertos5 = [k for k, v in ups.items() if v["entro"]]
            resp["5_cambiar_tipo_por_update"] = ups
            print(f"  5. ¿Puede cambiar el tipo (UPDATE)? "
                  f"{'SI -- ' + str(abiertos5) if abiertos5 else 'NO'}")
            if abiertos5:
                hallazgos.append(f"cambiar tipo por UPDATE: {abiertos5}")

            # 6 ---------------------------------------------------------
            prom = {}
            a, err = assertion("GLEIF", f"CUIT:AFIP:{CUIT_L}", facts=None)
            prom["gleif_cuit_sin_facts"] = {"assertion": a is not None,
                                            "mensaje": err or "assertion creada"}
            if a:
                e, m = ancla(a, "CUIT", "AFIP", CUIT_L)
                prom["gleif_cuit_sin_facts"].update(entro=e, ancla=m)
            a2, err2 = assertion("SEC_REGISTRY", f"CIK:SEC:{CIK_L}",
                                 status="CANDIDATE")
            if a2:
                e2, m2 = ancla(a2, "CIK", "SEC", CIK_L)
                prom["candidate_como_autoritativo"] = {"entro": e2, "mensaje": m2}
            abiertos6 = [k for k, v in prom.items() if v.get("entro")]
            resp["6_promover_sin_evidencia"] = prom
            print(f"  6. ¿Puede promover sin evidencia?   "
                  f"{'SI -- ' + str(abiertos6) if abiertos6 else 'NO'}")
            for k, v in prom.items():
                print(f"       {k}: {str(v.get('ancla') or v.get('mensaje'))[:100]}")
            if abiertos6:
                hallazgos.append(f"promover sin evidencia: {abiertos6}")
        finally:
            tx.rollback()
            print("\n  (transaccion revertida)")

    veredicto = "CLOSED" if not hallazgos else "OPEN"
    print(f"\n  F-045 = {veredicto}")
    for h in hallazgos:
        print(f"    - {h}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit_f045.json").write_text(
        json.dumps({"veredicto": veredicto, "hallazgos": hallazgos,
                    "respuestas": resp}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print("  evidencia -> outputs/docs/homologacion/audit_f045.json")
    return 0 if not hallazgos else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
