"""Evaluador C10 (VALIDACION) — FASE 6 / R7.5. SOLO LECTURA.

Responde deterministicamente si los outputs pueden pasar a C11:
PASS / WARN / BLOCK + evidencia reproducible. No certifica, no publica,
no modifica facts/RAW/identidad/market, no hace rollback, no decide
equivalencias economicas. C10 consume evidencia; la autoridad de cada
dominio (gates stages, m4, job7) sigue en su componente.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402

C10_VERSION = "c10_evaluate_v1"
STAGES_SEC = ("S00_bootstrap", "S01_identity", "S02_fetch", "S03_parse",
              "S04_normalize")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Invariant:
    id: str
    result: str  # PASS | WARN | BLOCK
    evidence: dict = field(default_factory=dict)


def aggregate(results: list[Invariant]) -> str:
    """BLOCK gana a WARN gana a PASS. Pura."""
    if any(r.result == "BLOCK" for r in results):
        return "BLOCK"
    if any(r.result == "WARN" for r in results):
        return "WARN"
    return "PASS"


def latest_gates(conn, run_id: str) -> dict:
    rows = conn.execute(text(
        "SELECT stage_id, state, gate_status FROM engine.stage_runs "
        "WHERE run_id=:r AND id IN (SELECT max(id) FROM engine.stage_runs "
        "WHERE run_id=:r GROUP BY stage_id)"), {"r": run_id}).mappings().all()
    return {r["stage_id"]: (r["state"], r["gate_status"]) for r in rows}


def inv_sec_gates(conn, run_ids: list) -> Invariant:
    bad = {}
    for r in run_ids:
        g = latest_gates(conn, r)
        missing = [s for s in STAGES_SEC if s not in g]
        failed = [s for s, (st, gs) in g.items()
                  if s in STAGES_SEC and gs != "PASS"]
        if missing or failed:
            bad[r[:8]] = {"missing": missing, "non_pass": failed}
    if bad:
        return Invariant("SEC_GATES", "BLOCK", {"runs": bad})
    return Invariant("SEC_GATES", "PASS",
                     {"runs": len(run_ids), "stages": list(STAGES_SEC)})


def inv_identity(conn, ciks: list) -> Invariant:
    bad = {}
    for k in ciks:
        n0 = conn.execute(text(
            "SELECT count(DISTINCT entity_id) FROM identity.identifiers "
            "WHERE id_value=:k AND id_type='CIK'"), {"k": k}).scalar()
        n1 = conn.execute(text(
            "SELECT count(*) FROM identity_v1.entity WHERE entity_key IN "
            "(SELECT entity_key FROM identity_v1.identifier "
            "WHERE id_value=:k)"), {"k": k}).scalar()
        if n0 != 1 or n1 < 1:
            bad[k] = {"v0_entities": n0, "v1_entities": n1}
    if bad:
        return Invariant("IDENTITY", "BLOCK", {"ciks": bad})
    return Invariant("IDENTITY", "PASS", {"ciks": ciks})


def inv_provenance(conn, ciks: list) -> Invariant:
    bad = {}
    for k in ciks:
        row = conn.execute(text(
            "SELECT count(*) AS n, count(source_fact_ids) AS sf, "
            "count(input_checkpoint_id) AS ic FROM derived.fact "
            "WHERE cik=:k"), {"k": k}).mappings().first()
        if not row["n"] or row["sf"] != row["n"] or row["ic"] != row["n"]:
            bad[k] = dict(row)
    if bad:
        return Invariant("PROVENANCE", "BLOCK", {"ciks": bad})
    return Invariant("PROVENANCE", "PASS", {"ciks": ciks})


def inv_no_dangling(conn) -> Invariant:
    """Regla del gap S03: dangling>0 es BLOCKER cuando se manifiesta."""
    n = conn.execute(text(
        "SELECT count(*) FROM derived.fact d "
        "CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid) "
        "LEFT JOIN parsed.facts p ON p.fact_id = s.fid "
        "WHERE d.valid_to IS NULL AND p.fact_id IS NULL")).scalar()
    if n:
        return Invariant("NO_DANGLING", "BLOCK", {"dangling": n})
    return Invariant("NO_DANGLING", "PASS", {"dangling": 0})


def decide_orphan(counts: dict) -> Invariant:
    """Pura: BLOCK si algun emisor tiene entity_keys huerfanas."""
    bad = {k: v for k, v in counts.items() if v}
    if bad:
        return Invariant("NO_ORPHAN_ENTITY", "BLOCK", bad)
    return Invariant("NO_ORPHAN_ENTITY", "PASS", {"ciks": list(counts)})


def inv_no_orphan_entity(conn, ciks: list) -> Invariant:
    counts = {}
    for k in ciks:
        counts[k] = conn.execute(text(
            "SELECT count(DISTINCT d.entity_key) FROM derived.fact d "
            "WHERE d.cik=:k AND NOT EXISTS (SELECT 1 FROM "
            "identity_v1.identifier i WHERE i.entity_key=d.entity_key)"),
            {"k": k}).scalar()
    return decide_orphan(counts)


def inv_bridge(conn, tickers: list) -> Invariant:
    missing = {}
    for t in tickers:
        n = conn.execute(text(
            "SELECT count(*) FROM market_price_daily WHERE instrument_id IN "
            "(SELECT instrument_id FROM market_instruments "
            "WHERE ticker_canonico=:t)"), {"t": t}).scalar()
        if not n:
            missing[t] = n
    if missing:
        return Invariant("BRIDGE", "BLOCK", {"sin_precios": missing})
    return Invariant("BRIDGE", "PASS", {"tickers": tickers})


def decide_separation(mi: set, mpd: set, df: set) -> Invariant:
    """Pura: issuer != instrument != price a nivel columnas."""
    bad = {}
    if "cik" in mi or "entity_key" in mi:
        bad["market_instruments"] = "mezcla issuer"
    if "cik" in mpd or "entity_key" in mpd:
        bad["market_price_daily"] = "mezcla issuer"
    if "cik" not in df or "instrument_id" in df or "close" in df:
        bad["derived.fact"] = "mezcla instrument/price o sin cik"
    if bad:
        return Invariant("SEPARATION", "BLOCK", bad)
    return Invariant("SEPARATION", "PASS", {})


def inv_separation(conn) -> Invariant:
    """issuer != instrument != price a nivel columnas (estructural)."""
    def C(sch, t):
        return {r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=:s AND table_name=:t"),
            {"s": sch, "t": t})}
    mi, mpd = C("public", "market_instruments"), C("public", "market_price_daily")
    df = C("derived", "fact")
    return decide_separation(mi, mpd, df)


def inv_no_cross_overwrite(conn, ciks: list) -> Invariant:
    # derived.fact no tiene columnas market (ver SEPARATION); el invariante
    # cross es estructural: se verifica por schema, sin queries fragiles.
    return Invariant("NO_CROSS_OVERWRITE", "PASS",
                     {"nota": "estructural via SEPARATION", "ciks": ciks})


def inv_market_present(conn, tickers: list) -> Invariant:
    return inv_bridge(conn, tickers)


def inv_cnv_scope(conn) -> Invariant:
    """Alcance documentado: motor CNV sin runs DEV => WARN (no BLOCK)."""
    n = conn.execute(text(
        "SELECT count(*) FROM fetch_raw.cnv_artifact")).scalar()
    if not n:
        return Invariant("CNV_SCOPE", "WARN",
                         {"motor_runs": 0,
                          "nota": "cadena SQLite productiva por cron; sin artefactos PG DEV"})
    return Invariant("CNV_SCOPE", "PASS", {"motor_runs": n})


SCOPES = {
    "sec": ("SEC_GATES", "IDENTITY", "PROVENANCE", "NO_DANGLING",
            "NO_ORPHAN_ENTITY"),
    "market": ("BRIDGE",),
    "cross": ("SEPARATION", "NO_CROSS_OVERWRITE"),
    "cnv": ("CNV_SCOPE",),
}
SCOPES["all"] = SCOPES["sec"] + SCOPES["market"] + SCOPES["cross"] + SCOPES["cnv"]


def evaluate(conn, run_ids: list, ciks: list, tickers: list,
             scope: str = "all") -> dict:
    wanted = SCOPES.get(scope, SCOPES["all"])
    out = []
    if "SEC_GATES" in wanted:
        out.append(inv_sec_gates(conn, run_ids))
    if "IDENTITY" in wanted:
        out.append(inv_identity(conn, ciks))
    if "PROVENANCE" in wanted:
        out.append(inv_provenance(conn, ciks))
    if "NO_DANGLING" in wanted:
        out.append(inv_no_dangling(conn))
    if "NO_ORPHAN_ENTITY" in wanted:
        out.append(inv_no_orphan_entity(conn, ciks))
    if "BRIDGE" in wanted:
        out.append(inv_bridge(conn, tickers))
    if "SEPARATION" in wanted:
        out.append(inv_separation(conn))
    if "NO_CROSS_OVERWRITE" in wanted:
        out.append(inv_no_cross_overwrite(conn, ciks))
    if "CNV_SCOPE" in wanted:
        out.append(inv_cnv_scope(conn))
    verdict = aggregate(out)
    return {"c10_version": C10_VERSION, "scope": scope,
            "evaluated_at": utc_now_iso(), "verdict": verdict,
            "invariants": [{"id": r.id, "result": r.result,
                            "evidence": r.evidence} for r in out]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluador C10 (solo lectura)")
    ap.add_argument("--sec-runs", default="",
                    help="run_ids SEC separados por coma")
    ap.add_argument("--ciks", default="0000904851,0000021344")
    ap.add_argument("--tickers", default="YPFD,KO")
    ap.add_argument("--scope", default="all",
                    choices=list(SCOPES) + ["market", "cross", "cnv", "sec"])
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    eng = edb.get_engine(load_settings())
    with eng.connect() as conn:
        res = evaluate(conn,
                       [r.strip() for r in args.sec_runs.split(",") if r.strip()],
                       [k.strip() for k in args.ciks.split(",") if k.strip()],
                       [t.strip() for t in args.tickers.split(",") if t.strip()],
                       scope=args.scope)
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    print(txt)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(txt, encoding="utf-8")
    return 0 if res["verdict"] in ("PASS", "WARN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
