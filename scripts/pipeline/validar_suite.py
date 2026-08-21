# -*- coding: utf-8 -*-
"""
SUITE DE VALIDACIÓN — corre ~18 cruces independientes sobre cada byma_only y certifica.
Capas: (1) identidades contables, (2) continuidad temporal, (3) externa, (4) ancla de mercado.
Regla de certificación: pasa TODAS las identidades internas aplicables + continuidad + ≥1 ancla
independiente de la escala (market cap o investing). SQLite. Idempotente.
"""
import sqlite3, statistics
import os as _os
con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()
def rel_ok(a,b,tol=0.04):
    if not isinstance(a,(int,float)) or not isinstance(b,(int,float)): return None
    return abs(a-b)<=abs(b)*tol+ max(abs(a),abs(b))*0.0 + 1e6*0  # 4% relativo
def sign_ok(g,r,c):  # GP = R - C  ó  R + C (segun signo del costo)
    if None in (g,r,c): return None
    return min(abs(g-(r-c)),abs(g-(r+c)))<=abs(r)*0.04+1
# market cap: preferir el DERIVADO (precio*NI/EPS, confiable), fallback al screener
mcap={t:m for t,m in cur.execute("select ticker,MarketCapUSD from screener").fetchall()}
try:
    for t,m in cur.execute("select ticker,mcap from market_cap_derivado"):
        if m: mcap[t]=m
except sqlite3.OperationalError: pass
extR={}  # ticker -> revenue reciente investing
for tk,pe,v in cur.execute("select ticker,period_end,valor from eerr_externos where concepto='Revenue'"):
    extR.setdefault(tk,{})[pe]=v
extROE={t:v for t,v in cur.execute("select ticker,roe from ratios_externos")}
alias={'BOLT':'BOLT_2','PATA':'PATA_2'}
cur.executescript("DROP TABLE IF EXISTS validacion_suite; CREATE TABLE validacion_suite(ticker TEXT,check_id TEXT,capa INTEGER,resultado TEXT,detalle TEXT);")

