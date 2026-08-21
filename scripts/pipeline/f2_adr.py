# -*- coding: utf-8 -*-
"""
Re-extrae los ADR argentinos desde eeff_html hacia cnv_reextract (APPEND, no borra — preserva
los fixes de byma_only). Para cerrar la triangulación SEC↔CNV. SQLite. Idempotente.
"""
import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from f2_reextract_batch import extraer, anti_outlier  # seguro: f2 tiene guard __main__

def main():
    con=sqlite3.connect('data/screener.db'); cur=con.cursor()
    data=extraer(['adr'])
    rows=anti_outlier(data)
    cur.executemany("insert or replace into cnv_reextract(cuit,concepto,period_end,valor,tipo_balance) values(?,?,?,?,?)",rows)
    con.commit()
    print(f'ADR agregados a cnv_reextract: {len(rows)} filas, {len(set(r[0] for r in rows))} empresas')
    con.close()

if __name__=='__main__':
    main()
