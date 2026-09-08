"""Publisher canonico (C12) en staging — FASE 2 / R7.1. SOLO STAGING, SIN CUTOVER.

Flujo: BUILD (staging) -> CHECK SCHEMA -> LOAD -> VALIDATE (volumen,
nunca-vacia, PK) -> C10 (evidencia, solo lectura) -> C11 (certificacion,
solo lectura) -> ATOMIC SWAP (RENAME transaccional) -> provenance log.
Regla unica: C10 PASS + C11 CERTIFIED o BLOQUEO. Sin cutover productivo:
TODAS las tablas viven en el schema `staging` (cualquier otro destino se
rechaza). No calcula nada: solo publica. Rollback = rename inverso.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

PUBLISHER_VERSION = "publisher_v1"
STAGING_SCHEMA = "staging"
CERTIFIED_VERDICT = "CERTIFICADA"
TARGET_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
FORBIDDEN_SQL = (";", "--", "/*", "*/", "union", "insert", "update",
                 "delete", "drop", "alter", "create", "grant", "copy",
                 "truncate", "exec", "call")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class PublishInput:
    source_schema: str
    source_table: str
    target: str  # nombre logico; vive como staging.<target>
    run_id: str
    pk_columns: list
    filter_sql: str = ""  # ej. "WHERE run_id = :r" (solo lectura)
    filter_params: dict = field(default_factory=dict)
    min_rows: int = 1  # estructural; umbral cuantitativo = PENDING_EVIDENCE

    @property
    def source_fqn(self) -> str:
        return "%s.%s" % (self.source_schema, self.source_table)


@dataclass
class PublishResult:
    ok: bool
    reason: str
    target: str = ""
    rows: int = 0
    input_hash: str = ""
    content_hash: str = ""
    c10_pass: bool = False
    certification_id: str | None = None
    cert_hash: str | None = None
    swap_ts: str | None = None
    provenance_id: int | None = None


def check_target_name(target: str) -> None:
    if not TARGET_RE.match(target):
        raise ValueError("target invalido (solo staging, [a-z0-9_]): %r" % target)


def check_identifiers(*names: str) -> None:
    for n in names:
        if not IDENT_RE.match(n or ""):
            raise ValueError("identificador invalido: %r" % (n,))


def check_filter(f: str) -> None:
    f = (f or "").strip()
    if not f:
        return
    if f[:5].upper() != "WHERE":
        raise ValueError("filter debe ser vacio o empezar con WHERE")
    if any(tok in f.lower() for tok in FORBIDDEN_SQL):
        raise ValueError("filter con tokens prohibidos")


def gate_decide(c10_pass: bool, verdict: str | None) -> tuple[bool, str]:
    """Regla unica. Pura (testeable sin DB)."""
    if not c10_pass:
        return False, "BLOCK:C10_NO_PASS"
    if verdict != CERTIFIED_VERDICT:
        return False, "BLOCK:C11_%s" % ("MISSING" if verdict is None else "NOT_CERTIFIED")
    return True, "ALLOW"


def columns_of(conn, schema: str, table: str) -> list[tuple]:
    rows = conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema=:s AND table_name=:t ORDER BY ordinal_position"),
        {"s": schema, "t": table}).mappings().all()
    return [(r["column_name"], r["data_type"]) for r in rows]


def compare_schema(src_cols: list[tuple], stg_cols: list[tuple]) -> tuple[bool, str]:
    if not src_cols:
        return False, "fuente inexistente o sin columnas"
    if [c for c, _ in src_cols] != [c for c, _ in stg_cols]:
        return False, "columnas difieren: %s vs %s" % (
            [c for c, _ in src_cols], [c for c, _ in stg_cols])
    mism = [(c, a, b) for (c, a), (_, b) in zip(src_cols, stg_cols) if a != b]
    if mism:
        return False, "tipos difieren: %s" % (mism,)
    return True, "schema ok (%d columnas)" % len(src_cols)


def never_empty(rows: int, min_rows: int) -> tuple[bool, str]:
    if rows <= 0:
        return False, "staging vacio"
    if rows < min_rows:
        return False, "staging incompleto: %d < minimo %d" % (rows, min_rows)
    return True, "volumen ok (%d filas)" % rows


def collect_c10(conn, run_id: str) -> tuple[bool, list]:
    """Lee evidencia C10 del run (solo lectura; no valida de nuevo)."""
    rows = conn.execute(text(
        "SELECT stage_id, state, gate_status FROM engine.stage_runs "
        "WHERE run_id=:r AND id IN (SELECT max(id) FROM engine.stage_runs "
        "WHERE run_id=:r GROUP BY stage_id) ORDER BY stage_id"),
        {"r": run_id}).mappings().all()
    detail = [{"stage": r["stage_id"], "state": r["state"],
               "gate": r["gate_status"]} for r in rows]
    if not detail:
        return False, detail
    ok = all((r["gate_status"] == "PASS") for r in rows)
    return ok, detail


def fetch_certification(conn, run_id: str) -> dict | None:
    """Lee la certificacion C11 del run (solo lectura; no modifica c11)."""
    row = conn.execute(text(
        "SELECT certification_id, veredicto, cert_hash FROM engine.certifications "
        "WHERE run_id=:r ORDER BY generado_at DESC LIMIT 1"),
        {"r": run_id}).mappings().first()
    return dict(row) if row else None


def content_digest(conn, schema: str, table: str, pk_columns: list) -> str:
    """Digest de fidelidad total (F3-K): md5 sobre filas completas en JSON
    (NULL distinguible de ''), ordenadas por PK. Detecta mutaciones de
    valores, no solo de membresia. Requiere pk_columns (orden determinista)."""
    if not pk_columns:
        raise ValueError("pk_columns requerido para digest (target protegido)")
    key = " || '|' || ".join("COALESCE(%s::text, '')" % c for c in pk_columns)
    return conn.execute(text(
        "SELECT md5(string_agg(j, ',' ORDER BY k)) FROM "
        "(SELECT %s AS k, row_to_json(s)::text AS j "
        "FROM %s.%s s) q" % (key, schema, table))).scalar()


def ensure_log_table(conn) -> None:
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS staging._publications ("
        "id SERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL, target TEXT NOT NULL, "
        "run_id TEXT NOT NULL, source_fqn TEXT NOT NULL, filter_sql TEXT NOT NULL, "
        "input_hash TEXT NOT NULL, content_hash TEXT NOT NULL, rows INT NOT NULL, "
        "c10_pass BOOLEAN NOT NULL, c10_ref JSONB NOT NULL, "
        "certification_id TEXT, cert_hash TEXT, swap_ts TIMESTAMPTZ, "
        "publisher_version TEXT NOT NULL, git_commit TEXT NOT NULL, "
        "rolled_back BOOLEAN NOT NULL DEFAULT FALSE)"))
    conn.execute(text(
        "ALTER TABLE staging._publications "
        "ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ"))
    conn.execute(text(
        "ALTER TABLE staging._publications "
        "ADD COLUMN IF NOT EXISTS restored_snapshot TEXT"))
    conn.execute(text(
        "ALTER TABLE staging._publications "
        "ADD COLUMN IF NOT EXISTS pk_columns TEXT"))
    conn.execute(text(
        "ALTER TABLE staging._publications "
        "ADD COLUMN IF NOT EXISTS snapshot_hash TEXT"))
    conn.execute(text(
        "ALTER TABLE staging._publications "
        "ADD COLUMN IF NOT EXISTS snapshot_rows INT"))


def _drop_quiet(conn, schema: str, table: str) -> None:
    """Elimina staging residual sin enmascarar el motivo original (F3)."""
    try:
        conn.execute(text("DROP TABLE IF EXISTS %s.%s" % (schema, table)))
    except Exception:
        pass


def verify_snapshot(conn, target: str, prev: str, pk_columns: list,
                    exp_hash: str | None = None,
                    exp_rows: int | None = None) -> tuple[bool, str, int]:
    """Verifica que el snapshot sea restaurable (F3 §8/§11).

    Compara contra el hash/conteo registrados al tomar el snapshot (si se
    conocen). Devuelve (ok, motivo, filas). No modifica nada."""
    rows = conn.execute(
        text("SELECT count(*) FROM staging.%s" % prev)).scalar()
    if rows is None or rows <= 0:
        return False, "BLOCK:EMPTY_SNAPSHOT", 0
    live = conn.execute(text(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='staging' AND table_name=:t"),
        {"t": target}).scalar() > 0
    if live:
        a = columns_of(conn, STAGING_SCHEMA, prev)
        b = columns_of(conn, STAGING_SCHEMA, target)
        if [c for c, _ in a] != [c for c, _ in b]:
            return False, "BLOCK:SNAPSHOT_SCHEMA_MISMATCH", rows
    if exp_rows is not None and rows != exp_rows:
        return False, "BLOCK:SNAPSHOT_COUNT_MISMATCH", rows
    if exp_hash is not None and pk_columns:
        cur = content_digest(conn, STAGING_SCHEMA, prev, pk_columns)
        if cur != exp_hash:
            return False, "BLOCK:SNAPSHOT_HASH_MISMATCH", rows
    return True, "snapshot ok (%d filas)" % rows, rows


def build_staging(conn, inp: PublishInput, attempt: str) -> str:
    """Crea staging.<target>__new__<attempt> desde la fuente (solo lectura
    sobre el origen). Devuelve el nombre de la tabla staging."""
    check_target_name(inp.target)
    check_identifiers(inp.source_schema, inp.source_table, *inp.pk_columns)
    check_filter(inp.filter_sql)
    new = "%s__new__%s" % (inp.target, attempt)
    src_cols = columns_of(conn, inp.source_schema, inp.source_table)
    if not src_cols:
        raise ValueError("fuente inexistente: %s" % inp.source_fqn)
    collist = ", ".join(c for c, _ in src_cols)
    conn.execute(text("DROP TABLE IF EXISTS staging.%s" % new))
    conn.execute(text(
        "CREATE TABLE staging.%s AS SELECT %s FROM %s %s"
        % (new, collist, inp.source_fqn, inp.filter_sql)), inp.filter_params)
    return new


def publish(inp: PublishInput, engine=None, dry_run: bool = False,
            git_commit: str | None = None) -> PublishResult:
    """Flujo completo. dry_run = build+validate sin swap. Todo staging."""
    check_target_name(inp.target)
    eng = engine or edb.get_engine(load_settings())
    git_commit = git_commit or os.environ.get("GIT_COMMIT", "dev-unknown")
    attempt = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    with eng.begin() as conn:
        ensure_log_table(conn)
        try:
            new = build_staging(conn, inp, attempt)
        except ValueError as e:
            return PublishResult(False, "BLOCK:%s" % e, target=inp.target)
        src_cols = columns_of(conn, inp.source_schema, inp.source_table)
        stg_cols = columns_of(conn, STAGING_SCHEMA, new)
        ok, msg = compare_schema(src_cols, stg_cols)
        if not ok:
            _drop_quiet(conn, STAGING_SCHEMA, new)
            return PublishResult(False, "BLOCK:SCHEMA_%s" % msg, target=inp.target)
        rows = conn.execute(
            text("SELECT count(*) FROM staging.%s" % new)).scalar()
        ok, msg = never_empty(rows, inp.min_rows)
        if not ok:
            _drop_quiet(conn, STAGING_SCHEMA, new)
            return PublishResult(False, "BLOCK:%s" % msg, target=inp.target)
        dups = 0
        if inp.pk_columns:
            key = " || '|' || ".join(
                "COALESCE(%s::text, '')" % c for c in inp.pk_columns)
            dups = conn.execute(text(
                "SELECT count(*) - count(DISTINCT k) FROM "
                "(SELECT %s AS k FROM staging.%s) q" % (key, new))).scalar()
        if dups:
            _drop_quiet(conn, STAGING_SCHEMA, new)
            return PublishResult(False, "BLOCK:PK_DUPLICADOS_%d" % dups,
                                 target=inp.target)
        digest = content_digest(conn, STAGING_SCHEMA, new, inp.pk_columns)
        input_hash = sha("|".join([inp.source_fqn, inp.filter_sql,
                                   inp.run_id, str(rows), digest]))
        c10_pass, c10_detail = collect_c10(conn, inp.run_id)
        cert = fetch_certification(conn, inp.run_id)
        verdict = cert["veredicto"] if cert else None
        allow, reason = gate_decide(c10_pass, verdict)
        if not allow:
            _drop_quiet(conn, STAGING_SCHEMA, new)
            return PublishResult(False, reason, target=inp.target, rows=rows,
                                 input_hash=input_hash, content_hash=digest,
                                 c10_pass=c10_pass,
                                 certification_id=(cert or {}).get("certification_id"),
                                 cert_hash=(cert or {}).get("cert_hash"))
        if dry_run:
            conn.execute(text("DROP TABLE staging.%s" % new))
            return PublishResult(True, "DRY_RUN_OK", target=inp.target,
                                 rows=rows, input_hash=input_hash,
                                 content_hash=digest, c10_pass=c10_pass,
                                 certification_id=cert["certification_id"],
                                 cert_hash=cert["cert_hash"])
        # Snapshot del target previo (si existe) + swap atomico.
        # Se registra hash+conteo del snapshot para verificacion exacta (F3).
        prev_exists = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": inp.target}).scalar() > 0
        snap_hash = None
        snap_rows = None
        if prev_exists:
            snap_rows = conn.execute(
                text("SELECT count(*) FROM staging.%s" % inp.target)).scalar()
            snap_hash = content_digest(conn, STAGING_SCHEMA, inp.target,
                                       inp.pk_columns)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            conn.execute(text("ALTER TABLE staging.%s RENAME TO %s__prev__%s"
                              % (inp.target, inp.target, stamp)))
        conn.execute(text("ALTER TABLE staging.%s RENAME TO %s" % (new, inp.target)))
        post = conn.execute(
            text("SELECT count(*) FROM staging.%s" % inp.target)).scalar()
        if post != rows or post <= 0:
            raise RuntimeError("swap inconsistente: %s != %s" % (post, rows))
        swap_ts = utc_now_iso()
        pid = conn.execute(text(
            "INSERT INTO staging._publications (ts, target, run_id, source_fqn, "
            "filter_sql, input_hash, content_hash, rows, c10_pass, c10_ref, "
            "certification_id, cert_hash, swap_ts, publisher_version, git_commit,"
            " pk_columns, snapshot_hash, snapshot_rows) "
            "VALUES (now(), :t, :r, :f, :fs, :ih, :ch, :n, :c10, "
            "CAST(:ref AS JSONB), :cid, :chh, now(), :pv, :gc, :pk, :sh, :sr) "
            "RETURNING id"),
            {"t": inp.target, "r": inp.run_id, "f": inp.source_fqn,
             "fs": inp.filter_sql, "ih": input_hash, "ch": digest, "n": rows,
             "c10": c10_pass, "ref": json.dumps(c10_detail),
             "cid": cert["certification_id"], "chh": cert["cert_hash"],
             "pv": PUBLISHER_VERSION, "gc": git_commit,
             "pk": ",".join(inp.pk_columns), "sh": snap_hash,
             "sr": snap_rows}).scalar()
        return PublishResult(True, "PUBLISHED", target=inp.target, rows=rows,
                             input_hash=input_hash, content_hash=digest,
                             c10_pass=c10_pass,
                             certification_id=cert["certification_id"],
                             cert_hash=cert["cert_hash"], swap_ts=swap_ts,
                             provenance_id=pid)


def rollback(target: str, engine=None) -> PublishResult:
    """Revierte al snapshot __prev__ mas reciente (una transaccion).

    Contrato F3: verifica el snapshot antes de tocar el target (nunca deja
    target vacio); si el target falta, lo recrea desde el snapshot; si no hay
    snapshot pero el target ya coincide con la ultima publicacion, es NOOP
    idempotente; si no, BLOCK:NO_SNAPSHOT. Registra provenance del rollback.
    """
    check_target_name(target)
    eng = engine or edb.get_engine(load_settings())
    with eng.begin() as conn:
        ensure_log_table(conn)
        prevs = [r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name LIKE :p "
            "ORDER BY table_name DESC"), {"p": target + "__prev__%"})]
        if not prevs:
            # Sin snapshot: NOOP idempotente solo si el vivo coincide con
            # ALGUNA publicacion registrada del target; si no, BLOCK.
            live = conn.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='staging' AND table_name=:t"),
                {"t": target}).scalar() > 0
            if live:
                for row in conn.execute(text(
                        "SELECT content_hash, pk_columns FROM staging._publications "
                        "WHERE target=:t AND content_hash IS NOT NULL "
                        "ORDER BY id DESC"), {"t": target}).mappings().all():
                    pks = [p for p in (row["pk_columns"] or "").split(",") if p]
                    if not pks:
                        continue
                    try:
                        cur = content_digest(conn, STAGING_SCHEMA, target, pks)
                    except Exception:
                        continue
                    if cur == row["content_hash"]:
                        return PublishResult(True, "NOOP_ALREADY_RESTORED",
                                             target=target)
            return PublishResult(False, "BLOCK:NO_SNAPSHOT", target=target)
        prev = prevs[0]
        snap = conn.execute(text(
            "SELECT snapshot_hash, snapshot_rows, pk_columns "
            "FROM staging._publications WHERE target=:t "
            "ORDER BY id DESC LIMIT 1"), {"t": target}).mappings().first()
        pks = [p for p in ((snap or {}).get("pk_columns") or "").split(",") if p]
        ok, msg, prev_rows = verify_snapshot(
            conn, target, prev, pks,
            exp_hash=(snap or {}).get("snapshot_hash"),
            exp_rows=(snap or {}).get("snapshot_rows"))
        if not ok:
            return PublishResult(False, msg, target=target)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        live = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='staging' AND table_name=:t"),
            {"t": target}).scalar() > 0
        if live:
            conn.execute(text("ALTER TABLE staging.%s RENAME TO %s__bad__%s"
                              % (target, target, stamp)))
        conn.execute(text("ALTER TABLE staging.%s RENAME TO %s" % (prev, target)))
        n = conn.execute(
            text("SELECT count(*) FROM staging.%s" % target)).scalar()
        if n != prev_rows or n <= 0:
            raise RuntimeError("recovery inconsistente: %s != %s" % (n, prev_rows))
        conn.execute(text("UPDATE staging._publications SET rolled_back=TRUE, "
                          "rolled_back_at=now(), restored_snapshot=:p "
                          "WHERE target=:t AND rolled_back=FALSE"),
                     {"t": target, "p": prev})
        return PublishResult(True, "ROLLED_BACK", target=target, rows=n)


def main() -> int:
    ap = argparse.ArgumentParser(description="Publisher C12 en staging (sin cutover)")
    ap.add_argument("--source", help="schema.tabla origen (lectura)")
    ap.add_argument("--target", required=True, help="nombre logico en staging")
    ap.add_argument("--run-id", help="run certificado (C10+C11)")
    ap.add_argument("--pk", help="columnas PK separadas por coma")
    ap.add_argument("--filter", default="", help="WHERE de lectura (solo SELECT)")
    ap.add_argument("--min-rows", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true", help="revertir al snapshot")
    args = ap.parse_args()
    try:
        if args.rollback:
            res = rollback(args.target)
        else:
            for req in ("source", "run_id", "pk"):
                if not getattr(args, req):
                    print("[error] --source/--run-id/--pk requeridos (salvo --rollback)")
                    return 2
            if "." not in args.source:
                print("[error] --source debe ser schema.tabla")
                return 2
            sch, tab = args.source.split(".", 1)
            res = publish(PublishInput(
                source_schema=sch, source_table=tab, target=args.target,
                run_id=args.run_id,
                pk_columns=[c.strip() for c in args.pk.split(",") if c.strip()],
                filter_sql=args.filter, min_rows=args.min_rows),
                dry_run=args.dry_run)
    except ValueError as e:
        print(json.dumps({"ok": False, "reason": "BLOCK:%s" % e,
                          "target": args.target}, ensure_ascii=False))
        return 1
    print(json.dumps(res.__dict__, ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
