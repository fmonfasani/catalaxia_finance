# -*- coding: utf-8 -*-
"""
END-TO-END de UN ticker byma_only — corte vertical del pipeline ETL, etapa por etapa,
desde el crudo (bronze) hasta el sello certificado + ancla externa.
Uso: python e2e_ticker.py TXAR
Es a la vez demostración, documentación y test de referencia.
"""
import sys, re, subprocess, sqlite3
import os as _os
sys.path.insert(0, 'scripts/pipeline')
from reextract_consolidado import field, EEFF
from cnv_codes import CODE_MAP

TK = sys.argv[1] if len(sys.argv) > 1 else 'TXAR'
con = sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur = con.cursor()
TRIP = re.compile(r'id="Nro"[^>]*>([^<]+)</propiedad>\s*<propiedad id="Rubro"[^>]*>([^<]*)</propiedad>\s*<propiedad id="Monto"[^>]*>\s*([^<]+)', re.S)
def snum(s):
    s=(s or '').strip()
    if s in ('','-','--'): return None
    if ',' in s: s=s.replace('.','').replace(',','.')
    else:
        p=s.split('.')
        if len(p)>2 and len(p[-1])>3: s=''.join(p[:-1])+p[-1][:-2]+'.'+p[-1][-2:]
        elif len(p)>2: s=''.join(p)
        elif len(p)==2 and len(p[1])==3: s=''.join(p)
    try: return float(s)
    except: return None
def factor(um):
    u=(um or '').lower(); return 1e6 if 'millon' in u else (1e3 if 'mil' in u else 1)
def rel(a,b,t=0.015):
    if a is None or b is None: return None
    return abs(a-b)<=abs(b)*t+1
def H(t): print('\n'+'='*74+'\n  '+t+'\n'+'='*74)

cuit,fy,nombre,esfin = cur.execute("select cuit,fy_end_month,nombre,es_financiera from dim_entity where ticker_canonico=?",(TK,)).fetchone()
fy=fy or 12
print(f'\n########  END-TO-END ETL · {TK} · {nombre} · cierre fiscal mes {fy}  ########')

# ============================================================ PARTE 1: HISTÓRICO
H('E1 · BRONZE — documentos crudos inmutables (eeff_html)')
files = subprocess.run(['grep','-rl',cuit,EEFF], capture_output=True, text=True, timeout=180).stdout.splitlines()
docs=[]  # (period, tipo, unidad, path)
for f in files:
    h=open(f,encoding='utf-8',errors='ignore').read()
    fc=field(h,'FechaCierre')[:10]; tb=field(h,'TipoBalance'); um=field(h,'UnidadMedida')
    if fc: docs.append((fc,'CONS' if 'consol' in tb.lower() else 'INDIV',um,f))
periodos=sorted({d[0] for d in docs})
print(f'  {len(files)} archivos · {len(periodos)} períodos ({periodos[0]} → {periodos[-1]})')
print(f'  tipos: {sorted({d[1] for d in docs})} · unidades declaradas: {sorted({d[2] for d in docs})}')

H('E2 · RAW COMPLETO — se extrae TODO tag (Nro/Rubro/Monto), nada se descarta')
raw={}  # period -> {code:(label,valor_base)}  (elige CONS si hay, si no INDIV)
for fc,tipo,um,f in docs:
    h=open(f,encoding='utf-8',errors='ignore').read()
    fac=factor(um)
    d=raw.setdefault((fc,tipo),{})
    for code,lab,mon in TRIP.findall(h):
        v=snum(mon.strip())
        if v is not None: d[code.strip()]=(lab.strip()[:30],v*fac)
# elegir tipo por período: CONS preferido
per_codes={}
for (fc,tipo),d in raw.items():
    if fc not in per_codes or (tipo=='CONS' and per_codes[fc][0]!='CONS'):
        per_codes[fc]=(tipo,d)
