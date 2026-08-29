#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HOMOLOGACION — las 7 rutas que ninguna ejecucion debe poder tomar.

AUDITORIA, no implementacion. No importa la logica del implementador para
decidir: ataca la BASE directamente y mira que responde.

TODO corre dentro de UNA transaccion que se revierte SIEMPRE. Ninguna fila
real se modifica. Es una prueba mutacional acotada, documentada aca y en
SYSTEM_HOMOLOGATION_REPORT.md.

Cada ataque debe ser rechazado POR LA GARANTIA QUE DECLARA. Un rechazo por
sintaxis, tipo o fixture no cuenta: se reporta como ERROR_DE_PRUEBA.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DataError, IntegrityError, InternalError  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

RECHAZO_REAL = (IntegrityError, InternalError, DataError)
OUT = REPO / "outputs" / "docs" / "homologacion"

CUIT_CEPU = "33650305499"
CIK_YPF, CIK_CEPU = "0000904851", "0001717161"


def ev(conn, entity_key, source_id="SEC_REGISTRY", facts='{"cik_str": 1}'):
    """Una assertion VERIFIED valida y propia. Sin esto los ataques mueren antes."""
    return conn.execute(text(
        "INSERT INTO identity_v1.assertion (subject_type, entity_key, method, "
        " confidence, status, source_id, source_record, evidence, resolved_by, "
        " source_facts) VALUES ('ENTITY_IDENTIFIER', :k,'REGISTRY','AUTHORITATIVE',"
        " 'VERIFIED', :s ,'artefacto-de-prueba','cita de la auditoria','proc:homologacion',"
        " CAST(:f AS jsonb)) RETURNING assertion_id"),
        {"k": entity_key, "s": source_id, "f": facts}).scalar_one()


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_admin_engine(s)   # el rol MAS privilegiado: si aca no entra, no entra
    res = []

    def ataque(n, nombre, fn, garantia=None):
        sp = conn.begin_nested()
        try:
            fn()
            sp.rollback()
            estado, det = "ENTRO", "la base ACEPTO la escritura"
        except RECHAZO_REAL as e:
            sp.rollback()
            m = str(e).split("\n")[0]
            if garantia and garantia not in str(e):
                estado, det = "RECHAZADO_POR_OTRA_COSA", m[:150]
            else:
                estado, det = "RECHAZADO", m[:130]
        except Exception as e:
            sp.rollback()
            estado, det = "ERROR_DE_PRUEBA", f"{type(e).__name__}: {str(e)[:120]}"
        marca = {"RECHAZADO": "OK    ", "ENTRO": "BLOCK ",
                 "RECHAZADO_POR_OTRA_COSA": "NOTA  ", "ERROR_DE_PRUEBA": "ERROR "}[estado]
        print(f"  {marca} {n}. {nombre}")
        print(f"           {det}")
        res.append({"n": n, "ataque": nombre, "resultado": estado, "detalle": det})

    print(f"HOMOLOGACION · RUTAS PROHIBIDAS · {s.describe()}")
    print("  (prueba mutacional sobre transaccion revertida; rol admin)\n")

    with eng.connect() as conn:
        tx = conn.begin()
        try:
            ypf = conn.execute(text(
                "SELECT entity_key FROM identity_v1.identifier WHERE id_type='CIK' "
                " AND id_value=:c AND is_authoritative AND valid_to IS NULL"),
                {"c": CIK_YPF}).scalar()
            cepu = conn.execute(text(
                "SELECT entity_key FROM identity_v1.identifier WHERE id_type='CIK' "
                " AND id_value=:c AND is_authoritative AND valid_to IS NULL"),
                {"c": CIK_CEPU}).scalar()
            print(f"  objetivos reales: YPF={ypf}  CEPU={cepu}\n")

            # ---- 1. INVENTAR UN CUIT ------------------------------------
            ataque(1, "inventar un CUIT sin fuente autoritativa (DERIVED_RULE)",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CUIT','AFIP','30111111118',TRUE,'ACTIVE',:a)"),
                       {"k": ypf, "a": ev(conn, ypf, "DERIVED_RULE")}))

            ataque("1b", "inventar un CUIT desde LEGACY_DIM_ENTITY (CORROBORATING)",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CUIT','AFIP','30222222229',TRUE,'ACTIVE',:a)"),
                       {"k": ypf, "a": ev(conn, ypf, "LEGACY_DIM_ENTITY")}))

            ataque("1c", "CUIT autoritativo SIN evidencia estructurada",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CUIT','AFIP','30333333330',TRUE,'ACTIVE',:a)"),
                       {"k": cepu, "a": conn.execute(text(
                           "INSERT INTO identity_v1.assertion (subject_type,entity_key,"
                           "method,confidence,status,source_id,source_record,evidence,"
                           "resolved_by) VALUES ('ENTITY_IDENTIFIER',:k,'REGISTRY',"
                           "'AUTHORITATIVE','VERIFIED','GLEIF','g','cita','proc:h') "
                           "RETURNING assertion_id"), {"k": cepu}).scalar_one()}))

            # ---- 2. CONVERTIR UN CIK EN CUIT -----------------------------
            ataque(2, "declarar el CIK de BMA como si fuera un CUIT (F-024)",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CUIT','AFIP','0001347426',TRUE,'ACTIVE',:a)"),
                       {"k": cepu, "a": ev(conn, cepu, "GLEIF")}))

            # ---- 3. CORROBORATING -> AUTHORITATIVE -----------------------
            ataque(3, "elevar LEGACY_DIM_ENTITY a fuente AUTHORITATIVE",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.source SET authority_level='AUTHORITATIVE', "
                       " authoritative_for=ARRAY['CUIT'] WHERE source_id='LEGACY_DIM_ENTITY'")))

            ataque("3b", "promover a autoritativo un identificador CANDIDATE existente",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.identifier SET is_authoritative=TRUE "
                       " WHERE id_type='CUIT' AND NOT is_authoritative AND valid_to IS NULL "
                       " AND identifier_id=(SELECT min(identifier_id) FROM identity_v1.identifier "
                       "   WHERE id_type='CUIT' AND NOT is_authoritative AND valid_to IS NULL)")))

            # ---- 4. FUSIONAR SIN IDENTIFICADOR AUTORITATIVO --------------
            ataque(4, "fusionar (MERGED) una entidad que tiene identidad autoritativa",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.entity SET entity_status='MERGED', "
                       " merged_into_key=:o WHERE entity_key=:k"), {"k": ypf, "o": cepu}))

            ataque("4b", "dar identidad autoritativa a una entidad DISSOLVED",
                   lambda: (
                       conn.execute(text(
                           "INSERT INTO identity_v1.entity (entity_key,preferred_name,"
                           "country,entity_status) VALUES "
                           "('E01M15AAAAAAAAAAAAAAAAAAAAA','Difunta','US','DISSOLVED')"),),
                       conn.execute(text(
                           "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                           "id_namespace,id_value,is_authoritative,status,assertion_id) "
                           "VALUES ('E01M15AAAAAAAAAAAAAAAAAAAAA','CIK','SEC','0009999991',"
                           "TRUE,'ACTIVE',:a)"),
                           {"a": ev(conn, "E01M15AAAAAAAAAAAAAAAAAAAAA")})))

            # ---- 5. DUPLICAR AL REEJECUTAR -------------------------------
            ataque(5, "el mismo CIK autoritativo designando DOS entidades",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CIK','SEC',:v,TRUE,'ACTIVE',:a)"),
                       {"k": cepu, "v": CIK_YPF, "a": ev(conn, cepu)}),
                   garantia="ux_identifier_autoritativo_unico")

            ataque("5b", "una entidad con DOS CIK autoritativos vigentes",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CIK','SEC','0009999992',TRUE,'ACTIVE',:a)"),
                       {"k": ypf, "a": ev(conn, ypf)}),
                   garantia="ux_entity_un_autoritativo_por_tipo")

            # ---- 6. MODIFICAR PROVENANCE HISTORICA ----------------------
            ataque(6, "editar `evidence` de una assertion historica",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.assertion SET evidence='reescrita' "
                       " WHERE assertion_id=1")),
                   garantia="inmutables")

            ataque("6b", "F-042: mutar `source_facts` de una assertion historica",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.assertion SET source_facts=CAST(:f AS jsonb) "
                       " WHERE assertion_id=(SELECT min(assertion_id) FROM "
                       "  identity_v1.assertion WHERE source_facts IS NOT NULL)"),
                       {"f": '{"fabricado": true}'}),
                   garantia="inmutables")

            ataque("6c", "F-042: BORRAR `source_facts` existentes",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.assertion SET source_facts=NULL "
                       " WHERE assertion_id=(SELECT min(assertion_id) FROM "
                       "  identity_v1.assertion WHERE source_facts IS NOT NULL)")),
                   garantia="inmutables")

            ataque("6d", "borrar una assertion vigente",
                   lambda: conn.execute(text(
                       "DELETE FROM identity_v1.assertion WHERE assertion_id=1")))

            ataque("6e", "reabrir una assertion ya cerrada",
                   lambda: conn.execute(text(
                       "UPDATE identity_v1.assertion SET valid_to=NULL "
                       " WHERE valid_to IS NOT NULL AND assertion_id=(SELECT "
                       "  min(assertion_id) FROM identity_v1.assertion WHERE valid_to IS NOT NULL)")))

            # ---- 7. DATOS DE UNA ENTIDAD ATRIBUIDOS A OTRA --------------
            ataque(7, "el CUIT de CEPU atribuido a YPF (el error historico)",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'CUIT','AFIP',:v,TRUE,'ACTIVE',:a)"),
                       {"k": ypf, "v": CUIT_CEPU,
                        "a": ev(conn, ypf, "SEC_20F",
                                '{"accession": "x", "seccion": "Item 4.A"}')}),
                   garantia="ux_identifier_autoritativo_unico")

            ataque("7b", "un TICKER declarado como identidad juridica",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.identifier (entity_key,id_type,"
                       "id_namespace,id_value,is_authoritative,status,assertion_id) "
                       "VALUES (:k,'TICKER','US','YPF',TRUE,'ACTIVE',:a)"),
                       {"k": ypf, "a": ev(conn, ypf)}))

            ataque("7c", "un bridge VERIFIED firmado por un proceso",
                   lambda: conn.execute(text(
                       "INSERT INTO identity_v1.assertion (subject_type,left_ref,right_ref,"
                       "relationship,method,confidence,status,source_id,source_record,"
                       "evidence,resolved_by) VALUES ('IDENTIFIER_BRIDGE',"
                       "'CIK:SEC:0001114700','LEI:GLEIF:5299008H3AXIXV5G3C23','SAME_ENTITY',"
                       "'CROSS_REFERENCE','AUTHORITATIVE','VERIFIED','GLEIF','g','cita',"
                       "'proc:homologacion')")))
        finally:
            tx.rollback()
            print("\n  (transaccion revertida: ninguna fila real fue modificada)")

    entraron = [r for r in res if r["resultado"] == "ENTRO"]
    errores = [r for r in res if r["resultado"] == "ERROR_DE_PRUEBA"]
    otras = [r for r in res if r["resultado"] == "RECHAZADO_POR_OTRA_COSA"]
    print(f"\n  rechazados={sum(1 for r in res if r['resultado']=='RECHAZADO')}"
          f"  ENTRARON={len(entraron)}  por-otra-garantia={len(otras)}"
          f"  errores-de-prueba={len(errores)}")
    for r in entraron:
        print(f"    BLOCK  {r['n']}. {r['ataque']}")
    for r in errores:
        print(f"    ERROR  {r['n']}. {r['ataque']} -> {r['detalle']}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rutas_prohibidas.json").write_text(
        json.dumps({"total": len(res), "entraron": len(entraron),
                    "errores_de_prueba": len(errores), "ataques": res},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  evidencia -> outputs/docs/homologacion/rutas_prohibidas.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
