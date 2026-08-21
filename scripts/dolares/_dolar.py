# -*- coding: utf-8 -*-
"""Fetchers de los dólares de referencia (CCL, MEP, A3500). Compartido por los dos scripts."""
import statistics, requests, urllib3
urllib3.disable_warnings()

# CCL por arbitraje de ADR: precio local (ARS) × acciones por ADR / precio del ADR (USD).
# Ratios estables y conocidos (1 ADR = N acciones ordinarias).
ADRS = {'GGAL': ('GGAL.BA', 'GGAL', 10),
        'YPFD': ('YPFD.BA', 'YPF', 1),
        'PAMP': ('PAMP.BA', 'PAM', 25)}

def ccl_yahoo():
    """(mediana, [(adr, ccl)]) del CCL calculado con cada par ADR de Yahoo Finance."""
    import yfinance as yf
    vals = []
    for name, (local, adr, ratio) in ADRS.items():
        try:
            pl = yf.Ticker(local).history(period='5d')['Close']
            pa = yf.Ticker(adr).history(period='5d')['Close']
            if len(pl) and len(pa):
                vals.append((name, float(pl.iloc[-1]) * ratio / float(pa.iloc[-1])))
        except Exception:
            pass
    med = statistics.median([v for _, v in vals]) if vals else None
    return med, vals

def dolarapi():
    """{casa: {compra, venta, ...}} de dolarapi.com (CCL, MEP/bolsa, mayorista≈A3500, oficial, blue)."""
    r = requests.get('https://dolarapi.com/v1/dolares', timeout=15, verify=False,
                     headers={'User-Agent': 'Mozilla/5.0'})
    return {d['casa']: d for d in r.json()}

def criptoya():
    """MEP por bono (AL30, GD30) desde criptoya.com — 2ª fuente independiente del MEP."""
    try:
        r = requests.get('https://criptoya.com/api/dolar', timeout=15, verify=False,
                         headers={'User-Agent': 'Mozilla/5.0'})
        return r.json()
    except Exception:
        return {}

def tres_dolares():
    """Devuelve los tres de referencia: {tipo: {valor, fuente, cruce, ...}}. MEP es el de referencia."""
    api = dolarapi()
    cy = criptoya()
    ccl_med, ccl_detalle = ccl_yahoo()
    out = {}
    # MEP (REFERENCIA): primario = criptoya (bono AL30), cruce = dolarapi (bolsa). Dos fuentes.
    mep_al30 = (((cy.get('mep') or {}).get('al30') or {}).get('24hs') or {}).get('price')
    mep_api = (api.get('bolsa') or {}).get('venta')
    out['mep'] = {'valor': mep_al30 or mep_api, 'fuente': 'criptoya-al30', 'cruce': mep_api,
                  'detalle': [('AL30', mep_al30), ('dolarapi', mep_api)]}
    # CCL: primario = Yahoo (arbitraje ADR), cruce = dolarapi
    ccl_api = (api.get('contadoconliqui') or {}).get('venta')
    out['ccl'] = {'valor': ccl_med, 'fuente': 'yahoo-adr', 'cruce': ccl_api, 'detalle': ccl_detalle}
    # A3500: mayorista (≈ publicación BCRA)
    may = api.get('mayorista') or {}
    out['a3500'] = {'valor': may.get('venta'), 'fuente': 'dolarapi-mayorista', 'cruce': None, 'detalle': []}
    return out
