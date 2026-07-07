# -*- coding: utf-8 -*-
"""
FASE 2 -- Ratios fundamentales CNV
===================================
Lee cnv_estados_norm + cnv_dividendos y calcula los 7+2 ratios
fundamentales del ultimo periodo disponible por entidad.

Tabla salida: ratios_cnv
  - 7 fundamentales (ROE, ROA, MargenNeto, DeudaEBITDA, EPS, FCFYield, Payout)
  - CNV_* precargados como cross-check
  - CAGR_EPS_5y (flageado vintage_mixto)
  - provenance: que conceptos se usaron y de que fuente
"""
from __future__ import annotations
import sqlite3, math
from pathlib import Path
from collections import defaultdict

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"


def get_valor_por_cuit(cur, cuit, concepto, period_end=None):
    """Obtener el valor mas reciente de un concepto para un CUIT."""
    if period_end:
        cur.execute("""
            SELECT valor FROM cnv_estados_norm
            WHERE cuit=? AND concepto=? AND period_end=?
            ORDER BY fecha_reexpresion DESC
            LIMIT 1
        """, (cuit, concepto, period_end))
    else:
        cur.execute("""
            SELECT valor FROM cnv_estados_norm
            WHERE cuit=? AND concepto=?
            ORDER BY period_end DESC, fecha_reexpresion DESC
            LIMIT 1
        """, (cuit, concepto))
    r = cur.fetchone()
    return r[0] if r else None


def get_valor_historico(cur, cuit, concepto, years=5):
    """Obtener valores historicos ordenados por period_end descendente."""
    cur.execute("""
        SELECT period_end, valor FROM cnv_estados_norm
        WHERE cuit=? AND concepto=? AND valor IS NOT NULL
        ORDER BY period_end DESC
    """, (cuit, concepto))
    return cur.fetchall()


def calcular_cagr(valores_hist, years=5):
    """Calcular CAGR usando los valores de hace ~5 anos y el actual."""
    if len(valores_hist) < 2:
        return None, "insuficientes_periodos"
    # Tomar el mas reciente (anio 0) y buscar el de ~5 anos atras
    actual = valores_hist[0][1]
    target_date = None
    try:
        anio_actual = int(valores_hist[0][0][:4])
        anio_target = anio_actual - years
        for pe, val in valores_hist:
            if int(pe[:4]) == anio_target:
                target_date = pe
                pasado = val
                break
        if target_date is None:
            # Si no hay exactamente 5 anos, tomar el mas lejano
            pasado = valores_hist[-1][1]
            target_date = valores_hist[-1][0]
    except (ValueError, IndexError):
        return None, "error_fecha"

    if not pasado or not actual or pasado == 0:
        return None, "division_por_cero"
    ratio = actual / abs(pasado)
    if ratio < 0:
        return None, "ratio_negativo"
    cagr = ratio ** (1.0 / years) - 1
    if isinstance(cagr, complex):
        return None, "complejo"
    return cagr, f"vintage_mixto({target_date}..{valores_hist[0][0]})"