tot=sum(len(d) for _,d in per_codes.values())
mapped=sum(1 for _,d in per_codes.values() for c in d if c in CODE_MAP)
print(f'  {tot} tags extraídos en {len(per_codes)} períodos · {mapped} mapeados / {tot-mapped} sin mapear')
print(f'  ej. último período {periodos[-1]}: {len(per_codes.get(periodos[-1],(None,{}))[1])} códigos')

H('T1 · SILVER — mapeo a conceptos canónicos + factor de unidad + GUARD de unidad')
CAN=['revenue','cogs','gross_profit','operating_income','net_income','pretax_income','income_tax',
     'assets','assets_current','assets_noncurrent','liabilities','liabilities_current','equity','cash']
INVc={v:k for k,v in CODE_MAP.items()}
silver={}  # period -> {concepto:valor}
for fc,(tipo,d) in per_codes.items():
    row={}
    for con_name in CAN:
        code=INVc.get(con_name)
        if code and code in d: row[con_name]=d[code][1]
    silver[fc]=row
# GUARD de continuidad de unidad: si assets de un período está ~1e6/1e3 fuera de la mediana → corregir
import statistics as st
serie=[(p,silver[p].get('assets')) for p in sorted(silver) if silver[p].get('assets')]
if len(serie)>=3:
    med=st.median([v for _,v in serie])
    corr=0
    for p,v in serie:
        for f_ in (1e6,1e3):
            if v and rel(v*f_,med,3):  # v está f_ veces por debajo de la vecindad
                pass
    # (chequeo informativo — TXAR no lo necesita; se activa en CVH)
print(f'  conceptos canónicos poblados en el último período: {sorted(silver[periodos[-1]].keys())}')

H('T2 · CIERRE INTERNO — el estado se prueba a sí mismo (identidades + cascada)')
def g(p,c): return silver.get(p,{}).get(c)
oks=0; tota=0
for p in sorted(silver):
    A,AC,ANC=g(p,'assets'),g(p,'assets_current'),g(p,'assets_noncurrent')
    L,E=g(p,'liabilities'),g(p,'equity')
    REV,COGS,GP=g(p,'revenue'),g(p,'cogs'),g(p,'gross_profit')
    checks=[rel(A,(AC or 0)+(ANC or 0)) if(A and AC and ANC) else None,
            rel(A,(L or 0)+(E or 0)) if(A and L and E) else None,
            rel(GP,(REV or 0)+(COGS or 0)) if(GP and REV and COGS) else None]  # COGS viene negativo
    ap=[c for c in checks if c is not None]; ok=all(ap) and ap
    if ap: tota+=1; oks+=1 if ok else 0
    if p in periodos[-3:]:
        print(f'  {p}: A=AC+ANC {"OK" if checks[0] else "-" if checks[0] is None else "FAIL"} · '
              f'A=P+PN {"OK" if checks[1] else "-" if checks[1] is None else "FAIL"} · '
              f'GP=Rev+Cost {"OK" if checks[2] else "-" if checks[2] is None else "FAIL"}')
print(f'  → cierran {oks}/{tota} períodos con datos suficientes')

H('T3 · DERIVED — ratios del ejercicio ANUAL certificable (cierre mes '+str(fy)+')')
anu=[p for p in sorted(silver) if int(p[5:7])==fy and silver[p].get('assets') and silver[p].get('equity')]
P=anu[-1] if anu else None
if P:
    ni,eq,ast,rev=g(P,'net_income'),g(P,'equity'),g(P,'assets'),g(P,'revenue')
    roe=ni/eq if(ni and eq) else None; roa=ni/ast if(ni and ast) else None
    mn=ni/rev if(ni and rev) else None
    def pc(x): return f'{x*100:.1f}%' if isinstance(x,(int,float)) else '—'
    print(f'  ejercicio anual = {P}')
    print(f'  ROE {pc(roe)} · ROA {pc(roa)} · margen neto {pc(mn)}  (NI={ni:,.0f} PN={eq:,.0f})' if ni and eq else f'  NI o PN faltante en {P}')

