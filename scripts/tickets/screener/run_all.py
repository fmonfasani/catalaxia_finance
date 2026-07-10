# -*- coding: utf-8 -*-
"""
FASE 4 · RECONSTRUCCION END-TO-END (from scratch, idempotente)
==============================================================
Orquesta TODO el pipeline en el orden canonico:

    EXTRACT  -> TRANSFORM -> ASSEMBLE -> EXPORT

  EXTRACT   (red, lento):
    - EDGAR : construir_base (companyfacts; SALTEA los CIK ya cacheados via fecha_facts)
    - CNV   : job1..job7 discovery+extract (guardado por conectividad; skip si CNV caido)
    - ADR   : sec_adr_ratios (ratio ADR oficial del 20-F/F-6)
  TRANSFORM :
    - calcular_ratios_base   (ratios EDGAR desde facts; DROPEA y recrea `ratios`)
    - precios_y_valuacion    (precios yfinance + per/p_book/p_sales/ev_ebitda)
      *** SIEMPRE van juntos: calcular_ratios_base BORRA la columna `per`, que
          precios_y_valuacion vuelve a crear. Correr uno sin el otro rompe s6/s7. ***
  ASSEMBLE  : s0 -> s2 -> s3 -> s4 -> s6 -> s7 -> s8
  EXPORT    : s5 -> data/screener_export.csv

Idempotente: cada stage reconstruye su salida; los pasos caros (EDGAR/CNV download)
saltean lo ya cacheado. Correrlo en una maquina limpia (con requirements.txt y la DB
o el raw cache) reconstruye la base entera.

Uso:
  python run_all.py                     # todo (extract con cache -> transform -> assemble -> export)
  python run_all.py --skip-extract      # reusa raw cacheado (facts+cnv ya en DB)
  python run_all.py --skip-transform    # NO recalcula ratios (mantiene tabla `ratios`)
  python run_all.py --offline           # sin red: implica skip-extract; transform solo si hay red
  python run_all.py --only assemble     # corre un solo stage (extract|transform|assemble|export)
  python run_all.py --with-cnv-fresh    # ademas corre discovery CNV completo (job1..job7)

Logging: data/logs/runall_YYYYMMDD_HHMMSS.log
"""
from __future__ import annotations
import sys, time, argparse, sqlite3, subprocess, traceback
from pathlib import Path
from datetime import datetime

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
LOG_DIR = ROOT / "data" / "logs"
SCREENER_DIR = Path(__file__).resolve().parent
SEC_DIR = SCREENER_DIR.parent / "sec_edgar" / "scripts"
CNV_JOBS = SCREENER_DIR.parent / "cnv" / "jobs"

