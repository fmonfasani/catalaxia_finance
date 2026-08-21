# -*- coding: utf-8 -*-
"""
Re-extractor de producción: lee los estados CONSOLIDADOS crudos (eeff_html) de una empresa,
extrae los códigos del estado de resultados con la unidad VALIDADA contra vecinos, y arma
la serie limpia. Corrige los 2 bugs: (1) individual→consolidado, (2) etiqueta de unidad falsa.

Uso:  python reextract_consolidado.py <CUIT> [<TICKER_para_comparar>]
"""
import re, sys, os, glob, sqlite3, statistics, subprocess
EEFF='scripts/tickets/cnv/eeff/eeff_html'
CODES={'3000100':'revenue','3009999':'gross_profit','3019999':'operating_income',
       '8000004':'ebitda','3049999':'net_income'}
def field(h,k):
    m=re.search(k+r'[^>]*>\s*([^<]{0,40})',h); return m.group(1).strip() if m else ''
def factor(um):
    u=um.lower()
    return 1_000_000 if 'millon' in u else (1_000 if 'mil' in u else 1)
def num(s):
    """Parsea número en formato plano (539991027822.00) o argentino (227.980.120,50)."""
    s=s.strip()
    if ',' in s:                       # coma decimal, punto miles
        s=s.replace('.','').replace(',','.')
    else:
        p=s.split('.')
        if len(p)>2 and len(p[-1])>3:  # miles + último grupo malformado: coma decimal perdida
            s=''.join(p[:-1])+p[-1][:-2]+'.'+p[-1][-2:]  # '95.715.20600' -> 95715206.00
        elif len(p)>2:                 # varios puntos = miles
            s=''.join(p)
        elif len(p)==2 and len(p[1])==3:  # un punto + 3 dígitos = miles
            s=''.join(p)
        # un punto + 1-2 dígitos = decimal (se deja)
    return float(s)
def val(h,code):
    m=re.search(r'id="Nro"[^>]*>'+code+r'</propiedad>\s*<propiedad id="Rubro"[^>]*>[^<]*</propiedad>\s*<propiedad id="Monto"[^>]*>\s*(-?[\d.,]+)',h)
    return num(m.group(1)) if m else None

def extract(cuit):
    # lista de docs de la empresa
    try:
        out=subprocess.run(['grep','-rl',cuit,EEFF],capture_output=True,text=True,timeout=120)
        files=[l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        files=[f for f in glob.glob(EEFF+'/*.html') if cuit in open(f,encoding='utf-8',errors='ignore').read()]
    # recolectar: preferir CONSOLIDADO; por período, quedarse con consolidado si existe
    data={}  # concepto -> {period_end: (base, tipo, um)}
    for f in files:
        h=open(f,encoding='utf-8',errors='ignore').read()
        tb=field(h,'TipoBalance').lower(); fc=field(h,'FechaCierre')[:10]; um=field(h,'UnidadMedida')
        if not fc: continue
        fac=factor(um)
        for code,concepto in CODES.items():
            v=val(h,code)
            if v is None: continue
            base=v*fac
            cur=data.setdefault(concepto,{})
            # preferir consolidado sobre individual
            if fc not in cur or (tb=='consolidado' and cur[fc][1]!='consolidado'):
                cur[fc]=(base,tb,um)
    # validación de unidad: pico local >30x vecinos -> descartar (parser viejo)
    for concepto,d in data.items():
        pes=sorted(d);
        for i,pe in enumerate(pes):
            neigh=[abs(d[pes[j]][0]) for j in (i-1,i+1) if 0<=j<len(pes) and d[pes[j]][0]]
            neigh=[x for x in neigh if x>0]
            ref=statistics.median(neigh) if neigh else 0
            if ref>0 and abs(d[pe][0])>30*ref: d[pe]=(None,)+d[pe][1:]
    return data

def mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
def decum(serie):
    pes=[p for p in sorted(serie) if serie[p][0] is not None]
    std={}
    for pe in pes:
        prev=[p for p in pes if p<pe and mb(p,pe)==3]
        # Q1 (sin trimestre previo 3m) = YTD; si no, resta
        std[pe]=serie[pe][0]-serie[prev[-1]][0] if prev else serie[pe][0]
    return std

if __name__=='__main__':
    cuit=sys.argv[1]; ticker=sys.argv[2] if len(sys.argv)>2 else None
    data=extract(cuit)
    print(f'CUIT {cuit}: conceptos extraídos:', {k:len([p for p,v in d.items() if v[0] is not None]) for k,d in data.items()})
    # tipo de balance dominante
    tbs=[v[1] for d in data.values() for v in d.values()]
    print('  tipos:', dict((x,tbs.count(x)) for x in set(tbs)))
    if ticker:
        con=sqlite3.connect('data/screener.db'); cur=con.cursor()
        for concepto,extc in [('revenue','Revenue'),('net_income','NetIncome')]:
            std=decum(data.get(concepto,{}))
            ext=dict(cur.execute("select period_end,valor from eerr_externos where ticker=? and concepto=?",(ticker,extc)).fetchall())
            print(f'\n== {concepto} standalone (millones): nuevo vs investing ==')
            for pe in sorted(set(list(std)+list(ext)))[-6:]:
                n=std.get(pe); e=ext.get(pe)
                nm=n/1e6 if isinstance(n,(int,float)) else None
                match='OK' if (nm is not None and e is not None and abs(nm-e)<=abs(e)*0.12+1) else ''
                print(f'  {pe}: nuevo={(f"{nm:,.0f}" if nm is not None else "-"):>12} investing={(f"{e:,.0f}" if e is not None else "-"):>10} {match}')
        con.close()
