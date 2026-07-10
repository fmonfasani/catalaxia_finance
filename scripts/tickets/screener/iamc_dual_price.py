# -*- coding: utf-8 -*-
"""
IAMC + DUAL PRICE (ARS / USD)  —  fuente de precios oficial BYMA + doble moneda
==============================================================================
1. Baja el "Informe Diario de Acciones" de IAMC (precio de cierre OFICIAL de BYMA +
   market cap por especie). Cache en data/raw/iamc/. Resiliente (usa el último cacheado
   si IAMC no responde).
2. Guarda tabla `iamc_precios` (ticker, cierre_ars, mcap_M_ars, fecha).
3. Inserta BMA (Banco Macro) al screener si falta (sus ratios ya están en `ratios`).
4. Calcula el **CCL** (dólar contado con liqui) desde los ADR:
       CCL = precio_local_ARS × adr_ratio / precio_ADR_USD   (mediana, robusto)
5. Llena `precio_ars` y `precio_usd` para las 571+ empresas:
       BYMA  → precio_ars = cierre oficial IAMC (o yfinance si falta) ; precio_usd = ars/CCL
       ADR   → precio_usd = ADR NYSE (yfinance) ; precio_ars = local IAMC (o usd×CCL/ratio)
       S&P   → precio_usd = NYSE (yfinance) ; precio_ars = usd × CCL (valor en pesos)
   Además guarda `ccl` y `precio_dif_iamc` (dif % yfinance vs IAMC, para BYMA).

Orden en el pipeline: … s7 → s8 → **iamc_dual_price** → s5 (export)
Uso:  python iamc_dual_price.py
"""
from __future__ import annotations
import re, sqlite3, statistics as st
from pathlib import Path
from datetime import datetime

import requests
import urllib3
import pdfplumber
urllib3.disable_warnings()

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"
IAMC_RAW = ROOT / "data" / "raw" / "iamc"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}

DEC2 = re.compile(r'^\d[\d,]*\.\d{2}$')
TICK = re.compile(r'^[A-Z][A-Z0-9]{1,5}$')
MCAP = re.compile(r'^[\d,]+M$')

# Banco Macro: ADR importante que faltaba en el screener (sus ratios ya están en `ratios`).
BMA_CIK = "0001347426"
BMA_ADR_RATIO = 10  # 1 ADR = 10 acciones clase B (dato oficial del filing, provisto)


def _num(s):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


# ── 1. Descarga del informe (con cache/resiliencia) ──
def descubrir_pdf_url(log):
    """informediario -> link del InformeDiarioAcciones más reciente -> URL del PDF (TempFiles).
    El slug es DDMMYY (no ordenable como string) → parsear y ordenar por (año, mes, día)."""
    try:
        r = requests.get("https://www.iamc.com.ar/informediario/", headers=H, timeout=20, verify=False)
        m = re.findall(r'/Informe/InformeDiarioAcciones(\d{2})(\d{2})(\d{2})/', r.text)
        if not m:
            return None
        dd, mm, yy = max(set(m), key=lambda x: (x[2], x[1], x[0]))  # (yy, mm, dd) cronológico
        page_url = f"https://www.iamc.com.ar/Informe/InformeDiarioAcciones{dd}{mm}{yy}/"
        log(f"iamc: informe más reciente = {dd}/{mm}/{yy}")
        r2 = requests.get(page_url, headers=H, timeout=20, verify=False)
        pdfs = re.findall(r'(https?://[^"\'\s]+?\.pdf)', r2.text, re.I)
        pdfs = [p for p in pdfs if "TempFiles" in p or "ingecloud" in p]
        return (pdfs[0], page_url) if pdfs else None
    except Exception as e:
        log(f"iamc: error descubriendo URL: {e}")
        return None


def bajar_pdf(log):
    """Devuelve path a un PDF del informe (bajado o el último cacheado)."""
    IAMC_RAW.mkdir(parents=True, exist_ok=True)
    hoy = datetime.now().strftime("%Y%m%d")
    dest = IAMC_RAW / f"iamc_acciones_{hoy}.pdf"
    if dest.exists() and dest.stat().st_size > 100000:
        log(f"iamc: usando PDF ya bajado hoy ({dest.name})")
        return dest
    found = descubrir_pdf_url(log)
    if found:
        url, _page = found
        try:
            r = requests.get(url, headers=H, timeout=40, verify=False)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf"):
                dest.write_bytes(r.content)
                log(f"iamc: PDF bajado ({len(r.content)//1024} KB) -> {dest.name}")
                return dest
        except Exception as e:
            log(f"iamc: error bajando PDF: {e}")
    # fallback: el cacheado más nuevo
    cached = sorted(IAMC_RAW.glob("iamc_acciones_*.pdf"))
    if cached:
        log(f"iamc: IAMC no responde — uso cache {cached[-1].name}")
        return cached[-1]
    log("iamc: sin PDF (ni bajado ni cacheado) — dual-price seguirá con yfinance solo")
    return None


