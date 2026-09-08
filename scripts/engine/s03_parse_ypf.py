from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import tracemalloc
import zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402

from engine import db as edb
from engine import hashout  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.fetch import RAW_ROOT, sha256_bytes  # noqa: E402
from engine.identity import resolve_golden_ypf  # noqa: E402
from engine.report import StageReport, utc_now_iso  # noqa: E402
from engine.states import GateStatus, StageState, assert_transition  # noqa: E402
from engine.xbrlparse import (  # noqa: E402
    companyfacts_index,
    parse_instance_bytes,
    parse_inline_bytes,
    parse_linkbase_bytes,
    parse_schema_bytes,
    zip_instance_candidates,
)

STAGE_ID = "S03_parse"
PIPELINE_VERSION = "engine-v1"
SCRIPT = "scripts/engine/s03_parse_ypf.py"
PARSER_VERSION = "xbrl_parse_v2"
OUT_DIR = REPO_ROOT / "outputs" / "docs" / "fase_s03"
GOLDEN_CIK = "0000904851"
STANDARD_HINTS = ("us-gaap", "ifrs-full", "dei", "srt")

XBRL_PAYLOAD_KINDS = {"XBRL_INSTANCE", "XBRL_SCHEMA", "LINKBASE_PRE", "LINKBASE_CAL",
                      "LINKBASE_DEF", "LINKBASE_LAB", "XBRL_OTHER", "XBRL_PACKAGE_ZIP"}
GLOBAL_KINDS = {"SUBMISSIONS", "COMPANYFACTS", "SUBMISSIONS_PAGE"}
INLINE_EXTS = (".htm", ".html")

FACT_COLS = ("run_id", "entity_id", "cik", "accession_number", "form", "filing_date",
             "report_period", "taxonomy", "namespace", "tag", "qname", "value_text",
             "value_numeric", "is_numeric", "is_nil", "unit_ref", "unit_type", "measure",
             "numerator", "denominator", "decimals", "context_id", "start_date", "end_date",
             "instant_date", "period_kind", "dimensions", "dim_count", "frame",
             "source_kind", "source_file", "source_path", "source_hash", "stage_run_id")
CTX_COLS = ("run_id", "entity_id", "accession_number", "context_id", "scheme", "identifier",
            "start_date", "end_date", "instant_date", "period_kind", "dimensions",
            "typed_dimensions", "dim_count", "has_typed", "source_file", "source_hash")
UNIT_COLS = ("run_id", "entity_id", "accession_number", "unit_ref", "unit_type", "measures",
             "numerator", "denominator", "fact_count", "source_file", "source_hash")
CONCEPT_COLS = ("run_id", "namespace", "tag", "qname", "label", "documentation", "xsd_type",
                "period_type", "balance", "abstract", "is_custom", "taxonomy", "source_schema")
REL_COLS = ("run_id", "entity_id", "accession_number", "linkbase", "role", "from_qname",
            "to_qname", "arc_role", "weight", "order_num", "label_type", "lang", "label_text",
            "preferred_sign", "dimension_qname", "member_qname", "source_file", "source_hash")
PX_COLS = ("run_id", "entity_id", "cik", "accession_number", "form", "filing_date",
           "period_of_report", "primary_doc", "index_path", "n_documents", "documents",
           "bytes_total", "classification", "note")
CMP_COLS = ("run_id", "entity_id", "taxonomy", "tag", "qname", "in_companyfacts", "in_filing",
            "cf_obs", "cf_unit_kinds", "cf_first_period", "cf_last_period", "filing_obs", "notes")
ERR_COLS = ("run_id", "entity_id", "accession_number", "source_file", "severity", "code", "message")

JSONB_TEMPLATES = {
    "parsed.facts": "(" + "%s," * 26 + "%s::jsonb," + "%s," * 6 + "%s)",
    "parsed.contexts": "(" + "%s," * 10 + "%s::jsonb,%s::jsonb," + "%s," * 3 + "%s)",
    "parsed.units": "(" + "%s," * 5 + "%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s)",
    "parsed.pre_xbrl_filings": "(" + "%s," * 10 + "%s::jsonb," + "%s," * 2 + "%s)",
    "parsed.companyfacts_compare": "(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
}
PARSED_TABLES = ("parsed.facts", "parsed.contexts", "parsed.units", "parsed.concepts",
                 "parsed.link_relations", "parsed.pre_xbrl_filings",
                 "parsed.companyfacts_compare", "parsed.parse_errors")


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def insert_many(cur, table: str, cols: tuple[str, ...], rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_values(cur, f"INSERT INTO {table} ({','.join(cols)}) VALUES %s",
                   rows, template=JSONB_TEMPLATES.get(table), page_size=1000)
    return len(rows)


def find_s02_input_run(engine) -> str:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT r.run_id FROM engine.runs r
             WHERE EXISTS (SELECT 1 FROM engine.stage_runs s
                            WHERE s.run_id = r.run_id AND s.stage_id='S02_fetch'
                              AND s.gate_status='PASS')
             ORDER BY r.started_at DESC LIMIT 1""")).scalar()
    if not row:
        raise SystemExit("BLOCK: no hay run S02 con gate PASS; correr scripts/engine/s02_fetch_ypf.py")
    return row


def load_s02_inputs(engine, run_id: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT log_id, request_kind, accession_number AS acc, form_type AS form,
                   filing_date, period_of_report AS period, raw_path, sha256, bytes
              FROM fetch_raw.download_log
             WHERE run_id=:r AND result IN ('DOWNLOADED','SIN_CAMBIOS')
               AND raw_path IS NOT NULL AND sha256 IS NOT NULL"""), {"r": run_id}).mappings().all()
    return [dict(r) for r in rows]


