"""
E4 — b4_mercado: capa MARKET DATA separada de fundamentals.

Fuentes (snapshot):
  screener.grupo='byma_only' -> Precio ARS + MEP pareado (s3_precios v2)
  precios.currency='USD'     -> ADR argentinos con precio nativo USD
  dolarito_cotizaciones      -> MEP mas fresco (para estimacion actual, flag mezcla)

Reglas:
  - precio_usd primario = temporalmente consistente (MEP misma fecha que el precio)
  - estimado con MEP actual se guarda aparte con mezcla_temporal=1
  - dif_max/min_52w SE RECALCULAN desde niveles y se comparan contra los guardados
  - staleness: FRESCO <=7d, VIEJO 8-60d, STALE >60d (peor entre precio y MEP)
"""
import os
import sqlite3
from datetime import datetime, date

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
SNAP = sorted([s for s in glob_snapshot()] if False else [])  # placeholder evitado abajo

def glob_snapshot():
    import glob
    return [s for s in glob.glob(os.path.join(BASE, 'data', 'backups', 'snapshot_byma_2*.db'))
            if '_baseline_' not in os.path.basename(s)]

SNAPS = glob_snapshot()
SNAP = SNAPS[-1]
PIPE = os.path.join(BASE, 'data', 'byma_pipeline.db')
HOY = date(2026, 8, 22)
print(f'snapshot: {os.path.basename(SNAP)}')

src = sqlite3.connect(SNAP); sc = src.cursor()
dst = sqlite3.connect(PIPE); dc = dst.cursor()

dc.execute("DROP TABLE IF EXISTS mercado_byma")
dc.execute("""CREATE TABLE mercado_byma (
    cuit TEXT PRIMARY KEY, ticker TEXT, grupo TEXT,
    precio_ars REAL, precio_ars_fecha TEXT,
    mep_pareado REAL, mep_pareado_fecha TEXT,
    precio_usd REAL, metodo_usd TEXT, mezcla_temporal INTEGER DEFAULT 0,
    precio_usd_estimado_hoy REAL, mep_actual REAL, mep_actual_fecha TEXT,
    max52w_ars REAL, min52w_ars REAL,
    dif_max_52w_pct REAL, dif_min_52w_pct REAL,
    dif_check_ok INTEGER, dif_check_detalle TEXT,
    market_cap_usd REAL, pct_ruedas_operadas REAL, guard_motivo TEXT,
    staleness_dias INTEGER, staleness_estado TEXT,
    fuente TEXT, built_at TEXT)""")

mep_act = sc.execute("""SELECT fecha, venta FROM dolarito_cotizaciones
                        WHERE tipo='MEP' ORDER BY ts_ms DESC LIMIT 1""").fetchone()
print(f'MEP actual: {mep_act[0]} = {mep_act[1]}')

# fecha del precio ARS por ticker (tabla precios, moneda ARS)
fechas_precios = {}
for tk, fe in sc.execute("""SELECT DISTINCT e.ticker_ppal, MAX(p.fecha)
                            FROM precios p JOIN empresas e ON e.cik=p.cik
                            WHERE p.currency='ARS' AND e.grupo='byma_yf'
                            GROUP BY e.ticker_ppal"""):
    if fe:
        fechas_precios[tk] = fe[:10]

def staleness(d_iso):
    if not d_iso:
        return None, 'SIN_FECHA'
    try:
        d = date.fromisoformat(d_iso[:10])
    except ValueError:
        return None, 'FECHA_INVALIDA'
    dias = (HOY - d).days
    est = 'FRESCO' if dias <= 7 else ('VIEJO' if dias <= 60 else 'STALE')
    return dias, est

now = datetime.now().isoformat()
rows_out = []
n_check_fail = 0

