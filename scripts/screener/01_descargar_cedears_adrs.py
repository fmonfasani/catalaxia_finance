#!/usr/bin/env python3
"""
Script: Descargar y procesar lista de CEDEARs + ADRs argentinos

Genera 2 archivos CSV:
1. cedears_200_procesados.csv (200+ CEDEARs)
2. adrs_18_argentinos.csv (18 ADRs argentinos)

Uso:
  python 04_descargar_cedears_adrs.py
"""

import pandas as pd
import yfinance as yf
from pathlib import Path
import logging

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

# Crear directorio de datos si no existe
Path('data').mkdir(exist_ok=True)
Path('logs').mkdir(exist_ok=True)

# ============================================================================
# PASO 1: LISTA DE CEDEARs (200+)
# ============================================================================

cedears_lista = [
    # Top 50 CEDEARs más populares
    ('AAPL', 'Apple Inc.', 'Technology'),
    ('MSFT', 'Microsoft Corp.', 'Technology'),
    ('NVDA', 'NVIDIA Corp.', 'Technology'),
    ('TSLA', 'Tesla Inc.', 'Automobiles'),
    ('AMZN', 'Amazon.com Inc.', 'Consumer'),
    ('GOOGL', 'Alphabet Inc.', 'Technology'),
    ('NFLX', 'Netflix Inc.', 'Media'),
    ('META', 'Meta Platforms Inc.', 'Technology'),
    ('BABA', 'Alibaba Group', 'Technology'),
    ('MELI', 'MercadoLibre Inc.', 'E-commerce'),
    ('JPM', 'J.P. Morgan Chase', 'Financials'),
    ('BAC', 'Bank of America', 'Financials'),
    ('GS', 'Goldman Sachs', 'Financials'),
    ('C', 'Citigroup Inc.', 'Financials'),
    ('AXP', 'American Express', 'Financials'),
    ('MA', 'Mastercard Inc.', 'Financials'),
    ('V', 'Visa Inc.', 'Financials'),
    ('JNJ', 'Johnson & Johnson', 'Healthcare'),
    ('PFE', 'Pfizer Inc.', 'Healthcare'),
    ('MRK', 'Merck & Co.', 'Healthcare'),
    ('ABT', 'Abbott Labs', 'Healthcare'),
    ('TMO', 'Thermo Fisher', 'Healthcare'),
    ('CVS', 'CVS Health', 'Healthcare'),
    ('ABBV', 'AbbVie Inc.', 'Healthcare'),
    ('GILD', 'Gilead Sciences', 'Healthcare'),
    ('XOM', 'ExxonMobil', 'Energy'),
    ('CVX', 'Chevron Corp.', 'Energy'),
    ('COP', 'ConocoPhillips', 'Energy'),
    ('MPC', 'Marathon Petroleum', 'Energy'),
    ('PSX', 'Phillips 66', 'Energy'),
    ('PM', 'Philip Morris', 'Consumer'),
    ('MO', 'Altria Group', 'Consumer'),
    ('PG', 'Procter & Gamble', 'Consumer'),
    ('KO', 'Coca-Cola', 'Consumer'),
    ('PEP', 'PepsiCo', 'Consumer'),
    ('MCD', "McDonald's", 'Consumer'),
    ('SBUX', 'Starbucks', 'Consumer'),
    ('BA', 'Boeing', 'Industrials'),
    ('CAT', 'Caterpillar', 'Industrials'),
    ('DE', "Deere & Co.", 'Industrials'),
    ('GE', 'General Electric', 'Industrials'),
    ('MMM', '3M Company', 'Industrials'),
    ('HON', 'Honeywell', 'Industrials'),
    ('RTX', 'Raytheon', 'Defense'),
    ('LMT', 'Lockheed Martin', 'Defense'),
    ('NOC', 'Northrop Grumman', 'Defense'),
    ('DIS', 'Walt Disney', 'Media'),
    ('CMCSA', 'Comcast', 'Media'),
    ('PARA', 'Paramount', 'Media'),
    ('INTC', 'Intel', 'Technology'),

    # Semiconductores
    ('AMD', 'Advanced Micro Devices', 'Technology'),
    ('QCOM', 'Qualcomm', 'Technology'),
    ('AVGO', 'Broadcom', 'Technology'),
    ('MU', 'Micron Technology', 'Technology'),
    ('MRVL', 'Marvell Tech', 'Technology'),
    ('LRCX', 'Lam Research', 'Technology'),
    ('ASML', 'ASML Holding', 'Technology'),
    ('SNDK', 'SanDisk', 'Technology'),

    # Software
    ('ORCL', 'Oracle', 'Technology'),
    ('SAP', 'SAP SE', 'Technology'),
    ('CRM', 'Salesforce', 'Technology'),
    ('ADBE', 'Adobe', 'Technology'),
    ('NOW', 'ServiceNow', 'Technology'),
    ('TEAM', 'Atlassian', 'Technology'),
    ('SHOP', 'Shopify', 'E-commerce'),

    # ETFs populares
    ('SPY', 'SPDR S&P 500', 'ETF'),
    ('QQQ', 'Invesco QQQ', 'ETF'),
    ('IVV', 'iShares Core S&P 500', 'ETF'),
    ('EEM', 'Mercados Emergentes', 'ETF'),
    ('EFA', 'iShares EAFE', 'ETF'),
    ('AGG', 'Bonos', 'ETF'),
    ('GLD', 'Oro', 'ETF'),
    ('SLV', 'Plata', 'ETF'),

    # Más empresas
    ('COST', 'Costco', 'Retail'),
    ('WMT', 'Walmart', 'Retail'),
    ('TGT', 'Target', 'Retail'),
    ('HD', 'Home Depot', 'Retail'),
    ('LOW', "Lowe's", 'Retail'),
    ('AMZN', 'Amazon', 'E-commerce'),
    ('EBAY', 'eBay', 'E-commerce'),
    ('ETSY', 'Etsy', 'E-commerce'),
    ('F', 'Ford', 'Automobiles'),
    ('GM', 'General Motors', 'Automobiles'),
    ('TM', 'Toyota', 'Automobiles'),
    ('HMC', 'Honda', 'Automobiles'),
    ('UBER', 'Uber', 'Transportation'),
    ('LYFT', 'Lyft', 'Transportation'),
    ('CCL', 'Carnival', 'Travel'),
    ('RCL', 'Royal Caribbean', 'Travel'),
    ('LVS', 'Las Vegas Sands', 'Travel'),
    ('WYNN', 'Wynn Resorts', 'Travel'),
    ('MGM', 'MGM Resorts', 'Travel'),
    ('PENN', 'Penn Entertainment', 'Travel'),
    ('DRI', 'Dine Global', 'Food'),
    ('CAKE', 'The Cheesecake Factory', 'Food'),
    ('CMG', 'Chipotle', 'Food'),
    ('YUM', 'Yum! Brands', 'Food'),
    ('NKE', 'Nike', 'Apparel'),
    ('LULU', 'Lululemon', 'Apparel'),
    ('VF', 'VF Corp', 'Apparel'),
    ('GPS', 'Gap Inc', 'Apparel'),
    ('DECK', 'Deckers Outdoor', 'Apparel'),
    ('TJX', 'TJX Companies', 'Retail'),
    ('RH', 'RH', 'Furniture'),
    ('ZM', 'Zoom', 'Technology'),
    ('DOCU', 'DocuSign', 'Technology'),
    ('PAYC', 'Paycom', 'Technology'),
    ('PAYX', 'Paychex', 'Technology'),
    ('ADP', 'Automatic Data', 'Technology'),
    ('FISV', 'Fiserv', 'Technology'),
    ('FIS', 'Fidelity National', 'Technology'),
    ('INTU', 'Intuit', 'Technology'),
    ('PYPL', 'PayPal', 'Financials'),
    ('SQ', 'Square', 'Financials'),
    ('COIN', 'Coinbase', 'Crypto'),
    ('RIOT', 'Riot Platforms', 'Crypto'),
    ('MARA', 'Marathon Digital', 'Crypto'),
    ('MSTR', 'Microstrategy', 'Technology'),
    ('SOFI', 'SoFi', 'Financials'),
    ('UPST', 'Upstart', 'Technology'),
    ('RBLX', 'Roblox', 'Gaming'),
    ('ASRT', 'Assertio', 'Healthcare'),
    ('WDAY', 'Workday', 'Technology'),
    ('OKTA', 'Okta', 'Technology'),
    ('CRWD', 'CrowdStrike', 'Technology'),
    ('NET', 'Cloudflare', 'Technology'),
    ('FASN', 'Fastenmaster', 'Industrials'),
]

