# -*- coding: utf-8 -*-
"""
Screener Pipeline Orchestrator
==============================
Ejecuta las 6 fases (FASE 0..5) secuencialmente con gates de validacion
entre cada una. Cada fase se importa como modulo y se llama a su entry point.

Uso: python run_screener.py
"""
from __future__ import annotations
import time, sys, traceback
from datetime import datetime


def run_phase(label: str, mod_name: str, entry: str) -> dict:
    start = time.perf_counter()
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"[{ts}] INICIANDO {label}")
    print(f"{'='*60}")
    try:
        __import__(mod_name)
        mod = sys.modules[mod_name]
        getattr(mod, entry)()
        status = "OK"
    except Exception:
        print(f"\n  ERROR en {label}:")
        traceback.print_exc()
        status = "FAILED"
    elapsed = time.perf_counter() - start
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {label} -- {status} ({elapsed:.1f}s)")
    return {"phase": label, "status": status, "duration": elapsed}


def main():
    start_all = time.perf_counter()
    print("=" * 60)
    print("  SCREENER PIPELINE")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    phases = [
        ("FASE 0 — Normalizacion CNV",   "s0_normalizar_cnv", "build"),
        ("FASE 2 — Ratios CNV",           "s2_ratios_cnv",     "build"),
        ("FASE 3 — Precios yfinance",     "s3_precios",        "main"),
        ("FASE 4 — Ensamblar screener",   "s4_ensamblar",      "build"),
        ("FASE 5 — Validacion + Export",  "s5_exportar",       "build"),
    ]

    results = [run_phase(*p) for p in phases]

    total_elapsed = time.perf_counter() - start_all
    n_ok = sum(1 for r in results if r["status"] == "OK")
    n_fail = sum(1 for r in results if r["status"] == "FAILED")

    print(f"\n{'='*60}")
    print("  RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"  {'Phase':<30s} {'Status':<10s} {'Duration':>8s}")
    print(f"  {'-'*30} {'-'*10} {'-'*8}")
    for r in results:
        print(f"  {r['phase']:<30s} {r['status']:<10s} {r['duration']:>7.1f}s")
    print(f"  {'-'*30} {'-'*10} {'-'*8}")
    print(f"  {'TOTAL':<30s} {f'{n_ok}/{n_ok+n_fail} phases':<10s} {total_elapsed:>7.1f}s")
    print(f"\n  Inicio: {start_all:.0f}")
    print(f"  Fin:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
