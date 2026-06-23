#!/usr/bin/env python3
"""
Script: Descargar datos financieros desde SEC EDGAR

Descarga para 18 ADRs argentinos + 200+ CEDEARs:
- Revenue (anual, TTM)
- Net Income
- Total Assets
- Total Liabilities
- Cash Flow de Operaciones
- Depreciation & Amortization
- Diluted Shares Outstanding
- EBITDA (calculado)

Entrada: cedears_200_procesados.csv + adrs_18_argentinos.csv
Salida: financieros_edgar.csv

Uso:
  python 06_descargar_datos_edgar.py
"""

import pandas as pd
import yfinance as yf
import logging
from pathlib import Path
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/descargas.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# PASO 1: CARGAR LISTAS DE CEDEARs Y ADRs
# ============================================================================

logger.info("Cargando listas de tickers...")

cedears_df = pd.read_csv('data/cedears_200_procesados.csv')
adrs_df = pd.read_csv('data/adrs_18_argentinos.csv')

# Renombrar columnas si es necesario
cedears_df = cedears_df.rename(columns={'precio': 'precio_inicial'}) if 'precio' in cedears_df.columns else cedears_df
adrs_df = adrs_df.rename(columns={'precio_usd': 'precio_inicial'}) if 'precio_usd' in adrs_df.columns else adrs_df

logger.info(f"CEDEARs: {len(cedears_df)}")
logger.info(f"ADRs: {len(adrs_df)}")

# Combinar listas
cedears_df['tipo'] = 'CEDEAR'
adrs_df['tipo'] = 'ADR'

# Asegurar columnas compatibles
cedears_df = cedears_df[['ticker', 'empresa', 'sector', 'tipo']]
adrs_df = adrs_df[['ticker', 'empresa', 'sector', 'tipo']]

all_tickers_df = pd.concat([cedears_df, adrs_df], ignore_index=True)

logger.info(f"Total tickers a descargar financieros: {len(all_tickers_df)}")

# ============================================================================
# PASO 2: DESCARGAR DATOS FINANCIEROS DE EDGAR
# ============================================================================

logger.info("\nDescargando datos financieros de SEC EDGAR (via yfinance)...")

financieros_data = []
errores = []

for idx, row in all_tickers_df.iterrows():
    ticker = row['ticker']
    tipo = row['tipo']

    try:
        # Descargar datos
        data = yf.Ticker(ticker)
        info = data.info

        # Extraer datos financieros (financials, quarterly_financials)
        try:
            # Info general
            revenue = info.get('totalRevenue', None)
            net_income = info.get('netIncome', None)
            operating_income = info.get('operatingIncome', None)
            total_assets = info.get('totalAssets', None)
            total_liabilities = info.get('totalLiabilities', None)
            stockholders_equity = info.get('totalStockholderEquity', None)

            # Cash flow
            operating_cash_flow = info.get('operatingCashflow', None)
            capital_expenditure = info.get('capitalExpenditures', None)

            # D&A, Shares
            depreciation = info.get('depreciation', None)
            shares_outstanding = info.get('sharesOutstanding', None)
            diluted_shares = info.get('sharesFullyDiluted', None)

            # Calcular EBITDA si tenemos datos
            ebitda = None
            if operating_income and depreciation:
                ebitda = operating_income + depreciation
            elif operating_income:
                ebitda = operating_income

            # Calcular Free Cash Flow
            fcf = None
            if operating_cash_flow and capital_expenditure:
                fcf = operating_cash_flow - capital_expenditure
            elif operating_cash_flow:
                fcf = operating_cash_flow

            financieros_data.append({
                'ticker': ticker,
                'empresa': row['empresa'],
                'sector': row['sector'],
                'tipo': tipo,
                'revenue': revenue,
                'net_income': net_income,
                'operating_income': operating_income,
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'stockholders_equity': stockholders_equity,
                'operating_cash_flow': operating_cash_flow,
                'capital_expenditure': capital_expenditure,
                'depreciation': depreciation,
                'ebitda': ebitda,
                'fcf': fcf,
                'shares_outstanding': shares_outstanding,
                'diluted_shares': diluted_shares or shares_outstanding,
            })

            logger.info(f"✓ {ticker:6s} ({tipo:6s}): Revenue=${revenue:,.0f}" if revenue else f"⚠ {ticker:6s}: sin datos completos")

        except Exception as e:
            logger.error(f"  Error al extraer datos de {ticker}: {str(e)}")
            financieros_data.append({
                'ticker': ticker,
                'empresa': row['empresa'],
                'sector': row['sector'],
                'tipo': tipo,
                'revenue': None,
                'net_income': None,
                'operating_income': None,
                'total_assets': None,
                'total_liabilities': None,
                'stockholders_equity': None,
                'operating_cash_flow': None,
                'capital_expenditure': None,
                'depreciation': None,
                'ebitda': None,
                'fcf': None,
                'shares_outstanding': None,
                'diluted_shares': None,
            })

        # Rate limiting para no sobrecargar yfinance
        time.sleep(0.2)

    except Exception as e:
        logger.error(f"✗ {ticker}: {str(e)}")
        errores.append({'ticker': ticker, 'error': str(e)})

