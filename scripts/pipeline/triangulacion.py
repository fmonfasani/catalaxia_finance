# -*- coding: utf-8 -*-
"""Triangulación ROE: SEC vs CNV re-extraído vs investing, ALINEADO por ejercicio anual."""
import sqlite3, datetime as dt
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
def days(a,b):
    try: return (dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days
    except: return None
def sec_annual(cik):
    """(roe, año, unit) del último anual SEC (NI anual / equity a esa fecha)."""
    for unit in ('ARS','USD'):
        rows=cur.execute("select period_start,period_end,val from facts where cik=? and concepto='NetIncome' and unit=? and period_start is not null order by period_end desc",(cik,unit)).fetchall()
        ann=[(pe,v) for ps,pe,v in rows if days(ps,pe) and 340<=days(ps,pe)<=380]
        if not ann: continue
        pe_ni,ni=ann[0]
        eq=cur.execute("select period_end,val from facts where cik=? and concepto='Equity' and unit=? and period_end<=? order by period_end desc limit 1",(cik,unit,pe_ni)).fetchone()
        if eq and eq[1]: return ni/eq[1], pe_ni[:4], unit
    return None,None,None
def cnv_roe_year(cuit,fy,year):
    """ROE CNV del ejercicio 'year' (NI YTD a fin de ejercicio / equity)."""
    fy=fy or 12
    ni=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='net_income'",(cuit,)))
    eq=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='equity'",(cuit,)))
    cand=[p for p in sorted(set(ni)&set(eq)) if int(p[5:7])==fy and p[:4]==year]
    if not cand: return None
    P=cand[-1]
    return ni[P]/eq[P] if eq[P] else None
adrs=cur.execute("select ticker_canonico,cik,cuit,fy_end_month from dim_entity where grupo='adr' and cik is not null order by ticker_canonico").fetchall()
extROE={t:v for t,v in cur.execute('select ticker,roe from ratios_externos')}
def pc(x): return f'{x*100:6.1f}%' if isinstance(x,(int,float)) else '   -  '
print(f'{"tk":>7} | {"año":>4} {"SEC":>7} {"CNV":>7} {"invest":>7} | veredicto')
print('-'*58)
ok=n=0
for tk,cik,cuit,fy in adrs:
    s,year,unit=sec_annual(cik)
    c=cnv_roe_year(cuit,fy,year) if year else None
    inv=extROE.get(tk); invf=inv/100 if inv is not None else None
    v=''
    if s is not None and c is not None:
        n+=1; good=abs(s-c)<=abs(c)*0.30+0.02; ok+=good; v='OK SEC=CNV' if good else 'DIF'
    print(f'{tk:>7} | {(year or "-"):>4} {pc(s)} {pc(c)} {pc(invf)} | {v}')
print(f'\nSEC=CNV (mismo ejercicio, 2 fuentes independientes): {ok}/{n}')
con.close()
