# -*- coding: utf-8 -*-
"""
M23 -- Escalamiento por lotes del motor Market Data
====================================================
No reimplementa el motor: orquesta `m2_fetch_engine.run_instrument()` sobre
el universo completo (o un subconjunto) de instrumentos MAPPED. Lo que M22
no necesitaba con 2 instrumentos y M23 sí necesita con cientos:

  RESUME     checkpoint via la tabla YA EXISTENTE `market_raw_runs`: si un
             instrumento ya tiene status='SUCCESS' para este --stage, se
             saltea. No se inventa un estado nuevo -- se reusa el que el
             motor ya escribe en cada corrida.
  RETRY      ademas del retry interno de YahooSource (2 intentos por
             request), una pasada final reintenta solo los que terminaron
             FAILED en este batch (con un sleep mayor). QUARANTINED nunca
             se reintenta solo: es una señal de integridad, no un error
             transitorio, y re-intentar a ciegas podría taparla.
  PACING     sleep configurable entre requests (default mas conservador que
             el golden case: son cientos de tickers, no 2).
  REPORTE    resumen agregado + JSON con el detalle de cada RunReport, bajo
             outputs/docs/fase_market/scale/.

Uso:
  python m6_scale.py --stage smoke-1 --limit 10                # ensayo chico
  python m6_scale.py --stage prod-batch-2026-08-25              # corrida completa
  python m6_scale.py --stage prod-batch-2026-08-25 --resume     # reanudar
  python m6_scale.py --stage prod-batch-2026-08-25 --dry-run    # solo listar
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import m2_fetch_engine as eng
from market_source import YahooSource

OUT_DIR = eng.ROOT / "outputs" / "docs" / "fase_market" / "scale"

SLEEP_DEFAULT = 2.0
RETRY_SLEEP_DEFAULT = 5.0


def ya_exitosos(cur, stage: str) -> set[str]:
    """Instrumentos con status='SUCCESS' en market_raw_runs para este stage.

    'SUCCESS' en esa tabla cubre tanto SUCCESS como SIN_CAMBIOS del
    RunReport (se escribe antes de calcular esa distincion) -- exactamente
    lo que hace falta para decidir 'ya no hace falta re-fetchear esto'.

    Por que esto es seguro ante un crash a mitad de `run_instrument()`: todo
    el camino normal (desde el fetch exitoso hasta el UPSERT de precios) es
    UNA sola transaccion, con un unico `conn.commit()` al final. Un proceso
    matado en cualquier punto intermedio deja CERO filas SUCCESS en
    market_raw_runs para esa corrida (Postgres revierte la transaccion) --
    nunca una fila SUCCESS a medias. Ver F013_M23_CHECKPOINT_CONTRACT.md.
    """
    cur.execute("""SELECT DISTINCT instrument_id FROM market_raw_runs
                   WHERE stage_run_id=%s AND status='SUCCESS'""", (stage,))
    return {r[0] for r in cur.fetchall()}


def cuarentenados_previamente(cur, stage: str):
    """Instrumentos que en una corrida ANTERIOR de este `stage` quedaron en
    cuarentena (regresion de cobertura -- `market_raw_runs.status='PARTIAL'`,
    ver `run_instrument`). `ya_exitosos()` ya los excluye del set SUCCESS
    (correcto, no se saltean), pero sin este chequeo un `--resume` los
    reintentaria en silencio, mezclados con instrumentos jamas intentados --
    exactamente el gap de visibilidad F-013 que un resume ciego tendria.
    Devuelve [(instrument_id, run_id, fetched_at_utc)] de la ULTIMA
    cuarentena por instrumento, no cada corrida."""
    cur.execute("""
        SELECT DISTINCT ON (instrument_id) instrument_id, run_id, fetched_at_utc
        FROM market_raw_runs
        WHERE stage_run_id=%s AND status='PARTIAL'
        ORDER BY instrument_id, fetched_at_utc DESC
    """, (stage,))
    return cur.fetchall()


def auditar_raw_huerfano(iids: list[str], conn=None) -> list[dict]:
    """Solo lectura: compara `data/raw/market/<iid>/<run_id>/` en disco contra
    `market_raw_files.rel_path` en la base. Un directorio en disco sin fila
    correspondiente es RAW huerfano -- el rastro de un `run_instrument()`
    matado a mitad de camino (el archivo ya se escribio en disco ANTES del
    `conn.commit()` que registra `market_raw_files`; si el proceso muere
    entre esos dos pasos, el archivo sobrevive sin fila que lo referencie).
    No borra nada (RAW es inmutable e irrecuperable) -- solo reporta, para
    que un humano decida. Ver F013_M23_CHECKPOINT_CONTRACT.md.

    `conn` es inyectable (default: abre una propia via `eng.pg_conn()`) para
    poder auditar contra una base de test aislada sin pasar por el destino
    de produccion -- si no, la funcion nunca podria probarse contra datos
    reales sin arriesgar produccion."""
    conn_propia = conn is None
    if conn_propia:
        conn = eng.pg_conn()
    huerfanos = []
    try:
        with conn.cursor() as cur:
            for iid in iids:
                base = eng.RAW_BASE / str(iid)
                if not base.is_dir():
                    continue
                cur.execute("""SELECT rel_path FROM market_raw_files f
                               JOIN market_raw_runs r USING (run_id)
                               WHERE r.instrument_id=%s""", (iid,))
                registrados = {eng.ROOT / rel for (rel,) in cur.fetchall()}
                for run_dir in base.iterdir():
                    if not run_dir.is_dir():
                        continue
                    for f in run_dir.iterdir():
                        if f.is_file() and f not in registrados:
                            huerfanos.append({
                                "instrument_id": iid,
                                "run_id": run_dir.name,
                                "path": str(f),
                                "bytes": f.stat().st_size,
                            })
    finally:
        if conn_propia:
            conn.close()
    return huerfanos


def correr_lote(conn, specs, source, stage, sleep_s, con_snapshot):
    reportes = []
    n = len(specs)
    for i, spec in enumerate(specs, 1):
        rep = eng.run_instrument(conn, spec, source, stage, con_snapshot=con_snapshot)
        reportes.append(rep)
        det = ""
        if rep.resumen:
            det = (f" new={rep.resumen['por_tipo'].get('NEW', 0)}"
                   f" changed={rep.resumen['por_tipo'].get('CHANGED', 0)}"
                   f" escritas={rep.resumen['filas_escritas']}")
        print(f"  [{i}/{n}] [{spec.instrument_id}] {spec.ticker_yahoo:<12} "
              f"{rep.status:<12} {rep.rows} ruedas{det}"
              + (f"  ERROR {rep.error}" if rep.error else ""))
        malos = [g for g in rep.gates if g[1] == "INVALID"]
        for g in malos:
            print(f"        GATE {g[0]} INVALID: {g[2]}")
        if i < n:
            time.sleep(sleep_s)
    return reportes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    help="tag de la corrida; tambien es la clave de resume")
    ap.add_argument("--instruments", help="tickers Yahoo separados por coma "
                    "(subconjunto; sin esto, procesa el universo MAPPED completo)")
    ap.add_argument("--limit", type=int, default=None,
                    help="tope de instrumentos a procesar en esta invocacion")
    ap.add_argument("--resume", action="store_true",
                    help="saltear instrumentos ya SUCCESS para este --stage")
    ap.add_argument("--sleep", type=float, default=SLEEP_DEFAULT)
    ap.add_argument("--max-retries", type=int, default=1,
                    help="pasadas adicionales solo sobre los FAILED de este batch")
    ap.add_argument("--retry-sleep", type=float, default=RETRY_SLEEP_DEFAULT)
    ap.add_argument("--no-snapshot", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="solo listar que se procesaria, sin llamar a la fuente")
    ap.add_argument("--audit-raw-orphans", action="store_true",
                    help="solo lectura: reporta RAW en disco sin fila en "
                    "market_raw_files (rastro de crashes previos) y termina")
    ap.add_argument("--json-out", help="default: outputs/docs/fase_market/scale/<stage>.json")
    args = ap.parse_args()

    t_start = time.time()
    started_at = datetime.now(timezone.utc).isoformat()

    # solo pide escritura si de verdad vamos a correr el lote -- --dry-run y
    # --audit-raw-orphans son de lectura y deben poder correr contra
    # produccion sin la guarda F-001 (MARKET_ALLOW_PROD_WRITE) de por medio.
    necesita_escritura = not (args.dry_run or args.audit_raw_orphans)
    conn = eng.pg_conn(write=necesita_escritura)
    cur = conn.cursor()
    specs = eng.cargar_specs(
        cur, args.instruments.split(",") if args.instruments else None, None)
    total_universo = len(specs)

    if args.audit_raw_orphans:
        huerfanos = auditar_raw_huerfano([s.instrument_id for s in specs], conn=conn)
        conn.close()
        if not huerfanos:
            print(f"RAW huerfano: 0 (sobre {total_universo} instrumentos revisados)")
            return 0
        print(f"RAW huerfano: {len(huerfanos)} archivo(s) sin fila en market_raw_files "
              f"-- rastro de corridas matadas a mitad de camino. NO se borra nada.")
        for h in huerfanos:
            print(f"  [{h['instrument_id']}] {h['run_id']} {h['path']} ({h['bytes']}B)")
        return 1

    saltados = []
    if args.resume:
        listos = ya_exitosos(cur, args.stage)
        if listos:
            specs, saltados = (
                [s for s in specs if s.instrument_id not in listos],
                [s for s in specs if s.instrument_id in listos])
        cuarentena_previa = cuarentenados_previamente(cur, args.stage)
        if cuarentena_previa:
            print(f"ATENCION -- {len(cuarentena_previa)} instrumento(s) quedaron en "
                  f"CUARENTENA en una corrida anterior de este stage (regresion de "
                  f"cobertura); este --resume los va a reintentar como si fueran "
                  f"nuevos, sin revision humana previa:")
            for iid, run_id, fetched_at in cuarentena_previa:
                print(f"    [{iid}] ultima cuarentena: {run_id} ({fetched_at})")

    if args.limit:
        specs = specs[:args.limit]
    cur.close()

    print(f"universo MAPPED: {total_universo} | a procesar ahora: {len(specs)} "
          f"| saltados por resume: {len(saltados)} | stage={args.stage}")

    if args.dry_run:
        for s in specs:
            print(f"  [{s.instrument_id}] {s.ticker_yahoo} ({s.currency}, {s.exchange})")
        conn.close()
        return 0

    if not specs:
        print("nada para procesar (todo ya estaba SUCCESS para este stage, o universo vacio)")
        conn.close()
        return 0

    source = YahooSource()
    reportes = correr_lote(conn, specs, source, args.stage, args.sleep,
                           not args.no_snapshot)

    fallidos = [r for r in reportes if r.status == "FAILED"]
    reintentos_log = []
    for ronda in range(1, args.max_retries + 1):
        if not fallidos:
            break
        print(f"\n-- reintento {ronda}/{args.max_retries}: {len(fallidos)} instrumento(s) FAILED --")
        by_iid = {s.instrument_id: s for s in specs}
        specs_retry = [by_iid[r.instrument_id] for r in fallidos
                      if r.instrument_id in by_iid]
        time.sleep(args.retry_sleep)
        nuevos = correr_lote(conn, specs_retry, source, args.stage,
                             args.retry_sleep, not args.no_snapshot)
        reintentos_log.append({"ronda": ronda, "instrumentos": len(specs_retry)})
        # reemplaza en `reportes` el resultado de cada instrumento reintentado
        nuevos_por_iid = {r.instrument_id: r for r in nuevos}
        reportes = [nuevos_por_iid.get(r.instrument_id, r) for r in reportes]
        fallidos = [r for r in reportes if r.status == "FAILED"]

    conn.close()

    por_estado = Counter(r.status for r in reportes)
    cuarentenados = [r for r in reportes if r.status == "QUARANTINED"]
    elapsed = round(time.time() - t_start, 1)

    print(f"\n== resumen batch '{args.stage}' ==")
    print(f"  procesados en esta corrida: {len(reportes)} (de {total_universo} en el universo)")
    for st, n in sorted(por_estado.items()):
        print(f"    {st}: {n}")
    if cuarentenados:
        print("  ATENCION -- instrumentos en QUARANTINED (revisar antes de reintentar a mano):")
        for r in cuarentenados:
            print(f"    [{r.instrument_id}] {r.ticker_yahoo}: {r.error}")
    print(f"  duracion: {elapsed}s")

    reporte_final = {
        "stage": args.stage,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "universo_total": total_universo,
        "procesados_esta_corrida": len(reportes),
        "saltados_por_resume": len(saltados),
        "por_estado": dict(por_estado),
        "reintentos": reintentos_log,
        "instrumentos": [asdict(r) for r in reportes],
    }
    out_path = Path(args.json_out) if args.json_out else OUT_DIR / f"{args.stage}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(reporte_final, indent=2, default=str), encoding="utf-8")
    print(f"  reporte -> {out_path}")

    bloqueante = [r for r in reportes if r.status in ("FAILED", "QUARANTINED")]
    return 1 if bloqueante else 0


if __name__ == "__main__":
    raise SystemExit(main())