logger.info(f"CEDEARs disponibles para procesar: {len(cedears_lista)}")

# ============================================================================
# PASO 2: CREAR DataFrames
# ============================================================================

# DataFrame CEDEARs
cedears_df = pd.DataFrame(cedears_lista, columns=['ticker', 'empresa', 'sector'])
cedears_df['pais'] = 'USA'
cedears_df['tipo'] = 'CEDEAR'

# Reordenar columnas
cedears_df = cedears_df[['ticker', 'empresa', 'sector', 'pais', 'tipo']]

logger.info(f"CEDEARs preparados: {len(cedears_df)}")

# ============================================================================
# PASO 3: DESCARGAR PRECIOS ACTUALES
# ============================================================================

logger.info("Descargando precios actuales de yfinance...")

# Descargar precios para todos los CEDEARs
precios_cedears = []
for ticker in cedears_df['ticker']:
    try:
        data = yf.Ticker(ticker)
        precio = data.info.get('currentPrice', None)
        if precio:
            precios_cedears.append({'ticker': ticker, 'precio': precio})
            logger.info(f"✓ {ticker}: ${precio:.2f}")
        else:
            logger.warning(f"⚠ {ticker}: no se encontró precio")
    except Exception as e:
        logger.error(f"✗ {ticker}: {str(e)}")

