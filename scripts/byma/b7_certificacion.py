"""E6 - b7_certificacion: estado por (empresa, metrica).

Statuses: CERTIFIED | NOT_CERTIFIED (+motivos acumulados).
Bloqueos (deterministicos):
  - IDENTIDAD ALTA (b2) -> bloquea metricas fundamentales derivadas de balance/TTM
  - >=5 anomalias ESCALA_JUMP ALTA en la empresa -> idem
  - MARGEN NETO ALTA (b2) -> bloquea margen_neto
  - FAIL PER_2PATH (b6) -> bloquea per y eps_anual (soscha split/escala/dilucion)
Warnings declarados (no bloquean): staleness VIEJO, mezcla temporal,
flags propios de la metrica (NOMINAL_sin_deflactar, CFI_positivo, es_FY_no_TTM).
"""
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = BASE + r'\data\byma_pipeline.db'
con = sqlite3.connect(PIPE)
c = con.cursor()
now = datetime.now().isoformat()

FUND = {'per', 'margen_neto', 'deuda_ebitda', 'roe_5y', 'fcf_market_cap'}
MKT = {'precio_usd', 'max_52w', 'dif_max_52w', 'min_52w', 'dif_min_52w'}

c.execute("DROP TABLE IF EXISTS certificacion")
c.execute("""CREATE TABLE certificacion (
    cuit TEXT, ticker TEXT, metrica TEXT, valor REAL,
    status TEXT, motivos TEXT, built_at TEXT,
    PRIMARY KEY(cuit, metrica))""")

ident_bad = {r[0] for r in c.execute(
    """SELECT DISTINCT cuit FROM anomalias
       WHERE check_id='IDENTIDAD' AND severidad='ALTA'""")}
margen_bad = {r[0] for r in c.execute(
    """SELECT DISTINCT cuit FROM anomalias
       WHERE check_id='MARGEN_NETO' AND severidad='ALTA'""")}
escala_n = {r[0]: r[1] for r in c.execute(
    """SELECT cuit, COUNT(*) FROM anomalias
       WHERE check_id='ESCALA_JUMP' AND severidad='ALTA'
       GROUP BY cuit HAVING COUNT(*)>=5""")}
per_fail = {r[0] for r in c.execute(
    """SELECT DISTINCT cuit FROM validacion_mat
       WHERE check_id='PER_2PATH' AND resultado='FAIL'""")}

stats = {'CERTIFIED': 0, 'NOT_CERTIFIED': 0}
rows = []
for cu, tk, met, val, flag in c.execute(
        """SELECT cuit, ticker, metrica, valor, flag FROM metricas ORDER BY ticker"""):
    mot, blk = [], False
    if cu in ident_bad and met in FUND:
        blk = True; mot.append('IDENTIDAD_balance')
    if cu in escala_n and met in FUND:
        blk = True; mot.append(f'ESCALA_ALTA_x{escala_n[cu]}')
    if cu in margen_bad and met == 'margen_neto':
        blk = True; mot.append('MARGEN_ALTA_CNV')
    if cu in per_fail and met in ('per', 'eps_anual'):
        blk = True; mot.append('PER_2PATH_desvio(split/escala?)')
    if met in MKT | FUND & {'per', 'fcf_market_cap'} and 'staleness' in (flag or ''):
        mot.append('stale_mercado_44-54d')
    if met in MKT and 'mezcla' not in ' '.join(mot):
        pass
    if flag:
        mot.append(flag.strip())
    st = 'NOT_CERTIFIED' if blk else 'CERTIFIED'
    stats[st] += 1
    rows.append((cu, tk, met, val, st, '; '.join(mot), now))

c.executemany('INSERT OR REPLACE INTO certificacion VALUES (?,?,?,?,?,?,?)', rows)

print(f'RESUMEN b7_certificacion: {stats["CERTIFIED"]} CERTIFIED, '
      f'{stats["NOT_CERTIFIED"]} NOT_CERTIFIED sobre {len(rows)} metricas')
print('\n-- Empresas con metricas bloqueadas:')
for r in c.execute("""SELECT ticker, GROUP_CONCAT(DISTINCT metricas_bloq) FROM (
        SELECT ticker, metrica AS metricas_bloq FROM certificacion
        WHERE status='NOT_CERTIFIED') GROUP BY ticker ORDER BY ticker"""):
    print(f'  {r[0]:<8} {r[1]}')
print('\n-- Motivos:')
for r in c.execute("""SELECT motivos, COUNT(*) FROM certificacion
    WHERE status='NOT_CERTIFIED' GROUP BY motivos ORDER BY 2 DESC LIMIT 12"""):
    print(f'  {r[1]:>3}  {r[0]}')
con.commit()
con.close()
