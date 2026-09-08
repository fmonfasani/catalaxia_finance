from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from engine import db as edb
from engine.config import REPO_ROOT, load_settings
from engine.fetch import Fetcher, RAW_ROOT, raw_existing_hash, sha256_bytes, write_raw_new
from engine.report import StageReport, utc_now_iso
from engine.states import GateStatus, StageState, assert_transition

STAGE_ID = "S02_fetch"
PIPELINE_VERSION = "s2-fetch-v1"
SCRIPT = "scripts/engine/s02_fetch_ypf.py"
OUT_DIR = REPO_ROOT / "outputs" / "docs" / "fase_s02"
SCOPE_RULE = "FAST:YPF:v1"
GOLDEN_CIK = "0000904851"
# El emisor y el formulario dejan de estar fijados en el codigo. Los defaults
# reproducen exactamente el comportamiento homologado (YPF, 20-F, sin tope);
# `--cik/--forms/--max-filings` permiten ingerir el resto del universo.
#
# El formulario NO es un detalle: un emisor extranjero presenta 20-F y uno
# domestico 10-K. Con el filtro fijo en 20-F, AAPL/MSFT/NVDA daban 0 filings.
FORMS = ("20-F", "20-F/A")
MAX_FILINGS = 0          # 0 = sin tope
LEGACY_FORBIDDEN_CIKS = {"0001104659", "0001069595", "0001113245", "0001082722"}
DATA_SEC = "https://data.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

KEEP_EXT = {".xml", ".xsd", ".htm", ".html"}
LINKBASE_SUFFIXES = {"_pre.xml": "LINKBASE_PRE", "_cal.xml": "LINKBASE_CAL",
                     "_defr.xml": "LINKBASE_DEF", "_def.xml": "LINKBASE_DEF",
                     "_lab.xml": "LINKBASE_LAB"}
R_FILE = re.compile(r"^R\d+\.(htm|html)$", re.IGNORECASE)
INSTANCE_RE = re.compile(r"-((19|20)\d{6})(_htm)?\.xml$", re.IGNORECASE)
XBRL_ZIP_RE = re.compile(r"-xbrl\.zip$", re.IGNORECASE)
TS_FMT = "%Y%m%dT%H%M%SZ"


def classify_file(name: str, acc_nodash: str) -> str | None:
    low = name.lower()
    if low == f"{acc_nodash}-index.htm":
        return "FILING_INDEX"
    if low == "filingsummary.xml":
        return "FILING_SUMMARY"
    if XBRL_ZIP_RE.search(low):
        return "XBRL_PACKAGE_ZIP"
    for suf, kind in LINKBASE_SUFFIXES.items():
        if low.endswith(suf):
            return kind
    if low.endswith(".xsd"):
        return "XBRL_SCHEMA"
    if INSTANCE_RE.search(low):
        return "XBRL_INSTANCE"
    if low.endswith((".htm", ".html")):
        return "DOC_HTM"
    return "XBRL_OTHER"


def is_xbrl_payload(name: str) -> bool:
    kind = classify_file(name, "x")
    return kind in {"XBRL_INSTANCE", "XBRL_SCHEMA", "LINKBASE_PRE", "LINKBASE_CAL",
                    "LINKBASE_DEF", "LINKBASE_LAB", "XBRL_OTHER", "XBRL_PACKAGE_ZIP"} or \
        name.lower() == "filingsummary.xml"


def resolve_entity_from_s01(engine) -> dict:
    with engine.connect() as conn:
        ents = conn.execute(
            text("SELECT entity_id, legal_name, country, cik, cuit FROM identity.entities "
                 "WHERE cik = :c"), {"c": GOLDEN_CIK}).mappings().all()
        if len(ents) != 1:
            raise RuntimeError(f"S01 debía resolver exactamente 1 entidad para CIK {GOLDEN_CIK}, hay {len(ents)}")
        ent = dict(ents[0])
        idents = conn.execute(
            text("SELECT id_type, id_value, marketplace FROM identity.identifiers "
                 "WHERE entity_id=:e AND status='ACTIVE' ORDER BY id_type, marketplace"),
            {"e": ent["entity_id"]}).all()
    ent["identifiers"] = [dict(r._mapping) for r in idents]
    return ent


