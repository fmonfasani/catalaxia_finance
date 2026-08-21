# -*- coding: utf-8 -*-
"""
FIX de mapeo de identidad: cada entidad a su ticker real de BYMA.
  B-GAMING (cuit 30709967424): BOLT -> GAMI  (su ticker real; libera 'BOLT')
  Boldt    (cuit 30500179151): BOLT_2 -> BOLT
  Import.Patagonia (30506730038): PATA_2 -> PATA
Actualiza dim_entity, dim_instrument, screener y los externos (eerr/ratios). Idempotente.
"""
import sqlite3
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
# orden: GAMI primero (libera BOLT), luego Boldt->BOLT, luego Importadora->PATA
renames=[('30709967424','GAMI'),('30500179151','BOLT'),('30506730038','PATA')]
print('== antes ==')
for cuit,new in renames:
    r=cur.execute("select ticker_canonico,nombre from dim_entity where cuit=?",(cuit,)).fetchone()
    print(f'  {cuit}: {r[0]:>7} ({r[1]}) -> {new}')
for cuit,new in renames:
    eid=cur.execute("select entity_id from dim_entity where cuit=?",(cuit,)).fetchone()[0]
    cur.execute("update dim_entity set ticker_canonico=? where cuit=?",(new,cuit))
    cur.execute("update screener set ticker=? where cuit=?",(new,cuit))
    cur.execute("update dim_instrument set ticker=? where entity_id=? and mercado='BYMA'",(new,eid))
# externos: la data de investing de Boldt/Importadora estaba bajo _2
for old,new in [('BOLT_2','BOLT'),('PATA_2','PATA')]:
    cur.execute("update eerr_externos set ticker=? where ticker=?",(new,old))
    cur.execute("update ratios_externos set ticker=? where ticker=?",(new,old))
con.commit()
print('== despues ==')
for cuit,new in renames:
    r=cur.execute("select ticker_canonico,nombre from dim_entity where cuit=?",(cuit,)).fetchone()
    print(f'  {cuit}: {r[0]:>7} ({r[1]})')
# verificar externos
print('  eerr con BOLT:', cur.execute("select count(distinct period_end) from eerr_externos where ticker='BOLT'").fetchone()[0],'| ratios BOLT:', cur.execute("select 1 from ratios_externos where ticker='BOLT'").fetchone() is not None)
con.close()
