# -*- coding: utf-8 -*-
"""C11_CERTIFICACION — CAPA 11: CERTIFICACIÓN INDEPENDIENTE (R4).

`VALIDACIÓN (C10) → CERTIFICACIÓN (C11) → PUBLICACIÓN (C12)`.
C11 LEE la evidencia ya producida por C10 (`engine.runs` + `engine.stage_runs`
+ `engine.checkpoints`) y emite un **acta de certificación** en
`engine.certifications`. NO calcula datos, NO modifica tablas de cálculo, NO
reemplaza VALIDACIÓN, NO publica.

UNA responsabilidad primaria: CERTIFICAR.

Lo que C11 NO hace (invariantes R4, doc
`docs/review/bymastocks_reingenieria/fase_definir/04_R4_CAPA11.md`):
  * INV1 — READ-ONLY sobre capas 1-10: única escritura = `engine.certifications`.
  * INV2 — No se acopla a `validar_suite` / `f6_sec` / `40_certificar` como
           autoridad: puede leer sus resultados, nunca delegarles el sello.
  * INV3 — Veredicto determinista y reproducible: mismas `stage_runs` →
           mismo `cert_hash`.
  * INV4 — `gate_status=BLOCK` en cualquier etapa → NEGADA; `WARNING` →
           CERTIFICADA_CON_OBSERVACIONES; `PASS` → limpia.
  * INV5 — Salida PRIMARIA: PostgreSQL `engine.certifications`. El JSON de
           evidencia es SOLO artefacto, no fuente primaria.
  * INV6 — Inmutables tras emitirse: un `cert_id` por `run_id`; re-ejecución
           idempotente (ON CONFLICT DO NOTHING), sin reescritura del acta.
  * INV7 — INFORMATIVA: NO bloquea API ni PUBLICACIÓN (eso es R5).

Actualmente la activación es INFORMATIVA (INV7): C11 emite el acta y la
reporta, pero no condiciona C12.

cerH_hash — determinismo:
  * regla   : `cert_rule` (por defecto `c11-rule-v1`), parte del hash.
  * inputs  : run_id + pipeline_version + run_status + el report JSON de cada
              etapa (fila final con report, por stage, orden stage_id).
  * canonicalización: JSON con sort_keys=True, separadores compactos,
              ensure_ascii=False (mismo texto → mismo digest).
  * algoritmo: sha256 hexadecimal minúscula (64 chars).
  * NO incluye timestamps (generado_at) ni aleatoriedad. Dos ejecuciones con
    exactamente la misma evidencia producen exactamente el mismo cert_hash.

Uso:
  python scripts/engine/c11_certificar.py --run-id <RUN_ID> [--json-output boletin/]
  python scripts/engine/c11_certificar.py [--mode FULL] [--json-output boletin/]

Salida: acta JSON por stdout. Exit 0 = acta emitida (o re-lectura idempotente).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
from engine.report import StageReport  # noqa: E402
from engine.states import GateStatus  # noqa: E402

SCRIPT = "scripts/engine/c11_certificar.py"
DEFAULT_RULE = "c11-rule-v1"
OBJETO = "RUN"
TERMINALES = {"OK", "BLOCKED", "ABORTED"}


def canonical_json(obj) -> str:
    """Serialización canónica (misma estructura → mismo string)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stage_report_from_dict(d: dict) -> StageReport:
    """Rehidrata el report JSONB almacenado a StageReport.

    Reusa la VALIDACIÓN de C10 (`StageReport.validate`) sin duplicarla: C11
    consume la evidencia de C10, no la recalcula.
    """
    return StageReport(
        stage=d.get("stage", ""),
        run_id=d.get("run_id", ""),
        mode=d.get("mode", ""),
        started_at=d.get("started_at", ""),
        finished_at=d.get("finished_at", ""),
        gate=GateStatus(d["gate"]["status"]),
        input_checkpoint_id=d.get("input", {}).get("checkpoint_id"),
        input_rows=d.get("input", {}).get("rows", 0),
        expected=d.get("coverage", {}).get("expected", -1),
        parsed=d.get("coverage", {}).get("parsed", 0),
        rejected=d.get("coverage", {}).get("rejected", 0),
        rejected_by_reason=d.get("coverage", {}).get("by_reason", {}),
        hash_in=d.get("integrity", {}).get("hash_in"),
        hash_out=d.get("integrity", {}).get("hash_out"),
        gate_reasons=d.get("gate", {}).get("reasons", []),
        checks=d.get("gate", {}).get("checks", []),
        nulls_count=d.get("nulls", {}).get("count", 0),
        nulls_by_reason=d.get("nulls", {}).get("by_reason", {}),
        parser_version=d.get("code", {}).get("parser_version"),
        script=d.get("code", {}).get("script"),
        git_commit=d.get("code", {}).get("git_commit"),
    )


