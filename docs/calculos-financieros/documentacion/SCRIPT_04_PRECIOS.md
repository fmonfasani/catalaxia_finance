# Script 04 — Descargar Precios desde yfinance

## 📋 Resumen

- **Qué hace:** Descarga precio actual, máximo/mínimo de 52 semanas, market cap y shares de yfinance.
- **Entrada:** `cedears_con_cik.json` (295 tickers SEC únicos)
- **Salida:** `precios.json` + `precios_errores.json`
- **Duración:** ~60 segundos (295 tickers × 0.2s)
- **Responsable:** Backend A (Valentino)

## 📥 Entrada

**Archivo:** `cedears_con_cik.json`

```json
{
  "cedears": [
    {
      "byma_ticker": "AAPL",
      "ticker_sec": "AAPL",
      "nombre_sec": "Apple Inc.",
      "cik": "0000320193"
    },
    ...
  ]
}
```

## 📤 Salida

### 1. Archivo principal: `precios.json`

```json
{
  "timestamp": "2024-06-20T14:30:00Z",
  "total": 295,
  "ok": 288,
  "errores": 7,
  "precios": {
    "AAPL": {
      "ticker_sec": "AAPL",
      "byma_tickers": ["AAPL", "AAPLB"],
      "nombre_sec": "Apple Inc.",
      "cik": "0000320193",
      "last_price": 300.23,
      "year_high": 303.20,
      "year_low": 193.46,
      "market_cap": 3000000000000,
      "shares": 14700000000,
      "currency": "USD",
      "exchange": "NMS",
      "previous_close": 298.50,
      "fetched_at": "2024-06-20T14:30:00Z"
    },
    "MSFT": {
      "ticker_sec": "MSFT",
      "byma_tickers": ["MSFT"],
      "nombre_sec": "Microsoft Corp",
      "cik": "0000789019",
      "last_price": 425.19,
      "year_high": 442.36,
      "year_low": 221.60,
      ...
    },
    ...
  }
}
```

### 2. Archivo de errores: `precios_errores.json`

```json
[
  {
    "ticker_sec": "XXXXX",
    "byma_tickers": ["XXXXX"],
    "nombre_sec": "Unknown Corp",
    "cik": "9999999999",
    "error": "no_data",
    "ticker_yf": "XXXXX"
  },
  {
    "ticker_sec": "YYYYY",
    "error": "Connection timeout",
    "ticker_yf": "YYYYY"
  },
  ...
]
```

## 📊 Estructura de cada Precio

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticker_sec` | string | Ticker de yfinance (AAPL, MSFT, etc.) |
| `byma_tickers` | array | Todos los tickers BYMA que usan este SEC ticker |
| `nombre_sec` | string | Nombre oficial de la empresa |
| `cik` | string | CIK de SEC (para mapeo) |
| `last_price` | float | Precio actual USD |
| `year_high` | float | Máximo últimos 365 días |
| `year_low` | float | Mínimo últimos 365 días |
| `market_cap` | float | Capitalización de mercado USD |
| `shares` | float | Acciones en circulación |
| `currency` | string | Moneda (normalmente USD) |
| `exchange` | string | Bolsa: NMS, NYQ, etc. |
| `previous_close` | float | Cierre anterior |
| `fetched_at` | ISO string | Timestamp exacto de la descarga |

## 📝 Normalización de Tickers

yfinance usa `-` donde SEC/BYMA usan `.`:
- Input: `BRK.B` → Converted: `BRK-B`
- Input: `AAPL` → No change: `AAPL`

## ⚙️ Parámetros

```python
DELAY = 0.2              # segundos entre requests
INPUT_FILE = "cedears_con_cik.json"
OUTPUT_FILE = "precios.json"
ERROR_FILE = "precios_errores.json"
```

## ❌ Errores Posibles

| Error | Causa | Acción |
|-------|-------|--------|
| `no_data` | yfinance no tiene datos para ese ticker | Registrar en errores, continuar |
| `Connection timeout` | yfinance no responde a tiempo | Registrar, continuar (retry en Job 1A) |
| `Network error` | Problema de conexión | Registrar, continuar |

## 🔗 Uso en Producción

En `backend/fetchers/precios.py` la función `descargar_ticker()` hace exactamente lo mismo pero devuelve un dict en lugar de escribir a archivo:

```python
def descargar_ticker(ticker: str) -> dict:
    """Devuelve dict con precio o {error: ...}"""
    # Mismo código que el script, pero sin I/O
    return {
        "last_price": ...,
        "year_high": ...,
        ...
    }
```

El Job 1A llama a esta función en un loop y hace UPSERT a `precios_raw`.

---

**Próximo paso:** 05_calcular_ratios.py (usa este output + financials_raw para calcular ratios)  
**Usa la salida:** Job 2 necesita `precios.json` para calcular PER, margen, etc.
