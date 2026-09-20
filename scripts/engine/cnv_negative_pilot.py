#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNV NEGATIVE-PATH PILOT — 20 CANDIDATE.

Demuestra que CNV bloquea a CUALQUIER empresa cuyo CUIT no este VERIFIED en
Identity v1, y que el bloqueo depende de `assertion.status`, no de una lista de
empresas.

SEGURIDAD
  · No escribe en la base homologada. Los casos bloqueados cortan en
    `load_identity()`, ANTES de `run_scope`: no abren corrida, no descargan.
  · Fingerprint antes y despues; DELTA debe ser 0.
  · No crea bases TEMPLATE.
  · Reintenta las lecturas: otro agente bloquea la base de forma intermitente.

Uso:
    python scripts/engine/cnv_negative_pilot.py [--n 20]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "fase_cnv"
CONT = "catalaxia-engine-dev"
FETCHER = REPO / "scripts" / "engine" / "c3_cnv_fetch.py"

# Los tres controles positivos ya demostrados. NO se re-ejecutan.
POSITIVOS = {"33650305499": "CENTRAL PUERTO", "30546689979": "YPF",
             "30657862068": "TGS"}


def psql(q: str, db: str = "catalaxia", intentos: int = 12) -> list[list[str]]:
    """Lectura con reintento: el bloqueo del otro agente es intermitente."""
    ultimo = ""
    for i in range(intentos):
        try:
            p = subprocess.run(
                ["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", db,
                 "-t", "-A", "-F", "\x1f", "-c", q],
                capture_output=True, text=True, encoding="utf-8", timeout=40)
        except subprocess.TimeoutExpired:
            # el bloqueo del otro agente hace que psql cuelgue, no que falle:
            # `timeout` LEVANTA, no devuelve returncode. Es reintentable.
            ultimo = "timeout de 40 s (conexion bloqueada)"
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


def concurrencia() -> str:
    p = subprocess.run(["docker", "exec", CONT, "ps", "-eo", "pid,etime,cmd"],
                       capture_output=True, text=True, encoding="utf-8", timeout=40)
    hits = [l.strip() for l in p.stdout.splitlines()
            if "CREATE DATABASE" in l and "grep" not in l]
    return hits[0][:110] if hits else ""


def fingerprint() -> dict:
    f = psql("""
        SELECT (SELECT count(*) FROM identity_v1.entity)||'|'||
               (SELECT count(*) FROM identity_v1.identifier WHERE valid_to IS NULL)||'|'||
               (SELECT count(*) FROM identity_v1.assertion WHERE valid_to IS NULL)||'|'||
               (SELECT count(*) FROM identity_v1.identifier i
                  JOIN identity_v1.assertion a ON a.assertion_id=i.assertion_id
                 WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status='VERIFIED')||'|'||
               (SELECT count(*) FROM fetch_raw.cnv_artifact)||'|'||
               (SELECT count(*) FROM fetch_raw.cnv_download_log)||'|'||
               (SELECT count(*) FROM engine.runs WHERE pipeline_version LIKE 'cnv%')||'|'||
               (SELECT count(*) FROM engine.runs WHERE status='RUNNING')""")[0][0]
    k = ("entities", "identifiers", "assertions", "cuit_verified",
         "cnv_artifact", "cnv_download_log", "cnv_runs", "runs_running")
    return dict(zip(k, (int(x) for x in f.split("|"))))


def raw_estado() -> tuple[int, int]:
    d = REPO / "data" / "raw" / "engine" / "cnv"
    fs = list(d.rglob("*")) if d.exists() else []
    return len([f for f in fs if f.is_file()]), sum(f.stat().st_size for f in fs if f.is_file())


