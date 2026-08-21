# -*- coding: utf-8 -*-
"""Arbitro: ROE propio (balance CNV, cierre de ejercicio) vs anual-nuestro vs investing."""
import sqlite3
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
alias={'BOLT':'BOLT_2','PATA':'PATA_2'}
extk={r[0] for r in cur.execute("select ticker from ratios_externos")}
def near(a,b,t=0.25): return isinstance(a,(int,float)) and isinstance(b,(int,float)) and b!=0 and abs(a-b)<=abs(b)*t
def pc(x): return f'{x*100:5.1f}%' if isinstance(x,(int,float)) else '  -  '
eer=[r[0] for r in cur.execute("select distinct ticker from eerr_externos").fetchall()]
print(f'{"tk":>7} | {"PROPIO":>7} {"nuestro":>7} {"invest":>7} | veredicto')
print('-'*62)
cnt={'ok':0,'inv_desv':0,'revisar':0,'sin_arb':0}
for tk in sorted(eer):
    dtk=alias.get(tk,tk)
    e=cur.execute("select entity_id,cuit,fy_end_month from dim_entity where ticker_canonico=?",(dtk,)).fetchone()
    if not e: continue
    eid,cuit,fy=e; fy=fy or 12
    def ser(c): return dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto=?",(cuit,c)).fetchall())
    ni=ser('net_income'); eq=ser('equity'); roe=ser('cnv_roe')
    # periodo de cierre de ejercicio mas reciente con los 3 datos
    P=[p for p in sorted(set(ni)&set(eq)) if int(p[5:7])==fy]
    P=P[-1] if P else None
    self_roe = roe.get(P) if (P and P in roe) else (roe[max(roe)] if roe else None)
    ann = ni[P]/eq[P] if (P and eq.get(P)) else None
    exr=cur.execute("select roe from ratios_externos where ticker=?",(dtk if dtk in extk else tk,)).fetchone()
    inv=exr[0]/100 if exr and exr[0] is not None else None
    v='sin arbitro';
    if self_roe is not None and inv is not None:
        if near(self_roe,inv):
            v='OK nosotros bien' if near(ann,inv) else 'propio=invest, metodo nuestro off'
            cnt['ok' if near(ann,inv) else 'revisar']+=1
        elif near(ann,self_roe):
            v='-> INVESTING desviado (propio=nuestro)'; cnt['inv_desv']+=1
        else:
            v='revisar (3 distintos)'; cnt['revisar']+=1
    else: cnt['sin_arb']+=1
    print(f'{tk:>7} | {pc(self_roe)} {pc(ann)} {pc(inv)} | {v}')
print('\n== resumen ==')
for k,val in cnt.items(): print(f'  {k}: {val}')
con.close()
