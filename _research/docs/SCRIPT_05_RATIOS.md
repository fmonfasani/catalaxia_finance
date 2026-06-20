# Script 05 — Calcular Ratios Fundamentales

## 📋 Resumen

- **Qué hace:** Calcula 60 ratios financieros por empresa combinando financials_sec/ + precios.json
- **Entrada:** `financials_sec/` (1 JSON/empresa) + `precios.json` + `cedears_con_cik.json`
- **Salida:** `seguimiento.csv` (1 fila/ticker) + `seguimiento.json`
- **Duración:** ~2-5 segundos (procesamiento en memoria)
- **Responsable:** Backend B (Mateo)

## 📥 Entrada

### 1. `financials_sec/{CIK}.json` (del Paso 3)

```json
{
  "metricas": {
    "Revenues": {
      "unit": "USD",
      "datos": [
        { "start": "2022-10-02", "end": "2023-09-30", "val": 394328000000, "form": "10-K", "fp": "FY" },
        { "start": "2023-10-01", "end": "2023-12-30", "val": 114315000000, "form": "10-Q", "fp": "Q1" },
        ...
      ]
    },
    "NetIncomeLoss": { ... },
    ...
  }
}
```

### 2. `precios.json` (del Paso 4)

```json
{
  "precios": {
    "AAPL": {
      "last_price": 300.23,
      "year_high": 303.20,
      "year_low": 193.46,
      "shares": 14700000000,
      ...
    },
    ...
  }
}
```

### 3. `cedears_con_cik.json` (mapeo maestro)

```json
{
  "cedears": [
    {
      "byma_ticker": "AAPL",
      "ticker_sec": "AAPL",
      "nombre_sec": "Apple Inc.",
      "cik": "0000320193",
      ...
    },
    ...
  ]
}
```

## 📤 Salida

### 1. CSV: `seguimiento.csv`

**Estructura:** 1 fila por BYMA ticker, ~60 columnas

```csv
byma_ticker,ticker_sec,nombre,cik,exchange,precio_usd,currency,per_ttm,year_high,dif_max_52w,year_low,dif_min_52w,deuda_lp_sobre_ebitda,deuda_total_sobre_ebitda,eps_ttm_diluted,cagr_eps_5y,margen_neto_ttm,roe_cagr_5y,fcfonce_equity_lp,fcfonce_neto_caja,payout_ttm,_revenue_ttm,_netincome_ttm,_ebitda_ttm,_fcf_ttm,_diluted_shares,_equity,_lt_debt,_deuda_total,_metric_revenue,_metric_da
AAPL,AAPL,Apple Inc.,0000320193,NMS,300.23,USD,36.17,303.20,-0.0098,193.46,0.552,0.52,0.57,8.30,,0.27,0.34,0.68,0.85,0.127,451442000000,122575000000,159976000000,129174000000,14768115000,106491000000,82700000000,91010000000,RevenueFromContractWithCustomerExcludingAssessedTax,DepreciationDepletionAndAmortization
MSFT,MSFT,Microsoft Corp,0000789019,NMS,425.19,USD,45.23,...
...
```

### 2. JSON: `seguimiento.json`

```json
{
  "timestamp": "2024-06-20T14:30:00Z",
  "count": 288,
  "filas": [
    {
      "byma_ticker": "AAPL",
      "ticker_sec": "AAPL",
      "nombre": "Apple Inc.",
      "cik": "0000320193",
      "exchange": "NMS",
      "precio_usd": 300.23,
      "per_ttm": 36.17,
      "eps_ttm_diluted": 8.30,
      "margen_neto_ttm": 0.27,
      "roe_cagr_5y": 0.34,
      "fcfonce_equity_lp": 0.68,
      "deuda_ebitda": 0.57,
      "payout_ttm": 0.127,
      ...
    },
    ...
  ]
}
```

## 📐 Ratios Calculados

### Precios (de yfinance)

| Ratio | Fórmula |
|-------|---------|
| `precio_usd` | Directo de yfinance |
| `year_high` / `year_low` | Directo de yfinance |
| `dif_max_52w` | (precio / year_high) - 1 |
| `dif_min_52w` | (precio / year_low) - 1 |

### Ratios de Valuación

| Ratio | Fórmula | Notas |
|-------|---------|-------|
| `per_ttm` | precio / EPS_TTM | NULL si EPS < 0 |
| `eps_ttm_diluted` | NetIncome_TTM / Diluted_Shares | Usar shares ponderadas |
| `cagr_eps_5y` | (EPS_fin / EPS_ini)^(1/5) - 1 | Solo si 5+ años de datos |

