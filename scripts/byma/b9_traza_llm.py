"""E7 - b9_traza_llm: exporta la traza completa de los 13 ratios por empresa,
capa por capa, para analisis de anomalias paso a paso (humano o LLM).

Salida: data/export_llm/
  traza_13ratios.csv   una fila por (empresa, ratio) con todas las capas
  README_TRAZA.md      diccionario de columnas y como leerlo
"""
import csv
import os
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = BASE + r'\data\byma_pipeline.db'
OUT = BASE + r'\data\export_llm'
os.makedirs(OUT, exist_ok=True)

con = sqlite3.connect(PIPE)
c = con.cursor()

R13 = [('precio_usd', 'Precio en u$s'), ('per', 'PER'),
       ('max_52w', 'Max 52s'), ('dif_max_52w', 'Dif vs Max 52s'),
       ('min_52w', 'Min 52s'), ('dif_min_52w', 'Dif vs Min 52s'),
       ('deuda_ebitda', 'Deuda/EBITDA'), ('eps_anual', 'EPS anual'),
       ('crecimiento_eps_5y', 'Crec EPS 5a'), ('margen_neto', 'Margen Neto'),
       ('roe_5y', 'ROE 5a'), ('fcf_market_cap', 'FCFonCE'), ('payout', 'Payout')]

CNV_MAP = {'margen_neto': 'CNV_margen_neto', 'roe_5y': 'CNV_roe',
           'deuda_ebitda': 'CNV_deuda_fin_ebitda'}

# --- capas ---
merc = {r[0]: r[1:] for r in c.execute("""SELECT cuit, ticker, precio_ars,
    mep_pareado, mep_pareado_fecha, staleness_dias, mezcla_temporal,
    dif_check_ok FROM mercado_byma""")}
met = {}
for cu, m, v, f, inp in c.execute(
        """SELECT cuit, metrica, valor, flag, inputs FROM metricas"""):
    met.setdefault(cu, {})[m] = (v, f, inp)
cert = {r[0]: r[1:] for r in c.execute(
    """SELECT cuit || '|' || metrica, status, motivos FROM certificacion""")}
val = {r[0]: r[1:] for r in c.execute(
    """SELECT cuit || '|' || check_id, resultado, desvio_pct FROM validacion_mat""")}
ana = {}
for cu, ck, sev in c.execute("SELECT cuit, check_id, severidad FROM anomalias"):
    ana.setdefault(cu, []).append(f'{ck}({sev})')
cnv = {}
for cu, co, pe, v in c.execute(
        """SELECT cuit, ratio, period_end, valor FROM partidas_ratios_cnv
           WHERE tipo='A' AND valor IS NOT NULL"""):
    cnv.setdefault(cu, {}).setdefault(co, []).append((pe, v))
fy_m = {r[0]: r[1] for r in c.execute(
    "SELECT cuit, fy_end_month FROM byma_universo")}
ttm_cov = {}
for cu in c.execute("SELECT DISTINCT cuit FROM ratios_ttm_byma WHERE cobertura_ok=1"):
    ttm_cov[cu[0]] = True

def l1_fy(cuit, concepto):
    """ultimo acumulado FY completo del concepto (L1 normalizado)."""
    fm = fy_m.get(cuit)
    if not fm:
        return None, None
    r = c.execute("""SELECT periodo_hasta, valor FROM partidas_norm WHERE cuit=?
        AND concepto_normalizado=? AND period_type='acumulado'
        AND CAST(substr(periodo_hasta,6,2) AS INTEGER)=?
        ORDER BY periodo_hasta DESC LIMIT 1""", (cuit, concepto, fm)).fetchone()
    return r if r else (None, None)

