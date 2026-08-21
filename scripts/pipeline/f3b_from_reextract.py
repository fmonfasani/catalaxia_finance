# -*- coding: utf-8 -*-
"""
FASE 3b — fact_financials desde cnv_reextract (consolidado limpio) + validación por
IDENTIDADES CONTABLES (Activo=Pasivo+PN, GrossProfit=Revenue-COGS) como certeza interna.
Reemplaza la fuente corrupta cnv_estados_v2 para byma_only. SQLite. Idempotente.
"""
import sqlite3, statistics, datetime as dt
import os as _os
con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()
FLOW={'revenue','cogs','gross_profit','operating_income','ebit','ebitda','da','interest_expense',
 'financial_income','recpam','pretax_income','income_tax','net_income','comprehensive_income',
 'cfo','cfi','cff','net_change_cash','eps_basic','eps_diluted'}
RECPAM_AFFECTED={'net_income','pretax_income','comprehensive_income'}
cur.executescript('''
DROP TABLE IF EXISTS fact_financials;
CREATE TABLE fact_financials(id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id INTEGER, concepto_canonico TEXT,
  period_end TEXT, period_type TEXT, fiscal_q INTEGER, valor NUMERIC, moneda TEXT, incluye_recpam INTEGER,
  fuente TEXT, loaded_at TEXT, UNIQUE(entity_id,concepto_canonico,period_end,period_type,incluye_recpam,fuente));
DROP TABLE IF EXISTS entity_validacion;
CREATE TABLE entity_validacion(entity_id INTEGER PRIMARY KEY, ticker TEXT, balance_err REAL,
  cascade_err REAL, balance_ok INTEGER, cascade_ok INTEGER, nivel TEXT);
''')
def mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
now=dt.datetime.now().isoformat(timespec='seconds')
ents=cur.execute("select entity_id,cuit,ticker_canonico,fy_end_month from dim_entity where grupo='byma_only' and cuit is not null").fetchall()
INS=[]
val_rows=[]
for eid,cuit,tk,fy in ents:
    fy=fy or 12
    raw=cur.execute("select concepto,period_end,valor from cnv_reextract where cuit=?",(cuit,)).fetchall()
    series={}
    for concepto,pe,valor in raw:
        if valor is None: continue
        series.setdefault(concepto,{})[pe]=valor
    perdata={}
    def pico(seq,i):
        ng=[abs(seq[j]) for j in (i-1,i+1) if 0<=j<len(seq) and seq[j] not in (None,0)]
        ng=[x for x in ng if x>0]; ref=statistics.median(ng) if ng else 0
        return ref>0 and abs(seq[i])>30*ref
    for canon,d in series.items():
        pes=sorted(d)
        if canon in FLOW:
            std={}
            for pe in pes:
                q=4-((fy-int(pe[5:7]))%12)//3
                if q==1: std[pe]=d[pe]
                else:
                    prev=[p for p in pes if p<pe and mb(p,pe)==3]
                    std[pe]=d[pe]-d[prev[-1]] if prev else None
            order=[pe for pe in pes if std.get(pe) is not None]; seq=[std[pe] for pe in order]
            for i,pe in enumerate(order):
                if pico(seq,i): continue
                q=4-((fy-int(pe[5:7]))%12)//3
                perdata[(canon,pe,'Q')]=(std[pe],q)
                if q==4: perdata[(canon,pe,'A')]=(d[pe],q)
        else:
            seq=[d[pe] for pe in pes]
            for i,pe in enumerate(pes):
                if pico(seq,i): continue
                q=4-((fy-int(pe[5:7]))%12)//3
                perdata[(canon,pe,'A' if q==4 else 'Q')]=(d[pe],q)
    recpam={(pe,pt):v for (c,pe,pt),(v,q) in perdata.items() if c=='recpam'}
    for (canon,pe,pt),(valor,q) in perdata.items():
        INS.append((eid,canon,pe,pt,q,valor,'ARS',1,'cnv_reextract',now))
        if canon in RECPAM_AFFECTED and recpam.get((pe,pt)) is not None:
            INS.append((eid,canon,pe,pt,q,valor-recpam[(pe,pt)],'ARS',0,'cnv_reextract',now))
    # ---- identidades contables (último período con los datos) ----
    def latest(c):
        d=series.get(c,{});
        return d[max(d)] if d else None
    A=latest('assets'); L=latest('liabilities'); E=latest('equity')
    R=latest('revenue'); C=latest('cogs'); G=latest('gross_profit')
    berr=abs(A-(L+E))/abs(A) if (A and L is not None and E is not None and A) else None
    cerr=min(abs(G-(R-C)),abs(G-(R+C)))/abs(R) if (R and C is not None and G is not None and R) else None
    bok=1 if (berr is not None and berr<0.02) else 0
    cok=1 if (cerr is not None and cerr<0.03) else 0
    val_rows.append((eid,tk,berr,cerr,bok,cok))

cur.executemany('''insert or ignore into fact_financials
 (entity_id,concepto_canonico,period_end,period_type,fiscal_q,valor,moneda,incluye_recpam,fuente,loaded_at)
 values(?,?,?,?,?,?,?,?,?,?)''',INS)
# nivel de certeza: externo (tiene eerr) > identidades > sin verificar
ext_tk={r[0] for r in cur.execute("select distinct ticker from eerr_externos")}
alias={'BOLT':'BOLT_2','PATA':'PATA_2'}
final=[]
for eid,tk,berr,cerr,bok,cok in val_rows:
    verif_ext = (alias.get(tk,tk) in ext_tk) or (tk in ext_tk)
    if verif_ext: nivel='verificado-externo'
    elif bok and cok: nivel='identidades-cierran'
    elif bok or cok: nivel='parcial-interno'
    else: nivel='sin-verificar'
    final.append((eid,tk,berr,cerr,bok,cok,nivel))
cur.executemany("insert or replace into entity_validacion values(?,?,?,?,?,?,?)",final)
con.commit()
print(f'fact_financials: {len(INS)} filas desde cnv_reextract | {len(ents)} entidades')
from collections import Counter
c=Counter(r[6] for r in final)
print('\\n== nivel de certeza (56 byma_only) ==')
for k in ['verificado-externo','identidades-cierran','parcial-interno','sin-verificar']:
    print(f'   {k:>22}: {c.get(k,0)}')
print('\\n== identidades: balance / cascada que cierran ==')
print(f'   balance (A=P+PN) cierra: {sum(r[4] for r in final)}/{len(final)}')
print(f'   cascada (GP=Rev-COGS) cierra: {sum(r[5] for r in final)}/{len(final)}')
print('\\n== las que NO cierran balance (revisar) ==')
for eid,tk,berr,cerr,bok,cok,nivel in sorted(final,key=lambda x:-(x[2] or 0))[:10]:
    if not bok: print(f'   {tk}: err balance={berr*100:.0f}%' if berr is not None else f'   {tk}: sin datos de balance')
con.close()