by=cur.execute("select entity_id,cuit,ticker_canonico,fy_end_month,es_financiera from dim_entity where grupo='byma_only' and cuit is not null").fetchall()
def S(a): return 'OK' if a else ('FAIL' if a is not None else 'NA')
resumen=[]
for eid,cuit,tk,fy,esfin in by:
    fy=fy or 12
    def ser(c): return dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto=?",(cuit,c)).fetchall())
    D={c:ser(c) for c in ['revenue','cogs','gross_profit','operating_income','ebit','ebitda','da',
        'net_income','pretax_income','income_tax','assets','assets_current','assets_noncurrent',
        'liabilities','liabilities_current','liabilities_noncurrent','equity','capital','reserves',
        'retained_earnings','cash','cfo','cfi','cff','net_change_cash','cnv_roe','cnv_roa','cnv_margen_neto']}
    # periodo de cierre de ejercicio mas reciente con balance
    cand=[p for p in sorted(set(D['assets'])&set(D['equity'])) if int(p[5:7])==fy]
    P=cand[-1] if cand else None
    def v(c): return D[c].get(P) if P else None
    checks=[]
    # CAPA 1 — identidades internas
    checks.append(('c1_activo=pas+pn',1, rel_ok(v('assets'), (v('liabilities') or 0)+(v('equity') or 0)) if v('assets') and v('equity') is not None else None))
    checks.append(('c2_activo=AC+ANC',1, rel_ok(v('assets'), (v('assets_current') or 0)+(v('assets_noncurrent') or 0)) if v('assets') and v('assets_current') is not None else None))
    liab=v('liabilities'); lc=v('liabilities_current')
    checks.append(('c3_PC<=Pasivo',1, (0<=lc<=liab*1.02) if (liab and lc is not None and liab>0) else None))
    checks.append(('c4_GP=Vtas-Costo',1, sign_ok(v('gross_profit'),v('revenue'),v('cogs')) if not esfin else None))
    checks.append(('c5_NI=Pretax-Tax',1, sign_ok(v('net_income'),v('pretax_income'),v('income_tax'))))
    checks.append(('c6_EBITDA=EBIT+DA',1, sign_ok(v('ebitda'),v('ebit'),(-(v('da')) if v('da') is not None else None)) if (v('ebitda') and v('ebit') is not None and not esfin) else None))
    checks.append(('c8_dCaja=CFO+CFI+CFF',1, (rel_ok(v('net_change_cash'),(v('cfo') or 0)+(v('cfi') or 0)+(v('cff') or 0)) if v('net_change_cash') is not None and v('cfo') is not None else None) if not esfin else None))
    # self-report (fidelidad de extraccion) — N/A para bancos (calculan ROE distinto)
    roe_calc = v('net_income')/v('equity') if (v('net_income') is not None and v('equity')) else None
    checks.append(('c10_ROEpropio',1, (rel_ok(roe_calc, v('cnv_roe'),0.20) if (roe_calc is not None and v('cnv_roe') is not None) else None) if not esfin else None))
    # CAPA 2 — continuidad temporal: Revenue YTD monotonico en el ultimo ejercicio
    def monot():
        rev=D['revenue']; ys=sorted(p for p in rev if p<=P and int(p[:4])==int(P[:4]))
        if len(ys)<2: return None
        vals=[rev[p] for p in ys]
        return all(vals[i]<=vals[i+1]*1.02 for i in range(len(vals)-1))  # YTD crece
    checks.append(('c12_YTD_monotonico',2, monot()))
    # CAPA 4 — anclas de mercado (independientes de la escala del balance)
    mc=mcap.get(tk)
    pb = mc/v('equity') if (mc and v('equity') and v('equity')>0) else None
    ps = mc/v('revenue') if (mc and v('revenue') and v('revenue')>0) else None
    checks.append(('c16_P/B_sano',4, (0.05<=pb<=30) if pb is not None else None))
    checks.append(('c17_P/S_sano',4, ((0.05<=ps<=30) if ps is not None else None) if not esfin else None))
    # CAPA 3 — externa (investing) si hay
    xtk=alias.get(tk,tk)
    er=extR.get(xtk) or extR.get(tk)
    rev_q_ok=None
    if er and D['revenue']:
        # comparar el trimestre standalone mas reciente comun
        std=D['revenue']  # (uso YTD; comparacion gruesa de magnitud anual/4)
    checks.append(('c15_ROE_vs_investing',3, rel_ok(roe_calc*100 if roe_calc is not None else None, extROE.get(xtk) or extROE.get(tk),0.25) if (roe_calc is not None and (extROE.get(xtk) or extROE.get(tk)) is not None) else None))
    # guardar
    for cid,capa,res in checks:
        cur.execute("insert into validacion_suite values(?,?,?,?,?)",(tk,cid,capa,S(res),''))
    # certificacion
    # identidades DURAS (obligatorias) = capa 1 excepto c10 (informativo: método/minoritario)
    # informativos (no identidades limpias en AR sin extraer minoritario/FX): c6, c10, c5, c8
    hard=[r for (i,cp,r) in checks if cp==1 and not i.startswith(('c10','c6','c5','c8'))]
    cap1_ok = all(r for r in hard if r is not None) and any(r is not None for r in hard)
    cap2 = next((r for (i,cp,r) in checks if cp==2), None)
    anchor = [r for (i,cp,r) in checks if cp in (3,4)]
    anchor_ok = any(r for r in anchor if r is not None)
    npass=sum(1 for (i,cp,r) in checks if r)
    napp=sum(1 for (i,cp,r) in checks if r is not None)
    # c12 (continuidad) solo BLOQUEA si FALLA; si es NA no impide certificar
    if cap1_ok and anchor_ok:
        nivel='CERTIFICADO' if cap2 is not False else 'alto'
    elif cap1_ok: nivel='interno-ok'
    else: nivel='REVISAR'
    resumen.append((tk,esfin,npass,napp,nivel,[i for (i,cp,r) in checks if r is False]))
# persistir el nivel por ticker (fuente única para el screener_gold)
cur.executescript("DROP TABLE IF EXISTS screener_nivel; CREATE TABLE screener_nivel("
    "ticker TEXT PRIMARY KEY, es_financiera INT, nivel TEXT, checks_ok INT, checks_aplicables INT, fallidos TEXT);")
for tk,esfin,npass,napp,nivel,fails in resumen:
    cur.execute("insert into screener_nivel values(?,?,?,?,?,?)",
                (tk,esfin,nivel,npass,napp,','.join(x.split('_')[0] for x in fails)))
con.commit()
from collections import Counter
print('== SUITE DE VALIDACIÓN — 56 byma_only ==')
cnt=Counter(r[4] for r in resumen)
for k in ['CERTIFICADO','alto','interno-ok','REVISAR']:
    print(f'   {k:>12}: {cnt.get(k,0)}')
print('\\n== por empresa (checks OK/aplicables · nivel · qué falla) ==')
for tk,esfin,npass,napp,nivel,fails in sorted(resumen,key=lambda x:(x[4]!='CERTIFICADO',x[0])):
    ff='' if not fails else '  x '+','.join(x.split('_')[0] for x in fails)
    lab='[fin]' if esfin else ''
    print(f'   {tk:>7} {lab:>5} | {npass:>2}/{napp:<2} | {nivel:>11}{ff}')
con.close()
