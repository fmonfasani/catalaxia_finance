"""E5b - b6_validacion_mat: valida aritmetica de b5 contra inputs certificados
de b3/b4 y contra ratios declarados por las propias empresas (CNV) como
referencia externa. NO re-deriva TTM (eso ya esta certificado en b3)."""
import sqlite3
from datetime import datetime

BASE = r'D:\Software Development\Porfolio\catalaxia-cedears-prod'
PIPE = BASE + r'\data\byma_pipeline.db'
con = sqlite3.connect(PIPE)
c = con.cursor()
now = datetime.now().isoformat()

c.execute("DROP TABLE IF EXISTS validacion_mat")
c.execute("""CREATE TABLE validacion_mat (
    cuit TEXT, ticker TEXT, check_id TEXT, resultado TEXT,
    nuestro REAL, referencia REAL, desvio_pct REAL,
    detalle TEXT, checked_at TEXT, PRIMARY KEY(cuit, check_id))""")

def log(cuit, tk, chk, res, nu=None, ref=None, det=''):
    dev = round((nu - ref) / abs(ref) * 100, 4) if nu is not None and ref else None
    c.execute('INSERT OR REPLACE INTO validacion_mat VALUES (?,?,?,?,?,?,?,?,?)',
              (cuit, tk, chk, res, nu, ref, dev, det, now))

ident_bad = {r[0] for r in c.execute(
    """SELECT DISTINCT cuit FROM anomalias
       WHERE check_id='IDENTIDAD' AND severidad='ALTA'""")}

# inputs certificados por capa anterior
ttm = {}
for cu, co, v in c.execute(
        """SELECT cuit, concepto, CAST(valor_ttm AS REAL) FROM ratios_ttm_byma
           WHERE cobertura_ok=1 AND valor_ttm IS NOT NULL"""):
    ttm.setdefault(cu, {})[co] = v
bal = {r[0]: r[1:] for r in c.execute(
    """SELECT cuit, CAST(equity_prom AS REAL), CAST(deuda_total AS REAL)
       FROM balances_ttm_byma""")}
merc = {r[0]: r[1:] for r in c.execute(
    """SELECT cuit, ticker, CAST(precio_ars AS REAL),
       CAST(market_cap_usd AS REAL) FROM mercado_byma
       WHERE precio_ars IS NOT NULL AND market_cap_usd IS NOT NULL""")}
cnv = {}
for cu, co, pe, v in c.execute(
    """SELECT cuit, ratio, period_end, CAST(valor AS REAL) FROM partidas_ratios_cnv
       WHERE valor IS NOT NULL AND ratio='CNV_margen_neto' AND tipo='A'"""):
    cnv.setdefault(cu, {}).setdefault(co, []).append((pe, v))
met = {}
for cu, m, v in c.execute("SELECT cuit, metrica, CAST(valor AS REAL) FROM metricas"):
    met.setdefault(cu, {})[m] = v

cnt = {'OK': 0, 'WARN': 0, 'INFO': 0, 'FAIL': 0}

def close(a, b, tol_rel):
    return abs(a - b) <= max(abs(b) * tol_rel, 1e-9)

