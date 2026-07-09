# -*- coding: utf-8 -*-
"""
FASE 3 · JOBS DE ACTUALIZACIÓN PERIÓDICA
==========================================
Modos:
  --daily     : yfinance precios/máx-mín 52s/market_cap para las 571 (idempotente, <5 min)
  --monthly   : bajar IPC INDEC (145.3 variación activa) y reconstruir índice → sobreescribe CSV
  --quarterly : EDGAR incremental: detecta CIKs con lastFiled nuevo → re-descarga companyfacts
                → recalcula ratios. CNV incremental: re-discovery del subset (72 cuits) via
                job2→job3→job4→job5_v2 con resume-safe. Después: rebuild (s0→…→s8→s5).
  --annual    : sec_adr_ratios contra el 20-F nuevo

Uso:
  python run_update.py --daily
  python run_update.py --quarterly
  python run_update.py --daily --quiet    # solo log, sin print

Logging: data/logs/upd_YYYYMMDD.log
"""
from __future__ import annotations
import sys, time, os, csv, re, json, sqlite3, traceback, html as ihtml
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import OrderedDict

import yfinance as yf
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
LOG_DIR = ROOT / "data" / "logs"
IPC_CSV = ROOT / "data" / "ipc_nacional.csv"
SEC_H = {"User-Agent": "catalaxia-research fmonfasani@gmail.com"}
CNV_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
         "Accept-Language": "es-AR"}
# Solo estos forms cambian los estados financieros
FORM_TYPES_FUNDAMENTAL = frozenset({"10-K", "10-Q", "20-F", "10-K/A", "10-Q/A", "20-F/A"})

# ADR: CUIT -> yfinance ticker (from s3_precios)
ADR_YF = {
    "30500001735": "GGAL", "30500003193": "BBAR", "30500010084": "BMA",
    "30500530851": "LOMA", "30509300700": "CRESY", "30525322749": "IRS",
    "30526552659": "PAM", "30546689979": "YPF", "30639453738": "TEO",
    "30657862068": "TGS", "30617442937": "SUPV", "33500005179": "SUPV",
    "33515950899": "VIST", "33650305499": "CEPU", "30704962807": "GGAL",
    "30696170580": "CAAP", "30714128309": "YPFD",
}



# ── Logging ──
class Logger:
    def __init__(self, quiet=False):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logfile = LOG_DIR / f"upd_{self.ts}.log"
        self.quiet = quiet
        self._fh = open(self.logfile, "w", encoding="utf-8")

    def log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self._fh.write(line + "\n")
        self._fh.flush()
        if not self.quiet:
            print(line)

    def close(self):
        self._fh.close()
        return self.logfile


# ── ── ── ── ── ──
#  --daily
# ── ── ── ── ── ──

def _yf_fetch_one(cuit, ticker, grupo):
    """Fetch yfinance data for one ticker. Returns (cuit, ticker, data_dict) or (cuit, ticker, None, err_msg)."""
    try:
        if grupo == "sp500":
            yf_tk = ticker
        elif grupo == "adr":
            yf_tk = ADR_YF.get(cuit)
            if yf_tk is None:
                return (cuit, ticker, None, "no_adr_mapping")
        else:
            yf_tk = f"{ticker}.BA"

        fi = yf.Ticker(yf_tk).fast_info
        if fi is None or fi.market_cap is None:
            return (cuit, ticker, None, f"no_data yf={yf_tk}")

        return (cuit, ticker, {
            "precio": fi.last_price,
            "mcap": fi.market_cap,
            "yhigh": fi.year_high,
            "ylow": fi.year_low,
            "cur": fi.currency,
        }, None)
    except Exception as e:
        return (cuit, ticker, None, str(e))


