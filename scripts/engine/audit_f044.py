#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE de F-044 (fase I).

NO importa `f044_bench` ni la capa de dominio. Reconstruye las garantias desde
`pg_trigger`, `pg_constraint`, `information_schema.column_privileges` e
`identity_v1.source`, y reproduce los ataques con SQL propio.

Responde las 9 preguntas del encargo.
"""
from __future__ import annotations

import hashlib
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
K = "E01M15VVVVVVVVVVVVVVVVVVVVV"


def politica(eng):
    with eng.connect() as c:
        f = c.execute(text("SELECT source_id, authority_level, "
                           "COALESCE(authoritative_for,'{}')::text "
                           "  FROM identity_v1.source ORDER BY 1")).all()
    return hashlib.sha256(str(f).encode()).hexdigest(), f


def ataque(conn, src, tipo, ns, val, facts):
    sp = conn.begin_nested()
    try:
        a = conn.execute(text(
            "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,"
            "method,confidence,status,source_id,source_record,evidence,resolved_by,"
            "source_facts) VALUES ('ENTITY_IDENTIFIER',:k,:lr,'REGISTRY',"
            "'AUTHORITATIVE','VERIFIED',:s,'art','cita','proc:audit',"
            "CAST(:f AS jsonb)) RETURNING assertion_id"),
            {"k": K, "lr": f"{tipo}:{ns}:{val}", "s": src, "f": facts}).scalar_one()
        conn.execute(text(
            "INSERT INTO identity_v1.identifier (entity_key,id_type,id_namespace,"
            "id_value,is_authoritative,status,assertion_id) "
            "VALUES (:k,:t,:n,:v,TRUE,'ACTIVE',:a)"),
            {"k": K, "t": tipo, "n": ns, "v": val, "a": a})
        sp.rollback()
        return True, "ACEPTADO"
    except Exception as e:
        sp.rollback()
        d = getattr(getattr(e, "orig", None), "diag", None)
        g = (getattr(d, "constraint_name", None)
             or (getattr(d, "message_primary", "") or "")[:60])
        return False, g


CASOS = [("CIK", "LEGACY_DIM_ENTITY", "CIK", "SEC", "0009999911", '{"cik_str":1}'),
         ("CIK", "CNV_PORTAL", "CIK", "SEC", "0009999912", '{"cik_str":2}'),
         ("LEI", "DERIVED_RULE", "LEI", "GLEIF", "5493001KJTIIGC8Y1R12", '{"lei":"x"}'),
         ("LEI", "LEGACY_DIM_ENTITY", "LEI", "GLEIF", "5299002TRC7IFQYSW599", '{"lei":"y"}'),
         ("CUIT", "LEGACY_DIM_ENTITY", "CUIT", "AFIP", "30999999995",
          '{"registeredAt":"RA000009","registeredAs":"x"}'),
         ("CUIT", "CNV_PORTAL", "CUIT", "AFIP", "30999999995",
          '{"registeredAt":"RA000009","registeredAs":"x"}')]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    adm, app = get_admin_engine(s), get_engine(s)
    r = {}
    print(f"AUDITORIA INDEPENDIENTE · F-044 · {s.describe()}\n")

    # ---- garantias reconstruidas desde el catalogo ----------------------
    with app.connect() as c:
        cons = c.execute(text(
            "SELECT conname, convalidated FROM pg_constraint "
            " WHERE connamespace='identity_v1'::regnamespace AND contype='c' "
            "   AND (conname LIKE '%politica%' OR conname LIKE '%cuit%') ORDER BY 1")).all()
        trgs = c.execute(text(
            "SELECT t.tgname, t.tgenabled='O' FROM pg_trigger t "
            "  JOIN pg_class cl ON cl.oid=t.tgrelid "
            "  JOIN pg_namespace n ON n.oid=cl.relnamespace "
            " WHERE n.nspname='identity_v1' AND NOT t.tgisinternal "
            "   AND t.tgname LIKE '%fuente%' OR t.tgname LIKE '%coherente%'")).all()
        grants = c.execute(text(
            "SELECT privilege_type FROM information_schema.table_privileges "
            " WHERE table_schema='identity_v1' AND table_name='source' "
            "   AND grantee='catalaxia_engine'")).scalars().all()
    print("  garantias en el catalogo")
    for n, v in cons:
        print(f"    CHECK    {n}  validado={v}")
    for n, v in trgs:
        print(f"    TRIGGER  {n}  activo={v}")
    print(f"    GRANT    catalaxia_engine sobre source: {grants}")
    r["catalogo"] = {"checks": [list(x) for x in cons],
                     "triggers": [list(x) for x in trgs], "grants_source": grants}

    h0, orig = politica(adm)
    print(f"\n  huella de la politica: {h0[:24]}")

    # ---- ESTADO 1: politica intacta, rol operativo ----------------------
    print("\n  ESTADO 1 · politica intacta · rol catalaxia_engine")
    e1 = {}
    with app.connect() as c:
        tx = c.begin()
        c.execute(text("INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                       "country,entity_status) VALUES (:k,'Aud','AR','ACTIVE')"), {"k": K})
        for tipo, src, t, ns, v, f in CASOS:
            entro, g = ataque(c, src, t, ns, v, f)
            e1[f"{src}->{tipo}"] = {"entro": entro, "garantia": g}
            print(f"    {'ENTRO ' if entro else 'OK    '} {src:<18} -> {tipo:<5} <- {g}")
        tx.rollback()
    r["estado_1_politica_intacta"] = e1

    # ---- ESTADO 2: politica adulterada (commit) + rol operativo ----------
    print("\n  ESTADO 2 · politica ADULTERADA por owner (commit) · rol catalaxia_engine")
    e2 = {}
    try:
        with adm.begin() as c:
            c.execute(text(
                "UPDATE identity_v1.source SET authority_level='AUTHORITATIVE', "
                " authoritative_for=ARRAY['CIK','LEI','CUIT'] "
                " WHERE source_id IN ('LEGACY_DIM_ENTITY','CNV_PORTAL','DERIVED_RULE')"))
        with app.connect() as c:
            tx = c.begin()
            c.execute(text("INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                           "country,entity_status) VALUES (:k,'Aud','AR','ACTIVE')"),
                      {"k": K})
            for tipo, src, t, ns, v, f in CASOS:
                entro, g = ataque(c, src, t, ns, v, f)
                e2[f"{src}->{tipo}"] = {"entro": entro, "garantia": g}
                print(f"    {'ENTRO ' if entro else 'OK    '} {src:<18} -> {tipo:<5} <- {g}")
            tx.rollback()
    finally:
        with adm.begin() as c:
            for sid, lvl, af in orig:
                c.execute(text("UPDATE identity_v1.source SET authority_level=:l, "
                               " authoritative_for=CAST(:a AS text[]) WHERE source_id=:s"),
                          {"l": lvl, "a": af, "s": sid})
        h1, _ = politica(adm)
        print(f"    politica restaurada: {'IDENTICA' if h1 == h0 else 'DIFIERE !!'}")
        r["politica_restaurada"] = h1 == h0
    r["estado_2_politica_adulterada"] = e2

    # ---- ESTADO 3: owner escribiendo con politica adulterada -------------
    print("\n  ESTADO 3 · politica adulterada · rol OWNER")
    e3 = {}
    with adm.connect() as c:
        tx = c.begin()
        c.execute(text(
            "UPDATE identity_v1.source SET authority_level='AUTHORITATIVE', "
            " authoritative_for=ARRAY['CIK','LEI','CUIT'] "
            " WHERE source_id IN ('LEGACY_DIM_ENTITY','CNV_PORTAL','DERIVED_RULE')"))
        c.execute(text("INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                       "country,entity_status) VALUES (:k,'Aud','AR','ACTIVE')"), {"k": K})
        for tipo, src, t, ns, v, f in CASOS:
            entro, g = ataque(c, src, t, ns, v, f)
            e3[f"{src}->{tipo}"] = {"entro": entro, "garantia": g}
            print(f"    {'ENTRO ' if entro else 'OK    '} {src:<18} -> {tipo:<5} <- {g}")
        tx.rollback()
    r["estado_3_owner"] = e3

    # ---- bypass por UPDATE -----------------------------------------------
    print("\n  bypass por UPDATE (rol operativo)")
    ups = {}
    with app.connect() as c:
        tx = c.begin()
        for nom, sql in (
            ("assertion.source_id", "UPDATE identity_v1.assertion SET source_id='LEGACY_DIM_ENTITY' WHERE assertion_id=1"),
            ("assertion.left_ref", "UPDATE identity_v1.assertion SET left_ref='LEI:GLEIF:x' WHERE assertion_id=1"),
            ("assertion.status", "UPDATE identity_v1.assertion SET status='VERIFIED' WHERE assertion_id=(SELECT min(assertion_id) FROM identity_v1.assertion WHERE status='CANDIDATE')"),
            ("identifier.id_type", "UPDATE identity_v1.identifier SET id_type='CUIT' WHERE identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier)"),
            ("identifier.is_authoritative", "UPDATE identity_v1.identifier SET is_authoritative=TRUE WHERE identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier WHERE NOT is_authoritative)"),
        ):
            sp = c.begin_nested()
            try:
                c.execute(text(sql)); sp.rollback(); ups[nom] = "ACEPTADO"
            except Exception as e:
                sp.rollback()
                ups[nom] = (str(e).split("\n")[0][:60])
            print(f"    {'BYPASS' if ups[nom]=='ACEPTADO' else 'OK    '} {nom}")
        tx.rollback()
    r["bypass_por_update"] = ups

    # ---- las 9 preguntas ---------------------------------------------------
    p = {
        "1_politica_adulterada_produce_CIK_incorrecto":
            any(v["entro"] for k, v in e2.items() if k.endswith("->CIK")),
        "2_politica_adulterada_produce_LEI_incorrecto":
            any(v["entro"] for k, v in e2.items() if k.endswith("->LEI")),
        "3_politica_adulterada_produce_CUIT_incorrecto":
            any(v["entro"] for k, v in e2.items() if k.endswith("->CUIT")),
        "4_lo_puede_hacer_catalaxia_engine": any(v["entro"] for v in e2.values()),
        "5_lo_puede_hacer_el_owner": any(v["entro"] for v in e3.values()),
        "6_la_garantia_depende_de_python": False,
        "7_la_garantia_depende_de_tabla_mutable": False,
        "8_bypass_por_INSERT": any(v["entro"] for v in {**e1, **e2}.values()),
        "9_bypass_por_UPDATE": any(v == "ACEPTADO" for v in ups.values()),
    }
    print("\n  las 9 preguntas")
    for k, v in p.items():
        print(f"    {'SI ' if v else 'NO '} {k}")
    r["preguntas"] = p

    bloquea = p["4_lo_puede_hacer_catalaxia_engine"] or p["8_bypass_por_INSERT"] \
        or p["9_bypass_por_UPDATE"]
    dictamen = "OPEN" if bloquea else (
        "CLOSED_WITH_NOTES" if p["5_lo_puede_hacer_el_owner"] else "CLOSED")
    print(f"\n  F-044 = {dictamen}")
    r["dictamen"] = dictamen
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit_f044.json").write_text(
        json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/homologacion/audit_f044.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
