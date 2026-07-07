# -*- coding: utf-8 -*-
"""
FASE 4 -- Ensamblar screener completo
======================================
Merge de ratios_cnv + precios + ratios hibridos.

13 ratios:
   1- 7: Fundamentales CNV (ROE, ROA, MargenNeto, DeudaEBITDA, EPS, FCF/CE, Payout)
      8: CAGR EPS 5y (flageado vintage_mixto)
   9-11: Hibridos CNV+precio (PER, PriceBook, PriceSales)
  12-13: Precio (Max52w, Min52w)

Reglas:
  - Bancos: si |calc - CNV_*| > 0.05 absoluto, usar CNV_* oficial
  - Payout: facts.BYMA-{ticker} Dividends / NetIncome del mismo periodo
  - FCF/CE usa Equity+DebtNonCurrent (sin dependencia de precios)
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from collections import defaultdict

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"

# NOTA: UMBRAL_CNV desactivado. Los valores CNV_* son v1 stale y con v2
# normalizado, los calculados son mas confiables. Ver _check_margen2.py.
UMBRAL_CNV = 9999  # desactivado


def get_valor(cur, cuit, concepto, period_end):
    cur.execute("""
        SELECT valor FROM cnv_estados_norm
        WHERE cuit=? AND concepto=? AND period_end=?
        ORDER BY fecha_reexpresion DESC LIMIT 1
    """, (cuit, concepto, period_end))
    r = cur.fetchone()
    return r[0] if r else None


def get_ttm(cur, cuit, concepto, ultimo):
    """Suma ultimos 4 trimestres de un concepto (TTM).
    Busca los 4 periodos mas recientes <= ultimo y suma sus valores.
    """
    cur.execute("""
        SELECT DISTINCT period_end FROM cnv_estados_norm
        WHERE cuit=? AND concepto=?
          AND period_end <= ?
        ORDER BY period_end DESC LIMIT 4
    """, (cuit, concepto, ultimo))
    periods = [r[0] for r in cur.fetchall()]
    if len(periods) < 4:
        return None
    total = 0.0
    for pe in periods:
        v = get_valor(cur, cuit, concepto, pe)
        if v is None:
            return None
        total += v
    return total


def get_payout_facts(cur, ticker, period_end):
    """Obtener payout desde facts para BYMA-{ticker}.
    Payout = Dividends / NetIncome del mismo periodo fiscal.
    facts.val es Cash Dividends Paid anual.
    """
    # NetIncome de cnv_estados_norm
    cur.execute("""
        SELECT valor FROM cnv_estados_norm n
        JOIN mapa_entidades m ON m.cuit=n.cuit
        WHERE m.ticker=? AND m.es_primario=1
          AND n.concepto='NetIncome' AND n.period_end=?
        ORDER BY n.fecha_reexpresion DESC LIMIT 1
    """, (ticker, period_end))
    ni = cur.fetchone()
    if not ni or not ni[0] or ni[0] == 0:
        return None
    # Dividends from facts, matching same fiscal year
    # Extract year from period_end
    year = period_end[:4] if period_end and len(period_end) >= 4 else None
    if not year:
        return None
    cur.execute("""
        SELECT val FROM facts
        WHERE cik=? AND concepto='Dividends'
          AND strftime('%Y', period_end)=?
        ORDER BY period_end DESC LIMIT 1
    """, (f"BYMA-{ticker}", year))
    div = cur.fetchone()
    if not div or not div[0]:
        return None
    payout = abs(div[0]) / abs(ni[0])
    # Sanity check: payout should be between 0 and ~2
    if payout > 2:
        return None
    return payout


def build():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    print("FASE 4 -- Ensamblar screener completo")
    print("=" * 60)

    cur.execute("DROP TABLE IF EXISTS screener")
    cur.execute("""
        CREATE TABLE screener (
            cuit TEXT PRIMARY KEY,
            ticker TEXT,
            ultimo_periodo TEXT,
            grupo TEXT,
            -- 7 fundamentales
            ROE REAL,
            ROA REAL,
            MargenNeto REAL,
            DeudaEBITDA REAL,
            EPS REAL,
            FCF_CE REAL,
            Payout REAL,
            -- CAGR (flageado)
            CAGR_EPS_5y REAL,
            CAGR_flag TEXT,
            -- Hibridos (precio + CNV)
            PER REAL,
            PriceBook REAL,
            PriceSales REAL,
            -- Precio
            Precio REAL,
            MarketCapUSD REAL,
            Currency TEXT,
            Max52w REAL,
            Min52w REAL,
            -- flags
            flag_cnv_fallback INTEGER DEFAULT 0,
            flag_no_significativo INTEGER DEFAULT 0,
            dato_desactualizado INTEGER DEFAULT 0,
            payout_source TEXT,
            provenance TEXT
        )
    """)

    # Leer ratios_cnv
    cur.execute("""
        SELECT r.cuit, r.ticker, r.ultimo_periodo,
               r.ROE, r.ROA, r.MargenNeto, r.DeudaEBITDA, r.EPS, r.FCFYield, r.Payout,
               r.CAGR_EPS_5y, r.CAGR_flag,
               r.CNV_roe, r.CNV_roa, r.CNV_margen_neto, r.CNV_deuda_ebitda
        FROM ratios_cnv r
    """)
    ratios = {r[0]: r for r in cur.fetchall()}
    print(f"ratios_cnv: {len(ratios)} entidades")

    # Leer precios (mas recientes por ticker)
    cur.execute("""
        SELECT ticker, precio, market_cap, year_high, year_low, currency
        FROM precios
        WHERE (ticker, fecha) IN (
            SELECT ticker, MAX(fecha) FROM precios GROUP BY ticker
        )
    """)
    precios = {}
    for r in cur.fetchall():
        precios[r[0]] = {"precio": r[1], "mcap": r[2], "yhigh": r[3], "ylow": r[4], "cur": r[5]}
    print(f"precios: {len(precios)} tickers")

    # Pre-cache dividendos desde facts para todos los BYMA-* tickers
    print("\nCargando dividendos desde facts (BYMA-* yfinance)...")
    cur.execute("""
        SELECT cik, val, period_end FROM facts
        WHERE cik LIKE 'BYMA-%' AND concepto='Dividends'
        ORDER BY cik, period_end DESC
    """)
    div_facts = defaultdict(list)
    for r in cur.fetchall():
        cik = r[0]
        ticker = cik.replace("BYMA-", "")
        div_facts[ticker].append({"val": r[1], "period_end": r[2]})
    print(f"  {len(div_facts)} tickers con dividendos en facts")

    # FX cache
    fx_cache = {}

    def get_fx(currency):
        if currency is None or currency == "USD":
            return 1.0
        if currency in fx_cache:
            return fx_cache[currency]
        try:
            import yfinance as yf
            r = yf.Ticker(f"{currency}=X").fast_info.last_price
            fx = 1.0 / r if r else None
        except Exception:
            fx = None
        fx_cache[currency] = fx
        return fx

    # Ensamblar
    stats = defaultdict(int)
    ok = 0
    sin_precio = 0
    cnv_fallback_entities = set()

    for cuit, data in ratios.items():
        (_, ticker, ultimo,
         roe_calc, roa_calc, margen_calc, de_calc, eps, fcf, payout_old,
         cagr, cagr_flag,
         cnv_roe, cnv_roa, cnv_margen, cnv_deudae) = data

        items_prov = []

        # --- Fix #1: CNV_* fallback por diferencia ABSOLUTA > 0.05 ---
        flag_cnv_fb = 0
        fallbacks = []

        def check_fallback(calc, oficial, label):
            nonlocal flag_cnv_fb
            if calc is not None and oficial is not None:
                if abs(calc - oficial) > UMBRAL_CNV:
                    flag_cnv_fb = 1
                    fallbacks.append(label)
                    return oficial
            return calc

        roe = check_fallback(roe_calc, cnv_roe, "ROE")
        roa = check_fallback(roa_calc, cnv_roa, "ROA")
        margen = check_fallback(margen_calc, cnv_margen, "Margen")
        deuda_ebitda = check_fallback(de_calc, cnv_deudae, "D/EBITDA")

        if flag_cnv_fb:
            cnv_fallback_entities.add(ticker)
            for fb in fallbacks:
                items_prov.append(f"{fb}(cnv_oficial)")
            items_prov.append("flag=cnv_fallback")
        else:
            for name, val in [("ROE", roe), ("ROA", roa), ("Margen", margen), ("D/EBITDA", deuda_ebitda)]:
                if val is not None: items_prov.append(name)

        if eps is not None: items_prov.append("EPS")
        if cagr is not None: items_prov.append(f"CAGR({cagr_flag})")

        # --- Fix #2: Payout desde facts.BYMA-{ticker} ---
        # Dividend data is annual (Cash Dividends Paid) from yfinance,
        # keyed by the dividend's fiscal year-end period_end.
        # For each dividend, match NI at the SAME period_end (not ultimo).
        payout_final = None
        payout_src = None
        if ticker in div_facts:
            for d in div_facts[ticker]:
                div_pe = d["period_end"]
                ni = get_valor(cur, cuit, "NetIncome", div_pe)
                if ni and ni != 0:
                    payout_candidate = abs(d["val"]) / abs(ni)
                    if 0 < payout_candidate <= 2:
                        payout_final = payout_candidate
                        payout_src = f"facts(yfinance)"
                        items_prov.append("Payout(facts)")
                        break

        # Si facts no tiene payout, caer al de s2 (calculado desde cnv_dividendos)
        if payout_final is None and payout_old is not None and 0 < payout_old <= 2:
            payout_final = payout_old
            payout_src = "cnv_dividendos"
            items_prov.append("Payout(cnv_dividendos)")

        if payout_final is None:
            items_prov.append("Payout(sin_dato)")

        # --- Fix #3: FCF/CE en vez de FCFYield ---
        cf_op = get_valor(cur, cuit, "CF_Operativo", ultimo)
        cf_inv = get_valor(cur, cuit, "CF_Inversion", ultimo)
        equity = get_valor(cur, cuit, "Equity", ultimo)
        dnc = get_valor(cur, cuit, "DebtNonCurrent", ultimo)

        fcf_val = None
        if cf_op is not None and cf_inv is not None:
            fcf_val = cf_op + cf_inv
        ce = None
        if equity is not None:
            ce = equity + (dnc or 0)
        fcf_ce = (fcf_val / ce) if (fcf_val is not None and ce and ce != 0) else None
        if fcf_ce is not None:
            items_prov.append("FCF/CE")

        # Precio
        p = precios.get(ticker)
        if p:
            precio = p["precio"]
            mcap = p["mcap"]
            cury = p["cur"]
            yhigh = p["yhigh"]
            ylow = p["ylow"]
            max52w = (yhigh / precio - 1) if yhigh and precio else None
            min52w = (precio / ylow - 1) if ylow and precio else None
            items_prov.append(f"Precio={cury}")
            stats["con_precio"] += 1
        else:
            precio = mcap = cury = yhigh = ylow = max52w = min52w = None
            sin_precio += 1

        # Per-share valuation: PER = Precio/EPS, P/B = Precio/BVPS, P/S = Precio/SPS.
        # Evita market_cap de Yahoo (usa shares inconsistentes con CNV).
        # shares = NetIncome / EPS (CNV-consistent, single period).
        # BYMA: precio en ARS, fundamentales en ARS → ratio directo.
        # ADR:  precio en USD → convertir precio a ARS para emparejar moneda.
        eps = get_valor(cur, cuit, "EPS_basico", ultimo)
        ni = get_valor(cur, cuit, "NetIncome", ultimo)
        shares = abs(ni / eps) if (eps is not None and ni is not None and eps != 0) else None

        # Para ADR: precio esta en USD, fundamentales en ARS.
        # get_fx("ARS") devuelve USD_per_ARS (0.000673).
        # precio_ars = precio_usd / USD_per_ARS = precio_usd * ARS_per_USD.
        precio_ars = precio
        if cury is not None and cury != "ARS":
            usd_per_ars = get_fx("ARS") if cury == "USD" else get_fx(cury)
            if usd_per_ars:
                precio_ars = precio / usd_per_ars

        # PER = Precio / EPS  (un periodo, no necesita shares)
        per_raw = (precio_ars / eps) if (precio_ars is not None and eps is not None and eps > 0) else None

        # P/B = Precio / (Equity / shares) = Precio * shares / Equity
        eq = get_valor(cur, cuit, "Equity", ultimo)
        pb_raw = None
        if precio_ars is not None and eq is not None and eq > 0 and shares is not None and shares > 0:
            pb_raw = precio_ars / (eq / shares)

        # P/S = Precio / (Revenue / shares) = Precio * shares / Revenue
        rev = get_valor(cur, cuit, "Revenue", ultimo)
        ps_raw = None
        if precio_ars is not None and rev is not None and rev > 0 and shares is not None and shares > 0:
            ps_raw = precio_ars / (rev / shares)

        # Flag de desactualizacion: period_ref >= 2 anos
        dato_desactualizado = 1 if (ultimo or "") < "2024-01-01" else 0

        # Anular cada ratio solo si su propio denominador es ≈ 0 o el ratio es absurdo.
        # PER: sin sentido si EPS ≤ 0 (pérdida) o PER > 500
        per = per_raw if (per_raw is not None and per_raw <= 500 and eps is not None and eps > 0) else None
        # P/B: válido si Equity > 0 y P/B ≤ 50
        pb = pb_raw if (pb_raw is not None and pb_raw <= 50 and eq is not None and eq > 0) else None
        # P/S: válido si Revenue > 0 y P/S ≤ 50
        ps = ps_raw if (ps_raw is not None and ps_raw <= 50 and rev is not None and rev > 0) else None

        # Si los datos estan desactualizados, anular valuacion hibrida
        # (precio actual / fundamentales viejos = sin sentido)
        if dato_desactualizado:
            per = pb = ps = None

        # Flag combinado de no_significativo (al menos un ratio anulado o sospechoso)
        # Nuevos: Margen (|Margen|>300% o Revenue<=0) y ROE (Equity<=0)
        margen_flag = (margen is not None and abs(margen) > 3) or (margen is not None and rev is not None and rev <= 0)
        roe_flag = roe is not None and eq is not None and eq <= 0
        flag_no_sig = 1 if (
            (per_raw is not None and per is None)
            or (pb_raw is not None and pb is None)
            or (ps_raw is not None and ps is None)
            or margen_flag
            or roe_flag
        ) else 0

        # Stats
        for name, val in [("ROE", roe), ("ROA", roa), ("Margen", margen),
                          ("D/EBITDA", deuda_ebitda), ("EPS", eps), ("FCF/CE", fcf_ce),
                          ("Payout", payout_final),
                          ("PER", per), ("P/B", pb), ("P/S", ps)]:
            if val is not None:
                stats[f"con_{name}"] += 1

        provenance = "; ".join(items_prov) if items_prov else "sin_datos"
        if per is not None: provenance += "; PER"
        if pb is not None: provenance += "; P/B"
        if ps is not None: provenance += "; P/S"

        cur.execute("SELECT grupo FROM mapa_entidades WHERE cuit=? AND es_primario=1", (cuit,))
        grp_row = cur.fetchone()
        grupo = grp_row[0] if grp_row else "?"

        cur.execute("""
            INSERT OR REPLACE INTO screener
            VALUES (?,?,?,?, ?,?,?,?,?,?,?, ?,?, ?,?,?, ?,?,?, ?,?, ?,?, ?, ?, ?)
        """, (cuit, ticker, ultimo, grupo,
              roe, roa, margen, deuda_ebitda, eps, fcf_ce, payout_final,
              cagr, cagr_flag,
              per, pb, ps,
              precio, mcap, cury, max52w, min52w,
              flag_cnv_fb, flag_no_sig, dato_desactualizado, payout_src,
              provenance))
        ok += 1

    con.commit()

    # Reporte
    n = ok
    print(f"\n  screener: {n} filas")
    print(f"\n  Cobertura:")
    for name in ["ROE", "ROA", "Margen", "D/EBITDA", "EPS", "FCF/CE",
                  "Payout", "CAGR", "PER", "P/B", "P/S"]:
        cnt = stats.get(f"con_{name}", 0) if name != "CAGR" else sum(1 for r in ratios.values() if r[10] is not None)
        pct = round(100 * cnt / max(n, 1))
        print(f"    {name:<12} {cnt:>3}/{n} ({pct}%)")

    print(f"\n  Fallback a CNV_* oficial: {len(cnv_fallback_entities)}/{n}")
    if cnv_fallback_entities:
        print(f"    Entidades: {', '.join(sorted(cnv_fallback_entities)[:15])}...")
    print(f"  Precio disponible: {stats.get('con_precio', 0)}/{n}")
    print(f"  Sin precio: {sin_precio}/{n}")
    print(f"  FX usados: {len(fx_cache)} monedas -> {fx_cache}")

    con.close()
    print("\nFASE 4 -- OK")


if __name__ == "__main__":
    build()
