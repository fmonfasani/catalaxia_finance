# -*- coding: utf-8 -*-
"""
FASE 4 — Deriva ratios desde fact_financials (gold).
TTM = suma de los últimos 4 trimestres standalone; balance = snapshot más reciente.
Doble variante RECPAM en los ratios que dependen de NetIncome. Marca confianza.
Cruza PER/ROE vs ratios_externos (investing). SQLite. Idempotente.
"""
import sqlite3, datetime as dt
import os as _os
# SCREENER_DB: apunta a una copia de prueba sin tocar produccion.
DB = _os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))
con=sqlite3.connect(DB); cur=con.cursor()

cur.executescript('''
DROP TABLE IF EXISTS fact_ratios;
CREATE TABLE fact_ratios(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id INTEGER NOT NULL, ticker TEXT, period_end TEXT, period_type TEXT DEFAULT 'TTM',
  incluye_recpam INTEGER NOT NULL DEFAULT 1, ratio TEXT NOT NULL, valor NUMERIC,
  confianza TEXT, built_at TEXT,
  UNIQUE(entity_id,period_type,incluye_recpam,ratio));
''')

def mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
def ttm(eid,concepto,recpam=1):
    rows=cur.execute("""select period_end,valor from fact_financials where entity_id=? and
        concepto_canonico=? and period_type='Q' and incluye_recpam=? order by period_end desc""",
        (eid,concepto,recpam)).fetchall()
    if len(rows)<4: return None,None,len(rows)
    l4=rows[:4]; pe=l4[0][0]
    span_ok = mb(l4[3][0],l4[0][0])==9   # 4 trimestres consecutivos
    return sum(v for _,v in l4), pe, (4 if span_ok else -1)
def snap(eid,concepto):
    r=cur.execute("""select period_end,valor from fact_financials where entity_id=? and
        concepto_canonico=? order by period_end desc limit 1""",(eid,concepto)).fetchone()
    return (r[1],r[0]) if r else (None,None)

# market cap (ARS) desde screener por ticker
# precio_ars (BYMA) por ticker → base para PER = precio/EPS y market_cap = precio×shares
precio={t:p for t,p in cur.execute("select ticker,precio_ars from screener").fetchall()}
now=dt.datetime.now().isoformat(timespec='seconds')
ROWS=[]
ents=cur.execute("select entity_id,ticker_canonico from dim_entity where grupo!='sp500'").fetchall()
for eid,tk in ents:
    rev,_,nrev=ttm(eid,'revenue'); oi,_,_=ttm(eid,'operating_income'); eb,_,_=ttm(eid,'ebitda')
    gp,_,_=ttm(eid,'gross_profit')
    equity,_=snap(eid,'equity'); assets,_=snap(eid,'assets'); cash,_=snap(eid,'cash')
    dc,_=snap(eid,'debt_current'); dnc,_=snap(eid,'debt_noncurrent')
    debt=(dc or 0)+(dnc or 0) if (dc is not None or dnc is not None) else None
    px=precio.get(tk)
    # shares derivadas de NI/EPS (recpam=1) → market_cap auto-consistente en ARS
    eps1,_,_=ttm(eid,'eps_basic',1); ni1,_,_=ttm(eid,'net_income',1)
    shares = ni1/eps1 if (eps1 and ni1 and eps1!=0) else None
    mc = px*shares if (px and shares) else None
    def emit(ratio,val,recpam,ok):
        if val is None: return
        ROWS.append((eid,tk,'TTM',recpam,ratio,val,'alta' if ok else 'baja',now))
    # ratios NO afectados por RECPAM (una variante)
    base_ok = nrev==4 and rev not in (None,0)
    if rev:
        emit('margen_operativo', oi/rev if oi is not None else None,1,base_ok)
        emit('margen_bruto', gp/rev if gp is not None else None,1,base_ok)
        emit('margen_ebitda', eb/rev if eb is not None else None,1,base_ok)
    if eb and eb>0 and debt is not None: emit('deuda_ebitda', debt/eb,1,base_ok)
    if eb and eb>0 and mc is not None:
        emit('ev_ebitda', (mc+ (debt or 0) - (cash or 0))/eb,1,base_ok)
    if mc is not None and rev: emit('p_sales', mc/rev,1,base_ok)
    if mc is not None and equity and equity>0: emit('p_book', mc/equity,1,base_ok)
    # ratios afectados por RECPAM (2 variantes: con y sin)
    for recpam in (1,0):
        ni,_,nni=ttm(eid,'net_income',recpam)
        eps,_,_=ttm(eid,'eps_basic',recpam)
        ok = nni==4
        if ni is not None and rev: emit('margen_neto', ni/rev, recpam, ok and base_ok)
        if ni is not None and equity and equity>0: emit('roe', ni/equity, recpam, ok)
        if ni is not None and assets and assets>0: emit('roa', ni/assets, recpam, ok)
        # PER = precio / EPS_ttm (estilo IAMC: solo si EPS>0)
        if px and eps and eps>0:
            per=px/eps
            emit('per', per, recpam, ok and 1<=per<=100)

