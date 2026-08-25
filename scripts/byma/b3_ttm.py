"""
E3b — b3_ttm: TTM con ventana declarada y coherencia verificada.

Formula (flujo):  TTM = YTD_cur - YTD_prev + FY_prev
  donde YTD_prev es el acumulado cuyo inicio fiscal = inicio_actual - 12 meses.
Si ttm_hasta ES cierre fiscal -> TTM = FY directo.
Balance: valores al ttm_hasta (+ promedio equity ~12m para ROE).
"""
import calendar
import os
import sqlite3
from datetime import date, datetime, timedelta

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = os.path.join(BASE, 'data', 'byma_pipeline.db')

FLUJOS = ['Revenue', 'NetIncome', 'OperatingIncome', 'EBITDA', 'CF_Operativo',
          'CF_Inversion', 'DA', 'InterestExpense', 'PretaxIncome', 'IncomeTax',
          'GrossProfit']

def add_months(d: date, m: int) -> date:
    y, mo = divmod((d.year * 12 + d.month - 1) + m, 12)
    last = calendar.monthrange(y, mo + 1)[1]
    return date(y, mo + 1, min(d.day, last))

con = sqlite3.connect(PIPE)
c = con.cursor()
fymap = {r[0]: (r[1] or 12) for r in c.execute(
    "SELECT cuit, fy_end_month FROM byma_universo")}
tickers = dict(c.execute(
    "SELECT cuit, COALESCE(ticker,'') FROM byma_universo"))

c.execute("DROP TABLE IF EXISTS ratios_ttm_byma")
c.execute("""CREATE TABLE ratios_ttm_byma (
    cuit TEXT NOT NULL, ticker TEXT,
    concepto TEXT NOT NULL,
    valor_ttm REAL,
    ttm_desde TEXT, ttm_hasta TEXT,
    metodo TEXT,
    comp_fy REAL, comp_ytd REAL, comp_ytd_prev REAL,
    cobertura_ok INTEGER, detalle TEXT,
    built_at TEXT,
    PRIMARY KEY(cuit, concepto))""")
c.execute("DROP TABLE IF EXISTS balances_ttm_byma")
c.execute("""CREATE TABLE balances_ttm_byma (
    cuit TEXT PRIMARY KEY, ticker TEXT, ttm_hasta TEXT,
    equity REAL, equity_12m_atras REAL, equity_prom REAL,
    assets REAL, deuda_total REAL, cash REAL,
    cobertura_ok INTEGER, detalle TEXT, built_at TEXT)""")
now = datetime.now().isoformat()

partidas = {}
for r in c.execute("""SELECT cuit, concepto_normalizado, period_type, clase,
                             valor, periodo_desde, periodo_hasta
                      FROM partidas_norm WHERE valor IS NOT NULL"""):
    partidas.setdefault(r[0], []).append(r)

