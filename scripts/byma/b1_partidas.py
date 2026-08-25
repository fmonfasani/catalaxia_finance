"""
E2b — b1_partidas: magnitudes base normalizadas desde cnv_estados_norm.

Lee:  snapshot -> cnv_estados_norm + fiscal_calendar
Escribe: data/byma_pipeline.db -> partidas_norm + partidas_ratios_cnv

Reglas:
  - tipo 'A' = Acumulado (YTD), tipo 'P' = Período (trimestre discreto).
    VERIFICADO: NetIncome en Q1 ratio A/P ~1.0; Revenue A/P hasta 19x.
  - Conceptos CNV_* son RATIOS declarados, no partidas -> tabla aparte.
  - Balance (stock): periodo_desde NULL. Flujo: periodo_desde según FY.
  - valor usa valor_corregido si existe; guarda valor_original.
  - confidence: BAJA (coherencia_falla o identidad>2%) / MEDIA (perimetro_mixto) / ALTA.
"""
import glob
import hashlib
import os
import sqlite3
from datetime import date, datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = os.path.join(BASE, 'data', 'byma_pipeline.db')

SNAPS = sorted(glob.glob(os.path.join(BASE, 'data', 'backups', 'snapshot_byma_2*.db')))
SNAPS = [s for s in SNAPS if '_baseline_' not in os.path.basename(s)]
SNAP = SNAPS[-1]
print(f'snapshot fuente: {os.path.basename(SNAP)}')

BALANCE = {'Assets','AssetsCurrent','AssetsNonCurrent','Cash','DebtCurrent','DebtNonCurrent',
           'Equity','Intangibles','Inventory','Liabilities','LiabilitiesCurrent',
           'LiabilitiesNonCurrent','PPE','Payables','Receivables','WorkingCapital',
           'Capital','Reservas','ResultadosNoAsignados'}
FLOW = {'COGS','CF_Financiacion','CF_Inversion','CF_Operativo','CashFlowNeto','DA','EBIT',
        'EBITDA','EPS_basico','EPS_diluido','GrossProfit','IncomeTax','IngresosFinancieros',
        'InterestExpense','NetIncome','OperatingIncome','PretaxIncome','RECPAM','Revenue',
        'ResultadoIntegral'}

def add_months(d: date, m: int) -> date:
    y, mo = divmod((d.year * 12 + d.month - 1) + m, 12)
    day = min(d.day, [31,29 if y%4==0 and (y%100!=0 or y%400==0) else 28,
                      31,30,31,30,31,31,30,31,30,31][mo])
    return date(y, mo+1, day)

def fy_start(pe: str, fy_month: int):
    """Inicio del ejercicio fiscal que contiene pe."""
    d = date.fromisoformat(pe)
    if d.month == fy_month:
        return add_months(d.replace(day=1), -11)
    # ultimo cierre fiscal anterior a d
    y = d.year if d.month > fy_month else d.year - 1
    fin = date(y, fy_month, 1)
    fin = add_months(fin.replace(day=1), 0).replace(day=28)
    # fin real = ultimo dia del mes fiscal anterior
    import calendar
    last = calendar.monthrange(y, fy_month)[1]
    fin = date(y, fy_month, last)
    return add_months(fin, 1)

src = sqlite3.connect(SNAP)
sc = src.cursor()
dst = sqlite3.connect(PIPE)
dc = dst.cursor()

dc.execute("DROP TABLE IF EXISTS partidas_norm")
dc.execute("""CREATE TABLE partidas_norm (
    partida_id INTEGER PRIMARY KEY,
    cuit TEXT NOT NULL, ticker TEXT,
    concepto_normalizado TEXT NOT NULL, concepto_original TEXT NOT NULL,
    clase TEXT NOT NULL,               -- balance | flujo
    period_type TEXT NOT NULL,         -- acumulado | periodo
    valor REAL, valor_original REAL,
    unidad_escala INTEGER, moneda TEXT DEFAULT 'ARS', unidad_normalizada TEXT DEFAULT 'ARS',
    periodo_desde TEXT, periodo_hasta TEXT NOT NULL, periodo_desde_aprox INTEGER DEFAULT 0,
    fecha_reexpresion TEXT, version_id TEXT,
    tipo_balance TEXT, perimetro_mixto INTEGER,
    fuente TEXT, documento TEXT,
    valor_usd REAL, mep_fecha TEXT,
    confidence TEXT, motivos_confidence TEXT,
    built_at TEXT,
    UNIQUE(cuit, concepto_original, period_type, periodo_hasta, tipo_balance, version_id))""")
dc.execute("""CREATE TABLE IF NOT EXISTS partidas_ratios_cnv (
    cuit TEXT, ticker TEXT, ratio TEXT, period_end TEXT, tipo TEXT,
    valor REAL, tipo_balance TEXT, accn TEXT, built_at TEXT)""")