def build():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    print("FASE 2 -- Ratios fundamentales CNV")
    print("=" * 60)

    # Obtener todas las entidades con sus periodos disponibles
    # y elegir el ultimo periodo NO corrupto (guardia anti-parseo).
    # Criterio: rechazar periodos donde Assets < max_historico/10
    # (un drop >10x del maximo historico siempre es anomalo --
    #  ningun going concern pierde >90% de sus activos).
    # NOTA: no usar mediana; cuando los periodos corruptos (>6 meses)
    # superan en numero a los buenos, la mediana cae en el rango corrupto
    # y no detecta el problema. MAX es robusto porque requiere al menos
    # un periodo bueno en toda la historia.
    cur.execute("""
        SELECT m.cuit, m.ticker, n.period_end, n.valor as assets
        FROM mapa_entidades m
        JOIN cnv_estados_norm n ON n.cuit = m.cuit AND n.concepto='Assets'
        WHERE m.es_primario = 1
        ORDER BY m.ticker, n.period_end DESC
    """)
    rows = cur.fetchall()
    rechazados = 0

    def ultimo_valido(periodos):
        nonlocal rechazados
        assets_vals = [p[3] for p in periodos if p[3] is not None and p[3] > 0]
        if not assets_vals:
            return periodos[0][2]
        max_assets = max(assets_vals)
        umbral = max(max_assets / 10, 1.0)  # rechaza si cae >90% vs maximo historico
        for p in periodos:
            if p[3] is not None and p[3] >= umbral:
                return p[2]
            rechazados += 1
        return periodos[0][2]

    entidades = []
    if rows:
        current = None
        buf = []
        for cuit, ticker, pe, assets in rows:
            if cuit != current:
                if current is not None:
                    ultimo = ultimo_valido(buf)
                    entidades.append((buf[0][0], buf[0][1], ultimo))
                current = cuit
                buf = []
            buf.append((cuit, ticker, pe, assets))
        if buf:
            ultimo = ultimo_valido(buf)
            entidades.append((buf[0][0], buf[0][1], ultimo))

    print(f"Entidades: {len(entidades)} ({rechazados} periodos rechazados por datos anomalos)")

    # Crear tabla ratios_cnv
    cur.execute("DROP TABLE IF EXISTS ratios_cnv")
    cur.execute("""
        CREATE TABLE ratios_cnv (
            cuit TEXT PRIMARY KEY,
            ticker TEXT,
            ultimo_periodo TEXT,
            -- 7 fundamentales
            ROE REAL,
            ROA REAL,
            MargenNeto REAL,
            DeudaEBITDA REAL,
            EPS REAL,
            FCFYield REAL,
            Payout REAL,
            -- CNV precargados (cross-check)
            CNV_roe REAL,
            CNV_roa REAL,
            CNV_margen_neto REAL,
            CNV_deuda_ebitda REAL,
            -- CAGR (flageado)
            CAGR_EPS_5y REAL,
            CAGR_flag TEXT,
            -- provenance
            provenance TEXT
        )
    """)

    stats = defaultdict(int)
    cagr_ok = 0
    cagr_flag = 0
    div_con_monto = 0

    for cuit, ticker, ultimo in entidades:
        prov = []

        # --- 1. ROE ---
        ni = get_valor_por_cuit(cur, cuit, "NetIncome", ultimo)
        eq = get_valor_por_cuit(cur, cuit, "Equity", ultimo)
        cnv_roe = get_valor_por_cuit(cur, cuit, "CNV_roe", ultimo)
        roe = (ni / eq) if (ni is not None and eq and eq != 0) else None
        prov.append(f"NetIncome={ni}, Equity={eq}")

        # --- 2. ROA ---
        assets = get_valor_por_cuit(cur, cuit, "Assets", ultimo)
        cnv_roa = get_valor_por_cuit(cur, cuit, "CNV_roa", ultimo)
        roa = (ni / assets) if (ni is not None and assets and assets != 0) else None
        prov.append(f"Assets={assets}")

        # --- 3. Margen Neto ---
        rev = get_valor_por_cuit(cur, cuit, "Revenue", ultimo)
        cnv_margen = get_valor_por_cuit(cur, cuit, "CNV_margen_neto", ultimo)
        margen = (ni / rev) if (ni is not None and rev and rev != 0) else None
        prov.append(f"Revenue={rev}")

        # --- 4. Deuda/EBITDA ---
        d_c = get_valor_por_cuit(cur, cuit, "DebtCurrent", ultimo)
        d_nc = get_valor_por_cuit(cur, cuit, "DebtNonCurrent", ultimo)
        ebitda = get_valor_por_cuit(cur, cuit, "EBITDA", ultimo)
        cnv_debt = get_valor_por_cuit(cur, cuit, "CNV_deuda_fin_ebitda", ultimo)
        deuda = (d_c or 0) + (d_nc or 0)
        de_ebitda = (deuda / ebitda) if (deuda and ebitda and ebitda != 0) else None
        prov.append(f"DebtC={d_c}, DebtNC={d_nc}, EBITDA={ebitda}")

        # --- 5. EPS ---
        eps = get_valor_por_cuit(cur, cuit, "EPS_basico", ultimo)
        prov.append(f"EPS_basico={eps}")

        # --- 6. FCF Yield (precisa market_cap de precios) ---
        # Buscar en tabla precios por ticker
        cur.execute("SELECT market_cap FROM precios WHERE ticker=? ORDER BY fecha DESC LIMIT 1", (ticker,))
        mc_row = cur.fetchone()
        mc = mc_row[0] if mc_row else None
        cf_op = get_valor_por_cuit(cur, cuit, "CF_Operativo", ultimo)
        cf_inv = get_valor_por_cuit(cur, cuit, "CF_Inversion", ultimo)
        fcf = None
        if cf_op is not None and cf_inv is not None:
            fcf_val = cf_op + cf_inv
            fcf = (fcf_val / mc) if (mc and mc != 0) else None
        elif cf_op is not None:
            fcf_val = cf_op
            fcf = (fcf_val / mc) if (mc and mc != 0) else None
        prov.append(f"CF_Op={cf_op}, CF_Inv={cf_inv}, MC={mc}")
        if fcf is not None:
            stats["con_fcf"] += 1

        # --- 7. Payout (dividendos / NetIncome) ---
        cur.execute("""
            SELECT por_accion FROM cnv_dividendos
            WHERE cuit=? AND por_accion IS NOT NULL AND por_accion != ''
            ORDER BY fecha_candidata DESC
            LIMIT 1
        """, (cuit,))
        div_row = cur.fetchone()
        div_total = None
        if div_row:
            try:
                div_val = float(div_row[0])
                div_con_monto += 1
                div_total = (div_val / eps) if (eps and eps != 0) else None
            except (ValueError, TypeError):
                pass
        prov.append(f"dividendo_por_accion={div_row[0] if div_row else None}")

        # --- 8. CAGR EPS 5y ---
        eps_hist = get_valor_historico(cur, cuit, "EPS_basico", 5)
        cagr, flag = calcular_cagr(eps_hist, 5)
        if cagr is not None:
            cagr_ok += 1
        if flag and "vintage_mixto" in flag:
            cagr_flag += 1
        prov.append(f"CAGR_flag={flag}")

        # Stats
        for name, val in [("ROE", roe), ("ROA", roa), ("Margen", margen),
                          ("D/E", de_ebitda), ("EPS", eps), ("FCF", fcf),
                          ("Payout", div_total)]:
            if val is not None:
                stats[f"con_{name}"] += 1
            else:
                stats[f"sin_{name}"] += 1

        provenance = "; ".join(prov)

        cur.execute("""
            INSERT OR REPLACE INTO ratios_cnv
            VALUES (?,?,?, ?,?,?,?,?,?,?, ?,?,?,?, ?,?, ?)
        """, (cuit, ticker, ultimo,
              roe, roa, margen, de_ebitda, eps, fcf, div_total,
              cnv_roe, cnv_roa, cnv_margen, cnv_debt,
              cagr, flag,
              provenance))

    con.commit()

    # --- Reporte ---
    n = len(entidades)
    print(f"\n  Tabla ratios_cnv: {n} filas")
    print(f"\n  Cobertura (ultimo periodo):")
    for name in ["ROE", "ROA", "Margen", "D/E", "EPS", "FCF", "Payout"]:
        ok = stats.get(f"con_{name}", 0)
        print(f"    {name:<12} {ok:>3}/{n} ({round(100*ok/n)}%)")

    print(f"\n  CAGR EPS 5y: {cagr_ok} calculados, {cagr_flag} con flag vintage_mixto")
    print(f"  Dividendos con monto: {div_con_monto}")

    # Cross-check CNV vs calculated
    print(f"\n  Cross-check CNV_* vs calculados:")
    cur.execute("""
        SELECT ticker, ROE, CNV_roe, ROA, CNV_roa, MargenNeto, CNV_margen_neto
        FROM ratios_cnv
        WHERE ROE IS NOT NULL AND CNV_roe IS NOT NULL
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"    {r[0]:20s} ROE calc={r[1]:.4f} CNV={r[2]:.4f}  ROA calc={r[3]:.4f} CNV={r[4]:.4f}")

    con.close()
    print("\nFASE 2 -- OK")


if __name__ == "__main__":
    build()