stats = {'empresas': 0, 'directo': 0, 'compuesto': 0, 'fallido': 0, 'sin_rev': 0}
ins_ttm, ins_bal = [], []
for cuit, plist in sorted(partidas.items()):
    stats['empresas'] += 1
    fym = fymap.get(cuit)
    acum, bal = {}, {}
    for _, co, pt, cl, v, pd_, ph in plist:
        if cl == 'flujo' and pt == 'acumulado':
            acum.setdefault(co, {})[ph] = (v, pd_)
        elif cl == 'balance':
            bal.setdefault(co, {})[ph] = v
    rev = acum.get('Revenue')
    if not rev:
        stats['sin_rev'] += 1
        continue
    hasta = max(rev)
    vhasta, shasta = rev[hasta]
    d_h = date.fromisoformat(hasta)

    if d_h.month == fym:
        es_fy, fs_cur = True, None
        win_desde = add_months(d_h.replace(day=1), -11) + timedelta(days=0)
        win_desde = win_desde.replace(day=1)
    else:
        es_fy = False
        y = d_h.year if d_h.month > fym else d_h.year - 1
        fin_fy = date(y, fym, calendar.monthrange(y, fym)[1])
        fs_cur = fin_fy + timedelta(days=1)
        win_desde = add_months(fs_cur, -12)
    desde_iso = win_desde.isoformat()

    for co in FLUJOS:
        serie = acum.get(co, {})
        if hasta not in serie:
            continue
        vc = serie[hasta][0]
        if es_fy:
            ins_ttm.append((cuit, tickers.get(cuit, ''), co, vc, desde_iso, hasta,
                            'FY_DIRECTO', vc, None, None, 1,
                            'TTM = cierre fiscal anual completo', now))
            stats['directo'] += 1
            continue
        # YTD previo: mismo inicio fiscal un anio antes
        obj = add_months(date.fromisoformat(shasta), -12).isoformat() if shasta else None
        ytd_prev = next((v for pe, (v, s2) in serie.items() if s2 == obj), None) \
            if obj else None
        fys = [v for pe, (v, _) in serie.items()
               if date.fromisoformat(pe).month == fym and pe < fs_cur.isoformat()]
        fy_v = max(fys) if fys else None
        ok = ytd_prev is not None and fy_v is not None
        val = round(vc - ytd_prev + fy_v, 4) if ok else None
        det = (f'YTD{hasta}={vc:.6g} - YTDprev={ytd_prev:.6g} + FY={fy_v:.6g}'
               if ok else
               'faltante: ' + ('YTD_prev ' if ytd_prev is None else '')
               + ('FY_prev' if fy_v is None else ''))
        stats['compuesto' if ok else 'fallido'] += 1
        ins_ttm.append((cuit, tickers.get(cuit, ''), co, val, desde_iso, hasta,
                        'YTD_FY_YTDPREV', fy_v, vc, ytd_prev, int(ok), det, now))

    def bval(concepto):
        s = bal.get(concepto, {})
        return s.get(max(s)) if s else None

    eq_s = bal.get('Equity', {})
    eq_h = bval('Equity')
    eq12 = None
    if eq_h is not None:
        otros = sorted((p for p in eq_s if p != max(eq_s)),
                       key=lambda x: abs((date.fromisoformat(x) - d_h).days))
        if otros and abs((date.fromisoformat(otros[0]) - d_h).days) <= 400:
            eq12 = eq_s[otros[0]]
    dc_, dn = bval('DebtCurrent'), bval('DebtNonCurrent')
    deuda = (dc_ or 0) + (dn or 0) if (dc_ is not None or dn is not None) else None
    ins_bal.append((cuit, tickers.get(cuit, ''), hasta, eq_h, eq12,
                    (eq_h + eq12) / 2 if (eq_h is not None and eq12 is not None) else None,
                    bval('Assets'), deuda, bval('Cash'),
                    int(eq_h is not None and bval('Assets') is not None),
                    f'equity_prom usa cierre anterior mas proximo <=400d', now))

c.executemany('INSERT OR REPLACE INTO ratios_ttm_byma VALUES '
              '(?,?,?,?,?,?,?,?,?,?,?,?,?)', ins_ttm)
c.executemany('INSERT OR REPLACE INTO balances_ttm_byma VALUES '
              '(?,?,?,?,?,?,?,?,?,?,?,?)', ins_bal)
con.commit()

print('RESUMEN b3_ttm:')
print(f"  empresas con datos: {stats['empresas']} (sin Revenue acumulado: {stats['sin_rev']})")
print(f"  TTM directos (cierre fiscal): {stats['directo']:,}")
print(f"  TTM compuestos OK: {stats['compuesto']:,}")
print(f"  TTM fallidos (sin componentes): {stats['fallido']:,}")
n_ni = c.execute("""SELECT COUNT(*), SUM(cobertura_ok) FROM ratios_ttm_byma
                    WHERE concepto='NetIncome'""").fetchone()
n_rev = c.execute("""SELECT COUNT(DISTINCT cuit) FROM ratios_ttm_byma
                     WHERE concepto='Revenue' AND cobertura_ok=1""").fetchone()[0]
n_eqp = c.execute("""SELECT COUNT(*) FROM balances_ttm_byma
                     WHERE equity_prom IS NOT NULL""").fetchone()[0]
print(f'  NetIncome TTM: {n_ni[1]}/{n_ni[0]} certificados | Revenue ok en {n_rev} empresas')
print(f'  balances con equity_prom (para ROE): {n_eqp}')
con.close()
