#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CATALAXIA V1.0 — generador del baseline machine-readable.

SOLO LECTURA. Cada valor sale de PostgreSQL o del filesystem; ninguno se
escribe a mano. Si un numero no se puede medir, se registra como null, no se
inventa.

Genera:
    docs/release/CATALAXIA_V1_BASELINE.json
    docs/release/CATALAXIA_V1_MANIFEST.json
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine, get_engine  # noqa: E402
from engine import hashout  # noqa: E402

REL = REPO / "docs" / "release"
VERSION = "1.0.0"
ESTADO = "HOMOLOGATED_WITH_NOTES"


def uno(c, sql, p=None):
    return c.execute(text(sql), p or {}).scalar()


def filas(c, sql, p=None):
    return [list(r) for r in c.execute(text(sql), p or {}).all()]


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                              capture_output=True, text=True, timeout=15).stdout.strip() or None
    except Exception:
        return None


def sha_archivo(p: Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return None


def main() -> int:
    s = load_settings()
    if s.is_prod:
        print("EXT-010: abortado.")
        return 2
    app, adm = get_engine(s), get_admin_engine(s)
    REL.mkdir(parents=True, exist_ok=True)
    b: dict = {"version": VERSION,
               "fecha_utc": datetime.now(timezone.utc).isoformat(),
               "estado_homologacion": ESTADO,
               "instancia": s.describe(),
               "git_commit": git_commit()}

    with app.connect() as c:
        # ---------------- IDENTITY -------------------------------------
        b["identity"] = {
            "entities": uno(c, "SELECT count(*) FROM identity_v1.entity"),
            "entities_por_estado": dict(c.execute(text(
                "SELECT entity_status, count(*) FROM identity_v1.entity "
                "GROUP BY 1 ORDER BY 1")).all()),
            "assertions": uno(c, "SELECT count(*) FROM identity_v1.assertion"),
            "assertions_por_status": dict(c.execute(text(
                "SELECT status, count(*) FROM identity_v1.assertion "
                "GROUP BY 1 ORDER BY 1")).all()),
            "assertions_superseded": uno(c, "SELECT count(*) FROM identity_v1.assertion "
                                            " WHERE superseded_by IS NOT NULL"),
            "identifiers_total": uno(c, "SELECT count(*) FROM identity_v1.identifier"),
            "identifiers_vigentes": uno(c, "SELECT count(*) FROM identity_v1.identifier "
                                           " WHERE valid_to IS NULL"),
            "identifiers_autoritativos_vigentes": uno(
                c, "SELECT count(*) FROM identity_v1.identifier "
                   " WHERE is_authoritative AND valid_to IS NULL"),
            "identifiers_retired": uno(c, "SELECT count(*) FROM identity_v1.identifier "
                                          " WHERE status='RETIRED'"),
            "por_tipo_vigente": {
                f"{t}_{'autoritativo' if a else 'candidato'}": n
                for t, a, n in c.execute(text(
                    "SELECT id_type, is_authoritative, count(*) "
                    "  FROM identity_v1.identifier WHERE valid_to IS NULL "
                    " GROUP BY 1,2 ORDER BY 1,2")).all()},
            "reviews_total": uno(c, "SELECT count(*) FROM identity_v1.review"),
            "reviews_open": uno(c, "SELECT count(*) FROM identity_v1.review "
                                   " WHERE status='OPEN'"),
            "conflicts": uno(c, "SELECT count(*) FROM identity_v1.conflict"),
            "sources": filas(c, "SELECT source_id, authority_level, "
                                " COALESCE(authoritative_for,'{}')::text "
                                "  FROM identity_v1.source ORDER BY 1"),
            "bridges": {
                "verified": uno(c, "SELECT count(*) FROM identity_v1.assertion "
                                   " WHERE subject_type='IDENTIFIER_BRIDGE' "
                                   "   AND status='VERIFIED'"),
                "candidate": uno(c, "SELECT count(*) FROM identity_v1.assertion "
                                    " WHERE subject_type='IDENTIFIER_BRIDGE' "
                                    "   AND status='CANDIDATE'"),
                "ratificados": filas(c,
                    "SELECT left_ref, right_ref, resolved_by FROM identity_v1.assertion "
                    " WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED' "
                    " ORDER BY left_ref")},
        }

        # ---------------- SEC ------------------------------------------
        b["sec"] = {
            "filings_pre_xbrl": uno(c, "SELECT count(*) FROM parsed.pre_xbrl_filings"),
            "filings_con_xbrl_parseados": uno(
                c, "SELECT count(DISTINCT accession_number) FROM parsed.facts"),
            "filings_normalizados_s04": uno(
                c, "SELECT count(DISTINCT accession_number) FROM derived.fact"),
            "parsed_facts": uno(c, "SELECT count(*) FROM parsed.facts"),
            "parsed_contexts": uno(c, "SELECT count(*) FROM parsed.contexts"),
            "parsed_units": uno(c, "SELECT count(*) FROM parsed.units"),
            "parsed_units_divided": uno(c, "SELECT count(*) FROM parsed.units "
                                           " WHERE unit_type='DIVIDED'"),
            "parsed_units_divided_sin_num_den": uno(
                c, "SELECT count(*) FROM parsed.units WHERE unit_type='DIVIDED' "
                   "  AND (numerator IS NULL OR denominator IS NULL)"),
            "parsed_concepts": uno(c, "SELECT count(*) FROM parsed.concepts"),
            "parsed_facts_sin_source_hash": uno(
                c, "SELECT count(*) FROM parsed.facts WHERE source_hash IS NULL"),
            "derived_fact": uno(c, "SELECT count(*) FROM derived.fact"),
            "derived_normalize_conflict": uno(
                c, "SELECT count(*) FROM derived.normalize_conflict"),
            "derived_sin_source_fact_ids": uno(
                c, "SELECT count(*) FROM derived.fact "
                   " WHERE source_fact_ids IS NULL OR array_length(source_fact_ids,1) IS NULL"),
            "derived_fact_key_duplicados": uno(
                c, "SELECT count(*) FROM (SELECT fact_key FROM derived.fact "
                   " WHERE valid_to IS NULL GROUP BY 1 HAVING count(*)>1) x"),
            "checkpoints_por_stage": dict(c.execute(text(
                "SELECT stage_id, count(*) FROM engine.checkpoints "
                "GROUP BY 1 ORDER BY 1")).all()),
            "checkpoints_en_corrida_no_ok": uno(
                c, "SELECT count(*) FROM engine.checkpoints ch "
                   "  JOIN engine.runs r USING (run_id) WHERE r.status<>'OK'"),
        }

        # hashout: se RECALCULA, no se copia de ningun reporte
        b["hashout"] = {}
        for t in hashout.CAMPOS:
            try:
                d1 = hashout.digest_tabla(c, t)
                d2 = hashout.digest_tabla(c, t)
                b["hashout"][t] = {"digest": d1, "determinista": d1 == d2}
            except Exception as e:
                b["hashout"][t] = {"digest": None, "error": str(e)[:120]}

        # ---------------- CNV -----------------------------------------
        b["cnv"] = {
            "empresas_con_datos": uno(
                c, "SELECT count(DISTINCT cuit) FROM fetch_raw.cnv_presentation"),
            "presentaciones_guid_unicos": uno(
                c, "SELECT count(DISTINCT guid) FROM fetch_raw.cnv_presentation"),
            "filas_totales_versionadas_por_corrida": uno(
                c, "SELECT count(*) FROM fetch_raw.cnv_presentation"),
            "artefactos": uno(c, "SELECT count(*) FROM fetch_raw.cnv_artifact"),
            "por_empresa": filas(c,
                "SELECT cuit, count(DISTINCT guid), count(DISTINCT run_id) "
                "  FROM fetch_raw.cnv_presentation GROUP BY 1 ORDER BY 2 DESC"),
            "nota_grano": ("UNIQUE(run_id,guid): RAW inmutable versionado por corrida. "
                           "Contar filas sobreestima la cobertura por el numero de corridas."),
        }

        # ---------------- LIFECYCLE -----------------------------------
        b["lifecycle"] = {
            "runs_por_estado": dict(c.execute(text(
                "SELECT status, count(*) FROM engine.runs GROUP BY 1 ORDER BY 1")).all()),
            "runs_running": uno(c, "SELECT count(*) FROM engine.runs "
                                   " WHERE status='RUNNING'"),
        }

        # ---------------- INTEGRIDAD ----------------------------------
        b["integridad"] = {
            "cik_autoritativo_duplicado": uno(
                c, "SELECT count(*) FROM (SELECT id_value FROM identity_v1.identifier "
                   " WHERE id_type='CIK' AND is_authoritative AND valid_to IS NULL "
                   " GROUP BY 1 HAVING count(*)>1) x"),
            "entidad_con_dos_cik_autoritativos": uno(
                c, "SELECT count(*) FROM (SELECT entity_key FROM identity_v1.identifier "
                   " WHERE id_type='CIK' AND is_authoritative AND valid_to IS NULL "
                   " GROUP BY 1 HAVING count(*)>1) y"),
            "identifiers_huerfanos": uno(
                c, "SELECT count(*) FROM identity_v1.identifier i WHERE NOT EXISTS "
                   " (SELECT 1 FROM identity_v1.entity e WHERE e.entity_key=i.entity_key)"),
            "contaminacion_de_tipo": uno(
                c, "SELECT count(*) FROM identity_v1.identifier i "
                   "  JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id "
                   " WHERE i.is_authoritative AND i.valid_to IS NULL "
                   "   AND a.left_ref IS NOT NULL "
                   "   AND a.left_ref <> i.id_type||':'||i.id_namespace||':'||i.id_value"),
            "entidades_muertas_con_identidad": uno(
                c, "SELECT count(*) FROM identity_v1.identifier i "
                   "  JOIN identity_v1.entity e USING (entity_key) "
                   " WHERE i.is_authoritative AND i.valid_to IS NULL "
                   "   AND e.entity_status IN ('MERGED','DISSOLVED')"),
            "verified_sin_evidencia": uno(
                c, "SELECT count(*) FROM identity_v1.assertion WHERE status='VERIFIED' "
                   "   AND (evidence IS NULL OR source_id IS NULL OR resolved_by IS NULL)"),
            "human_decision_firmada_por_proceso": uno(
                c, "SELECT count(*) FROM identity_v1.assertion "
                   " WHERE method='HUMAN_DECISION' "
                   "   AND (resolved_by IS NULL OR resolved_by LIKE 'proc:%')"),
            "assertions_autoritativas_sin_left_ref_F046": uno(
                c, "SELECT count(*) FROM identity_v1.identifier i "
                   "  JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id "
                   " WHERE i.is_authoritative AND i.valid_to IS NULL AND a.left_ref IS NULL"),
            "cik_autoritativo_sin_source_facts_F041": uno(
                c, "SELECT count(*) FROM identity_v1.identifier i "
                   "  JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id "
                   " WHERE i.id_type='CIK' AND i.is_authoritative AND i.valid_to IS NULL "
                   "   AND a.source_facts IS NULL"),
        }

        # ---------------- SEGURIDAD -----------------------------------
        b["seguridad"] = {
            "triggers_activos": filas(c,
                "SELECT cl.relname, t.tgname FROM pg_trigger t "
                "  JOIN pg_class cl ON cl.oid=t.tgrelid "
                "  JOIN pg_namespace n ON n.oid=cl.relnamespace "
                " WHERE n.nspname='identity_v1' AND NOT t.tgisinternal "
                "   AND t.tgenabled='O' ORDER BY 1,2"),
            "checks": filas(c,
                "SELECT conrelid::regclass::text, conname, convalidated "
                "  FROM pg_constraint WHERE connamespace='identity_v1'::regnamespace "
                "   AND contype='c' ORDER BY 1,2"),
            "indices_unicos": filas(c,
                "SELECT tablename, indexname FROM pg_indexes "
                " WHERE schemaname='identity_v1' AND indexdef LIKE '%UNIQUE%' "
                " ORDER BY 1,2"),
            "grants_update_por_columna": filas(c,
                "SELECT table_name, column_name FROM information_schema.column_privileges "
                " WHERE grantee='catalaxia_engine' AND table_schema='identity_v1' "
                "   AND privilege_type='UPDATE' ORDER BY 1,2"),
            "grants_tabla_source": filas(c,
                "SELECT grantee, privilege_type FROM information_schema.table_privileges "
                " WHERE table_schema='identity_v1' AND table_name='source' ORDER BY 1,2"),
        }

        b["migrations_aplicadas"] = [r[0] for r in c.execute(text(
            "SELECT filename FROM engine.schema_migrations ORDER BY filename"))]

    # ---------------- MARKET (otro rol: engine no tiene acceso) --------
    with adm.connect() as c:
        b["market"] = {
            "instrumentos": uno(c, "SELECT count(*) FROM market_instruments"),
            "con_venue_ticker": uno(c, "SELECT count(venue_ticker) FROM market_instruments"),
            "venue_divergente_de_canonico": uno(
                c, "SELECT count(*) FROM market_instruments "
                   " WHERE venue_ticker IS DISTINCT FROM ticker_canonico"),
            "divergentes_detalle": filas(c,
                "SELECT instrument_id, ticker_canonico, venue_ticker, exchange "
                "  FROM market_instruments "
                " WHERE venue_ticker IS DISTINCT FROM ticker_canonico "
                " ORDER BY instrument_id::int"),
            "m23_stage": "smoke-real-2026-08-28",
            "m23_filas": uno(c, "SELECT count(*) FROM market_raw_runs "
                                " WHERE stage_run_id='smoke-real-2026-08-28'"),
            "m23_instrumentos": uno(c, "SELECT count(DISTINCT instrument_id) "
                                       " FROM market_raw_runs "
                                       " WHERE stage_run_id='smoke-real-2026-08-28'"),
            "m23_success": uno(c, "SELECT count(*) FROM market_raw_runs "
                                  " WHERE stage_run_id='smoke-real-2026-08-28' "
                                  "   AND status='SUCCESS'"),
            "m23_failed": uno(c, "SELECT count(*) FROM market_raw_runs "
                                 " WHERE stage_run_id='smoke-real-2026-08-28' "
                                 "   AND status='FAILED'"),
            "m23_success_con_sha256": uno(c, "SELECT count(*) FROM market_raw_runs "
                                             " WHERE stage_run_id='smoke-real-2026-08-28' "
                                             "   AND status='SUCCESS' AND sha256 IS NOT NULL"),
            "m23_run_id_duplicados": uno(c, "SELECT count(*) FROM (SELECT run_id "
                                            " FROM market_raw_runs GROUP BY 1 "
                                            " HAVING count(*)>1) x"),
            "failed_con_error_empty_F043": uno(
                c, "SELECT count(*) FROM market_raw_runs WHERE status='FAILED' "
                   "   AND request_parameters->>'error_type'='EMPTY'"),
            "status_empty_emitido_F043": uno(
                c, "SELECT count(*) FROM market_raw_runs WHERE status='EMPTY'"),
            "failed_declarando_datos": uno(
                c, "SELECT count(*) FROM market_raw_runs WHERE status='FAILED' "
                   "   AND (sha256 IS NOT NULL OR row_count > 0)"),
        }

    # ---------------- FILESYSTEM ---------------------------------------
    raw = REPO / "data" / "raw" / "market"
    b["market"]["raw_instrumentos_en_disco"] = sum(1 for d in raw.iterdir() if d.is_dir()) \
        if raw.exists() else None
    b["market"]["raw_history_csv"] = len(list(raw.rglob("history.csv"))) if raw.exists() else None
    b["market"]["raw_meta_json"] = len(list(raw.rglob("meta.json"))) if raw.exists() else None

    b["findings"] = {
        "CLOSED": ["F-009", "F-024", "F-026", "F-028", "F-029", "F-031", "F-032",
                   "F-034", "F-035", "F-036", "F-037", "F-038", "F-040", "F-042",
                   "F-045"],
        "CLOSED_WITH_NOTES": ["F-041", "F-044", "F-046", "F-047"],
        "OPEN_POST_V1": ["F-043"],
        "MITIGADO": ["F-014"],
        "NO_REPRODUCIBLE": ["F-027"],
    }

    (REL / "CATALAXIA_V1_BASELINE.json").write_text(
        json.dumps(b, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # ---------------- MANIFEST ------------------------------------------
    def inventario(patrones):
        out = []
        for pat in patrones:
            for p in sorted(REPO.glob(pat)):
                if p.is_file():
                    out.append({"path": str(p.relative_to(REPO)).replace("\\", "/"),
                                "bytes": p.stat().st_size, "sha256": sha_archivo(p)})
        return out

    man = {
        "version": VERSION, "fecha_utc": b["fecha_utc"], "estado": ESTADO,
        "git_commit": b["git_commit"],
        "nota": "Sin secretos ni credenciales. Solo codigo, migraciones, contratos y evidencia.",
        "migrations": inventario(["migrations/engine/*.sql", "migrations/market/*.sql"]),
        "codigo_engine": inventario(["engine/*.py", "engine/cnv/*.py"]),
        "codigo_scripts": inventario(["scripts/engine/*.py"]),
        "tests": inventario(["tests/test_*.py"]),
        "contratos": inventario(["docs/architecture/*CONTRACT*.md",
                                 "docs/architecture/*CONTRATO*.md"]),
        "auditoria": inventario(["docs/review/*.md"]),
        "evidencia": inventario(["outputs/docs/homologacion/*.json"]),
        "release": inventario(["docs/release/*.json", "docs/release/*.md"]),
    }
    man["totales"] = {k: len(v) for k, v in man.items() if isinstance(v, list)}
    (REL / "CATALAXIA_V1_MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"CATALAXIA V1.0 · BASELINE  ({s.describe()})\n")
    print(f"  identity   entities={b['identity']['entities']} "
          f"assertions={b['identity']['assertions']} "
          f"identifiers_vig={b['identity']['identifiers_vigentes']} "
          f"autoritativos={b['identity']['identifiers_autoritativos_vigentes']}")
    print(f"  identity   {b['identity']['por_tipo_vigente']}")
    print(f"  identity   reviews_open={b['identity']['reviews_open']} "
          f"conflicts={b['identity']['conflicts']} "
          f"bridges_verified={b['identity']['bridges']['verified']}")
    print(f"  sec        filings {b['sec']['filings_pre_xbrl']} PRE_XBRL + "
          f"{b['sec']['filings_con_xbrl_parseados']} con XBRL · "
          f"facts={b['sec']['parsed_facts']} derived={b['sec']['derived_fact']}")
    print(f"  market     instrumentos={b['market']['instrumentos']} "
          f"M23 {b['market']['m23_success']} SUCCESS / {b['market']['m23_failed']} FAILED · "
          f"RAW {b['market']['raw_history_csv']} csv + {b['market']['raw_meta_json']} meta")
    print(f"  cnv        {b['cnv']['empresas_con_datos']} empresas · "
          f"{b['cnv']['presentaciones_guid_unicos']} GUIDs unicos "
          f"({b['cnv']['filas_totales_versionadas_por_corrida']} filas versionadas)")
    print(f"  lifecycle  {b['lifecycle']['runs_por_estado']} RUNNING={b['lifecycle']['runs_running']}")
    print(f"  seguridad  {len(b['seguridad']['triggers_activos'])} triggers · "
          f"{len(b['seguridad']['checks'])} CHECKs · "
          f"{len(b['seguridad']['indices_unicos'])} indices unicos")
    print(f"  migraciones aplicadas: {len(b['migrations_aplicadas'])}")
    print("\n  integridad")
    for k, v in b["integridad"].items():
        print(f"    {'OK ' if v == 0 else 'NOTA'} {k:<48} {v}")
    print(f"\n  hashout determinista: "
          f"{sum(1 for x in b['hashout'].values() if x.get('determinista'))}/{len(b['hashout'])}")
    print(f"\n  -> docs/release/CATALAXIA_V1_BASELINE.json")
    print(f"  -> docs/release/CATALAXIA_V1_MANIFEST.json  ({man['totales']})")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
