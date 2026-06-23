#!/usr/bin/env python3
"""
Script: Descargar precios actuales desde yfinance

Descarga:
- Precio actual
- Máximo 52 semanas
- Mínimo 52 semanas
- Volumen
- Market Cap
- Dividend Yield

Entrada: cedears_200_procesados.csv + adrs_18_argentinos.csv
Salida: precios_completos.csv

Uso:
  python 05_descargar_precios_yfinance.py
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

logger.info(f"Total tickers a descargar: {len(all_tickers_df)}")

# ============================================================================
# PASO 2: DESCARGAR DATOS DE YFINANCE
# ============================================================================

logger.info("\nDescargando datos de yfinance...")

precios_data = []
errores = []

for idx, row in all_tickers_df.iterrows():
    ticker = row['ticker']
    tipo = row['tipo']

    try:
        # Descargar datos
        data = yf.Ticker(ticker)
        info = data.info

        # Extraer datos
        precio_actual = info.get('currentPrice', None)
        max_52w = info.get('fiftyTwoWeekHigh', None)
        min_52w = info.get('fiftyTwoWeekLow', None)
        volumen = info.get('volume', None)
        market_cap = info.get('marketCap', None)
        dividend_yield = info.get('dividendYield', None)

        # Calcular cambios
        if max_52w and precio_actual:
            dif_max = ((precio_actual / max_52w) - 1) * 100
        else:
            dif_max = None

        if min_52w and precio_actual:
            dif_min = ((precio_actual / min_52w) - 1) * 100
        else:
            dif_min = None

        precios_data.append({
            'ticker': ticker,
            'empresa': row['empresa'],
            'sector': row['sector'],
            'tipo': tipo,
            'precio': precio_actual,
            'precio_52w_max': max_52w,
            'precio_52w_min': min_52w,
            'dif_max_52w': dif_max,
            'dif_min_52w': dif_min,
            'volumen': volumen,
            'market_cap': market_cap,
            'dividend_yield': dividend_yield,
        })

        logger.info(f"✓ {ticker:6s} ({tipo:6s}): ${precio_actual:.2f}" if precio_actual else f"⚠ {ticker:6s}: sin precio")

        # Rate limiting para no sobrecargar yfinance
        time.sleep(0.1)

    except Exception as e:
        logger.error(f"✗ {ticker}: {str(e)}")
        errores.append({'ticker': ticker, 'error': str(e)})

logger.info(f"\nDescargados: {len(precios_data)}/{len(all_tickers_df)}")
if errores:
    logger.warning(f"Errores: {len(errores)}")

# ============================================================================
# PASO 3: CREAR DataFrame Y GUARDAR
# ============================================================================

precios_df = pd.DataFrame(precios_data)

# Llenar columnas faltantes si es necesario
for col in ['precio', 'precio_52w_max', 'precio_52w_min', 'volumen', 'market_cap', 'dividend_yield']:
    if col not in precios_df.columns:
        precios_df[col] = None

# Reordenar columnas
precios_df = precios_df[[
    'ticker', 'empresa', 'sector', 'tipo',
    'precio', 'precio_52w_max', 'precio_52w_min',
    'dif_max_52w', 'dif_min_52w',
    'volumen', 'market_cap', 'dividend_yield'
]]

# Guardar
precios_path = 'data/precios_completos.csv'
precios_df.to_csv(precios_path, index=False)
logger.info(f"\n✓ Guardado: {precios_path}")

# ============================================================================
# PASO 4: GUARDAR ERRORES
# ============================================================================

if errores:
    errores_df = pd.DataFrame(errores)
    errores_path = 'data/errores_descargas.csv'
    errores_df.to_csv(errores_path, index=False)
    logger.info(f"✓ Errores guardados: {errores_path}")

# ============================================================================
# PASO 5: RESUMEN
# ============================================================================

logger.info("\n" + "="*70)
logger.info("RESUMEN - DESCARGAS COMPLETADAS")
logger.info("="*70)
logger.info(f"CEDEARs: {len(precios_df[precios_df['tipo']=='CEDEAR'])}")
logger.info(f"ADRs: {len(precios_df[precios_df['tipo']=='ADR'])}")
logger.info(f"Total descargados: {len(precios_df)}")
logger.info(f"Con precios: {precios_df['precio'].notna().sum()}")
logger.info(f"Sin precios: {precios_df['precio'].isna().sum()}")
if errores:
    logger.info(f"Errores: {len(errores)}")
logger.info("="*70 + "\n")

# Mostrar top 10
print("\n📊 TOP 10 POR MARKET CAP:")
print(precios_df.nlargest(10, 'market_cap')[['ticker', 'empresa', 'precio', 'market_cap', 'dividend_yield']])

print("\n✓ FASE 2 COMPLETADA: Precios descargados")
print(f"  - Archivo: {precios_path}")
print(f"  - Total: {len(precios_df)} acciones")
print(f"  - Con precios: {precios_df['precio'].notna().sum()}")
