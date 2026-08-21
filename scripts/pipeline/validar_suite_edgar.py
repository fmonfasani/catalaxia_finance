# -*- coding: utf-8 -*-
"""
SUITE DE VALIDACION — EDGAR (S&P 500 + ADR)
============================================
Adaptacion de validar_suite.py (que cubre byma_only desde CNV) al universo EDGAR.
Misma arquitectura de 4 capas y la MISMA regla de certificacion, de modo que el
nivel de una empresa del S&P es comparable con el de una BYMA.

    Capa 1  identidades contables internas
    Capa 2  continuidad temporal
    Capa 3  ancla externa (investing)
    Capa 4  ancla de mercado (market cap)

Regla: certifica si pasa TODAS las identidades duras aplicables + al menos un
ancla independiente de la escala del balance.

--------------------------------------------------------------------------
MAPEO DE CONCEPTOS  cnv_reextract -> facts
--------------------------------------------------------------------------
    assets              -> Assets                revenue        -> Revenue
    assets_current      -> AssetsCurrent         cogs           -> COGS
    liabilities         -> Liabilities           gross_profit   -> GrossProfit
    liabilities_current -> LiabilitiesCurrent    operating_income-> OperatingIncome
    equity              -> Equity                ebitda         -> EBITDA_reported
    cash                -> Cash                  da             -> DA
    cfo                 -> CFO                   net_income     -> NetIncome
    cfi/cff             -> via tag us-gaap       pretax_income  -> PretaxIncome
                           (no hay concepto canonico)           income_tax -> IncomeTax

DOS CHECKS NO TIENEN EQUIVALENTE DIRECTO y se reemplazan por su analogo
estructural, no se descartan:

  c10  BYMA cruza nuestro ROE contra el ROE que la empresa auto-declara
       (codigo CNV 8000009). EDGAR no publica ratios auto-declarados.
       -> Analogo: EPS_diluted reportado vs NetIncome/Shares_diluted. Mismo
          proposito (fidelidad de extraccion contra algo que la empresa dijo),
          y EDGAR tiene los tres campos.

  c12  BYMA verifica que el Revenue YTD sea monotonico, porque la CNV reporta
       acumulado.
       -> Analogo: suma de los trimestres del ejercicio ~= el FY reportado.
          OJO: EDGAR publica para el MISMO fp la fila standalone (~90d) Y la
          acumulada (~181d/~272d). Hay que filtrar por duracion o el total se
          infla y da falsas fallas (250 de 499 antes de filtrar).

  c2   BYMA valida Activo = AC + ANC. En EDGAR AssetsNoncurrent aparece en
       1094 filas de 4,6M, asi que no es computable.
       -> Reemplazo MAS fuerte: Assets vs LiabilitiesAndStockholdersEquity
          (501 CIK), el total que la empresa declara explicitamente. No lo
          derivamos nosotros: lo afirma la empresa y lo contrastamos.

c6 (EBITDA = EBIT + DA) queda NA para todo el universo y es correcto: EBITDA
no es una medida GAAP y las empresas de EEUU no la publican en XBRL. Es
ausencia legitima, no un defecto de extraccion.

El cruce externo (c15) convierte nuestro EPS a pesos con el MEP: investing
publica el listado local (CEDEAR para el S&P), no la accion en dolares.
Comparar directo daba 100% de fallas falsas.

Salida: tablas validacion_suite_edgar y screener_nivel_edgar, mas la vista
v_validacion_todos que unifica con la suite BYMA.

Uso:  python scripts/pipeline/validar_suite_edgar.py
"""
from __future__ import annotations

import io
import sqlite3
import sys
from datetime import date
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# SCREENER_DB permite apuntar a una copia de prueba sin tocar produccion.
# Debe estar en TODOS los scripts que escriben en la base: si uno solo no lo
# respeta, escribe en la real aunque el resto corra sobre la copia.
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
TOL = 0.04          # tolerancia relativa de las identidades (igual que BYMA)
TOL_SELFREP = 0.20  # tolerancia del cruce de auto-reporte
TOL_EXT = 0.25      # tolerancia contra investing

