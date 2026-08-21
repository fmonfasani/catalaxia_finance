# -*- coding: utf-8 -*-
"""
FASE 1 — Identidad canónica (medallion / silver).
Construye dim_entity y dim_instrument resolviendo el lío ticker/razón social.
Fuentes: screener (universo 572), adr_ratios+empresas (cik ADR), fiscal_calendar (fy AR),
empresas (fy/moneda US), mapa_entidades/empresas (nombre). SQLite-compatible.
Idempotente: reconstruye las 2 tablas.
"""
import sqlite3
import os as _os
# SCREENER_DB: apunta a una copia de prueba sin tocar produccion.
DB = _os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))
con=sqlite3.connect(DB); cur=con.cursor()

cur.executescript('''
DROP TABLE IF EXISTS dim_entity;
CREATE TABLE dim_entity (
  entity_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  cuit             TEXT,
  cik              TEXT,
  ticker_canonico  TEXT UNIQUE NOT NULL,
  nombre           TEXT,
  grupo            TEXT CHECK (grupo IN ('byma_only','adr','sp500')),
  moneda_funcional TEXT,
  fy_end_month     INTEGER,
  es_financiera    INTEGER NOT NULL DEFAULT 0
);
DROP TABLE IF EXISTS dim_instrument;
CREATE TABLE dim_instrument (
  instrument_id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id     INTEGER NOT NULL REFERENCES dim_entity(entity_id),
  ticker        TEXT NOT NULL,
  mercado       TEXT NOT NULL,
  tipo          TEXT,
  moneda        TEXT,
  ratio         REAL,
  UNIQUE(ticker, mercado)
);
''')

# --- mapas de enriquecimiento ---
adr={}   # cuit -> (cik, moneda, fye, edgar_ticker, ratio)
for et,cuit,cik,mon,fye in cur.execute('''
    select a.edgar_ticker,a.cuit,e.cik,e.moneda,e.fiscal_year_end
    from adr_ratios a left join empresas e on e.ticker_ppal=a.edgar_ticker''').fetchall():
    if cuit: adr[cuit]=[cik,mon,fye,et,None]
for et,cuit,ratio in cur.execute("select edgar_ticker,cuit,ratio from adr_ratios").fetchall():
    if cuit and cuit in adr: adr[cuit][4]=ratio

fcal=dict(cur.execute("select cuit,fy_end_month from fiscal_calendar").fetchall())
emp={cik:(mon,fye,nom) for cik,mon,fye,nom in
     cur.execute("select cik,moneda,fiscal_year_end,nombre from empresas").fetchall()}
nombre_ar={cuit:nom for cuit,nom in
     cur.execute("select cuit,nombre from mapa_entidades where es_primario=1").fetchall()}

def mes(fye):
    return int(fye[:2]) if fye and len(fye)>=2 and fye[:2].isdigit() and 1<=int(fye[:2])<=12 else None

ents=[]
for cuit,ticker,grupo,esfin,sector in cur.execute(
        "select cuit,ticker,grupo,es_financiera,sector from screener").fetchall():
    esfin = 1 if (esfin or (sector and 'financ' in sector.lower())) else 0
    if grupo=='sp500':
        cik=cuit; cuit_ar=None
        mon,fye,nom=emp.get(cik,(None,None,None))
        ents.append((cuit_ar,cik,ticker,nom,grupo,mon or 'USD',mes(fye),esfin))
    else:
        cuit_ar=cuit; fy=fcal.get(cuit); cik=None; moneda='ARS'
        nom=nombre_ar.get(cuit)
        if grupo=='adr' and cuit in adr:
            cik,mon,fye,et,ratio=adr[cuit]
            moneda=mon or 'ARS'
            if fy is None: fy=mes(fye)
            if not nom and cik: nom=emp.get(cik,(None,None,None))[2]
        ents.append((cuit_ar,cik,ticker,nom,grupo,moneda,fy,esfin))

cur.executemany('''insert or ignore into dim_entity
   (cuit,cik,ticker_canonico,nombre,grupo,moneda_funcional,fy_end_month,es_financiera)
   values(?,?,?,?,?,?,?,?)''', ents)
con.commit()

# --- dim_instrument: primario + ADR ---
eid={t:i for i,t in cur.execute("select entity_id,ticker_canonico from dim_entity").fetchall()}
instr=[]
for entity_id,ticker,grupo,cuit in cur.execute(
        "select entity_id,ticker_canonico,grupo,cuit from dim_entity").fetchall():
    if grupo=='sp500':
        instr.append((entity_id,ticker,'US','ordinaria','USD',None))
    else:
        instr.append((entity_id,ticker,'BYMA','ordinaria','ARS',None))
        if grupo=='adr' and cuit in adr:
            cik,mon,fye,et,ratio=adr[cuit]
            if et: instr.append((entity_id,et,'NYSE/NASDAQ','adr','USD',ratio))
cur.executemany('''insert or ignore into dim_instrument
   (entity_id,ticker,mercado,tipo,moneda,ratio) values(?,?,?,?,?,?)''', instr)
con.commit()

# --- reporte de cobertura ---
def q(s,*a): return cur.execute(s,a).fetchone()[0]
print('== dim_entity ==')
for g in ('sp500','adr','byma_only'):
    tot=q("select count(*) from dim_entity where grupo=?",g)
    ccik=q("select count(*) from dim_entity where grupo=? and cik is not null",g)
    cfy=q("select count(*) from dim_entity where grupo=? and fy_end_month is not null",g)
    print(f'   {g:>10}: {tot:>3} | con cik {ccik:>3} | con fy {cfy:>3}')
print(f'   TOTAL entidades: {q("select count(*) from dim_entity")}')
print(f'   es_financiera: {q("select count(*) from dim_entity where es_financiera=1")}')
print(f'== dim_instrument: {q("select count(*) from dim_instrument")} '
      f'(adr {q("select count(*) from dim_instrument where tipo=?","adr")}) ==')
print('\\n== GAPS (a resolver en Fase 2) ==')
print('   AR sin fy_end_month:', [r[0] for r in cur.execute(
    "select ticker_canonico from dim_entity where grupo!='sp500' and fy_end_month is null").fetchall()])
print('   ADR sin cik:', [r[0] for r in cur.execute(
    "select ticker_canonico from dim_entity where grupo='adr' and cik is null").fetchall()])
con.close()