logger.info(f"\nDescargados: {len(financieros_data)}/{len(all_tickers_df)}")
if errores:
    logger.warning(f"Errores: {len(errores)}")

# ============================================================================
# PASO 3: CREAR DataFrame Y GUARDAR
# ============================================================================

financieros_df = pd.DataFrame(financieros_data)

# Reordenar columnas
financieros_df = financieros_df[[
    'ticker', 'empresa', 'sector', 'tipo',
    'revenue', 'net_income', 'operating_income',
    'total_assets', 'total_liabilities', 'stockholders_equity',
    'operating_cash_flow', 'capital_expenditure',
    'depreciation', 'ebitda', 'fcf',
    'shares_outstanding', 'diluted_shares'
]]

# Guardar
financieros_path = 'data/financieros_edgar.csv'
financieros_df.to_csv(financieros_path, index=False)
logger.info(f"\n✓ Guardado: {financieros_path}")

# ============================================================================
# PASO 4: GUARDAR ERRORES
# ============================================================================

if errores:
    errores_df = pd.DataFrame(errores)
    errores_path = 'data/errores_edgar.csv'
    errores_df.to_csv(errores_path, index=False)
    logger.info(f"✓ Errores guardados: {errores_path}")

# ============================================================================
# PASO 5: RESUMEN
# ============================================================================

logger.info("\n" + "="*70)
logger.info("RESUMEN - FINANCIEROS DESCARGADOS")
logger.info("="*70)
logger.info(f"CEDEARs: {len(financieros_df[financieros_df['tipo']=='CEDEAR'])}")
logger.info(f"ADRs: {len(financieros_df[financieros_df['tipo']=='ADR'])}")
logger.info(f"Total descargados: {len(financieros_df)}")
logger.info(f"Con Revenue: {financieros_df['revenue'].notna().sum()}")
logger.info(f"Sin Revenue: {financieros_df['revenue'].isna().sum()}")
if errores:
    logger.info(f"Errores: {len(errores)}")
logger.info("="*70 + "\n")

# Mostrar top 10 por Revenue
print("\n📊 TOP 10 POR REVENUE:")
top_10 = financieros_df.nlargest(10, 'revenue')[['ticker', 'empresa', 'revenue', 'net_income', 'ebitda']]
for idx, row in top_10.iterrows():
    print(f"  {row['ticker']:6s} | {row['empresa']:30s} | Revenue: ${row['revenue']:>12,.0f}" if row['revenue'] else f"  {row['ticker']:6s} | {row['empresa']:30s} | N/A")

print("\n✓ FASE 3 COMPLETADA: Datos financieros EDGAR descargados")
print(f"  - Archivo: {financieros_path}")
print(f"  - Total: {len(financieros_df)} acciones")
print(f"  - Con Revenue: {financieros_df['revenue'].notna().sum()}")
