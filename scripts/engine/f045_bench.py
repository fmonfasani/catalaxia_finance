#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-045 — banco de ataque por SQL directo con el rol OPERATIVO.

No usa la capa de dominio. Ataca PostgreSQL con `catalaxia_engine`, que es el
rol que corre en produccion, y registra para cada ataque:

    SQL ejecutado · resultado · garantia que DEBERIA rechazarlo ·
    garantia que REALMENTE lo rechaza

"Rechazado" no alcanza: si lo rechaza otra barrera, el ataque no prueba nada.
Todo corre en una transaccion que se revierte siempre.

Uso:
    python scripts/engine/f045_bench.py            # reproduccion / verificacion
    python scripts/engine/f045_bench.py --json     # solo el JSON
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
from engine.db import get_engine  # noqa: E402

OUT = REPO / "outputs" / "docs" / "homologacion"

CIK_YPF = "0000904851"
CUIT_CEPU = "33650305499"
CUIT_LIBRE = "30999999995"      # valido por modulo 11, no usado por nadie
CIK_LIBRE = "0009999993"
OTRA = "E01M15GGGGGGGGGGGGGGGGGGGGG"  # segunda entidad, para A14
K = "E01M15DDDDDDDDDDDDDDDDDDDDD"   # entidad limpia: sin CIK y sin CUIT


def barrera(e) -> str:
    """Nombre EXACTO de lo que rechazo. Sin esto, un PASS no significa nada."""
    orig = getattr(e, "orig", None)
    diag = getattr(orig, "diag", None)
    if diag is not None:
        for attr in ("constraint_name",):
            v = getattr(diag, attr, None)
            if v:
                return v
        msg = (getattr(diag, "message_primary", "") or "")
        # los RAISE de plpgsql no traen constraint_name: se identifica la funcion
        # Nombre CANONICO de la garantia. Un ataque "rechazado" sin saber por
        # QUE no prueba nada: A9/A10 parecian fallar en la primera pasada solo
        # porque el matcher comparaba substrings sueltos.
        canon = [
            ("F-045: la assertion % no declara", "F045:left_ref_obligatorio"),
            ("no declara que identificador establece", "F045:left_ref_obligatorio"),
            ("tipo declarado distinto del real", "F045:left_ref_coincide"),
            ("La provenance no se presta", "F045:misma_entidad"),
            ("afirma sobre la entidad", "F045:misma_entidad"),
            ("no puede sostener el identificador", "F045:subject_type"),
            ("F-045: la fuente", "F045:fuente_autoritativa_para_el_tipo"),
            ("es autoritativa para", "fuente_autoritativa_para_el_tipo"),
            ("no puede establecer el identificador", "fuente_autoritativa_para_el_tipo"),
            ("no puede ser autoritativo", "tg_identifier_autoritativo"),
            ("los hechos afirmados son inmutables", "tg_assertion_inmutable"),
            ("esta en estado", "tg_identidad_exige_entidad_viva"),
            ("DELETE prohibido", "tg_no_borrar"),
        ]
        for aguja, nombre in canon:
            if aguja in msg:
                return nombre
        if msg:
            return f"RAISE:{msg[:60]}"
    return type(e).__name__


