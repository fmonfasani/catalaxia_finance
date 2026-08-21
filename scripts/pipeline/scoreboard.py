# -*- coding: utf-8 -*-
"""Tablero: de-acumula cnv_reextract (NUEVO consolidado) y compara vs investing por empresa."""
import sqlite3
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
def mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
def decum(serie,fy):
    pes=sorted(serie); std={}
    for pe in pes:
        q=4-((fy-int(pe[5:7]))%12)//3
        if q==1: std[pe]=serie[pe]
        else:
            prev=[p for p in pes if p<pe and mb(p,pe)==3]
            std[pe]=serie[pe]-serie[prev[-1]] if prev else None
    return std
def near(a,b,t=0.12): return isinstance(a,(int,float)) and isinstance(b,(int,float)) and abs(a-b)<=abs(b)*t+1

# cobertura general
tot=cur.execute("select count(distinct cuit) from cnv_reextract").fetchone()[0]
print(f'cnv_reextract: {tot} empresas con datos consolidados limpios\n')

eer=[r[0] for r in cur.execute("select distinct ticker from eerr_externos").fetchall()]
alias={'BOLT_2':'BOLT','PATA_2':'PATA'}
print(f'{"ticker":>7} | {"REV rec":>16} | {"NI rec":>16} | veredicto')
print('-'*70)
conf=parc=marc=0
for tk in sorted(eer):
    dtk=alias.get(tk,tk)
    e=cur.execute("select cuit,fy_end_month from dim_entity where ticker_canonico=?",(dtk,)).fetchone()
    if not e: continue
    cuit,fy=e; fy=fy or 12
    res={}
    for canon,extc in [('revenue','Revenue'),('net_income','NetIncome')]:
        serie=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto=?",(cuit,canon)).fetchall())
        std=decum(serie,fy) if serie else {}
        ext=dict(cur.execute("select period_end,valor from eerr_externos where ticker=? and concepto=?",(tk,extc)).fetchall())
        common=[p for p in sorted(set(std)&set(ext)) if std.get(p) is not None]
        if not common: res[canon]=(None,None,None); continue
        pe=common[-1]; mn=std[pe]/1e6; ev=ext[pe]
        res[canon]=(near(mn,ev),mn,ev)
    r=res['revenue']; n=res['net_income']
    def cell(x):
        if not x or x[1] is None: return 'sin dato'.center(16)
        return f'{x[1]:,.0f}/{x[2]:,.0f} {"OK" if x[0] else "  "}'.rjust(16)
    okr=r[0]; okn=n[0]
    if okr and okn: verd='CONFIABLE'; conf+=1
    elif okr or okn: verd='PARCIAL'; parc+=1
    else: verd='MARCADA (revisar)'; marc+=1
    print(f'{tk:>7} | {cell(r)} | {cell(n)} | {verd}')
print(f'\n=== TABLERO (20 con referencia investing) ===')
print(f'  CONFIABLE (rev+ni): {conf}   PARCIAL: {parc}   MARCADA: {marc}')
print(f'  (antes de re-extraer: ~4/19 cascada, muchos corruptos)')
con.close()
