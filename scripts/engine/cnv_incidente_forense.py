#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Forense del incidente CNV_NEGATIVE_PILOT_20 — SOLO LECTURA.

No importa ni reutiliza `cnv_negative_pilot.py`, que es el script que provocó el
incidente. Habla con PostgreSQL por `psql` y reconstruye el alcance con SQL
propio.

NO escribe. NO ejecuta fetch. NO crea bases. NO borra nada.

Uso:
    python scripts/engine/cnv_incidente_forense.py
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "fase_cnv"
RAW_CNV = REPO / "data" / "raw" / "engine" / "cnv"
CONT = "catalaxia-engine-dev"

# Estado declarado ANTES del incidente, tomado de CNV_NEGATIVE_PILOT_20_GATE.md.
# Se trata como una AFIRMACION a verificar, no como un hecho.
DECLARADO_ANTES = {"cnv_artifact": 3955, "cnv_download_log": 3956, "cnv_runs": 49,
                   "entities": 525, "identifiers": 574, "assertions": 608,
                   "cuit_verified": 3, "runs_running": 0}


def psql(q: str, intentos: int = 15) -> list[list[str]]:
    ultimo = ""
    for _ in range(intentos):
        try:
            p = subprocess.run(
                ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "catalaxia",
                 "-t", "-A", "-F", "\x1f", "-c", q],
                capture_output=True, text=True, encoding="utf-8", timeout=45)
        except subprocess.TimeoutExpired:
            ultimo = "timeout (conexion bloqueada por otro agente)"
            time.sleep(12)
            continue
        if p.returncode == 0:
            return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]
        ultimo = (p.stderr or "")[:200]
        time.sleep(12)
    raise SystemExit(f"psql bloqueado tras {intentos} intentos: {ultimo}")