def verify_raw_integrity(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for r in rows:
        path = RAW_ROOT / r["raw_path"]
        if not path.exists():
            bad.append({**r, "reason": "MISSING_FILE"})
            continue
        actual = sha256_bytes(path.read_bytes())
        if actual != r["sha256"]:
            bad.append({**r, "reason": f"SHA_MISMATCH db={r['sha256'][:12]} disk={actual[:12]}"})
        else:
            ok.append(r)
    return ok, bad


def build_buckets(files_ok: list[dict]) -> dict[str, dict]:
    buckets: dict[str, dict] = {}
    for r in files_ok:
        if r["request_kind"] in GLOBAL_KINDS:
            continue
        acc = r["acc"] if r["acc"] and r["acc"] != "N/A" else "_GLOBAL_"
        b = buckets.setdefault(acc, {"meta": {"form": r["form"], "filing_date": r["filing_date"],
                                              "period": r["period"]}, "files": []})
        b["files"].append(r)
    return buckets


def path_bytes(r: dict) -> bytes:
    return (RAW_ROOT / r["raw_path"]).read_bytes()


def parse_filing(acc: str, bucket: dict, run, stage_run_id: int) -> dict:
    out = {
        "acc": acc, "meta": bucket["meta"], "outcome": None,
        "facts_rows": [], "ctx_rows": [], "unit_rows": [],
        "concept_rows": [], "rel_rows": [], "errors": [],
        "metrics": {"payload_files": 0, "instances": 0, "inline_docs": 0, "zips": 0,
                    "schemas": 0, "linkbases": 0, "indexes": 0},
        "fact_index": defaultdict(lambda: {"obs": 0, "periods": set(), "units": set()}),
        "seconds": 0.0,
    }
    t0 = time.perf_counter()
    meta = bucket["meta"]
    base7 = [run.run_id, run.entity_id, GOLDEN_CIK, acc, meta.get("form"),
             meta.get("filing_date"), meta.get("period")]

    seen_hashes: set[str] = set()

    def consume_parsed(res, source_kind: str, source_file: str,
                       source_path: str, source_hash: str) -> int:
        for err in res.errors:
            out["errors"].append({"severity": "ERROR", "code": err["code"],
                                  "source_file": source_file, "message": err["message"]})
        if res.stats.get("errors") or source_hash in seen_hashes:
            return 0
        seen_hashes.add(source_hash)
        ctx_by_id = res.contexts
        units_by_ref = res.units
        n_new_facts = 0
        for ctx in ctx_by_id.values():
            out["ctx_rows"].append(tuple([
                run.run_id, run.entity_id, acc, ctx.context_id, ctx.scheme, ctx.identifier,
                ctx.start_date, ctx.end_date, ctx.instant_date, ctx.period_kind,
                j(ctx.dimensions), j(ctx.typed_dimensions) if ctx.typed_dimensions else None,
                ctx.dim_count, bool(ctx.typed_dimensions), source_file, source_hash]))
        unit_fact_count: dict[str, int] = defaultdict(int)
        for f in res.facts:
            unit_type = measure = numerator = denominator = None
            if f.unit_ref and f.unit_ref in units_by_ref:
                u = units_by_ref[f.unit_ref]
                unit_type = u.unit_type
                measure = "|".join(u.measures) or None
                numerator = "|".join(u.numerator) or None
                denominator = "|".join(u.denominator) or None
                unit_fact_count[f.unit_ref] += 1
            ctx = ctx_by_id.get(f.context_id)
            out["facts_rows"].append(tuple(base7 + [
                f.taxonomy, f.namespace, f.tag, f.qname, f.value_text,
                f.value_numeric, f.is_numeric, f.is_nil,
                f.unit_ref, unit_type, measure, numerator, denominator,
                f.decimals, f.context_id,
                ctx.start_date if ctx else None, ctx.end_date if ctx else None,
                ctx.instant_date if ctx else None, f.period_kind,
                j(ctx.dimensions), ctx.dim_count if ctx else 0, f.frame,
                source_kind, source_file, source_path, source_hash, stage_run_id]))
            n_new_facts += 1
            fi = out["fact_index"][f.qname]
            fi["obs"] += 1
            period_key = ctx.instant_date or (ctx.end_date if ctx else None)
            if period_key:
                fi["periods"].add(period_key)
            if measure:
                fi["units"].add(measure)
            elif numerator and denominator:
                fi["units"].add(f"{numerator}/{denominator}")
        for u_ref, u in units_by_ref.items():
            cnt = unit_fact_count.get(u_ref, 0)
            out["unit_rows"].append(tuple([
                run.run_id, run.entity_id, acc, u_ref, u.unit_type,
                j(u.measures), j(u.numerator) if u.numerator else None,
                j(u.denominator) if u.denominator else None, cnt, source_file, source_hash]))
        return n_new_facts

    def consume_instance(data: bytes, source_kind: str, source_file: str,
                         source_path: str, source_hash: str) -> int:
        return consume_parsed(parse_instance_bytes(data), source_kind,
                              source_file, source_path, source_hash)

    def consume_inline(data: bytes, source_kind: str, source_file: str,
                       source_path: str, source_hash: str) -> int:
        res = parse_inline_bytes(data)
        if not res.stats.get("facts"):
            return 0
        out["metrics"]["inline_docs"] += 1
        return consume_parsed(res, source_kind, source_file, source_path, source_hash)

    def concept_row(c, src):
        return (run.run_id, c.namespace, c.tag, c.qname, c.label, c.documentation,
                c.xsd_type, c.period_type, c.balance, c.abstract,
                not any(s in (c.taxonomy or "") for s in STANDARD_HINTS),
                c.taxonomy, src)

    def rel_row(rel, src, src_hash):
        return (run.run_id, run.entity_id, acc, rel.linkbase, rel.role, rel.from_qname,
                rel.to_qname, rel.arc_role, rel.weight, rel.order_num, rel.label_type,
                rel.lang, rel.label_text, rel.preferred_sign, rel.dimension_qname,
                rel.member_qname, src, src_hash)

    for r in sorted(bucket["files"], key=lambda x: x["request_kind"]):
        kind = r["request_kind"]
        path = RAW_ROOT / r["raw_path"]
        src_name = Path(r["raw_path"]).name
        try:
            data = path.read_bytes() if kind != "XBRL_PACKAGE_ZIP" else b""
            if kind == "XBRL_PACKAGE_ZIP":
                out["metrics"]["zips"] += 1
                with zipfile.ZipFile(path) as zf:
                    members = zf.namelist()
                    inst_members = set(zip_instance_candidates(members))
                    payload_members = [m for m in members if m not in inst_members]
                    for m in sorted(inst_members):
                        mdata = zf.read(m)
                        if consume_instance(mdata, "XBRL_PACKAGE_ZIP", m,
                                            f"{r['raw_path']}!{m}", sha256_bytes(mdata)):
                            out["metrics"]["instances"] += 1
                    if not inst_members:
                        for m in sorted(payload_members):
                            if not m.lower().endswith(INLINE_EXTS):
                                continue
                            mdata = zf.read(m)
                            consume_inline(mdata, "XBRL_PACKAGE_ZIP_INLINE", m,
                                           f"{r['raw_path']}!{m}", sha256_bytes(mdata))
                    for m in sorted(payload_members):
                        low = m.lower()
                        if low.endswith(".htm") or low.endswith(".html"):
                            continue
                        mdata = zf.read(m)
                        if low.endswith(".xsd"):
                            out["metrics"]["schemas"] += 1
                            for c in parse_schema_bytes(mdata, m):
                                out["concept_rows"].append(concept_row(c, f"{src_name}!{m}"))
                        elif low.endswith(("_pre.xml", "_cal.xml", "_defr.xml", "_def.xml", "_lab.xml")):
                            out["metrics"]["linkbases"] += 1
                            m_hash = sha256_bytes(mdata)
                            for rel in parse_linkbase_bytes(mdata, Path(m).name):
                                out["rel_rows"].append(rel_row(rel, f"{src_name}!{m}", m_hash))
            elif kind == "XBRL_INSTANCE":
                if consume_instance(data, "XBRL_INSTANCE", src_name, r["raw_path"], r["sha256"]):
                    out["metrics"]["instances"] += 1
            elif kind == "XBRL_SCHEMA":
                out["metrics"]["schemas"] += 1
                for c in parse_schema_bytes(data, src_name):
                    out["concept_rows"].append(concept_row(c, r["raw_path"]))
            elif kind in {"LINKBASE_PRE", "LINKBASE_CAL", "LINKBASE_DEF", "LINKBASE_LAB"}:
                out["metrics"]["linkbases"] += 1
                for rel in parse_linkbase_bytes(data, src_name):
                    out["rel_rows"].append(rel_row(rel, src_name, r["sha256"]))
            elif kind == "FILING_INDEX":
                out["metrics"]["indexes"] += 1
            out["metrics"]["payload_files"] += 1
        except Exception as exc:
            out["errors"].append({"severity": "ERROR", "code": f"PARSE_{kind}",
                                  "source_file": src_name, "message": str(exc)[:400]})
    has_xbrl_payload = any(r["request_kind"] in XBRL_PAYLOAD_KINDS for r in bucket["files"])
    if not out["facts_rows"] and has_xbrl_payload and out["metrics"]["instances"] == 0:
        for r in sorted(bucket["files"], key=lambda x: x["log_id"]):
            if r["request_kind"] != "DOC_HTM":
                continue
            try:
                consume_inline(path_bytes(r), "DOC_HTM_INLINE", Path(r["raw_path"]).name,
                               r["raw_path"], r["sha256"])
            except Exception as exc:
                out["errors"].append({"severity": "ERROR", "code": "PARSE_DOC_HTM",
                                      "source_file": Path(r["raw_path"]).name,
                                      "message": str(exc)[:400]})
    if len(out["facts_rows"]) > 0:
        out["outcome"] = "PARSED_XBRL"
    elif not has_xbrl_payload:
        out["outcome"] = "PRE_XBRL"
    else:
        out["outcome"] = "REJECTED"
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def main() -> int:
    """Envoltorio: setup + ciclo de vida GARANTIZADO (F-031).

    S03 usaba `start_run` al principio y `finish_run` suelto al final. Cualquier
    excepcion en el medio —y hubo cinco en esta serie: permisos de DDL, permisos
    de DELETE, permisos de secuencia, statement_timeout, ANALYZE salteado— dejaba
    la corrida en RUNNING para siempre. Ocho corridas huerfanas en total.

    `run_scope()` pone el cierre en `finally`: si el cuerpo levanta, la corrida
    queda ABORTED con `finished_at`. Es el mismo patron que S04, que corrio
    siete veces en la misma serie sin dejar una sola huerfana.

    No se toca el parsing, la normalizacion ni los contratos de datos: el cuerpo
    de la etapa se movio entero a `_etapa`, sin reindentar ni reordenar nada.
    """
    settings = load_settings()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[config] target={settings.describe()} scope=GOLDEN_CASE:YPF:{STAGE_ID}")
    engine = edb.get_engine(settings)
    applied = edb.apply_migrations(engine, settings=settings)
    print(f"[migrations] aplicadas ahora: {applied or '(ninguna nueva)'}")

    huerfanas = edb.corridas_huerfanas(engine)
    if huerfanas:
        print(f"BLOCK · F-009: hay {len(huerfanas)} corrida(s) huerfana(s). "
              "Cerrarlas antes de generar mas.")
        for h in huerfanas:
            print(f"   {h['run_id']} {h['pipeline_version']} {h['horas']} h")
        return 1

    with edb.run_scope(engine, settings, PIPELINE_VERSION, stage_id=STAGE_ID) as run:
        print(f"[run] run_id={run.run_id} git={run.git_commit}")
        return _etapa(engine, settings, run)


def _etapa(engine, settings, run) -> int:
    """Cuerpo de la etapa. Identico al que estaba en `main`, sin cambios."""
    # Mecanismo de PRUEBA del ciclo de vida (F-031): permite provocar un fallo
    # en un punto conocido para verificar que la corrida quede ABORTED.
    # No altera el parsing ni los datos.
    punto_falla = os.environ.get("S03_SIMULAR_FALLO")
    if punto_falla == "INICIO":
        raise RuntimeError("fallo simulado (F-031): antes de parsear")

    prev_state: StageState | None = None
    cur_state = StageState.PLANNED
    for nxt in (StageState.READY, StageState.RUNNING):
        assert_transition(cur_state, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=prev_state, new_state=nxt)
        prev_state, cur_state = cur_state, nxt
    with engine.connect() as conn:
        stage_run_id = conn.execute(
            text("SELECT id FROM engine.stage_runs WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run.run_id, "s": STAGE_ID}).scalar_one()

    ent = resolve_golden_ypf(engine)
    if not ent.get("present") or ent["cik"] != GOLDEN_CIK:
        raise SystemExit("BLOCK: identidad YPF inconsistente con golden case")
    run.entity_id = ent["entity_id"]
    print(f"[identity] {ent['entity_id']} | {ent['legal_name']}")

    s02_run_id = find_s02_input_run(engine)
    print(f"[input] checkpoint S02: run_id={s02_run_id}")
    s02_files = load_s02_inputs(engine, s02_run_id)
    files_ok, files_bad = verify_raw_integrity(s02_files)
    print(f"[integridad] archivos ok={len(files_ok)} corruptos/ausentes={len(files_bad)}")

    buckets = build_buckets(files_ok)
    filings_expected = len([a for a in buckets if a != "_GLOBAL_"])

    cf_row = next((r for r in files_ok if r["request_kind"] == "COMPANYFACTS"), None)
    cf_index: dict[str, dict] = {}
    if cf_row:
        cf_json = json.loads((RAW_ROOT / cf_row["raw_path"]).read_text(encoding="utf-8"))
        cf_index = companyfacts_index(cf_json)

    started_at = utc_now_iso()
    t_start = time.perf_counter()
    tracemalloc.start()
    filing_results: list[dict] = []
    px_rows: list[tuple] = []
    err_rows: list[tuple] = []
    cmp_rows: list[tuple] = []
    all_concepts: dict[str, tuple] = {}

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        for table in PARSED_TABLES:
            cur.execute(f"DELETE FROM {table}")
        cur.execute("SELECT setval(pg_get_serial_sequence('parsed.facts','fact_id'), 1, false)")

        for acc, bucket in buckets.items():
            if acc == "_GLOBAL_":
                continue
            res = parse_filing(acc, bucket, run, stage_run_id)
            filing_results.append(res)
            n_facts = insert_many(cur, "parsed.facts", FACT_COLS, res["facts_rows"])
            insert_many(cur, "parsed.contexts", CTX_COLS, res["ctx_rows"])
            insert_many(cur, "parsed.units", UNIT_COLS, res["unit_rows"])
            insert_many(cur, "parsed.link_relations", REL_COLS, res["rel_rows"])
            print(f"[filing] {res['meta'].get('form')} {acc} -> {res['outcome']} facts={n_facts} "
                  f"ctx={len(res['ctx_rows'])} units={len(res['unit_rows'])} "
                  f"rels={len(res['rel_rows'])} inline={res['metrics']['inline_docs']} t={res['seconds']}s")

        for res in filing_results:
            for row in res["concept_rows"]:
                all_concepts.setdefault(row[3], row)
        observed_missing: list[str] = []
        for res in filing_results:
            for qn in res["fact_index"]:
                if qn not in all_concepts and qn not in observed_missing:
                    observed_missing.append(qn)
                    ns, _, tag = qn.rpartition("#")
                    tax = qn.split("#")[0].rsplit("/", 1)[-1]
                    all_concepts[qn] = (run.run_id, ns or None, tag, qn, None, None, None,
                                        None, None, None,
                                        not any(s in tax for s in STANDARD_HINTS),
                                        tax, "INSTANCE_OBSERVED")
        insert_many(cur, "parsed.concepts", CONCEPT_COLS, list(all_concepts.values()))

        filing_agg: dict[str, dict] = defaultdict(lambda: {"obs": 0, "periods": set(), "units": set()})
        for res in filing_results:
            for qn, fi in res["fact_index"].items():
                agg = filing_agg[qn]
                agg["obs"] += fi["obs"]
                agg["periods"] |= fi["periods"]
                agg["units"] |= fi["units"]
        for qn in sorted(set(cf_index) | set(filing_agg)):
            cf = cf_index.get(qn)
            fa = filing_agg.get(qn)
            taxonomy, _, tag = qn.partition("#")
            notes_parts = []
            if cf and fa:
                if cf["obs"] != fa["obs"]:
                    notes_parts.append(f"obs_diff cf={cf['obs']} filing={fa['obs']}")
                if cf["first_period"] and fa["periods"] and min(fa["periods"]) > cf["first_period"]:
                    notes_parts.append(f"filing_comienza_despues filing={min(fa['periods'])} cf={cf['first_period']}")
                if cf["unit_kinds"] and fa["units"] and not set(cf["unit_kinds"]) & fa["units"]:
                    notes_parts.append("unidades_sin_interseccion")
            elif cf and not fa:
                notes_parts.append("solo_companyfacts")
            elif fa and not cf:
                notes_parts.append("solo_filing")
            cmp_rows.append((run.run_id, ent["entity_id"], taxonomy, tag, qn,
                             bool(cf), bool(fa),
                             cf["obs"] if cf else None,
                             j(cf["unit_kinds"]) if cf and cf["unit_kinds"] else None,
                             cf["first_period"] if cf else None, cf["last_period"] if cf else None,
                             fa["obs"] if fa else None, "; ".join(notes_parts) or None))
        insert_many(cur, "parsed.companyfacts_compare", CMP_COLS, cmp_rows)

        for res in filing_results:
            if res["outcome"] == "PRE_XBRL":
                docs = sorted({Path(r["raw_path"]).name for r in buckets[res["acc"]]["files"]})
                px_rows.append((
                    run.run_id, ent["entity_id"], GOLDEN_CIK, res["acc"], res["meta"].get("form"),
                    res["meta"].get("filing_date"), res["meta"].get("period"), None,
                    next((r["raw_path"] for r in buckets[res["acc"]]["files"]
                          if r["request_kind"] == "FILING_INDEX"), None),
                    len(docs), j(docs),
                    sum(r["bytes"] or 0 for r in buckets[res["acc"]]["files"]),
                    "PRE_XBRL",
                    "era sin XBRL estructurado (FY2001-FY2017): documento preservado en RAW, sin hechos parseables; NO se intento conversion automatica HTML->XBRL"))
        insert_many(cur, "parsed.pre_xbrl_filings", PX_COLS, px_rows)

        for res in filing_results:
            for e in res["errors"]:
                err_rows.append((run.run_id, ent["entity_id"], res["acc"], e["source_file"],
                                 e["severity"], e["code"], e["message"]))
        for b in files_bad:
            err_rows.append((run.run_id, ent["entity_id"], b.get("acc"), b["raw_path"],
                             "ERROR", b["reason"], "input RAW corrompido o ausente"))
        insert_many(cur, "parsed.parse_errors", ERR_COLS, err_rows)
        raw.commit()

        # F-028 — ANALYZE despues del replace-all, antes de validar.
        #
        # S03 vacia parsed.* y recarga ~67k filas. Las estadisticas del planner
        # quedan describiendo las filas viejas, y la validacion de integridad
        # facts<->contexts elige un plan que se pasa del statement_timeout:
        #     QueryCanceled: canceling statement due to statement timeout
        # La corrida moria DESPUES de haber escrito todo, y el trabajo se perdia.
        #
        # ANALYZE sobre los 8 objetos tarda ~3 s. Subir el timeout habria tapado
        # el sintoma dejando el plan malo.
        t_analyze = time.perf_counter()
        cur.execute("SELECT now()")
        t0_db = cur.fetchone()[0]
        for table in PARSED_TABLES:
            cur.execute(f"ANALYZE {table}")
        raw.commit()

        # ANALYZE sin privilegio NO falla: emite
        #     WARNING: permission denied to analyze "facts", skipping it
        # y devuelve exito. Un script que no mira los warnings cree que
        # analizo. Se verifica contra pg_stat_user_tables que las estadisticas
        # se hayan actualizado de verdad, y se aborta si no.
        cur.execute(
            "SELECT relname FROM pg_stat_user_tables "
            " WHERE schemaname='parsed' AND relname = ANY(%s) "
            "   AND (last_analyze IS NULL OR last_analyze < %s)",
            ([t.split('.', 1)[1] for t in PARSED_TABLES], t0_db))
        sin_analizar = [r[0] for r in cur.fetchall()]
        if sin_analizar:
            raise RuntimeError(
                f"F-028: ANALYZE no se aplico sobre {sin_analizar}. "
                "Postgres saltea con warning cuando el rol no es dueño de la tabla; "
                "verificar el OWNER (migracion 019).")
        print(f"[analyze] estadisticas actualizadas y VERIFICADAS sobre "
              f"{len(PARSED_TABLES)} tablas t={round(time.perf_counter() - t_analyze, 2)}s")
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    _cur_alloc, peak_alloc = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_seconds = round(time.perf_counter() - t_start, 3)
    peak_mb = round(peak_alloc / 1024 / 1024, 1)

    outcomes: dict[str, int] = defaultdict(int)
    for res in filing_results:
        outcomes[res["outcome"]] += 1
    facts_total = sum(len(res["facts_rows"]) for res in filing_results)
    ctx_total = sum(len(res["ctx_rows"]) for res in filing_results)
    units_total = sum(len(res["unit_rows"]) for res in filing_results)
    rels_total = sum(len(res["rel_rows"]) for res in filing_results)
    concepts_total = len(all_concepts)
    custom_tags = sum(1 for row in all_concepts.values() if row[10])
    dim_facts = sum(1 for res in filing_results for row in res["facts_rows"] if row[27])
    nodim_facts = facts_total - dim_facts
    unique_tags = len({qn for res in filing_results for qn in res["fact_index"]})

    per_acc_facts = {res["acc"]: len(res["facts_rows"]) for res in filing_results}
    xbrl_accs = [res["acc"] for res in filing_results if res["outcome"] == "PARSED_XBRL"]
    prexbrl_accs = [res["acc"] for res in filing_results if res["outcome"] == "PRE_XBRL"]
    rejected_accs = [res["acc"] for res in filing_results if res["outcome"] == "REJECTED"]

    checks: list[dict] = []

    ok1 = len(filing_results) == filings_expected and not rejected_accs and not files_bad
    checks.append({"id": "C-S03-001", "blocking": True,
                   "result": "PASS" if ok1 else "FAIL",
                   "detail": (f"conciliacion filings expected->parsed/rejected: "
                              f"filings={len(filing_results)}/{filings_expected} "
                              f"PARSED_XBRL={outcomes['PARSED_XBRL']} PRE_XBRL={outcomes['PRE_XBRL']} "
                              f"REJECTED={outcomes['REJECTED']} inputs_corruptos={len(files_bad)}"),
                   "evidence": {"filings_expected": filings_expected,
                                "filings_processed": len(filing_results),
                                "outcomes": dict(outcomes), "rejected_accessions": rejected_accs,
                                "bad_inputs": [{"raw_path": b["raw_path"], "reason": b["reason"]}
                                               for b in files_bad]}})

    dangling_ctx = dangling_unit = prov_viol = 0
    with engine.connect() as conn:
        # Bulk insert recien commiteado: sin esto el planner usa estadisticas
        # viejas/inexistentes y el NOT EXISTS de abajo cae a seq scan pese a
        # los indices de 006_s03_context_unit_indexes.sql, superando el
        # statement_timeout de 120s (visto en corridas reales sobre ~67k facts).
        conn.execute(text("ANALYZE parsed.facts, parsed.contexts, parsed.units"))
        dangling_ctx = conn.execute(text("""
            SELECT count(*) FROM parsed.facts f
             WHERE f.run_id=:r AND f.context_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM parsed.contexts c
                                WHERE c.run_id=f.run_id AND c.accession_number=f.accession_number
                                  AND c.context_id=f.context_id)"""), {"r": run.run_id}).scalar()
        dangling_unit = conn.execute(text("""
            SELECT count(*) FROM parsed.facts f
             WHERE f.run_id=:r AND f.unit_ref IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM parsed.units u
                                WHERE u.run_id=f.run_id AND u.accession_number=f.accession_number
                                  AND u.unit_ref=f.unit_ref)"""), {"r": run.run_id}).scalar()
        prov_viol = conn.execute(text("""
            SELECT count(*) FROM parsed.facts WHERE run_id=:r AND
              (source_hash IS NULL OR source_path IS NULL OR source_file IS NULL
               OR source_kind IS NULL OR entity_id IS NULL OR cik IS NULL
               OR accession_number IS NULL OR accession_number='N/A')"""),
            {"r": run.run_id}).scalar()

    checks.append({"id": "C-S03-002", "blocking": True,
                   "result": "PASS" if not files_bad and len(files_ok) == len(s02_files) else "FAIL",
                   "detail": (f"integridad RAW de entrada: sha256 re-verificado contra download_log "
                              f"S02 ok={len(files_ok)}/{len(s02_files)} fallidos={len(files_bad)}"),
                   "evidence": {"files_ok": len(files_ok), "files_total": len(s02_files),
                                "bad": [{"raw_path": b["raw_path"], "reason": b["reason"]}
                                        for b in files_bad]}})
    checks.append({"id": "C-S03-003", "blocking": True,
                   "result": "PASS" if prov_viol == 0 and facts_total > 0 else "FAIL",
                   "detail": ("provenance completo fact->source_file->sha256->accession->"
                              f"entity->run: violaciones={prov_viol} sobre facts={facts_total}"),
                   "evidence": {"provenance_violations": prov_viol, "facts_total": facts_total}})
    empty_xbrl = [a for a in xbrl_accs if per_acc_facts[a] == 0]
    checks.append({"id": "C-S03-004", "blocking": True,
                   "result": "PASS" if not empty_xbrl and outcomes["PARSED_XBRL"] >= 9 else "FAIL",
                   "detail": (f"cobertura XBRL: filings con hechos extraidos={len(xbrl_accs)} "
                              f"(esperado>=9, eras FY2017-FY2025); sin hechos: {empty_xbrl or 'ninguno'}"),
                   "evidence": {"filings_with_facts": xbrl_accs, "empty": empty_xbrl,
                                "expected_min": 9}})
    unclassified_pre = [a for a in prexbrl_accs
                        if a not in {p[3] for p in px_rows}]
    checks.append({"id": "C-S03-005", "blocking": True,
                   "result": "PASS" if not unclassified_pre else "FAIL",
                   "detail": (f"era pre-XBRL declarada explicitamente: filings={len(prexbrl_accs)}, "
                              f"registrados como PRE_XBRL={len(px_rows)}, "
                              f"sin registrar: {unclassified_pre or 'ninguno'}"),
                   "evidence": {"pre_xbrl_registered": len(px_rows), "missing": unclassified_pre}})
    checks.append({"id": "C-S03-006", "blocking": True,
                   "result": "PASS" if dangling_ctx == 0 and dangling_unit == 0 else "FAIL",
                   "detail": (f"integridad referencial parser-output: context_refs colgantes="
                              f"{dangling_ctx}, unit_refs colgantes={dangling_unit}"),
                   "evidence": {"dangling_context_refs": dangling_ctx,
                                "dangling_unit_refs": dangling_unit}})
    both_n = sum(1 for r in cmp_rows if r[5] and r[6])
    cf_only = sum(1 for r in cmp_rows if r[5] and not r[6])
    fil_only = sum(1 for r in cmp_rows if r[6] and not r[5])
    checks.append({"id": "C-S03-007", "blocking": True,
                   "result": "PASS" if cmp_rows and len(cmp_rows) >= len(set(cf_index) | set(filing_agg)) else "FAIL",
                   "detail": (f"comparacion CompanyFacts vs filing generada: conceptos={len(cmp_rows)} "
                              f"(ambos={both_n}, solo_cf={cf_only}, solo_filing={fil_only})"),
                   "evidence": {"rows": len(cmp_rows), "cf_concepts": len(cf_index),
                                "filing_concepts": len(filing_agg)}})

    perf = {"total_seconds": total_seconds, "peak_memory_mb": peak_mb,
            "payload_files_processed": sum(res["metrics"]["payload_files"] for res in filing_results),
            "files_per_sec": round(sum(res["metrics"]["payload_files"] for res in filing_results) / total_seconds, 2) if total_seconds else 0,
            "facts_per_sec": round(facts_total / total_seconds, 1) if total_seconds else 0,
            "per_filing_seconds": {res["acc"]: res["seconds"] for res in filing_results}}
    checks.append({"id": "C-S03-009", "blocking": False,
                   "result": "PASS" if total_seconds > 0 and facts_total > 0 else "WARN",
                   "detail": (f"performance: total={total_seconds}s facts/s={perf['facts_per_sec']} "
                              f"archivos/s={perf['files_per_sec']} memoria_pico={peak_mb}MB"),
                   "evidence": perf})

    metrics_ctx = {
        "outcomes": dict(outcomes), "filings_expected": filings_expected,
        "filings_processed": len(filing_results), "facts_total": facts_total,
        "ctx_total": ctx_total, "units_total": units_total, "rels_total": rels_total,
        "concepts_total": concepts_total, "custom_tags": custom_tags,
        "standard_tags": concepts_total - custom_tags, "unique_tags": unique_tags,
        "dim_facts": dim_facts, "nodim_facts": nodim_facts,
        "parse_errors": len(err_rows), "repeated_tag_occurrences": facts_total - unique_tags,
        "pre_xbrl": len(px_rows), "companyfacts_compare_rows": len(cmp_rows),
        "total_seconds": total_seconds, "peak_mb": peak_mb,
        "facts_per_sec": perf["facts_per_sec"], "s02_run_id": s02_run_id,
    }
    outputs = write_outputs(run, filing_results, px_rows, cmp_rows, err_rows,
                            checks, metrics_ctx, perf, per_acc_facts)
    manifest_path = write_manifest(run, s02_run_id, files_ok, outputs)

    missing_or_empty = [str(p) for p in list(outputs.values()) + [manifest_path]
                        if not p.exists() or p.stat().st_size == 0]
    checks.append({"id": "C-S03-008", "blocking": True,
                   "result": "PASS" if not missing_or_empty else "FAIL",
                   "detail": (f"outputs escritos y no vacios ({len(outputs)+1} artefactos); "
                              f"problemas: {missing_or_empty or 'ninguno'}"),
                   "evidence": {Path(p).name: (p.stat().st_size if Path(p).exists() else 0)
                                for p in list(outputs.values()) + [manifest_path]}})

    blocked = [c for c in checks if c["result"] == "FAIL" and c["blocking"]]
    gate = GateStatus.BLOCK if blocked else GateStatus.PASS

    assert_transition(cur_state, StageState.VALIDATING)
    edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cur_state,
                                new_state=StageState.VALIDATING)
    end_path = [StageState.FAILED] if gate is GateStatus.BLOCK else [StageState.PASSED, StageState.CHECKPOINTED]
    cursor = StageState.VALIDATING
    for nxt in end_path:
        assert_transition(cursor, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cursor, new_state=nxt,
                                    gate_status=gate if nxt == end_path[-1] else None,
                                    gate_reasons=[c["detail"] for c in blocked])
        cursor = nxt

    parsed_n = outcomes["PARSED_XBRL"] + outcomes["PRE_XBRL"]
    report = StageReport(
        stage=STAGE_ID, run_id=run.run_id, mode=settings.mode,
        started_at=started_at, finished_at=utc_now_iso(), gate=gate,
        input_checkpoint_id=f"S02:{s02_run_id}", input_rows=len(s02_files),
        expected=filings_expected, parsed=parsed_n, rejected=outcomes["REJECTED"] + len(files_bad),
        rejected_by_reason={"REJECTED_FILING": outcomes["REJECTED"], "BAD_INPUT": len(files_bad)},
        hash_in=hashlib.sha256(f"S02:{s02_run_id}".encode()).hexdigest(),
        hash_out=hashlib.sha256(json.dumps(
            {"facts": facts_total, "contexts": ctx_total, "units": units_total,
             "concepts": concepts_total, "relations": rels_total}, sort_keys=True).encode()).hexdigest(),
        gate_reasons=[c["detail"] for c in blocked],
        checks=[{"id": c["id"], "result": c["result"]} for c in checks],
        nulls_count=prov_viol, parser_version=PARSER_VERSION, script=SCRIPT,
        git_commit=run.git_commit,
    )
    report.validate()

    # F-029 — hash_out basado en CONTENIDO, no en conteos.
    # `hashout-v1` (los 5 conteos) queda como `hash_out_v1` para poder contrastar
    # con los checkpoints historicos, pero el hash que representa la salida de la
    # etapa pasa a ser el digest de contenido. Ver docs/architecture/HASH_OUT_CONTRACT.md
    with engine.connect() as conn:
        h2 = hashout.hash_out(conn, list(PARSED_TABLES[:5]))
    report_json = json.loads(report.to_json())
    report_json["integrity"]["hash_out_v1"] = report_json["integrity"]["hash_out"]
    report_json["integrity"]["hash_out"] = h2["hash_out"]
    report_json["integrity"]["hash_spec"] = h2["hash_spec"]
    report_json["integrity"]["por_tabla"] = h2["por_tabla"]
    print(f"[hash_out] {h2['hash_spec']} = {h2['hash_out']}")

    with engine.begin() as conn:
        conn.execute(text("UPDATE engine.stage_runs SET report = CAST(:r AS JSONB), finished_at=now(), "
                          "gate_status=:g WHERE id=(SELECT max(id) FROM engine.stage_runs "
                          "WHERE run_id=:run AND stage_id=:s)"),
                     {"r": json.dumps(report_json, ensure_ascii=False), "g": gate.value,
                      "run": run.run_id, "s": STAGE_ID})
        if gate is not GateStatus.BLOCK:
            # ON CONFLICT sobre ux_checkpoints_reuse: re-corrida con mismo
            # input+code+contract es un "checkpoint hit" por diseño
            # (STAGE_GRAPH.md S4), no un error. parsed.* ya es replace-all,
            # asi que el checkpoint debe apuntar a la corrida mas reciente.
            conn.execute(text("INSERT INTO engine.checkpoints "
                              "(checkpoint_id, stage_id, run_id, input_hash, code_version, contract_version, artifact_ref) "
                              "VALUES (:cid,:s,:r,:ih,:cv,:ctv,:ref) "
                              "ON CONFLICT (stage_id, input_hash, code_version, contract_version) "
                              "DO UPDATE SET checkpoint_id=EXCLUDED.checkpoint_id, run_id=EXCLUDED.run_id, "
                              "artifact_ref=EXCLUDED.artifact_ref, created_at=now()"),
                         {"cid": run.run_id[:16] + "-s03", "s": STAGE_ID, "r": run.run_id,
                          "ih": report.hash_in, "cv": PIPELINE_VERSION, "ctv": "parsed-v1",
                          "ref": "pg://parsed.* + fs://outputs/docs/fase_s03"})
    # F-031: el estado lo fija el cuerpo y lo PERSISTE run_scope en su `finally`.
    run.status = "OK" if gate is GateStatus.PASS else "BLOCKED"
    if punto_falla == "FIN":
        raise RuntimeError("fallo simulado (F-031): despues del checkpoint")

    validation = {
        "run_id": run.run_id, "git_commit": run.git_commit, "mode": settings.mode,
        "stage": STAGE_ID, "parser_version": PARSER_VERSION,
        "input_checkpoint": {"stage": "S02_fetch", "run_id": s02_run_id},
        "gate": gate.value, "verdict": "READY_FOR_S04" if gate is GateStatus.PASS else "BLOCKED_S04",
        "checks": checks,
        "totals": metrics_ctx,
        "performance": perf,
        "per_filing": [{"acc": res["acc"], "form": res["meta"].get("form"),
                        "filing_date": res["meta"].get("filing_date"),
                        "period": res["meta"].get("period"), "outcome": res["outcome"],
                        "facts": len(res["facts_rows"]), "contexts": len(res["ctx_rows"]),
                        "units": len(res["unit_rows"]), "relations": len(res["rel_rows"]),
                        "errors": len(res["errors"]), "seconds": res["seconds"]}
                       for res in filing_results],
    }
    val_path = OUT_DIR / "S03_VALIDATION.json"
    val_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")

    verdict = "READY_FOR_S04" if gate is GateStatus.PASS else "BLOCKED_S04"
    print(json.dumps({
        "gate": gate.value, "verdict": verdict,
        "filings": {"expected": filings_expected, **dict(outcomes)},
        "totals": {"facts": facts_total, "contexts": ctx_total, "units": units_total,
                   "relations": rels_total, "conceptos": concepts_total,
                   "custom": custom_tags, "standard": concepts_total - custom_tags,
                   "facts_dimensionales": dim_facts, "facts_sin_dimension": nodim_facts,
                   "pre_xbrl": len(px_rows), "errores_parseo": len(err_rows)},
        "performance": {"segundos": total_seconds, "facts_por_segundo": perf["facts_per_sec"],
                        "memoria_pico_mb": peak_mb},
        "outputs": {k: str(v) for k, v in outputs.items()} | {"S03_VALIDATION.json": str(val_path)},
    }, indent=2, ensure_ascii=False))
    print("--- conciliacion ---")
    print(f"filings_expected = {filings_expected}")
    print(f"filings_ok       = {parsed_n} ({dict(outcomes)})")
    print(f"filings_rejected = {outcomes['REJECTED'] + len(files_bad)}")
    print(f"gate             = {gate.value} -> {verdict}")
    return 0 if gate is GateStatus.PASS else 1


def write_outputs(run, filing_results, px_rows, cmp_rows, err_rows, checks,
                  metrics: dict, perf: dict, per_acc_facts: dict) -> dict[str, Path]:
    from openpyxl import Workbook

    paths: dict[str, Path] = {}

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("01_Summary")
    ws.append(["metrica", "valor"])
    for k, v in metrics.items():
        ws.append([k, j(v) if isinstance(v, (dict, list)) else v])

    ws = wb.create_sheet("02_Filings")
    ws.append(["accession", "form", "filing_date", "period", "outcome", "facts",
               "contexts", "units", "relations", "errors", "segundos"])
    for res in filing_results:
        ws.append([res["acc"], res["meta"].get("form"), res["meta"].get("filing_date"),
                   res["meta"].get("period"), res["outcome"], len(res["facts_rows"]),
                   len(res["ctx_rows"]), len(res["unit_rows"]), len(res["rel_rows"]),
                   len(res["errors"]), res["seconds"]])

    seen: dict[str, list] = {}
    for res in filing_results:
        for qn, fi in res["fact_index"].items():
            if qn not in seen:
                ns, _, tag = qn.rpartition("#")
                seen[qn] = [qn, qn.split("#")[0].rsplit("/", 1)[-1], ns, tag,
                            not any(s in qn for s in STANDARD_HINTS), fi["obs"]]
            else:
                seen[qn][5] += fi["obs"]
    ws = wb.create_sheet("03_Tags")
    ws.append(["qname", "taxonomy", "namespace", "tag", "custom", "ocurrencias"])
    for row in sorted(seen.values(), key=lambda r: r[0]):
        ws.append(row)

    ws = wb.create_sheet("04_Facts")
    ws.append(FACT_COLS)
    for res in filing_results:
        for row in res["facts_rows"]:
            ws.append([str(v) if isinstance(v, Decimal) else v for v in row])

    ws = wb.create_sheet("05_Contexts")
    ws.append(CTX_COLS)
    for res in filing_results:
        for row in res["ctx_rows"]:
            ws.append(list(row))

    ws = wb.create_sheet("06_Dimensions")
    ws.append(["accession", "context_id", "dimension", "miembro", "typed"])
    for res in filing_results:
        for row in res["ctx_rows"]:
            for d in json.loads(row[10]):
                ws.append([row[2], row[3], d.get("dimension"), d.get("member"), False])
            for d in json.loads(row[11]) if row[11] else []:
                ws.append([row[2], row[3], d.get("dimension"), (d.get("content") or "")[:150], True])

    ws = wb.create_sheet("07_Units")
    ws.append(UNIT_COLS)
    for res in filing_results:
        for row in res["unit_rows"]:
            ws.append(list(row))

    taxonomy_groups: dict[str, int] = defaultdict(int)
    for row in seen.values():
        taxonomy_groups[row[1]] += 1
    ws = wb.create_sheet("08_Taxonomies")
    ws.append(["taxonomy", "tags_distintos", "custom"])
    for tax, cnt in sorted(taxonomy_groups.items()):
        ws.append([tax, cnt, not any(s == tax for s in STANDARD_HINTS)])

    ws = wb.create_sheet("09_Labels")
    ws.append(REL_COLS)
    ws.append(["-- linkbase LABEL: ver tambien hoja 08 para labels de schema --"])
    for res in filing_results:
        for row in res["rel_rows"]:
            if row[3] == "LABEL":
                ws.append(list(row))

    ws = wb.create_sheet("10_Presentation")
    ws.append(REL_COLS)
    for res in filing_results:
        for row in res["rel_rows"]:
            if row[3] == "PRESENTATION":
                ws.append(list(row))

    ws = wb.create_sheet("11_Calculation")
    ws.append(REL_COLS)
    for res in filing_results:
        for row in res["rel_rows"]:
            if row[3] == "CALCULATION":
                ws.append(list(row))

    ws = wb.create_sheet("12_Definition")
    ws.append(REL_COLS)
    for res in filing_results:
        for row in res["rel_rows"]:
            if row[3] == "DEFINITION":
                ws.append(list(row))

    ws = wb.create_sheet("13_CompanyFacts")
    ws.append(CMP_COLS)
    for row in cmp_rows:
        ws.append(list(row))

    ws = wb.create_sheet("14_PreXBRL")
    ws.append(PX_COLS)
    for row in px_rows:
        ws.append(list(row))

    ws = wb.create_sheet("15_Provenance")
    ws.append(["accession", "source_kind", "source_file", "sha256", "run_id"])
    emitted = set()
    for res in filing_results:
        for row in res["facts_rows"][:1]:
            pass
        for row in res["ctx_rows"][:1]:
            key = (row[2], row[-2], row[-1])
            if key not in emitted:
                emitted.add(key)
                ws.append([row[2], "INSTANCE_OR_ZIP", row[-2], row[-1], run.run_id])

    ws = wb.create_sheet("16_Reconciliation")
    ws.append(["nivel", "clave", "valor"])
    ws.append(["RAW_input", "archivos_s02_verificados", metrics["s02_run_id"]])
    ws.append(["filings", "esperados", metrics["filings_expected"]])
    ws.append(["filings", "procesados", metrics["filings_processed"]])
    ws.append(["filings", "PARSED_XBRL", metrics["outcomes"].get("PARSED_XBRL", 0)])
    ws.append(["filings", "PRE_XBRL", metrics["pre_xbrl"]])
    ws.append(["filings", "RECHAZADOS", metrics["outcomes"].get("REJECTED", 0)])
    coverage = round(100.0 * (metrics["outcomes"].get("PARSED_XBRL", 0) + metrics["pre_xbrl"])
                     / max(metrics["filings_expected"], 1), 2)
    ws.append(["cobertura", "porcentaje_filings_procesados", f"{coverage}%"])
    for acc, n in sorted(per_acc_facts.items()):
        ws.append(["facts_por_filing", acc, n])

    ws = wb.create_sheet("17_Validation")
    ws.append(["check_id", "blocking", "resultado", "detalle"])
    for c in checks:
        ws.append([c["id"], c["blocking"], c["result"], c["detail"]])
    ws.append(["NOTA", "", "",
               "C-S03-008 verifica la existencia/no-vacidad de este mismo Excel y del MANIFEST; su resultado queda registrado en S03_VALIDATION.json"])

    ws = wb.create_sheet("18_Errors")
    ws.append(ERR_COLS)
    for row in err_rows:
        ws.append(list(row))

    excel_path = OUT_DIR / "S03_YPF_PARSE_AUDIT.xlsx"
    wb.save(excel_path)
    paths["S03_YPF_PARSE_AUDIT.xlsx"] = excel_path
    paths["S03_PARSE_REPORT.md"] = write_report_md(run, metrics, perf, checks)
    return paths


def write_report_md(run, metrics: dict, perf: dict, checks: list[dict]) -> Path:
    lines = [
        "# S03 PARSE — Reporte de ejecución (YPF GOLDEN CASE)",
        "",
        f"- run_id: `{run.run_id}`",
        f"- git_commit: `{run.git_commit}`",
        f"- input checkpoint: `S02:{metrics['s02_run_id']}`",
        f"- generado: {utc_now_iso()}",
        "",
        "## Resumen ejecutivo",
        "",
        f"- Filings procesados: {metrics['filings_processed']}/{metrics['filings_expected']} "
        f"(PARSED_XBRL={metrics['outcomes'].get('PARSED_XBRL', 0)}, "
        f"PRE_XBRL={metrics['pre_xbrl']}, REJECTED={metrics['outcomes'].get('REJECTED', 0)})",
        f"- Facts extraidos: {metrics['facts_total']:,}",
        f"- Contexts: {metrics['ctx_total']:,} | Units: {metrics['units_total']:,}",
        f"- Conceptos inventariados: {metrics['concepts_total']:,} "
        f"(custom={metrics['custom_tags']:,}, standard={metrics['standard_tags']:,})",
        f"- Relations (linkbases): {metrics['rels_total']:,}",
        f"- Facts con dimensiones: {metrics['dim_facts']:,} | sin dimensiones: {metrics['nodim_facts']:,}",
        f"- Errores de parseo registrados: {metrics['parse_errors']}",
        f"- Cobertura filings: {round(100.0 * (metrics['outcomes'].get('PARSED_XBRL', 0) + metrics['pre_xbrl']) / max(metrics['filings_expected'], 1), 2)}%",
        "",
        "## Performance",
        "",
        f"- Tiempo total: {perf['total_seconds']}s | facts/s: {perf['facts_per_sec']} "
        f"| memoria pico aprox: {perf['peak_memory_mb']} MB",
        "",
        "## Checks",
        "",
        "| check | blocking | resultado | detalle |",
        "|---|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c['id']} | {c['blocking']} | {c['result']} | {c['detail']} |")
    lines += [
        "",
        "## Decisiones tomadas (no silenciosas)",
        "",
        "1. Inline XBRL (.htm) NO se parsea como fuente de hechos: los filings iXBRL tienen su instancia canónica dentro de `-xbrl.zip`; los .htm quedan documentados como fuente duplicada no parseada.",
        "2. Los hechos textuales/nil se preservan con `value_numeric=NULL`; NO se descartan.",
        "3. NO se deduplica nada (norma S03); ocurrencias repetidas por tag quedan como métrica informativa.",
        "4. Era FY2001–FY2017 clasificada `PRE_XBRL` con nota explícita; conversión automática HTML→XBRL prohibida.",
        "5. Capa `parsed.*` es derivada y determinista: cada corrida reemplaza por entidad (delete+insert transaccional); la verdad permanece en RAW.",
        "6. Conceptos observados en instancias sin esquema local se registran con `source_schema='INSTANCE_OBSERVED'` — nunca se descartan.",
        "",
        "## Veredicto",
        "",
        "Ver `S03_VALIDATION.json` → campo `verdict` (`READY_FOR_S04` / `BLOCKED_S04`).",
        "",
    ]
    path = OUT_DIR / "S03_PARSE_REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_manifest(run, s02_run_id: str, inputs: list[dict], outputs: dict[str, Path]) -> Path:
    manifest = {
        "run_id": run.run_id, "git_commit": run.git_commit,
        "pipeline_version": PIPELINE_VERSION, "parser_version": PARSER_VERSION,
        "script": SCRIPT, "generated_at": utc_now_iso(),
        "input": {"checkpoint": f"S02:{s02_run_id}", "files_consumed": len(inputs),
                  "bytes_total": sum(i["bytes"] or 0 for i in inputs)},
        "outputs": [{"file": p.name, "sha256": sha256_bytes(p.read_bytes()),
                     "bytes": p.stat().st_size} for p in outputs.values()],
        "nota": "S03_VALIDATION.json se escribe posterior al manifiesto (contiene el resultado del gate completo).",
    }
    path = OUT_DIR / "S03_MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
