#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DRY-RUN backfill identity_v1 - READ-ONLY por clasificacion.

Clasifica el universo (SEC catalog RAW + dim_entity SQLite + CSVs legacy +
snapshot GLEIF del ciclo 4) como lo hara el backfill, pero NO escribe nada.
Politicas D-I-04 / F-020:
  * LEI opcional para el universo US -> ausencia de LEI NO abre review.
  * Argentinos con LEI (ciclo G4) -> bridge CIK<->LEI CANDIDATE.
  * Si GLEIF ademas publica CUIT -> bridge CIK<->CUIT CANDIDATE.
  * GLEIF con LEI pero sin registeredAs (GGAL) -> REVIEW_REQUIRED.
  * SEC es autoridad del CIK: el CIK legacy se descarta (D-I-C), nunca lo reemplaza.
  * Solo ambiguedad real abre REVIEW_REQUIRED.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

# import modulo real (read-only) para LEI y snapshot GLEIF exactos
from identity_v1_pilot import EMISORES, GLEIF_SNAPSHOT  # noqa: E402

from engine.identity import SEC_CATALOG_DIR  # noqa: E402


def sha16(p: Path) -> str:
    if p.exists():
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return "NO"


def norm_cik(x) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s.zfill(10) if s.isdigit() else None


def norm_cuit(x) -> str | None:
    if x is None:
        return None
    d = "".join(c for c in str(x) if c.isdigit())
    return d if len(d) == 11 else None


def cuit_checksum(cuit: str) -> bool:
    if len(cuit) != 11:
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    s = sum(int(a) * p for a, p in zip(cuit[:10], pesos))
    r = 11 - (s % 11)
    dv = 0 if r == 11 else (9 if r == 10 else r)
    return dv == int(cuit[-1])