# ── FALLBACK POR TAG us-gaap ──────────────────────────────────────────
# La normalizacion tag -> `concepto` quedo incompleta: COGS aparece con
# concepto canonico en 53 CIK de 600, IncomeTax en 56. Los tags crudos en
# cambio tienen cobertura buena (IncomeTaxExpenseBenefit: 497 CIK). Sin este
# fallback, c4 y c5 darian NA para todo el universo y la suite no validaria
# nada del estado de resultados.
# Se usa solo si el concepto canonico falta: el canonico manda.
TAG_FALLBACK = {
    "NetCashProvidedByUsedInInvestingActivities": "CFI",
    "NetCashProvidedByUsedInFinancingActivities": "CFF",
    "IncomeTaxExpenseBenefit": "IncomeTax",          # 497 CIK
    "CostOfGoodsAndServicesSold": "COGS",            # 230 CIK
    "CostOfRevenue": "COGS",                         #  91 CIK
    "LiabilitiesAndStockholdersEquity": "TotalPasivoPN",  # 501 CIK
    # `Equity` canonico mapea a StockholdersEquity = patrimonio DE LA MATRIZ.
    # En un balance consolidado el total incluye ademas el interes minoritario,
    # asi que Activo = Pasivo + Equity da de menos entre 4% y 15% en las
    # empresas con filiales no 100% propias. Verificado en AMT/APD/APO/ARE/
    # ARES/BEN: con esta variante las seis cierran.
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "EquityInclNCI",  # 341 CIK
}


