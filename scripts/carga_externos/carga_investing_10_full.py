# -*- coding: utf-8 -*-
"""
Carga estados contables ANUALES (2 ultimos ejercicios) de 10 empresas desde investing.com
"""
import sqlite3, datetime
import os as _os
# SCREENER_DB: apunta a una copia de prueba sin tocar produccion.
# La ruta absoluta ademas ataba el script a una maquina concreta.
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
DB = _os.path.join(_RAIZ, 'data', _os.environ.get('SCREENER_DB', 'screener.db'))
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
SCHEMA = """CREATE TABLE IF NOT EXISTS investing_estados (
    ticker TEXT, period_end TEXT, estado TEXT, concepto TEXT,
    valor REAL, unidad TEXT DEFAULT 'ARS', consolidado INTEGER DEFAULT 1,
    source TEXT DEFAULT 'investing.com', loaded_at TEXT,
    UNIQUE(ticker, period_end, estado, concepto));"""

con = sqlite3.connect(DB)
con.execute(SCHEMA)

def ins(tk, pe, es, co, va, un='ARS', co2=1):
    if va is not None:
        con.execute("INSERT OR REPLACE INTO investing_estados VALUES (?,?,?,?,?,?,?,'investing.com',?)",
                    (tk, pe, es, co, va, un, co2, NOW))

# ==============================
# 1) TXAR (31/12)
# ==============================
TXAR = ('TXAR','2024-12-31','2025-12-31')
bal_txar = {
    'assets': (5909214, 7538258), 'assets_current': (2395065, 2435812), 'assets_noncurrent': (3514149, 5102446),
    'liabilities': (815719, 725497), 'liabilities_current': (745727, 628966), 'liabilities_noncurrent': (69992, 96531),
    'equity': (5093495, 6812761), 'cash': (60515, 163490), 'debt': (57063, 71723),
}
res_txar = {
    'revenue': (2027306, 2514965), 'cogs': (1708166, 2158382), 'gross_profit': (319140, 356583),
    'operating_income': (101814, 66719), 'ebitda': (182328, 171172), 'da': (85593, 111764),
    'financial_result': (52740, 94724), 'pretax_income': (174634, 220196),
    'income_tax': (-226619, 143754), 'net_income': (106715, 83419),
    'eps_basic': (23.62, 18.47), 'shares': (4517090, 4517090),
}
flu_txar = {'cfo': (-106041, 296585), 'cfi': (-37881, 1277), 'cff': (159476, -218897), 'capex': (-309099, -157214)}
for co, (v1, v2) in {**bal_txar, **res_txar, **flu_txar}.items():
    e = 'balance' if co in bal_txar else ('resultados' if co in res_txar else 'flujo')
    ins(TXAR[0], TXAR[1], e, co, v1)
    ins(TXAR[0], TXAR[2], e, co, v2)

# ==============================
# 2) COME (31/12)
# ==============================
COME = ('COME','2024-12-31','2025-12-31')
bal_come = {
    'assets': (839287.45, 787361.02), 'assets_current': (224380.36, 207066.87), 'assets_noncurrent': (614907.09, 580294.15),
    'liabilities': (232282.34, 228306.82), 'liabilities_current': (125416.83, 126503.33), 'liabilities_noncurrent': (106865.51, 101803.49),
    'equity': (607005.11, 559054.20), 'cash': (14915.87, 9157.99), 'debt': (30308.44, 39140.84),
}
res_come = {
    'revenue': (735851.47, 655953.91), 'cogs': (668561.38, 590667.56), 'gross_profit': (67290.09, 65286.35),
    'operating_income': (-10969.87, -10157.88), 'ebitda': (22769.03, 14781.04), 'da': (33738.90, 25225.68),
    'financial_result': (147764.21, -1812.46), 'pretax_income': (128435.35, -40081.50),
    'income_tax': (-22325.07, -5033.70), 'net_income': (86375.74, -58200.18),
    'eps_basic': (28.01, -9.97), 'shares': (3083750, 5837530),
}
flu_come = {'cfo': (-50161.41, 25320.75), 'cfi': (71365.72, -24480.35), 'cff': (-12057.23, -7566.38), 'capex': (-9851.30, -10927.81)}
for co, (v1, v2) in {**bal_come, **res_come, **flu_come}.items():
    e = 'balance' if co in bal_come else ('resultados' if co in res_come else 'flujo')
    ins(COME[0], COME[1], e, co, v1)
    ins(COME[0], COME[2], e, co, v2)

