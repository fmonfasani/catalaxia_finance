# -*- coding: utf-8 -*-
"""
FIX de escala anclado en EPS. El EPS viene por-acción SIN escala → acciones=NI/EPS deben ser
constantes. Si lo son (error per-documento limpio), corrige los períodos con escala equivocada.
Si las acciones saltan (corrupción no-uniforme, ej. GCDI) → NO toca (flag). Seguro por diseño.
Escribe en cnv_reextract. Idempotente-ish (guarda log de correcciones).
"""
import sqlite3, statistics, math
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
CONC=[r[0] for r in cur.execute("select distinct concepto from cnv_reextract")]
by=cur.execute("select cuit,ticker_canonico from dim_entity where grupo='byma_only' and cuit is not null").fetchall()
def cluster_mode(vals):
    logs=[math.log10(abs(v)) for v in vals if v]
    if not logs: return None
    # redondear a 0.5 y tomar la moda
    from collections import Counter
    c=Counter(round(l*2)/2 for l in logs)
    return c.most_common(1)[0]
fixed=[]
for cuit,tk in by:
    ni=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='net_income'",(cuit,)))
    eps=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='eps_basic'",(cuit,)))
    ass=dict(cur.execute("select period_end,valor from cnv_reextract where cuit=? and concepto='assets'",(cuit,)))
    shares={pe: ni[pe]/eps[pe] for pe in set(ni)&set(eps) if eps[pe] and abs(eps[pe])>0.01}
    if len(shares)<4: continue
    logsh=[math.log10(abs(s)) for s in shares.values() if s]
    med=statistics.median(logsh)
    ref=[l for l in logsh if abs(l-med)<0.5]
    # estable solo si la mayoría (>=65%) cae en el cluster central
    if len(ref)/len(logsh) < 0.65: continue      # no-uniforme (GCDI) -> skip
    # escala verdadera de assets: mediana de assets-log en periodos de la escala de referencia
    ref_periods=[pe for pe,s in shares.items() if s and abs(math.log10(abs(s))-med)<0.5]
    ref_assets=[math.log10(abs(ass[pe])) for pe in ref_periods if ass.get(pe)]
    if not ref_assets: continue
    true_alog=statistics.median(ref_assets)
    # corregir cada periodo cuyo assets-log difiera por multiplo limpio de 3 (x1000)
    for pe in list(ass):
        if not ass[pe]: continue
        delta=math.log10(abs(ass[pe]))-true_alog
        k=round(delta/3)
        if k!=0 and abs(delta-3*k)<0.7:   # factor limpio 10^(3k)
            factor=10**(3*k)
            for c in CONC:
                cur.execute("update cnv_reextract set valor=valor/? where cuit=? and concepto=? and period_end=?",(factor,cuit,c,pe))
            fixed.append((tk,pe,f'/{factor:.0e}'))
con.commit()
print(f'== fix de escala anclado en EPS: {len(fixed)} períodos corregidos ==')
from collections import Counter
for tk,n in Counter(f[0] for f in fixed).most_common():
    print(f'   {tk}: {n} períodos')
con.close()