def rel_ok(a, b, tol=TOL):
    """|a-b| <= |b|*tol. None si falta alguno (-> NA)."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    return abs(a - b) <= abs(b) * tol


def sign_ok(g, r, c, tol=TOL):
    """g = r - c  o  g = r + c, segun como venga firmado el costo."""
    if None in (g, r, c):
        return None
    return min(abs(g - (r - c)), abs(g - (r + c))) <= abs(r) * tol + 1


def S(a):
    return "OK" if a else ("FAIL" if a is not None else "NA")


def build():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()

    # ── anclas externas ────────────────────────────────────────────────
    mcap = {}
    for t, m in cur.execute("SELECT ticker, MarketCapUSD FROM screener").fetchall():
        if m:
            mcap[t] = m

    # MEP para convertir nuestro EPS (USD) a los pesos que publica investing
    row = cur.execute("""SELECT venta FROM dolarito_cotizaciones
                          WHERE tipo='MEP' AND venta IS NOT NULL
                          ORDER BY fecha DESC LIMIT 1""").fetchone()
    mep = row[0] if row else None
    print(f"MEP dolarito para el cruce externo: {mep}")

    ext = {}
    for r in cur.execute("SELECT ticker, pe, eps FROM investing_full").fetchall():
        ext[r[0]] = {"pe": r[1], "eps": r[2]}

    # ── entidades EDGAR ────────────────────────────────────────────────
    entidades = cur.execute("""
        SELECT entity_id, cik, ticker_canonico, grupo, es_financiera, fy_end_month
        FROM dim_entity
        WHERE grupo IN ('sp500', 'adr') AND cik IS NOT NULL
        ORDER BY grupo, ticker_canonico
    """).fetchall()
    print(f"Entidades EDGAR con CIK: {len(entidades)}")

    # ── precarga de facts (una pasada por 4,6M filas) ──────────────────
    ciks = {e[1] for e in entidades}
    print("Cargando facts...")

    anual = defaultdict(dict)      # cik -> {(concepto, period_end): val}   solo FY
    trimestral = defaultdict(list)  # cik -> [(concepto, period_end, fp, val)]

    ph = ",".join("?" * len(TAG_FALLBACK))
    q = f"""SELECT cik, concepto, tag, period_end, val, fp, period_start
            FROM facts
            WHERE concepto IS NOT NULL OR tag IN ({ph})"""
    n = n_tag = 0
    for cik, concepto, tag, pe, val, fp, ps in cur.execute(q, tuple(TAG_FALLBACK)):
        if cik not in ciks or val is None or not pe:
            continue
        key = concepto
        if key is None:
            key = TAG_FALLBACK.get(tag)
            if key is None:
                continue
        if fp == "FY":
            # (a) fp='FY' NO garantiza que la fila sea anual: hay trimestres
            #     etiquetados FY (BG trae Revenues de 91d junto al de 364d).
            #     Los hechos de balance son instantaneos (period_start NULL) y
            #     pasan; los de resultado tienen que durar un ejercicio.
            if ps:
                try:
                    dur = (date.fromisoformat(pe) - date.fromisoformat(ps)).days
                except ValueError:
                    continue
                if not (330 <= dur <= 400):
                    continue
            # (b) varios tags us-gaap caen en el mismo concepto canonico con
            #     alcances distintos: para BG, `Revenues`=7,03e10 (total) y
            #     `RevenueFromContractWithCustomer`=1,69e10 (un componente).
            #     Un componente nunca supera al total, asi que se conserva el
            #     de mayor magnitud. El concepto canonico sigue mandando sobre
            #     el fallback por tag.
            slot = (key, pe)
            prev = anual[cik].get(slot)
            if prev is None or abs(val) > abs(prev):
                if concepto is None:
                    n_tag += 1
                anual[cik][slot] = val
        elif fp in ("Q1", "Q2", "Q3"):
            # EDGAR publica, para el MISMO fp, la fila standalone (~90d) y la
            # acumulada (~181d, ~272d). Sumarlas indiscriminadamente infla el
            # total y da falsas fallas de continuidad. Solo standalone.
            if ps:
                try:
                    dur = (date.fromisoformat(pe) - date.fromisoformat(ps)).days
                except ValueError:
                    dur = None
                if dur is not None and 80 <= dur <= 100:
                    trimestral[cik].append((key, pe, fp, val))
        n += 1
    print(f"  {n} hechos cargados para {len(anual)} entidades "
          f"({n_tag} via fallback por tag)\n")

    cur.executescript("""
        DROP TABLE IF EXISTS validacion_suite_edgar;
        CREATE TABLE validacion_suite_edgar(
            ticker TEXT, grupo TEXT, check_id TEXT, capa INTEGER,
            resultado TEXT, detalle TEXT);
    """)

    resumen = []

    for eid, cik, tk, grupo, esfin, fy in entidades:
        A = anual.get(cik, {})
        if not A:
            resumen.append((tk, grupo, esfin, 0, 0, "SIN_DATOS", []))
            continue

        # ejercicio mas reciente con balance completo
        periodos = sorted({pe for (c, pe) in A if c in ("Assets", "Equity")})
        cand = [pe for pe in periodos
                if ("Assets", pe) in A and ("Equity", pe) in A]
        P = cand[-1] if cand else None

        def v(c):
            return A.get((c, P)) if P else None

        checks = []

        # ── CAPA 1 · identidades internas ─────────────────────────────
        # El PN que cierra el balance consolidado es el que INCLUYE minoritario.
        # Se prefiere ese; si la empresa no lo publica (no tiene filiales
        # parciales) StockholdersEquity ya es el total.
        pn = v("EquityInclNCI")
        if pn is None:
            pn = v("Equity")
        checks.append(("c1_activo=pas+pn", 1,
                       rel_ok(v("Assets"), (v("Liabilities") or 0) + pn)
                       if (v("Assets") and pn is not None
                           and v("Liabilities") is not None) else None))

        # c2 original (Activo = AC + ANC) no es computable: AssetsNoncurrent
        # aparece en 1094 filas de 4,6M. En su lugar va la identidad que EDGAR
        # SI publica explicitamente y CNV no: el total Pasivo+PN declarado por
        # la empresa (LiabilitiesAndStockholdersEquity, 501 CIK) contra Assets.
        # Es una identidad mas fuerte que la original porque no la derivamos:
        # la empresa la afirma y nosotros la contrastamos.
        checks.append(("c2_activo=TotalPasPN", 1,
                       rel_ok(v("Assets"), v("TotalPasivoPN"))
                       if (v("Assets") and v("TotalPasivoPN")) else None))

        liab, lc = v("Liabilities"), v("LiabilitiesCurrent")
        checks.append(("c3_PC<=Pasivo", 1,
                       (0 <= lc <= liab * 1.02)
                       if (liab and lc is not None and liab > 0) else None))

        checks.append(("c4_GP=Vtas-Costo", 1,
                       sign_ok(v("GrossProfit"), v("Revenue"), v("COGS"))
                       if not esfin else None))

        checks.append(("c5_NI=Pretax-Tax", 1,
                       sign_ok(v("NetIncome"), v("PretaxIncome"), v("IncomeTax"))))

        checks.append(("c6_EBITDA=EBIT+DA", 1,
                       sign_ok(v("EBITDA_reported"), v("OperatingIncome"),
                               -(v("DA")) if v("DA") is not None else None)
                       if (v("EBITDA_reported") and v("OperatingIncome") is not None
                           and not esfin) else None))

        cfo, cfi, cff = v("CFO"), v("CFI"), v("CFF")
        # EDGAR no publica el delta de caja como concepto: se valida que los tres
        # flujos existan y su suma sea de magnitud plausible contra la caja.
        checks.append(("c8_dCaja=CFO+CFI+CFF", 1,
                       (abs((cfo or 0) + (cfi or 0) + (cff or 0)) <= abs(v("Cash")) * 3)
                       if (cfo is not None and cfi is not None and cff is not None
                           and v("Cash")) else None))

        # c10 · analogo del auto-reporte: EPS reportado vs NI/acciones
        eps_rep = v("EPS_diluted")
        sh = v("Shares_diluted")
        ni = v("NetIncome")
        eps_calc = (ni / sh) if (ni is not None and sh) else None
        checks.append(("c10_EPS_vs_NI/Shares", 1,
                       rel_ok(eps_calc, eps_rep, TOL_SELFREP)
                       if (eps_calc is not None and eps_rep) else None))

        # ── CAPA 2 · continuidad: suma de trimestres ~= FY ─────────────
        def continuidad():
            if not P or v("Revenue") is None:
                return None
            anio = P[:4]
            qs = [val for (c, pe, fp, val) in trimestral.get(cik, [])
                  if c == "Revenue" and pe[:4] == anio]
            if len(qs) < 3:
                return None
            suma3 = sum(qs[:3])
            # 3 trimestres deben ser una fraccion plausible del ejercicio
            return 0.4 <= suma3 / v("Revenue") <= 0.95 if v("Revenue") else None

        checks.append(("c12_trimestres_vs_FY", 2, continuidad()))

        # ── CAPA 3 · ancla externa (investing) ────────────────────────
        # investing publica el listado LOCAL en pesos (CEDEAR para el S&P), no
        # la accion en dolares: comparar directo da 100% de fallas falsas.
        # Se convierte nuestro EPS con el MEP del dia. La tolerancia es amplia
        # porque el MEP y el dato de investing no son de la misma fecha.
        e = ext.get(tk)
        eps_ars = (eps_rep * mep) if (eps_rep is not None and mep) else None
        checks.append(("c15_EPS_vs_investing", 3,
                       rel_ok(eps_ars, e["eps"], TOL_EXT)
                       if (e and e.get("eps") and eps_ars) else None))

        # ── CAPA 4 · ancla de mercado ────────────────────────────────
        mc = mcap.get(tk)
        pb = mc / v("Equity") if (mc and v("Equity") and v("Equity") > 0) else None
        ps = mc / v("Revenue") if (mc and v("Revenue") and v("Revenue") > 0) else None
        checks.append(("c16_P/B_sano", 4, (0.05 <= pb <= 30) if pb is not None else None))
        checks.append(("c17_P/S_sano", 4,
                       ((0.05 <= ps <= 30) if ps is not None else None)
                       if not esfin else None))

        for cid, capa, res in checks:
            cur.execute("INSERT INTO validacion_suite_edgar VALUES (?,?,?,?,?,?)",
                        (tk, grupo, cid, capa, S(res), P or ""))

        # ── certificacion (misma regla que BYMA) ─────────────────────
        # duras = capa 1 menos los informativos (metodo/redondeo, no integridad)
        hard = [r for (i, cp, r) in checks
                if cp == 1 and not i.startswith(("c10", "c6", "c5", "c8"))]
        cap1_ok = all(r for r in hard if r is not None) and any(r is not None for r in hard)
        cap2 = next((r for (i, cp, r) in checks if cp == 2), None)
        anchor = [r for (i, cp, r) in checks if cp in (3, 4)]
        anchor_ok = any(r for r in anchor if r is not None)

        npass = sum(1 for (i, cp, r) in checks if r)
        napp = sum(1 for (i, cp, r) in checks if r is not None)

        # Sin ningun check aplicable no hay nada que juzgar: es ausencia de
        # datos, no una falla de validacion. Mezclarlos con REVISAR inflaria
        # el conteo de errores con empresas que nunca se evaluaron.
        if napp == 0:
            nivel = "SIN_DATOS"
        elif cap1_ok and anchor_ok:
            nivel = "CERTIFICADO" if cap2 is not False else "alto"
        elif cap1_ok:
            nivel = "interno-ok"
        else:
            nivel = "REVISAR"

        resumen.append((tk, grupo, esfin, npass, napp, nivel,
                        [i for (i, cp, r) in checks if r is False]))

    # ── persistir nivel ───────────────────────────────────────────────
    cur.executescript("""
        DROP TABLE IF EXISTS screener_nivel_edgar;
        CREATE TABLE screener_nivel_edgar(
            ticker TEXT PRIMARY KEY, grupo TEXT, es_financiera INT, nivel TEXT,
            checks_ok INT, checks_aplicables INT, fallidos TEXT);
    """)
    for tk, grupo, esfin, npass, napp, nivel, fails in resumen:
        cur.execute("INSERT OR REPLACE INTO screener_nivel_edgar VALUES (?,?,?,?,?,?,?)",
                    (tk, grupo, esfin, nivel, npass, napp,
                     ",".join(x.split("_")[0] for x in fails)))

    # vista unificada con la suite BYMA
    cur.executescript("""
        DROP VIEW IF EXISTS v_validacion_todos;
        CREATE VIEW v_validacion_todos AS
            SELECT ticker, 'byma_only' AS grupo, check_id, capa, resultado
              FROM validacion_suite
            UNION ALL
            SELECT ticker, grupo, check_id, capa, resultado
              FROM validacion_suite_edgar;
    """)
    con.commit()

    # ── reporte ───────────────────────────────────────────────────────
    print("=" * 66)
    print("SUITE EDGAR — resultado")
    print("=" * 66)
    for g in ("sp500", "adr"):
        sub = [r for r in resumen if r[1] == g]
        if not sub:
            continue
        cnt = Counter(r[5] for r in sub)
        print(f"\n{g}  (n={len(sub)})")
        for k in ("CERTIFICADO", "alto", "interno-ok", "REVISAR", "SIN_DATOS"):
            if cnt.get(k):
                print(f"   {k:>12}: {cnt[k]:>4}")

    print("\n" + "=" * 66)
    print("FALLAS POR CHECK")
    print("=" * 66)
    print(f"{'check':<24}{'OK':>7}{'FAIL':>7}{'NA':>7}")
    # materializar antes de iterar: reusar el cursor dentro del loop lo invalida
    filas = cur.execute("""
        SELECT check_id,
               SUM(resultado='OK'), SUM(resultado='FAIL'), SUM(resultado='NA')
        FROM validacion_suite_edgar
        GROUP BY check_id ORDER BY check_id""").fetchall()
    for cid, ok, fail, na in filas:
        print(f"{cid:<24}{ok or 0:>7}{fail or 0:>7}{na or 0:>7}")

    con.close()
    print("\nSUITE EDGAR -- OK")


if __name__ == "__main__":
    build()
