# -*- coding: utf-8 -*-
"""
PLANTILLA DE CARGA — copiar este archivo, completar los datos de investing.com y correr:
    cd <raiz del repo>
    python scripts/carga_externos/template_carga.py

El agente operativo SOLO completa los bloques marcados. NO tocar el loader.
Idempotente: si te equivocaste, corregis el dato y volves a correr (pisa por PK).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from loader import save_ratios, save_eerr, status

# ============================================================================
# 1) RATIOS HEADLINE  (pestaña "Ratios" o "Financial Summary > Key Ratios")
#    Unidades: per/p_book = multiplo | roe/div_yield/debt_equity = % (11.14)
#              ebitda = MILLONES ARS (si dice "B" -> x1000) | financiera sin EBITDA -> 0
#    Campo faltante ('-') -> None
# ============================================================================
RATIOS = [
    # ('TICKER', per, p_book, debt_equity, roe, div_yield, ebitda, fair_value, fv_upside),
    # ejemplo:
    # ('METR', 7.2, 1.1, 25.3, 18.4, 4.1, 210000, 3100, 12.5),
]

# ============================================================================
# 2) EERR TRIMESTRAL  (pestaña "Income Statement > Quarterly")
#    valores en MILLONES, trimestres STANDALONE (como los muestra investing).
#    period_end = fin de cada trimestre. Celda vacia ('-') -> None
#    Minimo homogeneo: Revenue, GrossProfit, OperatingIncome, EBITDA, NetIncome
# ============================================================================
EERR = {
    # 'TICKER': {
    #   'periods': ['2024-03-31','2024-06-30','2024-09-30','2024-12-31','2025-03-31',
    #               '2025-06-30','2025-09-30','2025-12-31','2026-03-31'],
    #   'lines': {
    #     'Revenue':         [...],
    #     'GrossProfit':     [...],
    #     'OperatingIncome': [...],
    #     'EBITDA':          [...],
    #     'NetIncome':       [...],
    #   }
    # },
}

# ============================================================================
# EJECUCION — no tocar
# ============================================================================
if __name__=='__main__':
    print('== Cargando RATIOS ==')
    for row in RATIOS:
        tk=row[0]; vals=row[1:]
        keys=['per','p_book','debt_equity','roe','div_yield','ebitda','fair_value','fv_upside']
        r=save_ratios(tk, **dict(zip(keys, vals)))
        print(' ', r)
    print('\n== Cargando EERR ==')
    for tk, d in EERR.items():
        r=save_eerr(tk, d['periods'], d['lines'])
        print(' ', r)
    print('\n== COBERTURA ==')
    s=status()
    print(f"  ratios: {len(s['ratios_ok'])}/56 | eerr: {len(s['eerr_ok'])}/56")
    print(f"  falta ratios ({len(s['ratios_falta'])}):", ' '.join(s['ratios_falta']))
    print(f"  falta eerr   ({len(s['eerr_falta'])}):", ' '.join(s['eerr_falta']))
