# -*- coding: utf-8 -*-
"""
SCRIPT 1 · COMPARAR — baja los tres dólares (MEP=referencia, CCL, A3500), cruza cada uno entre
fuentes independientes, y compara el CCL contra NUESTRA fuente actual (screener.db). No escribe nada.
   python scripts/dolares/comparar_dolares.py
"""
import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dolar import tres_dolares

PROD = os.path.join('data', 'screener.db')
d = tres_dolares()

def f(x): return f'{x:,.2f}' if isinstance(x, (int, float)) else '—'
def dif(a, b): return (f'{(a-b)/b*100:+.2f}%' if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b else '—')

print('=== DÓLARES DE REFERENCIA ===')
print(f'  MEP   (referencia)  : {f(d["mep"]["valor"])}   [criptoya-AL30]  · cruce dolarapi {f(d["mep"]["cruce"])}  ({dif(d["mep"]["valor"], d["mep"]["cruce"])})')
print(f'  CCL                 : {f(d["ccl"]["valor"])}   [yahoo-ADR]      · cruce dolarapi {f(d["ccl"]["cruce"])}  ({dif(d["ccl"]["valor"], d["ccl"]["cruce"])})')
print(f'  A3500 (mayorista)   : {f(d["a3500"]["valor"])}   [dolarapi]')

print('\n  detalle MEP (fuentes independientes):')
for name, v in d['mep']['detalle']:
    print(f'     {name:<10} {f(v)}')
print('  detalle CCL por ADR (Yahoo):')
for name, v in d['ccl']['detalle']:
    print(f'     {name:<10} {f(v)}')

# CCL contra nuestra fuente guardada (screener.ccl) — es lo único que tenemos almacenado hoy
ccl_nuestro = None
try:
    c = sqlite3.connect(PROD)
    r = c.execute("SELECT ccl FROM screener WHERE ccl IS NOT NULL AND ccl>0 LIMIT 1").fetchone()
    ccl_nuestro = r[0] if r else None
    c.close()
except Exception:
    pass
print('\n=== CCL: fresco vs NUESTRA fuente guardada ===')
print(f'  nuestro (screener.db) : {f(ccl_nuestro)}')
print(f'  Yahoo ADR             : {f(d["ccl"]["valor"])}   ({dif(d["ccl"]["valor"], ccl_nuestro)})')
print(f'  dolarapi              : {f(d["ccl"]["cruce"])}   ({dif(d["ccl"]["cruce"], ccl_nuestro)})')
print('\n  Nota: no tenemos MEP guardado para comparar (nuestra fuente vieja era CCL). Por eso el MEP')
print('  se valida entre fuentes frescas (criptoya vs dolarapi), que es lo más robusto que hay hoy.')
