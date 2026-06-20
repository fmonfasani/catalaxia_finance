# Script 03 — Descargar Financials desde SEC EDGAR

## 📋 Resumen

- **Qué hace:** Descarga el historial financiero completo (10-K + 10-Q) de todas las empresas desde SEC EDGAR XBRL.
- **Entrada:** `cedears_con_cik.json` (295 CIKs únicos)
- **Salida:** `financials_sec/*.json` (1 JSON por empresa) + `financials_index.json`
- **Duración:** ~45 segundos (295 empresas × 0.15s)
- **Responsable:** Backend B (Mateo)

## 📥 Entrada

**Archivo:** `cedears_con_cik.json`

```json
{
  "cedears": [
    {
      "byma_ticker": "AAPL",
      "ticker_sec": "AAPL",
      "nombre_sec": "Apple Inc.",
      "cik": "0000320193",
      "exchange": "NMS"
    },
    ...
  ]
}
```

**Datos utilizados:**
- `cik` — Central Index Key de SEC (10 dígitos, con ceros a la izquierda)
- `ticker_sec` — Ticker de Yahoo Finance
- `nombre_sec` — Nombre oficial de la empresa

## 📤 Salida

### 1. Archivos individuales: `financials_sec/{CIK}.json`

**Ejemplo:** `financials_sec/0000320193.json`

```json
{
  "schema_version": 3,
  "cik": "0000320193",
  "ticker_sec": "AAPL",
  "byma_tickers": ["AAPL", "AAPLB"],
  "nombre": "Apple Inc.",
  "entity_type": "large-accel",
  "metricas_disponibles": [
    "Revenues",
    "GrossProfit",
    "NetIncomeLoss",
    "OperatingIncomeLoss",
    "EarningsPerShareDiluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "DepreciationDepletionAndAmortization",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "LongTermDebt",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsOfDividendsCommonStock",
    ...
  ],
  "metricas": {
    "Revenues": {
      "unit": "USD",
      "datos": [
        {
          "start": "2022-10-02",
          "end": "2023-09-30",
          "val": 394328000000,
          "fy": 2023,
          "fp": "FY",
          "form": "10-K",
          "filed": "2023-11-03",
          "frame": "CY2023"
        },
        {
          "start": "2023-10-01",
          "end": "2023-12-30",
          "val": 114315000000,
          "fy": 2024,
          "fp": "Q1",
          "form": "10-Q",
          "filed": "2024-02-02",
          "frame": "CY2024Q1I"
        },
        ...
      ]
    },
    "NetIncomeLoss": {
      "unit": "USD",
      "datos": [...]
    },
    ...
  },
  "descargado_en": "2024-06-20T14:30:00.123456"
}
```

### 2. Índice: `financials_index.json`

```json
{
  "timestamp": "2024-06-20T14:30:45.123456",
  "total": 295,
  "ok": 290,
  "errores": 5,
  "empresas": [
    {
      "cik": "0000320193",
      "ticker": "AAPL",
      "nombre": "Apple Inc.",
      "byma_tickers": ["AAPL", "AAPLB"],
      "metricas": ["Revenues", "GrossProfit", ...],
      "estado": "ok"
    },
    {
      "cik": "0001234567",
      "ticker": "XXXX",
      "estado": "error",
      "error": "HTTP 404"
    },
    ...
  ]
}
```

### 3. Errores: `financials_errores.json`

```json
[
  {
    "cik": "0001234567",
    "ticker_sec": "XXXX",
    "nombre_sec": "Unknown Inc.",
    "error": "HTTP 404",
    "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK1234567.json"
  },
  ...
]
```

## 🔍 Estructura de un Datapoint (métrica)

Cada métrica tiene un array `datos` con datapoints así:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `start` | string (ISO date) | Inicio del período (NULL para balance sheets) |
| `end` | string (ISO date) | Fin del período reportado |
| `val` | float | Valor numérico |
| `fy` | int | Año fiscal (ej. 2023) |
| `fp` | string | Fiscal period: Q1, Q2, Q3, FY (annual) |
| `form` | string | Tipo de reporte: 10-K, 10-Q, 20-F, etc. |
| `filed` | string (ISO date) | Fecha en que se presentó (para dedup) |
| `frame` | string | Frame fiscal SEC: ej. CY2024Q1I |

**Ejemplo de cálculo de días:**
```
Q3 10-Q:  start=2023-07-01, end=2023-09-30  → 92 días (trimestre)
FY 10-K:  start=2022-10-02, end=2023-09-30  → 364 días (año)
YTD 10-Q: start=2023-10-01, end=2023-12-30  → 91 días (YTD acumulado)
```

## ⚙️ Parámetros Configurables

```python
DELAY = 0.15                    # segundos entre requests (rate limit SEC: 10 req/s)
FORCE_REDOWNLOAD = True         # re-descargar aunque exista
SCHEMA_VERSION = 3              # bump si cambia la estructura
FORMS_ACEPTADOS = ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A")
METRICAS_GAAP = [...]           # lista de 30+ métricas a extraer
PREFERENCIA_UNIDAD = ("USD", "USD/shares", "shares", "pure")
```

## 📌 Notas Importantes

### Dedup por (start, end, filed)

Si una empresa presenta una enmienda (10-K/A = 10-K amended), el mismo período puede tener 2 datapoints:
- Uno con `filed=2023-11-03` (presentación original)
- Otro con `filed=2023-11-10` (enmienda)

El script keepea el más reciente (higher `filed`). La tabla `financials_raw` en Postgres tiene un índice único que enforce esto.

### Métricas Equivalentes

SEC EDGAR usa nombres distintos para el mismo concepto según la empresa:
- Revenue: `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`
- D&A: `DepreciationDepletionAndAmortization`, `DepreciationAndAmortization`, `Depreciation`

El script `extraer_metricas()` guarda TODAS las métricas que existan, y luego en el Paso 5 se elige la "mejor" según fallback definido en `SCRIPT_05`.

### IFRS vs GAAP

Por defecto busca `us-gaap`. Si una empresa (ej. Infosys) reporta en IFRS, busca `ifrs-full`. El script actual solo mira `us-gaap` — para IFRS hay que adaptar.

## 🔗 Input/Output Esperado

### Métricas Extraídas (~30)

**Income Statement:**
- Revenues (3 variantes)
- GrossProfit, OperatingIncomeLoss, NetIncomeLoss
- EarningsPerShareBasic, EarningsPerShareDiluted
- WeightedAverageNumberOfDilutedSharesOutstanding

**Balance Sheet:**
- Assets, AssetsCurrent
- Liabilities, LiabilitiesCurrent
- StockholdersEquity, CashAndCashEquivalentsAtCarryingValue
- LongTermDebt, ShortTermBorrowings, DebtCurrent

**Cash Flow:**
- NetCashProvidedByUsedInOperatingActivities
- PaymentsToAcquirePropertyPlantAndEquipment (CapEx)
- PaymentsOfDividendsCommonStock

**D&A (3 variantes):**
- DepreciationDepletionAndAmortization
- DepreciationAndAmortization
- Depreciation

---

**Próximo paso:** 04_descargar_precios.py (yfinance)  
**Usa la salida:** Paso 5 necesita `financials_sec/*.json` para calcular ratios
