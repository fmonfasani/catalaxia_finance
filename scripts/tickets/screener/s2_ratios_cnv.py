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
import sqlite3, math, csv
from pathlib import Path
from collections import defaultdict

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")


# ---------------------------------------------------------------------------
# REGLA DE PERIMETRO CONTABLE
# ---------------------------------------------------------------------------
# Una empresa presenta ante la CNV estados INDIVIDUAL y CONSOLIDADO, y ambos
# alimentan cnv_estados_norm. Combinar conceptos de los dos en un mismo ratio
# produce numeros sin significado: en una holding, dividir el NetIncome
# individual (resultado por participacion) entre el Revenue consolidado (ventas
# del grupo) no es un margen.
#
# La regla: por cada (cuit, period_end) se elige UN perimetro y se usan SOLO sus
# conceptos. Se prefiere el que contenga `Revenue`, porque es el que refleja la
# actividad economica real -- en holdings eso da consolidado, que es el correcto.
# Los conceptos que falten quedan sin dato; NO se rellenan con el otro perimetro.
#
# Se descartaron dos reglas antes de esta, y las dos parecian razonables:
#   - "consolidado siempre": destruye el 73% de los conceptos en casos mixtos.
#   - "el mas completo":     en una holding elige el individual, que es justo el
#                            perimetro sin operaciones.
# Ver docs/07-homologacion-cnv.md seccion 7.3.
_PERIM_CACHE = {}


def perimetro_preferido(cur, cuit, period_end):
    """Perimetro a usar para ese cuit+periodo. None si ninguno esta declarado."""
    k = (cuit, period_end)
    if k in _PERIM_CACHE:
        return _PERIM_CACHE[k]
    cur.execute("""
        SELECT tipo_balance,
               SUM(CASE WHEN concepto='Revenue' AND valor IS NOT NULL THEN 1 ELSE 0 END) tiene_rev,
               COUNT(DISTINCT concepto) n
        FROM cnv_estados_norm
        WHERE cuit=? AND period_end=? AND tipo_balance!=''
        GROUP BY tipo_balance
    """, (cuit, period_end))
    filas = cur.fetchall()
    if not filas:
        elegido = None
    elif len(filas) == 1:
        elegido = filas[0][0]
    else:
        # 1o el que tenga Revenue; a igualdad, el mas completo
        filas.sort(key=lambda f: (f[1], f[2]), reverse=True)
        elegido = filas[0][0]
    _PERIM_CACHE[k] = elegido
    return elegido


def _filtro_perim(cur, cuit, period_end):
    """Devuelve (sql_extra, params) para restringir al perimetro elegido."""
    p = perimetro_preferido(cur, cuit, period_end)
    return (" AND tipo_balance=? ", [p]) if p else ("", [])


def get_valor_por_cuit(cur, cuit, concepto, period_end=None):
    """Obtener el valor mas reciente de un concepto para un CUIT.

    Restringido al perimetro elegido para ese periodo (ver perimetro_preferido).
    """
    if period_end:
        extra, pars = _filtro_perim(cur, cuit, period_end)
        cur.execute("""
            SELECT valor FROM cnv_estados_norm
            WHERE cuit=? AND concepto=? AND period_end=?""" + extra + """
            ORDER BY fecha_reexpresion DESC
            LIMIT 1
        """, [cuit, concepto, period_end] + pars)
    else:
        # sin periodo fijo: se resuelve el mas reciente y se aplica su perimetro
        cur.execute("""
            SELECT period_end FROM cnv_estados_norm
            WHERE cuit=? AND concepto=? AND valor IS NOT NULL
            ORDER BY period_end DESC LIMIT 1
        """, (cuit, concepto))
        r = cur.fetchone()
        if not r:
            return None
        return get_valor_por_cuit(cur, cuit, concepto, r[0])
    r = cur.fetchone()
    return r[0] if r else None


def get_valor_historico(cur, cuit, concepto, years=5):
    """Valores historicos por period_end descendente, coherentes por perimetro.

    El perimetro se resuelve por periodo: una serie puede cambiar de perimetro a
    lo largo del tiempo, y eso es aceptable mientras cada punto sea coherente
    consigo mismo. Lo inaceptable es mezclarlos dentro del mismo periodo.
    """
    cur.execute("""
        SELECT DISTINCT period_end FROM cnv_estados_norm
        WHERE cuit=? AND concepto=? AND valor IS NOT NULL
        ORDER BY period_end DESC
    """, (cuit, concepto))
    periodos = [r[0] for r in cur.fetchall()]
    out = []
    for pe in periodos:
        v = get_valor_por_cuit(cur, cuit, concepto, pe)
        if v is not None:
            out.append((pe, v))
    return out


