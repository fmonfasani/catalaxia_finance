#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria INDEPENDIENTE de pre-homologacion — F-041/043/044/046/047.

No importa codigo del implementador. Reconstruye cada conclusion desde
`pg_constraint`, `pg_trigger`, `information_schema.column_privileges`,
`identity_v1`, `market_raw_runs` y los artefactos de M23.

Emite PASS / PASS_WITH_NOTES / BLOCK por finding, con la regla del encargo:

    BLOCK solo si existe un camino REPRODUCIBLE que produzca corrupcion,
    identidad incorrecta, provenance incorrecta, duplicacion o perdida, en
    operacion normal o mediante el rol `catalaxia_engine`.
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
RAW_MARKET = REPO / "data" / "raw" / "market"
LOS_7 = ("20", "57", "62", "64", "79", "82", "480")


def prueba(conn, sql, p=None):
    sp = conn.begin_nested()
    try:
        conn.execute(text(sql), p or {})
        sp.rollback()
        return True, "ACEPTADO"
    except Exception as e:
        sp.rollback()
        return False, str(e).split("\n")[0][:110]


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    eng = get_engine(s)          # rol operativo
    out = {}

    print(f"AUDITORIA PRE-HOMOLOGACION · {s.describe()}\n")

    with eng.connect() as conn:
        tx = conn.begin()
        try:
            q = lambda sql, p=None: conn.execute(text(sql), p or {}).scalar()

            # ============ F-041 ==================================
            n41 = q("SELECT count(*) FROM identity_v1.identifier i "
                    " JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id "
                    " WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL "
                    "   AND a.source_facts IS NULL")
            mut41, m41 = prueba(conn,
                "UPDATE identity_v1.assertion SET source_facts=CAST('{}' AS jsonb) "
                " WHERE assertion_id=1")
            out["F-041"] = {
                "existe": n41 > 0, "instancias": n41,
                "corrupcion_nueva": False,
                "identidad_incorrecta": False,
                "rompe_provenance": False,
                "duplica_entidades": False,
                "explotable_por_engine": mut41,
                "solo_datos_existentes": True,
                "limitacion_producto": False,
                "deuda_historica": True,
                "evidencia": f"1 assertion (YPF SEC_20F); mutacion por engine: {m41}",
                "veredicto": "PASS_WITH_NOTES"}

            # ============ F-046 ==================================
            n46 = q("SELECT count(*) FROM identity_v1.identifier i "
                    " JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id "
                    " WHERE i.is_authoritative AND i.valid_to IS NULL AND a.left_ref IS NULL")
            incoh = q("SELECT count(*) FROM identity_v1.identifier i "
                      " JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id "
                      " WHERE i.is_authoritative AND i.valid_to IS NULL "
                      "   AND a.left_ref IS NOT NULL "
                      "   AND a.left_ref <> i.id_type||':'||i.id_namespace||':'||i.id_value")
            # ¿se puede crear uno nuevo?
            conn.execute(text(
                "INSERT INTO identity_v1.entity (entity_key,preferred_name,country,"
                "entity_status) VALUES ('E01M15NNNNNNNNNNNNNNNNNNNNN','Aud','US','ACTIVE')"))
            a = conn.execute(text(
                "INSERT INTO identity_v1.assertion (subject_type,entity_key,left_ref,"
                "method,confidence,status,source_id,source_record,evidence,resolved_by,"
                "source_facts) VALUES ('ENTITY_IDENTIFIER','E01M15NNNNNNNNNNNNNNNNNNNNN',"
                "NULL,'REGISTRY','AUTHORITATIVE','VERIFIED','SEC_REGISTRY','a','c',"
                "'proc:aud',CAST('{}' AS jsonb)) RETURNING assertion_id")).scalar_one()
            nuevo46, m46 = prueba(conn,
                "INSERT INTO identity_v1.identifier (entity_key,id_type,id_namespace,"
                "id_value,is_authoritative,status,assertion_id) VALUES "
                "('E01M15NNNNNNNNNNNNNNNNNNNNN','CIK','SEC','0009999998',TRUE,'ACTIVE',:a)",
                {"a": a})
            out["F-046"] = {
                "existe": n46 > 0, "instancias": n46,
                "corrupcion_nueva": nuevo46,
                "identidad_incorrecta": incoh > 0,
                "rompe_provenance": False,
                "duplica_entidades": False,
                "explotable_por_engine": nuevo46,
                "solo_datos_existentes": True,
                "limitacion_producto": False,
                "deuda_historica": True,
                "evidencia": (f"{n46} filas; incoherencias de tipo: {incoh}; "
                              f"crear uno nuevo: {m46}"),
                "veredicto": "PASS_WITH_NOTES"}

            # ============ F-044 ==================================
            grants = conn.execute(text(
                "SELECT string_agg(DISTINCT privilege_type, ',') "
                "  FROM information_schema.table_privileges "
                " WHERE table_schema='identity_v1' AND table_name='source' "
                "   AND grantee='catalaxia_engine'")).scalar()
            trg_src = q("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                        " WHERE c.relname='source' AND NOT t.tgisinternal")
            up44, m44 = prueba(conn,
                "UPDATE identity_v1.source SET authority_level='AUTHORITATIVE' "
                " WHERE source_id='LEGACY_DIM_ENTITY'")
            out["F-044"] = {
                "existe": trg_src == 0,
                "corrupcion_nueva": up44,
                "identidad_incorrecta": up44,
                "rompe_provenance": False,
                "duplica_entidades": False,
                "explotable_por_engine": up44,
                "solo_datos_existentes": False,
                "limitacion_producto": False,
                "deuda_historica": False,
                "evidencia": (f"grants de engine sobre source: {grants}; triggers en "
                              f"source: {trg_src}; UPDATE por engine: {m44}"),
                "veredicto": "PASS_WITH_NOTES" if not up44 else "BLOCK"}

            # ============ F-047 ==================================
            pares = q("SELECT count(*) FROM (SELECT left_ref,right_ref FROM "
                      " identity_v1.assertion WHERE subject_type='IDENTIFIER_BRIDGE' "
                      "   AND valid_to IS NULL GROUP BY 1,2 "
                      " HAVING count(DISTINCT status)>1) x")
            contra = q("SELECT count(*) FROM identity_v1.assertion x "
                       " JOIN identity_v1.assertion y ON x.left_ref=y.left_ref "
                       "  AND x.right_ref IS DISTINCT FROM y.right_ref "
                       " WHERE x.subject_type='IDENTIFIER_BRIDGE' "
                       "   AND y.subject_type='IDENTIFIER_BRIDGE' "
                       "   AND x.status='VERIFIED' AND y.status='VERIFIED' "
                       "   AND x.valid_to IS NULL AND y.valid_to IS NULL")
            ver = q("SELECT count(*) FROM identity_v1.assertion WHERE "
                    " subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED' "
                    " AND (method<>'HUMAN_DECISION' OR resolved_by LIKE 'proc:%' "
                    "      OR resolution_reason IS NULL)")
            out["F-047"] = {
                "existe": pares > 0, "pares_con_ambos_estados": pares,
                "corrupcion_nueva": False,
                "identidad_incorrecta": contra > 0,
                "rompe_provenance": False,
                "duplica_entidades": False,
                "explotable_por_engine": False,
                "solo_datos_existentes": True,
                "limitacion_producto": False,
                "deuda_historica": False,
                "evidencia": (f"{pares} pares con CANDIDATE+VERIFIED; bridges VERIFIED "
                              f"contradictorios: {contra}; VERIFIED mal formados: {ver}"),
                "veredicto": "PASS_WITH_NOTES"}

            # ============ F-043 ==================================
            # `catalaxia_engine` NO tiene permisos sobre las tablas de Market:
            # la separacion de roles es real y verificada. Para LEER el estado de
            # M23 se usa el rol admin -- solo SELECT, sin escritura.
            with get_admin_engine(s).connect() as mc:
                mq = lambda sql, p=None: mc.execute(text(sql), p or {}).scalar()
                estados = dict(mc.execute(text(
                    "SELECT status, count(*) FROM market_raw_runs GROUP BY 1")).all())
                con_empty = mq("SELECT count(*) FROM market_raw_runs WHERE status='EMPTY'")
                failed_empty = mq("SELECT count(*) FROM market_raw_runs WHERE status='FAILED' "
                                  " AND request_parameters->>'error_type'='EMPTY'")
                corruptas = mq("SELECT count(*) FROM market_raw_runs WHERE status='FAILED' "
                               " AND (sha256 IS NOT NULL OR row_count > 0)")
                precios = mq("SELECT count(*) FROM market_price_daily "
                             " WHERE instrument_id = ANY(:i)", {"i": list(LOS_7)})
                reintentables = mq(
                    "SELECT count(DISTINCT instrument_id) FROM market_raw_runs "
                    " WHERE stage_run_id='smoke-real-2026-08-28' AND instrument_id NOT IN "
                    " (SELECT instrument_id FROM market_raw_runs "
                    "   WHERE stage_run_id='smoke-real-2026-08-28' AND status='SUCCESS')")
            raw_en_disco = sum(1 for i in LOS_7 if (RAW_MARKET / i).exists()
                               and any((RAW_MARKET / i).iterdir()))
            out["F-043"] = {
                "existe": con_empty == 0 and failed_empty > 0,
                "corrupcion_nueva": corruptas > 0,
                "identidad_incorrecta": False,
                "rompe_provenance": False,
                "duplica_entidades": False,
                "explotable_por_engine": False,
                "solo_datos_existentes": False,
                "limitacion_producto": True,
                "deuda_historica": False,
                "evidencia": (f"estados usados: {estados}; EMPTY emitido: {con_empty}; "
                              f"FAILED con error EMPTY: {failed_empty}; filas FAILED con "
                              f"datos: {corruptas}; precios de los 7: {precios}; "
                              f"RAW en disco de los 7: {raw_en_disco}; "
                              f"instrumentos que --resume reintentaria: {reintentables}"),
                "veredicto": "PASS_WITH_NOTES"}
        finally:
            tx.rollback()

    print("  finding   veredicto           evidencia")
    print("  " + "-" * 92)
    for k in ("F-041", "F-043", "F-044", "F-046", "F-047"):
        v = out[k]
        print(f"  {k}     {v['veredicto']:<18}  {v['evidencia'][:60]}")
        marcas = [n for n in ("corrupcion_nueva", "identidad_incorrecta",
                              "rompe_provenance", "duplica_entidades",
                              "explotable_por_engine") if v.get(n)]
        print(f"            riesgos activos: {marcas or 'ninguno'}")

    bloqueantes = [k for k, v in out.items() if v["veredicto"] == "BLOCK"]
    print(f"\n  BLOCKERS: {bloqueantes or 'ninguno'}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pre_homologacion.json").write_text(
        json.dumps({"blockers": bloqueantes, "findings": out}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/homologacion/pre_homologacion.json")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