fy = {r[0]: (r[1] or 12) for r in sc.execute(
    "SELECT cuit, fy_end_month FROM fiscal_calendar")}
tick = {r[0]: r[1] for r in sc.execute(
    "SELECT DISTINCT cuit, ticker FROM mapa_entidades WHERE es_primario=1")}

now = datetime.now().isoformat()
ins, ins_ratios, excl = [], [], 0
rows = sc.execute("""SELECT cuit, ticker, concepto, period_end, tipo, valor,
        valor_comparativo, fecha_reexpresion, form, escala, accn, fuente,
        tipo_balance, perimetro_mixto, identidad_desvio_pct,
        valor_corregido, correccion_motivo, coherencia_falla
        FROM cnv_estados_norm""").fetchall()

for (cuit, tk, con_, pe, tp, val, vcomp, frex, form, esc, accn, fuente,
     tb, pmix, idpct, vcorr, cmot, cofalla) in rows:
    if con_.startswith('CNV_'):
        ins_ratios.append((cuit, tick.get(cuit) or tk, con_, pe, tp, val, tb, accn, now))
        excl += 1
        continue
    clase = 'balance' if con_ in BALANCE else ('flujo' if con_ in FLOW else 'otro')
    ptype = 'acumulado' if tp == 'A' else 'periodo'
    fym = fy.get(cuit, int(pe[5:7]))
    pd_, aprox = None, 0
    if clase == 'flujo':
        try:
            fs = fy_start(pe, fym)
            if ptype == 'acumulado':
                pd_ = fs.isoformat()
            else:
                import math
                dm = (date.fromisoformat(pe).year - fs.year) * 12 + \
                     (date.fromisoformat(pe).month - fs.month)
                k = dm // 3
                pd_ = add_months(fs, k * 3).isoformat()
                aprox = 0 if dm % 3 == 0 else 1
        except Exception:
            pd_, aprox = None, 1
    vid = hashlib.sha256(f'{accn}|{tp}|{frex}|{tb}'.encode()).hexdigest()[:12]
    motivos = []
    if cofalla:
        conf = 'BAJA'; motivos.append(f'coherencia_falla={cofalla}')
    elif idpct is not None and abs(idpct) > 0.02:
        conf = 'BAJA'; motivos.append(f'identidad_desvio={idpct:.4f}')
    elif pmix == 1:
        conf = 'MEDIA'; motivos.append('perimetro_mixto')
    else:
        conf = 'ALTA'
    if vcorr is not None and cmot:
        motivos.append(f'corregido:{cmot}')
    valor_final = vcorr if vcorr is not None else val
    ins.append((cuit, tick.get(cuit) or tk, con_, con_, clase, ptype,
                valor_final, val, esc, 'ARS', 'ARS',
                pd_, pe, aprox, frex, vid, tb, pmix,
                fuente, accn,
                None, None,
                conf, ';'.join(motivos), now))

COLS = ['cuit','ticker','concepto_normalizado','concepto_original','clase','period_type',
        'valor','valor_original','unidad_escala','moneda','unidad_normalizada',
        'periodo_desde','periodo_hasta','periodo_desde_aprox','fecha_reexpresion',
        'version_id','tipo_balance','perimetro_mixto','fuente','documento',
        'valor_usd','mep_fecha','confidence','motivos_confidence','built_at']
ph = ','.join(['?'] * len(COLS))
dc.executemany(
    f'INSERT OR IGNORE INTO partidas_norm ({",".join(COLS)}) VALUES ({ph})', ins)
dc.executemany(
    "INSERT INTO partidas_ratios_cnv VALUES (?,?,?,?,?,?,?,?,?)", ins_ratios)
dst.commit()

print()
print('RESUMEN b1_partidas:')
tot = dc.execute('SELECT COUNT(*) FROM partidas_norm').fetchone()[0]
print(f'  partidas insertadas: {tot:,}')
print(f'  ratios CNV separados: {excl:,}')
for r in dc.execute("""SELECT clase, period_type, COUNT(*) FROM partidas_norm
                       GROUP BY 1,2 ORDER BY 1,2"""):
    print(f'  {r[0]:<8} {r[1]:<10} {r[2]:>7,}')
for r in dc.execute('SELECT confidence, COUNT(*) FROM partidas_norm GROUP BY 1 ORDER BY 2 DESC'):
    print(f'  conf {r[0]:<6} {r[1]:>7,}')
sin_pd = dc.execute(
    "SELECT COUNT(*) FROM partidas_norm WHERE clase='flujo' AND periodo_desde IS NULL").fetchone()[0]
print(f'  flujos sin periodo_desde (fallo calculo): {sin_pd}')
confs = dc.execute("""SELECT concepto_normalizado, COUNT(*) n FROM partidas_norm
                      WHERE confidence='BAJA' GROUP BY 1 ORDER BY n DESC LIMIT 5""").fetchall()
print(f'  conceptos mas afectados BAJA: {[(c, n) for c, n in confs]}')
src.close()
dst.close()
