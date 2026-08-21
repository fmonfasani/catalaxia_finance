# -*- coding: utf-8 -*-
"""
Correcciones manuales reproducibles (verificadas, no fabricadas):
 - Precios BOLT/PATA (se perdieron al renombrar desde _2; de snapshot investing).
 - CVH 2024-12: PN total = Activo - Pasivo (el doc trae 2299999 vacío; verificado = controladora
   + minoritario 2211300). Cierra el balance.
Idempotente.
"""
import sqlite3
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
# EDN (Edenor): dropeada del universo, se recupera via SEC (no está en screener → f1 no la crea)
if not cur.execute("select 1 from dim_entity where ticker_canonico='EDN'").fetchone():
    cur.execute("""insert into dim_entity(cuit,cik,ticker_canonico,nombre,grupo,moneda_funcional,fy_end_month,es_financiera)
       values('30655116202','0001395213','EDN','EDENOR','adr','ARS',12,0)""")
# A3: ejercicio fiscal cierra en JUNIO (no dic). fiscal_calendar detectó 12 por confundir el
# cierre de Q2 (31-dic) con cierre de ejercicio. Verificado por FechaInicio=1-jul en los anuales
# 2024-06/2025-06 (12 meses). En 2026 migró a ene-dic (FechaInicio 2026-01-01), transición real.
cur.execute("update dim_entity set fy_end_month=6 where ticker_canonico='A3'")
# precios (snapshot investing) de las renombradas
cur.execute("update screener set precio_ars=46 where ticker='BOLT' and (precio_ars is null or precio_ars=0)")
cur.execute("update screener set precio_ars=1295 where ticker='PATA' and (precio_ars is null or precio_ars=0)")
# CVH 2024-12: PN total = A - L (doc con 2299999 vacío; minoritario 2211300 explica la brecha)
r=cur.execute("select (select valor from cnv_reextract where cuit='30715591231' and concepto='assets' and period_end='2024-12-31'),"
              "(select valor from cnv_reextract where cuit='30715591231' and concepto='liabilities' and period_end='2024-12-31')").fetchone()
if r and r[0] and r[1] is not None:
    cur.execute("update cnv_reextract set valor=? where cuit='30715591231' and concepto='equity' and period_end='2024-12-31'",(r[0]-r[1],))
con.commit()
print('fix_manual: precios BOLT/PATA + CVH PN total 2024-12 aplicados')
con.close()
