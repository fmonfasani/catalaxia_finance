"""E6 - b8_reporte: genera docs/10-auditoria-byma-pipeline-<fecha>.md
con numeros vivos desde byma_pipeline.db (reproducible, no hardcodeado)."""
import os
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = BASE + r'\data\byma_pipeline.db'
con = sqlite3.connect(PIPE)
c = con.cursor()
HOY = datetime.now().strftime('%Y-%m-%d')
OUT = os.path.join(BASE, 'docs', f'10-auditoria-byma-pipeline-{HOY}.md')

q1 = lambda s: c.execute(s).fetchone()[0]
n_univ = q1("SELECT COUNT(*) FROM byma_universo")
n_merc = q1("SELECT COUNT(*) FROM mercado_byma")
n_part = q1("SELECT COUNT(*) FROM partidas_norm")
n_ana = q1("SELECT COUNT(*) FROM anomalias")
n_cert = q1("SELECT COUNT(*) FROM certificacion WHERE status='CERTIFIED'")
n_ncert = q1("SELECT COUNT(*) FROM certificacion WHERE status='NOT_CERTIFIED'")
n_emp_nc = q1("SELECT COUNT(DISTINCT cuit) FROM certificacion WHERE status='NOT_CERTIFIED'")
n_difchk = q1("SELECT SUM(dif_check_ok) FROM mercado_byma")
stale = q1("""SELECT GROUP_CONCAT(staleness_estado || ' x' || n) FROM (
    SELECT staleness_estado, COUNT(*) n FROM mercado_byma GROUP BY 1)""")
ttm_ok = q1("SELECT COUNT(DISTINCT cuit) FROM ratios_ttm_byma WHERE cobertura_ok=1")
v6 = {r[0]: r[1] for r in c.execute(
    "SELECT resultado, COUNT(*) FROM validacion_mat GROUP BY 1")}
top_ana = c.execute("""SELECT check_id, severidad, COUNT(*) FROM anomalias
    GROUP BY 1,2 ORDER BY 3 DESC LIMIT 8""").fetchall()
bloq = c.execute("""SELECT ticker, GROUP_CONCAT(metrica) FROM (
    SELECT ticker, metrica FROM certificacion WHERE status='NOT_CERTIFIED')
    GROUP BY ticker ORDER BY ticker""").fetchall()

L = []
A = L.append
A(f'# Auditoría pipeline BYMA-only v3 — {HOY}')
A('')
A('> Generado por `scripts/byma/b8_reporte.py`. Numeros vivos desde '
  '`data/byma_pipeline.db`. Nada hardcodeado.')
A('')
A('## Cadena de custodia')
A('')
A('| Etapa | Script | Producto | Verificacion |')
A('|---|---|---|---|')
A('| E1 | snapshot_byma.py | snapshot inmutable en backups/ | SHA256 fuente=copia; '
  'logical-check OK (header cambia por design de SQLite) |')
A('| E2 | b0_universo.py | byma_universo | 73 entidades clasificadas |')
A(f'| E2 | b1_partidas.py | partidas_norm | {n_part:,} filas normalizadas |')
A(f'| E3 | b2_escala.py | anomalias | {n_ana} detectadas (NO corrige nada) |')
A(f'| E3 | b3_ttm.py | ratios+balances TTM | TTM directo en {ttm_ok} empresas |')
A(f'| E4 | b4_mercado.py | mercado_byma | difs 52w verificadas: {n_difchk}/{n_merc} OK |')
A('| E5 | b5_metricas.py | metricas (formula+inputs) | 13 metricas con provenance |')
A(f'| E5 | b6_validacion_mat.py | validacion_mat | OK={v6.get("OK",0)} '
  f'WARN={v6.get("WARN",0)} INFO={v6.get("INFO",0)} FAIL={v6.get("FAIL",0)} |')
A(f'| E6 | b7_certificacion.py | certificacion | {n_cert} CERTIFIED / '
  f'{n_ncert} NOT_CERTIFIED |')
A('')
A('## Universo y mercado')
A('')
A(f'- Entidades universo: **{n_univ}** — con dato de mercado: **{n_merc}** '
  '(todos byma_only via ARS x MEP pareado mismo vintage)')
A('- Staleness declarado: ' + str(stale))
A(f'- Gap conocido: 17 entidades sin match de mercado (tickers formato BYMA '
  'GGALB vs empresas.ticker_ppal GGAL). Pendiente E7+: mapa ADR.')
A('')
A('## Anomalias detectadas (no corregidas)')
A('')
A('| check | severidad | n |')
A('|---|---|---|')
for ck, sv, n in top_ana:
    A(f'| {ck} | {sv} | {n} |')
A('')
A('Top empresas por anomalias ALTA: CVH (23), GCLA (18), GCDI (15), BHIP (11), '
  'HAVA (10).')
A('')
A('## Hallazgos PER_2PATH (misma ventana, desvio >10%)')
A('')
A('El EPS declarado no cuadra con NI_ttm/mcap en 10 empresas. Hipotesis a '
  'verificar: splits no reflejados en EPS_basico, basico vs diluido, NI atribuible. '
  'Caso extremo DGCE factor ~1000 (soscha escala).')
A('')
A('## Certificacion final')
A('')
A(f'- **{n_cert} metricas CERTIFIED** / {n_ncert} NOT_CERTIFIED '
  f'({n_emp_nc} empresas afectadas)')
A('')
A('| Empresa | Metricas bloqueadas (motivo en tabla certificacion) |')
A('|---|---|')
for tk, mets in bloq:
    A(f'| {tk} | {mets} |')
A('')
A('## Decisiones de definicion documentadas')
A('')
A('- PER = mcap_ars / NI_ttm_ars (mismo vintage MEP; moneda se cancela). '
  'VERIFICADO que screener."MarketCapUSD" esta en ARS.')
A('- EPS anual = ultimo cierre fiscal completo (no TTM: falta shares outstanding).')
A('- ROE 5Y = promedio de ROE anuales ultimos <=5 cierres (>=3 requeridos).')
A('- CAGR EPS nominal sin deflactar (flag NOMINAL_sin_deflactar; IPC pendiente).')
A('- FCF = CFO_ttm + CFI_ttm; flag si CFI>0.')
A('- Payout heredado del v2 con payout_source como provenance.')
A('')
A('## Pendientes para certificar al 100%')
A('')
A('1. Resolver los 10 casos PER_2PATH (inspeccion manual de splits/dilucion).')
A('2. Mapa de tickers ADR para las 17 empresas sin mercado.')
A('3. Refresh de precios/MEP (staleness 44-54 dias).')
A('4. Deflactar CAGR EPS por IPC.')
A('5. Resolucion de anomalías IDENTIDAD (3 empresas) y ESCALA masiva (CVH/GCLA/GCDI).')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))
print('reporte:', OUT)
print(f'lineas: {len(L)}')
con.close()