def uno(q: str):
    r = psql(q)
    return r[0][0] if r else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ev, res, ok_total = {}, [], True

    def chk(n, cond, det=""):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else 'ALERTA'} {n:<54} {det}")
        res.append({"control": n, "ok": bool(cond), "detalle": str(det)[:400]})
        if not cond:
            ok_total = False

    print("FORENSE DEL INCIDENTE — CNV_NEGATIVE_PILOT_20\n")
    print("  solo lectura · SQL propio · sin reutilizar el script del incidente\n")

    # ═══════════ FASE 1 · reconstruir el cambio ═══════════
    print("FASE 1 · alcance del cambio")
    ahora = dict(zip(
        ("entities", "identifiers", "assertions", "cuit_verified",
         "cnv_artifact", "cnv_download_log", "cnv_runs", "runs_running"),
        (int(x) for x in uno("""
            SELECT (SELECT count(*) FROM identity_v1.entity)||'|'||
                   (SELECT count(*) FROM identity_v1.identifier WHERE valid_to IS NULL)||'|'||
                   (SELECT count(*) FROM identity_v1.assertion WHERE valid_to IS NULL)||'|'||
                   (SELECT count(*) FROM identity_v1.identifier i
                      JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
                     WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status='VERIFIED')||'|'||
                   (SELECT count(*) FROM fetch_raw.cnv_artifact)||'|'||
                   (SELECT count(*) FROM fetch_raw.cnv_download_log)||'|'||
                   (SELECT count(*) FROM engine.runs WHERE pipeline_version LIKE 'cnv%')||'|'||
                   (SELECT count(*) FROM engine.runs WHERE status='RUNNING')""").split("|"))))
    ev["fingerprint_ahora"] = ahora
    ev["declarado_antes"] = DECLARADO_ANTES
    print(f"  {'metrica':<20} {'declarado antes':>16} {'ahora':>10} {'delta':>8}")
    deltas = {}
    for k, v in DECLARADO_ANTES.items():
        d = ahora[k] - v
        deltas[k] = d
        print(f"  {k:<20} {v:>16,} {ahora[k]:>10,} {d:>8}")
    ev["delta"] = deltas

    esperado = {"cnv_artifact": 2, "cnv_download_log": 2, "cnv_runs": 1}
    inesperados = {k: d for k, d in deltas.items()
                   if d != esperado.get(k, 0)}
    chk("1.1 · el cambio es EXACTAMENTE +1 run, +2 artefactos, +2 logs",
        not inesperados, f"desvios: {inesperados}" if inesperados else "sin desvios")

    # la corrida accidental
    corrida = psql("""
        SELECT run_id, pipeline_version, status, started_at::text, finished_at::text,
               coalesce(git_commit,'')
          FROM engine.runs WHERE pipeline_version LIKE 'cnv%'
         ORDER BY started_at DESC LIMIT 1""")[0]
    ev["corrida"] = dict(zip(("run_id", "pipeline", "status", "started_at",
                              "finished_at", "git"), corrida))
    print(f"\n  corrida accidental:")
    print(f"    run_id      {corrida[0]}")
    print(f"    pipeline    {corrida[1]}   status  {corrida[2]}")
    print(f"    inicio      {corrida[3]}")
    print(f"    fin         {corrida[4]}")

    filas = psql(f"""
        SELECT cuit, entity_key, artifact_kind, artifact_key, sha256, bytes,
               raw_path, first_seen_at::text
          FROM fetch_raw.cnv_artifact WHERE first_seen_run='{corrida[0]}'
         ORDER BY artifact_kind""")
    ev["artefactos"] = [dict(zip(("cuit", "entity_key", "kind", "key", "sha256",
                                  "bytes", "raw_path", "ts"), f)) for f in filas]
    print(f"\n  artefactos creados por esa corrida: {len(filas)}")
    for f in filas:
        print(f"    {f[2]:<14} cuit={f[0]} entity_key={f[1]}")
        print(f"      sha256 {f[4][:32]}…  {int(f[5]):,} bytes")
        print(f"      raw    {f[6][:78]}")

    logs = psql(f"""
        SELECT count(*), count(DISTINCT cuit), string_agg(DISTINCT result,','),
               string_agg(DISTINCT coalesce(http_status::text,'-'),',')
          FROM fetch_raw.cnv_download_log WHERE run_id='{corrida[0]}'""")[0]
    ev["download_log"] = {"filas": int(logs[0]), "cuits": int(logs[1]),
                          "resultados": logs[2], "http": logs[3]}
    print(f"\n  download_log de esa corrida: {logs[0]} filas · "
          f"{logs[1]} CUIT · resultados={logs[2]} · http={logs[3]}")

    # ¿algo fuera de esos objetos?
    otros = uno(f"""
        SELECT (SELECT count(*) FROM parsed.facts)||'|'||
               (SELECT count(*) FROM derived.fact WHERE valid_to IS NULL)||'|'||
               (SELECT count(*) FROM market_price_daily)||'|'||
               (SELECT count(*) FROM fetch_raw.download_log)""")
    ev["otros_workstreams"] = otros
    print(f"\n  otros workstreams (parsed|derived|market_price|sec_download): {otros}")

    # ═══════════ FASE 2 · integridad ═══════════
    print("\nFASE 2 · integridad, auditada de forma independiente")

    chk("2.1 · la corrida cerro correctamente",
        corrida[2] == "OK" and corrida[4] not in (None, "", "None"),
        f"status={corrida[2]} finished_at={corrida[4]}")
    chk("2.2 · no quedan corridas RUNNING", ahora["runs_running"] == 0,
        f"{ahora['runs_running']}")
    chk("2.3 · Identity NO fue modificada",
        deltas["entities"] == deltas["identifiers"] == deltas["assertions"]
        == deltas["cuit_verified"] == 0,
        f"entities={deltas['entities']} identifiers={deltas['identifiers']} "
        f"assertions={deltas['assertions']} cuit_verified={deltas['cuit_verified']}")

    cuits = {f[0] for f in filas}
    chk("2.4 · todos los artefactos son del MISMO CUIT", len(cuits) == 1, str(cuits))
    ek = {f[1] for f in filas}
    chk("2.5 · todos comparten el mismo entity_key", len(ek) == 1, str(ek))

    dup = uno(f"""
        SELECT count(*) FROM (SELECT artifact_kind, artifact_key, sha256
          FROM fetch_raw.cnv_artifact GROUP BY 1,2,3 HAVING count(*)>1) x""")
    chk("2.6 · sin artefactos duplicados en toda la tabla", dup == "0", f"{dup}")

    huerf = uno(f"""
        SELECT count(*) FROM fetch_raw.cnv_artifact a
         WHERE a.first_seen_run='{corrida[0]}'
           AND NOT EXISTS (SELECT 1 FROM fetch_raw.cnv_download_log d
                            WHERE d.run_id=a.first_seen_run AND d.sha256=a.sha256)""")
    chk("2.7 · cada artefacto tiene su fila de descarga", huerf == "0",
        f"{huerf} sin correspondencia")

    sin_prov = uno(f"""
        SELECT count(*) FROM fetch_raw.cnv_artifact
         WHERE first_seen_run='{corrida[0]}'
           AND (sha256 IS NULL OR raw_path IS NULL OR cuit IS NULL
                OR entity_key IS NULL OR endpoint IS NULL)""")
    chk("2.8 · provenance completa en los artefactos nuevos", sin_prov == "0",
        f"{sin_prov} incompletos")

    # hashes contra disco
    verif, faltan, difieren = 0, [], []
    for f in filas:
        p = RAW_CNV / f[6] if not str(f[6]).startswith("CUIT") else RAW_CNV / f[6]
        if not p.exists():
            p2 = REPO / "data" / "raw" / "engine" / f[6]
            p = p2 if p2.exists() else p
        if not p.exists():
            faltan.append(f[6])
            continue
        real = hashlib.sha256(p.read_bytes()).hexdigest()
        if real == f[4]:
            verif += 1
        else:
            difieren.append(f[6])
    chk("2.9 · el sha256 de cada artefacto coincide con el archivo en disco",
        verif == len(filas), f"{verif}/{len(filas)} verificados · "
        f"faltan {len(faltan)} · difieren {len(difieren)}")
    ev["hashes_verificados"] = {"ok": verif, "faltan": faltan, "difieren": difieren}

    # ═══════════ FASE 3 · legitimidad ═══════════
    print("\nFASE 3 · el dato agregado, ¿es legitimo?")
    cuit = list(cuits)[0] if cuits else None
    aut = psql(f"""
        SELECT a.status::text, a.method::text, coalesce(a.resolved_by,''),
               left(coalesce(a.evidence::text,''), 90), i.entity_key
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
         WHERE i.id_type='CUIT' AND i.id_value='{cuit}' AND i.valid_to IS NULL
           AND a.status='VERIFIED'""")
    ev["autorizacion"] = [dict(zip(("status", "method", "resolved_by", "evidence",
                                    "entity_key"), r)) for r in aut]
    chk("3.1 · el CUIT tenia una assertion VERIFIED vigente", len(aut) >= 1,
        f"{len(aut)} assertion(es) VERIFIED para el CUIT {cuit}")
    if aut:
        print(f"    status={aut[0][0]} method={aut[0][1]} por={aut[0][2]}")
    chk("3.2 · el entity_key del artefacto coincide con el de Identity",
        bool(aut) and aut[0][4] in ek, f"artefacto={ek} identity={aut[0][4] if aut else '-'}")

    ajenos = uno(f"""
        SELECT count(*) FROM fetch_raw.cnv_download_log
         WHERE run_id='{corrida[0]}' AND cuit <> '{cuit}'""")
    chk("3.3 · ninguna descarga de esa corrida pertenece a otro CUIT", ajenos == "0",
        f"{ajenos} ajenas")

    endpoints = psql(f"""
        SELECT DISTINCT endpoint FROM fetch_raw.cnv_download_log
         WHERE run_id='{corrida[0]}'""")
    fuera = [e[0] for e in endpoints if "cnv.gov.ar" not in e[0]]
    chk("3.4 · todos los endpoints son de CNV", not fuera, f"{len(endpoints)} endpoints")
    ev["endpoints"] = [e[0][:100] for e in endpoints]

    veredicto = ("INCIDENTE_CONTROLADO_SIN_CORRUPCION" if ok_total
                 else "INCIDENTE_REQUIERE_REMEDIACION")
    print(f"\n  {sum(1 for r in res if r['ok'])}/{len(res)} controles OK")
    print(f"\n  CLASIFICACION: {veredicto}")

    ev["controles"] = res
    ev["veredicto"] = veredicto
    (OUT / "CNV_NEGATIVE_PILOT_20_INCIDENT_AUDIT.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("  evidencia -> outputs/docs/fase_cnv/CNV_NEGATIVE_PILOT_20_INCIDENT_AUDIT.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
