#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HOMOLOGACION FINAL — adversarial (fase C) + mutacion (fase D).

AUDITORIA. No importa codigo de implementacion, no usa la capa de dominio, no
reutiliza los tests. Reconstruye las garantias desde el catalogo de PostgreSQL
y ataca con SQL propio.

Todo corre en transacciones revertidas -- incluido el DDL de las mutaciones, que
en PostgreSQL es transaccional.

Un ataque rechazado por una garantia distinta de la declarada NO cuenta.
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
from engine.db import get_admin_engine, get_engine  # noqa: E402

OUT = REPO / "outputs" / "docs" / "homologacion"
K, K2 = "E01M15WWWWWWWWWWWWWWWWWWWWW", "E01M15XXXXXXXXXXXXXXXXXXXXX"
CUIT_L, CIK_L, CIK_L2 = "30999999995", "0009999921", "0009999922"
LEI_L = "5493001KJTIIGC8Y1R12"
CUIT_CEPU, CIK_YPF = "33650305499", "0000904851"


def barrera(e) -> str:
    d = getattr(getattr(e, "orig", None), "diag", None)
    if d is None:
        return type(e).__name__
    if getattr(d, "constraint_name", None):
        return d.constraint_name
    m = getattr(d, "message_primary", "") or ""
    for a, n in (
        ("no declara que identificador establece", "tg_identifier_coherente(left_ref_obligatorio)"),
        ("tipo declarado distinto del real", "tg_identifier_coherente(left_ref_coincide)"),
        ("La provenance no se presta", "tg_identifier_coherente(misma_entidad)"),
        ("no puede sostener el identificador", "tg_identifier_coherente(subject_type)"),
        ("F-045: la fuente", "tg_identifier_coherente(fuente)"),
        ("no puede establecer el identificador", "tg_fuente_autoritativa_para_el_tipo"),
        ("es autoritativa para", "tg_fuente_autoritativa_para_el_tipo"),
        ("no puede ser autoritativo", "tg_identifier_autoritativo"),
        ("los hechos afirmados son inmutables", "tg_assertion_inmutable"),
        ("ya fue cerrada", "tg_assertion_inmutable(cierre)"),
        ("esta en estado", "tg_identidad_exige_entidad_viva"),
        ("sostiene", "tg_no_matar_entidad_con_identidad"),
        ("DELETE prohibido", "tg_no_borrar"),
        ("permission denied", "GRANT_de_columna"),
    ):
        if a in m:
            return n
    return f"RAISE:{m[:50]}"


def sembrar(c):
    for k, n in ((K, "Homolog A"), (K2, "Homolog B")):
        c.execute(text("INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                       "country,entity_status) VALUES (:k,:n,'AR','ACTIVE')"),
                  {"k": k, "n": n})


def ancla(c, src, tipo, ns, val, facts=None, left_ref="auto", dueno=None,
          status="VERIFIED", method="REGISTRY"):
    lr = f"{tipo}:{ns}:{val}" if left_ref == "auto" else left_ref
    a = c.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,method,"
        "confidence,status,source_id,source_record,evidence,resolved_by,source_facts) "
        "VALUES ('ENTITY_IDENTIFIER',:k,:lr,:m,'AUTHORITATIVE',:st,:s,'artefacto',"
        "'cita de la homologacion','proc:homolog',CAST(:f AS jsonb)) RETURNING assertion_id"),
        {"k": dueno or K, "lr": lr, "s": src, "f": facts, "st": status,
         "m": method}).scalar_one()
    c.execute(text(
        "INSERT INTO identity_v1.identifier (entity_key,id_type,id_namespace,id_value,"
        "is_authoritative,status,assertion_id) VALUES (:k,:t,:n,:v,TRUE,'ACTIVE',:a)"),
        {"k": K, "t": tipo, "n": ns, "v": val, "a": a})