def parse_submissions(payload: dict) -> tuple[list[dict], list[str]]:
    filings: dict[str, dict] = {}
    extra_pages: list[str] = []
    blocks = [payload.get("filings", {}).get("recent", {})]
    for f in payload.get("filings", {}).get("files", []):
        extra_pages.append(f["name"])
    for block in blocks:
        for i, acc in enumerate(block.get("accessionNumber", [])):
            form = block.get("form", [""] * len(block.get("accessionNumber", [])))[i]
            if form not in FORMS:
                continue
            filings[acc] = {
                "acc": acc,
                "acc_nodash": acc.replace("-", ""),
                "form": form,
                "filing_date": block.get("filingDate", [""] * len(block.get("accessionNumber", [])))[i],
                "period": block.get("reportDate", [""] * len(block.get("accessionNumber", [])))[i],
                "primary_doc": block.get("primaryDocument", [""] * len(block.get("accessionNumber", [])))[i],
            }
    return sorted(filings.values(), key=lambda f: f["filing_date"], reverse=True), extra_pages


def parse_index_hrefs(index_payload: str, acc_nodash: str) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    try:
        payload = json.loads(index_payload)
        names = [str(e.get("name") or "") for e in (payload.get("directory") or {}).get("item") or []]
    except json.JSONDecodeError:
        names = [unquote(Path(urlparse(h).path).name) for h in re.findall(r'href="([^"]+)"', index_payload)]
    chrome = {f"{acc_nodash}-index.htm", f"{acc_nodash}-index.html",
              f"{acc_nodash}-index-headers.html", "index.json"}
    for base in names:
        base = base.strip()
        if not base or "/" in base or "\\" in base or ".." in base:
            continue
        if Path(base).suffix.lower() not in KEEP_EXT and not XBRL_ZIP_RE.search(base):
            continue
        if R_FILE.match(base) or base.lower() in chrome:
            continue
        if base.lower().startswith("graphics"):
            continue
        seen.setdefault(base, None)
    return list(seen.keys())


