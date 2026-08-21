# -*- coding: utf-8 -*-
"""
FASE 3 (parte CNV) — Normaliza cnv_estados_v2 -> fact_financials (silver).
Contratos: identidad via dim_entity, escala via unidad_factor (valor*factor -> base ARS),
de-acumulación YTD->standalone con fy_end_month, RECPAM doble variante, validación/cuarentena.
SQLite. Idempotente.
"""
import sqlite3, statistics, datetime as dt
import os as _os
# SCREENER_DB: apunta a una copia de prueba sin tocar produccion.
DB = _os.path.join("data", _os.environ.get("SCREENER_DB", "screener.db"))
con=sqlite3.connect(DB); cur=con.cursor()

# ---- crosswalk CNV concepto -> canónico ----
X={'Revenue':'revenue','COGS':'cogs','GrossProfit':'gross_profit','OperatingIncome':'operating_income',
 'EBITDA':'ebitda','EBIT':'ebit','DA':'da','NetIncome':'net_income','PretaxIncome':'pretax_income',
 'IncomeTax':'income_tax','InterestExpense':'interest_expense','IngresosFinancieros':'financial_income',
 'RECPAM':'recpam','ResultadoIntegral':'comprehensive_income','Assets':'assets','AssetsCurrent':'assets_current',
 'AssetsNonCurrent':'assets_noncurrent','Cash':'cash','Receivables':'receivables','Inventory':'inventory',
 'PPE':'ppe','Intangibles':'intangibles','Liabilities':'liabilities','LiabilitiesCurrent':'liabilities_current',
 'LiabilitiesNonCurrent':'liabilities_noncurrent','Payables':'payables','DebtCurrent':'debt_current',
 'DebtNonCurrent':'debt_noncurrent','Equity':'equity','Capital':'capital','Reservas':'reserves',
 'ResultadosNoAsignados':'retained_earnings','WorkingCapital':'working_capital','CF_Operativo':'cfo',
 'CF_Inversion':'cfi','CF_Financiacion':'cff','CashFlowNeto':'net_change_cash','EPS_basico':'eps_basic',
 'EPS_diluido':'eps_diluted'}
FLOW={'revenue','cogs','gross_profit','operating_income','ebit','ebitda','da','interest_expense',
 'financial_income','recpam','pretax_income','income_tax','net_income','comprehensive_income',
 'cfo','cfi','cff','net_change_cash','eps_basic','eps_diluted'}
RECPAM_AFFECTED={'net_income','pretax_income','comprehensive_income'}

cur.executescript('''
DROP TABLE IF EXISTS fact_financials;
CREATE TABLE fact_financials(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id INTEGER NOT NULL, concepto_canonico TEXT NOT NULL,
  period_end TEXT NOT NULL, period_type TEXT NOT NULL, fiscal_q INTEGER,
  valor NUMERIC NOT NULL, moneda TEXT NOT NULL, unidad_factor NUMERIC DEFAULT 1,
  incluye_recpam INTEGER NOT NULL DEFAULT 1, fecha_reexpresion TEXT,
  fuente TEXT NOT NULL, source_ref TEXT, loaded_at TEXT,
  UNIQUE(entity_id,concepto_canonico,period_end,period_type,incluye_recpam,fuente));
DROP TABLE IF EXISTS fact_financials_cuarentena;
CREATE TABLE fact_financials_cuarentena(
  entity_id INTEGER, ticker TEXT, concepto_canonico TEXT, period_end TEXT,
  valor NUMERIC, motivo TEXT, detectado_at TEXT);
''')

def mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
def valid_date(pe):  # fin de trimestre real (descarta 2024-11-08)
    try: return int(pe[8:10])>=28
    except: return False

