# Mapeo de Columnas: De Fuentes a seguimiento.csv

Este documento explica de dónde viene cada columna en el CSV final.

## 📋 Columnas de Identificación

| Columna | Fuente | Descripción |
|---------|--------|-------------|
| `byma_ticker` | cedears_con_cik.json | Ticker BYMA (lo que ves en el screener) |
| `ticker_sec` | cedears_con_cik.json | Ticker SEC / yfinance |
| `nombre` | cedears_con_cik.json | Nombre oficial empresa |
| `cik` | cedears_con_cik.json | CIK de SEC |
| `exchange` | precios.json | Bolsa (NMS, NYQ, etc.) |

---

## 💵 Columnas de Precio (de PASO 4 — yfinance)

| Columna | Fórmula | Fuente |
|---------|---------|--------|
| `precio_usd` | Directo | precios.json / `last_price` |
| `currency` | Directo | precios.json / `currency` |
| `year_high` | Directo | precios.json / `year_high` |
| `year_low` | Directo | precios.json / `year_low` |
| `dif_max_52w` | (precio / year_high) - 1 | Derivado |
| `dif_min_52w` | (precio / year_low) - 1 | Derivado |

---

## 📊 Columnas de Valuación (de PASO 5 — Cálculos)

| Columna | Fórmula | Fuentes |
|---------|---------|---------|
| `per_ttm` | precio / eps_ttm | precios + financials |
| `eps_ttm_diluted` | netincome_ttm / shares | financials |
| `cagr_eps_5y` | (eps_fin / eps_ini)^(1/5) - 1 | financials (10-K serie) |

---

## 💹 Columnas de Rentabilidad (de PASO 5 — Cálculos)

| Columna | Fórmula | Fuentes |
|---------|---------|---------|
| `margen_neto_ttm` | netincome_ttm / revenue_ttm | financials |
| `roe_cagr_5y` | CAGR(netincome/equity anual) | financials (10-K serie) |

---

## 💰 Columnas de Flujo de Caja (de PASO 5 — Cálculos)

| Columna | Fórmula | Fuentes |
|---------|---------|---------|
| `fcf_ttm` | cfo_ttm - capex_ttm | financials (debug) |
| `fcfonce_equity_lp` | fcf_ttm / (equity + lt_debt) | financials |
| `fcfonce_neto_caja` | fcf_ttm / (equity + deuda_total - cash) | financials |

---

## 📈 Columnas de Endeudamiento (de PASO 5 — Cálculos)

| Columna | Fórmula | Fuentes |
|---------|---------|---------|
| `deuda_lp_sobre_ebitda` | lt_debt / ebitda_ttm | financials |
| `deuda_total_sobre_ebitda` | deuda_total / ebitda_ttm | financials |
| `payout_ttm` | dividendos_ttm / netincome_ttm | financials |

---

## 🔍 Columnas Debug (para validación)

Todas comienzan con `_` y contienen valores intermedios usados en los cálculos.

| Columna | Qué es | Por qué |
|---------|--------|---------|
| `_revenue_ttm` | Revenue TTM en USD | Ver exacto qué fuente se usó |
| `_netincome_ttm` | NetIncome TTM en USD | Confirmar componente de PER/Margen |
| `_ebitda_ttm` | (OpInc + D&A) TTM | Revisar Deuda/EBITDA |
| `_fcf_ttm` | (CFO - CapEx) TTM | Validar FCFonCE |
| `_diluted_shares` | Shares ponderadas | Confirmar EPS calculation |
| `_equity` | StockholdersEquity último período | Revisar ROE, CE |
| `_lt_debt` | LongTermDebt último período | Deuda LP |
| `_deuda_total` | LT + ST + Current | Deuda total |
| `_metric_revenue` | Nombre métrica usada | "Revenues" vs "RevenueFromContract..." |
| `_metric_da` | Nombre métrica D&A usada | "DepreciationDepletionAndAmortization" vs "Depreciation" |

**Uso:** Si un ratio se ve sospechoso, revisa estas columnas debug para entender qué fuentes se usaron.

---

## 📐 Traceabilidad Paso a Paso

### Ejemplo: PER de AAPL