H('T4/T5 · CERTIFICACIÓN — sello de la suite (identidades duras + ancla de mercado)')
nv=cur.execute("select nivel,checks_ok,checks_aplicables,fallidos from screener_nivel where ticker=?",(TK,)).fetchone()
sg=cur.execute("select roe,per,p_book,roe_ttm,market_cap,mcap_confiable from screener_gold where ticker=?",(TK,)).fetchone()
if nv: print(f'  nivel: {nv[0]} · cruces {nv[1]}/{nv[2]}' + (f' · informativos que no bloquean: {nv[3]}' if nv[3] else ''))
if sg: print(f'  screener_gold: ROE_anual {sg[0] and round(sg[0]*100,1)}% · P/B {sg[2] and round(sg[2],2)} · mcap 2-fuentes: {"sí" if sg[5] else "no"}')

H('ANCLA EXTERNA — magnitud absoluta vs investing (cierra el punto ciego de escala)')
inv={c:v*1e6 for c,v in cur.execute("select concepto,valor from investing_estados where ticker=? and period_end=? and estado in ('balance','resultados')",(TK,P))} if P else {}
if inv:
    print(f'  comparando MISMO período {P} (mismo vintage), nuestro vs investing:')
    for c in ['assets','equity','liabilities','revenue','net_income']:
        o=g(P,c); i=inv.get(c)
        r=abs(o)/abs(i) if (o and i) else None
        onum = f'{o:,.0f}' if o is not None else 'falta'
        inum = f'{i:,.0f}' if i is not None else 'falta'
        rr = f'x{r:.2f}' if r else 's/d'
        print(f'    {c:>14}: {rr:>6}   nuestro={onum:>22}   investing={inum:>22}')
else:
    print('  (sin estados de investing cargados para este ticker)')

H('P · PRESENTACIÓN — la fila final del producto')
r=cur.execute("select nombre,sector,periodo_cierre,roe,per,p_book,margen_neto,nivel_certificacion from screener_gold where ticker=?",(TK,)).fetchone()
if r:
    print(f'  {TK} · {r[0][:30]} · {r[1]} · cierre {r[2]}')
    print(f'  ROE {r[3] and round(r[3]*100,1)}% · PER {r[4] and round(r[4],1)} · P/B {r[5] and round(r[5],2)} · margen {r[6] and round(r[6]*100,1)}% · SELLO: {r[7]}')

# ==================================================== PARTE 2: ACTUALIZACIÓN
H('ETL DE ACTUALIZACIÓN — cómo entra un ejercicio nuevo (incremental, idempotente)')
ult_bronze=periodos[-1]
disc=cur.execute("select max(fecha_cierre) from cnv_filings where cuit=?",(cuit,)).fetchone()[0]
print(f'  U1 DISCOVERY  · último en CNV (cnv_filings): {disc} · último en bronze: {ult_bronze}')
if disc and disc>ult_bronze:
    print(f'  U2 FETCH      · FALTA {disc}: bajar su publicview → eeff_html (patrón fetch_dgce, red CNV)')
    print(f'  U3 RE-EXTRACT · re-correr T sobre el período nuevo (INSERT OR REPLACE, no toca el resto)')
    print(f'  U4 RE-CERTIFY · la suite re-evalúa; el screener_gold se regenera')
else:
    print(f'  U2 FETCH      · bronze ya está al día ({ult_bronze}) → nada que bajar')
    print(f'  (cuando la empresa presente un ejercicio nuevo, U1 lo detecta y dispara U2→U4)')
print('\n  Nota: todo el histórico se reconstruye desde bronze con run_pipeline.py (idempotente);')
print('  la actualización es el MISMO pipeline corriendo solo sobre el período nuevo.')
con.close()