# ==============================
# 3) CVH (31/12)
# ==============================
CVH = ('CVH','2024-12-31','2025-12-31')
bal_cvh = {
    'assets': (14472829, 16723652), 'assets_current': (1070314, 1930666), 'assets_noncurrent': (13402515, 14792986),
    'liabilities': (7121887, 9652286), 'liabilities_current': (2585336, 3851342), 'liabilities_noncurrent': (4536551, 5800944),
    'equity': (7350942, 7071366), 'cash': (428394, 483785), 'debt': (3903757, 5483670),
}
res_cvh = {
    'revenue': (5442958, 8328814), 'cogs': (2813187, 4018033), 'gross_profit': (2629771, 4310781),
    'operating_income': (-191414, 520259), 'ebitda': (1243116, 2218406), 'da': (1434530, 1696147),
    'financial_result': (-141497, -386126), 'pretax_income': (1964784, -198279),
    'income_tax': (538286, -46338), 'net_income': (509233, -81050),
    'eps_basic': (2819.01, -448.68), 'shares': (180640, 180640),
}
flu_cvh = {'cfo': (1064739, 2379954), 'cfi': (-503787, -2999327), 'cff': (-533590, 619709), 'capex': (-457953, -1355061)}
for co, (v1, v2) in {**bal_cvh, **res_cvh, **flu_cvh}.items():
    e = 'balance' if co in bal_cvh else ('resultados' if co in res_cvh else 'flujo')
    ins(CVH[0], CVH[1], e, co, v1)
    ins(CVH[0], CVH[2], e, co, v2)

# ==============================
# 4) MIRG (31/12)
# ==============================
MIRG = ('MIRG','2024-12-31','2025-12-31')
bal_mirg = {
    'assets': (1629553, 1842350), 'assets_current': (1141551, 1312529), 'assets_noncurrent': (488002, 529821),
    'liabilities': (1238118, 1431274), 'liabilities_current': (1145918, 1385552), 'liabilities_noncurrent': (92200, 45722),
    'equity': (391435, 411076), 'cash': (29779, 11511), 'debt': (272173, 504984),
}
res_mirg = {
    'revenue': (2033932, 2502021), 'cogs': (1816161, 2144836), 'gross_profit': (217771, 357185),
    'operating_income': (119867, 259548), 'ebitda': (145091, 281364), 'da': (49776, 40687),
    'financial_result': (-74370, -101853), 'pretax_income': (434805, 40594),
    'income_tax': (-6512, -18983), 'net_income': (268624, 12579),
    'eps_basic': (1492.36, 69.88), 'shares': (180000, 180000),
}
flu_mirg = {'cfo': (-516231, -73543), 'cfi': (155196, -116386), 'cff': (218443, 175836), 'capex': (-69066, -118845)}
for co, (v1, v2) in {**bal_mirg, **res_mirg, **flu_mirg}.items():
    e = 'balance' if co in bal_mirg else ('resultados' if co in res_mirg else 'flujo')
    ins(MIRG[0], MIRG[1], e, co, v1)
    ins(MIRG[0], MIRG[2], e, co, v2)

# ==============================
# 5) CELU (31/05) - fiscal mayo
# ==============================
CELU = ('CELU','2024-05-31','2025-05-31')
bal_celu = {
    'assets': (491091.86, 325845.70), 'assets_current': (155107.82, 100692.95), 'assets_noncurrent': (335984.04, 225152.75),
    'liabilities': (341534.76, 349620.31), 'liabilities_current': (168596.50, 308851.58), 'liabilities_noncurrent': (172938.26, 40768.73),
    'equity': (149557.11, -23774.61), 'cash': (21227.63, 1698.36), 'debt': (144042.06, 133641.41),
}
res_celu = {
    'revenue': (464722.43, 258637.93), 'cogs': (340498.66, 297469.09), 'gross_profit': (124223.76, -38831.16),
    'operating_income': (61320.03, -110913.54), 'ebitda': (98631.73, -50748.23), 'da': (37356.71, 60200.81),
    'financial_result': (-27673.14, -36276.25), 'pretax_income': (32124.54, -145659.97),
    'income_tax': (34785.86, -17201.37), 'net_income': (396.77, -133152.23),
    'eps_basic': (3.93, -1318.68), 'shares': (100970, 100970),
}
flu_celu = {'cfo': (33540.07, -35812.16), 'cfi': (-6305.56, -4653.03), 'cff': (-7133.60, 24100.95), 'capex': (-5499.59, -3730.85)}
for co, (v1, v2) in {**bal_celu, **res_celu, **flu_celu}.items():
    e = 'balance' if co in bal_celu else ('resultados' if co in res_celu else 'flujo')
    ins(CELU[0], CELU[1], e, co, v1)
    ins(CELU[0], CELU[2], e, co, v2)

