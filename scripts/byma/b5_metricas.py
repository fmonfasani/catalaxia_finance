"""
E5a - b5_metricas: las 13 metricas con formula e inputs registrados.

Definiciones (documentadas):
  PER = mcap_ars / NI_ttm_ars (VERIFICADO: screener.'MarketCapUSD' esta en ARS)
  EPS anual = EPS_basico del ultimo cierre fiscal completo
  CAGR EPS  = nominal, >=4 anios; flag NOMINAL_sin_deflactar
  ROE 5Y    = promedio ROE anual ultimos <=5 cierres fiscales (>=3 requeridos)
  FCF       = CFO_ttm + CFI_ttm ; flag si CFI>0
  Deuda/EBITDA = deuda_total / EBITDA_ttm
"""
import os
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = os.path.join(BASE, 'data', 'byma_pipeline.db')
con = sqlite3.connect(PIPE)
c = con.cursor()
now = datetime.now().isoformat()

c.execute("DROP TABLE IF EXISTS metricas")
c.execute("""CREATE TABLE metricas (
    cuit TEXT, ticker TEXT, metrica TEXT, valor REAL,
    formula TEXT, inputs TEXT, periodo TEXT,
    fuente TEXT, flag TEXT, built_at TEXT,
    PRIMARY KEY(cuit, metrica))""")

def put(cuit, tk, met, val, formula, inputs, periodo, fuente, flag=''):
    if val is not None:
        c.execute('INSERT OR REPLACE INTO metricas VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (cuit, tk, met, float(val), formula, inputs or '', periodo or '',
                   fuente, flag, now))

ttm, bal, merc = {}, {}, {}
for r in c.execute("""SELECT cuit, concepto, valor_ttm, ttm_desde, ttm_hasta
                      FROM ratios_ttm_byma WHERE cobertura_ok=1"""):
    ttm.setdefault(r[0], {})[r[1]] = r[2:]
for r in c.execute("""SELECT cuit, equity_prom, assets, deuda_total FROM balances_ttm_byma"""):
    bal[r[0]] = r[1:]
for r in c.execute("""SELECT cuit, ticker, precio_ars, precio_usd, max52w_ars,
                      dif_max_52w_pct, min52w_ars, dif_min_52w_pct, mep_pareado,
                      market_cap_usd, staleness_estado FROM mercado_byma"""):
    merc[r[0]] = r[1:]

fy_series = {}
q = """SELECT p.cuit, p.concepto_normalizado, p.periodo_hasta, p.valor
       FROM partidas_norm p JOIN byma_universo u ON u.cuit=p.cuit
       WHERE p.period_type='acumulado'
         AND p.concepto_normalizado IN ('NetIncome','Equity','EPS_basico')
         AND CAST(substr(p.periodo_hasta,6,2) AS INTEGER)=u.fy_end_month
         AND p.valor IS NOT NULL"""
for cuit, co, pe, v in con.execute(q):
    fy_series.setdefault(cuit, {}).setdefault(co, {})[pe] = v

