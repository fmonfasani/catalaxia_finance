# -*- coding: utf-8 -*-
"""
FASE 1 · UNIFICAR UNIVERSOS (S&P 500 + ADR + BYMA)
====================================================
Inserta en `screener` las empresas S&P 500 desde la tabla `ratios` (EDGAR),
junto a las 56 BYMA (CNV) y 16 ADR (CNV + EDGAR en s6) que ya existen.

Clave: los S&P no tienen CUIT → se usa `cik` como identificador único en la
columna `cuit` (TEXT). AR CUIT (11 dígitos) vs CIK (10 dígitos con ceros a la
izquierda) no colisionan.

Idempotente: INSERT OR REPLACE por cuit.

Orden en el pipeline: s0 → s2 → s3 → s4 → s6 → s7 → s5
Uso:  python s7_unificar.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion:
#   SCREENER_DB=screener.db.test python scripts/tickets/screener/run_all.py
# Debe estar en TODOS los scripts del pipeline: si uno solo no lo respeta,
# escribe en la base real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")

# Mapeo ratios → screener (reusado de s6.usar_edgar_para_adr)
MAP_RATIOS_SCREENER = {
    "ROE": "roe",
    "ROA": "roa",
    "MargenNeto": "margen_neto",
    "DeudaEBITDA": "deuda_ebitda",
    "EPS": "eps_anual",
    "PER": "per",
    "PriceBook": "p_book",
    "PriceSales": "p_sales",
    "Payout": "payout",
    "CAGR_EPS_5y": "cagr_eps_5y",
}

# Columnas del screener (orden del CREATE TABLE en s4 + ALTER TABLE en s6)
SCREENER_COLS = [
    "cuit", "ticker", "ultimo_periodo", "grupo",
    "ROE", "ROA", "MargenNeto", "DeudaEBITDA", "EPS", "FCF_CE", "Payout",
    "CAGR_EPS_5y", "CAGR_flag",
    "PER", "PriceBook", "PriceSales",
    "Precio", "MarketCapUSD", "Currency", "Max52w", "Min52w",
    "flag_cnv_fallback", "flag_no_significativo", "dato_desactualizado",
    "payout_source", "provenance",
    "es_financiera", "sector", "adr_ratio", "fuente_fund",
]
PH = ",".join("?" * len(SCREENER_COLS))


def build():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("FASE 1 — Unificar universos (S&P 500 desde EDGAR)")
    print("=" * 60)

    # ── Asegurar columnas necesarias ──
    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for c, tipo in [("es_financiera", "INTEGER DEFAULT 0"),
                    ("sector", "TEXT"),
                    ("adr_ratio", "INTEGER"),
                    ("fuente_fund", "TEXT")]:
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {tipo}")

    # ── Filter MAP to only existing ratios columns ──
    ratio_cols_in_db = {r[1] for r in cur.execute("PRAGMA table_info(ratios)")}
    MAP = {k: v for k, v in MAP_RATIOS_SCREENER.items() if v in ratio_cols_in_db}

    # ── Cargar precios (últimos por ticker, con 52w) ──
    cur.execute("""
        SELECT ticker, precio, market_cap, year_high, year_low, currency
        FROM precios
        WHERE (ticker, fecha) IN (
            SELECT ticker, MAX(fecha) FROM precios GROUP BY ticker
        )
    """)
    precios_map = {}
    for r in cur.fetchall():
        precios_map[r["ticker"]] = {
            "precio": r["precio"],
            "mcap": r["market_cap"],
            "yhigh": r["year_high"],
            "ylow": r["year_low"],
            "cur": r["currency"],
        }
    print(f"  precios cargados: {len(precios_map)} tickers")

    # ── Insertar S&P 500 desde ratios ──
    BUILD_COLS = ["_fcf_ttm", "_equity", "_deuda"]
    ratio_cols = ",".join(MAP.values())
    build_cols = ",".join(f"r.{c}" for c in BUILD_COLS)
    cur.execute(f"""
        SELECT r.cik, r.ticker, r.nombre, r.fecha,
               r.sector_gics,
               {ratio_cols}, {build_cols}
        FROM ratios r
        WHERE r.grupo = 'sp500'
        ORDER BY r.ticker
    """)
    rows = cur.fetchall()
    print(f"  ratios sp500: {len(rows)} empresas")

    # Column names for the select (for indexed access)
    R_COLS = ["cik", "ticker", "nombre", "fecha",
              "sector_gics"] + list(MAP.values()) + BUILD_COLS

    insertados = 0
    saltados = 0

    for row in rows:
        rd = dict(zip(R_COLS, row))

        cik = rd["cik"]
        ticker = rd["ticker"]
        fecha = rd["fecha"]
        sector_gics = rd["sector_gics"]

        # Precio desde ratios (tiene el mismo valor que precios.precio)
        p = precios_map.get(ticker)
        precio = p["precio"] if p else rd.get("precio")
        market_cap = p["mcap"] if p else rd.get("market_cap")
        currency = p["cur"] if p else "USD"
        if currency is None:
            currency = "USD"

        # 52w: distancia desde el precio actual
        max52w = None
        min52w = None
        if p and p["yhigh"] and precio:
            max52w = (p["yhigh"] / precio - 1) if precio > 0 else None
        if p and p["ylow"] and precio:
            min52w = (precio / p["ylow"] - 1) if p["ylow"] > 0 else None

        # Mapear ratios
        vals = {}
        for screener_col, ratio_col in MAP.items():
            vals[screener_col] = rd.get(ratio_col)
        for sc in ["PER", "PriceBook", "PriceSales"]:
            vals.setdefault(sc, None)

        # Building blocks para FCF_CE y sanity
        fcf_ttm = rd.get("_fcf_ttm")
        equity = rd.get("_equity")
        deuda = rd.get("_deuda")
        ce = (equity or 0) + (deuda or 0)
        fcf_ce_snp = (fcf_ttm / ce) if (fcf_ttm is not None and ce > 0) else None

        # Si no hay precio, anular valuacion hibrida
        if not precio:
            vals["PER"] = None
            vals["PriceBook"] = None
            vals["PriceSales"] = None

        # Flag no_significativo
        flag_no_sig = 0
        if (vals["PER"] is not None and vals["PER"] > 500) or \
           (vals["PriceBook"] is not None and vals["PriceBook"] > 50) or \
           (vals["PriceSales"] is not None and vals["PriceSales"] > 50) or \
           (vals["ROE"] is not None and vals["ROE"] > 10.0) or \
           (vals["MargenNeto"] is not None and abs(vals["MargenNeto"]) > 3):
            flag_no_sig = 1
        # Equity <= 0 (recompras): ROE y PriceBook son sin sentido
        if equity is not None and equity <= 0:
            flag_no_sig = 1

        # provenance
        prov = "EDGAR(10-K)"
        fuente = "edgar"

        # Fecha: truncar ISO datetime a date
        ultimo_periodo = fecha[:10] if fecha and "T" in fecha else fecha

        # Build full row in SCREENER_COLS order
        screener_row = [
            cik,                     # cuit (usamos CIK como key)
            ticker,                  # ticker
            ultimo_periodo,          # ultimo_periodo
            "sp500",                 # grupo
            vals["ROE"],             # ROE
            vals["ROA"],             # ROA
            vals["MargenNeto"],      # MargenNeto
            vals["DeudaEBITDA"],     # DeudaEBITDA
            vals["EPS"],             # EPS
            fcf_ce_snp,              # FCF_CE (computado: _fcf_ttm/(_equity+_deuda))
            vals["Payout"],          # Payout
            vals["CAGR_EPS_5y"],     # CAGR_EPS_5y
            "edgar",                 # CAGR_flag
            vals["PER"],             # PER
            vals["PriceBook"],       # PriceBook
            vals["PriceSales"],      # PriceSales
            precio,                  # Precio
            market_cap,              # MarketCapUSD
            currency,                # Currency
            max52w,                  # Max52w
            min52w,                  # Min52w
            0,                       # flag_cnv_fallback
            flag_no_sig,             # flag_no_significativo
            0,                       # dato_desactualizado
            "edgar",                 # payout_source
            prov,                    # provenance
            0,                       # es_financiera
            sector_gics,             # sector (GICS)
            None,                    # adr_ratio
            fuente,                  # fuente_fund
        ]

        cur.execute(f"INSERT OR REPLACE INTO screener ({','.join(SCREENER_COLS)}) VALUES ({PH})",
                    screener_row)
        insertados += 1

    con.commit()

    # ── BMA (Banco Macro): ADR argentino con fundamentales en EDGAR (20-F) que no
    #    entra por el SELECT de arriba porque en `ratios` esta como grupo='adr_arg',
    #    no 'sp500'. Antes lo insertaba iamc_dual_price.py; se movio aca, que es su
    #    lugar natural (unificar universos) y no depende de ninguna fuente externa.
    #    NOTA: hay otros 10 adr_arg en `ratios` sin entrar al screener (MELI, YPF,
    #    GLOB, PAM, TGS, TEO, IRS, EDN, CRESY, BIOX). Sumarlos es una decision de
    #    producto (cambia el universo publicado), no un arreglo tecnico.
    BMA_CIK = "0001347426"
    BMA_ADR_RATIO = 10  # 1 ADR = 10 acciones clase B (20-F oficial)
    ya_esta = cur.execute(
        "SELECT COUNT(*) FROM screener WHERE ticker='BMA'").fetchone()[0]
    if not ya_esta:
        r = cur.execute(
            "SELECT cik,roe,roa,margen_neto,deuda_ebitda,eps_anual,per,p_book,"
            "p_sales,payout,cagr_eps_5y FROM ratios WHERE cik=?", (BMA_CIK,)).fetchone()
        if r:
            cur.execute("""INSERT OR REPLACE INTO screener
                (cuit,ticker,grupo,ROE,ROA,MargenNeto,DeudaEBITDA,EPS,PER,PriceBook,
                 PriceSales,Payout,CAGR_EPS_5y,sector,adr_ratio,fuente_fund,
                 es_financiera,CAGR_flag,provenance)
                VALUES (?,?,'adr',?,?,?,?,?,?,?,?,?,?,?,?,'edgar',1,'edgar','EDGAR(20-F)')""",
                (r["cik"], "BMA", r["roe"], r["roa"], r["margen_neto"], r["deuda_ebitda"],
                 r["eps_anual"], r["per"], r["p_book"], r["p_sales"], r["payout"],
                 r["cagr_eps_5y"], "Financiero", BMA_ADR_RATIO))
            con.commit()
            print("  + BMA (Banco Macro) insertado en grupo adr desde EDGAR 20-F")

    # ── Reporte ──
    cur.execute("SELECT COUNT(*) FROM screener")
    total = cur.fetchone()[0]
    cur.execute("SELECT grupo, COUNT(*) FROM screener GROUP BY grupo ORDER BY grupo")
    grupos = cur.fetchall()

    print(f"\n  Insertados: {insertados} S&P 500")
    print(f"  Total screener: {total} filas")
    for g in grupos:
        print(f"    {g['grupo']}: {g['COUNT(*)']}")

    # Cobertura
    print(f"\n  Cobertura por ratio:")
    for r in ["ROE", "ROA", "MargenNeto", "DeudaEBITDA", "EPS",
              "Payout", "PER", "PriceBook", "PriceSales", "CAGR_EPS_5y"]:
        cur.execute(f'SELECT COUNT(*) FROM screener WHERE "{r}" IS NOT NULL')
        cnt = cur.fetchone()[0]
        pct = round(100 * cnt / max(total, 1))
        print(f"    {r:<15s} {cnt:>3}/{total} ({pct}%)")

    cur.execute("SELECT sector, COUNT(*) FROM screener GROUP BY sector ORDER BY 2 DESC LIMIT 15")
    print(f"\n  Sectores:")
    for r in cur.fetchall():
        print(f"    {r['sector']:<30s} {r['COUNT(*)']}")

    con.close()
    print("\nFASE 1 -- OK")


if __name__ == "__main__":
    build()
