# -*- coding: utf-8 -*-
"""
Loader idempotente para datos externos de investing.com.
Guarda en data/screener.db, tablas: ratios_externos y eerr_externos.

USO (desde otro script o REPL):
    from loader import save_ratios, save_eerr, DB
    save_ratios('DGCU2', per=6.01, p_book=1.44, debt_equity=0.47, roe=25.78,
                div_yield=3.21, ebitda=93060, fair_value=2428, fv_upside=44.62)
    save_eerr('DGCU2',
              periods=['2024-03-31','2024-06-30', ...],
              lines={'Revenue':[...], 'GrossProfit':[...], 'OperatingIncome':[...],
                     'EBITDA':[...], 'NetIncome':[...]})

Convenciones (RESPETAR SIEMPRE para tener datos homogéneos):
  - DB: data/screener.db  (correr desde la raíz del repo)
  - ratios_externos: per/p_book = múltiplos; roe/div_yield/debt_equity = PORCENTAJE (11.14 = 11,14%);
    ebitda = MILLONES ARS (si investing dice "B" multiplicar x1000; si dice "M" dejar igual).
    Financieras (bancos) que no reportan EBITDA -> ebitda = 0.
    Empresas que reportan en USD (ej. ADGO) -> anotar en source 'investing.com|USD'.
  - eerr_externos: valor en MILLONES (moneda nativa), trimestres STANDALONE (como muestra investing),
    period_end = fin de trimestre 'YYYY-MM-DD'. periodo_tipo = 'Q_standalone'.
  - Idempotente: INSERT OR REPLACE por PK. Re-correr no duplica.
"""
import sqlite3, datetime as dt, os

# SCREENER_DB: apunta a una copia de prueba sin tocar produccion.
DB = os.path.join(os.path.dirname(__file__), '..', '..', 'data',
                  os.environ.get('SCREENER_DB', 'screener.db'))
DB = os.path.normpath(DB)

RATIO_COLS = ['per','p_book','debt_equity','roe','div_yield','ebitda','fair_value','fv_upside']
EERR_CONCEPTOS = ['Revenue','GrossProfit','OperatingIncome','EBITDA','NetIncome']  # minimo homogeneo

def _con():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS ratios_externos(
        ticker TEXT PRIMARY KEY, per REAL, p_book REAL, debt_equity REAL, roe REAL,
        div_yield REAL, ebitda REAL, fair_value REAL, fv_upside REAL,
        source TEXT, loaded_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS eerr_externos(
        ticker TEXT, period_end TEXT, concepto TEXT, valor REAL,
        periodo_tipo TEXT DEFAULT 'Q_standalone', source TEXT DEFAULT 'investing.com', loaded_at TEXT,
        PRIMARY KEY(ticker,period_end,concepto))''')
    return c

def _now(): return dt.datetime.now().isoformat(timespec='seconds')

def _valid_ticker(cur, ticker):
    r = cur.execute("select 1 from screener where ticker=?", (ticker,)).fetchone()
    return r is not None

def save_ratios(ticker, per=None, p_book=None, debt_equity=None, roe=None,
                div_yield=None, ebitda=None, fair_value=None, fv_upside=None,
                source='investing.com', strict=True):
    """Guarda/actualiza la fila headline de un ticker. Devuelve dict con status."""
    con=_con(); cur=con.cursor()
    if strict and not _valid_ticker(cur, ticker):
        con.close()
        return {'ticker':ticker,'status':'ERROR','msg':'ticker no existe en screener'}
    cur.execute("""INSERT OR REPLACE INTO ratios_externos
        (ticker,per,p_book,debt_equity,roe,div_yield,ebitda,fair_value,fv_upside,source,loaded_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (ticker,per,p_book,debt_equity,roe,div_yield,ebitda,fair_value,fv_upside,source,_now()))
    con.commit(); con.close()
    return {'ticker':ticker,'status':'OK'}

def save_eerr(ticker, periods, lines, periodo_tipo='Q_standalone',
              source='investing.com', strict=True):
    """
    periods: lista de 'YYYY-MM-DD' (fin de trimestre).
    lines: dict {concepto: [valores alineados a periods]}. Usar los 5 conceptos minimos.
    Longitudes deben coincidir. Devuelve dict con status y nro de filas.
    """
    con=_con(); cur=con.cursor()
    if strict and not _valid_ticker(cur, ticker):
        con.close()
        return {'ticker':ticker,'status':'ERROR','msg':'ticker no existe en screener'}
    n=len(periods); rows=[]; now=_now()
    for concepto, vals in lines.items():
        if len(vals)!=n:
            con.close()
            return {'ticker':ticker,'status':'ERROR',
                    'msg':f'{concepto}: {len(vals)} valores != {n} periodos'}
        for pe,v in zip(periods, vals):
            if v is None: continue          # saltar celdas vacias ('-')
            rows.append((ticker,pe,concepto,float(v),periodo_tipo,source,now))
    cur.executemany("""INSERT OR REPLACE INTO eerr_externos
        (ticker,period_end,concepto,valor,periodo_tipo,source,loaded_at)
        VALUES(?,?,?,?,?,?,?)""", rows)
    con.commit(); con.close()
    faltan=[c for c in EERR_CONCEPTOS if c not in lines]
    return {'ticker':ticker,'status':'OK','filas':len(rows),
            'conceptos_faltantes':faltan or None}

def status():
    """Reporte de cobertura vs byma_only (56)."""
    con=_con(); cur=con.cursor()
    by=sorted({t[0] for t in cur.execute("select ticker from screener where grupo='byma_only'")})
    rat={t[0] for t in cur.execute('select ticker from ratios_externos')}
    eer={t[0] for t in cur.execute('select ticker from eerr_externos')}
    con.close()
    return {
        'byma_only':len(by),
        'ratios_ok':sorted(set(by)&rat), 'ratios_falta':[t for t in by if t not in rat],
        'eerr_ok':sorted(set(by)&eer),   'eerr_falta':[t for t in by if t not in eer],
    }

if __name__=='__main__':
    import json
    s=status()
    print(f"DB: {DB}")
    print(f"byma_only: {s['byma_only']}")
    print(f"ratios cargados: {len(s['ratios_ok'])}/56 | faltan {len(s['ratios_falta'])}")
    print(f"eerr cargados:   {len(s['eerr_ok'])}/56 | faltan {len(s['eerr_falta'])}")
    print('\nFALTA RATIOS:', ' '.join(s['ratios_falta']))
    print('\nFALTA EERR:  ', ' '.join(s['eerr_falta']))