# ==============================
# 6) CTIO (31/12)
# ==============================
CTIO = ('CTIO','2024-12-31','2025-12-31')
bal_ctio = {
    'assets': (1668198, 1555530), 'assets_current': (737256, 482620), 'assets_noncurrent': (930942, 1072910),
    'liabilities': (712630, 632436), 'liabilities_current': (287849, 229011), 'liabilities_noncurrent': (424781, 403425),
    'equity': (955568, 923094), 'cash': (11635, 35239), 'debt': (0, 0),
}
res_ctio = {
    'revenue': (212339, 247884), 'cogs': (110723, 205573), 'gross_profit': (101616, 42311),
    'operating_income': (14010, -23755), 'ebitda': (14689, -23115), 'da': (679, 640),
    'financial_result': (4950, -13196), 'pretax_income': (69103, -36391),
    'income_tax': (-34833, -10822), 'net_income': (-101200, -1215),
    'eps_basic': (-246.89, -2.96), 'shares': (409910, 409910),
}
flu_ctio = {'cfo': (26664, -85089), 'cfi': (66253, 151870), 'cff': (-73883, -37583), 'capex': (-605, -692)}
for co, (v1, v2) in {**bal_ctio, **res_ctio, **flu_ctio}.items():
    e = 'balance' if co in bal_ctio else ('resultados' if co in res_ctio else 'flujo')
    ins(CTIO[0], CTIO[1], e, co, v1)
    ins(CTIO[0], CTIO[2], e, co, v2)

# ==============================
# 7) HARG (31/12)
# ==============================
HARG = ('HARG','2024-12-31','2025-12-31')
bal_harg = {
    'assets': (973892, 986727), 'assets_current': (184103, 163952), 'assets_noncurrent': (789789, 822775),
    'liabilities': (345602, 399521), 'liabilities_current': (208358, 283958), 'liabilities_noncurrent': (137244, 115563),
    'equity': (628290, 587206), 'cash': (25136, 4953), 'debt': (6299, 11582),
}
res_harg = {
    'revenue': (526498, 499267), 'cogs': (368514, 370426), 'gross_profit': (157984, 128841),
    'operating_income': (24544, -23816), 'ebitda': (72741, 26138), 'da': (49808, 51654),
    'financial_result': (-3761, -44581), 'pretax_income': (88531, -45715),
    'income_tax': (33244, -18301), 'net_income': (53226, -40169),
    'eps_basic': (145.43, -109.75), 'shares': (366000, 366000),
}
flu_harg = {'cfo': (68199, 6561), 'cfi': (-80116, -62675), 'cff': (-2553, 38081), 'capex': (-72370, -60562)}
for co, (v1, v2) in {**bal_harg, **res_harg, **flu_harg}.items():
    e = 'balance' if co in bal_harg else ('resultados' if co in res_harg else 'flujo')
    ins(HARG[0], HARG[1], e, co, v1)
    ins(HARG[0], HARG[2], e, co, v2)

# ==============================
# 8) LEDE (31/05) - fiscal mayo
# ==============================
LEDE = ('LEDE','2024-05-31','2025-05-31')
bal_lede = {
    'assets': (748876.42, 761018.91), 'assets_current': (379134.19, 378572.25), 'assets_noncurrent': (369742.23, 382446.66),
    'liabilities': (272554.94, 331448.46), 'liabilities_current': (186582.38, 214559.47), 'liabilities_noncurrent': (85972.56, 116888.99),
    'equity': (476321.47, 429570.45), 'cash': (2578.47, 6058.00), 'debt': (62194.86, 154979.24),
}
res_lede = {
    'revenue': (1048875.07, 831947.42), 'cogs': (684839.48, 635831.39), 'gross_profit': (364035.60, 196116.03),
    'operating_income': (136473.01, -8183.11), 'ebitda': (169431.82, 27887.18), 'da': (35453.66, 37665.15),
    'financial_result': (-2256.37, -11422.31), 'pretax_income': (161197.97, -23661.10),
    'income_tax': (98779.82, -9493.07), 'net_income': (56186.66, -25178.47),
    'eps_basic': (127.78, -57.48), 'shares': (439710, 438070),
}
flu_lede = {'cfo': (141402.33, -47477.37), 'cfi': (-57034.87, -35326.63), 'cff': (-93261.08, 71031.45), 'capex': (-64501.54, -41030.22)}
for co, (v1, v2) in {**bal_lede, **res_lede, **flu_lede}.items():
    e = 'balance' if co in bal_lede else ('resultados' if co in res_lede else 'flujo')
    ins(LEDE[0], LEDE[1], e, co, v1)
    ins(LEDE[0], LEDE[2], e, co, v2)

