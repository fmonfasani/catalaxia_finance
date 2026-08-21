# -*- coding: utf-8 -*-
"""
FASE 2 (batch) — Re-extrae CONSOLIDADO de todas las byma_only desde eeff_html.
Corrige: individual→consolidado, etiqueta de unidad falsa, formatos de número.
Escribe tabla limpia cnv_reextract (concepto ya canónico). SQLite. Idempotente.
"""
import sys, os, re, sqlite3, statistics, subprocess
import os as _os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from reextract_consolidado import field, factor, num, EEFF
from cnv_codes import CODE_MAP, NO_FACTOR, PAIR  # definiciones compartidas (seguro de importar)

def extraer(grupos):
    """Extrae los cuits de los grupos dados hacia data[cuit][concepto]={period:(valor,tipo)}."""
    con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()
    q="select cuit from dim_entity where grupo in (%s) and cuit is not null" % ",".join("?"*len(grupos))
    cuits=[c for (c,) in cur.execute(q,grupos)]; con.close()
    CUIT=re.compile('|'.join(cuits))
    print(f'{grupos}: {len(cuits)} cuits. Buscando docs...')
    out=subprocess.run(['grep','-rlE','|'.join(cuits),EEFF],capture_output=True,text=True,timeout=600)
    files=[l for l in out.stdout.splitlines() if l.strip()]
    print(f'docs que matchean: {len(files)}. Parseando...')
    data=defaultdict(lambda: defaultdict(dict))
    for f in files:
        h=open(f,encoding='utf-8',errors='ignore').read()
        mc=CUIT.search(h)
        if not mc: continue
        cu=mc.group(0)
        tb=field(h,'TipoBalance').lower(); fc=field(h,'FechaCierre')[:10]; um=field(h,'UnidadMedida')
        if not fc or len(fc)!=10: continue
        fac=factor(um)
        for code,raw in PAIR.findall(h):
            concepto=CODE_MAP.get(code)
            if not concepto: continue
            try: v=num(raw)
            except: continue
            base=v if concepto in NO_FACTOR else v*fac
            d=data[cu][concepto]
            if fc not in d or (tb=='consolidado' and d[fc][1]!='consolidado'):
                d[fc]=(base,tb)
    return data

def anti_outlier(data):
    rows=[]
    for cu,concs in data.items():
        for concepto,d in concs.items():
            pes=sorted(d)
            for i,pe in enumerate(pes):
                v=d[pe][0]
                neigh=[abs(d[pes[j]][0]) for j in (i-1,i+1) if 0<=j<len(pes) and d[pes[j]][0]]
                neigh=[x for x in neigh if x>0]
                ref=statistics.median(neigh) if neigh else 0
                if ref>0 and abs(v)>30*ref: continue     # outlier de unidad -> descartar
                rows.append((cu,concepto,pe,v,d[pe][1]))
    return rows

def main():
    con=sqlite3.connect(_os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))); cur=con.cursor()
    data=extraer(['byma_only'])
    cur.executescript('''DROP TABLE IF EXISTS cnv_reextract;
    CREATE TABLE cnv_reextract(cuit TEXT,concepto TEXT,period_end TEXT,valor NUMERIC,tipo_balance TEXT,
      PRIMARY KEY(cuit,concepto,period_end));''')
    rows=anti_outlier(data)
    cur.executemany('insert or replace into cnv_reextract values(?,?,?,?,?)',rows)
    con.commit()
    print(f'cnv_reextract: {len(rows)} filas | {len(set(r[0] for r in rows))} empresas | '
          f'consolidado {sum(1 for r in rows if r[4]=="consolidado")} indiv {sum(1 for r in rows if r[4]=="individual")}')
    con.close()

if __name__=='__main__':
    main()