for p in (str(SCREENER_DIR), str(SEC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


class Logger:
    def __init__(self, quiet=False):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logfile = LOG_DIR / f"runall_{ts}.log"
        self.quiet = quiet
        self._fh = open(self.logfile, "w", encoding="utf-8")

    def log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self._fh.write(line + "\n"); self._fh.flush()
        if not self.quiet:
            print(line)

    def close(self):
        self._fh.close(); return self.logfile


def _run_module(mod_name, entry, log, argv=None):
    """Importa un modulo del pipeline y llama a su entry point. Devuelve (status, elapsed)."""
    start = time.perf_counter()
    log.log(f"  -> {mod_name}.{entry}()" + (f"  argv={argv}" if argv else ""))
    old_argv = sys.argv
    try:
        if argv is not None:
            sys.argv = [mod_name] + argv
        __import__(mod_name)
        mod = sys.modules[mod_name]
        getattr(mod, entry)()
        status = "OK"
    except Exception:
        log.log(f"     ERROR en {mod_name}:\n{traceback.format_exc()}")
        status = "FAILED"
    finally:
        sys.argv = old_argv
    elapsed = time.perf_counter() - start
    log.log(f"     {mod_name} -- {status} ({elapsed:.1f}s)")
    return status, elapsed


def _cnv_reachable():
    try:
        import requests
        r = requests.get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30546689979",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return r.status_code == 200 and len(r.text) > 5000
    except Exception:
        return False


# ────────────────────────────────────────────────────────────
#  STAGES
# ────────────────────────────────────────────────────────────

def stage_extract(log, results, offline, with_cnv_fresh):
    log.log("\n=== STAGE 1/4: EXTRACT ===")
    if offline:
        log.log("  offline: se saltea la descarga (se usa raw/DB cacheado)")
        return

    # EDGAR: companyfacts (construir_base saltea los CIK con fecha_facts != NULL)
    for modo in ("us", "adr"):
        st, el = _run_module("construir_base", "main", log, argv=[modo])
        results.append((f"extract:edgar-{modo}", st, el))

    # ADR ratios (20-F/F-6) — barato
    st, el = _run_module("sec_adr_ratios", "main", log)
    results.append(("extract:adr_ratios", st, el))

    # CNV: discovery completo solo bajo pedido (frágil + lento). Guardado por conectividad.
    if with_cnv_fresh:
        if _cnv_reachable():
            log.log("  CNV alcanzable: discovery completo (job1..job7)")
            for job in ("job1_universo.py", "job2_download.py", "job3_formtype.py",
                        "job4_clasificar.py", "job5_v2_extract_eeff.py",
                        "job6_v2_reparse_div.py", "job7_validar.py"):
                start = time.perf_counter()
                log.log(f"  -> cnv/{job}")
                try:
                    r = subprocess.run(["python", job], cwd=str(CNV_JOBS),
                                       capture_output=True, text=True, timeout=1800)
                    st = "OK" if r.returncode == 0 else "FAILED"
                    for line in r.stdout.strip().splitlines()[-5:]:
                        log.log(f"     {job}> {line}")
                except Exception as e:
                    st = "FAILED"; log.log(f"     {job} ERROR: {e}")
                results.append((f"extract:cnv-{job}", st, time.perf_counter() - start))
        else:
            log.log("  CNV inalcanzable: se saltea discovery (se usa cnv_estados_v2 cacheado)")
            results.append(("extract:cnv", "SKIP", 0.0))
    else:
        log.log("  CNV: reusando cnv_estados_v2 cacheado (usar --with-cnv-fresh para re-discovery)")


def stage_transform(log, results, offline):
    log.log("\n=== STAGE 2/4: TRANSFORM ===")
    # calcular_ratios_base DROPEA la tabla `ratios` (sin per). precios_y_valuacion la
    # completa con precios + per/p_book/p_sales/ev_ebitda. Van SIEMPRE juntos.
    st1, el1 = _run_module("calcular_ratios_base", "main", log)
    results.append(("transform:ratios_base", st1, el1))
    st2, el2 = _run_module("precios_y_valuacion", "main", log)
    results.append(("transform:precios_valuacion", st2, el2))
    if st1 == "OK" and st2 != "OK":
        log.log("  *** ATENCION: calcular_ratios_base corrio pero precios_y_valuacion NO. "
                "La columna `per` puede faltar en `ratios`. Re-corré transform con red. ***")


def stage_assemble(log, results):
    log.log("\n=== STAGE 3/4: ASSEMBLE ===")
    phases = [
        ("s0_normalizar_cnv", "build", "Normalizacion CNV"),
        ("s2_ratios_cnv",     "build", "Ratios CNV (IPC)"),
        ("s3_precios",        "main",  "Precios yfinance"),
        ("s4_ensamblar",      "build", "Ensamblar screener (AR)"),
        ("s6_ajustes",        "main",  "Ajustes (ADR/bancos/sector)"),
        ("s7_unificar",       "build", "Unificar S&P desde EDGAR"),
        ("s8_calidad",        "build", "Calidad (payout/EV/OpMargen)"),
        ("iamc_dual_price",   "build", "IAMC + Dual Price (ARS/USD)"),
    ]
    for mod, entry, label in phases:
        st, el = _run_module(mod, entry, log)
        results.append((f"assemble:{mod}", st, el))
        time.sleep(1.2)  # dar tiempo a que SQLite libere el lock entre fases


def stage_export(log, results):
    log.log("\n=== STAGE 4/4: EXPORT ===")
    st, el = _run_module("s5_exportar", "build", log)
    results.append(("export:s5", st, el))


# ────────────────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Reconstruccion end-to-end del screener")
    ap.add_argument("--skip-extract", action="store_true", help="Reusar raw cacheado (facts+cnv)")
    ap.add_argument("--skip-transform", action="store_true", help="No recalcular ratios")
    ap.add_argument("--offline", action="store_true", help="Sin red (implica skip-extract)")
    ap.add_argument("--with-cnv-fresh", action="store_true", help="Correr discovery CNV completo")
    ap.add_argument("--only", choices=["extract", "transform", "assemble", "export"],
                    help="Correr un solo stage")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.offline:
        args.skip_extract = True

    log = Logger(quiet=args.quiet)
    log.log("=" * 60)
    log.log(f"RUN_ALL — reconstruccion end-to-end — {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.log(f"  DB: {DB}  ({DB.stat().st_size/1e6:.0f} MB)" if DB.exists() else f"  DB: {DB} (NO EXISTE)")
    log.log("=" * 60)

    if not DB.exists():
        log.log("FATAL: data/screener.db no existe. En una maquina limpia hace falta el raw "
                "cache o correr el extract completo (EDGAR+CNV). Aborto.")
        log.close(); sys.exit(2)

    start_all = time.perf_counter()
    results = []

    stages = ["extract", "transform", "assemble", "export"]
    if args.only:
        stages = [args.only]

    for s in stages:
        if s == "extract":
            if args.skip_extract:
                log.log("\n=== STAGE 1/4: EXTRACT — SKIPPED (--skip-extract) ===")
            else:
                stage_extract(log, results, args.offline, args.with_cnv_fresh)
        elif s == "transform":
            if args.skip_transform:
                log.log("\n=== STAGE 2/4: TRANSFORM — SKIPPED (--skip-transform) ===")
            else:
                stage_transform(log, results, args.offline)
        elif s == "assemble":
            stage_assemble(log, results)
        elif s == "export":
            stage_export(log, results)

    total = time.perf_counter() - start_all
    n_ok = sum(1 for _, st, _ in results if st == "OK")
    n_fail = sum(1 for _, st, _ in results if st == "FAILED")
    n_skip = sum(1 for _, st, _ in results if st == "SKIP")

    log.log(f"\n{'='*60}")
    log.log("  RESUMEN")
    log.log(f"{'='*60}")
    for name, st, el in results:
        log.log(f"  {name:<34s} {st:<8s} {el:>7.1f}s")
    log.log(f"  {'-'*34} {'-'*8} {'-'*8}")
    log.log(f"  {'TOTAL':<34s} {f'{n_ok} OK / {n_fail} FAIL / {n_skip} SKIP':<18s} {total:>7.1f}s")

    # verificacion final
    try:
        con = sqlite3.connect(DB); cur = con.cursor()
        n = cur.execute("SELECT COUNT(*) FROM screener").fetchone()[0]
        by = dict(cur.execute("SELECT grupo, COUNT(*) FROM screener GROUP BY grupo").fetchall())
        con.close()
        log.log(f"  screener: {n} filas  {by}")
        if n != 572:
            log.log(f"  *** ADVERTENCIA: se esperaban 572 filas, hay {n} ***")
    except Exception as e:
        log.log(f"  no se pudo verificar screener: {e}")

    logfile = log.close()
    print(f"\nLog: {logfile}")
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
