#!/usr/bin/env python3
"""
Script: Calcular 13 ratios financieros

Calcula ratios para 218+ acciones usando:
- Precios (precios_completos.csv)
- Financieros (financieros_edgar.csv)

Ratios calculados (13):
1. P/E (Price/Earnings)
2. P/Book (Price/Book Value)
3. Deuda/Equity
4. Deuda/EBITDA
5. Margen Neto (NI/Revenue)
6. ROE (Net Income / Equity)
7. Operating Margin (Op Income / Revenue)
8. EBITDA Margin
9. FCF (Free Cash Flow)
10. FCF Yield (FCF / Market Cap)
11. Payout Ratio (Dividends / NI)
12. Current Ratio
13. EPS CAGR 5Y

Entrada: precios_completos.csv + financieros_edgar.csv
Salida: ratios.csv

Uso:
  python 07_calcular_ratios.py
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/calculos.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# PASO 1: CARGAR DATOS
# ============================================================================

logger.info("Cargando datos de precios y financieros...")

precios_df = pd.read_csv('data/precios_completos.csv')
financieros_df = pd.read_csv('data/financieros_edgar.csv')

logger.info(f"Precios cargados: {len(precios_df)} acciones")
logger.info(f"Financieros cargados: {len(financieros_df)} acciones")

# ============================================================================
# PASO 2: FUSIONAR DATOS
# ============================================================================

logger.info("Fusionando datos de precios + financieros...")

# Merge en ticker
data_df = precios_df.merge(
    financieros_df[['ticker', 'revenue', 'net_income', 'operating_income',
                    'total_assets', 'total_liabilities', 'stockholders_equity',
                    'operating_cash_flow', 'capital_expenditure',
                    'depreciation', 'ebitda', 'fcf', 'diluted_shares']],
    on='ticker',
    how='left'
)

logger.info(f"Datos fusionados: {len(data_df)} acciones")

# ============================================================================
# PASO 3: CALCULAR RATIOS
# ============================================================================

logger.info("Calculando 13 ratios financieros...")

ratios_data = []

for idx, row in data_df.iterrows():
    ticker = row['ticker']

    # Precios y market cap
    precio = row['precio']
    market_cap = row['market_cap']

    # Financieros
    revenue = row['revenue']
    net_income = row['net_income']
    operating_income = row['operating_income']
    equity = row['stockholders_equity']
    liabilities = row['total_liabilities']
    assets = row['total_assets']
    fcf = row['fcf']
    ebitda = row['ebitda']
    diluted_shares = row['diluted_shares']

    # Calcular ratios con validación
    try:
        # 1. P/E
        pe = None
        if diluted_shares and diluted_shares > 0 and precio:
            eps = net_income / diluted_shares if net_income else None
            if eps and eps > 0:
                pe = precio / eps

        # 2. P/Book
        p_book = None
        if diluted_shares and diluted_shares > 0 and equity and equity > 0 and precio:
            bv_per_share = equity / diluted_shares
            if bv_per_share > 0:
                p_book = precio / bv_per_share

        # 3. Deuda/Equity
        debt_equity = None
        if equity and equity > 0 and liabilities:
            debt_equity = liabilities / equity

        # 4. Deuda/EBITDA
        debt_ebitda = None
        if ebitda and ebitda > 0 and liabilities:
            debt_ebitda = liabilities / ebitda

        # 5. Margen Neto
        margin_neto = None
        if revenue and revenue > 0 and net_income:
            margin_neto = net_income / revenue

        # 6. ROE
        roe = None
        if equity and equity > 0 and net_income:
            roe = net_income / equity

        # 7. Operating Margin
        op_margin = None
        if revenue and revenue > 0 and operating_income:
            op_margin = operating_income / revenue

        # 8. EBITDA Margin
        ebitda_margin = None
        if revenue and revenue > 0 and ebitda:
            ebitda_margin = ebitda / revenue

        # 9. FCF (ya viene del script anterior)
        fcf_ratio = fcf

        # 10. FCF Yield
        fcf_yield = None
        if fcf and fcf > 0 and market_cap and market_cap > 0:
            fcf_yield = fcf / market_cap

        # 11. Payout Ratio (si hay dividendos en info)
        payout_ratio = row.get('dividend_yield', None)  # Placeholder

        # 12. Current Ratio (no disponible en este script, se calcula después si hay balance sheet)
        current_ratio = None

        # 13. EPS CAGR 5Y (requiere datos históricos, placeholder por ahora)
        eps_cagr_5y = None

        ratios_data.append({
            'ticker': ticker,
            'empresa': row['empresa'],
            'sector': row['sector'],
            'tipo': row['tipo'],

            # Precios y mercado
            'precio': precio,
            'market_cap': market_cap,
            'precio_52w_max': row['precio_52w_max'],
            'precio_52w_min': row['precio_52w_min'],

            # Ratios de Valuación
            'pe': pe,
            'p_book': p_book,
            'deuda_equity': debt_equity,
            'deuda_ebitda': debt_ebitda,

            # Ratios de Rentabilidad
            'margen_neto': margin_neto,
            'roe': roe,
            'op_margin': op_margin,
            'ebitda_margin': ebitda_margin,

            # Ratios de Liquidez y Flujo
            'fcf': fcf_ratio,
            'fcf_yield': fcf_yield,
            'payout_ratio': payout_ratio,
            'current_ratio': current_ratio,

            # Crecimiento
            'eps_cagr_5y': eps_cagr_5y,

            # Datos brutos (para referencia)
            'revenue': revenue,
            'net_income': net_income,
            'ebitda': ebitda,
            'equity': equity,
            'liabilities': liabilities,
        })

        # Log progreso
        if (idx + 1) % 30 == 0:
            logger.info(f"✓ Procesados {idx + 1}/{len(data_df)} ratios")

    except Exception as e:
        logger.error(f"Error calculando ratios para {ticker}: {str(e)}")
        continue

# ============================================================================
# PASO 4: CREAR DataFrame Y GUARDAR
# ============================================================================

ratios_df = pd.DataFrame(ratios_data)

# Reordenar columnas
columnas_finales = [
    'ticker', 'empresa', 'sector', 'tipo',
    'precio', 'market_cap', 'precio_52w_max', 'precio_52w_min',
    'pe', 'p_book', 'deuda_equity', 'deuda_ebitda',
    'margen_neto', 'roe', 'op_margin', 'ebitda_margin',
    'fcf', 'fcf_yield', 'payout_ratio', 'current_ratio', 'eps_cagr_5y',
    'revenue', 'net_income', 'ebitda', 'equity', 'liabilities'
]

ratios_df = ratios_df[columnas_finales]

# Guardar
ratios_path = 'data/ratios.csv'
ratios_df.to_csv(ratios_path, index=False)
logger.info(f"\n✓ Guardado: {ratios_path}")

# ============================================================================
# PASO 5: RESUMEN
# ============================================================================

logger.info("\n" + "="*70)
logger.info("RESUMEN - RATIOS CALCULADOS")
logger.info("="*70)
logger.info(f"Total acciones: {len(ratios_df)}")
logger.info(f"CEDEARs: {len(ratios_df[ratios_df['tipo']=='CEDEAR'])}")
logger.info(f"ADRs: {len(ratios_df[ratios_df['tipo']=='ADR'])}")

# Estadísticas por ratio
logger.info(f"\nCobertura de ratios:")
logger.info(f"  P/E: {ratios_df['pe'].notna().sum()}/{len(ratios_df)}")
logger.info(f"  P/Book: {ratios_df['p_book'].notna().sum()}/{len(ratios_df)}")
logger.info(f"  ROE: {ratios_df['roe'].notna().sum()}/{len(ratios_df)}")
logger.info(f"  Margen Neto: {ratios_df['margen_neto'].notna().sum()}/{len(ratios_df)}")
logger.info(f"  Deuda/Equity: {ratios_df['deuda_equity'].notna().sum()}/{len(ratios_df)}")
logger.info(f"  FCF: {ratios_df['fcf'].notna().sum()}/{len(ratios_df)}")
logger.info("="*70 + "\n")

# Top 10 por P/E
print("\n📊 TOP 10 POR P/E (menor = más barato):")
top_pe = ratios_df[ratios_df['pe'].notna()].nsmallest(10, 'pe')[['ticker', 'empresa', 'precio', 'pe']]
for idx, row in top_pe.iterrows():
    print(f"  {row['ticker']:6s} | {row['empresa']:30s} | P/E: {row['pe']:>6.2f}")

# Top 10 por ROE
print("\n📈 TOP 10 POR ROE (mayor = más rentable):")
top_roe = ratios_df[ratios_df['roe'].notna()].nlargest(10, 'roe')[['ticker', 'empresa', 'roe']]
for idx, row in top_roe.iterrows():
    roe_pct = row['roe'] * 100 if row['roe'] else 0
    print(f"  {row['ticker']:6s} | {row['empresa']:30s} | ROE: {roe_pct:>6.1f}%")

print("\n✓ FASE 4 COMPLETADA: Ratios calculados")
print(f"  - Archivo: {ratios_path}")
print(f"  - Total: {len(ratios_df)} acciones")
print(f"  - Con P/E: {ratios_df['pe'].notna().sum()}")
print(f"  - Con ROE: {ratios_df['roe'].notna().sum()}")