class Log:
    def __init__(self, engine, run_id: str, stage_run_id: int):
        self.engine = engine
        self.run_id = run_id
        self.stage_run_id = stage_run_id
        self.rows: list[dict] = []

    def insert(self, rec: dict) -> None:
        self.rows.append(rec)
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO fetch_raw.download_log
                (run_id, stage_run_id, stage_id, entity_id, cik, accession_number, form_type,
                 filing_date, period_of_report, source, endpoint, request_kind, critical,
                 raw_path, http_status, content_type, bytes, sha256, downloaded_at,
                 result, fail_reason, attempt)
                VALUES (:run_id,:stage_run_id,:stage_id,:entity_id,:cik,:acc,:form,
                 :filing_date,:period,'SEC_EDGAR',:endpoint,:kind,:critical,
                 :raw_path,:http_status,:content_type,:bytes,:sha256,
                 COALESCE(CAST(:downloaded_at AS timestamptz), now()), :result,:fail_reason,:attempt)
            """), rec)


def make_rec(run_id: str, stage_run_id: int, ent: dict, item: dict, res: dict,
             rel_path: str | None, content_sha: str | None, size: int | None,
             result: str, ts: str | None) -> dict:
    return {
        "run_id": run_id, "stage_run_id": stage_run_id, "stage_id": STAGE_ID,
        "entity_id": ent["entity_id"], "cik": GOLDEN_CIK,
        "acc": item.get("acc") or "N/A", "form": item.get("form"),
        "filing_date": item.get("filing_date"), "period": item.get("period"),
        "endpoint": item["url"], "kind": item["kind"], "critical": item.get("critical", False),
        "raw_path": rel_path, "http_status": res.get("http_status"),
        "content_type": res.get("content_type"), "bytes": size, "sha256": content_sha,
        "downloaded_at": ts, "result": result, "fail_reason": res.get("error"), "attempt": res.get("attempt", 1),
    }


def run_item(log: Log, fetcher: Fetcher, ent: dict, item: dict) -> dict:
    res = fetcher.fetch(item["url"])
    if res["http_status"] != 200 or res["content"] is None:
        rec = make_rec(log.run_id, log.stage_run_id, ent, item, res, None, None, None, "FAILED", None)
        log.insert(rec)
        return rec
    content = res["content"]
    sha = sha256_bytes(content)
    prev = raw_existing_hash(item["rel_path"]) if item.get("rel_path") else None
    if prev == sha:
        rec = make_rec(log.run_id, log.stage_run_id, ent, item, res, item["rel_path"], sha,
                       len(content), "SIN_CAMBIOS", utc_now_iso())
        log.insert(rec)
        return rec
    rel_path = item["rel_path"]
    stored_rel = rel_path
    if prev is not None and prev != sha:
        p = Path(rel_path)
        stored_rel = str(p.with_name(f"{p.stem}__conflict_{datetime.now(timezone.utc).strftime(TS_FMT)}{p.suffix}"))
        rec_partial = make_rec(log.run_id, log.stage_run_id, ent, item, res, stored_rel, sha,
                               len(content), "DOWNLOADED", utc_now_iso())
        rec_partial["fail_reason"] = f"CONFLICT_VERSIONED: hash local {prev[:12]} difiere de remoto {sha[:12]}"
        write_raw_new(stored_rel, content)
        log.insert(rec_partial)
        return rec_partial
    write_raw_new(rel_path, content)
    rec = make_rec(log.run_id, log.stage_run_id, ent, item, res, stored_rel, sha,
                   len(content), "DOWNLOADED", utc_now_iso())
    log.insert(rec)
    return rec


def main() -> int:
    global GOLDEN_CIK, FORMS, MAX_FILINGS, SCOPE_RULE
    ap = argparse.ArgumentParser(description="S02 fetch SEC (por CIK)")
    ap.add_argument("--cik", default=GOLDEN_CIK, help="CIK objetivo, 10 digitos")
    ap.add_argument("--forms", default=",".join(FORMS),
                    help="formularios anuales a ingerir (20-F para emisores extranjeros, "
                         "10-K para domesticos)")
    ap.add_argument("--max-filings", type=int, default=MAX_FILINGS,
                    help="tope de filings mas recientes; 0 = todos")
    args = ap.parse_args()
    GOLDEN_CIK = args.cik.zfill(10)
    FORMS = tuple(f.strip() for f in args.forms.split(",") if f.strip())
    MAX_FILINGS = args.max_filings
    if GOLDEN_CIK != "0000904851":
        SCOPE_RULE = f"FAST:CIK{GOLDEN_CIK}:{'|'.join(FORMS)}:v1"

    settings = load_settings()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[config] target={settings.describe()} scope={SCOPE_RULE}")
    engine = edb.get_engine(settings)
    applied = edb.apply_migrations(engine)
    print(f"[migrations] aplicadas ahora: {applied or '(ninguna nueva)'}")


    # F-050: el cierre va en `finally` (run_scope). Antes, `start_run` abria
    # aca y `finish_run` cerraba decenas de lineas mas abajo: cualquier
    # excepcion en el medio dejaba la corrida en RUNNING para siempre. Es el
    # mismo patron que F-031 aplico a S03 y F-040 a C3.
    huerfanas = edb.corridas_huerfanas(engine)
    if huerfanas:
        print(f"[huerfanas] {len(huerfanas)} corridas previas quedaron en RUNNING:")
        for h in huerfanas[:5]:
            print(f"   {h['run_id'][:12]} {h['pipeline_version']} hace {h['horas']}h")
    with edb.run_scope(engine, settings, PIPELINE_VERSION, stage_id=STAGE_ID) as run:
        print(f"[run] run_id={run.run_id} git={run.git_commit}")
        return _correr(engine, settings, run)


def _correr(engine, settings, run) -> int:
    """Cuerpo de la etapa. Fija `run.status`; NUNCA llama a finish_run (F-050)."""

    prev_state: StageState | None = None
    cur = StageState.PLANNED
    for nxt in (StageState.READY, StageState.RUNNING):
        assert_transition(cur, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=prev_state, new_state=nxt)
        prev_state, cur = cur, nxt
    with engine.connect() as conn:
        stage_run_id = conn.execute(
            text("SELECT id FROM engine.stage_runs WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run.run_id, "s": STAGE_ID}).scalar_one()

    ent = resolve_entity_from_s01(engine)
    print(f"[identity] {ent['entity_id']} | {ent['legal_name']} | tickers="
          f"{[(i['id_value'], i['marketplace']) for i in ent['identifiers'] if i['id_type']=='TICKER']}")
    if ent["cik"] != GOLDEN_CIK:
        raise RuntimeError("identidad inconsistente con golden case")

    cikz = GOLDEN_CIK
    ts_now = utc_now_iso()
    stamp = datetime.now(timezone.utc).strftime(TS_FMT)
    fetcher = Fetcher()
    log = Log(engine, run.run_id, stage_run_id)

    plan: list[dict] = []
    plan.append({"kind": "SUBMISSIONS", "critical": True,
                 "url": f"{DATA_SEC}/submissions/CIK{cikz}.json",
                 "rel_path": f"CIK{cikz}/submissions/CIK{cikz}__{stamp}.json"})
    plan.append({"kind": "COMPANYFACTS", "critical": True,
                 "url": f"{DATA_SEC}/api/xbrl/companyfacts/CIK{cikz}.json",
                 "rel_path": f"CIK{cikz}/companyfacts/CIK{cikz}__{stamp}.json"})

    sub_rec = run_item(log, fetcher, ent, plan[0])
    if sub_rec["result"] == "FAILED":
        raise SystemExit(f"BLOCK: submissions crítica falló: {sub_rec['fail_reason']}")
    cf_rec = run_item(log, fetcher, ent, plan[1])

    sub_json = json.loads((RAW_ROOT / sub_rec["raw_path"]).read_text(encoding="utf-8"))
    filings_list, extra_pages = parse_submissions(sub_json)
    print(f"[discovery] 20-F encontrados={len(filings_list)} páginas submissions extra={len(extra_pages)}")
    filings_by_acc = {f["acc"]: f for f in filings_list}

    page_recs = []
    for name in extra_pages:
        item = {"kind": "SUBMISSIONS_PAGE", "critical": True,
                "url": f"{DATA_SEC}/submissions/{name}",
                "rel_path": f"CIK{cikz}/submissions/{Path(name).stem}__{stamp}.json"}
        plan.append(item)
        page_recs.append(run_item(log, fetcher, ent, item))
        payload = json.loads((RAW_ROOT / page_recs[-1]["raw_path"]).read_text(encoding="utf-8")) \
            if page_recs[-1]["result"] != "FAILED" else {}
        older, _ = parse_submissions({"filings": {"recent": payload, "files": []}})
        for f in older:
            filings_by_acc.setdefault(f["acc"], f)

    warnings_list: list[str] = []
    filings = sorted(filings_by_acc.values(), key=lambda f: f["filing_date"], reverse=True)
    if MAX_FILINGS and len(filings) > MAX_FILINGS:
        print(f"[scope] {len(filings)} filings encontrados; se ingieren los "
              f"{MAX_FILINGS} mas recientes (--max-filings)")
        filings = filings[:MAX_FILINGS]
    for f in filings:
        acc_nd = f["acc_nodash"]
        idx_item = {"kind": "FILING_INDEX", "critical": True, "acc": f["acc"], "form": f["form"],
                    "filing_date": f["filing_date"], "period": f["period"],
                    "url": f"{ARCHIVES}/{int(GOLDEN_CIK)}/{acc_nd}/index.json",
                    "rel_path": f"CIK{cikz}/filings/{acc_nd}/index.json"}
        plan.append(idx_item)
        idx_rec = run_item(log, fetcher, ent, idx_item)
        if idx_rec["result"] == "FAILED":
            continue
        names = parse_index_hrefs((RAW_ROOT / idx_rec["raw_path"]).read_text(encoding="utf-8", errors="replace"), acc_nd)
        xbrl_present = any(is_xbrl_payload(n) for n in names)
        era_note = "" if xbrl_present else " [era sin XBRL: solo index por diseño]"
        print(f"[filing] {f['form']} {f['acc']} filed={f['filing_date']} period={f['period']} "
              f"archivos={len(names)} xbrl={xbrl_present}{era_note}")
        for name in names:
            kind = classify_file(name, acc_nd)
            if kind == "FILING_INDEX":
                continue
            if not xbrl_present:
                continue
            item = {"kind": kind, "critical": kind in {"XBRL_INSTANCE", "XBRL_SCHEMA", "XBRL_PACKAGE_ZIP"},
                    "acc": f["acc"], "form": f["form"], "filing_date": f["filing_date"],
                    "period": f["period"],
                    "url": f"{ARCHIVES}/{int(GOLDEN_CIK)}/{acc_nd}/{name}",
                    "rel_path": f"CIK{cikz}/filings/{acc_nd}/{name}"}
            plan.append(item)
            rec = run_item(log, fetcher, ent, item)
            if rec["fail_reason"] and "CONFLICT" in str(rec["fail_reason"]):
                warnings_list.append(rec["fail_reason"])

    if cf_rec["result"] == "FAILED" and cf_rec["critical"]:
        pass

    rows = log.rows
    successes = [r for r in rows if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS")]
    failures = [r for r in rows if r["result"] == "FAILED"]
    counts_by_result = {}
    for r in rows:
        counts_by_result[r["result"]] = counts_by_result.get(r["result"], 0) + 1
    bytes_total = sum(r["bytes"] or 0 for r in successes)

    ev_failures = [{"endpoint": r["endpoint"], "kind": r["kind"],
                    "http_status": r["http_status"], "error": r["fail_reason"]} for r in failures]

    c1 = {"id": "C-S02-001", "blocking": True}
    failed_critical = [r for r in failures if r["critical"]]
    ok1 = len(rows) == len(plan) and not failed_critical
    c1.update({"result": "PASS" if ok1 else "FAIL",
               "detail": f"conciliación expectedâ†’downloaded: plan={len(plan)} filas={len(rows)} "
                         f"fallidas_críticas={len(failed_critical)} fallidas={len(failures)}",
               "evidence": {"counts_by_result": counts_by_result, "plan_expected": len(plan),
                            "log_rows": len(rows), "failures": ev_failures}})

    verified, mismatches, missing_files = 0, [], []
    for r in successes:
        path = RAW_ROOT / r["raw_path"]
        if not path.exists():
            missing_files.append(r["raw_path"])
            continue
        actual = sha256_bytes(path.read_bytes())
        if actual != r["sha256"]:
            mismatches.append({"raw_path": r["raw_path"], "db": r["sha256"][:12], "disk": actual[:12]})
        else:
            verified += 1
    c2 = {"id": "C-S02-002", "blocking": True,
          "result": "PASS" if not mismatches and not missing_files else "FAIL",
          "detail": f"RAW persistido e integridad sha256 verificada re-leyendo disco: "
                    f"ok={verified}/{len(successes)} mismatch={len(mismatches)} missing={len(missing_files)}"
                    + ("" if not warnings_list else f"; avisos={'|'.join(warnings_list[:3])}"),
          "evidence": {"verified": verified, "total_success": len(successes),
                       "hash_mismatches": mismatches, "missing_on_disk": missing_files,
                       "warnings": warnings_list}}

    with engine.connect() as conn:
        viol = conn.execute(text("""
            SELECT log_id, endpoint FROM fetch_raw.download_log
             WHERE run_id=:r AND result IN ('DOWNLOADED','SIN_CAMBIOS')
               AND (entity_id IS NULL OR cik IS NULL OR source IS NULL OR sha256 IS NULL
                    OR raw_path IS NULL OR endpoint IS NULL OR accession_number IS NULL)
        """), {"r": run.run_id}).all()
    c3 = {"id": "C-S02-003", "blocking": True,
          "result": "PASS" if not viol else "FAIL",
          "detail": f"vinculación completa entidadâ†’cikâ†’fuenteâ†’accessionâ†’urlâ†’shaâ†’run: "
                    f"violaciones={len(viol)} sobre {len(successes)} éxitos",
          "evidence": {"violations": [{"log_id": v[0], "endpoint": v[1]} for v in viol]}}

    starts = sorted(fetcher.request_starts)
    min_gap = None
    if len(starts) >= 2:
        min_gap = round(min(b - a for a, b in zip(starts, starts[1:])), 3)
    c4 = {"id": "C-S02-004", "blocking": True,
          "result": "PASS" if (min_gap is None or min_gap >= fetcher.delay * 0.5) else "FAIL",
          "detail": f"cortesía SEC: secuencial sin paralelo, UA='{fetcher.session.headers['User-Agent']}', "
                    f"delay={fetcher.delay}s, intervalo mínimo entre requests emitidos={min_gap}s",
          "evidence": {"requests_ok": len(successes), "requests_emitidos": len(starts),
                       "min_interval_sec": min_gap,
                       "user_agent": fetcher.session.headers["User-Agent"],
                       "max_attempts": fetcher.max_attempts}}

    with engine.connect() as conn:
        urls = [u for (u,) in conn.execute(text("SELECT endpoint FROM fetch_raw.download_log WHERE run_id=:r"),
                                           {"r": run.run_id})]
    legacy_hits = [u for u in urls if any(c.lstrip("0") in urlparse(u).path.split("/") for c in LEGACY_FORBIDDEN_CIKS)]
    c5 = {"id": "C-S02-005", "blocking": True,
          "result": "PASS" if not legacy_hits else "FAIL",
          "detail": f"S01 consumido exclusivamente (entity_id={ent['entity_id']}, CIK={GOLDEN_CIK}); "
                    f"0 URLs contienen CIKs del catálogo legacy prohibido",
          "evidence": {"entity_id": ent["entity_id"], "endpoints_scanned": len(urls),
                       "legacy_forbidden": sorted(LEGACY_FORBIDDEN_CIKS), "legacy_hits": legacy_hits}}

    checks = [c1, c2, c3, c4, c5]
    blocked = [c for c in checks if c["result"] == "FAIL" and c["blocking"]]
    gate = GateStatus.BLOCK if blocked else GateStatus.PASS

    assert_transition(cur, StageState.VALIDATING)
    edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cur, new_state=StageState.VALIDATING)
    end_path = [StageState.FAILED] if gate is GateStatus.BLOCK else [StageState.PASSED, StageState.CHECKPOINTED]
    cursor = StageState.VALIDATING
    for nxt in end_path:
        assert_transition(cursor, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cursor, new_state=nxt,
                                    gate_status=gate if nxt == end_path[-1] else None,
                                    gate_reasons=[c["detail"] for c in blocked])
        cursor = nxt

    report = StageReport(
        stage=STAGE_ID, run_id=run.run_id, mode=settings.mode,
        started_at=ts_now, finished_at=utc_now_iso(), gate=gate,
        input_checkpoint_id="S01:identity-v1", input_rows=1,
        expected=len(plan), parsed=sum(1 for r in rows if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS")),
        rejected=len(failures), rejected_by_reason={},
        hash_in=hashlib.sha256(f"{ent['entity_id']}|{SCOPE_RULE}".encode()).hexdigest(),
        hash_out=hashlib.sha256(json.dumps(counts_by_result, sort_keys=True).encode()).hexdigest(),
        gate_reasons=[c["detail"] for c in blocked], checks=[{"id": c["id"], "result": c["result"], "detail": c["detail"]} for c in checks],
        nulls_count=0, parser_version="edgar_fetch_v1", script=SCRIPT, git_commit=run.git_commit,
    )
    report.validate()

    with engine.begin() as conn:
        conn.execute(text("UPDATE engine.stage_runs SET report = CAST(:r AS JSONB), finished_at=now(), "
                          "gate_status=:g WHERE id=(SELECT max(id) FROM engine.stage_runs "
                          "WHERE run_id=:run AND stage_id=:s)"),
                     {"r": report.to_json(), "g": gate.value, "run": run.run_id, "s": STAGE_ID})
        if gate is not GateStatus.BLOCK:
            conn.execute(text("INSERT INTO engine.checkpoints "
                              "(checkpoint_id, stage_id, run_id, input_hash, code_version, contract_version, artifact_ref) "
                              "VALUES (:cid,:s,:r,:ih,:cv,:ctv,:ref)"),
                         {"cid": uuid.uuid4().hex, "s": STAGE_ID, "r": run.run_id,
                          "ih": report.hash_in, "cv": PIPELINE_VERSION, "ctv": "fetch_raw-v1",
                          "ref": "pg://fetch_raw.download_log + fs://data/raw/engine"})

    run.status = "OK" if gate is not GateStatus.BLOCK else "BLOCKED"

    filings_summary = []
    for f in filings:
        frs = [r for r in rows if r.get("acc") == f["acc"]]
        filings_summary.append({
            "accession": f["acc"], "form": f["form"], "filing_date": f["filing_date"],
            "period": f["period"], "files_planned": sum(1 for i in plan if i.get("acc") == f["acc"]),
            "files_ok": sum(1 for r in frs if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS")),
            "bytes": sum(r["bytes"] or 0 for r in frs)})
    kinds_count = {}
    for r in rows:
        kinds_count[r["kind"]] = kinds_count.get(r["kind"], 0) + 1
    taxonomies = sorted({re.sub(r"(-\d{8})?([-_](pre|cal|defr?|lab))?(\.\w+)+$", "",
                               Path(r["raw_path"]).name, flags=re.IGNORECASE)
                         for r in rows if r["raw_path"] and r["kind"] in
                         ("XBRL_INSTANCE", "XBRL_SCHEMA", "LINKBASE_PRE", "LINKBASE_CAL",
                          "LINKBASE_DEF", "LINKBASE_LAB")})
    validation = {"run_id": run.run_id, "git_commit": run.git_commit,
                  "mode": settings.mode, "scope": SCOPE_RULE,
                  "gate": gate.value, "checks": checks,
                  "totals": {"plan": len(plan), "rows": len(rows),
                             "counts_by_result": counts_by_result,
                             "bytes_total": bytes_total, "by_kind": kinds_count},
                  "filings": filings_summary, "taxonomies": taxonomies}
    (OUT_DIR / "S02_VALIDATION.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"gate": gate.value, "plan": len(plan), "rows": len(rows),
                      "counts": counts_by_result, "bytes_total": bytes_total,
                      "kinds": kinds_count, "filings": len(filings_summary),
                      "taxonomies": taxonomies}, indent=2, ensure_ascii=False))
    print("--- conciliacion ---")
    print(f"rows_expected = {len(plan)}")
    print(f"rows_ok       = {len(successes)}")
    print(f"rows_failed   = {len(failures)} {ev_failures if failures else ''}")
    print(f"gate          = {gate.value}")
    return 0 if gate is GateStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
