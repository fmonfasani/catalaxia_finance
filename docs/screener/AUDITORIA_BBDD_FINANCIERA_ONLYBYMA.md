# Auditoría Técnica y Funcional — Base de Datos Financiera Catalaxia Finance
## Universo: Empresas Only-BYMA

**Fecha:** 28 Junio 2026  
**Versión:** 1.0

---

## Índice

1. [Estado General del Dataset](#1-estado-general-del-dataset)
2. [Cobertura por Empresa](#2-cobertura-por-empresa)
3. [Cobertura Temporal](#3-cobertura-temporal)
4. [Cobertura por Tipo de Estado Financiero](#4-cobertura-por-tipo-de-estado-financiero)
5. [Inventario Completo de Conceptos (Tags)](#5-inventario-completo-de-conceptos)
6. [Clasificación de Conceptos Financieros](#6-clasificación-de-conceptos-financieros)
7. [Calidad del Modelo Actual](#7-calidad-del-modelo-actual)
8. [Ratios Financieros Actualmente Posibles](#8-ratios-financieros-actualmente-posibles)
9. [Ratios Potenciales con Datos Adicionales](#9-ratios-potenciales-con-datos-adicionales)
10. [Diseño Recomendado del Modelo de Datos Maestro](#10-diseño-recomendado-del-modelo-de-datos-maestro)
11. [Principales Debilidades](#11-principales-debilidades)
12. [Principales Fortalezas](#12-principales-fortalezas)
13. [Riesgos](#13-riesgos)
14. [Oportunidades de Mejora](#14-oportunidades-de-mejora)
15. [Roadmap de Evolución](#15-roadmap-de-evolución)

---

## 1. Estado General del Dataset

### 1.1 Universo Only-BYMA

| Métrica | Valor |
|---|---|
| Empresas en universo Only-BYMA | **56** |
| Empresas en `acciones_solo_byma.csv` original | 19 (subconjunto) |
| Empresas realmente "solo-BYMA" (sin ADR en USA) | ~49 de 56 |
| Empresas con datos financieros | **56/56 (100%)** vía yfinance, **14/56 (25%)** vía CNV |
| Empresas sin ningún dato | **0** |

### 1.2 Tablas en `screener.db`

| Tabla | Filas | Propósito | Calidad |
|---|---|---|---|
| `facts` | 4,644,898 | EDGAR XBRL (US, ADRs) + yfinance BYMA | Completa para US; incompleta en mapeo BYMA |
| `cnv_estados` | 367 | CNV AIF2 + IR + 6-K para Argentina | Muy pocos períodos, solo 7 empresas con datos ricos |
| `empresas` | 8,077 | Catálogo maestro de empresas | 56 byma_yf, 500 sp500, 7,458 us_other |
| `ratios` | 553 | Ratios pre-calculados | Solo ADRs argentinos (7), no cubre pure BYMA |
| `precios` | 553 | Precios y market cap | Mismo alcance que ratios |
| `tickers` | 10,433 | Mapeo ticker→CIK→exchange | Completo para US |
| `descargas_log` | 0 | Log de descargas | Vacío |

### 1.3 Fuentes de Datos

| Fuente | Cobertura BYMA | Conceptos | Períodos | Calidad |
|---|---|---|---|---|
| **YFinance (ANUAL-YF)** | **56/56 (100%)** | 254 tags únicos, ~157/empresa | 5 años (2021-2025) | **ALTA**: datos estandarizados, multi-año |
| **CNV AIF2** | 7/56 (12.5%) | 36 conceptos | 1-2 períodos | **ALTA** en riqueza conceptual, pero **MUY BAJA** cobertura |
| **CNV 6-K** | 7/56 (12.5%) | 3-10 conceptos | 1 período | **BAJA**: muy pocos conceptos |
| **CNV IR** | 8/56 (14.3%) | 8-10 conceptos | 1 período | **BAJA** |

**Hallazgo crítico:** La fuente YFinance es **drásticamente superior** a CNV en cobertura (100% vs 25%) y cantidad de períodos (5 años vs 1-2). Sin embargo, CNV AIF2 tiene conceptos más detallados del balance (activo corriente/pasivo corriente, inventarios, etc.) que yfinance no provee.

---

## 2. Cobertura por Empresa

### 2.1 Empresas con Datos Ricos (>=100 conceptos)

**56 empresas** vía yfinance (ANUAL-YF), detalle completo en Anexo A.

### 2.2 Empresas con Datos CNV AIF2 Detallados (>=30 conceptos)

| # | Ticker | Empresa | Conceptos | Períodos | Fuente |
|---|---|---|---|---|---|
| 1 | ALUA | Aluar Aluminio Argentino | 36 | 2 | cnv-aif2 |
| 2 | CVH | Cablevisión Holding | 36 | 1 | cnv-aif2 |
| 3 | LEDE | Ledesma S.A. | 35 | 1 | cnv-aif2 |
| 4 | MOLA | Molinos Agro S.A. | 35 | 1 | cnv-aif2 |
| 5 | GBAN | Naturgy BAN S.A. | 34 | 1 | cnv-aif2 |
| 6 | TRAN | Transener S.A. | 34 | 1 | cnv-aif2 |
| 7 | METR | Metrogas S.A. | 33 | 1 | cnv-aif2 |

### 2.3 Empresas con Datos CNV 6-K Parciales (3-10 conceptos)

| # | Ticker | Conceptos | Períodos |
|---|---|---|---|
| 1 | LOMA | 10 | 1 |
| 2 | CEPU | 9 | 1 |
| 3 | BYMA | 10 | 1 |
| 4 | BOLT, A3, GAMI, CTIO | 8-9 | 1 |
| 5 | EDN | 5 | 1 |
| 6 | BBAR | 4 | 2 |
| 7 | BMA, SUPV | 4 | 1 |
| 8 | GGAL | 3 | 1 |

### 2.4 Empresas SIN Datos en `cnv_estados`

**0 empresas** — todas las 56 tienen datos vía yfinance en `facts` table (CIK format `BYMA-TICKER`).

### 2.5 Matriz de Cobertura Consolidada

```
                          yfinance  CNV-AIF2  CNV-6K   Ratios   Precios
ALUA       Aluar             √         √         -        -        -
BBAR       BBVA Banco        √         -         √        √        √
BMA        Banco Macro       √         -         √        √        √
CEPU       Central Puerto    √         -         √        √        √
CVH        Cablevisión       √         √         -        -        -
EDN        Edenor            √         -         √        √        √
GBAN       Naturgy BAN       √         √         -        -        -
GCLA       Grupo Clarín      √         -         -        -        -
GGAL       Grupo Galicia     √         -         √        √        √
LEDE       Ledesma           √         √         -        -        -
LOMA       Loma Negra        √         -         √        √        √
METR       Metrogas          √         √         -        -        -
MOLA       Molinos Agro      √         √         -        -        -
PAMP       Pampa Energía     √         -         -        -        -
SUPV       Supervielle       √         -         √        √        √
TRAN       Transener         √         √         -        -        -
...        40 más            100%      0%         0%       0%       0%
```

---

## 3. Cobertura Temporal

### 3.1 YFinance (ANUAL-YF)

| Métrica | Valor |
|---|---|
| Rango total | FY2021 — FY2026 |
| Períodos promedio | **4.7 años** por empresa |
| Máximo de períodos | **5 años** (45/56 empresas) |
| Mínimo de períodos | **2 años** (ECOG) |
| Datapoints FY2021 | 1,028 |
| Datapoints FY2022 | 7,765 |
| Datapoints FY2023 | 7,926 |
| Datapoints FY2024 | 8,158 |
| Datapoints FY2025 | 7,480 |
| Datapoints FY2026 | 285 (parcial) |

### 3.2 CNV AIF2

| Empresa | Períodos | Rango |
|---|---|---|
| ALUA | 2 (2025-12-31, latest) | 1 año |
| CVH, GBAN, LEDE, METR, MOLA, TRAN | 1 ("latest") | 0 años reales |

**Problema grave:** Los datos CNV AIF2 en `cnv_estados` tienen `period_end="latest"` en lugar de una fecha real. Esto impide cualquier análisis temporal. Solo ALUA tiene 2 períodos con una fecha real (2025-12-31) y "latest".

### 3.3 CNV 6-K

| Empresa | Períodos | Rango |
|---|---|---|
| BBAR | 2 | 2024-05 a 2024-08 |
| BMA, CEPU, EDN, GGAL, LOMA, SUPV | 1 | 2026 |

### 3.4 Huecos Históricos

- **YFinance**: Sin datos pre-2021. Cubre 5 años. No hay datos 2020 (pandemia) ni históricos más largos.
- **CNV AIF2**: Datos existentes en `links_eeff_refined.csv` con GUIDS para múltiples años (formTypeId=147), pero **nunca fueron extraídos más que el último**. GRIM pipeline demostró que hay datos desde al menos 2019.
- **CNV 6-K**: Solo un trimestre o un punto en el tiempo. No hay series.

---

## 4. Cobertura por Tipo de Estado Financiero

### 4.1 YFinance (ANUAL-YF)

Los 254 tags se agrupan naturalmente en:

| Categoría | Tags | Cobertura |
|---|---|---|
| **Estado de Resultados** | ~24 | Total Revenue, Net Income, EBITDA, Gross Profit, etc. |
| **Balance General** | ~21 | Total Assets, Stockholders Equity, Total Debt, etc. |
| **Flujo de Caja** | ~9 | Free Cash Flow, Operating Cash Flow, Capex, Dividends |
| **Métricas Financieras** | ~20+ | Market Cap, Enterprise Value, PER, ROE, etc. |
| **Métricas Operativas** | ~3 | Asset Turnover, Inventory Turnover, etc. |
| **No clasificados** | ~197 | Otros ratios y métricas derivadas de yfinance |

**Limitación importante:** yfinance no discrimina entre Current/Non-Current para activos y pasivos. No existen `Total Current Assets`, `Total Current Liabilities`, `Inventory` como tags separados. Esto impide ratios de liquidez.

### 4.2 CNV AIF2 (36 conceptos)

| Categoría | Conceptos | Ejemplos |
|---|---|---|
| **Balance - Activo** | 8/8 (100%) | Cash, Receivables, Inventory, AssetsCurrent, PPE, Intangibles, AssetsNonCurrent, Assets |
| **Balance - Pasivo** | 6/6 (100%) | DebtCurrent, Payables, LiabilitiesCurrent, DebtNonCurrent, LiabilitiesNonCurrent, Liabilities |
| **Balance - PN** | 4/4 (100%) | Capital, Reservas, ResultadosNoAsignados, Equity |
| **Resultados** | 12/12 (100%) | Revenue, COGS, GrossProfit, DA, OperatingIncome, etc. |
| **Flujo** | 1 | CashFlowNeto |
| **Métricas** | 5 | EBIT, EBITDA, EPS_basico, EPS_diluido, WorkingCapital |

**Fortaleza de CNV AIF2:** Es la **única fuente** que provee desglose Activo Corriente/No Corriente, Pasivo Corriente/No Corriente, Deuda CP/LP, Inventarios, e Intangibles.

### 4.3 CNV 6-K

- Sparse: 3-10 conceptos por empresa. Principalmente datos de Balance general (Assets, Liabilities, Equity) y algunos de resultados (NetIncome, Revenue).

---

## 5. Inventario Completo de Conceptos

### 5.1 YFinance — Top 50 Tags por Frecuencia

| Tag | Frecuencia | Empresas | Períodos |
|---|---|---|---|
| Total Revenue | 217 | 56 | 5 |
| Net Income | 217 | 56 | 5 |
| Total Assets | 217 | 56 | 5 |
| Stockholders Equity | 217 | 56 | 5 |
| Total Liabilities Net Minority Interest | 217 | 56 | 5 |
| Total Equity Gross Minority Interest | 217 | 56 | 5 |
| Total Capitalization | 217 | 56 | 5 |
| Tax Provision | 217 | 56 | 5 |
| Pretax Income | 217 | 56 | 5 |
| Free Cash Flow | 217 | 56 | 5 |
| Basic EPS | 217 | 56 | 5 |
| Cash And Cash Equivalents | 216 | 56 | 5 |
| Operating Revenue | 217 | 56 | 5 |
| Other Operating Expenses | 218 | 56 | 5 |
| Operating Expense | 218 | 56 | 5 |
| Normalized Income | 218 | 56 | 5 |
| Total Tax Payable | 217 | 56 | 5 |
| ... | ... | ... | ... |

**254 tags únicos** en total. Disponibilidad completa para las 56 empresas en los tags principales.

### 5.2 CNV AIF2 — Conceptos Completo

| Concepto | Frecuencia | Empresas | Categoría |
|---|---|---|---|
| Assets | 15 | 13 | Balance |
| Liabilities | 14 | 12 | Balance |
| NetIncome | 13 | 11 | Resultados |
| Equity | 13 | 11 | Balance |
| Cash | 13 | 12 | Balance |
| OperatingIncome | 11 | 11 | Resultados |
| GrossProfit | 11 | 10 | Resultados |
| Revenue | 10 | 9 | Resultados |
| COGS | 10 | 9 | Resultados |
| AssetsCurrent | 10 | 9 | Balance |
| LiabilitiesCurrent | 10 | 9 | Balance |
| ... y 26 más | | | |

### 5.3 Equivalencias CNV ↔ YFinance

| Concepto CNV | Tag YFinance | Notas |
|---|---|---|
| Cash | Cash And Cash Equivalents | ✓ |
| Receivables | Accounts Receivable | Diferente nombre |
| Inventory | (no existe como tag separado) | Solo disponible CNV |
| AssetsCurrent | (no existe) | Solo disponible CNV |
| AssetsNonCurrent | (no existe) | Solo disponible CNV |
| PPE | Property Plant And Equipment Gross | ✓ |
| Intangibles | Intangible Assets Excluding Goodwill | ✓ |
| Assets | Total Assets | ✓ |
| Equity | Stockholders Equity | ✓ |
| DebtCurrent | Short Term Debt | ✓ |
| DebtNonCurrent | Long Term Debt | ✓ |
| Revenue | Total Revenue | ✓ |
| COGS | Cost Of Revenue | ✓ |
| GrossProfit | Gross Profit | ✓ |
| DA | Reconciled Depreciation | ✓ |
| OperatingIncome | Operating Income | ✓ |
| InterestExpense | Interest Expense | ✓ |
| PretaxIncome | Pretax Income | ✓ |
| IncomeTax | Tax Provision | ✓ |
| NetIncome | Net Income | ✓ |
| EBITDA | EBITDA | ✓ |
| EPS_basico | Basic EPS | ✓ |
| CashFlowNeto | Cash Flow | ✓ |
| WorkingCapital | Working Capital | ✓ |

---

## 6. Clasificación de Conceptos Financieros

### 6.1 Taxonomía Propuesta

Basado en el inventario real, se propone la siguiente taxonomía para Catalaxia Finance:

```
📂 Balance General
   ├── Activo Corriente (CNV only: Cash, Receivables, Inventory)
   ├── Activo No Corriente (CNV only: PPE, Intangibles)
   ├── Total Activo (CNV + YF)
   ├── Pasivo Corriente (CNV+only: DebtCurrent, Payables)
   ├── Pasivo No Corriente (CNV only)
   ├── Total Pasivo (CNV + YF)
   └── Patrimonio Neto (CNV + YF)

📂 Estado de Resultados
   ├── Revenue / Total Revenue
   ├── COGS / Cost Of Revenue
   ├── Gross Profit
   ├── Operating Expense
   ├── EBITDA
   ├── Operating Income
   ├── Pretax Income
   ├── Tax Provision
   └── Net Income

📂 Flujo de Caja
   ├── Operating Cash Flow
   ├── Free Cash Flow
   ├── Capital Expenditure
   └── Dividends Paid

📂 Métricas por Acción
   ├── Basic EPS
   ├── Book Value Per Share
   └── Free Cash Flow Per Share

📂 Ratios (calculados)
   ├── Margen Neto, Bruto, EBITDA, Operativo
   ├── ROE, ROA, ROIC
   ├── Deuda/Equity, Deuda/EBITDA
   ├── PER, P/BV, P/S
   └── Current Ratio, Quick Ratio (solo CNV)
```

### 6.2 Mapeo a Taxonomías IFRS / US GAAP

Los tags YFinance siguen una nomenclatura propietaria pero consistente con US GAAP. Los conceptos CNV siguen RT (Resoluciones Técnicas) argentinas (RT 6, RT 9, RT 17) que convergen con IFRS. El mapeo es 1:1 en la mayoría de los casos.

---

## 7. Calidad del Modelo Actual

### 7.1 Problemas Detectados

| # | Problema | Severidad | Impacto |
|---|---|---|---|
| 1 | **`period_end="latest"`** en CNV AIF2 | **CRÍTICO** | 6/7 empresas AIF2 tienen fecha "latest". Imposible hacer análisis temporal |
| 2 | **CIK inconsistente entre tablas** | **ALTO** | `facts` usa `BYMA-TICKER` para BYMA; `empresas` lo mapea bien pero `ratios`/`precios` no tienen BYMA |
| 3 | **Dos modelos de datos aislados** | **ALTO** | `cnv_estados` (CNV AIF2) y `facts` (YF/EDGAR) son tablas separadas sin join posible |
| 4 | **Duplicados en cnv_estados** | MEDIO | Posibles duplicados (ticker+concepto+period_end) |
| 5 | **Sin datos pre-2021** | MEDIO | YFinance solo ofrece 5 años históricos |
| 6 | **Ratios solo para ADRs** | MEDIO | 7/56 empresas tienen ratios calculados; 49/56 no |
| 7 | **Escalas inconsistentes** | BAJO | `escala` columna existe pero no está normalizada |
| 8 | **Empresas sin nombre** | BAJO | Muchas empresas solo-BYMA no tienen nombre completo en `empresas.csv` |

### 7.2 Métricas de Calidad

| Métrica | Valor |
|---|---|
| Cobertura de empresas (YF) | 100% |
| Cobertura de empresas (CNV) | 12.5% |
| Conceptos duplicados | 0 (nombres únicos) |
| Sinónimos detectados | Ninguno (CNV e YF usan nomenclatura diferente) |
| Valores NULL | 0 |
| Valores CERO | ~5% |
| Series multi-año completas | 80% (45/56 con 5 años) |

---

## 8. Ratios Financieros Actualmente Posibles

### 8.1 Ratios Calculables con YFinance (56 empresas)

| Ratio | Fórmula | Disponibilidad | Empresas |
|---|---|---|---|
| **Margen Neto** | NetIncome / TotalRevenue | ✓ | 56/56 |
| **Margen Bruto** | GrossProfit / TotalRevenue | ✓ | 53/56 |
| **Margen EBITDA** | EBITDA / TotalRevenue | ✓ | 54/56 |
| **Margen Operativo** | OperatingIncome / TotalRevenue | ✓ | 54/56 |
| **ROE** | NetIncome / StockholdersEquity | ✓ | 56/56 |
| **ROA** | NetIncome / TotalAssets | ✓ | 56/56 |
| **Debt/Equity** | TotalDebt / StockholdersEquity | ✓ | 50/56 |
| **Debt/EBITDA** | TotalDebt / EBITDA | ✓ | 48/56 |
| **EPS** | Basic EPS | ✓ | 56/56 |
| **FCF Yield** | FreeCashFlow / MarketCap | Parcial (sin MarketCap) | 0/56 |
| **Payout** | DividendsPaid / NetIncome | Parcial | ~50/56 |
| **Capex/Revenue** | CapitalExpenditure / TotalRevenue | ✓ | 55/56 |
| **Crecimiento Revenue** | CAGR 5y Revenue | ✓ | 56/56 |
| **Crecimiento EPS** | CAGR 5y BasicEPS | ✓ | 56/56 |
| **Crecimiento NetIncome** | CAGR 5y NetIncome | ✓ | 56/56 |
| **Crecimiento Equity** | CAGR 5y StockholdersEquity | ✓ | 56/56 |
| **Book Value Per Share** | StockholdersEquity / Shares | ✓ | 56/56 |
| **FCF/Share** | FreeCashFlow / Shares | ✓ | 56/56 |

### 8.2 Ratios Solo Posibles con CNV AIF2 (7 empresas)

| Ratio | Fórmula | Disponibilidad |
|---|---|---|
| **Current Ratio** | AssetsCurrent / LiabilitiesCurrent | 7/56 |
| **Quick Ratio** | (Cash + Receivables) / LiabilitiesCurrent | 7/56 |
| **Cash Ratio** | Cash / LiabilitiesCurrent | 7/56 |
| **Deuda CP/LP** | DebtCurrent / DebtNonCurrent | 5/56 |
| **Working Capital** | AssetsCurrent - LiabilitiesCurrent | 7/56 |
| **Rotación Inventarios** | COGS / Inventory | 5/56 |
| **Rotación Activos** | Revenue / Assets | 7/56 |

### 8.3 Ratios del Dashboard Seguimiento.xlsx vs Realidad

| Ratio | Seguimiento.xlsx | YF (56 emp) | CNV (7 emp) |
|---|---|---|---|
| Precio u$s | ✓ | Parcial (sin precio BYMA) | ✗ |
| PER | ✓ | Necesita precio + EPS | ✗ |
| Máx/Mín 52 sem | ✓ | Sin datos de precio BYMA | ✗ |
| Deuda/EBITDA | ✓ | ✓ (48/56) | ✓ (7/7) |
| EPS | ✓ | ✓ (56/56) | ✓ (7/7) |
| Crec. EPS 5y | ✓ | ✓ (56/56) | ✗ (solo 1 período) |
| Margen Neto | ✓ | ✓ (56/56) | ✓ (7/7) |
| ROE | ✓ | ✓ (56/56) | ✓ (7/7) |
| FCF/CE | ✓ | ✓ (55/56) | ✗ |
| Payout | ✓ | ~50/56 | ✗ |

---

## 9. Ratios Potenciales con Datos Adicionales

### 9.1 Lo que Falta para Tener Ratios Completos

Para emular Seguimiento.xlsx para las 56 empresas, falta:

| Dato Faltante | Fuente Posible | Complejidad |
|---|---|---|
| **Precio BYMA (ARS)** | Yahoo Finance `TICKER.BA` | Baja |
| **Precio BYMA (USD)** | Yahoo Finance + tipo de cambio CCL | Media |
| **Market Cap BYMA** | Precio × Shares Outstanding | Baja (una vez tenemos precio) |
| **Shares Outstanding** | YF ya lo tiene (Weighted Average Shares) | Baja |
| **52-week High/Low** | Yahoo Finance history | Baja |
| **Tipo de Cambio ARS/USD** | API bluelytics / BCRA | Baja |
| **Ratios de liquidez** | Solo CNV (necesita Current Assets/Liabilities) | Alta (solo 7 empresas) |
| **EV (Enterprise Value)** | Market Cap + Debt - Cash | Media |

### 9.2 Potencial Completo con Integración YF + Precio

Si se agrega el precio BYMA (Yahoo Finance `TICKER.BA`) para las 56 empresas:

| Ratio | Disponible para |
|---|---|
| PER | 56/56 |
| P/BV | 56/56 |
| P/S | 56/56 |
| EV/EBITDA | 50/56 |
| FCF Yield | 56/56 |
| Earnings Yield | 56/56 |
| Dividend Yield | 50/56 |
| Crecimiento 5y (Revenue, EPS, NI, Equity) | 56/56 |
| Margen Neto, Bruto, EBITDA, Op. | 53-56/56 |
| ROE, ROA | 56/56 |
| Deuda/Equity, Deuda/EBITDA | 48-50/56 |
| Capex/Revenue | 55/56 |

**Solo NO posible sin CNV**: Current Ratio, Quick Ratio, Rotación Inventarios, DSO — porque requieren desglose corriente/no corriente que solo CNV AIF2 provee.

---

## 10. Diseño Recomendado del Modelo de Datos Maestro

### 10.1 Arquitectura

Basado en el análisis, propongo un modelo unificado con 5 capas:

```
┌────────────────────────────────────────────────────┐
│                  CAPA DE CONSUMO                     │
│  dashboard_eeff  │  ratios_master  │  signals        │
├────────────────────────────────────────────────────┤
│               CAPA DE NORMALIZACIÓN                  │
│  eeff_unified (unifica cnv_estados + facts)          │
├────────────────────────────────────────────────────┤
│           CAPA DE FUENTES (raw, inmutable)           │
│  facts (raw)  │  cnv_estados (raw)  │  precios       │
├────────────────────────────────────────────────────┤
│              CAPA MAESTRA DE ENTIDADES                │
│  empresa_master (SSOT) │  ticker_map                 │
└────────────────────────────────────────────────────┘
```

### 10.2 Tablas Propuestas

#### `empresa_master` (SSOT definitivo)

```sql
CREATE TABLE empresa_master (
    id INTEGER PRIMARY KEY,
    ticker_byma TEXT NOT NULL,          -- Ticker en BYMA (ej: PAMP)
    nombre_oficial TEXT,                -- Razón social
    nombre_corto TEXT,                  -- Nombre de fantasia
    cuit TEXT,                          -- CUIT Argentina
    cik_edgar TEXT,                     -- CIK SEC EDGAR (si aplica)
    cik_byma TEXT,                      -- CIK BYMA-YF (BYMA-TICKER)
    is_solo_byma INTEGER DEFAULT 1,     -- 1 = solo BYMA, 0 = tiene ADR
    is_adr INTEGER DEFAULT 0,           -- 1 = también cotiza en USA
    sector TEXT,                        -- Sector industrial
    pais TEXT DEFAULT 'AR',
    moneda_fiscal TEXT DEFAULT 'ARS',
    fiscal_year_end TEXT,               -- MM-DD
    fuente_descubrimiento TEXT,         -- Cómo se descubrió
    estado TEXT DEFAULT 'activo',        -- activo, inactivo, fusionado
    created_at TEXT,
    updated_at TEXT
);
```

#### `eeff_unified` (hechos financieros normalizados)

```sql
CREATE TABLE eeff_unified (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresa_master(id),
    concepto TEXT NOT NULL,              -- Concepto normalizado (IFRS/US GAAP)
    periodo_inicio TEXT,                 -- Fecha inicio del período
    periodo_fin TEXT,                    -- Fecha cierre del período
    valor REAL,                         -- Valor numérico
    moneda TEXT DEFAULT 'ARS',          -- ARS / USD
    escala INTEGER DEFAULT 1,           -- 1=unidad, 1000=miles, 1e6=millones
    tipo_periodo TEXT,                  -- FY / Q1 / Q2 / Q3 / Q4 / H1
    año_fiscal INTEGER,                 -- Año fiscal (2021, 2022...)
    fuente TEXT,                        -- 'yfinance' / 'cnv-aif2' / 'cnv-6k' / 'cnv-ir' / 'edgar'
    fuente_id TEXT,                     -- ID en la fuente original (GUID, ACCN...)
    calidad INTEGER DEFAULT 1,          -- 1=OK, 0=revisar
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### `ratios_master` (ratios pre-calculados, versionados)

```sql
CREATE TABLE ratios_master (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresa_master(id),
    año_fiscal INTEGER,
    tipo_periodo TEXT,                  -- FY / TTM
    moneda TEXT DEFAULT 'ARS',
    -- Rentabilidad
    margen_neto REAL,
    margen_bruto REAL,
    margen_ebitda REAL,
    margen_operativo REAL,
    roe REAL,
    roa REAL,
    roce REAL,                          -- ROCE si hay datos
    -- Endeudamiento
    deuda_equity REAL,
    deuda_ebitda REAL,
    deuda_neta_ebitda REAL,
    -- Liquidez (si hay datos)
    current_ratio REAL,
    quick_ratio REAL,
    -- Valuación
    per REAL,
    p_book REAL,
    p_sales REAL,
    ev_ebitda REAL,
    earnings_yield REAL,
    fcf_yield REAL,
    div_yield REAL,
    -- Crecimiento
    cagr_revenue_5y REAL,
    cagr_eps_5y REAL,
    cagr_ni_5y REAL,
    cagr_equity_5y REAL,
    -- Flujo
    fcf_margin REAL,
    capex_revenue REAL,
    earnings_quality REAL,
    payout REAL,
    -- Flags
    flags TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### `precios_byma` (precios históricos diarios)

```sql
CREATE TABLE precios_byma (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresa_master(id),
    fecha TEXT NOT NULL,
    precio_ars REAL,
    precio_usd_ccl REAL,
    fx_ars_usd REAL,
    market_cap_ars REAL,
    market_cap_usd REAL,
    shares_outstanding REAL,
    year_high REAL,
    year_low REAL,
    fuente TEXT DEFAULT 'yfinance',
    UNIQUE(empresa_id, fecha)
);
```

### 10.3 Relaciones Clave

```
empresa_master 1──N eeff_unified      (una empresa, muchos períodos)
empresa_master 1──N ratios_master     (una empresa, muchos años-fiscales)
empresa_master 1──N precios_byma      (una empresa, muchas fechas)
empresa_master 1──1 ticker_map        (mapeo ticker→CIK→cuit)
empresa_master 1──N source_heartbeat  (estado de cada fuente)
```

### 10.4 Mapeo de CIK Actual a Nuevo Modelo

| Tabla Actual | CIK usado | Problema | Solución |
|---|---|---|---|
| `facts` (EDGAR) | `00000XXXXX` (10 dígitos) | OK | Mapear a empresa_master.cik_edgar |
| `facts` (YF BYMA) | `BYMA-TICKER` | No es CIK real | Mapear a empresa_master.cik_byma |
| `cnv_estados` | ticker directo | Inconsistente | Vincular via ticker_byma |
| `empresas` | `BYMA-TICKER` | Mix de ambos | Migrar a empresa_master |
| `ratios` | CIK EDGAR | Solo ADRs | Expandir a todas las empresas |

---

## 11. Principales Debilidades

| # | Debilidad | Impacto | Prioridad |
|---|---|---|---|
| D1 | **`period_end="latest"`** en 6/7 empresas CNV AIF2 | Imposible análisis temporal | **Crítica** |
| D2 | **Dos tablas financieras desconectadas** (`cnv_estados` + `facts`) | No se puede consultar unified | **Crítica** |
| D3 | **Sin precios BYMA para 56 empresas** | No se puede calcular PER, P/BV, Market Cap | **Alta** |
| D4 | **Ratios calculados solo para 7 ADRs** | 49 empresas sin ratios | **Alta** |
| D5 | **Solo 5 años históricos** (2021-2025) | No permite análisis de ciclos largos | Media |
| D6 | **Sin Current/NonCurrent en YF** | No hay ratios de liquidez para 49 empresas | Media |
| D7 | **Universo fragmentado** (19 vs 56) | Confusión sobre qué es "solo-byma" | Media |
| D8 | **`cnv_estados` con datos incompletos** | 7 empresas con 33-36 concepts, pero 7 con 3-10 | Media |
| D9 | **Sin heartbeat de fuentes** | No se sabe cuándo se actualizó cada fuente | Baja |
| D10 | **`descargas_log` vacía** | Sin trazabilidad de errores | Baja |

---

## 12. Principales Fortalezas

| # | Fortaleza | Valor |
|---|---|---|
| F1 | **Cobertura 100% del universo BYMA vía YFinance** | 56 empresas con 5 años de datos es una base sólida |
| F2 | **Datos estandarizados** | YFinance usa nomenclatura consistente en todas las empresas |
| F3 | **254 tags únicos** | Riqueza conceptual comparable a proveedores internacionales |
| F4 | **4.6M datapoints en EDGAR** | Base para expandir a ADRs, CEDEARs, S&P 500 |
| F5 | **Pipeline CNV AIF2 funcional** | Para 7 empresas con datos detallados de balance |
| F6 | **`links_eeff_refined.csv` (18,492 EEFF)** | Catálogo de presentaciones CNV listo para extracción masiva |
| F7 | **Infraestructura de base de datos operativa** | SQLite funcional con esquema extensible |
| F8 | **Pipeline GRIM demostrado** | Prueba de concepto de pipeline completo (discovery → ratio → dashboard) |

---

## 13. Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | **YFinance deja de funcionar para BYMA** | Media | Alto | Tener CNV AIF2 como backup para los 7 principales |
| R2 | **Datos YFinance no auditables** | Alta | Medio | Cross-validate con CNV para las 7 empresas que tienen ambas fuentes |
| R3 | **Inflación Argentina distorsiona ratios** | Alta | Alto | Usar estado de reexpresión (RECPAM) de CNV; YF no ajusta por inflación |
| R4 | **CNV AIF2 cambia formato HTML** | Media | Alto | Monitoreo heartbeat; parser con tests automáticos |
| R5 | **CIK inconsistencies** | Alta | Medio | Script de reconciliación; tabla de mapeo explícita |
| R6 | **Escala no normalizada** | Media | Medio | Detectar automáticamente (miles/millones) y normalizar |
| R7 | **Empresas cambian de nombre/ticker** | Baja | Medio | Historial en empresa_master; detección fuzzy |

---

## 14. Oportunidades de Mejora

| # | Oportunidad | Beneficio | Esfuerzo |
|---|---|---|---|
| O1 | **Extraer AIF2 multi-año para 56 empresas** | Ratios históricos 5y+ vía CNV (incluye Current Assets) | 2 semanas |
| O2 | **Integrar precios BYMA vía yfinance** | Dashboard completo para 56 empresas | 1 día |
| O3 | **Pipeline unificado YF + CNV + precios** | Una sola consulta para todos los datos | 1 semana |
| O4 | **Calcular ratios para las 56 empresas** | Cobertura 100% de ratios | 2 días |
| O5 | **Cross-validate YF vs CNV** | Calidad y confianza en los datos | 1 semana |
| O6 | **Extender CNV AIF2 a formTypeId=349** | Cubrir GCLA y otras empresas | 3-5 días |
| O7 | **Agregar precios históricos diarios** | Series de tiempo, backtesting | 1 semana |
| O8 | **Dashboard web interactivo** | Visualización en tiempo real | 2-3 semanas |

---

## 15. Roadmap de Evolución

### Fase 1: Quick Wins (1-2 días)

| # | Acción | Beneficio |
|---|---|---|
| 1.1 | Corregir `period_end="latest"` → fecha real en cnv_estados | Base para análisis temporal |
| 1.2 | Agregar precios BYMA (YF `TICKER.BA`) para 56 empresas | PER, P/BV, Market Cap |
| 1.3 | Calcular ratios para las 56 empresas en tabla `ratios_master` | Dashboard completo |
| 1.4 | Definir la lista definitiva de 56 empresas como SSOT | Eliminar ambigüedad |

### Fase 2: Unificación de Datos (1 semana)

| # | Acción | Complejidad |
|---|---|---|
| 2.1 | Crear `empresa_master` y migrar datos | Media |
| 2.2 | Normalizar `eeff_unified` desde `facts` (YF BYMA) + `cnv_estados` | Alta |
| 2.3 | Vincular CIK byma_yf con ticker_ppal | Baja |
| 2.4 | Pipeline de carga de precios BYMA | Media |

### Fase 3: Extracción Masiva CNV (2-3 semanas)

| # | Acción | Complejidad |
|---|---|---|
| 3.1 | Extraer AIF2 multi-año (formTypeId=147) para todas las empresas disponibles | Media |
| 3.2 | Extender parser a formTypeId=349 (Controladas) | Alta |
| 3.3 | Cargar datos CNV a `eeff_unified` | Media |
| 3.4 | Cross-validation YF vs CNV para empresas superpuestas | Media |

### Fase 4: Pipeline Automatizado (1-2 semanas)

| # | Acción | Complejidad |
|---|---|---|
| 4.1 | Heartbeat de fuentes (CNV, YF, EDGAR) | Media |
| 4.2 | Actualización programada (semanal para CNV, diaria para precios) | Media |
| 4.3 | Alertas de cambios/drift en fuentes | Alta |
| 4.4 | Dashboard de monitoreo de datos | Alta |

### Fase 5: Dashboard y Consumo (2-4 semanas)

| # | Acción | Complejidad |
|---|---|---|
| 5.1 | Dashboard Seguimiento.xlsx para todas las 56 empresas | Media |
| 5.2 | Dashboard web interactivo | Alta |
| 5.3 | API de consulta REST | Alta |
| 5.4 | Alertas de valorización (PER < X, ROE > Y) | Alta |

---

## Anexo A: Lista Completa de 56 Empresas Only-BYMA

| # | Ticker | Empresa | Tags YF | Períodos | Fuente CNV |
|---|---|---|---|---|---|
| 1 | A3 | A3 Mercados | 183 | 5 | IR (9 conc.) |
| 2 | AGRO | Agrometal | 143 | 5 | - |
| 3 | ALUA | Aluar Aluminio Argentino | 161 | 5 | AIF2 (36 conc.) |
| 4 | AUSO | Autopistas del Sol | 142 | 5 | - |
| 5 | BHIP | Banco Hipotecario | 121 | 5 | - |
| 6 | BOLT | Boldt | 175 | 5 | IR (9 conc.) |
| 7 | BPAT | Banco Patagonia | 122 | 5 | - |
| 8 | BYMA | Bolsas y Mercados Argentinos | 160 | 5 | IR (10 conc.) |
| 9 | CADO | Carlos Casado | 138 | 5 | - |
| 10 | CAPX | Capex | 167 | 4 | - |
| 11 | CARC | Carboclor | 126 | 4 | - |
| 12 | CECO2 | Endesa Costanera | 158 | 4 | - |
| 13 | CELU | Celulosa Argentina | 170 | 3 | - |
| 14 | CGPA2 | Camuzzi Gas Pampeana | 167 | 5 | - |
| 15 | COME | Soc. Comercial del Plata | 176 | 5 | - |
| 16 | COUR | Continental Urbana | 162 | 5 | - |
| 17 | CTIO | Consultatio | 172 | 5 | IR (8 conc.) |
| 18 | CVH | Cablevisión Holding | 188 | 5 | AIF2 (36 conc.) |
| 19 | DGCE | Distr. Gas del Centro | 142 | 3 | - |
| 20 | DGCU2 | Distr. Gas Cuyana | 155 | 5 | - |
| 21 | DOME | Domec | 132 | 4 | - |
| 22 | ECOG | Ecogas Inversiones | 155 | 2 | - |
| 23 | EDSH | EDESA Holding | 162 | 5 | - |
| 24 | FERR | Ferrum | 161 | 5 | - |
| 25 | FIPL | Fiplasto | 163 | 5 | - |
| 26 | GAMI | B-Gaming | 155 | 5 | IR (9 conc.) |
| 27 | GARO | Garovaglio y Zorraquin | 151 | 5 | - |
| 28 | GBAN | Gas Natural Ban | 157 | 5 | AIF2 (34 conc.) |
| 29 | GCDI | GCDI | 165 | 5 | - |
| 30 | GCLA | Grupo Clarín | 187 | 5 | - |
| 31 | GRIM | Grimoldi | 160 | 5 | (pipeline demo) |
| 32 | HARG | Holcim Argentina | 168 | 5 | - |
| 33 | HAVA | Havanna Holding | 174 | 5 | - |
| 34 | INTR | Introductora Bs As | 166 | 5 | - |
| 35 | INVJ | Inversora Juramento | 158 | 3 | - |
| 36 | LEDE | Ledesma | 158 | 4 | AIF2 (35 conc.) |
| 37 | LONG | Longvie | 153 | 5 | - |
| 38 | METR | Metrogas | 164 | 5 | AIF2 (33 conc.) |
| 39 | MIRG | Mirgor | 190 | 5 | - |
| 40 | MOLA | Molinos Agro | 159 | 5 | AIF2 (35 conc.) |
| 41 | MOLI | Molinos Rio de la Plata | 170 | 5 | - |
| 42 | MORI | Morixe | 159 | 4 | - |
| 43 | OEST | Gpo. Concesionario Oeste | 152 | 5 | - |
| 44 | PATA | Imp. y Exp. Patagonia | 178 | 5 | - |
| 45 | POLL | Polledo | 106 | 5 | - |
| 46 | RAGH | RAGHSA | 142 | 3 | - |
| 47 | REGE | Garcia Reguera | 134 | 5 | - |
| 48 | RICH | Laboratorios Richmond | 178 | 5 | - |
| 49 | RIGO | Rigolleau | 145 | 4 | - |
| 50 | ROSE | Instituto Rosenbusch | 142 | 5 | - |
| 51 | SAMI | San Miguel | 169 | 5 | - |
| 52 | SEMI | Molinos Juan Semino | 147 | 4 | - |
| 53 | TGNO4 | Transp. Gas del Norte | 164 | 5 | - |
| 54 | TRAN | Transener | 152 | 5 | AIF2 (34 conc.) |
| 55 | TXAR | Ternium Argentina | 164 | 5 | - |
| 56 | VALO | Banco de Valores | 151 | 5 | - |

---

## Anexo B: Mapeo YFinance Tags → Categorías IFRS

*(Disponible completo en el script de análisis, 254 tags clasificados)*

---

*Documento generado el 28 Junio 2026 como parte de la auditoría técnica de Catalaxia Finance.*
