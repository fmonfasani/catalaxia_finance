# -*- coding: utf-8 -*-
"""
f5_screener — construye screener_gold: UNA fila por empresa con sus ratios + el NIVEL DE
CERTIFICACIÓN adjunto. Es el producto: "no te damos datos, te damos datos que podés probar".

DOS ventanas por empresa (byma_only):
  - ANUAL (certificado): ratios desde el mismo cierre de ejercicio que certificó validar_suite
    (dato validado, escala consistente). Es el sello.
  - TTM (comparativo): últimos 4 trimestres standalone + balance más reciente. Comparable 1:1 con
    investing (que reporta TTM). NO certificado — a veces el trimestre reciente trae error de escala
    (ej. CVH ×1e6) → el guard lo marca y se cae al anual.
PER estilo IAMC: solo si las ganancias del período son positivas. Guards: SANE por ratio +
cross-check de market cap (2 fuentes). flag > fabricar. Idempotente.
"""
import sqlite3
import os as _os
con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()

RATIOS=['per','p_book','p_sales','roe','roa','margen_neto','margen_bruto',
        'margen_operativo','margen_ebitda','deuda_ebitda','ev_ebitda']
MCAP_DEP={'per','p_book','p_sales','ev_ebitda'}
SANE={'per':(0,1000),'p_book':(0.03,200),'p_sales':(0.02,100),'roe':(-3,3),'roa':(-3,3),
      'ev_ebitda':(-100,500),'deuda_ebitda':(-60,100),
      'margen_neto':(-3,2),'margen_bruto':(-3,1.5),'margen_operativo':(-3,2),'margen_ebitda':(-3,2)}
def sane(ratio,val):
    if val is None: return None,True
    lo,hi=SANE.get(ratio,(-1e18,1e18))
    return (val,True) if lo<=val<=hi else (None,False)

def pick_mc(mc_scr,mc_der,eq):
    """Mejor market cap: el feed real (screener) salvo que sea implausible vs el patrimonio
    (feed roto, ej. HAVA/CELU con mcap≈0) → ahí el derivado (precio×NI/EPS)."""
    if mc_scr and eq and eq>0:
        r=mc_scr/eq
        return mc_scr if 0.02<=r<=50 else (mc_der or mc_scr)
    return mc_scr or mc_der

def ratios_from(ni,eq,assets,rev,gp,oi,ebitda,cash,debt,mcap,esfin):
    """Fórmula única de ratios (la usan tanto la ventana ANUAL como la TTM)."""
    R={}
    if eq and eq>0:
        if ni is not None: R['roe']=ni/eq
        if mcap: R['p_book']=mcap/eq
    if assets and assets>0 and ni is not None: R['roa']=ni/assets
    if rev and rev>0:
        if ni is not None: R['margen_neto']=ni/rev
        if gp is not None and not esfin: R['margen_bruto']=gp/rev
        if oi is not None: R['margen_operativo']=oi/rev
        if ebitda is not None and not esfin: R['margen_ebitda']=ebitda/rev
        if mcap: R['p_sales']=mcap/rev
    if ebitda and ebitda>0 and not esfin:
        if debt is not None: R['deuda_ebitda']=debt/ebitda
        if mcap: R['ev_ebitda']=(mcap+(debt or 0)-(cash or 0))/ebitda
    if mcap and ni and ni>0: R['per']=mcap/ni   # = precio/EPS (IAMC: solo si ganancia>0)
    return R

# --- ventana ANUAL: cierre de ejercicio certificado (cnv_reextract) ---
CONCEPTOS=['revenue','gross_profit','operating_income','ebitda','net_income',
    'assets','equity','cash','debt_current','debt_noncurrent']