# ==============================
# 9) CAPX (30/04) - fiscal abril
# ==============================
CAPX = ('CAPX','2025-04-30','2026-04-30')
bal_capx = {
    'assets': (1245576.69, 1678867.38), 'assets_current': (104834.92, 227713.76), 'assets_noncurrent': (1140741.77, 1451153.62),
    'liabilities': (725849.20, 963234.88), 'liabilities_current': (243102.11, 283308.76), 'liabilities_noncurrent': (482747.09, 679926.12),
    'equity': (519727.49, 715632.50), 'cash': (9203.72, 113806.18), 'debt': (494148.86, 702529.79),
}
res_capx = {
    'revenue': (407152.62, 600893.79), 'cogs': (300622.41, 401129.81), 'gross_profit': (106530.20, 199763.98),
    'operating_income': (17498.65, 62259.82), 'ebitda': (149829.95, 206298.87), 'da': (133343.97, 145379.32),
    'financial_result': (-40219.25, -210298.42), 'pretax_income': (20473.90, 61070.67),
    'income_tax': (-48474.01, 15201.02), 'net_income': (25856.74, 45911.07),
    'eps_basic': (143.81, 255.34), 'shares': (179800, 179800),
}
flu_capx = {'cfo': (174395.63, 149888.18), 'cfi': (-184388.06, -136941.82), 'cff': (-10394.96, 64242.91), 'capex': (-177196.60, -141817.36)}
for co, (v1, v2) in {**bal_capx, **res_capx, **flu_capx}.items():
    e = 'balance' if co in bal_capx else ('resultados' if co in res_capx else 'flujo')
    ins(CAPX[0], CAPX[1], e, co, v1)
    ins(CAPX[0], CAPX[2], e, co, v2)

# ==============================
# 10) MOLA (31/03) - fiscal marzo
# ==============================
MOLA = ('MOLA','2025-03-31','2026-03-31')
bal_mola = {
    'assets': (749601, 960367), 'assets_current': (618485, 747263), 'assets_noncurrent': (131116, 213104),
    'liabilities': (563605, 818992), 'liabilities_current': (563552, 735199), 'liabilities_noncurrent': (53, 83793),
    'equity': (185996, 141375), 'cash': (13526, 1087), 'debt': (52973, 449503),
}
res_mola = {
    'revenue': (3038112, 4154408), 'cogs': (2952753, 3746724), 'gross_profit': (85359, 407684),
    'operating_income': (15934, 312033), 'ebitda': (25170, 325485), 'da': (9418, 13670),
    'financial_result': (41925, -22017), 'pretax_income': (58167, 299821),
    'income_tax': (6953, 82883), 'net_income': (51201, 216803),
    'eps_basic': (1043.17, 4424.55), 'shares': (49080, 49000),
}
flu_mola = {'cfo': (-93182, 159862), 'cfi': (123345, -113483), 'cff': (-39157, -47690), 'capex': (-45399, -34835)}
for co, (v1, v2) in {**bal_mola, **res_mola, **flu_mola}.items():
    e = 'balance' if co in bal_mola else ('resultados' if co in res_mola else 'flujo')
    ins(MOLA[0], MOLA[1], e, co, v1)
    ins(MOLA[0], MOLA[2], e, co, v2)

con.commit()

# Verificacion
print("=== FILAS POR TICKER / PERIOD_END ===")
cur = con.execute("""
    SELECT ticker, period_end,
           SUM(CASE WHEN estado='balance' THEN 1 ELSE 0 END) as bal,
           SUM(CASE WHEN estado='resultados' THEN 1 ELSE 0 END) as res,
           SUM(CASE WHEN estado='flujo' THEN 1 ELSE 0 END) as flu
    FROM investing_estados GROUP BY ticker, period_end ORDER BY ticker, period_end
""")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]}: bal={r[2]} res={r[3]} flu={r[4]}")

print("\n=== IDENTIDAD CONTABLE (assets = liabilities + equity) ===")
cur = con.execute("""
    SELECT ticker, period_end,
           MAX(CASE WHEN concepto='assets' THEN valor END),
           MAX(CASE WHEN concepto='liabilities' THEN valor END),
           MAX(CASE WHEN concepto='equity' THEN valor END)
    FROM investing_estados WHERE estado='balance'
    GROUP BY ticker, period_end ORDER BY ticker, period_end
""")
for r in cur.fetchall():
    tk, pe, a, l, e = r
    if a and l and e:
        dif = abs(a - (l+e))
        ok = 'OK' if dif/a < 0.02 else f'DIF={dif:.0f}'
        print(f"  {tk} {pe}: {a:.0f} = {l:.0f} + {e:.0f} -> {ok}")

print(f"\nTotal filas insertadas: {con.execute('SELECT COUNT(*) FROM investing_estados').fetchone()[0]}")
con.close()