for cuit, tk in sorted(merc.items()):
    tk = tk[0]
    precio_ars, mcap_ars = merc[cuit][1], merc[cuit][2]
    M = met.get(cuit, {})
    warn = 'IDENTIDAD_ALTA' if cuit in ident_bad else ''

    def emit(chk, ok, nu=None, ref=None, det='', info_only=False):
        if not ok and info_only:
            cnt['INFO'] += 1
            log(cuit, tk, chk, 'INFO', nu, ref, det)
        elif not ok:
            cnt['FAIL'] += 1
            log(cuit, tk, chk, 'FAIL', nu, ref, det)
        else:
            res = 'WARN' if warn else 'OK'
            cnt[res] += 1
            log(cuit, tk, chk, res, nu, ref,
                det + ('; ' + warn if warn else ''))

    # CHK_PER_2PATH: mcap/NI_ttm vs precio_ars/EPS_fy (ventanas pueden diferir)
    ni = ttm.get(cuit, {}).get('NetIncome')
    eps = M.get('eps_anual')
    if mcap_ars and ni and ni > 0 and eps and eps > 0 and precio_ars:
        p1, p2 = mcap_ars / ni, precio_ars / eps
        mismo_anio = False
        w = c.execute("""SELECT ttm_hasta FROM ratios_ttm_byma
            WHERE cuit=? AND concepto='NetIncome'""", (cuit,)).fetchone()
        e = c.execute("""SELECT periodo FROM metricas
            WHERE cuit=? AND metrica='eps_anual'""", (cuit,)).fetchone()
        if w and e and w[0][:4] == e[0][:4]:
            mismo_anio = True
        ok = close(p1, p2, 0.10)
        emit('PER_2PATH', ok and mismo_anio, p1, p2,
             'PER_TTM vs PER_FY_anterior' if not mismo_anio else
             'misma ventana, desvio >10%', info_only=not mismo_anio)

    # CHK_MARGEN_vs_CNV: margen TTM vs ultimo margen anual declarado en CNV
    mg = M.get('margen_neto')
    decls = cnv.get(cuit, {}).get('CNV_margen_neto', [])
    if mg is not None and decls:
        ref = max(decls)[1] / 100 if abs(max(decls)[1]) > 1 else max(decls)[1]
        emit('MARGEN_vs_CNV', close(mg, ref, 0.35), mg, ref,
             f'declarado={max(decls)[0]} (TTM vs FY anual)', info_only=True)

    # CHK_FCF_ARIT: fcf_mcap * mcap == CFO_ttm + CFI_ttm (aritmetica b5)
    fcfmc = M.get('fcf_market_cap')
    cfo = ttm.get(cuit, {}).get('CF_Operativo')
    cfi = ttm.get(cuit, {}).get('CF_Inversion')
    if fcfmc is not None and mcap_ars and cfo is not None and cfi is not None:
        emit('FCF_ARITMETICA', close(fcfmc * mcap_ars, cfo + cfi, 0.001),
             fcfmc * mcap_ars, cfo + cfi)

    # CHK_DEUDA_ARIT: deuda_ebitda * EBITDA_ttm == deuda_total (b3)
    deb = M.get('deuda_ebitda')
    eb = ttm.get(cuit, {}).get('EBITDA')
    dtot = bal.get(cuit, (None, None))[1]
    if deb is not None and eb and dtot is not None:
        emit('DEUDA_ARITMETICA', close(deb * eb, dtot, 0.001), deb * eb, dtot)

    # CHK_EPS_RAW: eps_anual == valor crudo de la partida en su cierre
    eps = M.get('eps_anual')
    if eps is not None:
        pe = c.execute("""SELECT periodo FROM metricas
            WHERE cuit=? AND metrica='eps_anual'""", (cuit,)).fetchone()[0]
        raw = c.execute("""SELECT valor FROM partidas_norm WHERE cuit=?
            AND concepto_normalizado='EPS_basico' AND period_type='acumulado'
            AND periodo_hasta=?""", (cuit, pe)).fetchone()
        emit('EPS_MATCH_RAW', bool(raw) and close(eps, raw[0], 1e-6),
             eps, raw[0] if raw else None, f'cierre={pe}')

    # CHK_ROE5Y_ARIT: re-promedia los ROES anuales guardados en inputs
    r5 = M.get('roe_5y')
    if r5 is not None:
        ins = c.execute("""SELECT inputs FROM metricas
            WHERE cuit=? AND metrica='roe_5y'""", (cuit,)).fetchone()[0]
        try:
            vals = [float(x.split(':')[1]) for x in ins.split(';')]
            prom = sum(vals) / len(vals)
            emit('ROE5Y_ARITMETICA', close(r5, prom, 0.01), r5, prom,
                 'inputs redondeados a 4 dec')
        except Exception as ex:
            log(cuit, tk, 'ROE5Y_ARITMETICA', 'WARN', detail=f'unparseable: {ex}')

print(f'RESUMEN b6_validacion_mat: ' +
      ' '.join(f'{k}={v}' for k, v in cnt.items()))
for row in c.execute("""SELECT check_id, resultado, COUNT(*) FROM validacion_mat
    GROUP BY check_id, resultado ORDER BY check_id, resultado"""):
    print(' ', row)
print('-- FAILs detalle:')
for row in c.execute("""SELECT ticker, check_id, nuestro, referencia, desvio_pct
    FROM validacion_mat WHERE resultado='FAIL' ORDER BY check_id LIMIT 30"""):
    print(' ', row)
con.commit()
con.close()