ent=cur.execute("select entity_id,cuit,ticker_canonico,fy_end_month from dim_entity where grupo!='sp500' and cuit is not null").fetchall()
now=dt.datetime.now().isoformat(timespec='seconds')
INS=[]; QUAR=[]
for entity_id,cuit,ticker,fy in ent:
    if not fy: fy=12
    # traer todo el crudo de la entidad
    raw=cur.execute("select concepto,period_end,valor,unidad_factor,fecha_reexpresion from cnv_estados_v2 where cuit=?",(cuit,)).fetchall()
    # normalizar por concepto canónico
    series={}   # canon -> {period_end: (base, factor, reexp)}
    for concepto,pe,valor,uf,reexp in raw:
        canon=X.get(concepto)
        if not canon or valor is None: continue
        if not valid_date(pe):
            QUAR.append((entity_id,ticker,canon,pe,valor,'fecha_no_trimestral',now)); continue
        # valor ya está en pesos base; unidad_factor es metadato del reporte original (NO multiplicar)
        base=valor
        series.setdefault(canon,{})[pe]=(base,uf or 1,reexp)
    # calcular standalone + anual por concepto
    perdata={}  # (canon, period_end, ptype) -> (valor, factor, reexp, fq)
    for canon,d in series.items():
        pes=sorted(d)
        # detector de pico LOCAL: valor >30x la mediana de sus vecinos temporales
        def es_pico(seq, i):
            neigh=[abs(seq[j]) for j in (i-1,i+1) if 0<=j<len(seq) and seq[j] not in (None,0)]
            neigh=[x for x in neigh if x>0]
            ref=statistics.median(neigh) if neigh else 0
            return ref>0 and abs(seq[i])>30*ref
        if canon in FLOW:
            std={}
            for pe in pes:
                base=d[pe][0]; q=4-((fy-int(pe[5:7]))%12)//3
                if q==1: std[pe]=base
                else:
                    prev=[p for p in pes if p<pe and mb(p,pe)==3]
                    std[pe]= base-d[prev[-1]][0] if prev else None
            order=[pe for pe in pes if std.get(pe) is not None]
            seq=[std[pe] for pe in order]
            for i,pe in enumerate(order):
                v=std[pe]; q=4-((fy-int(pe[5:7]))%12)//3
                if es_pico(seq,i):
                    QUAR.append((entity_id,ticker,canon,pe,v,'escala_outlier',now)); continue
                if canon=='revenue' and v<0:
                    QUAR.append((entity_id,ticker,canon,pe,v,'revenue_negativo',now)); continue
                perdata[(canon,pe,'Q')]=(v,d[pe][1],d[pe][2],q)
                if q==4:  # anual = YTD a fin de ejercicio
                    perdata[(canon,pe,'A')]=(d[pe][0],d[pe][1],d[pe][2],q)
        else:  # stock: point-in-time
            seq=[d[pe][0] for pe in pes]
            for i,pe in enumerate(pes):
                base=d[pe][0]; q=4-((fy-int(pe[5:7]))%12)//3
                if es_pico(seq,i):
                    QUAR.append((entity_id,ticker,canon,pe,base,'escala_outlier',now)); continue
                perdata[(canon,pe,'A' if q==4 else 'Q')]=(base,d[pe][1],d[pe][2],q)
    # emitir filas + variante RECPAM
    # index recpam por (period_end, ptype)
    recpam={(pe,pt):v[0] for (c,pe,pt),v in perdata.items() if c=='recpam'}
    for (canon,pe,pt),(valor,factor,reexp,q) in perdata.items():
        INS.append((entity_id,canon,pe,pt,q,valor,'ARS',factor,1,reexp or None,'cnv','cnv_estados_v2',now))
        if canon in RECPAM_AFFECTED:
            rp=recpam.get((pe,pt))
            if rp is not None:
                INS.append((entity_id,canon,pe,pt,q,valor-rp,'ARS',factor,0,reexp or None,'cnv','cnv_estados_v2',now))

cur.executemany('''insert or ignore into fact_financials
  (entity_id,concepto_canonico,period_end,period_type,fiscal_q,valor,moneda,unidad_factor,
   incluye_recpam,fecha_reexpresion,fuente,source_ref,loaded_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)''',INS)
cur.executemany('''insert into fact_financials_cuarentena
  (entity_id,ticker,concepto_canonico,period_end,valor,motivo,detectado_at) values(?,?,?,?,?,?,?)''',QUAR)
con.commit()

# ---- reporte ----
def q(s,*a): return cur.execute(s,a).fetchone()[0]
print(f'fact_financials: {q("select count(*) from fact_financials")} filas | '
      f'{q("select count(distinct entity_id) from fact_financials")} entidades | '
      f'{q("select count(distinct concepto_canonico) from fact_financials")} conceptos')
print(f'  con RECPAM=0 (ex-recpam): {q("select count(*) from fact_financials where incluye_recpam=0")}')
print(f'  period_type Q/A: {q("select count(*) from fact_financials where period_type=?","Q")}/{q("select count(*) from fact_financials where period_type=?","A")}')
print(f'\\nCUARENTENA: {q("select count(*) from fact_financials_cuarentena")} filas')
print('  por motivo:', cur.execute("select motivo,count(*) from fact_financials_cuarentena group by motivo").fetchall())
print('  entidades más afectadas:')
for tk,n in cur.execute("select ticker,count(*) from fact_financials_cuarentena group by ticker order by count(*) desc limit 8").fetchall():
    print(f'     {tk}: {n}')
con.close()