@dataclass
class _StageEval:
    stage_id: str
    state: str | None
    gate_status: str | None
    report: dict
    report_sha256: str
    result: str                      # PASS | WARNING | BLOCK | INSUF
    reason: str | None = None
    check_count: int = 0
    expected: int = 0
    parsed: int = 0
    rejected: int = 0


def _evaluate_report(report: dict, gate_status: str | None,
                     stage_id: str) -> _StageEval:
    """Evalúa un report de una etapa como evidencia C10 consumible.

    - report ausente o no-objeto            → INSUF (sin evidencia)
    - `gate_status` ausente                 → INSUF (gate externo no decidido)
    - report inválido según C10             → INSUF (validación de C10 falla)
    - gate_status contradictorio al report  → INSUF (integridad rota)
    - válido: se clasifica por gate_status  → PASS | WARNING | BLOCK
    """
    def mk(result: str, reason: str | None = None,
           check_count: int = 0, expected: int = 0,
           parsed: int = 0, rejected: int = 0) -> _StageEval:
        return _StageEval(
            stage_id=stage_id,
            state=None,
            gate_status=gate_status,
            report=report or {},
            report_sha256=sha256_hex(canonical_json(report or {})),
            result=result,
            reason=reason,
            check_count=check_count,
            expected=expected,
            parsed=parsed,
            rejected=rejected,
        )

    if not gate_status:
        return mk("INSUF", "sin gate_status (evidencia C10 no decidida)")
    if gate_status not in {e.value for e in GateStatus}:
        return mk("INSUF", f"gate_status invalido: {gate_status!r}")
    try:
        rep = _stage_report_from_dict(report)
        rep.validate()
    except Exception as e:  # noqa: BLE001 — cualquier fallo = evidencia no válida
        return mk("INSUF", f"report invalido: {e}")
    if rep.gate.value != gate_status:
        return mk("INSUF",
                  f"gate_status {gate_status!r} contradice report ({rep.gate.value})")
    return mk(gate_status,
              check_count=len(rep.checks), expected=rep.expected,
              parsed=rep.parsed, rejected=rep.rejected)


def _stages_final(conn, run_id: str) -> list[dict]:
    """La evidencia final por etapa: la fila con report de cada stage (max id)."""
    rows = conn.execute(text(
        """
        SELECT stage_id, state, gate_status, report
          FROM (
               SELECT stage_id, state, gate_status, report,
                      row_number() OVER (
                          PARTITION BY stage_id ORDER BY id DESC) AS rn
                 FROM engine.stage_runs
                WHERE run_id = :run AND report IS NOT NULL
               ) t
         WHERE rn = 1
         ORDER BY stage_id
        """
    ), {"run": run_id}).mappings().all()
    return [dict(r) for r in rows]


def _checkpoints_ctx(conn, run_id: str) -> dict:
    out: dict[str, dict] = {}
    for r in conn.execute(text(
        "SELECT stage_id, checkpoint_id, input_hash, code_version, contract_version "
        "  FROM engine.checkpoints WHERE run_id = :run ORDER BY stage_id"),
            {"run": run_id}).mappings().all():
        out[r["stage_id"]] = {
            "stage_id": r["stage_id"],
            "checkpoint_id": r["checkpoint_id"],
            "input_hash": r["input_hash"],
            "code_version": r["code_version"],
            "contract_version": r["contract_version"],
        }
    return out