def parsear_pdf(path):
    """Devuelve {especie: {'cierre': float, 'mcap_M': float}} de las tablas de precios.
    SOLO las páginas de paneles de precios (MERVAL, BYMA GENERAL, PANEL GENERAL). Las
    páginas de VARIACIONES/rankings (4+) tienen otro layout y corromperían el cierre."""
    out = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            # solo los paneles de precios tienen el encabezado con "Cierre"
            if "Cierre" not in txt:
                continue
            for line in txt.splitlines():
                t = line.split()
                if len(t) < 10 or not TICK.match(t[0]):
                    continue
                dec2 = [x for x in t if DEC2.match(x)]
                mc = [x for x in t if MCAP.match(x)]
                if len(dec2) >= 4:
                    out[t[0]] = {"cierre": _num(dec2[3]),
                                 "mcap_M": _num(mc[0][:-1]) if mc else None}
    return out


# ── 2/3/4/5: build ──
def build():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    log = lambda m: print(m)

    print("IAMC + DUAL PRICE (ARS/USD)")
    print("=" * 60)

    # ── 1. bajar + parsear ──
    pdf = bajar_pdf(log)
    iamc = parsear_pdf(pdf) if pdf else {}
    print(f"  IAMC: {len(iamc)} especies con precio de cierre oficial")

    # ── 2. tabla iamc_precios ──
    cur.execute("""CREATE TABLE IF NOT EXISTS iamc_precios (
        ticker TEXT PRIMARY KEY, cierre_ars REAL, mcap_M_ars REAL, fecha TEXT)""")
    cur.execute("DELETE FROM iamc_precios")
    fecha = datetime.now().strftime("%Y-%m-%d")
    for tk, d in iamc.items():
        cur.execute("INSERT OR REPLACE INTO iamc_precios VALUES (?,?,?,?)",
                    (tk, d["cierre"], d["mcap_M"], fecha))
    con.commit()

    # ── 3. asegurar columnas ──
    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for c, tipo in [("precio_ars", "REAL"), ("precio_usd", "REAL"),
                    ("ccl", "REAL"), ("precio_dif_iamc", "REAL"), ("precio_fuente", "TEXT")]:
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {tipo}")

    # ── 3b. insertar BMA (Banco Macro) si falta ──
    existe_bma = cur.execute("SELECT COUNT(*) FROM screener WHERE ticker='BMA' AND grupo='adr'").fetchone()[0]
    if not existe_bma:
        r = cur.execute("SELECT cik,ticker,nombre,roe,roa,margen_neto,deuda_ebitda,eps_anual,"
                        "per,p_book,p_sales,payout,cagr_eps_5y,sector_gics FROM ratios WHERE cik=?",
                        (BMA_CIK,)).fetchone()
        if r:
            cur.execute("""INSERT OR REPLACE INTO screener
                (cuit,ticker,grupo,ROE,ROA,MargenNeto,DeudaEBITDA,EPS,PER,PriceBook,PriceSales,
                 Payout,CAGR_EPS_5y,sector,adr_ratio,fuente_fund,es_financiera,CAGR_flag,provenance)
                VALUES (?,?,'adr',?,?,?,?,?,?,?,?,?,?,?,?, 'edgar', 1, 'edgar','EDGAR(20-F)')""",
                (r["cik"], "BMA", r["roe"], r["roa"], r["margen_neto"], r["deuda_ebitda"],
                 r["eps_anual"], r["per"], r["p_book"], r["p_sales"], r["payout"],
                 r["cagr_eps_5y"], "Financiero", BMA_ADR_RATIO))
            con.commit()
            print("  + BMA (Banco Macro) insertado al grupo adr (ratio 10, desde EDGAR 20-F)")

    # ── 4. CCL desde los ADR ──
    ccl_rows = cur.execute("SELECT ticker, adr_ratio, Precio FROM screener "
                           "WHERE grupo='adr' AND adr_ratio IS NOT NULL AND Precio IS NOT NULL").fetchall()
    ccls = []
    for row in ccl_rows:
        loc = iamc.get(row["ticker"])
        if loc and loc["cierre"] and row["Precio"]:
            c = loc["cierre"] * row["adr_ratio"] / row["Precio"]
            ccls.append((row["ticker"], c))
    # descartar outliers (dato IAMC de mala celda): quedarnos con los cercanos a la mediana
    if ccls:
        med0 = st.median([c for _, c in ccls])
        buenos = [(t, c) for t, c in ccls if 0.7 * med0 <= c <= 1.3 * med0]
        ccl = st.median([c for _, c in buenos]) if buenos else med0
        for t, c in ccls:
            marca = "" if 0.7 * med0 <= c <= 1.3 * med0 else "  <-- outlier (descartado)"
            print(f"    CCL {t:6} = {c:>7.0f}{marca}")
        disp = 100 * (max(c for _, c in buenos) - min(c for _, c in buenos)) / ccl if buenos else 0
        print(f"  CCL (mediana de {len(buenos)}/{len(ccls)} ADR) = {ccl:.0f} ARS/USD  (dispersión {disp:.1f}%)")
    else:
        ccl = None
        print("  CCL: no calculable (sin ADR con local IAMC) — precio_usd de BYMA quedará NULL")

    # ── 5. dual price por fila ──
    n_ars = n_usd = n_fix = 0
    filas = cur.execute("SELECT cuit, ticker, grupo, adr_ratio, Precio, Currency FROM screener").fetchall()
    upd = con.cursor()
    for row in filas:
        tk, grupo = row["ticker"], row["grupo"]
        precio, cur_ = row["Precio"], row["Currency"]
        loc = iamc.get(tk)
        precio_ars = precio_usd = dif = None
        fuente = None

        if grupo == "byma_only":
            if loc and loc["cierre"]:
                precio_ars = loc["cierre"]; fuente = "iamc"
                if precio and precio > 0:
                    dif = 100 * (precio - loc["cierre"]) / loc["cierre"]
                    if abs(dif) > 10:
                        n_fix += 1
            elif cur_ == "ARS" and precio:
                precio_ars = precio; fuente = "yfinance"
            if precio_ars and ccl:
                precio_usd = precio_ars / ccl

        elif grupo == "adr":
            precio_usd = precio  # yfinance ADR NYSE (USD)
            if loc and loc["cierre"]:
                precio_ars = loc["cierre"]; fuente = "iamc"
            elif precio_usd and ccl and row["adr_ratio"]:
                precio_ars = precio_usd * ccl / row["adr_ratio"]; fuente = "implied"
            # fallback: si no hay ADR USD (ej. BMA insertado sin Precio), derivarlo del local
            if precio_usd is None and precio_ars and ccl and row["adr_ratio"]:
                precio_usd = precio_ars * row["adr_ratio"] / ccl; fuente = fuente or "implied_usd"

        else:  # sp500
            precio_usd = precio
            if precio_usd and ccl:
                precio_ars = precio_usd * ccl; fuente = "ccl"

        if precio_ars is not None:
            n_ars += 1
        if precio_usd is not None:
            n_usd += 1
        upd.execute("UPDATE screener SET precio_ars=?, precio_usd=?, ccl=?, precio_dif_iamc=?, precio_fuente=? WHERE cuit=?",
                    (precio_ars, precio_usd, ccl, dif, fuente, row["cuit"]))
    con.commit()

    print(f"  precio_ars: {n_ars} · precio_usd: {n_usd} · BYMA con dif>10% vs IAMC (yfinance mal): {n_fix}")
    # reporte de los que yfinance tenía mal
    malos = cur.execute("SELECT ticker, Precio, precio_ars FROM screener "
                        "WHERE grupo='byma_only' AND precio_dif_iamc IS NOT NULL AND ABS(precio_dif_iamc)>10 "
                        "ORDER BY ABS(precio_dif_iamc) DESC").fetchall()
    if malos:
        print("  precios BYMA corregidos con IAMC (yfinance estaba mal):")
        for m in malos[:12]:
            print(f"    {m['ticker']:6} yfinance={m['Precio']:>10.2f}  ->  IAMC={m['precio_ars']:>10.2f}")
    con.close()
    print("\nIAMC + DUAL PRICE -- OK")


if __name__ == "__main__":
    build()
