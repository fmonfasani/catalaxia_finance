# -*- coding: utf-8 -*-
"""
f6_sec — integra las 499 US (sp500) + 16 ADR al screener_gold desde SEC EDGAR (tabla facts).
Ratios desde el último ejercicio anual (10-K, span ~365d) + balance de cierre alineado.
Certificación SEC:
  - identidad independiente Activo = Pasivo + PN (cuando Liabilities se reporta aparte y alinea),
  - ancla de mercado: market cap yfinance vs derivado (precio × acciones SEC) — 2 fuentes,
  - ADR: además ROE SEC ≈ ROE CNV (2 reguladores) → 'triangulado-SEC'.
Mismos guards que f5 (SANE + mcap cross-check). APPEND a screener_gold (corre DESPUÉS de f5).
Idempotente (borra sus propias filas sp500/adr antes de insertar).
"""
import sqlite3, datetime as dt
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
def days(a,b):
    try: return (dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days
    except: return None

SANE={'per':(0,1000),'p_book':(0.03,200),'p_sales':(0.02,100),'roe':(-3,3),'roa':(-3,3),
      'ev_ebitda':(-100,500),'deuda_ebitda':(-60,100),
      'margen_neto':(-3,2),'margen_bruto':(-3,1.5),'margen_operativo':(-3,2),'margen_ebitda':(-3,2)}
MCAP_DEP={'per','p_book','p_sales','ev_ebitda'}
RATIOS=list(SANE)
def sane(r,v):
    if v is None: return None,True
    lo,hi=SANE[r]; return (v,True) if lo<=v<=hi else (None,False)

FLOWS=['Revenue','NetIncome','GrossProfit','OperatingIncome','DA','EBIT','PretaxIncome']
STOCKS=['Assets','Equity','Liabilities','Cash','Debt']
def annual(rc,c):
    """(period_end,val) del anual más reciente (span 350-380d, último filed)."""
    best=None
    for ps,pe,val,filed in rc.get(c,()):
        d=days(ps,pe)
        if d and 350<=d<=380 and (best is None or (pe,filed)>(best[0],best[2])):
            best=(pe,val,filed)
    return (best[0],best[1]) if best else (None,None)
def stock_at(rc,c,P):
    """valor de un stock en el cierre P (exacto si existe, si no el más cercano<=P), último filed."""
    ex=[(pe,val,filed) for ps,pe,val,filed in rc.get(c,()) if pe==P]
    if ex: return max(ex,key=lambda x:x[2])[1]
    le=[(pe,val,filed) for ps,pe,val,filed in rc.get(c,()) if pe<=P]
    if le: return max(le,key=lambda x:(x[0],x[2]))[1]
    al=list(rc.get(c,()))
    return max(al,key=lambda x:(x[1],x[3]))[2] if al else None
def snap(rc,c):
    al=rc.get(c,())
    return max(al,key=lambda x:(x[1],x[3]))[2] if al else None   # (ps,pe,val,filed): último pe, val

universe=cur.execute("select ticker_canonico,cik,grupo,es_financiera,nombre,cuit,fy_end_month "
    "from dim_entity where grupo in ('sp500','adr') and cik is not null").fetchall()
scr={t:(prec,mcap,sector,pa,ccl) for t,prec,mcap,sector,pa,ccl in
     cur.execute("select ticker,Precio,MarketCapUSD,sector,precio_ars,ccl from screener")}

# CNV anual (ARS) para triangular ADR: ROE del ejercicio, ALINEADO al año del anual SEC
def cnv_roe(cuit,fy,year=None):
    fy=fy or 12
    ni=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='net_income'",(cuit,)))
    eq=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='equity'",(cuit,)))
    cand=[p for p in sorted(set(ni)&set(eq)) if int(p[5:7])==fy and (year is None or p[:4]==year)]
    if not cand: return None
    P=cand[-1]; return ni[P]/eq[P] if eq[P] else None

cur.execute("delete from screener_gold where grupo in ('sp500','adr')")
CONC=FLOWS+STOCKS+['EPS_diluted','EPS_basic','SharesOutstanding']
ins=0
for tk,cik,grupo,esfin,nombre,cuit,fy in universe:
    rows=cur.execute("select concepto,period_start,period_end,val,filed from facts where cik=? and concepto is not null",(cik,)).fetchall()
    rc={}
    for c,ps,pe,val,filed in rows:
        if c in CONC and pe: rc.setdefault(c,[]).append((ps,pe,val,filed or pe))
    Pann,rev=annual(rc,'Revenue')
    Pni,ni=annual(rc,'NetIncome')
    P=Pann or Pni
    if P is None or ni is None: continue
    gp=annual(rc,'GrossProfit')[1]; oi=annual(rc,'OperatingIncome')[1]
    da=annual(rc,'DA')[1]; eps=annual(rc,'EPS_diluted')[1] or annual(rc,'EPS_basic')[1]
    equity=stock_at(rc,'Equity',P); assets=stock_at(rc,'Assets',P)
    liab=stock_at(rc,'Liabilities',P); cash=stock_at(rc,'Cash',P); debt=stock_at(rc,'Debt',P)
    prec,mcap_scr,sector,precio_ars,ccl=scr.get(tk,(None,None,None,None,None))
    if grupo=='adr':
        # market cap en la MONEDA DEL BALANCE (evita mezclar USD/ARS): acciones = NI/EPS (SEC),
        # × precio local BYMA (precio_ars) si el balance está en ARS, o su equiv. USD (÷CCL) si en USD.
        equ=cur.execute("select unit from facts where cik=? and concepto='Equity' order by period_end desc, filed desc limit 1",(cik,)).fetchone()
        eq_unit=equ[0] if equ else 'ARS'
        sh=(ni/eps) if (eps and eps!=0) else None
        # si no podemos armar un mcap en la MISMA moneda del balance, mejor SIN dato (no mezclar USD/ARS)
        if sh and precio_ars and (eq_unit=='ARS' or ccl):
            mc=sh*precio_ars if eq_unit=='ARS' else sh*precio_ars/ccl
            mcap_conf=1
        else:
            mc=None; mcap_conf=0
    else:
        shares=snap(rc,'SharesOutstanding')
        mc_der=prec*shares if (prec and shares) else None
        mc=mc_der or mcap_scr
        ratio_mc=(mc_der/mcap_scr) if (mc_der and mcap_scr and mcap_scr>0) else None
        mcap_conf=1 if (ratio_mc is not None and 0.33<=ratio_mc<=3.0) else 0
    ebitda=(oi+da) if (oi is not None and da is not None) else None
    R={}
    if equity and equity>0:
        R['roe']=ni/equity;  R['p_book']=mc/equity if mc else None
    if assets and assets>0: R['roa']=ni/assets
    if rev and rev>0:
        R['margen_neto']=ni/rev
        if gp is not None and not esfin: R['margen_bruto']=gp/rev
        if oi is not None: R['margen_operativo']=oi/rev
        if ebitda is not None and not esfin: R['margen_ebitda']=ebitda/rev
        if mc: R['p_sales']=mc/rev
    if ebitda and ebitda>0 and not esfin:
        if debt is not None: R['deuda_ebitda']=debt/ebitda
        if mc: R['ev_ebitda']=(mc+(debt or 0)-(cash or 0))/ebitda
    if mc and ni and ni>0: R['per']=mc/ni   # = precio/EPS, en moneda consistente con el balance
    # identidad independiente Activo = Pasivo + PN (solo si Liab reportado y alinea)
    ident=None
    if assets and liab is not None and equity is not None:
        ident=abs(assets-(liab+equity))<=abs(assets)*0.03
    # nivel
    ratios_core_ok=all(sane(k,R.get(k))[1] for k in ('roe','roa','margen_neto'))
    if grupo=='adr':
        cr=cnv_roe(cuit,fy,P[:4]); tri=(cr is not None and R.get('roe') is not None and abs(R['roe']-cr)<=abs(cr)*0.30+0.02)
        nivel='triangulado-SEC' if tri else ('CERTIFICADO-SEC' if (ident and mcap_conf) else 'SEC-ok')
    else:
        nivel='CERTIFICADO-SEC' if (ident and mcap_conf and ratios_core_ok) else 'SEC-ok'
    ncheck=sum(x for x in [bool(ident), bool(mcap_conf), bool(ratios_core_ok)])
    flagged=[]
    def g(x):
        v,ok=sane(x,R.get(x))   # solo oculta INSANOS; mcap_confiable queda como info
        if not ok: flagged.append(x)
        return v
    V={x:g(x) for x in RATIOS}
    cur.execute("insert into screener_gold values("+"?,"*38+"?)",
        (tk,nombre,grupo,sector,esfin,P,prec,None,mc,
         V['per'],V['p_book'],V['p_sales'],V['roe'],V['roa'],
         V['margen_neto'],V['margen_bruto'],V['margen_operativo'],V['margen_ebitda'],
         V['deuda_ebitda'],V['ev_ebitda'],
         nivel,ncheck,3,'',mcap_conf,','.join(flagged),
         None,None,None,None,None,None,None,None,None,None,None,None,''))  # TTM no aplica a US (anual SEC ya reciente)
    ins+=1
con.commit()
from collections import Counter
c=Counter(r[0] for r in cur.execute("select nivel_certificacion from screener_gold where grupo in ('sp500','adr')"))
print(f'f6_sec: {ins} empresas SEC integradas (sp500+adr)')
for k,n in sorted(c.items(),key=lambda x:-x[1]): print(f'  {k:>18}: {n}')
tot=cur.execute("select count(*) from screener_gold").fetchone()[0]
print(f'screener_gold total ahora: {tot}')
print('\nTop 10 ROE US CERTIFICADO-SEC (con PER sano):')
for tk,nombre,roe,per,pb in cur.execute("select ticker,nombre,roe,per,p_book from screener_gold "
    "where grupo='sp500' and nivel_certificacion='CERTIFICADO-SEC' and roe is not null and per is not null "
    "order by roe desc limit 10"):
    print(f'  {tk:>6} ROE {roe*100:6.1f}%  PER {per:6.1f}  P/B {pb:5.1f}  {nombre[:34]}')
con.close()