ATAQUES = [
    # (id, descripcion, garantia_esperada, sql_assertion, sql_identifier)
    ("A1", "LEGACY_DIM_ENTITY (CORROBORATING) establece CUIT, sin left_ref",
     "F045:left_ref_obligatorio",
     dict(source_id="LEGACY_DIM_ENTITY", left_ref=None, facts=None),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A2", "DERIVED_RULE (DISCOVERY_ONLY) establece CUIT, sin left_ref",
     "F045:left_ref_obligatorio",
     dict(source_id="DERIVED_RULE", left_ref=None, facts=None),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A3", "CNV_PORTAL (DISCOVERY_ONLY) establece CUIT, sin left_ref",
     "F045:left_ref_obligatorio",
     dict(source_id="CNV_PORTAL", left_ref=None, facts=None),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A4", "assertion SEC_20F que declara CIK, reutilizada para establecer CUIT",
     "F045:left_ref_coincide",
     dict(source_id="SEC_20F", left_ref=f"CIK:SEC:{CIK_LIBRE}",
          facts='{"accession": "0000000000-00-000000", "seccion": "Item 4.A"}'),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A5", "source_id correcto (GLEIF) pero left_ref NULL",
     "F045:left_ref_obligatorio",
     dict(source_id="GLEIF", left_ref=None,
          facts='{"registeredAt": "RA000009", "registeredAs": "x"}'),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A6", "left_ref apunta a un identificador de OTRO valor/namespace",
     "F045:left_ref_coincide",
     dict(source_id="GLEIF", left_ref="CUIT:AFIP:30546689979",
          facts='{"registeredAt": "RA000009", "registeredAs": "x"}'),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A9", "SEC_REGISTRY (autoritativa para CIK) intenta establecer CUIT",
     "fuente_autoritativa_para_el_tipo",
     dict(source_id="SEC_REGISTRY", left_ref=f"CUIT:AFIP:{CUIT_LIBRE}",
          facts='{"cik_str": 1}'),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A10", "GLEIF (autoritativa para LEI/CUIT) intenta establecer CIK",
     "fuente_autoritativa_para_el_tipo",
     dict(source_id="GLEIF", left_ref=f"CIK:SEC:{CIK_LIBRE}",
          facts='{"registeredAt": "RA000009"}'),
     dict(id_type="CIK", id_namespace="SEC", id_value=CIK_LIBRE)),

    ("A11", "el CUIT de CEPU atribuido a otra entidad (contaminacion)",
     "ux_identifier_autoritativo_unico",
     dict(source_id="GLEIF", left_ref=f"CUIT:AFIP:{CUIT_CEPU}",
          facts='{"registeredAt": "RA000009", "registeredAs": "x"}'),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_CEPU)),

    ("A12", "el CIK de YPF designando tambien a otra entidad",
     "ux_identifier_autoritativo_unico",
     dict(source_id="SEC_REGISTRY", left_ref=f"CIK:SEC:{CIK_YPF}",
          facts='{"cik_str": 904851}'),
     dict(id_type="CIK", id_namespace="SEC", id_value=CIK_YPF)),

    # -- variantes con left_ref POBLADO: prueban la politica de fuente, que es
    #    lo que A1/A2/A3 no alcanzaban a ejercitar (cortaban antes, en left_ref)
    ("A1b", "LEGACY_DIM_ENTITY establece CUIT, con left_ref correcto",
     "fuente_autoritativa_para_el_tipo",
     dict(source_id="LEGACY_DIM_ENTITY", left_ref=f"CUIT:AFIP:{CUIT_LIBRE}", facts=None),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A2b", "DERIVED_RULE establece CUIT, con left_ref correcto",
     "fuente_autoritativa_para_el_tipo",
     dict(source_id="DERIVED_RULE", left_ref=f"CUIT:AFIP:{CUIT_LIBRE}", facts=None),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A3b", "CNV_PORTAL establece CUIT, con left_ref correcto",
     "fuente_autoritativa_para_el_tipo",
     dict(source_id="CNV_PORTAL", left_ref=f"CUIT:AFIP:{CUIT_LIBRE}", facts=None),
     dict(id_type="CUIT", id_namespace="AFIP", id_value=CUIT_LIBRE)),

    ("A14", "la assertion de OTRA entidad usada para anclar la propia",
     "F045:misma_entidad",
     dict(source_id="SEC_REGISTRY", left_ref=f"CIK:SEC:{CIK_LIBRE}",
          facts='{"cik_str": 9999993}', entity_key="OTRA"),
     dict(id_type="CIK", id_namespace="SEC", id_value=CIK_LIBRE)),
]


