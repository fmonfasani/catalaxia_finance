# -*- coding: utf-8 -*-
"""
FASE 2 · CALIDAD DE RATIOS (payout_status, EV/EBITDA, margen_operativo)
========================================================================
Agrega tres columnas al screener:
  1. payout_status  → 'calculado' / 'no_paga' / 'falta_dato'
  2. ev_ebitda      → Enterprise Value / EBITDA
  3. margen_operativo → Operating Income / Revenue

Fuentes:
  - S&P 500: tabla `ratios` (EDGAR) + `facts` (dividendos)
  - BYMA/ADR: `cnv_estados_norm` + `facts.BYMA-*`

Orden en el pipeline: s0 → s2 → s3 → s4 → s6 → s7 → s8 → s5
Uso:  python s8_calidad.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from collections import defaultdict

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
from _perimetro import perimetro_preferido
from _precondiciones import requiere_columnas, requiere_filas
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")


def ensure_columns(cur):
    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    for c, tipo in [("payout_status", "TEXT"),
                    ("ev_ebitda", "REAL"),
                    ("margen_operativo", "REAL")]:
        if c not in cols:
            cur.execute(f"ALTER TABLE screener ADD COLUMN {c} {tipo}")


def load_ratios_edgar(cur):
    """Load ratios data for S&P 500 (joined by cik==cuit)."""
    cur.execute("""
        SELECT s.cuit, s.ticker, s.MarketCapUSD, s.Precio, s.Payout,
               r._deuda, r._ebitda_ttm, r.margen_operativo,
               r._assets, r._equity
        FROM screener s
        JOIN ratios r ON r.cik = s.cuit
        WHERE s.grupo = 'sp500'
    """)
    rows = cur.fetchall()
    result = {}
    for r in rows:
        result[r["cuit"]] = {
            "ticker": r["ticker"],
            "mcap": r["MarketCapUSD"],
            "precio": r["Precio"],
            "payout_screener": r["Payout"],
            "deuda": r["_deuda"],
            "ebitda": r["_ebitda_ttm"],
            "margen_op": r["margen_operativo"],
            "assets": r["_assets"],
            "equity": r["_equity"],
        }
    return result


def load_valor_ar(cur, cuit, concepto):
    """Get the most recent reliable value for an AR company concept.
    Queries both cnv_estados_v2 and cnv_estados_norm, preferring the
    most recent period after a sanity check against the prior period."""
    # Get latest from v2
    cur.execute("""
        SELECT period_end, valor FROM cnv_estados_v2
        WHERE cuit=? AND concepto=?
        ORDER BY period_end DESC LIMIT 1
    """, (cuit, concepto))
    v2 = cur.fetchone()

    # Get latest 2 from norm (for sanity check)
    # Regla de perimetro: se toman los 2 periodos mas recientes y de cada uno el
    # valor del perimetro elegido. Ver _perimetro.py y docs/07-homologacion-cnv.md.
    cur.execute("""
        SELECT DISTINCT period_end FROM cnv_estados_norm
        WHERE cuit=? AND concepto=?
        ORDER BY period_end DESC LIMIT 2
    """, (cuit, concepto))
    normas = []
    for (_pe,) in cur.fetchall():
        _p = perimetro_preferido(cur, cuit, _pe)
        if _p:
            cur.execute("""SELECT valor FROM cnv_estados_norm
                           WHERE cuit=? AND concepto=? AND period_end=? AND tipo_balance=?
                           ORDER BY fecha_reexpresion DESC LIMIT 1""",
                        (cuit, concepto, _pe, _p))
        else:
            cur.execute("""SELECT valor FROM cnv_estados_norm
                           WHERE cuit=? AND concepto=? AND period_end=?
                           ORDER BY fecha_reexpresion DESC LIMIT 1""",
                        (cuit, concepto, _pe))
        _r = cur.fetchone()
        if _r:
            normas.append((_pe, _r[0]))

    use_norm = False
    if len(normas) >= 1:
        norm_latest = normas[0]
        # Sanity check: latest must not be < 0.1% of previous
        if len(normas) >= 2:
            prev_val = normas[1][1]
            if prev_val and prev_val > 0:
                if norm_latest[1] and norm_latest[1] > 0 and norm_latest[1] < prev_val * 0.001:
                    pass  # garbage — do not use norm
                else:
                    use_norm = True
            else:
                use_norm = True
        else:
            use_norm = True

    if use_norm and v2:
        return norm_latest[1] if norm_latest[0] >= v2[0] else v2[1]
    if use_norm:
        return norm_latest[1]
    if v2:
        return v2[1]
    return None


def compute_payout_status(cur, cuit, grupo, payout_val):
    """Classify payout: calculado / no_paga / falta_dato."""
    if payout_val is not None:
        return "calculado"

    if grupo == "sp500":
        # Check if company has Dividends in facts by CIK
        cur.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND concepto='Dividends'", (cuit,))
        has_div = cur.fetchone()[0] > 0
        return "falta_dato" if has_div else "no_paga"

    elif grupo == "adr":
        # Check EDGAR ratios for their ticker, plus CNV data
        cur.execute("""
            SELECT COUNT(*) FROM adr_ratios ar
            JOIN ratios r ON r.ticker = ar.edgar_ticker
            WHERE ar.cuit=? AND r.payout IS NOT NULL
        """, (cuit,))
        has_edgar_div = cur.fetchone()[0] > 0
        if has_edgar_div:
            return "falta_dato"
        # Fall through to byma check
        return compute_payout_status_byma(cur, cuit)

    else:  # byma_only
        return compute_payout_status_byma(cur, cuit)


def compute_payout_status_byma(cur, cuit):
    """Check if a BYMA company has dividend data (facts or CNV)."""
    cur.execute("""
        SELECT COUNT(*) FROM facts f
        JOIN mapa_entidades m ON m.cuit=?
        WHERE f.cik = 'BYMA-' || m.ticker AND f.concepto='Dividends'
    """, (cuit,))
    has_facts_div = cur.fetchone()[0] > 0
    cur.execute("SELECT COUNT(*) FROM cnv_dividendos WHERE cuit=?", (cuit,))
    has_cnv_div = cur.fetchone()[0] > 0
    return "falta_dato" if (has_facts_div or has_cnv_div) else "no_paga"


def compute_ev_ebitda_sp500(row):
    """EV = MarketCapUSD + deuda. EBITDA = _ebitda_ttm.
    Fallbacks when _deuda is NULL:
      - total_liabilities = _assets - _equity (if both positive)
    """
    mcap = row.get("mcap")
    ebitda = row.get("ebitda")
    if mcap is None or ebitda is None or ebitda <= 0:
        return None

    deuda = row.get("deuda")
    if deuda is not None:
        ev = mcap + deuda
        return ev / ebitda

    # Fallback: total liabilities as debt proxy
    assets = row.get("assets")
    equity = row.get("equity")
    if assets is not None and equity is not None and assets > 0:
        liab = assets - equity
        if liab > 0:
            ev = mcap + liab
            ratio = ev / ebitda
            # Cap at 100x to avoid absurd results (financials with deposits)
            if ratio < 100:
                return ratio
    return None


def compute_ev_ebitda_cnv(mcap, deuda, ebitda):
    if mcap is not None and deuda is not None and ebitda is not None and ebitda > 0:
        ev = mcap + deuda
        return ev / ebitda
    return None


def compute_margen_operativo_cnv(oi, rev):
    if oi is not None and rev is not None and rev > 0:
        return oi / rev
    return None


def apply_no_significativo(cur):
    """Post-pass que aplica flag_no_significativo sobre TODAS las filas del screener.
    Corre después de s7 (donde se insertan las S&P), porque s4/s6 no cubren las S&P."""
    cur.execute("SELECT cuit, ticker, grupo FROM screener ORDER BY grupo, ticker")
    rows = cur.fetchall()
    updated = 0
    for r in rows:
        cuit = r["cuit"]
        ticker = r["ticker"]
        grupo = r["grupo"]

        # Obtener equity y revenue según el universo
        if grupo == "sp500":
            cur.execute("SELECT _equity, _revenue_ttm, _netincome_ttm FROM ratios WHERE cik=?", (cuit,))
            rr = cur.fetchone()
            equity = rr[0] if rr else None
            revenue = rr[1] if rr else None
            netincome = rr[2] if rr else None
        else:
            equity = load_valor_ar(cur, cuit, "Equity")
            revenue = load_valor_ar(cur, cuit, "Revenue")
            netincome = load_valor_ar(cur, cuit, "NetIncome")

        # Leer valores actuales del screener
        cur.execute("SELECT ROE, PER, PriceBook, PriceSales, MargenNeto, EPS, DeudaEBITDA, ev_ebitda, flag_no_significativo FROM screener WHERE cuit=?", (cuit,))
        sr = cur.fetchone()
        if not sr:
            continue
        roe = sr["ROE"]
        per = sr["PER"]
        pb = sr["PriceBook"]
        ps = sr["PriceSales"]
        margen = sr["MargenNeto"]
        eps = sr["EPS"]
        deuda_ebitda = sr["DeudaEBITDA"]
        ev_ebitda = sr["ev_ebitda"]
        flag_old = sr["flag_no_significativo"]

        flag_new = flag_old

        # Reglas de null + flag
        null_per = False
        null_pb = False
        null_ps = False
        null_roe = False
        null_deuda_ebitda = False
        null_ev_ebitda = False

        # Equity <= 0 (recompras): P/B y ROE quedan sin sentido, PERO el PER sigue
        # siendo válido si la empresa tiene utilidad (MCD, SBUX, PM, AZO, HCA... tienen
        # equity contable negativo por buybacks y earnings sólidos). Anulamos P/B y ROE.
        if equity is not None and equity <= 0:
            flag_new = 1
            null_pb = True
            null_roe = True

        # Revenue <= 0: P/S no tiene sentido
        if revenue is not None and revenue <= 0:
            flag_new = 1
            null_ps = True

        # NetIncome (TTM) <= 0: la empresa no genera ganancia → PER sin sentido.
        # Usamos netincome (la base con la que se calcula el PER), NO eps_anual, que
        # puede ser un corte anual atípico negativo aun con TTM positivo (APD, F, EL...).
        if netincome is not None and netincome <= 0:
            null_per = True

        # PER > 500
        if per is not None and per > 500:
            flag_new = 1
            null_per = True

        # P/B > 50
        if pb is not None and pb > 50:
            flag_new = 1
            null_pb = True

        # P/S > 50
        if ps is not None and ps > 50:
            flag_new = 1
            null_ps = True

        # ROE extremo (|ROE| > 5 = 500%): equity ínfimo o dato de mala unidad (NIC-29).
        # No es significativo para screening → null + flag. (Real máx ~ AAPL 1.4, KO 0.46.)
        if roe is not None and abs(roe) > 5:
            flag_new = 1
            null_roe = True

        # PER > 500
        if per is not None and per > 500:
            flag_new = 1
            null_per = True

        # P/B > 50
        if pb is not None and pb > 50:
            flag_new = 1
            null_pb = True

        # P/S > 50 (ya cubierto arriba, redundante-safe)
        if ps is not None and ps > 50:
            flag_new = 1
            null_ps = True

        # EV/EBITDA fuera de rango razonable → dato no confiable (EBITDA ~0 o mala unidad
        # NIC-29 en BYMA: ROSE/AUSO/OEST dan millones). Válido: 0 < x <= 100.
        if ev_ebitda is not None and not (0 < ev_ebitda <= 100):
            flag_new = 1
            null_ev_ebitda = True

        # Deuda/EBITDA fuera de rango → mismo problema (ROSE 14M, VICI 51.7, RICH -71).
        # Válido: -25 (net cash fuerte) <= x <= 40 (muy apalancado).
        if deuda_ebitda is not None and not (-25 <= deuda_ebitda <= 40):
            flag_new = 1
            null_deuda_ebitda = True

        # MargenNeto absurdo
        if margen is not None and abs(margen) > 3:
            flag_new = 1

        # Aplicar cambios
        new_per = None if null_per else per
        new_pb = None if null_pb else pb
        new_ps = None if null_ps else ps
        new_roe = None if null_roe else roe
        new_de = None if null_deuda_ebitda else deuda_ebitda
        new_ev = None if null_ev_ebitda else ev_ebitda

        changes = []
        for old, new, lbl in [(per, new_per, "PER"), (pb, new_pb, "P/B"), (ps, new_ps, "P/S"),
                              (roe, new_roe, "ROE"), (deuda_ebitda, new_de, "D/EBITDA"),
                              (ev_ebitda, new_ev, "EV/EBITDA")]:
            if new != old:
                changes.append(lbl)
        if flag_new != flag_old:
            changes.append(f"flag={flag_old}->{flag_new}")

        if changes:
            cur.execute("""
                UPDATE screener SET PER=?, PriceBook=?, PriceSales=?, ROE=?,
                       DeudaEBITDA=?, ev_ebitda=?, flag_no_significativo=?
                WHERE cuit=?
            """, (new_per, new_pb, new_ps, new_roe, new_de, new_ev, flag_new, cuit))
            updated += 1
    return updated


def build():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("FASE 2 — Calidad de ratios (payout_status, EV/EBITDA, margen_operativo)")
    print("=" * 60)

    # s8 lee columnas que crea s6 (fuente_fund, sector, es_financiera) y trabaja
    # sobre el universo completo que arma s7. Sin esto el fallo es un IndexError
    # cripitico al leer row["fuente_fund"].
    requiere_columnas(cur, "screener",
                      ["fuente_fund", "sector", "es_financiera"], "s6_ajustes")
    requiere_filas(cur, "screener", 100, "s7_unificar")

    ensure_columns(cur)

    # Load S&P EDGAR data
    edgar_data = load_ratios_edgar(cur)
    print(f"  S&P con datos EDGAR: {len(edgar_data)}")

    # Cache CNV dividend data for BYMA
    cur.execute("SELECT DISTINCT cuit FROM cnv_dividendos")
    cnv_div_cuits = {r[0] for r in cur.fetchall()}

    # Cache facts BYMA dividends by ticker
    cur.execute("""
        SELECT DISTINCT REPLACE(cik, 'BYMA-', '') as tk FROM facts
        WHERE cik LIKE 'BYMA-%' AND concepto='Dividends'
    """)
    facts_byma_tickers = {r[0] for r in cur.fetchall()}

    # Also cache facts dividends by CIK for sp500
    cur.execute("SELECT DISTINCT cik FROM facts WHERE concepto='Dividends' AND cik NOT LIKE 'BYMA-%'")
    facts_div_ciks = {r[0] for r in cur.fetchall()}

    # Process each company
    stats = defaultdict(int)
    cur.execute("SELECT * FROM screener ORDER BY grupo, ticker")
    rows = cur.fetchall()
    n = len(rows)

    for row in rows:
        cuit = row["cuit"]
        ticker = row["ticker"]
        grupo = row["grupo"]

        # --- payout_status ---
        payout_val = row["Payout"]
        if grupo == "sp500":
            if payout_val is not None:
                ps = "calculado"
            elif cuit in facts_div_ciks:
                ps = "falta_dato"
            else:
                ps = "no_paga"
        elif grupo == "adr":
            if payout_val is not None:
                ps = "calculado"
            else:
                # Check if EDGAR has payout for this ADR
                cur.execute("""
                    SELECT COUNT(*) FROM adr_ratios ar
                    JOIN ratios r ON r.ticker = ar.edgar_ticker
                    WHERE ar.cuit=? AND r.payout IS NOT NULL
                """, (cuit,))
                has_edgar_payout = cur.fetchone()[0] > 0
                if has_edgar_payout:
                    ps = "falta_dato"
                else:
                    # Fall through to BYMA check
                    base_ticker = ticker.replace("B", "").replace("2", "").replace("D", "").replace("LUZ", "")
                    has_data = (base_ticker in facts_byma_tickers) or (cuit in cnv_div_cuits)
                    ps = "falta_dato" if has_data else "no_paga"
        else:  # byma_only
            if payout_val is not None:
                ps = "calculado"
            else:
                base_tk = ticker.replace("_2", "")
                has_data = (base_tk in facts_byma_tickers) or (cuit in cnv_div_cuits)
                ps = "falta_dato" if has_data else "no_paga"
        stats[f"payout_{ps}"] += 1

        # --- ev_ebitda ---
        ev_ebitda = None
        if grupo == "sp500":
            ed = edgar_data.get(cuit)
            if ed:
                ev_ebitda = compute_ev_ebitda_sp500(ed)
        elif grupo == "adr" and row["fuente_fund"] == "edgar":
            # ADR con EDGAR: usar ev_ebitda de ratios si existe
            cur.execute("PRAGMA table_info(ratios)")
            ratio_cols = {r[1] for r in cur.fetchall()}
            if "ev_ebitda" in ratio_cols:
                cur.execute("""
                    SELECT r.ev_ebitda FROM adr_ratios ar
                    JOIN ratios r ON r.ticker = ar.edgar_ticker
                    WHERE ar.cuit=?
                """, (cuit,))
                er = cur.fetchone()
                if er and er[0] is not None:
                    ev_ebitda = er[0]
        if ev_ebitda is None:
            # BYMA-only: EV/EBITDA desde CNV, todo en ARS
            if grupo == "byma_only":
                mcap = row["MarketCapUSD"]
                ebitda = load_valor_ar(cur, cuit, "EBITDA")
                if mcap and ebitda and ebitda > 0:
                    deuda_nc = load_valor_ar(cur, cuit, "DebtNonCurrent")
                    deuda_c = load_valor_ar(cur, cuit, "DebtCurrent")
                    if deuda_nc is not None or deuda_c is not None:
                        deuda_ct = (deuda_nc or 0) + (deuda_c or 0)
                        ev = mcap + deuda_ct
                        ev_ebitda = ev / ebitda
        if ev_ebitda is not None:
            stats["ev_ebitda_ok"] += 1

        # --- margen_operativo ---
        margen_op = None
        if grupo == "sp500":
            ed = edgar_data.get(cuit)
            if ed:
                margen_op = ed.get("margen_op")
        else:
            oi = load_valor_ar(cur, cuit, "OperatingIncome")
            rev = load_valor_ar(cur, cuit, "Revenue")
            margen_op = compute_margen_operativo_cnv(oi, rev)
        if margen_op is not None:
            stats["margen_op_ok"] += 1

        # Update screener
        cur.execute("""
            UPDATE screener SET payout_status=?, ev_ebitda=?, margen_operativo=?
            WHERE cuit=?
        """, (ps, ev_ebitda, margen_op, cuit))

    con.commit()

    # --- Post-pass: no_significativo sobre TODAS las filas ---
    n_flagged = apply_no_significativo(cur)
    print(f"\n  no_significativo flag actualizado: {n_flagged} filas")
    con.commit()

    # --- Report ---
    print(f"\n  Procesadas: {n} empresas")
    print(f"\n  payout_status:")
    for st in ["calculado", "no_paga", "falta_dato"]:
        cnt = stats.get(f"payout_{st}", 0)
        print(f"    {st:<15s} {cnt:>3} ({100*cnt//n}%)")
    n_payout_respondido = stats.get("payout_calculado", 0) + stats.get("payout_no_paga", 0)
    print(f"    {'respondido':<15s} {n_payout_respondido:>3} ({100*n_payout_respondido//n}%)")
    print(f"\n  ev_ebitda:         {stats['ev_ebitda_ok']:>3}/{n} ({100*stats['ev_ebitda_ok']//n}%)")
    print(f"  margen_operativo:  {stats['margen_op_ok']:>3}/{n} ({100*stats['margen_op_ok']//n}%)")

    # By universe
    for grupo in ["sp500", "adr", "byma_only"]:
        cur.execute(f"""
            SELECT COUNT(*) as total,
                   COALESCE(SUM(CASE WHEN payout_status='calculado' THEN 1 ELSE 0 END), 0) as calc,
                   COALESCE(SUM(CASE WHEN payout_status='no_paga' THEN 1 ELSE 0 END), 0) as no_paga,
                   COALESCE(SUM(CASE WHEN payout_status='falta_dato' THEN 1 ELSE 0 END), 0) as falta,
                   COALESCE(SUM(CASE WHEN ev_ebitda IS NOT NULL THEN 1 ELSE 0 END), 0) as ev,
                   COALESCE(SUM(CASE WHEN margen_operativo IS NOT NULL THEN 1 ELSE 0 END), 0) as margen
            FROM screener WHERE grupo=?
        """, (grupo,))
        r = cur.fetchone()
        tot = r["total"]
        print(f"\n  {grupo:15s} n={tot:>3}: payout_calc={r['calc']:>3} no_paga={r['no_paga']:>3} falta={r['falta']:>2}  ev/ebitda={r['ev']:>3}/{tot} margen_op={r['margen']:>3}/{tot}")

    # Coverage summary
    cur.execute("SELECT COUNT(*) FROM screener WHERE payout_status IS NOT NULL")
    print(f"\n  payout_status coverage: {cur.fetchone()[0]}/{n}")
    cur.execute("SELECT COUNT(*) FROM screener WHERE payout_status IS NOT NULL AND payout_status != 'falta_dato'")
    print(f"  payout respondido (calc+no_paga): {cur.fetchone()[0]}/{n}")

    con.close()
    print("\nFASE 2 -- OK")


if __name__ == "__main__":
    build()