def upd_precios(log):
    """yfinance: refresh precios + 52w + market_cap for all 571 tickers.
    Usa ThreadPoolExecutor para paralelizar descargas."""
    con = sqlite3.connect(DB)
    cur = con.cursor()
    fecha_iso = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cur.execute("SELECT cuit, ticker, grupo FROM screener ORDER BY ticker")
    rows = cur.fetchall()
    log.log(f"upd_precios: {len(rows)} companies")

    # Filter to only those not already updated today
    pending = []
    for cuit, ticker, grupo in rows:
        if grupo == "sp500":
            cur.execute("SELECT fecha FROM precios WHERE ticker=? ORDER BY fecha DESC LIMIT 1", (ticker,))
            last = cur.fetchone()
            if last and last[0].startswith(today):
                continue  # skip S&P already updated today
        pending.append((cuit, ticker, grupo))

    log.log(f"upd_precios: {len(pending)} to update (remaining {len(rows) - len(pending)} skipped)")

    # Collect results from parallel workers, write in main thread
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_yf_fetch_one, cuit, ticker, grupo)
                   for cuit, ticker, grupo in pending]
        for fut in as_completed(futures):
            results.append(fut.result())

    # Write all results
    ok = 0
    errors = 0
    for cuit, ticker, data, err in results:
        if data is None:
            log.log(f"  [ERR] {ticker:20s} {err}")
            errors += 1
            continue
        cur.execute("""
            INSERT OR REPLACE INTO precios (cik, ticker, precio, market_cap, year_high, year_low, currency, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cuit, ticker, data["precio"], data["mcap"],
              data["yhigh"], data["ylow"], data["cur"], fecha_iso))
        ok += 1

    con.commit()
    con.close()
    log.log(f"upd_precios: {ok} OK, {errors} errors")
    return ok, errors


# ── ── ── ── ── ──
#  --monthly
# ── ── ── ── ── ──

# IPC Nacional Nivel General base dic-2016=100 — serie ACTIVA de variación mensual
IPC_SERIES_VAR = "145.3_INGNACUAL_DICI_M_38"

def upd_ipc(log):
    """Download IPC variation from datos.gob.ar, reconstruct index level, overwrite CSV."""
    import io
    url = f"https://apis.datos.gob.ar/series/api/series/?ids={IPC_SERIES_VAR}&format=csv&limit=5000"
    log.log(f"upd_ipc: fetching {url}")
    try:
        resp = requests.get(url, headers=SEC_H, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        log.log(f"upd_ipc: FAILED to fetch IPC variation: {e}")
        return 0

    rows = [x for x in csv.reader(io.StringIO(resp.text))][1:]
    raw = [(x[0][:7], float(x[1])) for x in rows if x and x[0] and x[1]]
    if not raw:
        log.log("upd_ipc: no data parsed from CSV response")
        return 0

    # Reconstruct index level from base 2016-12 = 100
    idx = 100.0
    serie = [("2016-12", 100.0)]
    for fecha, var in raw:
        idx *= (1 + var)
        serie.append((fecha, idx))

    ult = serie[-1][1]
    fieldnames = ["fecha", "ipc_indice", "coef_deflacion_a_ultimo"]
    with open(IPC_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fieldnames)
        for fecha, i in serie:
            w.writerow([fecha, f"{i:.4f}", f"{ult / i:.6f}"])

    log.log(f"upd_ipc: {len(serie)} months, {serie[0][0]}..{serie[-1][0]}, last index {ult:.0f}")
    return len(serie)


# ── ── ── ── ── ──
#  --quarterly
# ── ── ── ── ── ──

# EDGAR tickers for which we track CIK (sp500 + adr from ratios table)
def get_edgar_ciks(cur):
    """Return set of CIKs in the ratios table (S&P + ADR)."""
    cur.execute("SELECT DISTINCT cik FROM ratios")
    return {r[0] for r in cur.fetchall()}


def get_last_filed_sec(cik):
    """Query SEC submissions endpoint for most recent filing date of a CIK.
    Filtra SOLO forms que cambian los estados financieros: 10-K, 10-Q, 20-F y /A.
    Devuelve (lastFiled_date, form_type) o (None, None)."""
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    try:
        resp = requests.get(url, headers=SEC_H, timeout=15)
        if resp.status_code != 200:
            return (None, None)
        data = resp.json()
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        best_date, best_form = None, None
        for form, d in zip(forms, dates):
            if form in FORM_TYPES_FUNDAMENTAL:
                if best_date is None or d > best_date:
                    best_date, best_form = d, form
        return (best_date, best_form)
    except Exception:
        return (None, None)


def upd_edgar_detect(cur, log):
    """Check CIKs vs their own fecha_facts. Para cada CIK donde SEC lastFiled >
    su fecha_facts: re-bajar companyfacts. Sin hueco porque cada CIK se compara
    contra cuándo se bajó realmente."""
    ciks = get_edgar_ciks(cur)
    log.log(f"upd_edgar: checking {len(ciks)} CIKs for new filings")

    # Load per-CIK fecha_facts
    ff_map = {}
    for row in cur.execute("SELECT cik, fecha_facts FROM empresas WHERE cik IN (SELECT DISTINCT cik FROM ratios)"):
        ff_map[row[0]] = row[1][:10] if row[1] else None

    cik_list = sorted(ciks)

    def _check_one(cik):
        last_filed, form = get_last_filed_sec(cik)
        baseline = ff_map.get(cik)
        is_new = bool(last_filed and (baseline is None or last_filed > baseline))
        return (cik, last_filed, form, is_new)

    new_ciks = []
    checked = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_check_one, cik) for cik in cik_list]
        for i, fut in enumerate(as_completed(futures)):
            cik, last_filed, form, is_new = fut.result()
            checked += 1
            if is_new:
                new_ciks.append(cik)
                baseline = ff_map.get(cik, "N/A")
                log.log(f"  [NEW] CIK={cik} form={form} lastFiled={last_filed} fecha_facts={baseline}")
            if (i + 1) % 10 == 0:
                time.sleep(1)  # SEC rate limit: 10 req/s

    log.log(f"upd_edgar: checked {checked} CIKs, {len(new_ciks)} have new filings")
    return new_ciks


def re_download_edgar(con, new_ciks, log):
    """Re-download companyfacts for specific CIKs and update facts table."""
    sec_dir = Path(__file__).resolve().parent.parent / "sec_edgar" / "scripts"
    sys.path.insert(0, str(sec_dir))
    from construir_base import descargar_empresa

    cur = con.cursor()
    meta = {}
    for cik in new_ciks:
        row = cur.execute("SELECT ticker_ppal, nombre FROM empresas WHERE cik=?", (cik,)).fetchone()
        meta[cik] = (row[0] or cik, row[1]) if row else (cik, None)

    raw_dir = ROOT / "data" / "raw"
    ok = 0
    for cik in new_ciks:
        # delete stale cache to force re-download
        for f in [raw_dir / "companyfacts" / f"CIK{cik}.json",
                  raw_dir / "submissions" / f"CIK{cik}.json"]:
            if f.exists():
                f.unlink()
        ticker, nombre = meta[cik]
        res = descargar_empresa(con, ticker, cik, nombre)
        if res:
            ok += 1
            log.log(f"  [RE-DL] CIK={cik} {ticker} -> {res[0]}")
        time.sleep(0.12)
    log.log(f"re_download_edgar: {ok}/{len(new_ciks)} CIKs re-downloaded")
    return ok


def recompute_edgar_ratios(log):
    """Recompute the ratios table from facts (EDGAR-only, no price)."""
    sec_dir = Path(__file__).resolve().parent.parent / "sec_edgar" / "scripts"
    sys.path.insert(0, str(sec_dir))
    try:
        import calcular_ratios_base
        calcular_ratios_base.main()
        log.log("recompute_ratios: OK")
        return True
    except Exception as e:
        log.log(f"recompute_ratios: FAILED: {e}")
        return False


RX_CNV_TR = re.compile(
    r'<tr>.*?<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>.*?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
    re.I | re.S
)
RX_CIERRE_BAL = re.compile(r"FECH\.\s*CIERRE\s+BAL\.?\s*:\s*(\d{2}-\d{2}-\d{4})", re.I)


def cnv_discovery_subset(log):
    """Run CNV discovery pipeline scoped to the 72-cuit subset.
    job2 (re-download pages to detect new filings) → parse company HTMLs
    to identify codigo GUIDs (with period_end in descripcion) → diff against
    cnv_estados_v2 → extract SOLO los nuevos codigos (no anexos)."""
    cnv_dir = Path(__file__).resolve().parent.parent / "cnv" / "jobs"
    cwd = str(cnv_dir)
    cnv_datos = cnv_dir.parent / "datos"
    subset = cnv_datos / "empresas_subset.csv"
    html_dir = cnv_datos / "html_descargados"
    import subprocess, re

    # ── 0. Load subset CUITs ──
    subset_cuits = {r["cuit"].strip() for r in csv.DictReader(open(subset, encoding="utf-8-sig")) if r.get("cuit")}

    # Quick connectivity check — CNV may be rate-limiting us
    cnv_reachable = False
    try:
        r = requests.get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30546689979",
                         headers=CNV_H, timeout=10)
        cnv_reachable = (r.status_code == 200 and len(r.text) > 5000)
    except Exception:
        pass

    if cnv_reachable:
        log.log("cnv: job2 download subset pages...")
        r = subprocess.run(["python", "job2_download.py", "--empresas", str(subset),
                            "--sleep", "0.5", "--max", "80"],
                           capture_output=True, text=True, cwd=cwd, timeout=120)
        for line in r.stdout.strip().splitlines():
            log.log(f"  job2> {line}")
    else:
        log.log("cnv: CNV unreachable, using cached pages (if any)")

    # job3+job4: re-run if any pages exist (even partial cache)
    if list(html_dir.glob("*.html")):
        log.log("cnv: job3+job4 re-parse...")
        r = subprocess.run(["python", "job3_formtype.py"], capture_output=True, text=True, cwd=cwd, timeout=300)
        for line in r.stdout.strip().splitlines():
            log.log(f"  job3> {line}")
        r = subprocess.run(["python", "job4_clasificar.py"], capture_output=True, text=True, cwd=cwd, timeout=60)
        for line in r.stdout.strip().splitlines():
            log.log(f"  job4> {line}")
    else:
        log.log("cnv: no cached company pages, skipping job3+job4")

    # ── 3. Parse company HTMLs directly to identify codigo GUIDs ──
    # A codigo has "FECH. CIERRE BAL.: dd-mm-yyyy" in its table description
    codigo_guids = {}  # guid -> (cuit, empresa, url, descripcion)
    for f in sorted(html_dir.glob("*.html")):
        m = re.match(r"(\d{11})_(.+)\.html$", f.name)
        if not m:
            continue
        cuit, nombre_raw = m.group(1), m.group(2).replace("_", " ")
        if cuit not in subset_cuits:
            continue
        html = f.read_text(encoding="utf-8", errors="ignore")
        for tr_m in RX_CNV_TR.finditer(html):
            guid = tr_m.group(5).lower()
            desc = ihtml.unescape(re.sub(r"<[^>]+>", " ", tr_m.group(3))).strip()
            if RX_CIERRE_BAL.search(desc):
                url = f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}"
                codigo_guids[guid] = (cuit, nombre_raw, url, desc)
    log.log(f"cnv: detected {len(codigo_guids)} codigo GUIDs from {len(list(html_dir.glob('*.html')))} cached pages")

    # ── 4. Download missing company pages for companies with no cached HTML ──
    companies_with_html = set()
    for f in html_dir.glob("*.html"):
        m = re.match(r"(\d{11})_", f.stem)
        if m:
            companies_with_html.add(m.group(1))
    missing = subset_cuits - companies_with_html
    if missing:
        log.log(f"cnv: {len(missing)} companies have no cached page (CNV unreachable), "
                f"skipping re-discovery for them this run")

    # ── 5. Diff against cnv_estados_v2 ──
    con2 = sqlite3.connect(DB)
    cur2 = con2.cursor()
    cur2.execute("SELECT DISTINCT accn FROM cnv_estados_v2 WHERE fuente='cnv-aif2' AND accn != ''")
    done_guids = {r[0] for r in cur2.fetchall()}
    con2.close()

    new_rows = []
    for guid, (cuit, empresa, url, _desc) in codigo_guids.items():
        if cuit in subset_cuits and guid not in done_guids:
            new_rows.append({"cuit": cuit, "empresa": empresa, "guid": guid,
                             "formulario": "Estados Contables", "clase": "eeff", "url": url})

    # ── 6. Factor out old anexos already marked done for cleanup ──
    tmp_new = cnv_datos / "whitelist_nuevos.csv"

    # Read whitelist to find NON-codigo GUIDs for subset (anexos) and bulk-mark them done
    whitelist_path = cnv_datos / "whitelist_eeff.csv"
    anexo_guids = []
    with open(whitelist_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cu = row["cuit"].strip()
            g = row["guid"].strip()
            if cu in subset_cuits and g not in codigo_guids and g not in done_guids:
                anexo_guids.append(g)

    if anexo_guids:
        done_file = ROOT / "data" / "log_job5_v2_done.txt"
        existing = set(done_file.read_text(encoding="utf-8").split()) if done_file.exists() else set()
        new_done = [g for g in anexo_guids if g not in existing]
        if new_done:
            with open(done_file, "a", encoding="utf-8") as f:
                for g in new_done:
                    f.write(g + "\n")
            log.log(f"cnv: bulk-marked {len(new_done)} anexo GUIDs as done (no period_end in descripcion)")

    # ── 7. Extract only new codigo GUIDs (skip if CNV unreachable) ──
    if new_rows:
        log.log(f"cnv: {len(new_rows)} new codigo GUIDs (subset={len(subset_cuits)} companies)")
        if cnv_reachable:
            with open(tmp_new, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=["cuit", "empresa", "guid", "formulario", "clase", "url"])
                w.writeheader(); w.writerows(new_rows)
            log.log("cnv: job5_v2 extract nuevos...")
            r = subprocess.run(["python", "job5_v2_extract_eeff.py", "--whitelist", str(tmp_new),
                                "--cuits", str(subset), "--max", "500"],
                               capture_output=True, text=True, cwd=cwd, timeout=300)
            for line in r.stdout.strip().splitlines():
                log.log(f"  job5> {line}")
            tmp_new.unlink(missing_ok=True)
        else:
            log.log("cnv: CNV down, extraccion diferida al proximo run")
    else:
        log.log("cnv: no new codigo GUIDs to extract (all subset codigos already in cnv_estados_v2)")

    log.log("cnv: subset discovery complete")


def rebuild_screener(log):
    """Re-run s0→s2→s3→s4→s6→s7→s8→s5 (the full pipeline)."""
    phases = [
        ("s0_normalizar_cnv", "build", "Normalizacion CNV"),
        ("s2_ratios_cnv", "build", "Ratios CNV"),
        ("s3_precios", "main", "Precios yfinance"),
        ("s4_ensamblar", "build", "Ensamblar screener"),
        ("s6_ajustes", "main", "Ajustes (ADR/bancos/sector)"),
        ("s7_unificar", "build", "Unificar S&P desde EDGAR"),
        ("s8_calidad", "build", "Calidad (payout/EV/OpMargen)"),
        ("s5_exportar", "build", "Validacion + Export"),
    ]
    results = []
    ok = True
    for mod_name, entry, label in phases:
        start = time.perf_counter()
        log.log(f"rebuild: INICIANDO {label}")
        try:
            __import__(mod_name)
            mod = sys.modules[mod_name]
            getattr(mod, entry)()
            status = "OK"
        except Exception:
            log.log(f"rebuild: ERROR en {label}: {traceback.format_exc()}")
            status = "FAILED"
            ok = False
        elapsed = time.perf_counter() - start
        log.log(f"rebuild: {label} -- {status} ({elapsed:.1f}s)")
        results.append((label, status, elapsed))
        time.sleep(1.5)
    return results


def upd_quarterly(log):
    """EDGAR incremental (detect → re-download → recompute) + CNV subset discovery + rebuild."""
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # ── 1. EDGAR incremental ──
    new_ciks = upd_edgar_detect(cur, log)
    if new_ciks:
        log.log(f"  -> re-downloading {len(new_ciks)} CIKs with new filings")
        n_dl = re_download_edgar(con, new_ciks, log)
        log.log(f"  -> re-downloaded {n_dl}/{len(new_ciks)}")
    else:
        log.log("  -> No new EDGAR filings detected")

    # ── 2. Recompute EDGAR ratios (if any CIK was re-downloaded) ──
    if new_ciks:
        recompute_edgar_ratios(log)
    else:
        log.log("  -> Skipping EDGAR ratio recompute (no changes)")

    con.close()

    # ── 3. CNV incremental (subset-scoped discovery + extraction) ──
    cnv_discovery_subset(log)

    # ── 4. Rebuild screener (s0→s8→s5) ──
    log.log("rebuild: Rebuilding screener...")
    results = rebuild_screener(log)
    n_ok = sum(1 for r in results if r[1] == "OK")
    log.log(f"rebuild: {n_ok}/{len(results)} phases OK")
    return results


# ── ── ── ── ── ──
#  --annual
# ── ── ── ── ── ──

def upd_adr_ratios(log):
    """Refresh ADR ratios from SEC 20-F / F-6 filings."""
    log.log("upd_adr_ratios: refreshing ADR ratios from SEC")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sec_edgar" / "scripts"))
        import sec_adr_ratios
        sec_adr_ratios.main()
        log.log("upd_adr_ratios: OK")
        return True
    except Exception as e:
        log.log(f"upd_adr_ratios: FAILED: {e}")
        log.log(traceback.format_exc())
        return False


# ── ── ── ── ── ──
#  CLI
# ── ── ── ── ── ──

def main():
    parser = argparse.ArgumentParser(description="Screener update jobs")
    parser.add_argument("--daily", action="store_true", help="Update prices from yfinance")
    parser.add_argument("--monthly", action="store_true", help="Update IPC INDEC data")
    parser.add_argument("--quarterly", action="store_true", help="EDGAR + CNV incremental + rebuild")
    parser.add_argument("--annual", action="store_true", help="Refresh ADR ratios from SEC 20-F")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild screener (s0→s5)")
    parser.add_argument("--quiet", action="store_true", help="Minimal output (log only)")
    args = parser.parse_args()

    log = Logger(quiet=args.quiet)
    log.log("=" * 60)
    log.log(f"SCREENER UPDATE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.log("=" * 60)

    mode_count = sum([bool(args.daily), bool(args.monthly), bool(args.quarterly),
                      bool(args.annual), bool(args.rebuild)])
    if mode_count == 0:
        log.log("No mode specified. Use --daily, --monthly, --quarterly, --annual, or --rebuild")
        log.close()
        print(f"\nLog: {log.logfile}")
        return

    # Track overall timing
    start_all = time.perf_counter()
    errors = 0

    if args.daily:
        log.log("\n--- MODE: daily ---")
        try:
            ok, err = upd_precios(log)
            log.log(f"--daily: {ok} updated, {err} errors")
            errors += err
        except Exception:
            log.log(f"--daily FAILED: {traceback.format_exc()}")
            errors += 1

    if args.monthly:
        log.log("\n--- MODE: monthly ---")
        try:
            n = upd_ipc(log)
            log.log(f"--monthly: {n} new months")
        except Exception:
            log.log(f"--monthly FAILED: {traceback.format_exc()}")
            errors += 1

    if args.quarterly:
        log.log("\n--- MODE: quarterly ---")
        try:
            results = upd_quarterly(log)
            n_ok = sum(1 for r in results if r[1] == "OK")
            n_fail = len(results) - n_ok
            log.log(f"--quarterly: {n_ok}/{len(results)} phases OK, {n_fail} failed")
            errors += n_fail
        except Exception:
            log.log(f"--quarterly FAILED: {traceback.format_exc()}")
            errors += 1

    if args.annual:
        log.log("\n--- MODE: annual ---")
        try:
            ok = upd_adr_ratios(log)
            if not ok:
                errors += 1
        except Exception:
            log.log(f"--annual FAILED: {traceback.format_exc()}")
            errors += 1

    if args.rebuild:
        log.log("\n--- MODE: rebuild ---")
        try:
            results = rebuild_screener(log)
            n_ok = sum(1 for r in results if r[1] == "OK")
            n_fail = len(results) - n_ok
            log.log(f"--rebuild: {n_ok}/{len(results)} phases OK, {n_fail} failed")
            errors += n_fail
        except Exception:
            log.log(f"--rebuild FAILED: {traceback.format_exc()}")
            errors += 1

    elapsed = time.perf_counter() - start_all
    log.log(f"\n{'='*60}")
    log.log(f"UPDATE COMPLETE — {elapsed:.1f}s, {errors} errors")
    log.log(f"{'='*60}")
    logfile = log.close()

    print(f"\nLog: {logfile}")
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
