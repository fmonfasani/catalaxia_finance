# -*- coding: utf-8 -*-
"""
FASE 6 · AJUSTES POST-ENSAMBLADO (reproducible, idempotente)
============================================================
Consolida en el pipeline los ajustes que antes se hacían a mano sobre la DB, para que
NO se pierdan al re-correr s4. Lee artefactos versionados y ajusta la tabla `screener`.

Aplica:
  1. Tickers reales de los ADR (desde datos/adr_tickers.csv) → screener + mapa_entidades.
  2. Flag `es_financiera` para bancos + N/A de los ratios industriales que no aplican
     (MargenNeto, DeudaEBITDA, PriceSales, FCF_CE).
  3. Relleno de ROE/ROA donde s2 lo dejó NULL pero hay NetIncome + Equity(>0) (gap de s2).
  4. Columna `sector` (clasificación por nombre; bancos → Financiero).

Orden en el pipeline: s0 → s2 → s3 → s4 → **s6** → s5 (export).
Uso:  python s6_ajustes.py
"""
from __future__ import annotations
import sqlite3, csv
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
DATOS = Path(__file__).resolve().parent.parent / "cnv" / "datos"

NA_BANCO = ["MargenNeto", "DeudaEBITDA", "PriceSales", "FCF_CE"]
BANK_TK = {"GGAL", "GGALB", "SUPV", "SUPVB", "BBAR", "BHIP", "BPAT", "BMA", "VALO"}

SECTORES = [  # (sector, keywords en el nombre) — orden importa
    ("Energia",         ["ypf", "pampa", "central puerto", "vista", "capex", "transener",
                          "transportadora de gas", "metrogas", "edenor", "distribuidora",
                          "comercializadora norte", "energia", "petrole", "albanesi", "genneia", "solar"]),
    ("Materiales",      ["aluar", "ternium", "siderar", "loma negra", "holcim", "celulosa",
                          "ledesma", "acero", "cemento", "carboclor"]),
    ("RealEstate_Agro", ["irsa", "cresud", "inmobil", "agro", "san miguel", "juramento", "semino"]),
    ("Telecom_Media",   ["telecom", "cablevis", "clarin"]),
    ("Consumo",         ["molinos", "mirgor", "grimoldi", "morixe", "boldt", "domec",
                          "longvie", "havanna", "garovaglio", "importadora"]),
    ("Infra_Utilities", ["aeropuertos", "autopistas", "concesion", "gas natural"]),
]


def nombre_map():
    m = {}
    for fn in ("empresas_556.csv", "empresas_subset.csv"):
        p = DATOS / fn
        if p.exists():
            for r in csv.DictReader(open(p, encoding="utf-8-sig")):
                m[r["cuit"].strip()] = r.get("empresa", "")
    return m


def clasificar_sector(nombre, es_fin):
    if es_fin:
        return "Financiero"
    n = (nombre or "").lower()
    for sec, kws in SECTORES:
        if any(k in n for k in kws):
            return sec
    return "Otros"


def usar_edgar_para_adr(cur):
    """Para los ADR: reemplaza fundamentales+valuacion por los ratios EDGAR OFICIALES
    (20-F), que son limpios (USD/IFRS, sin FX/ratio-ADR/vintage). Guarda el ratio ADR."""
    cols = [r[1] for r in cur.execute("PRAGMA table_info(screener)")]
    for c, t in (("adr_ratio", "INTEGER"), ("fuente_fund", "TEXT")):
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {t}")
    cur.execute("UPDATE screener SET fuente_fund='cnv' WHERE fuente_fund IS NULL")
    has_cols = {r[1] for r in cur.execute("PRAGMA table_info(ratios)")}
    MAP = {"ROE": "roe", "ROA": "roa", "MargenNeto": "margen_neto", "DeudaEBITDA": "deuda_ebitda",
           "EPS": "eps_anual", "Payout": "payout", "CAGR_EPS_5y": "cagr_eps_5y"}
    for sc, rc in [("PER", "per"), ("PriceBook", "p_book"), ("PriceSales", "p_sales")]:
        if rc in has_cols:
            MAP[sc] = rc
    n = 0
    for cuit, etk, adrr in cur.execute(
        "SELECT s.cuit, ar.edgar_ticker, ar.ratio FROM screener s JOIN adr_ratios ar ON s.cuit=ar.cuit WHERE s.grupo='adr'").fetchall():
        er = cur.execute(f"SELECT {','.join(MAP.values())} FROM ratios WHERE ticker=?", (etk,)).fetchone()
        if not er:
            continue
        sets = ", ".join(f'"{sc}"=?' for sc in MAP)
        cur.execute(f"UPDATE screener SET {sets}, adr_ratio=?, fuente_fund='edgar', CAGR_flag='edgar' WHERE cuit=?",
                    list(er) + [adrr, cuit])
        n += 1
    return n