def cargar_ipc():
    """Cargar IPC Nacional desde data/ipc_nacional.csv.
    
    Retorna dict {YYYY-MM: coef_deflacion_a_ultimo} o None si no existe.
    Cada valor nominal * coef = pesos constantes del ultimo mes del IPC.
    """
    ipc_path = ROOT / "data" / "ipc_nacional.csv"
    if not ipc_path.exists():
        return None
    ipc = {}
    with open(ipc_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fecha = r["fecha"].strip()
            ipc[fecha] = float(r["coef_deflacion_a_ultimo"])
    return ipc


def deflactar(valor, period_end, ipc):
    """Convertir valor nominal a pesos constantes del ultimo mes IPC."""
    if ipc is None or valor is None:
        return valor
    coef = ipc.get(period_end[:7])
    return valor * coef if coef else valor


def calcular_cagr(valores_hist, ipc=None, years=5):
    """Calcular CAGR real (deflactado por IPC) o nominal.
    
    Si ipc dict esta presente, deflacta cada valor por su periodo
    antes de calcular el CAGR. Toda la serie queda en pesos constantes
    del ultimo mes del IPC → CAGR real.
    
    Retorna (cagr, flag). flag = 'vintage_mixto' solo cuando usa fechas
    aproximadas (no encuentra alineacion exacta).
    """
    if len(valores_hist) < 2:
        return None, "insuficientes_periodos"
    
    # Deflactar el valor actual si hay IPC
    actual_raw = valores_hist[0][1]
    actual = deflactar(actual_raw, valores_hist[0][0], ipc)
    
    target_date = None
    exacto = True
    try:
        anio_actual = int(valores_hist[0][0][:4])
        anio_target = anio_actual - years
        mes_actual = int(valores_hist[0][0][5:7])
        for pe, val in valores_hist:
            if int(pe[:4]) == anio_target:
                target_date = pe
                pasado = deflactar(val, pe, ipc)
                # Verificar si el mes tambien alinea
                if int(pe[5:7]) != mes_actual:
                    exacto = False
                break
        if target_date is None:
            # Fallback: no hay periodo en el anio exacto, tomar el mas lejano
            pasado = deflactar(valores_hist[-1][1], valores_hist[-1][0], ipc)
            target_date = valores_hist[-1][0]
            exacto = False
    except (ValueError, IndexError):
        return None, "error_fecha"

    if not pasado or not actual or pasado == 0:
        return None, "division_por_cero"
    ratio = actual / abs(pasado)
    if ratio < 0:
        return None, "ratio_negativo"

    # Si no es exacto, ajustar years al差距 real
    if not exacto and target_date:
        try:
            d1 = int(valores_hist[0][0][:4]) * 12 + int(valores_hist[0][0][5:7])
            d0 = int(target_date[:4]) * 12 + int(target_date[5:7])
            years_real = (d1 - d0) / 12.0
        except (ValueError, IndexError):
            years_real = years
    else:
        years_real = years

    if years_real <= 0:
        return None, "span_cero"

    cagr = ratio ** (1.0 / years_real) - 1
    if isinstance(cagr, complex):
        return None, "complejo"

    if exacto:
        return cagr, ""
    else:
        return cagr, f"vintage_mixto({target_date}..{valores_hist[0][0]})"


def build():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
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

    # Cargar IPC para deflactar CAGR
    ipc = cargar_ipc()
    if ipc:
        print(f"IPC cargado: {len(ipc)} meses, deflactando CAGR a constantes")
    else:
        print("IPC no encontrado — CAGR nominal con fallback vintage_mixto")

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
        # Usar monto_candidato (total dividend amount) de cnv_dividendos v2.
        # Ventana de 12 meses desde ultimo (fiscal year end) para alinear
        # correctamente los dividendos con el ejercicio fiscal:
        #   suma_div = pagos en [ultimo - 12m, ultimo]
        #   payout = suma_div / NI del mismo ejercicio
        cur.execute("""
            SELECT fecha_candidata, CAST(monto_candidato AS REAL)
            FROM cnv_dividendos
            WHERE cuit=? AND monto_candidato IS NOT NULL AND monto_candidato != ''
              AND CAST(monto_candidato AS REAL) > 0
            ORDER BY fecha_candidata DESC
        """, (cuit,))
        div_rows = cur.fetchall()
        div_total = None
        suma_div = 0.0
        if div_rows and ni and ni != 0:
            try:
                anio_ultimo = int(ultimo[:4])
                mes_ultimo = int(ultimo[5:7])
                dia_ultimo = int(ultimo[8:10])
                anio_inicio = anio_ultimo - 1
                window_start = f"{anio_inicio}-{mes_ultimo:02d}-{dia_ultimo:02d}"
            except (ValueError, IndexError, TypeError):
                window_start = ""
            for f, m in div_rows:
                if f and f >= window_start and f <= ultimo:
                    suma_div += m
            if suma_div > 0:
                payout_candidate = suma_div / abs(ni)
                if 0 < payout_candidate <= 2:
                    div_total = payout_candidate
                    div_con_monto += 1
        prov.append(f"dividendos_total={suma_div:.0f}" if div_rows and suma_div else "dividendos=N/A")

        # --- 8. CAGR EPS 5y ---
        eps_hist = get_valor_historico(cur, cuit, "EPS_basico", 5)
        cagr, flag = calcular_cagr(eps_hist, ipc, 5)
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
