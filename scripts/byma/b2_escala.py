"""
E3a — b2_escala: detectores de anomalia de escala/unidad sobre partidas_norm.

Checks (FASE 5):
  ESCALA_JUMP      salto ~1e3/~1e6 entre períodos consecutivos del mismo concepto
  MARGEN_NETO      |NI/Revenue| fuera de rango plausible
  ROE_EXTREMO      |NI/Equity| > 10 o equity<=0 con NI!=0
  ROA_EXTREMO      |NI/Assets| > 3
  EBITDA_MARGEN    |EBITDA/Revenue| > 2
  IDENTIDAD        |Assets-(Lias+Eq)|/Assets > 2%
  CERO_SOSPECHOSO  Revenue/Assets/Equity = 0 en período reciente

Escribe tabla anomalias. NO corrige nada.
"""
import os
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = os.path.join(BASE, 'data', 'byma_pipeline.db')
con = sqlite3.connect(PIPE)
c = con.cursor()

c.execute("DROP TABLE IF EXISTS anomalias")
c.execute("""CREATE TABLE anomalias (
    id INTEGER PRIMARY KEY,
    cuit TEXT, ticker TEXT, concepto TEXT, periodo_hasta TEXT,
    check_id TEXT, severidad TEXT, valor REAL, referencia REAL,
    ratio REAL, detalle TEXT, built_at TEXT)""")
now = datetime.now().isoformat()
N = 0

def reg(cuit, tk, con_, pe, chk, sev, val, ref, ratio, det):
    global N
    c.execute('INSERT INTO anomalias VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?)',
              (cuit, tk, con_, pe, chk, sev, val, ref, ratio, det, now))
    N += 1

# --- 1) ESCALA_JUMP: saltos de orden de magnitud entre cierres consecutivos
rows = c.execute("""
    SELECT p.cuit, p.ticker, p.concepto_normalizado, p.periodo_hasta, p.valor
    FROM partidas_norm p
    WHERE p.clase='flujo' AND p.period_type='acumulado' AND p.valor IS NOT NULL
    ORDER BY p.cuit, p.concepto_normalizado, p.periodo_hasta""").fetchall()
prev = {}
for cuit, tk, co, pe, v in rows:
    k = (cuit, co)
    if k in prev and prev[k][1]:
        pv, ppe = prev[k]
        if pv != 0 and abs(v) > 0 and pe[:4] == ppe[:4] or True:
            r = abs(v / pv) if pv else None
            if r and (r >= 900 or r <= 0.0011):
                # solo si el salto es casi exactamente 10^n (tipico error de unidad)
                import math
                lg = math.log10(r)
                if min(abs(lg - round(lg)), 0.15) < 0.15 and abs(lg) >= 2:
                    reg(cuit, tk, co, pe, 'ESCALA_JUMP', 'ALTA', v, pv, r,
                        f'salto x{r:.4g} vs {ppe}; log10={lg:.2f}')
    prev[k] = (v, pe)

# --- 2..7) checks de plausibilidad por período (acumulado anual completo)
q = """
SELECT p.cuit, MAX(p.ticker), p.periodo_hasta,
       SUM(CASE WHEN p.concepto_normalizado='Revenue' THEN p.valor END) rev,
       SUM(CASE WHEN p.concepto_normalizado='NetIncome' THEN p.valor END) ni,
       SUM(CASE WHEN p.concepto_normalizado='EBITDA' THEN p.valor END) ebitda,
       SUM(CASE WHEN p.concepto_normalizado='Equity' AND p.period_type='acumulado' THEN p.valor END) eq,
       SUM(CASE WHEN p.concepto_normalizado='Assets' AND p.period_type='acumulado' THEN p.valor END) act
FROM partidas_norm p
WHERE p.period_type='acumulado'
GROUP BY p.cuit, p.periodo_hasta"""
for cuit, tk, pe, rev, ni, ebitda, eq, act in c.execute(q).fetchall():
    if rev and ni and rev > 0:
        mg = ni / rev
        if abs(mg) > 5:
            reg(cuit, tk, 'NetIncome/Revenue', pe, 'MARGEN_NETO', 'ALTA', ni, rev, mg,
                f'margen {mg:.2%} implausible')
    if eq is not None and ni:
        if eq <= 0 and ni != 0:
            reg(cuit, tk, 'NetIncome/Equity', pe, 'ROE_EXTREMO', 'MEDIA', ni, eq, None,
                f'equity {eq:.4g}<=0 con NI!=0 -> ROE indefinido')
        elif eq != 0:
            roe = ni / eq
            if abs(roe) > 10:
                reg(cuit, tk, 'NetIncome/Equity', pe, 'ROE_EXTREMO', 'ALTA', ni, eq, roe,
                    f'|ROE| {roe:.3g} > 10')
    if act and ni and act != 0:
        roa = ni / act
        if abs(roa) > 3:
            reg(cuit, tk, 'NetIncome/Assets', pe, 'ROA_EXTREMO', 'MEDIA', ni, act, roa,
                f'|ROA| {roa:.3g} > 3')
    if ebitda is not None and rev and rev > 0:
        m = ebitda / rev
        if abs(m) > 2:
            reg(cuit, tk, 'EBITDA/Revenue', pe, 'EBITDA_MARGEN', 'MEDIA', ebitda, rev, m,
                f'margen EBITDA {m:.3g}')
    if act and eq is not None and act > 0:
        ident = (act - ((eq or 0))) / act
        # identidad aproximada sin Liabilities aqui se valida en check dedicado abajo
    if rev == 0 or act == 0 or (eq is not None and eq == 0):
        if pe >= '2025-01-01':
            reg(cuit, tk, 'Revenue/Assets/Equity', pe, 'CERO_SOSPECHOSO', 'ALTA',
                rev if rev == 0 else (act if act == 0 else eq), None, None,
                'valor 0 en período reciente')

# --- identidad contable independiente (balance acumulado)
q2 = """
SELECT p.cuit, MAX(p.ticker), p.periodo_hasta,
       SUM(CASE WHEN p.concepto_normalizado='Assets' THEN p.valor END) act,
       SUM(CASE WHEN p.concepto_normalizado='Liabilities' THEN p.valor END) lia,
       SUM(CASE WHEN p.concepto_normalizado='Equity' THEN p.valor END) eq
FROM partidas_norm p
WHERE p.concepto_normalizado IN ('Assets','Liabilities','Equity') AND p.period_type='acumulado'
GROUP BY p.cuit, p.periodo_hasta HAVING act IS NOT NULL AND lia IS NOT NULL"""
for cuit, tk, pe, act, lia, eq in c.execute(q2).fetchall():
    if act:
        desvio = abs(act - (lia + (eq or 0))) / abs(act)
        if desvio > 0.02:
            reg(cuit, tk, 'Assets=Liab+Equity', pe, 'IDENTIDAD', 'ALTA', act, lia + (eq or 0),
                desvio, f'desvio {desvio:.3%} > 2%')
con.commit()

print(f'RESUMEN b2_escala: {N:,} anomalias registradas')
for r in c.execute("""SELECT check_id, severidad, COUNT(*), COUNT(DISTINCT cuit)
                      FROM anomalias GROUP BY 1,2 ORDER BY 3 DESC"""):
    print(f'  {r[0]:<16} sev={r[1]:<6} n={r[2]:>5} empresas={r[3]}')
top = c.execute("""SELECT ticker, COUNT(*) FROM anomalias
                   WHERE severidad='ALTA' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall()
print(f'  top ALTA por empresa: {top}')
con.close()