def evaluar_evidencia(run: dict, filas: list[dict], cp_ctx: dict,
                      stage_ids_presentes: list[str]) -> dict:
    """Produce (stages, counts, veredicto, motivo) de forma PERMUTA-PURA.

    Determinista: solo depende de la evidencia leída, nunca de reloj/azar.
    """
    stages: list[_StageEval] = []
    reportados = {f["stage_id"] for f in filas}
    for st_id in sorted(set(stage_ids_presentes)):
        if st_id in reportados:
            fila = next(f for f in filas if f["stage_id"] == st_id)
            eval_ = _evaluate_report(fila.get("report") or {},
                                     fila.get("gate_status"), st_id)
            eval_.state = fila.get("state")
        else:
            eval_ = _StageEval(
                stage_id=st_id, state=None, gate_status=None, report={},
                report_sha256=sha256_hex(canonical_json({})), result="INSUF",
                reason="etapa declarada sin report (sin evidencia C10)")
        stages.append(eval_)

    count = lambda r: sum(1 for s in stages if s.result == r)  # noqa: E731
    p, w, b, i = count("PASS"), count("WARNING"), count("BLOCK"), count("INSUF")
    total = len(stages)

    veredicto = "CERTIFICADA"
    motivo: str | None = None

    if run["status"] not in TERMINALES:
        veredicto, motivo = "NEGADA", "corrida en curso (sin evidencia C10 final)"
    elif run["status"] == "ABORTED":
        veredicto, motivo = "NEGADA", "corrida abortada (evidencia C10 incompleta)"
    elif not stages:
        veredicto, motivo = "NEGADA", "sin stage_runs (sin evidencia C10)"
    elif i > 0:
        insuf = ", ".join(f"{s.stage_id}:{s.reason}" for s in stages if s.result == "INSUF")
        veredicto, motivo = "NEGADA", f"evidencia C10 insuficiente — {insuf}"
    elif b > 0:
        bloq = ", ".join(s.stage_id for s in stages if s.result == "BLOCK")
        veredicto, motivo = "NEGADA", f"gate BLOCK en etapa(s): {bloq}"
    elif w > 0:
        warn = ", ".join(s.stage_id for s in stages if s.result == "WARNING")
        veredicto, motivo = "CERTIFICADA_CON_OBSERVACIONES", f"observaciones: {warn}"
    elif run["status"] == "BLOCKED":
        # corrida dice BLOCKED pero ninguna etapa lo declara: inconsistencia
        veredicto, motivo = "NEGADA", "inconsistencia: corrida BLOCKED sin etapa BLOCK en stage_runs"

    evidence = []
    for s in stages:
        e = {
            "stage_id": s.stage_id,
            "state": s.state,
            "gate_status": s.gate_status,
            "result": s.result,
            "reason": s.reason,
            "report_sha256": s.report_sha256,
            "check_count": s.check_count,
            "expected": s.expected,
            "parsed": s.parsed,
            "rejected": s.rejected,
        }
        if s.stage_id in cp_ctx:
            e["checkpoint"] = cp_ctx[s.stage_id]
        evidence.append(e)

    return {
        "veredicto": veredicto,
        "motivo": motivo,
        "stages_total": total,
        "stages_pass": p,
        "stages_warn": w,
        "stages_block": b,
        "stages_insuf": i,
        "evidence": evidence,
        "stages_raw": stages,
    }


def cert_hash(rule: str, run: dict, filas: list[dict],
              stage_ids_presentes: list[str]) -> str:
    """cert_hash determinista de la evidencia (INV3). No incluye reloj/azar."""
    payload = {
        "cert_rule": rule,
        "run_id": run["run_id"],
        "pipeline_version": run["pipeline_version"],
        "run_status": run["status"],
        "etapas_declaradas": sorted(stage_ids_presentes),
        "stages": [
            {
                "stage_id": f["stage_id"],
                "state": f.get("state"),
                "gate_status": f.get("gate_status"),
                "report": f.get("report") or {},
            }
            for f in sorted(filas, key=lambda x: x["stage_id"])
        ],
    }
    return sha256_hex(canonical_json(payload))