for r in sc.execute("""SELECT s.cuit, s.ticker, s.Precio, s.MarketCapUSD,
        s.max_52w_ars_yfinance, s.min_52w_ars_yfinance, s.dif_max_52w_pct,
        s.dif_min_52w_pct, s.precio_usd_calc_mep_dolarito, s.valor_mep_dolarito,
        s.fecha_mep_dolarito, s.pct_ruedas_operadas, s.guard_motivo
        FROM screener s WHERE s.grupo='byma_only'""").fetchall():
    (cuit, tk, precio, mcapusd, mx, mn, difmx, difmn,
     pusd, mep, mep_f, ruedas, guard) = r
    p_fecha = fechas_precios.get(tk)
    # recalcular diferencias desde niveles (validacion independiente)
    # OJO VERIFICADO: columnas dif_*_pct del screener estan en PUNTOS PORCENTUALES
    det = ''
    okflag = 1
    dmx_c = dmn_c = None
    if precio and mx:
        dmx_c = round((precio / mx - 1) * 100, 6)
        if difmx is not None and abs(dmx_c - difmx) > 0.05:
            okflag = 0; det += f'dif_max stored={difmx:.4f} calc={dmx_c:.4f}; '
    if precio and mn:
        dmn_c = round((precio / mn - 1) * 100, 6)
        if difmn is not None and abs(dmn_c - difmn) > 0.05:
            okflag = 0; det += f'dif_min stored={difmn:.4f} calc={dmn_c:.4f}; '
    if not okflag:
        n_check_fail += 1
    d1, e1 = staleness(p_fecha or mep_f)
    d2, e2 = staleness(mep_f)
    orden = {'SIN_FECHA': 0, 'FRESCO': 1, 'VIEJO': 2, 'STALE': 3, 'FECHA_INVALIDA': 4}
    peor = max(e1, e2, key=lambda x: orden.get(x, 0))
    dias_peor = max(x for x in (d1, d2) if x is not None) if (d1 or d2) else None
    est_hoy = None
    if precio and mep and mep_act:
        est_hoy = round(precio / mep_act[1], 6)
    rows_out.append((cuit, tk, 'byma_only', precio, p_fecha,
                     mep, mep_f, pusd, 'ARS_x_MEP_pareado',
                     1 if (p_fecha and mep_f and p_fecha[:10] != mep_f[:10]) else 0,
                     est_hoy, mep_act[1] if mep_act else None,
                     mep_act[0] if mep_act else None,
                     mx, mn, dmx_c, dmn_c, okflag, det.strip('; '), mcapusd,
                     ruedas, guard, dias_peor, peor,
                     'yfinance(ARS)+MEP dolarito', now))

# ADR argentinos con precio nativo USD
cuits_mapa = dict(sc.execute("SELECT ticker, cuit FROM mapa_entidades"))
for tk, precio, hi, lo, fe in sc.execute("""SELECT e.ticker_ppal, MAX(p.precio),
        MAX(p.year_high), MIN(p.year_low), MAX(p.fecha)
        FROM precios p JOIN empresas e ON e.cik=p.cik
        WHERE e.grupo IN ('adr_arg','latam') AND p.currency='USD'
        GROUP BY e.ticker_ppal""").fetchall():
    cuit = cuits_mapa.get(tk)
    if not cuit:
        continue
    ya = {r[0] for r in rows_out} if rows_out else set()
    # por si ya existe fila por screener (no deberia: adr no esta en byma_only)
    d1, e1 = staleness(fe)
    dmx_c = round(precio / hi - 1, 6) if (precio and hi) else None
    dmn_c = round(precio / lo - 1, 6) if (precio and lo) else None
    rows_out.append((cuit, tk, 'adr', None, None, None, None, precio,
                     'NATIVO_USD_ADR', 0, None, None, None,
                     None, None, dmx_c, dmn_c, 1, '', None, None, None,
                     d1, e1, 'yfinance(ADR)', now))

COLS = ['cuit','ticker','grupo','precio_ars','precio_ars_fecha','mep_pareado',
        'mep_pareado_fecha','precio_usd','metodo_usd','mezcla_temporal',
        'precio_usd_estimado_hoy','mep_actual','mep_actual_fecha',
        'max52w_ars','min52w_ars','dif_max_52w_pct','dif_min_52w_pct',
        'dif_check_ok','dif_check_detalle','market_cap_usd',
        'pct_ruedas_operadas','guard_motivo','staleness_dias','staleness_estado',
        'fuente','built_at']
ph = ','.join(['?'] * len(COLS))
dc.executemany(
    f'INSERT OR REPLACE INTO mercado_byma ({",".join(COLS)}) VALUES ({ph})',
    rows_out)
dst.commit()

print()
print('RESUMEN b4_mercado:')
tot = dc.execute('SELECT COUNT(*) FROM mercado_byma').fetchone()[0]
print(f'  filas mercado: {tot}')
for r in dc.execute("""SELECT metodo_usd, staleness_estado, COUNT(*)
                       FROM mercado_byma GROUP BY 1,2 ORDER BY 3 DESC"""):
    print(f'  {r[0]:<18} {r[1]:<12} {r[2]}')
print(f'  dif-check fallidos (>0.5%): {n_check_fail}')
mezcla = dc.execute('SELECT COUNT(*) FROM mercado_byma WHERE mezcla_temporal=1').fetchone()[0]
print(f'  con mezcla temporal precio/MEP declarada: {mezcla}')
sin_precio = dc.execute(
    "SELECT COUNT(*) FROM byma_universo u WHERE NOT EXISTS "
    "(SELECT 1 FROM mercado_byma m WHERE m.cuit=u.cuit)").fetchone()[0]
print(f'  empresas del universo SIN dato de mercado: {sin_precio}')
src.close(); dst.close()