for cuit, m in merc.items():
    tk = m[0]
    precio_ars, precio_usd, mx, difmx, mn, difmn, mep, mcap_ars, st = m[1:]
    T = ttm.get(cuit, {})
    B = bal.get(cuit, (None, None, None))
    win = T['Revenue'][2] if 'Revenue' in T else None

    put(cuit, tk, 'precio_usd', precio_usd, 'precio_ars / MEP_pareado',
        f'precio_ars={precio_ars}; mep={mep}', None, 'b4',
        '' if st == 'FRESCO' else f'staleness={st}')
    put(cuit, tk, 'max_52w', mx / mep if (mx and mep) else None,
        'max52w_ars / MEP', f'max52w_ars={mx}', None, 'b4')
    put(cuit, tk, 'dif_max_52w', difmx, '(precio/max52w-1)*100',
        'validado en b4 dif_check_ok=1', None, 'b4')
    put(cuit, tk, 'min_52w', mn / mep if (mn and mep) else None,
        'min52w_ars / MEP', f'min52w_ars={mn}', None, 'b4')
    put(cuit, tk, 'dif_min_52w', difmn, '(precio/min52w-1)*100',
        'validado en b4 dif_check_ok=1', None, 'b4')

    g = lambda co: T.get(co, (None,))[0]
    ni, rev, ebitda = g('NetIncome'), g('Revenue'), g('EBITDA')

    if mcap_ars and ni:
        put(cuit, tk, 'per', mcap_ars / ni if ni > 0 else None,
            'mcap_ars / NI_ttm_ars (mismo vintage)',
            f'mcap_ars={mcap_ars:.6g}; NI={ni:.6g}' if ni else '',
            win, 'b3+b4', '' if ni > 0 else 'NI_negativo->NULL')
    if ebitda and ebitda > 0 and B[2] is not None:
        put(cuit, tk, 'deuda_ebitda', B[2] / ebitda,
            '(DebtCurrent+DebtNonCurrent)/EBITDA_ttm',
            f'deuda={B[2]:.6g}; ebitda={ebitda:.6g}', win, 'b3')
    eps_s = fy_series.get(cuit, {}).get('EPS_basico', {})
    if eps_s:
        pe_last = max(eps_s)
        put(cuit, tk, 'eps_anual', eps_s[pe_last],
            'EPS_basico ultimo cierre fiscal completo', f'cierre={pe_last}',
            pe_last, 'b1', 'es_FY_no_TTM')
    if len(eps_s) >= 2:
        items = sorted(eps_s.items())
        (p0, v0), (p1, v1) = items[0], items[-1]
        yrs = int(p1[:4]) - int(p0[:4])
        if yrs >= 4 and v0 > 0 and v1 > 0:
            put(cuit, tk, 'crecimiento_eps_5y', (v1 / v0) ** (1 / yrs) - 1,
                f'CAGR nominal {p0}->{p1} ({yrs} anios)',
                f'eps0={v0:.6g}; eps1={v1:.6g}', f'{p0}->{p1}', 'b1',
                'NOMINAL_sin_deflactar')
    if ni is not None and rev:
        put(cuit, tk, 'margen_neto', ni / rev, 'NI_ttm/Revenue_ttm',
            f'NI={ni:.6g}; Rev={rev:.6g}' if ni else '', win, 'b3')
    nis = fy_series.get(cuit, {}).get('NetIncome', {})
    eqs = fy_series.get(cuit, {}).get('Equity', {})
    roes = [(pe, nis[pe] / eqs[pe]) for pe in sorted(set(nis) & set(eqs))
            if eqs[pe] > 0][-5:]
    if len(roes) >= 3:
        put(cuit, tk, 'roe_5y', sum(v for _, v in roes) / len(roes),
            f'promedio ROE anuales ultimos {len(roes)} cierres '
            f'{[p[:4] for p,_ in roes]}',
            '; '.join(f'{p}:{v:.4f}' for p, v in roes),
            f'{roes[0][0]}->{roes[-1][0]}', 'b1')
    cfo, cfi = g('CF_Operativo'), g('CF_Inversion')
    if None not in (cfo, cfi) and mcap_ars:
        fcf = cfo + cfi
        put(cuit, tk, 'fcf_market_cap', fcf / mcap_ars,
            '(CFO+CFI)_ttm / mcap_ars', f'cfo={cfo:.6g}; cfi={cfi:.6g}',
            win, 'b3+b4', 'CFI_positivo' if cfi > 0 else '')

# 13) payout heredado del v2 (con su provenance)
src = sqlite3.connect(os.path.join(BASE, 'data', 'backups',
                                   sorted(x for x in os.listdir(
                                       os.path.join(BASE, 'data', 'backups'))
                                       if x.startswith('snapshot_byma_2026')
                                       and x.endswith('.db'))[-1]))
for cuit, pay, pstat, psource in src.execute(
        """SELECT s.cuit, s.Payout, s.payout_status, s.payout_source
           FROM screener s WHERE s.grupo='byma_only' AND s.Payout IS NOT NULL"""):
    put(cuit, merc.get(cuit, (None,))[0], 'payout', pay,
        'heredado v2: cash-basis ventana 12m al cierre fiscal',
        f'status={pstat}', None, f'screener_v2/{psource}')
src.close()
con.commit()

print('RESUMEN b5_metricas:')
tot_emp = c.execute('SELECT COUNT(DISTINCT cuit) FROM metricas').fetchone()[0]
print(f'  empresas con al menos una metrica: {tot_emp}')
for met in ['precio_usd','per','max_52w','dif_max_52w','min_52w','dif_min_52w',
            'deuda_ebitda','eps_anual','crecimiento_eps_5y','margen_neto',
            'roe_5y','fcf_market_cap','payout']:
    n = c.execute('SELECT COUNT(*) FROM metricas WHERE metrica=?',(met,)).fetchone()[0]
    print(f'  {met:<20} {n:>3}/56')
con.close()