def _acta(run: dict, rule: str, resultado: dict, run_hash: str) -> dict:
    return {
        "certification_id": f"c11-{run['run_id']}",
        "run_id": run["run_id"],
        "objeto": OBJETO,
        "veredicto": resultado["veredicto"],
        "cert_rule": rule,
        "cert_hash": run_hash,
        "pipeline_version": run["pipeline_version"],
        "stages_total": resultado["stages_total"],
        "stages_pass": resultado["stages_pass"],
        "stages_warn": resultado["stages_warn"],
        "stages_block": resultado["stages_block"],
        "stages_insuf": resultado["stages_insuf"],
        "evidence": resultado["evidence"],
        "motivo": resultado["motivo"],
        "generado_por": SCRIPT,
        "generado_at": _utc_now(),
    }


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def certificar_run(engine: Engine, run_id: str, rule: str = DEFAULT_RULE) -> dict:
    """Evalúa un run, emite (o re-lee) su acta y devuelve el acta.

    Única escritura de C11: `engine.certifications`. Idempotente por
    `ux_cert_run` + ON CONFLICT DO NOTHING (INV6).
    """
    with engine.connect() as conn:
        run_row = conn.execute(text(
            "SELECT run_id, status, mode, pipeline_version, git_commit "
            "  FROM engine.runs WHERE run_id = :r"), {"r": run_id}).mappings().first()
        if run_row is None:
            raise ValueError(f"run inexistente: {run_id}")
        run = dict(run_row)
        filas = _stages_final(conn, run_id)
        cp_ctx = _checkpoints_ctx(conn, run_id)
        stage_ids_presentes = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT stage_id FROM engine.stage_runs "
            " WHERE run_id = :run ORDER BY stage_id"), {"run": run_id}).all()]

    resultado = evaluar_evidencia(run, filas, cp_ctx, stage_ids_presentes)
    run_hash = cert_hash(rule, run, filas, stage_ids_presentes)
    acta = _acta(run, rule, resultado, run_hash)

    with engine.begin() as conn:
        insertado = conn.execute(text(
            """
            INSERT INTO engine.certifications
                (certification_id, run_id, objeto, veredicto, cert_rule, cert_hash,
                 pipeline_version, stages_total, stages_pass, stages_warn,
                 stages_block, stages_insuf, evidence, motivo, generado_por)
            VALUES
                (:cid, :run_id, :objeto, :veredicto, :rule, :hash,
                 :pv, :tot, :pass, :warn, :block, :insuf,
                 CAST(:evidence AS JSONB), :motivo, :generado_por)
            ON CONFLICT (run_id) DO NOTHING
            RETURNING certification_id, cert_hash
            """
        ), {
            "cid": acta["certification_id"], "run_id": run_id,
            "objeto": acta["objeto"], "veredicto": acta["veredicto"],
            "rule": rule, "hash": acta["cert_hash"], "pv": acta["pipeline_version"],
            "tot": acta["stages_total"], "pass": acta["stages_pass"],
            "warn": acta["stages_warn"], "block": acta["stages_block"],
            "insuf": acta["stages_insuf"],
            "evidence": json.dumps(acta["evidence"], ensure_ascii=False),
            "motivo": acta["motivo"], "generado_por": SCRIPT,
        }).first()

    if insertado is None:
        # Re-ejecución idempotente: el acta ya existe. Se lee, no se reescribe.
        with engine.connect() as conn:
            existente = conn.execute(text(
                "SELECT * FROM engine.certifications WHERE run_id = :r"),
                {"r": run_id}).mappings().first()
        acta = dict(existente)
        # Normalizar tipos nativos de la fila (datetime/JSONB) a JSON-safe para
        # que el acta devuelta sea idéntica en forma al insertado (INV3).
        acta["generado_at"] = acta["generado_at"].isoformat()
        if isinstance(acta.get("evidence"), str):
            acta["evidence"] = json.loads(acta["evidence"])
    return acta


def _latest_run_id(engine: Engine, mode: str | None) -> str | None:
    q = ("SELECT run_id FROM engine.runs WHERE status IN :t "
         "ORDER BY started_at DESC LIMIT 1")
    params: dict = {"t": tuple(TERMINALES)}
    if mode:
        q = ("SELECT run_id FROM engine.runs WHERE status IN :t AND mode = :m "
             "ORDER BY started_at DESC LIMIT 1")
        params["m"] = mode
    with engine.connect() as conn:
        return conn.execute(text(q), params).scalar()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="c11_certificar", description=__doc__)
    ap.add_argument("--run-id", help="run a certificar (último terminal por defecto)")
    ap.add_argument("--mode", help="filtrar por mode (FAST/FULL/AUDIT)")
    ap.add_argument("--rule", default=DEFAULT_RULE, help="regla/versión de certificación")
    ap.add_argument("--json-output", help="directorio para el artefacto JSON (opcional)")
    args = ap.parse_args(argv)

    settings = load_settings()          # EXT-010 si apunta a prod sin allow_prod
    engine = edb.get_engine(settings)

    if args.mode and args.mode not in {"FAST", "FULL", "AUDIT"}:
        print(f"[error] mode invalido: {args.mode}", file=sys.stderr)
        return 2

    run_id = args.run_id or _latest_run_id(engine, args.mode)
    if not run_id:
        print("[error] no hay corrida para certificar (run_id o --mode)", file=sys.stderr)
        return 2

    print(f"[config] target={settings.describe()}")
    print(f"[run] run_id={run_id}")

    acta = certificar_run(engine, run_id, rule=args.rule)

    print("--- acta ---")
    print(json.dumps({k: v for k, v in acta.items() if k != "evidence"},
                     ensure_ascii=False, indent=2))
    print("evidence:")
    for e in acta.get("evidence", []):
        print(f"   {e.get('stage_id')}  result={e.get('result'):8s} "
              f"gate={e.get('gate_status')}  checks={e.get('check_count')} "
              f"expected={e.get('expected')} parsed={e.get('parsed')} "
              f"rejected={e.get('rejected')}")

    if args.json_output:
        out_dir = Path(args.json_output)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"certificacion_c11_{run_id}.json"
        path.write_text(json.dumps(acta, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"[artefacto] evidencia JSON (no primaria): {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())