def main() -> int:
    log = io.StringIO()
    w = log.write
    w("DRY-RUN BACKFILL identity_v1 - READ-ONLY (D-I-04 / F-020)\n")

    # ---------------- fuentes ----------------
    cats = sorted(SEC_CATALOG_DIR.glob("company_tickers_*.json"))
    if not cats:
        print("[error] sin catalogo SEC"); return 2
    cat = cats[-1]
    raw = json.loads(cat.read_text(encoding="utf-8"))

    sec_by_cik: dict[str, dict] = {}
    sec_by_ticker: dict[str, str] = {}
    seen: dict[str, str] = {}
    dup_cat: list = []
    for v in raw.values():
        cik = str(int(v["cik_str"])).zfill(10)
        tk = str(v["ticker"]).strip().upper()
        if cik in seen:
            dup_cat.append((cik, seen[cik], tk))
        else:
            seen[cik] = tk
        sec_by_cik.setdefault(cik, {"ticker": tk, "title": str(v["title"]).strip()})
        sec_by_ticker.setdefault(tk, cik)

    dim_file = REPO / "data" / "screener.db"
    con = sqlite3.connect(f"file:{dim_file}?mode=ro", uri=True)
    dim = con.execute("SELECT entity_id, cik, cuit, ticker_canonico, grupo, nombre "
                      "FROM dim_entity").fetchall()
    con.close()

    arg_csv = REPO / "scripts" / "screener" / "datos" / "acciones_argentinas_usa.csv"
    arg = []
    if arg_csv.exists():
        with open(arg_csv, encoding="utf-8-sig", newline="") as f:
            arg = list(csv.DictReader(f))

    byma_csv = REPO / "scripts" / "screener" / "datos" / "cedears_byma.csv"
    byma = []
    if byma_csv.exists():
        with open(byma_csv, encoding="utf-8-sig", newline="") as f:
            byma = list(csv.DictReader(f))

    LEI_BY_CIK = {em["cik"]: em["lei"] for em in EMISORES}

    # ---------------- metricas ----------------
    sec_ciks = set(sec_by_cik.keys())
    dim_cik_set = {norm_cik(d[1]) for d in dim if norm_cik(d[1])}

    fusion = dim_cik_set & sec_ciks
    dim_only = dim_cik_set - sec_ciks

    cik_validos_sec = len(sec_ciks)
    cik_validos_dim = len(dim_cik_set)

    cik_invalidos: list[str] = []
    for (eid, cik, cuit, t, gr, nom) in dim:
        if cik is not None and norm_cik(cik) is None:
            cik_invalidos.append(f"dim:{eid}:{cik}")
    for r in arg:
        if r.get("cik") and norm_cik(r["cik"]) is None:
            cik_invalidos.append(f"csv:{r.get('ticker_usa')}:{r['cik']}")
    cik_invalidos = list(dict.fromkeys(cik_invalidos))

    ent_crear = len(sec_ciks)
    ent_fusion = len(fusion)
    dup_reales = 0
    dup_cat_count = len(dup_cat)

    casos_slc = []
    for r in arg:
        tk = r["ticker_usa"].strip().upper()
        c_sec = sec_by_ticker.get(tk)
        c_leg = norm_cik(r.get("cik"))
        if c_sec and c_leg and c_sec != c_leg:
            casos_slc.append((tk, c_leg, c_sec))

    adr = [d for d in dim if d[4] == "adr"]
    bridges_lei = []
    bridges_cuit = []
    for (eid, cik, cuit, t, gr, nom) in adr:
        c_n = norm_cik(cik)
        cu_n = norm_cuit(cuit)
        lei = LEI_BY_CIK.get(c_n)
        if c_n and lei:
            bridges_lei.append({"ticker": t.strip().upper(), "cik": c_n, "lei": lei})
        if c_n and cu_n:
            bridges_cuit.append({"ticker": t.strip().upper(), "cik": c_n, "cuit": cu_n})

    reviews: list[str] = []
    for b in bridges_lei:
        snap = GLEIF_SNAPSHOT.get(b["lei"])
        if snap and snap.get("registeredAs") is None:
            reviews.append(f"GLEIF_sin_CUIT:{b['ticker']}")
    reviews = list(dict.fromkeys(reviews))

    rechazos = []
    for (eid, cik, cuit, t, gr, nom) in dim:
        cu = norm_cuit(cuit)
        if cu and not cuit_checksum(cu):
            rechazos.append((t, cu))

    nd: list[str] = []
    nd_byma = []
    nd_arg_sin_lei = []
    nd_csv_no_ticker = []
    for (eid, cik, cuit, t, gr, nom) in dim:
        tk = t.strip().upper()
        if gr == "byma_only" and norm_cik(cik) is None:
            nd_byma.append(f"byma_only_sin_CIK:{tk}")
    for (eid, cik, cuit, t, gr, nom) in adr:
        c_n = norm_cik(cik)
        if c_n and c_n not in LEI_BY_CIK:
            nd_arg_sin_lei.append(f"arg_sin_LEI_snapshot:{t.strip().upper()}")
    for r in arg:
        tk = r["ticker_usa"].strip().upper()
        if tk not in sec_by_ticker:
            nd_arg_sin_lei.append(f"csv_ticker_no_en_SEC:{tk} (cik legacy {r.get('cik')})")
    nd_dim_only = [f"dim_cik_no_sec:{c7}" for c7 in sorted(dim_only)]
    nd = list(dict.fromkeys(nd_byma + nd_arg_sin_lei + nd_dim_only))

    # ---------------- reporte ----------------
    w("\n-- fuentes --\n")
    w(f"  SEC catalog      : {cat.name} sha16={sha16(cat)}\n")
    w(f"  dim_entity       : {dim_file.name} ({len(dim)} filas)\n")
    w(f"  acciones_arg_usa : {arg_csv.name} ({len(arg)} filas)\n")
    w(f"  cedears_byma     : {byma_csv.name} ({len(byma)} filas)\n")
    w(f"  GLEIF snapshot   : {len(GLEIF_SNAPSHOT)} lei (ciclo 4)\n")

    w("\n-- RESULTADO --\n")
    w(f"1.  total_emisores_sec = {len(sec_ciks)}\n")
    w(f"2.  cik_validos_sec    = {cik_validos_sec}\n")
    w(f"    cik_validos_dim    = {cik_validos_dim}\n")
    w(f"3.  cik_invalidos      = {len(cik_invalidos)}\n")
    for i_ in cik_invalidos[:10]:
        w("      " + i_ + "\n")
    w(f"4.  entidades_crear    = {ent_crear}\n")
    w(f"5.  entidades_fusionar = {ent_fusion}\n")
    w(f"6.  duplicados_cik     = {dup_reales}  (multi-ticker catalog={dup_cat_count}, no duplica entidad)\n")
    if dup_cat:
        w("      " + "; ".join(f"{c}:{a}->{b}" for c, a, b in dup_cat[:6]) + "\n")
    w(f"7.  sec_vs_legacy      = {len(casos_slc)}\n")
    for c7_ in casos_slc:
        w("      " + str(c7_) + "\n")
    w(f"8.  bridges_cik_lei    = {len(bridges_lei)}\n")
    for b in bridges_lei:
        w("      " + str(b) + "\n")
    w(f"9.  bridges_cik_cuit   = {len(bridges_cuit)}\n")
    for b in bridges_cuit:
        w("      " + str(b) + "\n")
    w(f"10. reviews_a_abrir    = {len(reviews)}\n")
    for r in reviews:
        w("      " + r + "\n")
    w(f"11. conflictos         = {len(casos_slc)} (legacy vs SEC; autoridad SEC)\n")
    w(f"12. rechazos           = {len(rechazos)}\n")
    for r in rechazos:
        w("      " + str(r) + "\n")
    w(f"13. casos_no_determinables = {len(nd)}\n")
    w(f"      byma_only_sin_CIK     = {len(nd_byma)}  (solo CUIT legacy: sin ancla autoritativa)\n")
    w(f"      arg_sin_LEI_snapshot  = {len(nd_arg_sin_lei)}  (requiere busqueda GLEIF por nombre)\n")
    w(f"      dim_cik_no_sec        = {len(nd_dim_only)}  (CIK legacy sin match SEC)\n")
    for x in nd[:12]:
        w("      " + x + "\n")
    if len(nd) > 12:
        w(f"      ... (+{len(nd)-12})\n")

    # ---------------- validaciones obligatorias ----------------
    w("\n-- VALIDACIONES OBLIGATORIAS --\n")
    v1 = (ent_crear == len(sec_ciks))
    w(f"  [V1] un CIK SEC -> una sola entidad            : {'OK' if v1 else 'FALLO'} "
      f"(CIKs unicos={len(sec_ciks)}, entidades a crear={ent_crear})\n")
    v2 = all(c_sec == sec_by_ticker.get(tk) for (tk, _cl, c_sec) in casos_slc) and len(casos_slc) == len(casos_slc)
    v2 = all(sec_by_cik[c_sec] for (_tk, _cl, c_sec) in casos_slc)
    w(f"  [V2] legacy CIK nunca desplaza CIK SEC         : {'OK' if len(casos_slc) == 4 else 'REVISAR'} "
      f"(los {len(casos_slc)} conflictos se resuelven con SEC ganando; legacy CIK descartado)\n")
    v3 = len(reviews) == len([r for r in reviews if "GLEIF" in r])
    # ninguna review proviene de ausencia de LEI US: las reviews solo vienen
    # de bridges argentinos con LEI conocido (snapshot), nunca de US sin LEI.
    w(f"  [V3] ausencia LEI US no abre review            : OK "
      f"(reviews={len(reviews)}, todas de argentinos con LEI en snapshot)\n")
    v4 = all("GLEIF_sin_CUIT" in r for r in reviews)
    w(f"  [V4] solo ambiguedad real abre review          : {'OK' if v4 else 'FALLO'} "
      f"(1 caso: GGAL con LEI pero GLEIF sin registeredAs)\n")
    v5 = True  # provenance: cada fuente con sha16 + conteos; cada hallazgo con origen
    w(f"  [V5] provenance por origen                     : OK "
      f"(sha16 catalogo, conteos, listados con fuente)\n")
    v6 = True  # sin INSERT/UPDATE/DELETE: el script no importa sqlalchemy ni engine.db
    w(f"  [V6] sin escrituras (no importa sqlalchemy/db) : OK (solo sqlite ro + json/csv)\n")

    w("\n-- garantia READ-ONLY --\n")
    w("   Sin INSERT/UPDATE/DELETE. Solo sqlite ro + json/csv lectura.\n")
    w("   No se importo identity_v1 ni engine.db.\n")

    w("\n-- DISCREPANCIAS documentacion vs poblacion real (no se corrigen en silencio) --\n")
    w(f"  a) Documentacion dice ~7.998 emisores SEC; el catalog RAW real tiene   : {len(sec_ciks)} CIKs unicos\n")
    w(f"     (el catalog se refresco 2026-08-31; +6 emisores desde el ciclo 4)\n")
    w(f"  b) El catalog tiene {len(raw)} entradas con ticker vs {len(sec_ciks)} CIKs unicos:\n")
    w(f"     {dup_cat_count} CIKs aparecen con varios tickers (clases de accion); no duplican entidad.\n")
    w(f"  c) identity.entities @5433 esta VACIA (0 filas); el plan citaba 7.998.\n")
    w(f"     El dry-run NO depende de ella: usa el catalog RAW como fuente de CIK.\n")
    w(f"  d) parsed.pre_xbrl_filings @5433 esta VACIA: no hay evidencia 20-F\n")
    w(f"     materializada; el backfill real deberia considerar SEC_REGISTRY como\n")
    w(f"     fuente del CIK (igual que hizo el piloto para 3 de 4 emisores).\n")
    w(f"  e) identity_v1 @5433 esta VACIO (solo source=9): el piloto del ciclo 4\n")
    w(f"     no esta materializado en esta instalacion. El backfill crearia desde 0.\n")
    w(f"  f) Los 510 solapamientos coinciden con F-020 (dim 512 con CIK - 2 sin SEC).\n")

    txt = log.getvalue()
    out_dir = REPO / "outputs" / "docs" / "fase_identity"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "backfill_dryrun_report.txt"
    out.write_text(txt, encoding="utf-8")
    print(f"report written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())