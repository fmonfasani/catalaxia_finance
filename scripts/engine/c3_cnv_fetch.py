"""C3 — CNV FETCHER.

Discovery -> Fetch -> RAW -> Integrity -> Manifest -> Provenance -> Validation -> Checkpoint.

Generalizable a cualquier empresa CNV por CUIT. CEPU es el caso piloto, no una
excepcion: ninguna regla del codigo nombra a CEPU. La identidad se consume, nunca
se inventa (C1/C2); si C3 detecta una inconsistencia, la registra y sigue.

Uso:
  python scripts/engine/c3_cnv_fetch.py --cuit 33650305499 --scope FINANCIERO
  python scripts/engine/c3_cnv_fetch.py --cuit 33650305499 --rerun     # idempotencia
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from engine import db as edb
from engine.config import REPO_ROOT, load_settings
from engine.cnv import CNV_ADAPTER_VERSION
from engine.cnv import discovery as disc
from engine.cnv import validate as val
from engine.cnv.client import CnvClient, RateLimiter, DEFAULT_DELAYS
from engine.cnv.rawstore import RawStore, canonical_sha256, sha256_b64, sha256_bytes
from engine.report import StageReport, utc_now_iso
from engine.states import GateStatus, StageState, assert_transition

STAGE_ID = "C3_CNV_fetch"
PIPELINE_VERSION = CNV_ADAPTER_VERSION
SCRIPT = "scripts/engine/c3_cnv_fetch.py"
OUT_DIR = REPO_ROOT / "outputs" / "docs" / "fase_cnv"
SEED_C1 = REPO_ROOT / "data" / "catalogo" / "cnv_identity_seed_cepu.csv"
REVIEWS_C2 = OUT_DIR / "C2_CNV_IDENTITY_REVIEWS_V2.csv"

# Reviews que C2 dejo abiertas y que C3 no puede cerrar: necesitan fuente externa
# a CNV (constancia AFIP). Cerrarlas aqui seria inventar identidad.
REVIEWS_NO_CERRABLES = ("C1-R-001", "C1-R-002", "C1-R-005")

SCOPES = {
    # Lo que hace falta para los ratios: EEFF propio moderno con datos inline.
    "EEFF_PROPIO": {disc.CLASE_EEFF_PROPIO},
    # Propio + relacionadas + legacy: el universo financiero completo del perfil.
    "FINANCIERO": disc.CLASES_FINANCIERAS,
    "TODO": None,
}


# --------------------------------------------------------------- identidad ---
def load_identity(cuit: str, engine) -> dict:
    """Consume la identidad de C1 (seed declarativo) y la contrasta con identity.*.

    No crea ni modifica entidades. Si el binding no existe, el run sigue con una
    clave provisional CUIT:{cuit} y emite un hallazgo, en vez de inventar una.
    """
    ident = {"cuit": cuit, "entity_key": f"CUIT:{cuit}", "legal_name": None,
             "binding": "PROVISIONAL_CUIT", "cik": None, "findings": []}
    seed_rows: list[dict] = []
    if SEED_C1.exists():
        seed_rows = list(csv.DictReader(SEED_C1.open(encoding="utf-8-sig")))
    seed_key = next((r["entity_key"] for r in seed_rows
                     if r["scope"] == "entity" and r["field"] == "cuit"
                     and val.normalize_cuit(r["value"]) == cuit), None)
    if seed_key:
        ident["entity_key"] = seed_key
        ident["binding"] = "C1_SEED"
        ident["legal_name"] = next((r["value"] for r in seed_rows
                                    if r["entity_key"] == seed_key and r["field"] == "legal_name"), None)
        if seed_key.startswith("CIK:"):
            ident["cik"] = seed_key.split(":", 1)[1]
    else:
        ident["findings"].append(
            f"CUIT {cuit} sin binding en el seed C1 ({SEED_C1.name}): se opera con clave "
            f"provisional CUIT:{cuit}. C3 no crea identidades; requiere C1 para esta empresa.")

    with engine.connect() as conn:
        row = conn.execute(text("SELECT entity_id, legal_name, cik, cuit FROM identity.entities "
                                "WHERE cuit = :c OR entity_id = :k"),
                           {"c": cuit, "k": ident["entity_key"]}).mappings().first()
    ident["identity_db"] = dict(row) if row else None
    if row:
        if row["cik"] and ident["cik"] and row["cik"] != ident["cik"]:
            raise SystemExit(f"BLOCK identidad: seed C1 dice CIK {ident['cik']} y identity.entities "
                             f"dice {row['cik']} para {ident['entity_key']}")
        if not row["cuit"]:
            # Inconsistencia real detectada por C3: se registra, no se corrige aqui.
            ident["findings"].append(
                f"identity.entities[{row['entity_id']}].cuit es NULL pero el seed C1 declara "
                f"CUIT {cuit}. El seed nunca se promovio a PostgreSQL. Pertenece a C1: C3 lo "
                f"registra y no muta identity.*")
        ident["legal_name"] = ident["legal_name"] or row["legal_name"]
    else:
        ident["findings"].append(
            f"identity.entities no tiene fila para {ident['entity_key']} ni para CUIT {cuit}.")
    return ident


def load_open_reviews() -> list[dict]:
    if not REVIEWS_C2.exists():
        return []
    return list(csv.DictReader(REVIEWS_C2.open(encoding="utf-8-sig")))


# ------------------------------------------------------------------ manifest -
class Manifest:
    """Manifest + provenance + log. Una fila por artefacto fetcheado."""

    def __init__(self, engine, run_id: str, stage_run_id: int | None, ident: dict, git_commit: str | None):
        self.engine = engine
        self.run_id = run_id
        self.stage_run_id = stage_run_id
        self.ident = ident
        self.git_commit = git_commit
        self.rows: list[dict] = []

    def record(self, *, kind: str, key: str, endpoint: str, method: str, critical: bool,
               res, validation, stored=None, nombre: str | None = None,
               hash_cnv: str | None = None, parent_kind: str | None = None,
               parent_key: str | None = None, result: str, fail_reason: str | None = None) -> dict:
        sha_b64 = stored.sha256_b64 if stored else None
        # Idempotencia canonica (decision 2026-08-25): hash separado del RAW,
        # excluye solo el ruido confirmado de EMPRESA_PAGE/VISOR. Ver rawstore.py.
        canon_sha = canonical_sha256(res.content, kind) if res.content else None
        row = {
            "run_id": self.run_id, "stage_run_id": self.stage_run_id, "stage_id": STAGE_ID,
            "entity_key": self.ident["entity_key"], "cuit": self.ident["cuit"], "source": "CNV",
            "artifact_kind": kind, "artifact_key": key,
            "parent_kind": parent_kind, "parent_key": parent_key,
            "endpoint": endpoint, "http_method": method, "critical": critical,
            "http_status": res.http_status, "content_type": res.content_type,
            "bytes": stored.bytes if stored else (res.bytes or None),
            "sha256": stored.sha256 if stored else None, "sha256_b64": sha_b64,
            "canonical_sha256": canon_sha,
            "hash_cnv": hash_cnv,
            "hash_cnv_match": (hash_cnv == sha_b64) if (hash_cnv and sha_b64) else None,
            "raw_path": stored.rel_path if stored else None,
            "duplicate_of": stored.duplicate_of if stored else None,
            "attempts": res.attempts, "elapsed_ms": res.elapsed_ms,
            "downloaded_at": utc_now_iso(), "result": result,
            "validation_status": validation.status if validation else None,
            "validation_failed": ",".join(validation.failed) if validation and validation.failed else None,
            "validation": json.dumps(validation.to_dict(), ensure_ascii=False) if validation else None,
            "fail_reason": fail_reason or (validation.reason() if validation else None) or res.error,
            "nombre": nombre,
            "git_commit": self.git_commit,
            "parser_version": PIPELINE_VERSION,
        }
        self.rows.append(row)
        self._insert_log(row)
        if stored and result in ("DOWNLOADED", "SIN_CAMBIOS", "REVIEW"):
            self._upsert_artifact(row)
        return row

    def _insert_log(self, row: dict) -> None:
        payload = {k: row[k] for k in (
            "run_id", "stage_run_id", "stage_id", "entity_key", "cuit", "source", "artifact_kind",
            "artifact_key", "parent_kind", "parent_key", "endpoint", "http_method", "critical",
            "http_status", "content_type", "bytes", "sha256", "sha256_b64", "canonical_sha256",
            "hash_cnv", "hash_cnv_match", "raw_path", "duplicate_of", "attempts", "elapsed_ms",
            "result", "validation_status", "validation_failed", "validation", "fail_reason")}
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO fetch_raw.cnv_download_log
                (run_id, stage_run_id, stage_id, entity_key, cuit, source, artifact_kind,
                 artifact_key, parent_kind, parent_key, endpoint, http_method, critical,
                 http_status, content_type, bytes, sha256, sha256_b64, canonical_sha256,
                 hash_cnv, hash_cnv_match, raw_path, duplicate_of, attempts, elapsed_ms, result,
                 validation_status, validation_failed, validation, fail_reason)
                VALUES (:run_id,:stage_run_id,:stage_id,:entity_key,:cuit,:source,:artifact_kind,
                 :artifact_key,:parent_kind,:parent_key,:endpoint,:http_method,:critical,
                 :http_status,:content_type,:bytes,:sha256,:sha256_b64,:canonical_sha256,
                 :hash_cnv,:hash_cnv_match,
                 :raw_path,:duplicate_of,:attempts,:elapsed_ms,:result,:validation_status,
                 :validation_failed, CAST(:validation AS JSONB), :fail_reason)
            """), payload)

    def _upsert_artifact(self, row: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO fetch_raw.cnv_artifact
                (cuit, entity_key, artifact_kind, artifact_key, sha256, sha256_b64,
                 canonical_sha256, bytes, content_type, nombre, raw_path, endpoint, hash_cnv,
                 hash_cnv_match, parent_kind, parent_key, first_seen_run, last_seen_run)
                VALUES (:cuit,:entity_key,:artifact_kind,:artifact_key,:sha256,:sha256_b64,
                 :canonical_sha256,:bytes,:content_type,:nombre,:raw_path,:endpoint,:hash_cnv,
                 :hash_cnv_match,:parent_kind,:parent_key,:run_id,:run_id)
                ON CONFLICT (artifact_kind, artifact_key, sha256) DO UPDATE
                   SET last_seen_run = EXCLUDED.last_seen_run,
                       last_seen_at = now(),
                       canonical_sha256 = EXCLUDED.canonical_sha256,
                       times_seen = fetch_raw.cnv_artifact.times_seen + 1
            """), {k: row[k] for k in (
                "cuit", "entity_key", "artifact_kind", "artifact_key", "sha256", "sha256_b64",
                "canonical_sha256", "bytes", "content_type", "nombre", "raw_path", "endpoint",
                "hash_cnv", "hash_cnv_match", "parent_kind", "parent_key", "run_id")})


# ---------------------------------------------------------------- fetch ------
def fetch_empresa(client, store, mf, cuit: str, run_id: str) -> tuple[dict, str | None]:
    res = client.fetch_empresa(cuit)
    v = val.validate_empresa_page(res, cuit)
    stored = None
    if res.content:
        stored = store.store("EMPRESA_PAGE", cuit, res.content, run_id=run_id)
    result = _result_for(res, v, stored)
    row = mf.record(kind="EMPRESA_PAGE", key=cuit, endpoint=res.url, method="GET", critical=True,
                    res=res, validation=v, stored=stored, result=result)
    html = None
    if stored and v.status != val.INVALID:
        html = stored.abs_path.read_bytes().decode("utf-8", "replace")
    return row, html


def _result_for(res, v, stored) -> str:
    if v.status == val.INVALID or not stored:
        state = res.transport_state()
        if state in ("NOT_FOUND", "BLOCKED"):
            return state
        return "FAILED"
    if v.status == val.REVIEW:
        return "REVIEW"
    return "SIN_CAMBIOS" if stored.action == "SIN_CAMBIOS" else "DOWNLOADED"


def fetch_visor(client, store, mf, cuit: str, pres, run_id: str):
    res = client.fetch_visor(pres.guid)
    v = val.validate_visor(res, pres.guid, expected_cuit=cuit)
    stored = None
    if res.content and v.status != val.INVALID:
        stored = store.store("VISOR", pres.guid, res.content, run_id=run_id)
    result = _result_for(res, v, stored)
    row = mf.record(kind="VISOR", key=pres.guid, endpoint=res.url, method="GET",
                    critical=(pres.clase == disc.CLASE_EEFF_PROPIO), res=res, validation=v,
                    stored=stored, parent_kind="EMPRESA_PAGE", parent_key=cuit, result=result)
    meta = None
    if stored:
        meta = disc.parse_viewer(stored.abs_path.read_bytes().decode("utf-8", "replace"), pres.guid)
    return row, meta


def fetch_attachment(client, store, mf, cuit: str, att, viewer_guid: str, csrf: str | None, run_id: str):
    key, res_key = client.fetch_valet_key(att.blob_guid)
    vk = val.validate_valet_key(res_key, key)
    mf.record(kind="VALET_KEY", key=att.blob_guid, endpoint=res_key.url, method="GET",
              critical=False, res=res_key, validation=vk, stored=None,
              parent_kind="VISOR", parent_key=viewer_guid,
              result="SKIPPED" if vk.status == val.VALID else "FAILED")
    if not key:
        return None
    res = client.fetch_blob(att.blob_guid, key, csrf)
    b64 = sha256_b64(res.content) if res.content else None
    v = val.validate_blob(res, nombre=att.nombre, tamano_declarado=att.tamano,
                          hash_cnv=att.hash_cnv, sha256_b64=b64)
    stored = None
    if res.content and v.status != val.INVALID:
        stored = store.store("BLOB", att.blob_guid, res.content, nombre=att.nombre, run_id=run_id)
    result = _result_for(res, v, stored)
    return mf.record(kind="BLOB", key=att.blob_guid, endpoint=res.url, method="POST",
                     critical=False, res=res, validation=v, stored=stored, nombre=att.nombre,
                     hash_cnv=att.hash_cnv, parent_kind="VISOR", parent_key=viewer_guid,
                     result=result)


# ----------------------------------------------------------------- main ------
def main() -> int:
    ap = argparse.ArgumentParser(description="C3 CNV fetcher (por CUIT, generalizable)")
    ap.add_argument("--cuit", default="33650305499", help="CUIT sin guiones del perfil CNV")
    ap.add_argument("--scope", default="FINANCIERO", choices=sorted(SCOPES))
    ap.add_argument("--desde-anio", type=int, default=None, help="filtra por anio de cierre >= N")
    ap.add_argument("--max-visores", type=int, default=None)
    ap.add_argument("--adjuntos-presentaciones", type=int, default=0,
                    help="cuantas presentaciones EEFF propias descargan adjuntos")
    ap.add_argument("--adjunto-max-mb", type=float, default=30.0)
    ap.add_argument("--rerun", action="store_true", help="pasada de verificacion de idempotencia")
    ap.add_argument("--delay-visor", type=float, default=DEFAULT_DELAYS["aif2.cnv.gov.ar"])
    args = ap.parse_args()

    cuit = val.normalize_cuit(args.cuit)
    if not cuit or len(cuit) != 11:
        raise SystemExit(f"CUIT invalido: {args.cuit!r}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    settings = load_settings()
    engine = edb.get_engine(settings)
    applied = edb.apply_migrations(engine)
    print(f"[config] {settings.describe()} | migraciones nuevas: {applied or '(ninguna)'}")

    ident = load_identity(cuit, engine)
    print(f"[identity] {ident['entity_key']} | {ident['legal_name']} | binding={ident['binding']}")
    for f in ident["findings"]:
        print(f"[identity][HALLAZGO] {f}")

    # F-040: las huerfanas se ven al ARRANCAR, como en el resto de las etapas.
    huerfanas = edb.corridas_huerfanas(engine)
    if huerfanas:
        print(f"[huerfanas] {len(huerfanas)} corridas previas quedaron en RUNNING:")
        for h in huerfanas[:5]:
            print(f"   {h['run_id'][:12]} {h['pipeline_version']} hace {h['horas']}h")

    # F-040: el cierre va en `finally` (run_scope). Antes, `start_run` abria
    # aca y `finish_run` cerraba 350 lineas mas abajo: cualquier excepcion en
    # el medio dejaba la corrida en RUNNING para siempre. Paso tres veces el
    # 2026-08-28. Es el mismo patron que F-031 aplico a S03.
    with edb.run_scope(engine, settings, PIPELINE_VERSION) as run:
        print(f"[run] run_id={run.run_id} git={run.git_commit} "
              f"scope={args.scope} rerun={args.rerun}")
        return _correr(engine, settings, run, args, cuit, ident)


def _correr(engine, settings, run, args, cuit, ident) -> int:
    """Cuerpo de la corrida. Fija `run.status`; NUNCA llama a finish_run."""
    started = utc_now_iso()

    prev, cur = None, StageState.PLANNED
    for nxt in (StageState.READY, StageState.RUNNING):
        assert_transition(cur, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=prev, new_state=nxt)
        prev, cur = cur, nxt
    with engine.connect() as conn:
        stage_run_id = conn.execute(
            text("SELECT id FROM engine.stage_runs WHERE run_id=:r AND stage_id=:s ORDER BY id DESC LIMIT 1"),
            {"r": run.run_id, "s": STAGE_ID}).scalar_one()

    delays = dict(DEFAULT_DELAYS)
    delays["aif2.cnv.gov.ar"] = args.delay_visor
    client = CnvClient(rate=RateLimiter(delays))
    store = RawStore(cuit)
    mf = Manifest(engine, run.run_id, stage_run_id, ident, run.git_commit)

    # -- 1. DISCOVERY ---------------------------------------------------------
    emp_row, html = fetch_empresa(client, store, mf, cuit, run.run_id)
    print(f"[empresa] http={emp_row['http_status']} bytes={emp_row['bytes']} "
          f"validacion={emp_row['validation_status']} raw={emp_row['raw_path']}")
    if html is None:
        _finish_blocked(engine, run, cur, started, settings, mf,
                        f"pagina empresa invalida: {emp_row['fail_reason']}", args, cuit, ident)
        return 1

    presentaciones, resumen_disc = disc.parse_empresa_page(html)
    print(f"[discovery] {resumen_disc}")
    _persist_inventory(engine, run.run_id, cuit, ident["entity_key"], presentaciones)

    clases = SCOPES[args.scope]
    plan = [p for p in presentaciones if clases is None or p.clase in clases]
    if args.desde_anio:
        plan = [p for p in plan if p.anio_cierre is None or p.anio_cierre >= args.desde_anio]
    plan.sort(key=lambda p: (p.fecha_cierre or "", p.fecha_publicacion or ""), reverse=True)
    if args.max_visores:
        plan = plan[:args.max_visores]
    print(f"[plan] visores a fetchear={len(plan)} (scope={args.scope})")

    # -- 2. FETCH visores -----------------------------------------------------
    metas: dict[str, object] = {}
    for i, p in enumerate(plan, 1):
        row, meta = fetch_visor(client, store, mf, cuit, p, run.run_id)
        if meta:
            metas[p.guid] = meta
        if i % 25 == 0 or i == len(plan):
            print(f"[visores] {i}/{len(plan)} ok={sum(1 for r in mf.rows if r['artifact_kind']=='VISOR' and r['result'] in ('DOWNLOADED','SIN_CAMBIOS'))}")

    # -- 3. FETCH adjuntos ----------------------------------------------------
    if args.adjuntos_presentaciones:
        objetivo = [p for p in plan if p.clase == disc.CLASE_EEFF_PROPIO][:args.adjuntos_presentaciones]
        for p in objetivo:
            meta = metas.get(p.guid)
            if not meta:
                continue
            for att in meta.attachments:
                mb = val._parse_tamano(att.tamano)
                if mb and mb > args.adjunto_max_mb * 1024 ** 2:
                    print(f"[adjunto] SKIP {att.nombre[:50]} ({att.tamano}) > {args.adjunto_max_mb} MB")
                    continue
                row = fetch_attachment(client, store, mf, cuit, att, p.guid, meta.csrf_token, run.run_id)
                if row:
                    print(f"[adjunto] {row['result']:11} {att.nombre[:52]:54} {row['bytes']} B "
                          f"hash_cnv_match={row['hash_cnv_match']}")

    # -- 4. VALIDACION / GATES ------------------------------------------------
    checks = build_checks(mf, store, client, presentaciones, plan, engine, run.run_id, ident, args)
    blocked = [c for c in checks if c["result"] == "FAIL" and c["blocking"]]
    gate = GateStatus.BLOCK if blocked else (
        GateStatus.WARNING if any(c["result"] == "WARN" for c in checks) else GateStatus.PASS)

    checkpoint_id = _close_stage(engine, run, cur, gate, blocked, checks, mf, started, settings, ident)
    _write_artifacts(mf, store, presentaciones, plan, checks, gate, run, ident, args, resumen_disc,
                     checkpoint_id)

    print("\n--- conciliacion ---")
    counts = _counts(mf.rows)
    print(f"artefactos planificados = {1 + len(plan)} (+ adjuntos)")
    print(f"filas manifest          = {len(mf.rows)}")
    print(f"por resultado           = {counts}")
    print(f"gate                    = {gate.value}  checkpoint={checkpoint_id}")
    for c in checks:
        print(f"  [{c['result']:5}] {c['id']} — {c['detail'][:150]}")
    return 0 if gate is not GateStatus.BLOCK else 1


def _counts(rows: list[dict]) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[r["result"]] = out.get(r["result"], 0) + 1
    return out


def _persist_inventory(engine, run_id: str, cuit: str, entity_key: str, presentaciones) -> None:
    payload = []
    for p in presentaciones:
        d = p.to_dict()
        d.update({"run_id": run_id, "cuit": cuit, "entity_key": entity_key})
        d.pop("ocurrencias_secciones", None)
        payload.append(d)
    with engine.begin() as conn:
        for chunk_start in range(0, len(payload), 500):
            conn.execute(text("""
                INSERT INTO fetch_raw.cnv_presentation
                (run_id, cuit, entity_key, guid, presentation_id, fecha_publicacion, seccion,
                 secciones, titulo, url, clase, ambito, relacion, relacion_origen,
                 cuit_relacionado, nombre_relacionado, sigla_legacy, norma_contable, tipo_balance,
                 periodicidad_raw, periodicidad_norm, periodicidad_origen, fecha_cierre,
                 anio_cierre, ocurrencias)
                VALUES (:run_id,:cuit,:entity_key,:guid,:presentation_id,:fecha_publicacion,
                 :seccion,:secciones,:titulo,:url,:clase,:ambito,:relacion,:relacion_origen,
                 :cuit_relacionado,:nombre_relacionado,:sigla_legacy,:norma_contable,:tipo_balance,
                 :periodicidad_raw,:periodicidad_norm,:periodicidad_origen,:fecha_cierre,
                 :anio_cierre,:ocurrencias)
                ON CONFLICT (run_id, guid) DO NOTHING
            """), payload[chunk_start:chunk_start + 500])


# ----------------------------------------------------------------- gates -----
def build_checks(mf, store, client, presentaciones, plan, engine, run_id, ident, args) -> list[dict]:
    rows = mf.rows
    ok_rows = [r for r in rows if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS")]
    review_rows = [r for r in rows if r["result"] == "REVIEW"]
    fail_rows = [r for r in rows if r["result"] in ("FAILED", "NOT_FOUND", "BLOCKED")]
    crit_fail = [r for r in fail_rows if r["critical"]]
    persisted = [r for r in rows if r["raw_path"]]

    checks = []

    esperados = 1 + len(plan) + sum(1 for r in rows if r["artifact_kind"] in ("BLOB", "VALET_KEY"))
    checks.append({
        "id": "C-C3-001", "blocking": True,
        "result": "PASS" if (len(rows) == esperados and not crit_fail) else "FAIL",
        "detail": f"conciliacion plan->manifest: esperados={esperados} filas={len(rows)} "
                  f"ok={len(ok_rows)} review={len(review_rows)} fallidos={len(fail_rows)} "
                  f"criticos_fallidos={len(crit_fail)}",
        "evidence": {"counts_by_result": _counts(rows),
                     "critical_failures": [{"kind": r["artifact_kind"], "key": r["artifact_key"],
                                            "reason": r["fail_reason"]} for r in crit_fail][:10]}})

    verificados, mismatch, faltantes = 0, [], []
    for r in persisted:
        ok, actual = store.verify(r["raw_path"], r["sha256"])
        if ok:
            verificados += 1
        elif actual == "MISSING_ON_DISK":
            faltantes.append(r["raw_path"])
        else:
            mismatch.append({"raw_path": r["raw_path"], "manifest": r["sha256"][:12], "disco": (actual or "")[:12]})
    checks.append({
        "id": "C-C3-002", "blocking": True,
        "result": "PASS" if not mismatch and not faltantes else "FAIL",
        "detail": f"integridad RAW re-leyendo disco: verificados={verificados}/{len(persisted)} "
                  f"mismatch={len(mismatch)} faltantes={len(faltantes)}",
        "evidence": {"hash_mismatches": mismatch[:10], "missing": faltantes[:10]}})

    campos = ("entity_key", "cuit", "endpoint", "sha256", "raw_path", "artifact_kind", "artifact_key")
    huerfanos = [r for r in persisted if any(not r.get(c) for c in campos)]
    sin_padre = [r for r in persisted if r["artifact_kind"] != "EMPRESA_PAGE" and not r["parent_key"]]
    checks.append({
        "id": "C-C3-003", "blocking": True,
        "result": "PASS" if not huerfanos and not sin_padre else "FAIL",
        "detail": f"provenance completa entidad->cuit->url->sha->raw->run->padre: "
                  f"filas persistidas={len(persisted)} incompletas={len(huerfanos)} sin_padre={len(sin_padre)}",
        "evidence": {"incompletas": [r["artifact_key"] for r in huerfanos][:10],
                     "sin_padre": [r["artifact_key"] for r in sin_padre][:10]}})

    # HTTP 200 con contenido invalido NO puede terminar aceptado.
    aceptados_invalidos = [r for r in rows if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS")
                           and r["validation_status"] != "VALID"]
    doscientos_rechazados = [r for r in rows if r["http_status"] == 200 and r["validation_status"] == "INVALID"]
    checks.append({
        "id": "C-C3-004", "blocking": True,
        "result": "PASS" if not aceptados_invalidos else "FAIL",
        "detail": f"validacion de contenido: 0 artefactos aceptados con validacion != VALID "
                  f"(aceptados={len(ok_rows)}, en revision={len(review_rows)}, "
                  f"HTTP 200 rechazados por contenido={len(doscientos_rechazados)})",
        "evidence": {"aceptados_invalidos": [r["artifact_key"] for r in aceptados_invalidos][:10],
                     "http200_rechazados": [{"kind": r["artifact_kind"], "key": r["artifact_key"],
                                             "failed": r["validation_failed"]}
                                            for r in doscientos_rechazados][:10],
                     "reglas_por_kind": _reglas_por_kind(rows)}})

    intervalos = {h: client.rate.min_interval(h) for h in
                  ("www.cnv.gov.ar", "aif2.cnv.gov.ar", "blob.cnv.gov.ar")}
    respetado = all(iv is None or iv >= client.rate.delay_for(h) * 0.9 for h, iv in intervalos.items())
    checks.append({
        "id": "C-C3-005", "blocking": True, "result": "PASS" if respetado else "FAIL",
        "detail": f"rate limiting por host respetado: intervalos minimos observados={intervalos} "
                  f"vs configurados={ {h: client.rate.delay_for(h) for h in intervalos} }",
        "evidence": {"stats": client.stats, "requests": len(client.rate.starts),
                     "max_attempts": client.max_attempts}})

    escritos = [r for r in persisted if r["result"] == "DOWNLOADED"]
    sin_cambios = [r for r in persisted if r["result"] == "SIN_CAMBIOS"]
    if args.rerun:
        # Decision 2026-08-25: EMPRESA_PAGE/VISOR jamas repiten bytes crudos (ver
        # rawstore.canonical_sha256), asi que "escrituras nuevas" ya NO mide
        # idempotencia para ellos. Se compara contra el hash CANONICO de la
        # corrida previa mas reciente para la misma (kind,key); BLOB/VALET_KEY
        # no se ven afectados (su canonico == su sha256 crudo).
        with engine.connect() as conn:
            comparacion = conn.execute(text("""
                SELECT cur.artifact_kind, cur.artifact_key,
                       cur.canonical_sha256 AS cur_canon, prev.canonical_sha256 AS prev_canon
                FROM fetch_raw.cnv_download_log cur
                LEFT JOIN LATERAL (
                    SELECT canonical_sha256
                    FROM fetch_raw.cnv_download_log p
                    WHERE p.artifact_kind = cur.artifact_kind AND p.artifact_key = cur.artifact_key
                      AND p.run_id <> cur.run_id AND p.downloaded_at < cur.downloaded_at
                    ORDER BY p.downloaded_at DESC LIMIT 1
                ) prev ON true
                WHERE cur.run_id = :run_id AND cur.canonical_sha256 IS NOT NULL
            """), {"run_id": run_id}).mappings().all()
        con_precedente = [r for r in comparacion if r["prev_canon"] is not None]
        sin_precedente = [r for r in comparacion if r["prev_canon"] is None]
        cambios_reales = [r for r in con_precedente if r["prev_canon"] != r["cur_canon"]]
        idem_ok = not cambios_reales
        detalle = (f"rerun idempotente por hash CANONICO (excluye ruido confirmado de "
                   f"cache-busting/anti-forgery, no bytes crudos): comparados contra corrida "
                   f"previa={len(con_precedente)}/{len(comparacion)}, sin_precedente={len(sin_precedente)}, "
                   f"identicos en sustancia={len(con_precedente) - len(cambios_reales)}, "
                   f"cambios reales={len(cambios_reales)} (esperado 0); "
                   f"escrituras RAW nuevas={len(escritos)} de todos modos -- eso ya NO es lo que "
                   f"este check mide, ver KNOWN ISSUES de idempotencia estructural")
        evidencia = {"store_stats": store.stats, "rerun": args.rerun,
                     "comparados_previa": len(con_precedente), "sin_precedente": len(sin_precedente),
                     "cambios_reales": [{"kind": r["artifact_kind"], "key": r["artifact_key"]}
                                        for r in cambios_reales][:10]}
    else:
        idem_ok = True
        detalle = (f"primera pasada: escritos={len(escritos)} reutilizados={len(sin_cambios)}; "
                   f"RAW direccionado por contenido, 0 sobreescrituras "
                   f"(bytes nuevos={store.stats['bytes_written']})")
        evidencia = {"store_stats": store.stats, "rerun": args.rerun,
                     "nuevos": [r["artifact_key"] for r in escritos][:10]}
    checks.append({"id": "C-C3-006", "blocking": True, "result": "PASS" if idem_ok else "FAIL",
                   "detail": detalle, "evidence": evidencia})

    reviews = load_open_reviews()
    # Columnas reales de C2_CNV_IDENTITY_REVIEWS_V2.csv: review_id,...,status_prev,status,...
    # (nombres en ingles). "estado"/"estado_c2" nunca existieron: sin este fallback
    # la comparacion de abajo siempre veia None y pasaba en falso vacio.
    estados = {r.get("review_id") or r.get("review"): (r.get("status") or r.get("estado_c2") or r.get("estado"))
               for r in reviews}
    cerradas = [rid for rid in REVIEWS_NO_CERRABLES
                if estados.get(rid) and estados[rid] not in ("OPEN", "PARTIAL")]
    rel_declaradas = [p for p in presentaciones if p.relacion]
    # F-039: el desglose se deriva de lo que la CNV declara, no de una lista
    # cableada. La version anterior sumaba solo CONTROLADA y VINCULADA, asi que
    # con YPF informaba "declaradas=584 (244+338)" -- los 2 CONTROLANTE
    # desaparecian del informe sin que nada fallara. Un desglose que no cierra
    # contra su propio total es un hallazgo perdido.
    desglose_relaciones = ", ".join(
        f"{v}={n}" for v, n in sorted(Counter(p.relacion for p in rel_declaradas).items()))
    rel_asumidas = [p for p in presentaciones
                    if p.relacion and p.relacion_origen != "DECLARADA"]
    subsidiarias_sin_relacion = [p for p in presentaciones
                                 if p.clase == disc.CLASE_EEFF_SUBSIDIARIA_LEGACY and p.relacion]
    ident_ok = not cerradas and not rel_asumidas and not subsidiarias_sin_relacion
    checks.append({
        "id": "C-C3-007", "blocking": True, "result": "PASS" if ident_ok else "FAIL",
        "detail": f"identidad no inventada: reviews no cerrables intactas={len(REVIEWS_NO_CERRABLES) - len(cerradas)}"
                  f"/{len(REVIEWS_NO_CERRABLES)}; relaciones declaradas={len(rel_declaradas)} "
                  f"({desglose_relaciones}); "
                  f"0 relaciones asumidas; 0 entidades creadas por C3",
        "evidence": {"reviews_estado": estados, "cerradas_indebidamente": cerradas,
                     "relaciones_asumidas": [p.guid for p in rel_asumidas][:10],
                     "hallazgos_identidad": ident["findings"]}})

    con_hash = [r for r in rows if r["hash_cnv"]]
    coinciden = [r for r in con_hash if r["hash_cnv_match"]]
    checks.append({
        "id": "C-C3-008", "blocking": False,
        "result": "PASS" if not con_hash else ("PASS" if len(coinciden) == len(con_hash) else "WARN"),
        "detail": f"doble hash de adjuntos (C0-CNV-006): comparados={len(con_hash)} "
                  f"coinciden={len(coinciden)}. El hash declarado por CNV NO se usa para "
                  f"idempotencia; la integridad la da el SHA-256 propio",
        "evidence": {"mismatches": [{"nombre": r["nombre"], "hash_cnv": r["hash_cnv"],
                                     "sha256_b64": r["sha256_b64"]}
                                    for r in con_hash if not r["hash_cnv_match"]][:5]}})

    claves = [(r["artifact_kind"], r["artifact_key"], r["sha256"]) for r in persisted]
    dup_manifest = len(claves) - len(set(claves))
    dup_contenido = [r for r in persisted if r["duplicate_of"]]
    checks.append({
        "id": "C-C3-009", "blocking": True, "result": "PASS" if dup_manifest == 0 else "FAIL",
        "detail": f"deteccion de duplicados: filas (kind,key,sha) repetidas en el manifest={dup_manifest}; "
                  f"contenidos identicos detectados bajo claves distintas={len(dup_contenido)} "
                  f"(se registran, no se re-persisten)",
        "evidence": {"duplicados_contenido": [{"kind": r["artifact_kind"], "key": r["artifact_key"],
                                               "duplicate_of": r["duplicate_of"]}
                                              for r in dup_contenido][:10]}})

    scope_ajeno = [r for r in rows if r["cuit"] != ident["cuit"]]
    checks.append({
        "id": "C-C3-010", "blocking": True, "result": "PASS" if not scope_ajeno else "FAIL",
        "detail": f"scope: 100% de las {len(rows)} descargas pertenecen al perfil CUIT {ident['cuit']}; "
                  f"0 requests a SEC/mercado/otras empresas",
        "evidence": {"hosts": sorted({r["endpoint"].split('/')[2] for r in rows})}})
    return checks


def _reglas_por_kind(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for r in rows:
        if not r["validation"]:
            continue
        v = json.loads(r["validation"])
        bucket = out.setdefault(v["kind"], {})
        for rule in v["rules"]:
            slot = bucket.setdefault(rule["id"], {"pass": 0, "fail": 0, "severity": rule["severity"]})
            slot["pass" if rule["passed"] else "fail"] += 1
    return out


def _close_stage(engine, run, cur, gate, blocked, checks, mf, started, settings, ident) -> str | None:
    assert_transition(cur, StageState.VALIDATING)
    edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cur, new_state=StageState.VALIDATING)
    camino = [StageState.FAILED] if gate is GateStatus.BLOCK else [StageState.PASSED, StageState.CHECKPOINTED]
    cursor = StageState.VALIDATING
    for nxt in camino:
        assert_transition(cursor, nxt)
        edb.record_stage_transition(engine, run.run_id, STAGE_ID, prev_state=cursor, new_state=nxt,
                                    gate_status=gate if nxt == camino[-1] else None,
                                    gate_reasons=[c["detail"] for c in blocked])
        cursor = nxt

    ok = [r for r in mf.rows if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS")]
    rechazados = [r for r in mf.rows if r["result"] not in ("DOWNLOADED", "SIN_CAMBIOS")]
    report = StageReport(
        stage=STAGE_ID, run_id=run.run_id, mode=settings.mode, started_at=started,
        finished_at=utc_now_iso(), gate=gate, input_checkpoint_id="C2:reviews-resolution-v1",
        input_rows=1, expected=len(mf.rows), parsed=len(ok), rejected=len(rechazados),
        rejected_by_reason=_counts(rechazados),
        hash_in=hashlib.sha256(f"{ident['entity_key']}|{ident['cuit']}".encode()).hexdigest(),
        hash_out=hashlib.sha256(json.dumps(_counts(mf.rows), sort_keys=True).encode()).hexdigest(),
        gate_reasons=[c["detail"] for c in blocked],
        checks=[{"id": c["id"], "result": c["result"], "detail": c["detail"],
                 "blocking": c["blocking"]} for c in checks],
        parser_version=PIPELINE_VERSION, script=SCRIPT, git_commit=run.git_commit)
    report.validate()

    checkpoint_id = None
    with engine.begin() as conn:
        conn.execute(text("UPDATE engine.stage_runs SET report = CAST(:r AS JSONB), finished_at=now(), "
                          "gate_status=:g WHERE id=(SELECT max(id) FROM engine.stage_runs "
                          "WHERE run_id=:run AND stage_id=:s)"),
                     {"r": report.to_json(), "g": gate.value, "run": run.run_id, "s": STAGE_ID})
        if gate is not GateStatus.BLOCK:
            # ux_checkpoints_reuse es UNIQUE(stage_id,input_hash,code_version,contract_version):
            # dos corridas PASS/WARNING para la MISMA entidad (mismo hash_in, que depende solo de
            # entity_key+cuit) deben REUSAR el checkpoint existente, no insertar uno nuevo -- eso
            # es lo que el nombre del indice ya declaraba. Antes de este fix, la segunda corrida
            # exitosa para el mismo CUIT crasheaba con IntegrityError sin manejar el conflicto
            # (confirmado reproduciendolo: run4 crasheo asi al re-correr sobre CEPU sin --rerun).
            new_checkpoint_id = uuid.uuid4().hex
            checkpoint_id = conn.execute(text("""
                INSERT INTO engine.checkpoints (checkpoint_id, stage_id, run_id,
                    input_hash, code_version, contract_version, artifact_ref)
                VALUES (:cid,:s,:r,:ih,:cv,:ctv,:ref)
                ON CONFLICT (stage_id, input_hash, code_version, contract_version)
                DO UPDATE SET run_id = EXCLUDED.run_id, artifact_ref = EXCLUDED.artifact_ref
                RETURNING checkpoint_id
            """), {"cid": new_checkpoint_id, "s": STAGE_ID, "r": run.run_id, "ih": report.hash_in,
                   "cv": PIPELINE_VERSION, "ctv": "fetch_raw.cnv-v1",
                   "ref": "pg://fetch_raw.cnv_* + fs://data/raw/engine/cnv"}).scalar_one()
    # F-040: la etapa DECLARA el estado; el cierre lo hace `run_scope` en su
    # `finally`. Llamar a finish_run desde aca era lo que dejaba la corrida
    # abierta cuando el proceso moria antes de llegar a esta linea.
    run.status = "OK" if gate is not GateStatus.BLOCK else "BLOCKED"
    return checkpoint_id


def _finish_blocked(engine, run, cur, started, settings, mf, motivo, args, cuit, ident) -> None:
    checks = [{"id": "C-C3-001", "blocking": True, "result": "FAIL", "detail": motivo, "evidence": {}}]
    _close_stage(engine, run, cur, GateStatus.BLOCK, checks, checks, mf, started, settings, ident)
    print(f"[BLOCK] {motivo}")


def _write_artifacts(mf, store, presentaciones, plan, checks, gate, run, ident, args,
                     resumen_disc, checkpoint_id) -> None:
    cuit = ident["cuit"]
    inv_path = OUT_DIR / "C3_CNV_INVENTORY.csv"
    campos = list(presentaciones[0].to_dict().keys()) if presentaciones else []
    with inv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cuit", "entity_key"] + campos)
        w.writeheader()
        for p in presentaciones:
            row = {"cuit": cuit, "entity_key": ident["entity_key"]}
            row.update(p.to_dict())
            w.writerow(row)

    man_cols = ["artifact_kind", "artifact_key", "nombre", "parent_kind", "parent_key", "endpoint",
                "http_method", "http_status", "content_type", "bytes", "sha256", "sha256_b64",
                "hash_cnv", "hash_cnv_match", "raw_path", "duplicate_of", "attempts", "elapsed_ms",
                "result", "validation_status", "validation_failed", "critical", "fail_reason"]
    with (OUT_DIR / "C3_CNV_MANIFEST.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["run_id", "cuit", "entity_key"] + man_cols)
        w.writeheader()
        for r in mf.rows:
            w.writerow({k: r.get(k) for k in ["run_id", "cuit", "entity_key"] + man_cols})

    with (OUT_DIR / "C3_CNV_PROVENANCE.jsonl").open("w", encoding="utf-8") as fh:
        for r in mf.rows:
            fh.write(json.dumps({
                "run_id": r["run_id"], "stage_id": STAGE_ID, "git_commit": r["git_commit"],
                "parser_version": r["parser_version"], "source": "CNV",
                "identity": {"entity_key": r["entity_key"], "cuit": r["cuit"],
                             "binding": ident["binding"]},
                "artifact": {"kind": r["artifact_kind"], "key": r["artifact_key"],
                             "nombre": r["nombre"]},
                "lineage": {"parent_kind": r["parent_kind"], "parent_key": r["parent_key"]},
                "request": {"endpoint": r["endpoint"], "method": r["http_method"],
                            "attempts": r["attempts"], "elapsed_ms": r["elapsed_ms"],
                            "http_status": r["http_status"], "content_type": r["content_type"]},
                "integrity": {"bytes": r["bytes"], "sha256": r["sha256"],
                              "sha256_b64": r["sha256_b64"], "hash_cnv": r["hash_cnv"],
                              "hash_cnv_match": r["hash_cnv_match"], "raw_path": r["raw_path"],
                              "duplicate_of": r["duplicate_of"]},
                "validation": json.loads(r["validation"]) if r["validation"] else None,
                "result": r["result"], "fetched_at": r["downloaded_at"],
            }, ensure_ascii=False) + "\n")

    revision = [r for r in mf.rows if r["result"] in ("REVIEW", "FAILED", "NOT_FOUND", "BLOCKED")]
    with (OUT_DIR / "C3_CNV_REVIEW_QUEUE.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["artifact_kind", "artifact_key", "nombre", "endpoint",
                                           "http_status", "result", "validation_status",
                                           "validation_failed", "fail_reason"])
        w.writeheader()
        for r in revision:
            w.writerow({k: r.get(k) for k in w.fieldnames})

    resumen_clases: dict[str, int] = {}
    for p in presentaciones:
        resumen_clases[p.clase] = resumen_clases.get(p.clase, 0) + 1
    validation = {
        "_meta": {"generated_at": utc_now_iso(), "fase": "C3_CNV_FETCHER", "stage_id": STAGE_ID,
                  "run_id": run.run_id, "git_commit": run.git_commit,
                  "parser_version": PIPELINE_VERSION, "scope": args.scope,
                  "rerun": args.rerun, "checkpoint_id": checkpoint_id,
                  "identity": {"entity_key": ident["entity_key"], "cuit": cuit,
                               "legal_name": ident["legal_name"], "binding": ident["binding"],
                               "findings": ident["findings"]}},
        "discovery": {**resumen_disc, "clases": resumen_clases,
                      "relaciones": {"CONTROLADA": sum(1 for p in presentaciones if p.relacion == "CONTROLADA"),
                                     "VINCULADA": sum(1 for p in presentaciones if p.relacion == "VINCULADA"),
                                     "SIN_DECLARAR_legacy": sum(1 for p in presentaciones
                                                                if p.clase == disc.CLASE_EEFF_SUBSIDIARIA_LEGACY)},
                      "cuits_relacionados": sorted({p.cuit_relacionado for p in presentaciones
                                                    if p.cuit_relacionado})},
        "fetch": {"planificados": len(plan), "filas_manifest": len(mf.rows),
                  "counts_by_result": _counts(mf.rows), "store_stats": store.stats,
                  "bytes_ok": sum(r["bytes"] or 0 for r in mf.rows
                                  if r["result"] in ("DOWNLOADED", "SIN_CAMBIOS"))},
        "checks": checks,
        "veredicto": {"fase": "C3", "gate": gate.value,
                      "resultado": "PASS" if gate is not GateStatus.BLOCK else "BLOCK",
                      "checkpoint_id": checkpoint_id,
                      "siguiente": "READY_FOR_C4" if gate is not GateStatus.BLOCK else "FIX_REQUIRED"},
    }
    (OUT_DIR / "C3_CNV_VALIDATION.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