def correr(conn, a):
    """Ejecuta un ataque. Devuelve el registro con SQL, resultado y barrera."""
    aid, desc, esperada, ass, ident = a
    sql_a = ("INSERT INTO identity_v1.assertion (subject_type, entity_key, left_ref, "
             "method, confidence, status, source_id, source_record, evidence, "
             "resolved_by, source_facts) VALUES ('ENTITY_IDENTIFIER', :k, :lr, "
             "'REGISTRY', 'AUTHORITATIVE', 'VERIFIED', :src, 'artefacto-ataque', "
             "'cita del ataque " + aid + "', 'proc:f045_bench', CAST(:f AS jsonb)) "
             "RETURNING assertion_id")
    sql_i = ("INSERT INTO identity_v1.identifier (entity_key, id_type, id_namespace, "
             "id_value, is_authoritative, status, assertion_id) "
             "VALUES (:k, :t, :ns, :v, TRUE, 'ACTIVE', :a)")
    reg = {"id": aid, "ataque": desc, "garantia_esperada": esperada,
           "sql": [sql_a, sql_i], "params": {**ass, **ident}}
    sp = conn.begin_nested()
    try:
        dueno = OTRA if ass.get("entity_key") == "OTRA" else K
        a_id = conn.execute(text(sql_a),
                            {"k": dueno, "lr": ass["left_ref"], "src": ass["source_id"],
                             "f": ass["facts"]}).scalar_one()
        conn.execute(text(sql_i), {"k": K, "t": ident["id_type"],
                                   "ns": ident["id_namespace"],
                                   "v": ident["id_value"], "a": a_id})
        sp.rollback()
        reg.update(resultado="ENTRO", garantia_real=None,
                   veredicto="BYPASS")
    except Exception as e:
        sp.rollback()
        b = barrera(e)
        reg.update(resultado="RECHAZADO", garantia_real=b,
                   mensaje=str(e).split("\n")[0][:150])
        reg["veredicto"] = "OK" if b == esperada else "RECHAZADO_POR_OTRA_BARRERA"
    return reg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_engine(s)        # ROL OPERATIVO, nunca admin
    regs = []

    with eng.connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(text(
                "INSERT INTO identity_v1.entity (entity_key, preferred_name, country, "
                "entity_status) VALUES (:k, 'Entidad limpia F-045', 'AR', 'ACTIVE')"),
                {"k": K})
            conn.execute(text(
                "INSERT INTO identity_v1.entity (entity_key, preferred_name, country, "
                "entity_status) VALUES (:k, 'Otra entidad F-045', 'US', 'ACTIVE')"),
                {"k": OTRA})
            if not args.json:
                print(f"F-045 · BANCO DE ATAQUE POR SQL DIRECTO")
                print(f"  rol: {s.describe()}")
                print(f"  entidad limpia: {K}  (sin CIK, sin CUIT)\n")
            for a in ATAQUES:
                r = correr(conn, a)
                regs.append(r)
                if not args.json:
                    marca = {"OK": "OK      ", "BYPASS": "BYPASS  ",
                             "RECHAZADO_POR_OTRA_BARRERA": "OTRA    "}[r["veredicto"]]
                    print(f"  {marca} {r['id']:<4} {r['ataque']}")
                    print(f"           esperada: {r['garantia_esperada']}")
                    print(f"           real    : {r.get('garantia_real') or 'NINGUNA (entro)'}")
        finally:
            tx.rollback()
            if not args.json:
                print("\n  (transaccion revertida: ninguna fila real modificada)")

    byp = [r for r in regs if r["veredicto"] == "BYPASS"]
    otra = [r for r in regs if r["veredicto"] == "RECHAZADO_POR_OTRA_BARRERA"]
    ok = [r for r in regs if r["veredicto"] == "OK"]
    if not args.json:
        print(f"\n  OK={len(ok)}  BYPASS={len(byp)}  RECHAZADO_POR_OTRA_BARRERA={len(otra)}")
        for r in byp:
            print(f"    BYPASS  {r['id']} {r['ataque']}")
        for r in otra:
            print(f"    OTRA    {r['id']} esperada={r['garantia_esperada']} "
                  f"real={r['garantia_real']}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "f045_bench.json").write_text(
        json.dumps({"rol": s.describe(), "total": len(regs), "ok": len(ok),
                    "bypass": len(byp), "otra_barrera": len(otra),
                    "ataques": regs}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    if args.json:
        print(json.dumps({"ok": len(ok), "bypass": len(byp), "otra": len(otra)}))
    else:
        print(f"  evidencia -> outputs/docs/homologacion/f045_bench.json")
    return 1 if (byp or otra) else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