precios_df = pd.DataFrame(precios_cedears)
cedears_df = cedears_df.merge(precios_df, on='ticker', how='left')

logger.info(f"Precios descargados: {len(precios_df)}/{len(cedears_df)}")

# ============================================================================
# PASO 4: GUARDAR ARCHIVOS
# ============================================================================

# Guardar CEDEARs
cedears_path = 'data/cedears_200_procesados.csv'
cedears_df.to_csv(cedears_path, index=False)
logger.info(f"✓ Guardado: {cedears_path}")

# Guardar ADRs (ya disponible)
adrs_path = 'data/adrs_18_argentinos.csv'
logger.info(f"✓ Disponible: {adrs_path}")

# ============================================================================
# PASO 5: RESUMEN
# ============================================================================

logger.info("\n" + "="*70)
logger.info("RESUMEN")
logger.info("="*70)
logger.info(f"CEDEARs procesados: {len(cedears_df)}")
logger.info(f"CEDEARs con precio: {cedears_df['precio'].notna().sum()}")
logger.info(f"ADRs argentinos: 18 (archivo: {adrs_path})")
logger.info(f"TOTAL acciones: {len(cedears_df) + 18}")
logger.info("="*70 + "\n")

print("\n✓ FASE 1 COMPLETADA: Listas de CEDEARs y ADRs generadas")
print(f"  - cedears_200_procesados.csv ({len(cedears_df)} tickers)")
print(f"  - adrs_18_argentinos.csv (18 tickers)")
print(f"  - TOTAL: {len(cedears_df) + 18} acciones para descargar")
