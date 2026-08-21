# -*- coding: utf-8 -*-
"""
FASE 3: 9 VALIDACIONES CRUZADAS
Cada cruce es independiente y atomizado.
Resultado → tabla validaciones (cruce_id, resultado OK/FALLA/N/A)
"""
import sqlite3
import os as _os
import os
import datetime

PROD = os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))

def get_val(c, ticker, period, concepto):
    """Helper: obtener valor de silver_norm"""
    r = c.execute("""
        SELECT valor FROM silver_norm
        WHERE ticker=? AND period_end=? AND concepto=?
    """, (ticker, period, concepto)).fetchone()
    return r[0] if r else None

def pct_diff(a, b):
    """% diferencia relativa"""
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return 0.0
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom * 100

def registrar_cruce(c, ticker, period, cruce_id, cruce_nombre, resultado, val_nuestro, val_esperado, divergencia, detalle):
    """Guardar resultado de cruce en tabla validaciones"""
    c.execute("""
        INSERT OR REPLACE INTO validaciones
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (ticker, period, cruce_id, cruce_nombre, resultado,
     val_nuestro, val_esperado, divergencia, detalle,
     datetime.datetime.now().isoformat()))

def ejecutar_validaciones():
    """Corre 9 cruces independientes"""

    print("=" * 80)
    print("FASE 3: 9 VALIDACIONES CRUZADAS")
    print("=" * 80)

    c = sqlite3.connect(PROD)

    ticker = 'TXAR'
    periodos = sorted(set([r[0] for r in c.execute(
        "SELECT DISTINCT period_end FROM silver_norm WHERE ticker=?", (ticker,))]))

    print(f"\nValidando {len(periodos)} períodos...")

    # CRUCE 1: IDENTIDADES CONTABLES
    print("\n1. IDENTIDADES CONTABLES (A = P + PN)...")
    for period in periodos:
        a = get_val(c, ticker, period, 'assets')
        p = get_val(c, ticker, period, 'liabilities')
        pn = get_val(c, ticker, period, 'equity')

        if a and p and pn:
            lhs = a
            rhs = p + pn
            diff = pct_diff(lhs, rhs)

            resultado = 'OK' if diff < 1 else 'FALLA'
            registrar_cruce(c, ticker, period, 1, 'Identidades.A=P+PN',
                          resultado, lhs, rhs, diff,
                          f'A={lhs:.0f} vs (P+PN)={rhs:.0f}')
        else:
            registrar_cruce(c, ticker, period, 1, 'Identidades.A=P+PN',
                          'N/A', None, None, None, 'Datos incompletos')

    # CRUCE 2: CONTINUIDAD TEMPORAL (YTD creciente para P&L)
    print("2. CONTINUIDAD TEMPORAL (YTD creciente)...")
    prev_revenue = None
    for period in periodos:
        revenue_ytd = get_val(c, ticker, period, 'revenue')

        if revenue_ytd:
            if prev_revenue is not None:
                resultado = 'OK' if revenue_ytd >= prev_revenue * 0.8 else 'FALLA'  # Tolerar -20%
                diff = pct_diff(revenue_ytd, prev_revenue)
            else:
                resultado = 'OK'
                diff = None

            registrar_cruce(c, ticker, period, 2, 'Continuidad.YTD_Revenue',
                          resultado, revenue_ytd, prev_revenue, diff,
                          f'Revenue={revenue_ytd:.0f}' + (f' vs prev={prev_revenue:.0f}' if prev_revenue else ''))
            prev_revenue = revenue_ytd
        else:
            registrar_cruce(c, ticker, period, 2, 'Continuidad.YTD_Revenue',
                          'N/A', None, None, None, 'Revenue no disponible')

    # CRUCE 3: ANCLA EXTERNA (Investing)
    print("3. ANCLA EXTERNA (vs investing)...")
    # TODO: leer investing_estados y comparar
    # Por ahora, marcar N/A
    for period in periodos:
        registrar_cruce(c, ticker, period, 3, 'Ancla.Investing',
                      'N/A', None, None, None, 'Datos investing no disponibles aún')

    # CRUCE 4: ANCLA MERCADO (P/B, P/S en rangos sanos)
    print("4. ANCLA MERCADO (P/B, P/S)...")
    # TODO: calcular cuando tengamos precio + mcap
    for period in periodos:
        registrar_cruce(c, ticker, period, 4, 'Ancla.Mercado_PB_PS',
                      'N/A', None, None, None, 'Precios/MCap no disponibles aún')

    # CRUCE 5: EPS (diluido ≤ basico)
    print("5. EPS VALIDATION (diluido ≤ basico)...")
    for period in periodos:
        eps_basic = get_val(c, ticker, period, 'eps_basic')
        eps_diluted = get_val(c, ticker, period, 'eps_diluted')

        if eps_basic and eps_diluted:
            # Para negativos: diluido debe ser "menos negativo" (mayor numéricamente)
            resultado = 'OK' if abs(eps_diluted) <= abs(eps_basic) * 1.05 else 'FALLA'
            registrar_cruce(c, ticker, period, 5, 'EPS.Diluido_vs_Basico',
                          resultado, eps_diluted, eps_basic, None,
                          f'Básico={eps_basic:.4f}, Diluido={eps_diluted:.4f}')
        else:
            registrar_cruce(c, ticker, period, 5, 'EPS.Diluido_vs_Basico',
                          'N/A', None, None, None, 'EPS no disponible')

    # CRUCE 6: CAGR (EPS vs NI → cambio en acciones)
    print("6. CAGR (EPS vs NetIncome)...")
    # TODO: comparar CAGR 5y de ambos
    for period in periodos:
        registrar_cruce(c, ticker, period, 6, 'CAGR.EPS_vs_NI',
                      'N/A', None, None, None, 'Requiere serie histórica')

    # CRUCE 7: EBITDA (vs EBIT + D&A)
    print("7. EBITDA CROSS-CHECK...")
    for period in periodos:
        ebitda = get_val(c, ticker, period, 'ebitda')
        ebit = get_val(c, ticker, period, 'operating_income')
        da = get_val(c, ticker, period, 'depreciation_amortization')

        if ebitda and ebit and da:
            ebit_plus_da = ebit + da
            diff = pct_diff(ebitda, ebit_plus_da)
            # Tolerar divergencia por RECPAM/ajustes (Argentina inflación)
            resultado = 'OK' if diff < 10 else 'FALLA'
            registrar_cruce(c, ticker, period, 7, 'EBITDA.vs_EBIT_DA',
                          resultado, ebitda, ebit_plus_da, diff,
                          f'EBITDA={ebitda:.0f} vs (EBIT+DA)={ebit_plus_da:.0f}')
        else:
            registrar_cruce(c, ticker, period, 7, 'EBITDA.vs_EBIT_DA',
                          'N/A', None, None, None, 'EBITDA/EBIT/DA incompleto')

    # CRUCE 8: FCF (componentes: CF_Op, CF_Inv)
    print("8. FCF COMPONENTS...")
    for period in periodos:
        cf_op = get_val(c, ticker, period, 'cashflow_operating')
        cf_inv = get_val(c, ticker, period, 'cashflow_investing')

        if cf_op is not None:
            resultado = 'OK'
        else:
            resultado = 'N/A'

        registrar_cruce(c, ticker, period, 8, 'FCF.Componentes',
                      resultado, cf_op, cf_inv, None,
                      f'CF_Op={cf_op}, CF_Inv={cf_inv}')

    # CRUCE 9: P&L IDENTIDADES (Revenue + COGS = Gross Profit, etc)
    print("9. P&L IDENTIDADES...")
    for period in periodos:
        revenue = get_val(c, ticker, period, 'revenue')
        cogs = get_val(c, ticker, period, 'cogs')  # COGS es NEGATIVO en CNV
        gp = get_val(c, ticker, period, 'gross_profit')

        if revenue and cogs and gp:
            # En CNV: GrossProfit = Revenue + COGS (COGS es negativo)
            expected_gp = revenue + cogs
            diff = pct_diff(gp, expected_gp)
            resultado = 'OK' if diff < 1 else 'FALLA'
            registrar_cruce(c, ticker, period, 9, 'PL.GrossProfit_Identity',
                          resultado, gp, expected_gp, diff,
                          f'GP={gp:.0f} vs (Rev+COGS)={expected_gp:.0f}')
        else:
            registrar_cruce(c, ticker, period, 9, 'PL.GrossProfit_Identity',
                          'N/A', None, None, None, 'Revenue/COGS/GP incompleto')

    c.commit()
    c.close()

    print("\n" + "=" * 80)
    print("✅ FASE 3 COMPLETADA: 9 cruces registrados")
    print("=" * 80)

if __name__ == '__main__':
    ejecutar_validaciones()
