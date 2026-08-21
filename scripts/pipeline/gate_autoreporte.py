# -*- coding: utf-8 -*-
"""
GATE de sanitización: cruza NUESTRO ROE calculado (anual) contra el ROE que la empresa
DECLARA en su propio balance (código 8000009 = cnv_roe). No depende de fuentes externas.
Marca automáticamente las empresas donde nuestro cálculo NO coincide con el auto-reporte.
"""
import sqlite3
import os as _os
con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()
def near(a,b,t=0.20): return isinstance(a,(int,float)) and isinstance(b,(int,float)) and b!=0 and abs(a-b)<=abs(b)*t+0.01
by=cur.execute("select entity_id,cuit,ticker_canonico,fy_end_month from dim_entity where grupo='byma_only' and cuit is not null").fetchall()
cur.executescript("DROP TABLE IF EXISTS gate_roe; CREATE TABLE gate_roe(entity_id INTEGER PRIMARY KEY, ticker TEXT, roe_nuestro REAL, roe_autoreporte REAL, estado TEXT);")
rows=[]
ok=disc=sin=0
for eid,cuit,tk,fy in by:
    fy=fy or 12
    def ser(c): return dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto=?",(cuit,c)).fetchall())
    ni=ser('net_income'); eq=ser('equity'); roe=ser('cnv_roe')
    P=[p for p in sorted(set(ni)&set(eq)&set(roe)) if int(p[5:7])==fy]
    P=P[-1] if P else None
    if not P or not eq.get(P):
        rows.append((eid,tk,None,None,'sin-autoreporte')); sin+=1; continue
    our=ni[P]/eq[P]; self_=roe[P]
    est='verificado' if near(our,self_) else 'DISCREPANCIA'
    if est=='verificado': ok+=1
    else: disc+=1
    rows.append((eid,tk,our,self_,est))
cur.executemany("insert or replace into gate_roe values(?,?,?,?,?)",rows)
con.commit()
print(f'== GATE auto-reporte (nuestro ROE vs ROE del balance) — 56 byma_only ==')
print(f'   verificado (coinciden): {ok}')
print(f'   DISCREPANCIA (se marcan): {disc}')
print(f'   sin auto-reporte usable: {sin}')
print(f'\\n== las DISCREPANCIA (a revisar, con motivo cuantificado) ==')
for eid,tk,our,self_,est in rows:
    if est=='DISCREPANCIA':
        print(f'   {tk:>7}: nuestro={our*100:6.1f}%  balance={self_*100:6.1f}%')
con.close()