rows = []
for cu, mr in merc.items():
    tk = mr[0]
    anoms = '; '.join(sorted(set(ana.get(cu, [])))) or ''
    for metrica, etiqueta in R13:
        m = met.get(cu, {}).get(metrica, (None, '', ''))
        valor, flag, inputs = m
        key = cu + '|' + metrica
        st, mot = cert.get(key, ('', ''))
        # L4: check asociado
        chk_map = {'per': 'PER_2PATH', 'margen_neto': 'MARGEN_vs_CNV',
                   'fcf_market_cap': 'FCF_MC_recalc' if False else None}
        chk_id = chk_map.get(metrica) or (
            {'per': 'PER_2PATH', 'margen_neto': 'MARGEN_vs_CNV'}.get(metrica))
        if metrica == 'deuda_ebitda':
            chk_id = 'DEUDA_ARITMETICA'
        elif metrica == 'fcf_market_cap':
            chk_id = 'FCF_ARITMETICA'
        elif metrica == 'roe_5y':
            chk_id = 'ROE5Y_ARITMETICA'
        elif metrica == 'eps_anual':
            chk_id = 'EPS_MATCH_RAW'
        vres, vdes = val.get(key, ('', '')) if chk_id is None else \
            (val.get(cu + '|' + chk_id, ('', '')) or ('', ''))[0:2]
        # L0/L1 segun tipo de ratio
        l0 = l1 = ''
        if metrica in CNV_MAP:
            decls = sorted(cnv.get(cu, {}).get(CNV_MAP[metrica], []))
            if decls:
                pe, v = decls[-1]
                l0, l1 = f'{v} ({pe})', f'declarado CNV'
        elif metrica == 'eps_anual':
            pe, v = l1_fy(cuit := cu, 'EPS_basico')
            if pe:
                l0, l1 = str(v), f'EPS_basico FY {pe}'
        elif metrica == 'payout':
            l0, l1 = 'screener v2', 'cash-basis heredado'
        elif metrica in ('max_52w', 'min_52w'):
            col = 'max52w_ars' if metrica == 'max_52w' else 'min52w_ars'
            pass
        rows.append({
            'cuit': cu, 'ticker': tk, 'ratio': etiqueta, 'clave_interna': metrica,
            'L0_fuente_cruda': l0, 'L1_normalizado': l1,
            'L2_ttm_cobertura_ok': 'si' if ttm_cov.get(cu) else 'no',
            'L3_valor_final': round(valor, 6) if valor is not None else '',
            'L3_inputs': (inputs or '')[:120],
            'L3_flags': flag or '',
            'L4_validacion': vres or 'n/a',
            'L4_desvio_pct': vdes if vdes != '' else '',
            'L5_status': st, 'L5_motivos': mot,
            'anomalias_empresa': anoms,
            'staleness_dias': mr[4] if len(mr) > 4 else '',
        })

cols = list(rows[0].keys())
with open(OUT + r'\traza_13ratios.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

n_emp = len(set(r['cuit'] for r in rows))
with open(OUT + r'\README_TRAZA.md', 'w', encoding='utf-8') as f:
    f.write(f'''# Traza 13 ratios — generada {datetime.now():%Y-%m-%d %H:%M}

Una fila por (empresa x ratio): {len(rows)} filas, {n_emp} empresas.
Fuente: data/byma_pipeline.db (pipeline v3, snapshot certificado).

## Columnas (capas del pipeline)
- L0_fuente_cruda: dato tal como lo declara la fuente (ratio CNV anual, partida EPS, o heredado v2)
- L1_normalizado: tras normalizacion de unidades/tickers (b1)
- L2_ttm_cobertura_ok: si la ventana TTM de la empresa esta completa (b3)
- L3_valor_final / inputs / flags: metrica calculada con formula e inputs registrados (b5)
- L4_validacion / desvio_pct: chequeo matematico independiente (b6). OK/WARN/INFO/FAIL/n/a
- L5_status / motivos: CERTIFIED o NOT_CERTIFIED + causa (b7)
- anomalias_empresa: detectores de b2 que tocan la empresa
- staleness_dias: antiguedad del precio usado

## Como detectar anomalia paso a paso
1. L4=FAIL o L5=NOT_CERTIFIED -> mirar motivo exacto
2. Si L0 existe -> comparar L3 contra L0 (ej: margen propio vs CNV declarado)
3. anomalias_empresa no vacio -> contexto de escala/identidad
4. Los 13 ratios son los de Seguimiento_original.xlsx (mismos nombres)

## Regla del proyecto
Nada se corrige a mano: anomalia -> se marca -> se decide. La certificacion
atestigua consistencia interna y provenance, no veracidad externa.
''')

print(f'OK: {OUT}\\traza_13ratios.csv ({len(rows)} filas, {n_emp} empresas)')
print(f'OK: {OUT}\\README_TRAZA.md')
con.close()
