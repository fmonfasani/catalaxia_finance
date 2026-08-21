# -*- coding: utf-8 -*-
"""
FASE SEC — Extrae fundamentals SEC (facts) de los 12 ADR argentinos y valida ROE
contra investing. Segunda fuente independiente (misma moneda ARS para 10 de 12).
"""
import sqlite3, datetime as dt
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
def days(a,b):
    try: return (dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days
    except: return None
adrs=cur.execute("select ticker_canonico,cik from dim_entity where grupo='adr' and cik is not null order by ticker_canonico").fetchall()
extROE={t:v for t,v in cur.execute("select ticker,roe from ratios_externos")}
print(f'{"tk":>7} | {"SEC ROE":>8} {"unit":>4} {"invest":>7} | veredicto')
print('-'*54)
def near(a,b,t=0.25): return isinstance(a,(int,float)) and isinstance(b,(int,float)) and b!=0 and abs(a-b)<=abs(b)*t
ok=n=0
for tk,cik in adrs:
    # NetIncome anual (span ~365d) mas reciente; probar ARS luego USD
    best=None
    for unit in ('ARS','USD'):
        rows=cur.execute("""select period_start,period_end,val from facts where cik=? and concepto='NetIncome'
            and unit=? and period_start is not null order by period_end desc""",(cik,unit)).fetchall()
        ann=[(pe,v) for ps,pe,v in rows if days(ps,pe) and 340<=days(ps,pe)<=380]
        if ann:
            eq=cur.execute("""select val from facts where cik=? and concepto='Equity' and unit=?
                order by period_end desc limit 1""",(cik,unit)).fetchone()
            if eq and eq[0]: best=(ann[0][1]/eq[0], unit); break
    inv=extROE.get(tk)
    inv_f=inv/100 if inv is not None else None
    if best:
        roe,unit=best
        v=''
        if inv_f is not None:
            n+=1; good=near(roe,inv_f); ok+=good; v='OK coincide' if good else 'DIF'
        invs=f'{inv:.1f}%' if inv is not None else '-'
        print(f'{tk:>7} | {roe*100:7.1f}% {unit:>4} {invs:>7} | {v}')
    else:
        sd='sin dato SEC'
        print(f'{tk:>7} | {sd:>13}')
print(f'\\nSEC ROE coincide con investing: {ok}/{n}')
con.close()