```
1. PASO 4 (yfinance):
   precios.json["AAPL"]["last_price"] = 300.23

2. PASO 3 (SEC EDGAR):
   financials_sec/0000320193.json["metricas"]["NetIncomeLoss"]
     + datos de 4 trimestres últimos
     = NetIncome_TTM = 122,575,000,000

   + financials_sec/0000320193.json["metricas"]["WeightedAverageNumberOfDilutedSharesOutstanding"]
     = Shares_Diluted = 14,768,115,000

3. PASO 5 (Cálculo):
   EPS_TTM = 122,575,000,000 / 14,768,115,000 = 8.30
   PER = 300.23 / 8.30 = 36.17

En seguimiento.csv:
   per_ttm = 36.17
   eps_ttm_diluted = 8.30
   _netincome_ttm = 122,575,000,000
   _diluted_shares = 14,768,115,000
```

---

## 🗺️ Mapeo Métrica XBRL

Cuando el script busca una métrica en SEC EDGAR, usa "fallback" — si la principal no existe, intenta alternativas:

| Concepto | Candidatos (en orden) |
|----------|----------------------|
| Revenue | Revenues → RevenueFromContractWithCustomerExcludingAssessedTax → SalesRevenueNet |
| NetIncome | NetIncomeLoss |
| OperatingIncome | OperatingIncomeLoss |
| D&A | DepreciationDepletionAndAmortization → DepreciationAndAmortization → Depreciation |
| CapEx | PaymentsToAcquirePropertyPlantAndEquipment → PaymentsToAcquireProductiveAssets |
| CFO | NetCashProvidedByUsedInOperatingActivities |
| Dividendos | PaymentsOfDividendsCommonStock → PaymentsOfDividends |
| Equity | StockholdersEquity |
| LT Debt | LongTermDebt |
| ST Debt | ShortTermBorrowings → DebtCurrent |
| Shares | WeightedAverageNumberOfDilutedSharesOutstanding → WeightedAverageNumberOfSharesOutstandingBasic |

Las columnas `_metric_*` registran cuál fue usada para cada empresa.

---

## 📊 Histograma: Columnas por Tipo

| Tipo | Cantidad | Ejemplos |
|------|----------|----------|
| Identificación | 5 | byma_ticker, nombre, cik |
| Precio (yfinance) | 6 | precio_usd, year_high, dif_max_52w |
| Ratios (cálculos) | 10+ | per_ttm, eps_ttm_diluted, margen_neto_ttm, etc. |
| Debug | 10+ | _revenue_ttm, _netincome_ttm, _metric_revenue, etc. |
| **Total** | **~30-35** | (varies: algunas columnas pueden ser NULL si falta data) |

**Nota:** El CSV real en `seguimiento.csv` tiene más columnas porque el script calcula otras variantes (ej. `crec_eps_5y` aunque esté NULL, ambas variantes de D/EBITDA, etc.).

---

## 🔗 Diagrama: Flujo de Datos a Columnas

```
cedears_con_cik.json
├─→ byma_ticker
├─→ ticker_sec
├─→ nombre
├─→ cik
└─→ exchange (también en precios.json)

precios.json
├─→ precio_usd
├─→ currency
├─→ year_high
├─→ year_low
├─→ dif_max_52w (calculado)
└─→ dif_min_52w (calculado)

financials_sec/*.json
├─→ NetIncomeLoss
│   ├─→ eps_ttm_diluted
│   ├─→ per_ttm (con precio_usd)
│   ├─→ cagr_eps_5y
│   └─→ _netincome_ttm
├─→ Revenues
│   ├─→ margen_neto_ttm (con NetIncome)
│   └─→ _revenue_ttm
├─→ OperatingIncomeLoss + D&A
│   ├─→ _ebitda_ttm
│   ├─→ deuda_lp_sobre_ebitda
│   └─→ deuda_total_sobre_ebitda
├─→ NetCashProvidedByUsedInOperatingActivities
│   ├─→ _fcf_ttm (con CapEx)
│   ├─→ fcfonce_equity_lp
│   └─→ fcfonce_neto_caja
├─→ StockholdersEquity
│   ├─→ roe_5y (con NetIncome)
│   └─→ _equity
├─→ Debt
│   ├─→ _lt_debt
│   ├─→ _deuda_total
│   └─→ deuda_ebitda
└─→ PaymentsOfDividends
    └─→ payout_ttm
```

---

**Para profundizar:** Ver `FORMULAS_RATIOS.md` para cómo se calcula cada ratio.