def main():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(screener)")]
    for c, tipo in (("es_financiera", "INTEGER DEFAULT 0"), ("sector", "TEXT")):
        if c not in cols:
            cur.execute(f'ALTER TABLE screener ADD COLUMN {c} {tipo}')
    nom = nombre_map()

    # 1) tickers ADR
    n_adr = 0
    adr = DATOS / "adr_tickers.csv"
    if adr.exists():
        for r in csv.DictReader(open(adr, encoding="utf-8-sig")):
            for tbl in ("screener", "mapa_entidades"):
                if tbl in [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
                    cur.execute(f"UPDATE {tbl} SET ticker=? WHERE cuit=?", (r["ticker"], r["cuit"]))
            n_adr += 1

    # 1b) ADR: usar ratios EDGAR oficiales (reemplaza CNV para los que cotizan en NY)
    n_edgar = usar_edgar_para_adr(cur)

    # 2) bancos: flag + N/A ratios industriales
    n_bank = 0
    for tk, cuit in cur.execute("SELECT ticker, cuit FROM screener").fetchall():
        n = nom.get(cuit, "")
        if tk in BANK_TK or "banco" in n.lower() or "financ" in n.lower():
            cur.execute("UPDATE screener SET es_financiera=1 WHERE cuit=?", (cuit,))
            cur.execute(f"UPDATE screener SET {','.join(c+'=NULL' for c in NA_BANCO)} WHERE cuit=?", (cuit,))
            n_bank += 1

    # 3) relleno ROE/ROA (gap de s2): NULL pero hay NI + Equity>0
    def v(cuit, c):
        r = cur.execute("SELECT valor FROM cnv_estados_v2 WHERE cuit=? AND concepto=? ORDER BY period_end DESC LIMIT 1", (cuit, c)).fetchone()
        return r[0] if r else None
    n_roe = 0
    for (cuit,) in cur.execute("SELECT cuit FROM screener WHERE ROE IS NULL").fetchall():
        ni, eq, asset = v(cuit, "NetIncome"), v(cuit, "Equity"), v(cuit, "Assets")
        if ni is not None and eq and eq > 0:
            cur.execute("UPDATE screener SET ROE=?, ROA=? WHERE cuit=?",
                        (ni / eq, (ni / asset if asset else None), cuit)); n_roe += 1

    # 4) sector
    n_sec = 0
    for cuit, esf in cur.execute("SELECT cuit, es_financiera FROM screener").fetchall():
        cur.execute("UPDATE screener SET sector=? WHERE cuit=?", (clasificar_sector(nom.get(cuit, ""), esf), cuit)); n_sec += 1

    con.commit()
    print(f"s6 ajustes: {n_adr} tickers ADR · {n_edgar} ADR desde EDGAR · {n_bank} bancos (flag+N/A) · {n_roe} ROE rellenados · {n_sec} sectores")
    print("  sectores:", dict(cur.execute("SELECT sector, COUNT(*) FROM screener GROUP BY sector ORDER BY 2 DESC").fetchall()))
    con.close()


if __name__ == "__main__":
    main()