### Ratios de Rentabilidad

| Ratio | Fórmula | Notas |
|-------|---------|-------|
| `margen_neto_ttm` | NetIncome_TTM / Revenue_TTM | NULL si Revenue = 0 |
| `roe_cagr_5y` | CAGR(NetIncome/Equity anual) | CAGR de la serie ROE anual |

### Ratios de Flujo de Caja

| Ratio | Fórmula | Notas |
|-------|---------|-------|
| `fcf_ttm` | CFO_TTM - CapEx_TTM | Free Cash Flow Trailing |
| `fcfonce_equity_lp` | FCF_TTM / (Equity + LT_Debt) | CE = Capital Empleado (variante 1) |
| `fcfonce_neto_caja` | FCF_TTM / (Equity + Deuda_Total - Cash) | CE neto de caja (variante 2) |

### Ratios de Endeudamiento

| Ratio | Fórmula | Notas |
|-------|---------|-------|
| `deuda_lp_sobre_ebitda` | LongTermDebt / EBITDA_TTM | Solo deuda LP |
| `deuda_total_sobre_ebitda` | Deuda_Total / EBITDA_TTM | Deuda LP + ST |
| `payout_ttm` | Dividendos_TTM / NetIncome_TTM | NULL si NI < 0 |

### Columnas Debug (para validación)

Todas empiezan con `_`:

| Columna | Descripción |
|---------|-------------|
| `_revenue_ttm` | Ingresos TTM usados |
| `_netincome_ttm` | Ingreso neto TTM usados |
| `_ebitda_ttm` | EBITDA calculado (OpInc + D&A) |
| `_fcf_ttm` | FCF calculado (CFO - CapEx) |
| `_diluted_shares` | Shares ponderadas diluted |
| `_equity` | Patrimonio último período |
| `_lt_debt` | Deuda LP último período |
| `_deuda_total` | Deuda total (LP + ST) |
| `_metric_revenue` | Nombre del campo Revenue usado |
| `_metric_da` | Nombre del campo D&A usado |

## 🧮 TTM (Trailing Twelve Months)

**Para FLUJOS (Revenue, NetIncome, CFO, CapEx, Dividendos, D&A):**

Estrategia 1: 4 trimestres consecutivos (~90d c/u) → Sumar  
Estrategia 2: Annual_FY + YTD_actual - YTD_prior_year  
Estrategia 3: Último Annual (~365d) solo

```python
# En el script, función ttm_flujo():
# Intenta A primero, luego B, luego C
```

**Para STOCKS (Equity, Debt, Cash, Shares):**  
Última fecha disponible del período más reciente.

## 🔄 CAGR (Compound Annual Growth Rate)

```
CAGR = (valor_fin / valor_ini)^(1/years) - 1
```

Requiere:
- Serie anual (10-K, ~365d)
- Mínimo `years + 1` datapoints (ej. 6 años para CAGR 5y)
- Ambos extremos > 0

Si no hay datos suficientes: `NULL`

## 🛑 EBITDA (No existe en XBRL)

Se calcula:
```
EBITDA = OperatingIncome + D&A
```

Si falta algún componente: `NULL` (nunca se estima)

## 📊 Ejemplo de Cálculo

**Para AAPL (ficticio):**

```
Revenue_TTM = $394B (anual 2023)
NetIncome_TTM = $122B (anual 2023)
CFO_TTM = $129B (anual 2023)
CapEx_TTM = $11B (anual 2023)
D&A_TTM = $15B (anual 2023)
Shares_Diluted = 14.77B
Equity = $106.5B
LT_Debt = $82.7B
Cash = $29.9B (para CE neto)

Cálculos:
- EPS_TTM = 122B / 14.77B = $8.26
- PER = 300.23 / 8.26 = 36.36
- Margen Neto = 122B / 394B = 31%
- EBITDA = OpInc + 15B = ~$100B (OpInc = ~85B, aproximado)
- Deuda/EBITDA = 82.7B / 100B = 0.83
- FCF = 129B - 11B = $118B
- FCFonCE = 118B / (106.5B + 82.7B) = 63%
- Payout = Dividendos_TTM / 122B = (depende de Dividendos)
```

---

**Próximo paso:** Estos datos van a `precios_raw` + `financials_raw` en PostgreSQL, y luego a `ratios`  
**Usa la salida:** El frontend consume `seguimiento.csv` para el dashboard