cur.executemany("""insert or ignore into fact_ratios
   (entity_id,ticker,period_type,incluye_recpam,ratio,valor,confianza,built_at)
   values(?,?,?,?,?,?,?,?)""",ROWS)
con.commit()

def q(s,*a): return cur.execute(s,a).fetchone()[0]
print(f'fact_ratios: {q("select count(*) from fact_ratios")} filas | '
      f'{q("select count(distinct entity_id) from fact_ratios")} entidades')
print('  por ratio (alta/baja confianza):')
for r,a,b in cur.execute("select ratio,sum(confianza='alta'),sum(confianza='baja') from fact_ratios where incluye_recpam=1 group by ratio order by ratio").fetchall():
    print(f'     {r:>18}: alta {a}  baja {b}')

# ---- cruce PER/ROE vs investing ----
print('\\n== PER y ROE: nuestro (recpam=1) vs investing ==')
print(f'{"tk":>7} | {"ROE mio":>8} {"ROE ext":>8} {"":>3}| {"PER mio":>8} {"PER ext":>8} {"":>3}| conf')
alias={'BOLT':'BOLT_2','PATA':'PATA_2'}
def near(a,b,t): return isinstance(a,(int,float)) and isinstance(b,(int,float)) and abs(a-b)<=abs(b)*t+ (0.02 if t<1 else 1)
roe_ok=per_ok=roe_n=per_n=0
for eid,tk in ents:
    extk=alias.get(tk,tk)
    ext=cur.execute("select roe,per from ratios_externos where ticker=?",(extk,)).fetchone()
    if not ext: continue
    mroe=cur.execute("select valor,confianza from fact_ratios where entity_id=? and ratio='roe' and incluye_recpam=1",(eid,)).fetchone()
    mper=cur.execute("select valor,confianza from fact_ratios where entity_id=? and ratio='per' and incluye_recpam=1",(eid,)).fetchone()
    eroe,eper=ext
    def f(x,pct=False):
        if not x: return '—'
        v=x[0]*100 if pct else x[0]; return f'{v:.1f}'+('%' if pct else '')
    rk=pk=''
    if mroe and eroe is not None: roe_n+=1; ok=near(mroe[0]*100,eroe,0.20); rk='OK' if ok else 'DIF'; roe_ok+=ok
    if mper and eper is not None: per_n+=1; ok=near(mper[0],eper,0.20); pk='OK' if ok else 'DIF'; per_ok+=ok
    ec=lambda x: f'{x:.1f}%' if isinstance(x,(int,float)) else '—'
    ep=lambda x: f'{x:.1f}' if isinstance(x,(int,float)) else '—'
    conf=(mroe[1] if mroe else (mper[1] if mper else '-'))
    print(f'{tk:>7} | {f(mroe,1):>8} {ec(eroe):>8} {rk:>3}| {f(mper):>8} {ep(eper):>8} {pk:>3}| {conf}')
print(f'\\nROE coincide: {roe_ok}/{roe_n} | PER coincide: {per_ok}/{per_n}  (tol 20%)')
con.close()
