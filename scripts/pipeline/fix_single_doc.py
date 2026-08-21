# -*- coding: utf-8 -*-
"""
FIX single-doc: re-extrae CVH/EDSH tomando TODOS los conceptos de UN mismo documento por período
(no mezclar docs) → el balance cierra (el PN total ya incluye minoritario). Actualiza cnv_reextract.
"""
import re,os,subprocess,sqlite3
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
CODE_MAP={'3000100':'revenue','3000200':'cogs','3009999':'gross_profit','3011600':'da',
 '3019999':'operating_income','3021400':'financial_income','3021500':'interest_expense',
 '3021800':'recpam','3029999':'pretax_income','3031100':'income_tax','3049999':'net_income',
 '3099999':'comprehensive_income','3240000':'net_change_cash','3241100':'cfo','3241200':'cfi',
 '3241300':'cff','8000000':'eps_basic','8000001':'eps_diluted','8000003':'ebit','8000004':'ebitda',
 '1122500':'cash','1121999':'receivables','1120100':'inventory','1139999':'assets_current',
 '1110100':'ppe','1119999':'assets_noncurrent','1999999':'assets','2299999':'equity',
 '2322200':'debt_current','2339999':'liabilities_current','2312300':'debt_noncurrent',
 '2399999':'liabilities','8000009':'cnv_roe','8000010':'cnv_roa','8000014':'cnv_margen_neto'}
NO_FACTOR={'eps_basic','eps_diluted','cnv_roe','cnv_roa','cnv_margen_neto'}
def field(h,k):
    m=re.search(k+r'[^>]*>\s*([^<]{0,40})',h); return m.group(1).strip() if m else ''
def factor(um):
    u=um.lower(); return 1_000_000 if 'millon' in u else (1_000 if 'mil' in u else 1)
def num(s):
    if ',' in s: s=s.replace('.','').replace(',','.')
    else:
        p=s.split('.')
        if len(p)>2 or (len(p)==2 and len(p[1])==3): s=''.join(p)
    return float(s)
PAIR=re.compile(r'id="Nro"[^>]*>(\d+)</propiedad>\s*<propiedad id="Rubro"[^>]*>[^<]*</propiedad>\s*<propiedad id="Monto"[^>]*>\s*(-?[\d.,]+)')
EEFF='scripts/tickets/cnv/eeff/eeff_html'
for tk in ['CVH','EDSH']:
    cuit=cur.execute('select cuit from dim_entity where ticker_canonico=?',(tk,)).fetchone()[0]
    files=subprocess.run(['grep','-rl',cuit,EEFF],capture_output=True,text=True,timeout=120).stdout.splitlines()
    # agrupar docs consolidados por FechaCierre; por período elegir el MÁS COMPLETO (más códigos)
    porperiodo={}
    for f in files:
        h=open(f,encoding='utf-8',errors='ignore').read()
        if field(h,'TipoBalance').lower()!='consolidado': continue
        fc=field(h,'FechaCierre')[:10]
        if not fc or len(fc)!=10: continue
        pairs={n:v for n,v in PAIR.findall(h) if n in CODE_MAP}
        cur_best=porperiodo.get(fc)
        if not cur_best or len(pairs)>cur_best[2]:
            porperiodo[fc]=(h,field(h,'UnidadMedida'),len(pairs))
    n=0
    for fc,(h,um,_) in porperiodo.items():
        fac=factor(um)
        for code,conc in CODE_MAP.items():
            m=re.search(r'id="Nro"[^>]*>'+code+r'</propiedad>\s*<propiedad id="Rubro"[^>]*>[^<]*</propiedad>\s*<propiedad id="Monto"[^>]*>\s*(-?[\d.,]+)',h)
            if not m: continue
            try: v=num(m.group(1))
            except: continue
            base=v if conc in NO_FACTOR else v*fac
            cur.execute("insert or replace into cnv_reextract(cuit,concepto,period_end,valor,tipo_balance) values(?,?,?,?,'consolidado')",(cuit,conc,fc,base))
            n+=1
    print(f'{tk}: {len(porperiodo)} períodos re-extraídos de doc único, {n} valores')
con.commit(); con.close()