# (id, descripcion, garantia_esperada, callable)
def ataques(c):
    G = "tg_fuente_autoritativa_para_el_tipo"
    CO = "tg_identifier_coherente"
    return [
        # ---- A. rol operativo -----------------------------------------
        ("A1", "inventar CIK desde fuente no autoritativa", G,
         lambda: ancla(c, "LEGACY_DIM_ENTITY", "CIK", "SEC", CIK_L, '{"x":1}')),
        ("A2", "inventar LEI desde fuente no autoritativa", G,
         lambda: ancla(c, "DERIVED_RULE", "LEI", "GLEIF", LEI_L, '{"x":1}')),
        ("A3", "inventar CUIT desde fuente no autoritativa", G,
         lambda: ancla(c, "CNV_PORTAL", "CUIT", "AFIP", CUIT_L,
                       '{"registeredAt":"RA000009","registeredAs":"x"}')),
        ("A4", "convertir CIK en CUIT (assertion de CIK usada para CUIT)",
         f"{CO}(left_ref_coincide)",
         lambda: ancla(c, "SEC_20F", "CUIT", "AFIP", CUIT_L,
                       '{"accession":"x","seccion":"Item 4.A"}',
                       left_ref=f"CIK:SEC:{CIK_L}")),
        ("A5", "CORROBORATING como autoridad (LEGACY -> CIK, left_ref ok)", G,
         lambda: ancla(c, "LEGACY_DIM_ENTITY", "CIK", "SEC", CIK_L2, '{"x":1}')),
        ("A6", "left_ref NULL", f"{CO}(left_ref_obligatorio)",
         lambda: ancla(c, "SEC_REGISTRY", "CIK", "SEC", CIK_L, '{"x":1}', left_ref=None)),
        ("A7", "left_ref apuntando a otro identificador", f"{CO}(left_ref_coincide)",
         lambda: ancla(c, "SEC_REGISTRY", "CIK", "SEC", CIK_L, '{"x":1}',
                       left_ref=f"CIK:SEC:{CIK_L2}")),
        ("A8", "assertion de otra entidad", f"{CO}(misma_entidad)",
         lambda: ancla(c, "SEC_REGISTRY", "CIK", "SEC", CIK_L, '{"x":1}', dueno=K2)),
        ("A9", "promover CANDIDATE a autoritativo", "tg_identifier_autoritativo",
         lambda: ancla(c, "SEC_REGISTRY", "CIK", "SEC", CIK_L, '{"x":1}',
                       status="CANDIDATE")),
        ("A10", "alterar source_id de assertion historica", "GRANT_de_columna",
         lambda: c.execute(text("UPDATE identity_v1.assertion SET source_id='AFIP' "
                                "WHERE assertion_id=1"))),
        ("A11", "alterar id_type de un identificador", "GRANT_de_columna",
         lambda: c.execute(text("UPDATE identity_v1.identifier SET id_type='CUIT' "
                                "WHERE identifier_id=(SELECT min(identifier_id) "
                                "FROM identity_v1.identifier)"))),
        ("A12", "alterar left_ref", "GRANT_de_columna",
         lambda: c.execute(text("UPDATE identity_v1.assertion SET left_ref='CUIT:AFIP:1' "
                                "WHERE assertion_id=1"))),
        ("A13", "modificar provenance (evidence)", "GRANT_de_columna",
         lambda: c.execute(text("UPDATE identity_v1.assertion SET evidence='otra' "
                                "WHERE assertion_id=1"))),
        ("A14", "borrar assertion historica", "GRANT_de_columna",
         lambda: c.execute(text("DELETE FROM identity_v1.assertion WHERE assertion_id=1"))),
        # ---- unicidad y contaminacion ----------------------------------
        ("A15", "el CUIT de CEPU sobre otra entidad", "ux_identifier_autoritativo_unico",
         lambda: ancla(c, "GLEIF", "CUIT", "AFIP", CUIT_CEPU,
                       '{"registeredAt":"RA000009","registeredAs":"x"}')),
        ("A16", "el CIK de YPF sobre otra entidad", "ux_identifier_autoritativo_unico",
         lambda: ancla(c, "SEC_REGISTRY", "CIK", "SEC", CIK_YPF, '{"x":1}')),
        # ---- C. lifecycle ----------------------------------------------
        ("C1", "entidad MERGED adquiriendo identidad", "tg_identidad_exige_entidad_viva",
         lambda: (c.execute(text(
             "INSERT INTO identity_v1.entity (entity_key,preferred_name,country,"
             "entity_status,merged_into_key) VALUES "
             "('E01M15YYYYYYYYYYYYYYYYYYYYY','Fusionada','US','MERGED',:o)"), {"o": K}),
             c.execute(text(
                 "INSERT INTO identity_v1.identifier (entity_key,id_type,id_namespace,"
                 "id_value,is_authoritative,status,assertion_id) SELECT "
                 "'E01M15YYYYYYYYYYYYYYYYYYYYY','CIK','SEC',:v,TRUE,'ACTIVE',"
                 "assertion_id FROM identity_v1.assertion WHERE status='VERIFIED' "
                 "AND left_ref='CIK:SEC:'||:v LIMIT 1"), {"v": CIK_YPF}))),
        ("C2", "matar una entidad que sostiene identidad",
         "tg_no_matar_entidad_con_identidad",
         lambda: c.execute(text(
             "UPDATE identity_v1.entity SET entity_status='DISSOLVED' WHERE entity_key="
             "(SELECT entity_key FROM identity_v1.identifier WHERE is_authoritative "
             " AND valid_to IS NULL LIMIT 1)"))),
        ("C3", "reabrir una assertion cerrada", "GRANT_de_columna",
         lambda: c.execute(text("UPDATE identity_v1.assertion SET valid_to=NULL, "
                                "status='VERIFIED' WHERE valid_to IS NOT NULL "
                                "AND assertion_id=(SELECT min(assertion_id) FROM "
                                "identity_v1.assertion WHERE valid_to IS NOT NULL)"))),
    ]


