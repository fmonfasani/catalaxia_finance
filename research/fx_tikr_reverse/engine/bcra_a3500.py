#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collector BCRA A3500 — PRIORIDAD 1 (fuente primaria, sin auth).

Fuente primaria: API Estadísticas Cambiarias BCRA v1.0 (VERIFICADO POR EJECUCIÓN
2026-09-15: GET Maestros/Divisas y Cotizaciones responden 200 sin credenciales).
  - GET https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones?fecha=YYYY-MM-DD
    -> {status, results:{fecha|None, detalle:[{codigoMoneda, tipoPase, tipoCotizacion}]}}
    USD: codigoMoneda=USD, descripcion=DOLAR E.E.U.U., tipoCotizacion = referencia
    A3500/mayorista del día hábil (ej. 2023-09-29 -> 349.95; 2023-12-29 -> 808.45).
    Fines de semana/feriados -> detalle=[] y fecha=None (sin backfill del servidor).
  - Rango: GET .../Cotizaciones/USD?fechadesde=&fechahasta= (máx. 1000 por página).

Regla OBS-V1 (congelada en 00_DEFINIR/target_dates.csv): para cada target_date se
resuelve la última publicación con observation_date <= target y lag <= 5 días.
Este collector persiste el crudo diario; la resolución OBS-V1 vive en universe.py.

RAW: raw/bcra/a3500/YYYY-MM-DD.json (envelope con meta + payload íntegro).
Cada archivo contiene: source_url, retrieved_at, source_date, sha256 (del payload
canónico), http_status. RAW inmutable vía write_raw_noreplace (common.py).

Idempotencia: clave canónica = source_date. Re-correr con mismo contenido ->
EXISTS_IDENTICAL (no duplica, no reescribe). Contenido distinto -> VERSIONED.

Uso:
  python engine/bcra_a3500.py --from 2023-09-01 --to 2026-06-30
  python engine/bcra_a3500.py --targets 00_DEFINIR/target_dates.csv --window 5
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import requests

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ENGINE_VERSION, assert_in_sandbox, git_commit, utcnow_iso,
                    write_raw_noreplace)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW_DIR = ROOT / "raw" / "bcra" / "a3500"
API = "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones"
COLLECTOR_VERSION = "bcra_a3500@v1.0.0"
TIMEOUT = 30


def fetch_day(source_date: date) -> tuple[str, int, dict]:
    """Retorna (source_url, http_status, payload_json). No escribe nada."""
    url = f"{API}?fecha={source_date.isoformat()}"
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "catalaxia-fx-engine/1.0"})
    r.raise_for_status()
    return url, r.status_code, r.json()


def usd_value(payload: dict) -> float | None:
    try:
        for row in payload.get("results", {}).get("detalle", []):
            if row.get("codigoMoneda") == "USD":
                v = float(row.get("tipoCotizacion"))
                return v if v > 0 else None
    except (TypeError, ValueError, AttributeError):
        return None
    return None


def store_day(source_date: date, url: str, http_status: int, payload: dict,
              retrieved_at: str) -> dict:
    import hashlib
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sha = hashlib.sha256(canonical).hexdigest()
    envelope = {"meta": {"source": "BCRA-estadisticas-cambiarias-v1.0",
                         "fx_type": "A3500",
                         "source_url": url,
                         "retrieved_at": retrieved_at,
                         "source_date": source_date.isoformat(),
                         "sha256": sha,
                         "http_status": http_status,
                         "collector": COLLECTOR_VERSION,
                         "engine": ENGINE_VERSION,
                         "git_commit": git_commit()},
                "payload": payload,
                "parsed_hint": {"usd_tipoCotizacion": usd_value(payload)}}
    out = RAW_DIR / f"{source_date.isoformat()}.json"
    res = write_raw_noreplace(out, json.dumps(envelope, ensure_ascii=False, indent=1).encode("utf-8"))
    res.update({"source_date": source_date.isoformat(), "usd": usd_value(payload)})
    return res


def collect_range(a: date, b: date, sleep_s: float = 0.3) -> list[dict]:
    import time
    results = []
    d = a
    retrieved = utcnow_iso()
    while d <= b:
        url, st, payload = fetch_day(d)
        results.append(store_day(d, url, st, payload, retrieved))
        d += timedelta(days=1)
        time.sleep(sleep_s)
    return results


def collect_targets(targets_csv: Path, window: int = 5) -> list[dict]:
    """Descarga cada target y su ventana previa (target-window .. target)."""
    import csv
    results = []
    with open(targets_csv, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(l for l in f if not l.lstrip().startswith("#") and l.strip())]
    days: set[date] = set()
    for r in rows:
        t = date.fromisoformat(r["target_date"])
        for k in range(window + 1):
            days.add(t - timedelta(days=k))
    retrieved = utcnow_iso()
    import time
    for d in sorted(days):
        try:
            url, st, payload = fetch_day(d)
            results.append(store_day(d, url, st, payload, retrieved))
        except Exception as e:  # sin imputación: se registra el fallo, no se inventa
            results.append({"action": "FETCH_ERROR", "source_date": d.isoformat(),
                            "error": f"{type(e).__name__}: {e}"})
        time.sleep(0.2)
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_", default=None)
    ap.add_argument("--to", default=None)
    ap.add_argument("--targets", default=None)
    ap.add_argument("--window", type=int, default=5)
    a = ap.parse_args()
    assert_in_sandbox(RAW_DIR)
    if a.targets:
        res = collect_targets(Path(a.targets), a.window)
    elif a.from_ and a.to:
        res = collect_range(date.fromisoformat(a.from_), date.fromisoformat(a.to))
    else:
        raise SystemExit("usar --targets CSV o --from/--to YYYY-MM-DD")
    ok = sum(1 for r in res if r.get("action") in ("CREATED", "EXISTS_IDENTICAL"))
    print(f"[{COLLECTOR_VERSION}] dias={len(res)} ok={ok} "
          + str({k: sum(1 for r in res if r.get('action') == k) for k in set(r.get('action') for r in res)}))


if __name__ == "__main__":
    main()
