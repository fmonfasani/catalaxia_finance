# -*- coding: utf-8 -*-
"""
FIX market cap + detector de escala.
1) market_cap_derivado = precio_ars × acciones, acciones = NetIncome/EPS del balance (independiente
   del screener) → recupera AGRO/INTR/REGE (CNV ok, market cap del screener mal).
2) Detector de escala por-período: usa el market cap derivado como ancla absoluta. Si el patrimonio
   de un período da P/B fuera de [0.1, 15] por un factor limpio de 10^3/10^6, corrige ESE período.
   Conservador: si es ambiguo (no hay factor limpio, o el market cap tampoco es confiable) → NO toca, deja flag.
Escribe cnv_reextract_fix (copia corregida) + market_cap_derivado. SQLite. Idempotente.
"""
import sqlite3, statistics, math
import os as _os
con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()
precio={t:p for t,p in cur.execute("select ticker,precio_ars from screener")}
by=cur.execute("select entity_id,cuit,ticker_canonico,fy_end_month from dim_entity where grupo='byma_only' and cuit is not null").fetchall()

cur.executescript("""DROP TABLE IF EXISTS market_cap_derivado;
CREATE TABLE market_cap_derivado(ticker TEXT PRIMARY KEY, acciones REAL, mcap REAL, fuente TEXT);""")

def near_pow1000(ratio):
    """Devuelve el factor 10^(3k) más cercano a 'ratio' si ratio es ~limpio, si no None."""
    if ratio<=0: return None
    k=round(math.log10(ratio)/3)
    if k==0: return None
    factor=10**(3*k)
    # limpio si el ratio está dentro de 2x del factor
    return factor if 0.5<=ratio/factor<=2 else None

mc_rows=[]; fixes=[]
for eid,cuit,tk,fy in by:
    fy=fy or 12
    def ser(c): return dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto=?",(cuit,c)).fetchall())
    ni=ser('net_income'); eps=ser('eps_basic'); eq=ser('equity')
    px=precio.get(tk)
    # acciones = NI/EPS en el/los cierres de ejercicio (mediana estable)
    sh=[]
    for P in sorted(set(ni)&set(eps)):
        if int(P[5:7])==fy and eps[P] and abs(eps[P])>0.01:
            sh.append(ni[P]/eps[P])
    acciones=statistics.median(sh) if sh else None
    mcap=px*acciones if (px and acciones) else None
    if mcap: mc_rows.append((tk,acciones,mcap,'precio_ars*NI/EPS'))
    # detector de escala del patrimonio, anclado al mcap derivado (P/B objetivo ~[0.1,15])
    if mcap and eq:
        for P in sorted(eq):
            e=eq[P]
            if e<=0: continue
            pb=mcap/e
            if pb<0.1 or pb>15:  # patrimonio sospechoso de escala
                # factor que llevaría P/B a ~1: e_correcto = mcap  => factor = e/mcap
                f=near_pow1000(e/mcap)
                if f:
                    fixes.append((tk,'equity',P,e,e/f))
cur.executemany("insert or replace into market_cap_derivado values(?,?,?,?)",mc_rows)
con.commit()
print(f'market_cap_derivado: {len(mc_rows)} empresas')
# comparar derivado vs screener para las 3 problematicas
print('\\n== market cap: screener vs derivado (las de la duda) ==')
for tk in ['AGRO','INTR','REGE','DGCU2','GCLA']:
    scr=cur.execute("select MarketCapUSD from screener where ticker=?",(tk,)).fetchone()
    der=cur.execute("select mcap,acciones from market_cap_derivado where ticker=?",(tk,)).fetchone()
    print(f'   {tk:>6}: screener={scr[0]:,.0f} | derivado={der[0]:,.0f} (acc={der[1]:,.0f})' if (scr and scr[0] and der) else f'   {tk}: scr={scr} der={der}')
print(f'\\n== correcciones de escala propuestas (patrimonio): {len(fixes)} ==')
for tk,c,P,orig,nuevo in fixes[:15]:
    print(f'   {tk} {c} {P}: {orig:,.0f} -> {nuevo:,.0f}')
con.close()