def correr(c, lista):
    r = []
    for aid, desc, esp, fn in lista:
        sp = c.begin_nested()
        try:
            fn()
            sp.rollback()
            r.append({"id": aid, "ataque": desc, "esperada": esp, "real": None,
                      "veredicto": "BYPASS"})
        except Exception as e:
            sp.rollback()
            b = barrera(e)
            r.append({"id": aid, "ataque": desc, "esperada": esp, "real": b,
                      "veredicto": "OK" if b.startswith(esp) or esp.startswith(b) or b == esp
                      else "OTRA_BARRERA"})
    return r


MUTACIONES = [
    ("tg_identifier_coherente_con_assertion (F-045)",
     "DROP TRIGGER tg_identifier_coherente_con_assertion ON identity_v1.identifier"),
    ("ck_politica_estructural_cik_lei (F-044)",
     "ALTER TABLE identity_v1.assertion DROP CONSTRAINT ck_politica_estructural_cik_lei"),
    ("ck_cuit_exige_evidencia_estructurada (F-036/037)",
     "ALTER TABLE identity_v1.assertion DROP CONSTRAINT ck_cuit_exige_evidencia_estructurada"),
    ("ux_identifier_autoritativo_unico (unicidad)",
     "DROP INDEX identity_v1.ux_identifier_autoritativo_unico"),
    ("tg_assertion_inmutable (inmutabilidad)",
     "DROP TRIGGER tg_assertion_inmutable ON identity_v1.assertion"),
    ("tg_identidad_exige_entidad_viva (lifecycle)",
     "DROP TRIGGER tg_identidad_exige_entidad_viva ON identity_v1.identifier"),
]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    app, adm = get_engine(s), get_admin_engine(s)
    doc = {}

    # ---------- FASE C ----------------------------------------------------
    print("FASE C · ADVERSARIAL FINAL · rol catalaxia_engine\n")
    with app.connect() as c:
        tx = c.begin()
        sembrar(c)
        base = correr(c, ataques(c))
        tx.rollback()
    for r in base:
        m = {"OK": "OK    ", "BYPASS": "BYPASS", "OTRA_BARRERA": "OTRA  "}[r["veredicto"]]
        print(f"  {m} {r['id']:<4} {r['ataque']:<52} <- {r['real'] or 'NINGUNA'}")
    doc["fase_C_engine"] = base

    # ---------- FASE C · owner -------------------------------------------
    print("\nFASE C · rol OWNER (con politica adulterada en la misma transaccion)")
    with adm.connect() as c:
        tx = c.begin()
        c.execute(text("UPDATE identity_v1.source SET authority_level='AUTHORITATIVE',"
                       " authoritative_for=ARRAY['CIK','LEI','CUIT'] WHERE source_id IN "
                       "('LEGACY_DIM_ENTITY','CNV_PORTAL','DERIVED_RULE')"))
        sembrar(c)
        owner = correr(c, [a for a in ataques(c) if a[0] in
                           ("A1", "A2", "A3", "A4", "A5", "A6")])
        tx.rollback()
    for r in owner:
        m = {"OK": "OK    ", "BYPASS": "BYPASS", "OTRA_BARRERA": "OTRA  "}[r["veredicto"]]
        print(f"  {m} {r['id']:<4} {r['ataque']:<52} <- {r['real'] or 'NINGUNA'}")
    doc["fase_C_owner_politica_adulterada"] = owner

    # ---------- FASE D ----------------------------------------------------
    print("\nFASE D · MUTACION (DDL transaccional, revertido)\n")
    mut = {}
    for nombre, ddl in MUTACIONES:
        with adm.connect() as c:
            tx = c.begin()
            try:
                c.execute(text(ddl))
                sembrar(c)
                r = correr(c, ataques(c))
                reaparecen = [x["id"] for x in r if x["veredicto"] == "BYPASS"]
                mut[nombre] = reaparecen
                print(f"  sin {nombre}")
                print(f"      reaparecen: {reaparecen or 'NINGUNO'}")
            finally:
                tx.rollback()
    doc["fase_D_mutaciones"] = mut

    byp = [r for r in base + owner if r["veredicto"] == "BYPASS"]
    otra = [r for r in base + owner if r["veredicto"] == "OTRA_BARRERA"]
    print(f"\n  ADVERSARIAL: OK={len(base+owner)-len(byp)-len(otra)} "
          f"BYPASS={len(byp)} OTRA_BARRERA={len(otra)}")
    for r in otra:
        print(f"    OTRA  {r['id']} esperada={r['esperada']} real={r['real']}")
    for r in byp:
        print(f"    BYPASS {r['id']} {r['ataque']}")
    sin_efecto = [n for n, v in mut.items() if not v]
    if sin_efecto:
        print(f"\n  ATENCION: mutaciones sin efecto (posible test vacio): {sin_efecto}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "homologacion_final.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n  evidencia -> outputs/docs/homologacion/homologacion_final.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