def certperiod_ratios(cuit,fy,mc_scr,mc_der,esfin):
    fy=fy or 12
    D={c:dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto=?",(cuit,c))) for c in CONCEPTOS}
    cand=[p for p in sorted(set(D['assets'])&set(D['equity'])) if int(p[5:7])==fy]
    if not cand: return None,{},None
    P=cand[-1]
    def v(c): return D[c].get(P)
    dc,dnc=v('debt_current'),v('debt_noncurrent')
    debt=(dc or 0)+(dnc or 0) if (dc is not None or dnc is not None) else None
    mcap=pick_mc(mc_scr,mc_der,v('equity'))
    return P,ratios_from(v('net_income'),v('equity'),v('assets'),v('revenue'),v('gross_profit'),
                         v('operating_income'),v('ebitda'),v('cash'),debt,mcap,esfin),mcap

# --- ventana TTM: últimos 4 trimestres standalone (fact_financials) + balance más reciente ---
def _mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
def ttm_flow(eid,c,recpam=1):
    q=cur.execute("select period_end,valor from fact_financials where entity_id=? and concepto_canonico=? "
        "and period_type='Q' and incluye_recpam=? order by period_end desc limit 4",(eid,c,recpam)).fetchall()
    if len(q)<4 or _mb(q[3][0],q[0][0])!=9: return None,None
    return sum(v for _,v in q),q[0][0]
def ttm_snap(eid,c):
    r=cur.execute("select valor from fact_financials where entity_id=? and concepto_canonico=? "
        "order by period_end desc limit 1",(eid,c)).fetchone()
    return r[0] if r else None
def ttm_ratios(eid,mc_scr,mc_der,esfin):
    ni,pe=ttm_flow(eid,'net_income')
    if ni is None: return None,{}
    rev,_=ttm_flow(eid,'revenue'); gp,_=ttm_flow(eid,'gross_profit')
    oi,_=ttm_flow(eid,'operating_income'); ebitda,_=ttm_flow(eid,'ebitda')
    eq=ttm_snap(eid,'equity')
    dc,dnc=ttm_snap(eid,'debt_current'),ttm_snap(eid,'debt_noncurrent')
    debt=(dc or 0)+(dnc or 0) if (dc is not None or dnc is not None) else None
    return pe,ratios_from(ni,eq,ttm_snap(eid,'assets'),rev,gp,oi,ebitda,
                          ttm_snap(eid,'cash'),debt,pick_mc(mc_scr,mc_der,eq),esfin)

# --- catálogos ---
niv={t:(n,ok,ap,f) for t,n,ok,ap,f in
     cur.execute("select ticker,nivel,checks_ok,checks_aplicables,fallidos from screener_nivel")}
ent={t:(eid,nombre,grupo,esfin,cuit,fy) for t,eid,nombre,grupo,esfin,cuit,fy in
     cur.execute("select ticker_canonico,entity_id,nombre,grupo,es_financiera,cuit,fy_end_month from dim_entity")}
mcapd={t:m for t,m in cur.execute("select ticker,mcap from market_cap_derivado")}
scr={t:(prec,mcap,sector,precio_ars) for t,prec,mcap,sector,precio_ars in
     cur.execute("select ticker,Precio,MarketCapUSD,sector,precio_ars from screener")}

cur.executescript("""
DROP TABLE IF EXISTS screener_gold;
CREATE TABLE screener_gold(
  ticker TEXT PRIMARY KEY, nombre TEXT, grupo TEXT, sector TEXT, es_financiera INT,
  periodo_cierre TEXT, precio REAL, precio_ars REAL, market_cap REAL,
  per REAL, p_book REAL, p_sales REAL, roe REAL, roa REAL,
  margen_neto REAL, margen_bruto REAL, margen_operativo REAL, margen_ebitda REAL,
  deuda_ebitda REAL, ev_ebitda REAL,
  nivel_certificacion TEXT, checks_ok INT, checks_aplicables INT, checks_fallidos TEXT,
  mcap_confiable INT, ratios_no_confiables TEXT,
  ttm_cierre TEXT, per_ttm REAL, p_book_ttm REAL, p_sales_ttm REAL, roe_ttm REAL, roa_ttm REAL,
  margen_neto_ttm REAL, margen_bruto_ttm REAL, margen_operativo_ttm REAL, margen_ebitda_ttm REAL,
  deuda_ebitda_ttm REAL, ev_ebitda_ttm REAL, ttm_no_confiables TEXT);
""")

def aplicar_guard(R,mcap_conf):
    """Devuelve ({ratio:valor_limpio}, [flageados]). Solo oculta valores INSANOS (SANE); el
    cross-check de market cap queda como info en mcap_confiable, no oculta ratios sanos."""
    fl=[]; V={}
    for x in RATIOS:
        val,okk=sane(x,R.get(x))
        if not okk: fl.append(x)
        V[x]=val
    return V,fl

filas=ttm_ok=0
for tk,(eid,nombre,grupo,esfin,cuit,fy) in ent.items():
    if grupo!='byma_only': continue      # ADR y sp500 se integran desde SEC (f6_sec)
    prec,mcap_scr,sector,precio_ars=scr.get(tk,(None,None,None,None))
    mc_der=mcapd.get(tk)
    ratio_mc=(mc_der/mcap_scr) if (mc_der and mcap_scr and mcap_scr>0) else None
    mcap_conf=1 if (ratio_mc is not None and 0.33<=ratio_mc<=3.0) else 0  # info: 2 fuentes coinciden
    P,R,mc=certperiod_ratios(cuit,fy,mcap_scr,mc_der,esfin)
    if P is None: continue
    V,flagged=aplicar_guard(R,mcap_conf)
    # ventana TTM
    Ptt,Rtt=ttm_ratios(eid,mcap_scr,mc_der,esfin)
    Vtt,flag_tt=aplicar_guard(Rtt,mcap_conf) if Rtt else ({x:None for x in RATIOS},[])
    if Ptt and any(Vtt[x] is not None for x in RATIOS): ttm_ok+=1
    lvl=niv.get(tk,('sin-datos','','',''))[0]
    ok,ap,fall=niv.get(tk,('',None,None,''))[1:]
    cur.execute("insert into screener_gold values("+ "?,"*38 +"?)",
        (tk,nombre,grupo,sector,esfin,P,prec,precio_ars,mc,
         V['per'],V['p_book'],V['p_sales'],V['roe'],V['roa'],
         V['margen_neto'],V['margen_bruto'],V['margen_operativo'],V['margen_ebitda'],
         V['deuda_ebitda'],V['ev_ebitda'],
         lvl,ok,ap,fall,mcap_conf,','.join(flagged),
         Ptt,Vtt['per'],Vtt['p_book'],Vtt['p_sales'],Vtt['roe'],Vtt['roa'],
         Vtt['margen_neto'],Vtt['margen_bruto'],Vtt['margen_operativo'],Vtt['margen_ebitda'],
         Vtt['deuda_ebitda'],Vtt['ev_ebitda'],','.join(flag_tt)))
    filas+=1
con.commit()

from collections import Counter
c=Counter(r[0] for r in cur.execute("select nivel_certificacion from screener_gold"))
print(f'screener_gold: {filas} empresas byma  |  con ventana TTM utilizable: {ttm_ok}')
for k,n in sorted(c.items(),key=lambda x:-x[1]): print(f'  {k:>18}: {n}')
print('\nTop 8 ROE — Anual (cert.) vs TTM (comparable a investing):')
for tk,roe,roett in cur.execute("select ticker,roe,roe_ttm from screener_gold "
    "where nivel_certificacion='CERTIFICADO' and roe is not null order by roe desc limit 8"):
    rt=f'{roett*100:5.1f}%' if roett is not None else '   —'
    print(f'  {tk:>7}  anual {roe*100:5.1f}%   TTM {rt}')
con.close()
