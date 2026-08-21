# -*- coding: utf-8 -*-
"""Baja los estados contables de DGCE de la CNV (el mecanismo publicview->XBRL FUNCIONA)."""
import requests, urllib3, sqlite3, os
from concurrent.futures import ThreadPoolExecutor, as_completed
urllib3.disable_warnings()
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120','Accept-Language':'es-AR'}
OUT='scripts/tickets/cnv/eeff/eeff_html'
con=sqlite3.connect('data/screener.db'); cur=con.cursor()
docids=[r[0] for r in cur.execute("select docid,url from cnv_documents where cuit='33657865279'").fetchall()]
con.close()
print(f'DGCE: {len(docids)} docids a chequear...')
ses=requests.Session(); ses.headers.update(H)
def fetch(guid):
    path=os.path.join(OUT,guid+'.html')
    if os.path.exists(path): return ('cache',guid)
    try:
        h=ses.get(f'https://aif2.cnv.gov.ar/presentations/publicview/{guid}',timeout=25,verify=False).text
        # es estado contable? tiene XBRL con codigos financieros
        if 'id="Nro"' in h and ('3000100' in h or '1999999' in h):
            open(path,'w',encoding='utf-8').write(h); return ('eeff',guid)
        return ('noeeff',guid)
    except Exception as e: return ('err',guid)
res={'eeff':0,'noeeff':0,'cache':0,'err':0}
with ThreadPoolExecutor(max_workers=8) as ex:
    for fut in as_completed([ex.submit(fetch,g) for g in docids]):
        res[fut.result()[0]]+=1
print(f"  EEFF guardados: {res['eeff']} | no-eeff: {res['noeeff']} | cache: {res['cache']} | err: {res['err']}")
