"""S03 PARSE — orquestador generico (RAW -> parsed.*).

Toma las filas de `fetch_raw.download_log` de un checkpoint S02 y produce la
capa PARSED en PostgreSQL, con conciliacion
EXPECTED -> DISCOVERED -> SELECTED -> PARSED -> REJECTED -> PERSISTED.

Este modulo no conoce ninguna empresa: recibe entity_id/cik por parametro.
Cualquier caso particular vive en fixtures, configuracion o tests.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from psycopg2.extras import execute_values
from sqlalchemy import text

from engine import xbrlparse as X
from engine.fetch import RAW_ROOT, sha256_bytes

STAGE_ID = "S03_parse"
CONTRACT_VERSION = "parsed-v2"
PARSER_VERSION = X.PARSER_VERSION

# request_kind de S02 que pueden contener payload XBRL. XBRL_OTHER incluye la
# instancia extraida por la SEC de un iXBRL (`*_htm.xml`): omitirla fue el bug
# que dejaba 4 ejercicios sin instancia canonica.
XBRL_PAYLOAD_KINDS = frozenset({
    "XBRL_INSTANCE", "XBRL_SCHEMA", "LINKBASE_PRE", "LINKBASE_CAL", "LINKBASE_DEF",
    "LINKBASE_LAB", "LINKBASE_REF", "XBRL_OTHER", "XBRL_PACKAGE_ZIP"})
# Filas del log que no pertenecen a ningun filing.
GLOBAL_KINDS = frozenset({"SUBMISSIONS", "COMPANYFACTS", "SUBMISSIONS_PAGE"})
ZIP_KINDS = frozenset({"XBRL_PACKAGE_ZIP"})

_DATE_RE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")


# --------------------------------------------------------------------------
# Contrato de tablas: (columna, tipo). El tipo 'jsonb' genera el cast en el
# template de execute_values, en vez de contar '%s' a mano.
# --------------------------------------------------------------------------
FACT_COLS = (
    ("run_id", ""), ("entity_id", ""), ("cik", ""), ("accession_number", ""),
    ("form", ""), ("filing_date", ""), ("report_period", ""),
    ("taxonomy", ""), ("namespace", ""), ("tag", ""), ("qname", ""),
    ("value_text", ""), ("value_raw_text", ""), ("value_numeric", ""),
    ("is_numeric", ""), ("is_nil", ""),
    ("unit_ref", ""), ("unit_type", ""), ("measure", ""), ("numerator", ""),
    ("denominator", ""), ("decimals", ""), ("precision_attr", ""),
    ("context_id", ""), ("start_date", ""), ("end_date", ""), ("instant_date", ""),
    ("period_kind", ""), ("dimensions", "jsonb"), ("dim_count", ""), ("frame", ""),
    ("element_id", ""), ("scale", ""), ("sign", ""), ("ix_format", ""),
    ("numeric_transform", ""), ("transform_status", ""), ("is_hidden", ""),
    ("is_escaped", ""), ("ix_target", ""), ("continuation_steps", ""),
    ("fact_key", ""), ("doc_kind", ""),
    ("source_kind", ""), ("source_file", ""), ("source_path", ""),
    ("source_hash", ""), ("stage_run_id", ""))

CTX_COLS = (
    ("run_id", ""), ("entity_id", ""), ("accession_number", ""), ("context_id", ""),
    ("scheme", ""), ("identifier", ""), ("start_date", ""), ("end_date", ""),
    ("instant_date", ""), ("period_kind", ""), ("dimensions", "jsonb"),
    ("typed_dimensions", "jsonb"), ("non_dimensional", "jsonb"), ("dim_count", ""),
    ("has_typed", ""), ("has_segment", ""), ("has_scenario", ""),
    ("source_file", ""), ("source_hash", ""))

UNIT_COLS = (
    ("run_id", ""), ("entity_id", ""), ("accession_number", ""), ("unit_ref", ""),
    ("unit_type", ""), ("measures", "jsonb"), ("numerator", "jsonb"),
    ("denominator", "jsonb"), ("fact_count", ""), ("source_file", ""),
    ("source_hash", ""))

CONCEPT_COLS = (
    ("run_id", ""), ("entity_id", ""), ("namespace", ""), ("tag", ""), ("qname", ""),
    ("label", ""), ("documentation", ""), ("xsd_type", ""), ("period_type", ""),
    ("balance", ""), ("abstract", ""), ("is_custom", ""), ("taxonomy", ""),
    ("source_schema", ""), ("element_id", ""), ("substitution_group", ""),
    ("nillable", ""), ("is_dimension", ""), ("is_hypercube", ""))

REL_COLS = (
    ("run_id", ""), ("entity_id", ""), ("accession_number", ""), ("linkbase", ""),
    ("role", ""), ("from_qname", ""), ("to_qname", ""), ("arc_role", ""), ("weight", ""),
    ("order_num", ""), ("label_type", ""), ("lang", ""), ("label_text", ""),
    ("preferred_sign", ""), ("dimension_qname", ""), ("member_qname", ""),
    ("from_href", ""), ("to_href", ""), ("use_attr", ""), ("priority", ""),
    ("target_role", ""), ("closed", ""), ("context_element", ""),
    ("source_file", ""), ("source_hash", ""))

FOOTNOTE_COLS = (
    ("run_id", ""), ("entity_id", ""), ("accession_number", ""), ("footnote_id", ""),
    ("role", ""), ("lang", ""), ("footnote_text", ""), ("fact_refs", "jsonb"),
    ("source_file", ""), ("source_hash", ""))

DOC_COLS = (
    ("run_id", ""), ("entity_id", ""), ("accession_number", ""), ("container", ""),
    ("container_file", ""), ("member", ""), ("doc_name", ""), ("source_path", ""),
    ("bytes", ""), ("sha256", ""), ("declared_kind", ""), ("sniffed_kind", ""),
    ("sniff_detail", ""), ("doc_role", ""), ("selection_reason", ""), ("parsed", ""),
    ("facts_extracted", ""), ("relations_extracted", ""), ("concepts_extracted", ""))

PX_COLS = (
    ("run_id", ""), ("entity_id", ""), ("cik", ""), ("accession_number", ""),
    ("form", ""), ("filing_date", ""), ("period_of_report", ""), ("primary_doc", ""),
    ("index_path", ""), ("n_documents", ""), ("documents", "jsonb"),
    ("bytes_total", ""), ("classification", ""), ("note", ""))

CMP_COLS = (
    ("run_id", ""), ("entity_id", ""), ("taxonomy", ""), ("tag", ""), ("qname", ""),
    ("in_companyfacts", ""), ("in_filing", ""), ("cf_obs", ""),
    ("cf_unit_kinds", "jsonb"), ("cf_first_period", ""), ("cf_last_period", ""),
    ("filing_obs", ""), ("notes", ""))

ERR_COLS = (
    ("run_id", ""), ("entity_id", ""), ("accession_number", ""), ("source_file", ""),
    ("severity", ""), ("code", ""), ("message", ""))

RECON_COLS = (
    ("run_id", ""), ("entity_id", ""), ("level", ""), ("metric", ""), ("value", ""),
    ("detail", ""))

TABLES = {
    "parsed.facts": FACT_COLS,
    "parsed.contexts": CTX_COLS,
    "parsed.units": UNIT_COLS,
    "parsed.concepts": CONCEPT_COLS,
    "parsed.link_relations": REL_COLS,
    "parsed.footnotes": FOOTNOTE_COLS,
    "parsed.documents": DOC_COLS,
    "parsed.pre_xbrl_filings": PX_COLS,
    "parsed.companyfacts_compare": CMP_COLS,
    "parsed.parse_errors": ERR_COLS,
    "parsed.reconciliation": RECON_COLS,
}


def col_names(spec) -> tuple[str, ...]:
    return tuple(c for c, _ in spec)


def template_for(spec) -> str:
    return "(" + ",".join("%s::jsonb" if t == "jsonb" else "%s" for _, t in spec) + ")"


def insert_many(cur, table: str, spec, rows: list[tuple]) -> int:
    if not rows:
        return 0
    names = ",".join(col_names(spec))
    for i, row in enumerate(rows[:1]):
        if len(row) != len(spec):
            raise ValueError(
                f"{table}: fila con {len(row)} valores para {len(spec)} columnas "
                f"(fila {i}); contrato de columnas desincronizado")
    execute_values(cur, f"INSERT INTO {table} ({names}) VALUES %s", rows,
                   template=template_for(spec), page_size=1000)
    return len(rows)


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=False)


def as_date(value: str | None) -> date | None:
    if not value:
        return None
    m = _DATE_RE.match(value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Descubrimiento
# --------------------------------------------------------------------------
@dataclass
class DiscoveredDoc:
    accession: str
    container: str            # LOOSE | ZIP
    container_file: str | None
    member: str | None
    name: str
    source_path: str          # ruta RAW relativa (+ '!miembro' si viene de zip)
    sha256: str
    nbytes: int
    declared_kind: str        # request_kind de S02
    kind: str                 # clasificacion por contenido
    detail: str
    linkbase_types: list[str] = field(default_factory=list)
    data: bytes | None = None


@dataclass
class FilingResult:
    accession: str
    meta: dict
    outcome: str = "PENDING"
    docs: list[DiscoveredDoc] = field(default_factory=list)
    selected: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    fact_rows: list[tuple] = field(default_factory=list)
    ctx_rows: list[tuple] = field(default_factory=list)
    unit_rows: list[tuple] = field(default_factory=list)
    rel_rows: list[tuple] = field(default_factory=list)
    concept_rows: list[tuple] = field(default_factory=list)
    footnote_rows: list[tuple] = field(default_factory=list)
    doc_rows: list[tuple] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    fact_index: dict = field(default_factory=lambda: defaultdict(
        lambda: {"obs": 0, "periods": set(), "units": set()}))
    metrics: dict = field(default_factory=dict)
    seconds: float = 0.0


def verify_raw_integrity(rows: list[dict], raw_root: Path = RAW_ROOT
                         ) -> tuple[list[dict], list[dict]]:
    """Re-verifica el sha256 de cada crudo contra el download_log de S02."""
    ok, bad = [], []
    for r in rows:
        path = raw_root / r["raw_path"]
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
        b = buckets.setdefault(acc, {"meta": {"form": r["form"],
                                              "filing_date": r["filing_date"],
                                              "period": r["period"]}, "files": []})
        b["files"].append(r)
    return buckets


def discover_documents(acc: str, files: list[dict], raw_root: Path = RAW_ROOT,
                       keep_data: bool = True) -> tuple[list[DiscoveredDoc], list[dict]]:
    """Enumera y clasifica por contenido todo payload del filing, abriendo los
    zip. Un zip nunca se asume homogeneo: cada miembro se clasifica solo."""
    docs: list[DiscoveredDoc] = []
    errors: list[dict] = []
    for r in sorted(files, key=lambda x: (x["request_kind"], x["raw_path"])):
        kind_declared = r["request_kind"]
        rel = r["raw_path"]
        path = raw_root / rel
        name = Path(rel).name
        try:
            if kind_declared in ZIP_KINDS:
                with zipfile.ZipFile(path) as zf:
                    for info in sorted(zf.infolist(), key=lambda i: i.filename):
                        if info.is_dir():
                            continue
                        data = zf.read(info)
                        info_s = X.sniff_document(info.filename, data)
                        docs.append(DiscoveredDoc(
                            accession=acc, container="ZIP", container_file=name,
                            member=info.filename, name=Path(info.filename).name,
                            source_path=f"{rel}!{info.filename}",
                            sha256=sha256_bytes(data), nbytes=len(data),
                            declared_kind=kind_declared, kind=info_s.kind,
                            detail=info_s.detail, linkbase_types=info_s.linkbase_types,
                            data=data if keep_data else None))
            else:
                data = path.read_bytes()
                info_s = X.sniff_document(name, data)
                docs.append(DiscoveredDoc(
                    accession=acc, container="LOOSE", container_file=None, member=None,
                    name=name, source_path=rel, sha256=r["sha256"], nbytes=len(data),
                    declared_kind=kind_declared, kind=info_s.kind, detail=info_s.detail,
                    linkbase_types=info_s.linkbase_types,
                    data=data if keep_data else None))
        except zipfile.BadZipFile as exc:
            errors.append({"severity": "ERROR", "code": "ZIP_CORRUPTO",
                           "source_file": name, "message": str(exc)[:400]})
        except OSError as exc:
            errors.append({"severity": "ERROR", "code": "RAW_IO",
                           "source_file": name, "message": str(exc)[:400]})
    return docs, errors


# --------------------------------------------------------------------------
# Parseo de un filing
# --------------------------------------------------------------------------
def parse_filing(acc: str, bucket: dict, ctxinfo: dict,
                 raw_root: Path = RAW_ROOT) -> FilingResult:
    """Parsea un filing completo: descubre, selecciona fuente de hechos,
    extrae hechos/contextos/unidades/conceptos/relaciones/footnotes."""
    res = FilingResult(accession=acc, meta=bucket["meta"])
    t0 = time.perf_counter()
    run_id, entity_id, cik = ctxinfo["run_id"], ctxinfo["entity_id"], ctxinfo["cik"]
    stage_run_id = ctxinfo["stage_run_id"]
    meta = bucket["meta"]
    base7 = [run_id, entity_id, cik, acc, meta.get("form"),
             meta.get("filing_date"), meta.get("period")]

    docs, disc_errors = discover_documents(acc, bucket["files"], raw_root)
    res.docs = docs
    res.errors.extend(disc_errors)

    cand = [{"name": d.name, "kind": d.kind, "sha256": d.sha256,
             "container": d.container, "path": d.source_path, "_doc": d} for d in docs]
    selected, rejected = X.select_fact_sources(cand)
    res.selected, res.rejected = selected, rejected
    selected_paths = {s["path"] for s in selected}
    role_by_path = {r["path"]: (r["role"], r["selection_reason"]) for r in rejected}
    role_by_path.update({s["path"]: (s["role"], s["selection_reason"]) for s in selected})

    per_doc_counts: dict[str, dict] = defaultdict(
        lambda: {"facts": 0, "relations": 0, "concepts": 0, "parsed": False})

    # ---- fuentes de hechos elegidas
    for doc in docs:
        if doc.source_path not in selected_paths:
            continue
        data = doc.data if doc.data is not None else _read_doc(doc, raw_root)
        parsed = (X.parse_inline_bytes(data, doc.name) if doc.kind == "INLINE_XBRL"
                  else X.parse_instance_bytes(data, doc.name))
        for e in parsed.errors:
            res.errors.append({"severity": e["severity"], "code": e["code"],
                               "source_file": doc.name, "message": e["message"]})
        if parsed.fatal:
            per_doc_counts[doc.source_path]["parsed"] = False
            continue
        n = _consume(res, parsed, doc, base7, run_id, entity_id, acc, stage_run_id)
        per_doc_counts[doc.source_path] = {
            "facts": n, "relations": 0, "concepts": 0, "parsed": True}

    # ---- schemas y linkbases (siempre, no son fuente de hechos)
    seen_payload_sha: set[str] = set()
    for doc in docs:
        if doc.kind not in ("XSD_SCHEMA", "LINKBASE"):
            continue
        if doc.sha256 in seen_payload_sha:
            role_by_path[doc.source_path] = (
                "DUPLICATE_SHA", "mismo sha256 que otro schema/linkbase del filing")
            continue
        seen_payload_sha.add(doc.sha256)
        data = doc.data if doc.data is not None else _read_doc(doc, raw_root)
        n_rel = n_con = 0
        if doc.kind == "XSD_SCHEMA":
            try:
                for c in X.parse_schema_bytes(data, doc.name):
                    res.concept_rows.append((
                        run_id, entity_id, c.namespace, c.tag, c.qname, c.label,
                        c.documentation, c.xsd_type, c.period_type, c.balance,
                        c.abstract, c.is_custom, c.taxonomy, doc.name, c.element_id,
                        c.substitution_group, c.nillable, c.is_dimension, c.is_hypercube))
                    n_con += 1
            except ValueError as exc:
                res.errors.append({"severity": "ERROR", "code": "SCHEMA_PARSE",
                                   "source_file": doc.name, "message": str(exc)[:400]})
        if doc.linkbase_types:
            try:
                for rel in X.parse_linkbase_bytes(data, doc.name):
                    res.rel_rows.append(_rel_row(rel, run_id, entity_id, acc,
                                                 doc.name, doc.sha256))
                    n_rel += 1
            except ValueError as exc:
                res.errors.append({"severity": "ERROR", "code": "LINKBASE_PARSE",
                                   "source_file": doc.name, "message": str(exc)[:400]})
        per_doc_counts[doc.source_path] = {"facts": 0, "relations": n_rel,
                                           "concepts": n_con, "parsed": True}

    # ---- ledger de documentos (EXPECTED -> DISCOVERED -> SELECTED -> PARSED)
    for doc in docs:
        role, reason = role_by_path.get(doc.source_path, ("NOT_A_FACT_SOURCE", ""))
        counts = per_doc_counts[doc.source_path]
        if doc.kind in ("XSD_SCHEMA", "LINKBASE") and role == "NOT_A_FACT_SOURCE":
            role = "SCHEMA" if doc.kind == "XSD_SCHEMA" else "LINKBASE"
            reason = doc.detail
        res.doc_rows.append((
            run_id, entity_id, acc, doc.container, doc.container_file, doc.member,
            doc.name, doc.source_path, doc.nbytes, doc.sha256, doc.declared_kind,
            doc.kind, doc.detail, role, reason, counts["parsed"],
            counts["facts"], counts["relations"], counts["concepts"]))
        doc.data = None  # liberar memoria: el filing puede pesar >40 MB

    has_xbrl_payload = any(r["request_kind"] in XBRL_PAYLOAD_KINDS
                           for r in bucket["files"])
    if res.fact_rows:
        res.outcome = "PARSED_XBRL"
    elif not has_xbrl_payload:
        res.outcome = "PRE_XBRL"
    else:
        res.outcome = "REJECTED"

    res.metrics = {
        "docs_discovered": len(docs),
        "docs_selected": len(selected),
        "docs_rejected": len(rejected),
        "instances": sum(1 for d in docs if d.kind == "XBRL_INSTANCE"
                         and d.source_path in selected_paths),
        "inline_docs": sum(1 for d in docs if d.kind == "INLINE_XBRL"
                           and d.source_path in selected_paths),
        "schemas": sum(1 for d in docs if d.kind == "XSD_SCHEMA"),
        "linkbase_files": sum(1 for d in docs if d.linkbase_types),
        "zips": sum(1 for r in bucket["files"] if r["request_kind"] in ZIP_KINDS),
        "bytes_discovered": sum(d.nbytes for d in docs),
    }
    res.seconds = round(time.perf_counter() - t0, 3)
    return res


def _read_doc(doc: DiscoveredDoc, raw_root: Path) -> bytes:
    if doc.container == "ZIP":
        with zipfile.ZipFile(raw_root / doc.source_path.split("!", 1)[0]) as zf:
            return zf.read(doc.member)
    return (raw_root / doc.source_path).read_bytes()


def _rel_row(rel: X.ParsedRelation, run_id: str, entity_id: str, acc: str,
             source_file: str, source_hash: str) -> tuple:
    return (run_id, entity_id, acc, rel.linkbase, rel.role, rel.from_qname,
            rel.to_qname, rel.arc_role, rel.weight, rel.order_num, rel.label_type,
            rel.lang, rel.label_text, rel.preferred_sign, rel.dimension_qname,
            rel.member_qname, rel.from_href, rel.to_href, rel.use, rel.priority,
            rel.target_role, rel.closed, rel.context_element, source_file, source_hash)


def _consume(res: FilingResult, parsed: X.InstanceParseResult, doc: DiscoveredDoc,
             base7: list, run_id: str, entity_id: str, acc: str,
             stage_run_id: int) -> int:
    """Convierte el resultado de parseo de UN documento en filas de la capa
    PARSED, preservando provenance completa por fila."""
    src_kind = f"{doc.declared_kind}:{doc.kind}"
    for ctx in parsed.contexts.values():
        res.ctx_rows.append((
            run_id, entity_id, acc, ctx.context_id, ctx.scheme, ctx.identifier,
            as_date(ctx.start_date), as_date(ctx.end_date), as_date(ctx.instant_date),
            ctx.period_kind, j(ctx.dimensions),
            j(ctx.typed_dimensions) if ctx.typed_dimensions else None,
            j(ctx.non_dimensional) if ctx.non_dimensional else None,
            ctx.dim_count, bool(ctx.typed_dimensions), ctx.has_segment,
            ctx.has_scenario, doc.name, doc.sha256))
        for kind_name, raw in (("start", ctx.start_date), ("end", ctx.end_date),
                               ("instant", ctx.instant_date)):
            if raw and as_date(raw) is None:
                res.errors.append({
                    "severity": "WARNING", "code": "DATE_UNPARSEABLE",
                    "source_file": doc.name,
                    "message": f"contexto {ctx.context_id}: {kind_name}={raw!r} no es fecha ISO"})

    unit_fact_count: dict[str, int] = defaultdict(int)
    n_new = 0
    for f in parsed.facts:
        unit_type = measure = numerator = denominator = None
        if f.unit_ref and f.unit_ref in parsed.units:
            u = parsed.units[f.unit_ref]
            unit_type = u.unit_type
            measure = "|".join(u.measures) or None
            numerator = "|".join(u.numerator) or None
            denominator = "|".join(u.denominator) or None
            unit_fact_count[f.unit_ref] += 1
        ctx = parsed.contexts.get(f.context_id)
        res.fact_rows.append(tuple(base7 + [
            f.taxonomy, f.namespace, f.tag, f.qname, f.value_text, f.value_raw_text,
            f.value_numeric, f.is_numeric, f.is_nil,
            f.unit_ref, unit_type, measure, numerator, denominator,
            f.decimals, f.precision, f.context_id,
            as_date(ctx.start_date) if ctx else None,
            as_date(ctx.end_date) if ctx else None,
            as_date(ctx.instant_date) if ctx else None,
            f.period_kind, j(ctx.dimensions) if ctx else "[]",
            ctx.dim_count if ctx else 0, f.frame, f.element_id, f.scale, f.sign,
            f.ix_format, f.numeric_transform, f.transform_status, f.is_hidden,
            f.is_escaped, f.ix_target, f.continuation_steps, f.key, f.doc_kind,
            src_kind, doc.name, doc.source_path, doc.sha256, stage_run_id]))
        n_new += 1
        fi = res.fact_index[f.qname]
        fi["obs"] += 1
        period_key = (ctx.instant_date or ctx.end_date) if ctx else None
        if period_key:
            fi["periods"].add(period_key)
        if measure:
            fi["units"].add(measure)
        elif numerator and denominator:
            fi["units"].add(f"{numerator}/{denominator}")

    for u_ref, u in parsed.units.items():
        res.unit_rows.append((
            run_id, entity_id, acc, u_ref, u.unit_type, j(u.measures),
            j(u.numerator) if u.numerator else None,
            j(u.denominator) if u.denominator else None,
            unit_fact_count.get(u_ref, 0), doc.name, doc.sha256))

    for fn in parsed.footnotes:
        res.footnote_rows.append((
            run_id, entity_id, acc, fn.footnote_id, fn.role, fn.lang, fn.text,
            j(fn.fact_ids), doc.name, doc.sha256))
    return n_new


# --------------------------------------------------------------------------
# Idempotencia / checkpoint
# --------------------------------------------------------------------------
def input_hash(entity_id: str, files_ok: list[dict]) -> str:
    """Huella del input: entidad + (ruta, sha256) de cada crudo consumido.

    Es la clave de reutilizacion junto a code_version y contract_version:
    mismo input + mismo codigo + mismo contrato => checkpoint hit.
    """
    h = hashlib.sha256()
    h.update(entity_id.encode())
    for r in sorted(files_ok, key=lambda x: x["raw_path"]):
        h.update(f"|{r['raw_path']}={r['sha256']}".encode())
    return h.hexdigest()


def output_hash(fact_rows_count: int, digests: dict[str, str]) -> str:
    payload = json.dumps({"facts": fact_rows_count, **digests}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def content_digest(rows: list[tuple], key_index: int | None = None) -> str:
    """Digest estable del contenido persistido (independiente del run_id)."""
    h = hashlib.sha256()
    if key_index is None:
        for row in rows:
            h.update(repr(row[1:]).encode("utf-8", "replace"))
    else:
        for row in rows:
            h.update(str(row[key_index]).encode("utf-8", "replace"))
    return h.hexdigest()


def find_checkpoint(engine, ih: str, code_version: str,
                    contract_version: str = CONTRACT_VERSION) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT checkpoint_id, run_id, created_at FROM engine.checkpoints "
            " WHERE stage_id=:s AND input_hash=:h AND code_version=:c "
            "   AND contract_version=:ct"),
            {"s": STAGE_ID, "h": ih, "c": code_version, "ct": contract_version}
        ).mappings().first()
    return dict(row) if row else None


def find_s02_input_run(engine) -> str:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT r.run_id FROM engine.runs r
             WHERE EXISTS (SELECT 1 FROM engine.stage_runs s
                            WHERE s.run_id = r.run_id AND s.stage_id='S02_fetch'
                              AND s.gate_status='PASS')
             ORDER BY r.started_at DESC LIMIT 1""")).scalar()
    if not row:
        raise SystemExit("BLOCK: no hay run S02 con gate PASS; "
                         "correr scripts/engine/s02_fetch_ypf.py")
    return row


def load_s02_inputs(engine, run_id: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT log_id, request_kind, accession_number AS acc, form_type AS form,
                   filing_date, period_of_report AS period, raw_path, sha256, bytes
              FROM fetch_raw.download_log
             WHERE run_id=:r AND result IN ('DOWNLOADED','SIN_CAMBIOS')
               AND raw_path IS NOT NULL AND sha256 IS NOT NULL
             ORDER BY log_id"""), {"r": run_id}).mappings().all()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------
def persist(engine, entity_id: str, payload: dict) -> dict:
    """Escribe la capa PARSED de la entidad en UNA transaccion.

    `parsed.*` es derivada y determinista: se reemplaza SOLO lo de esta entidad
    (no un DELETE global, que borraria otras entidades). Si algo falla,
    rollback completo: nunca queda media capa escrita.
    """
    counts: dict[str, int] = {}
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        for table in TABLES:
            cur.execute(f"DELETE FROM {table} WHERE entity_id = %s", (entity_id,))
        for table, spec in TABLES.items():
            rows = payload.get(table) or []
            counts[table] = insert_many(cur, table, spec, rows)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    return counts