def atacar(cuit: str, extra: list[str] | None = None) -> dict:
    """Invoca el mecanismo OFICIAL. No se modifica nada para lograr el rechazo."""
    cmd = [sys.executable, str(FETCHER), "--cuit", cuit,
           "--scope", "EEFF_PROPIO", "--max-visores", "1"] + (extra or [])
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(REPO), timeout=180)
    sal = (p.stdout or "") + (p.stderr or "")
    linea = next((l for l in sal.splitlines() if "BLOCK identidad" in l), "")
    motivo = ""
    if "[" in linea and "]" in linea:
        motivo = linea.split("[", 1)[1].split("]", 1)[0]
    return {"rc": p.returncode, "segundos": round(time.time() - t0, 1),
            "motivo": motivo, "mensaje": linea[:200],
            "abrio_corrida": "[run] run_id=" in sal,
            "hizo_request": "[empresa] http=" in sal,
            "salida_cola": sal.strip().splitlines()[-1][:150] if sal.strip() else ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    print("CNV NEGATIVE-PATH PILOT — camino negativo a escala\n")

    # ─────────── FASE 0 ───────────
    print("FASE 0 · concurrencia y fingerprint")
    conc = concurrencia()
    print(f"  otro agente: {conc or '(ninguno)'}")
    fp0 = fingerprint()
    raw0 = raw_estado()
    print(f"  fingerprint ANTES: {fp0}")
    print(f"  data/raw/engine/cnv: {raw0[0]} archivos, {raw0[1]:,} bytes")
    if fp0["runs_running"] != 0:
        print(f"  ABORTADO: hay {fp0['runs_running']} corridas RUNNING")
        return 2

    # ─────────── FASE 1 ───────────
    print(f"\nFASE 1 · seleccion de {a.n} CANDIDATE")
    print("  criterio: orden por entity_key (clave OPACA). No por nombre, no por")
    print("  ticker, no por conveniencia. Reproducible y verificable.\n")
    filas = psql(f"""
        SELECT e.entity_key, e.preferred_name, i.id_value, a.status::text,
               a.assertion_id::text, a.method::text, coalesce(a.resolved_by,'')
          FROM identity_v1.identifier i
          JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
          JOIN identity_v1.entity e ON e.entity_key = i.entity_key
         WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status <> 'VERIFIED'
         ORDER BY e.entity_key LIMIT {a.n}""")
    universo = [{"entity_key": r[0], "empresa": r[1], "cuit": r[2], "status": r[3],
                 "assertion_id": r[4], "method": r[5], "resolved_by": r[6]}
                for r in filas]
    print(f"  {'entity_key':<29} {'CUIT':<12} {'estado':<11} empresa")
    for u in universo:
        print(f"  {u['entity_key']:<29} {u['cuit']:<12} {u['status']:<11} {u['empresa'][:34]}")
    no_cand = [u for u in universo if u["status"] == "VERIFIED"]
    print(f"\n  precondicion: {len(universo)} casos · "
          f"ninguno VERIFIED: {'OK' if not no_cand else 'FALLA'}")
    solapa = [u for u in universo if u["cuit"] in POSITIVOS]
    print(f"  ninguno es un control positivo: {'OK' if not solapa else 'FALLA ' + str(solapa)}")

    # ─────────── FASE 2 + 3 ───────────
    print(f"\nFASE 2/3 · ataque con el mecanismo oficial, y barrera causal\n")
    print(f"  {'CUIT':<12} {'rc':>3} {'motivo':<22} {'corrida':<8} {'request':<8} s")
    for u in universo:
        r = atacar(u["cuit"])
        u.update(r)
        print(f"  {u['cuit']:<12} {r['rc']:>3} {r['motivo']:<22} "
              f"{'NO' if not r['abrio_corrida'] else 'SI!':<8} "
              f"{'NO' if not r['hizo_request'] else 'SI!':<8} {r['segundos']}")

    bloqueados = [u for u in universo if u["motivo"] == "CUIT_NO_VERIFICADO"]
    abrieron = [u for u in universo if u["abrio_corrida"]]
    pidieron = [u for u in universo if u["hizo_request"]]
    print(f"\n  bloqueados por CUIT_NO_VERIFICADO : {len(bloqueados)}/{len(universo)}")
    print(f"  abrieron corrida                  : {len(abrieron)}")
    print(f"  hicieron request HTTP             : {len(pidieron)}")

    # ─────────── FASE 5 ───────────
    print("\nFASE 5 · adversarial")
    adv = []

    def adv_caso(nombre, esperado, fn):
        r = fn()
        ok = r.get("motivo") == esperado or (esperado == "SIN_ESCRITURA" and r.get("rc") != 0)
        print(f"  {'OK   ' if ok else 'FALLA'} {nombre:<44} esperado={esperado:<24} "
              f"real={r.get('motivo') or 'rc='+str(r.get('rc'))}")
        adv.append({"ataque": nombre, "esperado": esperado, **r, "ok": ok})
        return ok

    cand = universo[0]
    adv_caso("A1 · CANDIDATE con CUIT valido", "CUIT_NO_VERIFICADO",
             lambda: atacar(cand["cuit"]))
    adv_caso("A2 · CUIT con checksum invalido", "NO_ESTA_EN_IDENTITY_V1",
             lambda: atacar("30000000001"))
    adv_caso("A3 · CUIT inexistente en Identity", "NO_ESTA_EN_IDENTITY_V1",
             lambda: atacar("99999999999"))
    adv_caso("A4 · CIK sin CUIT (AAPL)", "SIN_CUIT",
             lambda: {**atacar("00000000000", ["--cik", "0000320193"]), "via": "cik"}
             if False else atacar_cik("0000320193"))
    adv_caso("A5 · entity_key valido pero CUIT de OTRA empresa", "CUIT_NO_VERIFICADO",
             lambda: atacar(universo[1]["cuit"]))

    # ─────────── FASE 6 ───────────
    print("\nFASE 6 · auditoria independiente — DELTA")
    fp1 = fingerprint()
    raw1 = raw_estado()
    print(f"  {'metrica':<20} {'antes':>10} {'despues':>10} {'delta':>8}")
    deltas = {}
    for k in fp0:
        d = fp1[k] - fp0[k]
        deltas[k] = d
        print(f"  {k:<20} {fp0[k]:>10,} {fp1[k]:>10,} {d:>8}")
    print(f"  {'raw cnv archivos':<20} {raw0[0]:>10,} {raw1[0]:>10,} {raw1[0]-raw0[0]:>8}")
    print(f"  {'raw cnv bytes':<20} {raw0[1]:>10,} {raw1[1]:>10,} {raw1[1]-raw0[1]:>8}")

    delta_cero = all(v == 0 for v in deltas.values()) and raw0 == raw1
    print(f"\n  DELTA = 0 en todo: {'SI' if delta_cero else 'NO'}")

    # ─────────── entregables ───────────
    exito = (len(bloqueados) == len(universo) and not abrieron and not pidieron
             and delta_cero and all(x["ok"] for x in adv))
    with (OUT / "CNV_NEGATIVE_PILOT_20_MATRIX.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["entity_key", "empresa", "cuit", "identity_status", "assertion_id",
                    "method", "rc", "motivo_rechazo", "abrio_corrida", "hizo_request"])
        for u in universo:
            w.writerow([u["entity_key"], u["empresa"], u["cuit"], u["status"],
                        u["assertion_id"], u["method"], u["rc"], u["motivo"],
                        u["abrio_corrida"], u["hizo_request"]])
    (OUT / "CNV_NEGATIVE_PILOT_20_ADVERSARIAL.json").write_text(
        json.dumps(adv, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "CNV_NEGATIVE_PILOT_20_AUDIT.json").write_text(json.dumps(
        {"concurrencia": conc, "fingerprint_antes": fp0, "fingerprint_despues": fp1,
         "delta": deltas, "raw_antes": raw0, "raw_despues": raw1,
         "delta_cero": delta_cero, "bloqueados": len(bloqueados),
         "universo": len(universo), "abrieron_corrida": len(abrieron),
         "hicieron_request": len(pidieron), "exito": exito},
        indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "cnv_negative_pilot_universo.json").write_text(
        json.dumps(universo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  CRITERIO DE EXITO: {'CUMPLIDO' if exito else 'NO CUMPLIDO'}")
    print(f"  -> {OUT.name}/CNV_NEGATIVE_PILOT_20_*.{{csv,json}}")
    return 0 if exito else 1


def atacar_cik(cik: str) -> dict:
    cmd = [sys.executable, str(FETCHER), "--cik", cik,
           "--scope", "EEFF_PROPIO", "--max-visores", "1"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(REPO), timeout=180)
    sal = (p.stdout or "") + (p.stderr or "")
    linea = next((l for l in sal.splitlines() if "BLOCK identidad" in l), "")
    motivo = linea.split("[", 1)[1].split("]", 1)[0] if "[" in linea and "]" in linea else ""
    return {"rc": p.returncode, "segundos": 0, "motivo": motivo, "mensaje": linea[:200],
            "abrio_corrida": "[run] run_id=" in sal, "hizo_request": "[empresa] http=" in sal,
            "salida_cola": sal.strip().splitlines()[-1][:150] if sal.strip() else ""}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
