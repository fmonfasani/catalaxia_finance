# -*- coding: utf-8 -*-
"""
Carga estados contables ANUALES (2 ultimos ejercicios) de 10 empresas argentinas
desde investing.com a tabla investing_estados.
"""
import sqlite3, datetime
from pathlib import Path

import os as _os
# SCREENER_DB: apunta a una copia de prueba sin tocar produccion.
# La ruta absoluta ademas ataba el script a una maquina concreta.
DB = Path(__file__).resolve().parents[2] / 'data' / _os.environ.get('SCREENER_DB', 'screener.db')
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS investing_estados (
    ticker TEXT, period_end TEXT, estado TEXT, concepto TEXT,
    valor REAL, unidad TEXT DEFAULT 'ARS', consolidado INTEGER DEFAULT 1,
    source TEXT DEFAULT 'investing.com', loaded_at TEXT,
    UNIQUE(ticker, period_end, estado, concepto)
);
"""

def upsert(con, ticker, period_end, estado, concepto, valor, unidad='ARS', consolidado=1):
    con.execute("""
        INSERT OR REPLACE INTO investing_estados
        (ticker, period_end, estado, concepto, valor, unidad, consolidado, source, loaded_at)
        VALUES (?,?,?,?,?,?,?,'investing.com',?)
    """, (ticker, period_end, estado, concepto, valor, unidad, consolidado, NOW))

def cargar_empresa(con, ticker, period_end_1, period_end_2, estados):
    """
    estados = {'balance': {concepto: val_1, ...}, 'resultados': {...}, 'flujo': {...}}
    val_1 corresponde a period_end_1, val_2 a period_end_2
    """
    for estado, conceptos in estados.items():
        for concepto, (v1, v2) in conceptos.items():
            if v1 is not None:
                upsert(con, ticker, period_end_1, estado, concepto, v1)
            if v2 is not None:
                upsert(con, ticker, period_end_2, estado, concepto, v2)

def verificar(con):
    cur = con.execute("""
        SELECT ticker, period_end,
               SUM(CASE WHEN estado='balance' THEN 1 ELSE 0 END) as bal,
               SUM(CASE WHEN estado='resultados' THEN 1 ELSE 0 END) as res,
               SUM(CASE WHEN estado='flujo' THEN 1 ELSE 0 END) as flu
        FROM investing_estados GROUP BY ticker, period_end ORDER BY ticker, period_end
    """)
    for r in cur.fetchall():
        print(f'  {r[0]} {r[1]}: balance={r[2]} conceptos, resultados={r[3]}, flujo={r[4]}')
    print()

    # Check identity: assets = liabilities + equity
    cur2 = con.execute("""
        SELECT ticker, period_end,
               MAX(CASE WHEN concepto='assets' THEN valor END) as assets,
               MAX(CASE WHEN concepto='liabilities' THEN valor END) as liab,
               MAX(CASE WHEN concepto='equity' THEN valor END) as equity
        FROM investing_estados WHERE estado='balance'
        GROUP BY ticker, period_end ORDER BY ticker, period_end
    """)
    for r in cur2.fetchall():
        tk, pe, a, l, e = r
        if a and l and e:
            diff = abs(a - (l + e))
            ok = 'OK' if diff < 0.01 * a else f'DIF={diff:.0f}'
            print(f'  {tk} {pe}: assets={a:.0f} = liab({l:.0f})+equity({e:.0f}) -> {ok}')

# ============================================================================
# DATOS POR EMPRESA
# Cada tupla: (ticker, period_end_1, period_end_2, {estados})
# Valores en MILLONES de ARS (excepto eps_basic=ARS/accion, shares=acciones)
# ============================================================================

# ---- TXAR (31/12) ----
TXAR = ('TXAR','2024-12-31','2025-12-31', {
    'balance': {
        'assets': (5909214, 7538258),
        'assets_current': (2395065, 2435812),
        'assets_noncurrent': (3514149, 5102446),
        'liabilities': (815719, 725497),
        'liabilities_current': (745727, 628966),
        'liabilities_noncurrent': (69992, 96531),
        'equity': (5093495, 6812761),
        'cash': (60515, 163490),
        'debt': (57063, 71723),
    },
    'resultados': {
        'revenue': (2027306, 2514965),
        'cogs': (1708166, 2158382),
        'gross_profit': (319140, 356583),
        'operating_income': (101814, 66719),
        'ebitda': (182328, 171172),
        'da': (85593, 111764),
        'financial_result': (52740, 94724),
        'pretax_income': (174634, 220196),
        'income_tax': (-226619, 143754),
        'net_income': (106715, 83419),
        'eps_basic': (23.62, 18.47),
        'shares': (4517090, 4517090),
    },
    'flujo': {
        'cfo': (-106041, 296585),
        'cfi': (-37881, 1277),
        'cff': (159476, -218897),
        'capex': (-309099, -157214),
    },
})

# ---- COME (31/12) ----
COME = ('COME','2024-12-31','2025-12-31', {
    'balance': {
        'assets': (839287.45, 787361.02),
        'assets_current': (224380.36, 207066.87),
        'assets_noncurrent': (614907.09, 580294.15),
        'liabilities': (232282.34, 228306.82),
        'liabilities_current': (125416.83, 126503.33),
        'liabilities_noncurrent': (106865.51, 101803.49),
        'equity': (607005.11, 559054.20),
        'cash': (14915.87, 9157.99),
        'debt': (30308.44, 39140.84),
    },
    'resultados': {
        'revenue': (735851.47, 655953.91),
        'cogs': (668561.38, 590667.56),
        'gross_profit': (67290.09, 65286.35),
        'operating_income': (-10969.87, -10157.88),
        'ebitda': (22769.03, 14781.04),
        'da': (33738.90, 25225.68),
        'financial_result': (147764.21, -1812.46),
        'pretax_income': (128435.35, -40081.50),
        'income_tax': (-22325.07, -5033.70),
        'net_income': (86375.74, -58200.18),
        'eps_basic': (28.01, -9.97),
        'shares': (3083750, 5837530),
    },
    'flujo': {
        'cfo': (-50161.41, 25320.75),
        'cfi': (71365.72, -24480.35),
        'cff': (-12057.23, -7566.38),
        'capex': (-9851.30, -10927.81),
    },
})

# Empresas cargadas hasta ahora (agregar las 8 restantes con el mismo formato)
EMPRESAS = [TXAR, COME]

if __name__ == '__main__':
    con = sqlite3.connect(DB)
    con.execute(SCHEMA)
    for emp in EMPRESAS:
        cargar_empresa(con, *emp)
    con.commit()
    print(f'Cargadas {len(EMPRESAS)} empresas en investing_estados:', [e[0] for e in EMPRESAS])
    verificar(con)
    con.close()
