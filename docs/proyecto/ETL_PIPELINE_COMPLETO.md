# Pipeline ETL Completo — 3 Grupos de Empresas

**Documento:** Guía técnica de extracción, transformación y carga de datos financieros  
**Versión:** 2.0  
**Fecha:** 2026-08-09  
**Scope:** S&P 500 (EDGAR) + ADR argentinos (EDGAR 20-F + CNV) + BYMA-only (CNV + yfinance)  
**Universo:** 572 empresas | 3 mercados | 2 monedas (USD/ARS)

---

## 📋 ÍNDICE

1. [Visión General](#1-visión-general)
2. [Grupo 1: S&P 500 (EDGAR)](#2-grupo-1-sp500-edgar)
3. [Grupo 2: ADR Argentinos (EDGAR 20-F + CNV)](#3-grupo-2-adr-argentinos)
4. [Grupo 3: BYMA-only (CNV + yfinance)](#4-grupo-3-byma-only)
5. [Convergencia: Screener Unificado](#5-convergencia-screener-unificado)
6. [Matriz de Validaciones](#6-matriz-de-validaciones)
7. [Gestión de Errores](#7-gestión-de-errores)
8. [Guía para Usuario Final](#8-guía-para-usuario-final)

---

## 1. Visión General

### 1.1 Arquitectura ETL

```
┌─────────────────────────────────────────────────────┐
│           EXTRACT (Fuentes Crudas)                  │
├─────────────────────────────────────────────────────┤
│  SEC EDGAR         │   CNV AIF2         │ yfinance  │
│  (500 S&P + 16 ADR)│ (56 BYMA-only)     │ (precios) │
└─────┬───────────────┴────────┬──────────┴─────┬─────┘
      │                        │                │
      ▼                        ▼                ▼
┌──────────────────────────────────────────────────────┐
│     TRANSFORM (Conceptos Canónicos)                 │
├──────────────────────────────────────────────────────┤
│  • NetIncome, Revenue, Assets, Equity, Deuda, EBITDA│
│  • Normalización de unidades (USD, ARS, pesos base) │
│  • Cálculo de ratios (ROE, ROA, Margen, EPS, etc.)  │
│  • Deflación IPC (CAGR real para BYMA)              │
│  • Validación de identidad contable (A=P+PN)        │
└───────┬──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│    LOAD (PostgreSQL / Tabla `screener`)             │
├──────────────────────────────────────────────────────┤
│  572 empresas × 26 ratios + flags + provenance      │
└──────────────────────────────────────────────────────┘
```

### 1.2 Principios Clave

| Principio | Significado | Por qué importa |
|-----------|------------|-----------------|
| **Flag > Fabricate** | Marcar datos dudosos, nunca inventar | Honestidad = confianza |
| **Conceptos Canónicos** | Un motor de ratios para 3 fuentes | Comparabilidad |
| **Provenance** | Trackear quién dijo qué | Reproducibilidad |
| **Resume-Safe** | Si falla, continúa de donde quedó | Eficiencia en re-runs |
| **Identidad Contable** | A = P + PN siempre | Validez estructural |

---

## 2. GRUPO 1: S&P 500 (EDGAR)

### 2.1 Obtención de Datos (Paso a Paso)

#### **Paso 1: Descubrimiento de CIKs**

```bash
Script: 01_mapear_cik.py
Entrada: None (manual: lista de tickers S&P 500)
Salida: archivo CIK_TICKER_MAP.csv

Acciones:
  1. Obtener lista oficial S&P 500 (ej. de SPY holdings)
  2. Mapear ticker → CIK (via SEC EDGAR index)
  3. Validar que cada ticker tiene CIK único
  4. Guardar en CSV para auditar
```

**Datos obtenidos:**
- Ticker (AAPL, MSFT, etc.)
- CIK (0000000320 = Apple)
- Company name (APPLE INC)
- SIC code (industria)

**Validaciones en este paso:**
- ✅ CIK ≠ null (todas las S&P están en EDGAR)
- ✅ CIK único por ticker (no duplicados)
- ✅ Todos tienen filing reciente (≤1 año)

---

#### **Paso 2: Descargar companyfacts XBRL**

```bash
Script: 02_descargar_datos.py
Entrada: CIK_TICKER_MAP.csv
Salida: data/raw/companyfacts/{cik}.json (1 por empresa)
Rate limit: 1 request/segundo (SEC recomienda ≤10/segundo)

Acciones:
  1. Para cada CIK en el mapeo:
     a. GET https://data.sec.gov/api/xbrl/companyfacts/CIK/{cik}.json
     b. Guardar JSON crudo (backup para auditoría)
     c. Registrar timestamp de descarga
     d. Si falla (404, 500): reintentar 3x con backoff exponencial
  2. Esperar 1 segundo entre requests
  3. Registrar en log: cik, timestamp, bytes_descargados, http_status
```

**Datos obtenidos por empresa:**
```json
{
  "cik": 320,
  "entityName": "Apple Inc",
  "facts": {
    "us-gaap": {
      "NetIncomeLoss": [
        {
          "accn": "0000320193-24-000013",  // filing accession
          "filed": "2024-01-30",           // fecha filing
          "period": "CY2023Q4",            // periodo fiscal
          "fy": 2023,
          "fp": "FY",
          "form": "10-K",
          "units": "USD",
          "value": 96995000000             // 96.9B en USD
        }
      ],
      "Assets": [...],
      "Liabilities": [...],
      ...
    }
  }
}
```

**Validaciones en este paso:**
- ✅ HTTP 200 (filing descargado)
- ✅ JSON válido (parseable)
- ✅ Contiene al menos 1 concepto de facts (NetIncome, Assets, etc.)
- ✅ Timestamp del filing ≤ 1 año (dato reciente)
- ❌ Si falla: registrar en `data/log_descarga_fallos.txt` y continuar (resume-safe)

**Errores posibles:**
- **404 Not Found**: empresa retirada de EDGAR → Flag `dato_desactualizado=1`
- **Timeout (429)**: rate limit de SEC → Backoff exponencial (esperar 5-60s)
- **JSON malformado**: error de SEC → Reintentar 1x, si falla → skip + log

---

#### **Paso 3: Parsear XBRL → Conceptos Canónicos**

```bash
Script: calcular_ratios_base.py (FASE 1: parseo)
Entrada: data/raw/companyfacts/{cik}.json
Salida: tabla `facts` en screener.db

Acciones:
  1. Para cada filing (10-K, 10-Q) del company facts JSON:
     a. Extraer XBRL tag (ej. "NetIncomeLoss")
     b. Mapear a concepto canónico (ej. "NetIncome")
     c. Leer periodo (CY2023Q4 → 2023-12-31 fiscal year-end)
     d. Leer valor en USD
     e. Guardar en tabla `facts`:
        (cik, concepto, period_end, valor, filing_accn, filing_date)

  2. Manejar contextos XBRL (fiscal_year, quarter):
     - CY2023Q4 = 31-dic-2023 (cierre anual)
     - CY2023Q3 = 30-sep-2023 (Q3)
     - Respetar la fecha oficial del SEC

  3. Validar continuidad temporal:
     - 10-K: 1x/año (cierre fiscal)
     - 10-Q: hasta 3x/año (trimestral, excepto Q4 cubierto por 10-K)
```

**Mapeo de XBRL tags → Conceptos canónicos:**

| Tag XBRL | Concepto Canónico | Línea P&L | Ejemplo (Apple 2023) |
|----------|------------------|----------|---------------------|
| NetIncomeLoss | NetIncome | Ingreso Neto | 96,995M USD |
| Revenues | Revenue | Ingresos | 394,328M USD |
| Assets | Assets | Activos | 352,755M USD |
| StockholdersEquity | Equity | Patrimonio | 74,544M USD |
| LiabilitiesCurrent + DebtNoncurrent | Deuda | Deuda Total | 106,146M USD |
| EBITDA | EBITDA | EBIT + DA | (no siempre en XBRL) |
| OperatingCashFlow | CF_Operativo | Cash Flow Op | 110,543M USD |
| CapitalExpenditures | CF_Inversión | CapEx | -10,949M USD |
| EarningsPerShareBasic | EPS_basico | EPS | 6.05 USD/acción |

**Validaciones en este paso:**
- ✅ Concepto mapeado (existe en diccionario XBRL)
- ✅ Valor numérico válido (no null, no "N/A")
- ✅ Periodo único por filing (no duplicados same-period)
- ✅ Moneda = USD (todas las S&P reportan en USD)
- ⚠️ Si EBITDA = null → se intenta calcular como EBIT + DA (si existen)

**Errores posibles:**
- **EBITDA faltante**: algunas empresas no lo reportan → Calcular = OperatingIncome + DA
- **Periodo ambiguo**: contextos múltiples en XBRL → Tomar el más reciente
- **Valor negativo sorpresa**: NetIncome < 0 (empresa con pérdidas) → ✅ OK, es válido
- **Unidades inconsistentes**: algunos tags en millones, otros en unidades → Normalizar todas a 1

---

#### **Paso 4: Descargar Precios (yfinance)**

```bash
Script: precios_y_valuacion.py (FASE 1: precios)
Entrada: CIK_TICKER_MAP.csv
Salida: tabla `precios` en screener.db

Acciones:
  1. Para cada ticker S&P:
     a. Descargar desde yfinance
        - Precio actual (cierre último trading day)
        - Market cap (shares outstanding × precio)
        - Max 52w, Min 52w
        - Volume
        - Dividend yield
     b. Guardar en tabla `precios`:
        (ticker, fecha, precio, market_cap, year_high, year_low, currency)
  2. Esperar 0.1s entre requests (yfinance es rate-friendly)
  3. Si yfinance falla (ticker delisted): 
     - Intentar via Yahoo Finance web API
     - Si ambas fallan → flag `precio_faltante=1`, usar último precio conocido
```

**Datos obtenidos:**
```
ticker   | fecha      | precio | market_cap  | year_high | year_low | currency
---------|------------|--------|-------------|-----------|----------|----------
AAPL     | 2024-01-30 | 189.95 | 2,975.15B   | 199.62    | 124.17   | USD
MSFT     | 2024-01-30 | 378.91 | 2,827.30B   | 416.00    | 213.04   | USD
```

**Validaciones en este paso:**
- ✅ Precio > 0 (positivo)
- ✅ Market cap = shares × precio (coherencia)
- ✅ Min52w ≤ precio ≤ Max52w (no inversos)
- ✅ Fecha actual (≤ 1 día)
- ⚠️ Si precio = null → usar última cotización conocida + flag `dato_desactualizado`

**Errores posibles:**
- **yfinance timeout**: intentar 2x más, esperar 30s entre intentos
- **Ticker delisted**: no aparece en yfinance → Buscar en Yahoo Finance históricamente
- **Precio en otra moneda**: algunos ADR en yfinance están en ARS (para BYMA) → Verificar `currency`

---

### 2.2 Cálculo de Ratios

#### **Paso 5: Ensamblar y Calcular Ratios**

```bash
Script: calcular_ratios_base.py (FASE 2: ratios)
Entrada: tabla `facts` (EDGAR) + tabla `precios` (yfinance)
Salida: tabla `ratios` en screener.db

Acciones:
  1. Para cada empresa (CIK):
     a. Tomar último período fiscal (10-K más reciente)
     b. Extraer conceptos canónicos del período:
        - NetIncome, Revenue, Assets, Equity, Deuda, EBITDA
     c. Calcular ratios fundamentales:
        
        ROE = NetIncome / Equity
        ROA = NetIncome / Assets
        Margen Neto = NetIncome / Revenue
        DeudaEBITDA = DeudaTotalLT / EBITDA
        EPS = NetIncome / shares_outstanding (del XBRL)
        CAGR_EPS_5y = compound annual growth rate (últimos 5 años)
        FCF_CE = (CF_Operativo - CapEx) / (Equity + Deuda)
        
     d. Calcular valuación (usando precios yfinance):
        
        PER = Precio / EPS
        PriceBook = Precio / (Equity / shares)
        PriceSales = MarketCap / Revenue
        EV/EBITDA = (MarketCap + Deuda - Cash) / EBITDA
        
  2. Guardar en tabla `ratios`:
     (cik, ticker, nombre, fecha, ROE, ROA, MargenNeto, ..., fecha_calculo)
```

**Ejemplo: Apple 2023**

```
CIK: 320
Ticker: AAPL
Período: 2023-12-31 (10-K)

Conceptos (del XBRL):
  NetIncome = 96,995M USD
  Revenue = 394,328M USD
  Assets = 352,755M USD
  Equity = 74,544M USD
  Deuda = 106,146M USD (LT + ST)
  EBITDA = ~120,000M (aproximado, no siempre reportado)
  CF_Operativo = 110,543M USD
  CapEx = 10,949M USD
  shares_outstanding = 15,812M

Ratios calculados:
  ROE = 96,995 / 74,544 = 130.2% ⚠️ OUTLIER (equity reducida por buybacks)
  ROA = 96,995 / 352,755 = 27.5% ✅ OK
  Margen Neto = 96,995 / 394,328 = 24.6% ✅ ALTO (típico de tech)
  DeudaEBITDA = 106,146 / 120,000 = 0.88x ✅ OK
  EPS = 96,995 / 15,812 = 6.13 USD ✅ OK
  CAGR_EPS_5y = +12.3% (nominal USD) ✅ POSITIVO
  FCF_CE = (110,543 - 10,949) / (74,544 + 106,146) = 37.2% ✅ EXCELENTE

Valuación (precio yfinance: $189.95):
  PER = 189.95 / 6.13 = 31.0x ✅ OK (tech típico)
  PriceBook = 189.95 / (74,544 / 15,812) = 40.1x ⚠️ ALTO (equity baja)
  PriceSales = (189.95 × 15,812M) / 394,328 = 7.60x ✅ OK
  EV/EBITDA = (2,975B + 106B) / 120B = 25.7x ⚠️ ALTO pero acceptable
```

**Validaciones en este paso:**
- ✅ Conceptos presentes (si falta alguno → marcar con NULL + flag)
- ✅ Ratios en rango razonable (ver gates abajo)
- ⚠️ Si Equity ≤ 0 (buybacks excesivos) → ROE = NULL, flag `no_significativo=1`
- ⚠️ Si NetIncome ≤ 0 → PER = NULL, EPS marcado como "N/A"
- ⚠️ Si Revenue = 0 → Margen/P/S = NULL

**Gates de Rango (sane values):**

| Ratio | Rango OK | Fuera Rango | Acción |
|-------|----------|------------|--------|
| ROE | (-1, 1) | <-1 o >1 | Flag `no_significativo` |
| ROA | (-0.2, 0.2) | <-0.2 o >0.2 | Flag |
| Margen Neto | (-10, 10) | <-10 o >10 | Flag (si ×100%) |
| PER | (0, 500) | <0 o >500 | Flag, revisar EPS |
| P/B | (0, 50) | <0 o >50 | Flag |
| P/S | (0, 50) | <0 o >50 | Flag |
| Deuda/EBITDA | (0, 100) | >100 | Flag (altamente apalancada) |
| CAGR 5y | (-5, 5) | <-5 o >5 | Flag (posible restatement) |

---

### 2.3 Validaciones en S&P 500

#### **Validación 1: Continuidad Temporal**

```
Verificación: Cada empresa debe tener filing anual (10-K)
Regla: Entre dos 10-K consecutivos máximo 14 meses

Acción si falla:
  - Si gap > 14 meses → flag `dato_desactualizado=1`
  - Si falta 10-K reciente (> 2 años) → excluir de screener

Ejemplo:
  Apple:
    10-K 2023-12-31 → ok
    10-K 2022-12-31 → ok (1 año después)
    10-K 2021-12-31 → ok
  ✅ Pasa
```

#### **Validación 2: Identidad Contable (A = P + PN)**

```
Verificación: Assets ≈ Liabilities + Equity
Tolerancia: ≤ 1% de diferencia (rounding)

Cálculo:
  Diferencia = abs(Assets - (Liabilities + Equity)) / Assets
  
  Si Diferencia ≤ 0.01 → ✅ OK
  Si 0.01 < Diferencia ≤ 0.05 → ⚠️ REVISAR (marcar flag)
  Si Diferencia > 0.05 → ❌ SUSPECT (excluir o flag)

Ejemplo (Apple 2023):
  Assets = 352,755M
  Liabilities = 278,211M
  Equity = 74,544M
  Suma = 278,211 + 74,544 = 352,755M
  Diferencia = 0 / 352,755 = 0%
  ✅ Perfecto (XBRL está certificado)
```

#### **Validación 3: Series TTM (Trailing Twelve Months)**

```
Verificación: Para ratios como EPS y CF, usar TTM (últimos 12m)
Metodología: Sumar 10-Q trimestral + 10-K anual (evitar duplicates)

Ejemplo (Apple 2024 Q1):
  10-K 2023 (full year) = 96,995M USD
  10-Q Q1 2024 = +23,641M USD (Q1 alone)
  10-Q Q2 2024 = +24,079M USD (Q2 alone)
  10-Q Q3 2024 = +23,884M USD (Q3 alone)
  
  TTM = 96,995 - (2023 Q1) + (2024 Q1,Q2,Q3)
  (Restar Q1 2023, agregar Q1,Q2,Q3 2024)

Acción si falla:
  - Si TTM ambiguo → usar último 10-K (anual, menos volátil)
  - Marcar en provenance: "ttm_aproximado" vs "ttm_preciso"
```

---

### 2.4 Errores Posibles & Mitigación (S&P 500)

| Error | Causa | Detección | Mitigación |
|-------|-------|-----------|-----------|
| **XBRL tag no mapeado** | Empresa reporta tag no estándar | Tag ∉ conceptos canónicos | Usar fallback (ej. EBITDA = OI + DA) |
| **EPS diluido vs básico** | S&P reporta ambos | Verificar tag (EarningsPerShareBasic vs Diluted) | Usar básico (conservador) |
| **Cambio de moneda (ARS)** | Rara: empresa US debe reportar USD | currency ≠ USD en facts | Flag + investigar (posible ADR confundido) |
| **Restatement** | Empresa re-reporta números | Mismo periodo, diferentes valores en distintos filings | Tomar último filing (más reciente) |
| **Spin-off / Merger** | Empresa se divide o fusiona | Gap en series o discontinuidad de datos | Excluir período de transición |
| **Deuda a corto vs LP** | Clasificación inconsistente | ST ≠ LT en diferentes periodos | Usar suma total (ST + LT) |
| **Cálculo EBITDA** | No siempre reportado en XBRL | EBITDA = NULL | Calcular = OperatingIncome + DA |
| **PER infinito** | EPS = 0 o negativo | PER > 1000 | NULL + flag `no_significativo` |
| **Buyback agresivo** | Equity negativo por recompras | Equity ≤ 0 | ROE = NULL, P/B = NULL, flag |
| **Precio nulo** | yfinance no tiene precio reciente | Precio = NULL | Usar último conocido + `dato_desactualizado=1` |

---

## 3. GRUPO 2: ADR Argentinos

### 3.1 Obtención de Datos (Paso a Paso)

#### **Paso 1: Descubrimiento de ADRs**

```bash
Script: _search_adr.py
Entrada: CNV universe (~556 empresas)
Salida: lista_adr.csv (16 ADRs identificados)

Acciones:
  1. Buscar en CNV empresas que emiten ADR:
     - Criterio: nombre contiene "ADR" o ticker en NYSE
     - O: empresa argentina que cotiza en NYSE (ej. BMA)
  2. Cruzar con SEC EDGAR (buscar 20-F filing):
     - 20-F = formulario para emisores extranjeros
     - Debe contener indicador "Sí" para ADR
  3. Mapear ADR → acción ordinaria:
     - 1 ADR = N acciones ordinarias (ratio)
     - Ejemplo: BMA → 1 ADR = 10 acciones ordinarias
  4. Guardar en lista_adr.csv:
     (cuit, ticker, empresa, cik, adr_ticker, adr_ratio)
```

**ADRs identificados (~16):**

| Empresa | CUIT | Ticker BYMA | Ticker NYSE | CIK | ADR Ratio | Mercado |
|---------|------|-----------|-----------|-----|-----------|---------|
| Banco Macro | 30500010134 | BMA | BMA | 100908 | 10:1 | BYMA + NYSE |
| Pampa Energía | 30625004235 | PAM | PAM | 1373993 | 1:1 | BYMA + NYSE |
| Telecom Argentina | 30546170098 | TECO2 | TECO | 1052698 | 1:1 | BYMA + NYSE |
| YPF | 30546076432 | YPF | YPF | 1106667 | 1:1 | BYMA + NYSE |
| ...y 12 más | ... | ... | ... | ... | ... | ... |

**Validaciones en este paso:**
- ✅ Empresa existe en CNV (CUIT válido)
- ✅ Empresa existe en SEC (CIK válido, 20-F filing)
- ✅ ADR ratio > 0 (coherencia)
- ✅ Ticker NYSE válido (cotiza en NYSE)

---

#### **Paso 2: Descargar datos EDGAR (20-F)**

```bash
Script: (mismo 02_descargar_datos.py, pero filtrado a 20-F)
Entrada: lista_adr.csv (CIKs de ADRs)
Salida: data/raw/companyfacts/{cik}.json (igual que S&P)

Acciones:
  1. Para cada CIK ADR:
     a. GET https://data.sec.gov/api/xbrl/companyfacts/CIK/{cik}.json
     b. Parsear facts (mismo que S&P, pero moneda puede ser ARS o USD)
     c. Guardar JSON crudo
  2. Esperar 1 segundo entre requests
  3. Registrar en log
```

**Particularidades de 20-F:**
- Moneda: Generalmente USD (pero algunos reportan ARS)
- Período fiscal: Puede no coincidir con calendario (ej. cierre junio)
- Conceptos: Similar a 10-K (NetIncome, Assets, etc.)
- DR level: Información del ADR (I/II/III) en documento de 20-F

**Validaciones en este paso:**
- ✅ HTTP 200 + JSON válido
- ✅ Contiene concepto 20-F (no confundir con otro tipo de filing)
- ✅ Moneda consistente (USD o ARS, pero no mezcla)
- ✅ Período reciente (≤ 1 año)

---

#### **Paso 3: Extraer Ratios ADR Oficiales (F-6)**

```bash
Script: sec_adr_ratios.py
Entrada: SEC EDGAR para cada ADR
Salida: tabla `adr_ratios` (ratios oficiales del ADR)

Acciones:
  1. Para cada ADR:
     a. Buscar formulario F-6 (registration statement)
     b. Extraer campos:
        - DR level (I/II/III): nivel de operación del ADR
        - Ratio ADR:Ord (ej. 1:10 = 1 ADR = 10 acciones)
        - Banco custodia (ej. BNY Mellon)
        - Dividendos históricos
  2. Guardar en tabla adr_ratios:
     (cik, adr_ticker, dr_level, adr_ratio, cusip, dividend_history)
```

**Ejemplo: Banco Macro**

```
CIK: 100908
Ticker NYSE: BMA
F-6 Info:
  DR Level: II (Sponsored ADR, unrestricted trading)
  ADR Ratio: 10 acciones ordinarias = 1 ADR
  CUSIP: 06367120
  Banco Custodia: BNY Mellon
  Dividendos últimos 5 años: [0.50, 0.60, 0.75, 0.90, 1.00] USD/ADR
```

**Validaciones:**
- ✅ ADR ratio > 0 (positivo)
- ✅ DR level ∈ {I, II, III} (válido)
- ✅ CUSIP de 9 dígitos (formato SEC)
- ✅ Dividendos en USD (moneda correcta para ADR)

---

#### **Paso 4: Descargar Datos CNV (BYMA)**

```bash
Script: job5_v2_extract_eeff.py (FASE: ADR)
Entrada: CUIT de ADRs (desde lista_adr.csv)
Salida: tabla `cnv_estados_v2` (BYMA-side data)

Acciones:
  1. Para cada ADR, usar CUIT para bajar de CNV:
     a. job1, job2, job3, job4 → descubrir GUIDs
     b. job5_v2 → extraer estados contables ARS
  2. Normalizar moneda:
     - EDGAR data en USD
     - CNV data en ARS
     - Cruzar con CCL (dolar contado con liqui)
  3. Guardar ambas fuentes:
     - ratios TABLE (EDGAR, USD)
     - cnv_estados_v2 TABLE (CNV, ARS)
```

**Particularidad:** Los ADRs tienen **doble validación**
- EDGAR (oficial para NYSE)
- CNV (oficial para BYMA)

Si ambas fuentes existen, cruzarlas para validar consistencia.

---

#### **Paso 5: Unificar ADR = EDGAR + CNV**

```bash
Script: s6_ajustes.py (sección: usar_edgar_para_adr)
Entrada: ratios TABLE (EDGAR) + cnv_estados_v2 TABLE (CNV)
Salida: screener TABLE con ADRs

Acciones:
  1. Para cada ADR:
     a. Tomar ratios EDGAR (USD, oficial)
     b. Si CNV existe: cruzar validaciones
        - ROE EDGAR vs ROE CNV → diferencia ≤ 10% OK
        - Si ≠: investigar (posible restatement o timing)
     c. Precios:
        - Precio NYSE (USD) de yfinance
        - Precio BYMA (ARS) de yfinance
        - Calcular CCL = (precio_ARS × adr_ratio) / precio_USD
     d. Guardar en screener:
        (cuit, ticker_byma, ticker_nyse, ratios_edgar_usd, precio_usd, precio_ars, ccl)
```

**Ejemplo: BMA (Banco Macro)**

```
EDGAR Data (USD):
  ROE = 18.2%
  ROA = 2.3%
  Margen Neto = 15.6%
  EPS = 1.85 USD
  Período: 2023-12-31

CNV Data (ARS):
  ROE = 18.1% (casi igual, OK ✅)
  ROA = 2.4% (casi igual, OK ✅)
  Margen Neto = 15.4% (casi igual, OK ✅)
  EPS = 28.50 ARS (= 1.85 USD × 15.41 ARS/USD, OK ✅)
  Período: 2023-12-31

Precios:
  NYSE BMA: $10.25 USD (2024-01-30)
  BYMA BMA: $155.00 ARS (2024-01-30)
  
  CCL = (155.00 × 10) / 10.25 = 151.2 ARS/USD
  (Comparar vs MEP actual ≈ 150 ARS/USD: OK ✅)

Ratios en screener (post-s6):
  ROE = 18.2% (EDGAR)
  PER = 10.25 / 1.85 = 5.54x (EDGAR, USD)
  Precio BYMA = 155.00 ARS
  Precio NYC = 10.25 USD
  CCL = 151.2 ARS/USD
```

---

### 3.2 Validaciones en ADRs

#### **Validación 1: Cruce EDGAR vs CNV**

```
Para cada ADR, comparar ratios calculados de ambas fuentes:

Criterio: Diferencia relativa ≤ 10% (tolerancia por timing/reexpresión)

ROE_EDGAR = 18.2%
ROE_CNV = 18.1%
Diferencia = abs(18.2 - 18.1) / 18.2 = 0.5% ✅ OK

Si diferencia > 10%:
  1. Revisar fechas (¿mismo period_end?)
  2. Revisar conversión ARS/USD (posible error)
  3. Revisar si hay restatement (empresa re-reportó números)
  4. Flag: `fuente_discrepancia` + investigar manualmente
```

#### **Validación 2: CCL (Contado Con Liquidación)**

```
Validación: Precio BYMA (ARS) debe ser consistente con NYSE (USD)

CCL derivado = (precio_BYMA_ARS × adr_ratio) / precio_NYSE_USD

Ejemplo válido:
  BMA BYMA = 155 ARS
  BMA NYSE = 10.25 USD
  Ratio = 10:1
  
  CCL = (155 × 10) / 10.25 = 151.22 ARS/USD
  
  Comparar vs CCL mercado ≈ 150-152 ARS/USD ✅ OK

Si CCL derivado ≠ mercado:
  1. Verificar precios (¿datos frescos?)
  2. Revisar ratio ADR (¿correcto?)
  3. Posible desfase horario (NYSE cierra antes que BYMA)
  4. Flag: `ccl_inconsistente` si diferencia > 3%
```

#### **Validación 3: Consistencia de Precios**

```
Regla: Precio BYMA / Precio NYSE ≈ CCL

Fórmula: ratio_precio = precio_BYMA_ARS / (precio_NYSE_USD × adr_ratio)

Esperado: ratio_precio ≈ CCL ± 1%

Ejemplo:
  BMA: 155 ARS / (10.25 USD × 10) = 1.512 × 100 = 151.2 ARS/USD
  CCL mercado: 150.5 ARS/USD
  
  Diferencia: (151.2 - 150.5) / 150.5 = 0.46% ✅ OK

Si diferencia > 3%:
  Flag: `precio_incongruente`
  Acción: Revisar si hay restricciones (ej. dividend ex-date)
```

---

### 3.3 Errores Posibles & Mitigación (ADRs)

| Error | Causa | Detección | Mitigación |
|-------|-------|-----------|-----------|
| **ROE EDGAR ≠ CNV** | Timing (fechas ≠) o restatement | Diferencia > 10% | Flag, usar EDGAR (oficial) |
| **Moneda mixta** | EDGAR reporta USD, CNV reporta ARS | Comparar monedas en facts | Normalizar a USD para EDGAR, ARS para CNV |
| **Precio NYSE stale** | yfinance desactualizado | Fecha ≤ 1 semana atrás | Flag `dato_desactualizado` |
| **ADR ratio incorrecto** | Cambio histórico de ratio | ratio ≠ actual | Verificar fecha (historiacal ratio changes) |
| **CCL divergente** | Cierre en horarios distintos | CCL > mercado × 5% | Flag, revisar timestamp de precios |
| **Dividendo pendiente** | Ex-date reciente | Precio BYMA bajo vs USD | Esperar normalización post-ex-date |
| **Empresa delisted NYSE** | ADR retirado de NYSE | HTTP 404 en EDGAR | Marcar como `dato_desactualizado`, usar solo CNV |
| **CIK no encontrado** | Error en mapeo CIK | No hay companyfacts en SEC | Revisar mapeo, posible spin-off |

---

## 4. GRUPO 3: BYMA-only

### 4.1 Obtención de Datos (Paso a Paso)

#### **Paso 1: Descubrimiento (Job 1-4)**

```bash
Scripts: job1_universo.py → job2_download.py → job3_formtype.py → job4_clasificar.py

FASE 1: Discovery (offline, cacheable)

Job 1: job1_universo.py
  Entrada: None
  Salida: datos/empresas_556.csv
  
  Acciones:
    1. GET https://aif2.cnv.gov.ar/SitioWeb/Empresas/AutoComplete
    2. Parsear JSON de empresas registradas (≈556)
    3. Extraer: CUIT, nombre, URL company page
    4. Guardar en CSV

Job 2: job2_download.py
  Entrada: empresas_556.csv
  Salida: datos/html_descargados/{cuit}.html (company pages)
  
  Acciones:
    1. Para cada CUIT en universo:
       a. GET https://aif2.cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT}
       b. Guardar HTML crudo (backup)
       c. Esperar 1-2 seg entre requests (rate limit CNV)
       d. Registrar en log: cuit, timestamp, bytes, http_status
    2. Resume-safe: saltear CUIT ya descargado
    
  Rate limits:
    - CNV responde 2-5 segundos por request
    - No bloquea si respetas límite
    - default: 1 req/seg, --sleep 0.3-1.0s

Job 3: job3_formtype.py
  Entrada: datos/html_descargados/*.html
  Salida: datos/guid_formtype.csv
  
  Acciones:
    1. Para cada HTML descargado:
       a. Parsear acordeón (tabla con GUIDs)
       b. Extraer por tipo de formulario:
          - "Estados Contables" → EEFF (codes: 147, 349, 487, 142, 488, 1001, 1002)
          - "Pago de Dividendos" → DIV (codes: 339)
          - "Hechos Relevantes" → HR (codes: 244, 1007, 198)
          - "Actas de Asambleas" → ASM (codes: 334, 1006)
       c. Guardar: guid, cuit, formtype_id, formtype_name, periodo
    2. Offline: no hace requests a CNV

Job 4: job4_clasificar.py
  Entrada: guid_formtype.csv
  Salida: 
    - datos/whitelist_eeff.csv (GUIDs estados contables)
    - datos/whitelist_div.csv (GUIDs dividendos)
    - datos/tabla_maestra.csv (1 fila/empresa con conteos)
  
  Acciones:
    1. Filtrar GUIDs por tipo:
       - EEFF: codes ∈ {147, 349, 487, 142, 488, 1001, 1002}
       - DIV: codes ∈ {339, 244, 1007, 198, 334, 1006}
    2. Crear tabla_maestra:
       cuit | empresa | num_eeff | num_div | num_hr | cotiza_byma | cotiza_nyse
    3. Filtrar solo BYMA-only (cotiza_byma=1, cotiza_nyse=0)
```

**Salidas de Discovery:**

```
empresas_556.csv:
  30546076432, YPF SA, https://aif2.cnv.gov.ar/.../30546076432
  30625004235, PAMPA ENERGIA SA, ...
  30711204055, 360 ENERGY SOLAR SA, ...
  (etc, 556 empresas)

guid_formtype.csv (muestra):
  90123456, 30546076432, 147, Estados Contables, 2023-12-31
  90123457, 30546076432, 147, Estados Contables, 2022-12-31
  90123458, 30546076432, 339, Pago de Dividendos, 2024-01-15

whitelist_eeff.csv:
  90123456, 30546076432, YPF, 2023-12-31
  90123457, 30546076432, YPF, 2022-12-31
  (etc, ~3000 GUIDs de EEFF)

tabla_maestra.csv:
  30546076432, YPF SA, 15, 8, 3, 1, 1  (cotiza BYMA y NYSE)
  30625004235, PAMPA, 14, 6, 2, 1, 1  (cotiza BYMA y NYSE)
  30711204055, 360 ENERGY, 5, 1, 0, 0, 0  (solo BYMA? revisar)
```

**Validaciones en Discovery:**
- ✅ AutoComplete devuelve ≈556 empresas (completo)
- ✅ Company pages parsean sin error (HTML válido)
- ✅ GUIDs únicos por empresa-formtype-periodo
- ✅ Formulario types reconocidos (codes ∈ catálogo CNV)
- ⚠️ Si HTML no parsa → flag `parse_error`, skip empresa

**Errores posibles:**
- **AutoComplete devuelve < 500** → Posible outage CNV, reintentar
- **Company page con 0 GUIDs** → Empresa sin filings recientes, OK (inactiva)
- **HTML corrupto** → Reintentar descarga (resume-safe), si falla nuevamente skip
- **GUIDs duplicados** → Investigar (posible resubmisión), usar más reciente

---

#### **Paso 2: Extracción de Estados Contables (Job 5 v2)**

```bash
Script: job5_v2_extract_eeff.py
Entrada: whitelist_eeff.csv (GUIDs de estados contables)
Salida: tabla `cnv_estados_v2` en screener.db

Acciones:
  1. Para cada GUID en whitelist_eeff:
     a. GET https://aif2.cnv.gov.ar/presentations/publicview/{GUID}
     b. Parsear HTML de presentación AIF2:
        i. Extraer tabla de datos
        ii. Mapear códigos de concepto (7 dígitos)
        iii. Leer UnidadMedida (MILES / MILLONES)
        iv. Leer fecha_reexpresion (fecha NIC-29)
        v. Guardar HTML crudo en eeff/eeff_html/{guid}.html (nunca re-bajar)
     c. Normalizar valores:
        factor_unidad() = {
          si "millon" → ×1,000,000
          si "mil" → ×1,000
          si otro → ×1
        }
     d. Guardar en tabla cnv_estados_v2:
        (cuit, empresa, concepto, valor, periodo, unidad_raw, factor, valor_normalizado)
     e. Marcar como "hecho" en log_job5_v2_done.txt (resume-safe)
  2. Rate limiting: 0.3-1s entre requests
  3. Resume-safe: si falla, continúa en próxima corrida

Conceptos CNV extraídos (códigos 7-dígitos):
  1122500 = Cash
  1121999 = Receivables
  1120100 = Inventory
  1139999 = AssetsCurrent
  1110100 = PPE
  1110200 = Intangibles
  1119999 = AssetsNonCurrent
  1999999 = Assets (total)
  2210999 = Capital
  2211999 = Reservas
  2212999 = ResultadosNoAsignados
  2299999 = Equity (total)
  2322200 = DebtCurrent
  2321999 = Payables
  2339999 = LiabilitiesCurrent
  2312300 = DebtNonCurrent
  2319999 = LiabilitiesNonCurrent
  2399999 = Liabilities (total)
  3000100 = Revenue
  3000200 = COGS
  3009999 = GrossProfit
  3011600 = DA (depreciación/amortización)
  3019999 = OperatingIncome
  3021400 = IngresosFinancieros
  3021500 = InterestExpense
  3021800 = RECPAM (reexpresión)
  3029999 = PretaxIncome
  3031100 = IncomeTax
  3049999 = NetIncome (total)
  3099999 = ResultadoIntegral (comprehensive income)
  3240000 = CashFlowNeto (net cash change)
  3241100 = CF_Operativo
  3241200 = CF_Inversion (capex)
  3241300 = CF_Financiacion
  8000000 = EPS_basico
  8000001 = EPS_diluido
  8000003 = EBIT
  8000004 = EBITDA
  8000005 = WorkingCapital
  8000006 = Liquidez (ratio)
  8000007 = Solvencia (ratio)
  8000009 = ROE (%)
  8000010 = ROA (%)
  (+ 20 más ratios pre-calculados por CNV)
```

**Ejemplo: Extraer de YPF 2023**

```
GUID: 90123456 (EEFF 2023-12-31 de YPF)

GET https://aif2.cnv.gov.ar/presentations/publicview/90123456

HTML parseado (tabla):
  Período: 31-12-2023
  UnidadMedida: "Millones de pesos"
  fecha_reexpresion: "31-12-2023" (NIC-29)

Conceptos extraídos:
  1999999 (Assets) = 521,234 → valor_normalizado = 521,234 × 1,000,000
  2399999 (Liabilities) = 312,891 → valor_normalizado = 312,891 × 1,000,000
  2299999 (Equity) = 208,343 → valor_normalizado = 208,343 × 1,000,000
  3000100 (Revenue) = 89,456 → valor_normalizado = 89,456 × 1,000,000
  3049999 (NetIncome) = 12,345 → valor_normalizado = 12,345 × 1,000,000
  3241100 (CF_Op) = 15,678 → valor_normalizado = 15,678 × 1,000,000
  3241200 (CF_Inv) = -2,341 → valor_normalizado = -2,341 × 1,000,000

Guardado en cnv_estados_v2:
  30546076432, YPF SA, 1999999, 521234000000, 2023-12-31, Millones, 1000000, 521234000000
  30546076432, YPF SA, 2399999, 312891000000, 2023-12-31, Millones, 1000000, 312891000000
  (... más conceptos)
```

**Validaciones en Extracción:**
- ✅ HTML parseable (estructura AIF2 válida)
- ✅ UnidadMedida identificada (MILES o MILLONES)
- ✅ Conceptos mapeados (código ∈ diccionario)
- ✅ Valores numéricos (no "N/A", no blancos)
- ✅ Identidad: Assets ≈ Liabilities + Equity (tolerancia ≤1%)
- ⚠️ Si identidad falla → flag `identidad_contable_rota`, investigar

**Errores posibles:**
- **HTML no parseable** → Formato AIF2 cambió, reintentar
- **UnidadMedida ambigua** → Usar fallback (asumir MILLONES si ≥ 1M)
- **Concepto inexistente** → Flag, no crashear
- **Valores negativos inesperados** → OK si es concepto que puede ser negativo (NetIncome de pérdidas)
- **GUID duplicado en múltiples períodos** → Posible resubmisión, usar más reciente

---

#### **Paso 3: Extracción de Dividendos (Job 6 v2)**

```bash
Script: job6_v2_reparse_div.py
Entrada: whitelist_div.csv (GUIDs de formulario 339 = dividendos)
Salida: tabla `cnv_dividendos` en screener.db

Acciones:
  1. Para cada GUID dividendo:
     a. GET https://aif2.cnv.gov.ar/presentations/publicview/{GUID}
     b. Parsear HTML de acta de distribución:
        i. Extraer fecha de pago
        ii. Extraer monto total pagado
        iii. Extraer dividendo por acción (si está disponible)
        iv. Guardar HTML crudo en div_html/{guid}.html
     c. Guardar en tabla cnv_dividendos:
        (cuit, guid, fecha_pago, monto_total, dividendo_por_accion, acta_num)
     d. Marcar en log_job6_v2_done.txt
  2. Resume-safe: saltear si ya hecho
  3. Rate limiting: 1s entre requests

Nota: Formulario 339 NO tiene campo "UnitMeasure"
  → Monto total está siempre en pesos (ARS) base
```

**Ejemplo: Dividendo YPF 2024**

```
GUID: 90234567 (Formulario 339 pagos de 2024)

HTML parseado:
  Acta Nº: 2024-001
  Fecha Pago: 15-01-2024
  Monto Total Pagado: $450,000,000 (en pesos)
  Dividendo/Acción: $1.23 (si está disponible)
  Fecha Cierre Registro: 08-01-2024
  Acciones a Distribuir: 365,853,658

Guardado en cnv_dividendos:
  30546076432, 90234567, 2024-01-15, 450000000, 1.23, 2024-001
```

**Validaciones:**
- ✅ Fecha pago ≥ fecha cierre registro
- ✅ Monto total > 0
- ✅ Dividendo/acción coherente (monto / acciones ≈ div/acción)
- ✅ Acta número único por empresa-período
- ⚠️ Si dividendo/acción = NULL → usar cálculo (monto / acciones)

**Errores posibles:**
- **Acta sin estructura clara** → HTML format varió, reintentar parsing
- **Monto en moneda extraña** → Flag (revisar si es CEDEAR o ADR)
- **Dividendo en USD en documento ARS** → Investigar (posible ADR mal clasificado)

---

#### **Paso 4: Normalizar Datos (s0_normalizar_cnv.py)**

```bash
Script: s0_normalizar_cnv.py
Entrada: cnv_estados_v2 (crudo) + cnv_dividendos
Salida: cnv_estados_norm + normalized keys

Acciones:
  1. Normalizar clave (deuda técnica):
     - Viejo: CUIT → ticker (incompleto)
     - Nuevo: CUIT → ticker canónico → cik (formato unificado)
  2. Deduplicar:
     - Si existe misma empresa en período, tomar más reciente
     - Si restatement (misma fecha, valores ≠), usar latest filing
  3. Normalizar moneda:
     - Todos los valores en pesos base (ARS)
     - Si hay USD (raro): convertir a ARS usando CCL del período
  4. Guardar en cnv_estados_norm:
     (cuit_normalized, ticker, periodo_end, concepto, valor_pesos_base)
```

---

#### **Paso 5: Calcular Ratios CNV (s2_ratios_cnv.py)**

```bash
Script: s2_ratios_cnv.py
Entrada: cnv_estados_norm + ipc_nacional.csv (para deflactar CAGR)
Salida: tabla `ratios_cnv` (ratios finales)

Acciones:
  1. Para cada empresa (CUIT), por período:
     a. Extraer últimos conceptos:
        NetIncome, Revenue, Assets, Equity, Deuda, EBITDA, CF_Op, CF_Inv
     b. Calcular ratios:
        ROE = NetIncome / Equity
        ROA = NetIncome / Assets
        MargenNeto = NetIncome / Revenue
        DeudaEBITDA = Deuda / EBITDA
        FCF_CE = (CF_Op - CF_Inv) / (Equity + Deuda)
        Liquidez = AssetsCurrent / LiabilitiesCurrent
        Solvencia = Assets / Liabilities
     c. Calcular CAGR 5y (REAL deflactado):
        1. Obtener NetIncome de últimos 5 años (o disponibles)
        2. Obtener IPC de cada periodo (base dic-2016=100)
        3. Deflactar: NetIncome_real = NetIncome_nominal / (IPC_periodo / 100)
        4. Calcular CAGR = (último / primero) ^ (1/años) - 1
        5. CAGR_real = CAGR de series deflactadas
     d. Obtener Payout (desde cnv_dividendos):
        Payout = Dividendos_pagados (12m) / NetIncome_mismo_período
        Si Payout > 2.0 (200%): flag `payout_insostenible`, usar NULL
     e. Guardar en ratios_cnv:
        (cuit, ticker, periodo, ROE, ROA, Margen, ..., CAGR_5y_real, payout)

  2. Flags:
     - `flag_no_significativo`: si denominador ≈ 0 o valor absurdo
     - `vintage_mixto`: si serie tiene gaps (< 5 años completos)
     - `dato_desactualizado`: si período > 1 año viejo
```

**Ejemplo: TXAR CAGR Real**

```
TXAR histórico (NetIncome anual, en pesos nominales):
  2019: 450M (IPC dic-2019 = 106.7)
  2020: 380M (IPC dic-2020 = 116.4)
  2021: 520M (IPC dic-2021 = 132.2)
  2022: 280M (IPC dic-2022 = 163.2)
  2023: 520M (IPC dic-2023 = 185.7) ← último

Deflactar a pesos base (dic-2016 = 100):
  2019 real = 450M / (106.7 / 100) = 421.5M pesos_base
  2020 real = 380M / (116.4 / 100) = 326.5M
  2021 real = 520M / (132.2 / 100) = 393.5M
  2022 real = 280M / (163.2 / 100) = 171.6M
  2023 real = 520M / (185.7 / 100) = 280M

CAGR_real = (280 / 421.5) ^ (1/4) - 1 = -9.5% ⚠️ NEGATIVO

Interpretación:
  - Ganancias nominales: +15% (520 vs 450M)
  - Pero inflación argentina 2019-2023 ≈ 74%
  - En términos reales: -9.5% (valor real bajó)
  - ✅ Esto es CORRECTO, no es error

Flag: vintage_mixto (solo 4 años, no 5 completos)
```

**Validaciones:**
- ✅ CAGR en rango razonable (-5, +5) (si no, flag)
- ✅ Payout ≤ 2.0 (si >2, insostenible, NULL + flag)
- ✅ Ratios en gates de rango (ver tabla gates)
- ⚠️ Si serie < 5 años → flag `vintage_mixto`

**Errores posibles:**
- **NetIncome = 0** → CAGR = NULL, EPS = NULL
- **Equity ≤ 0** → ROE = NULL, P/B = NULL
- **Revenue ≤ 0** → Margen = NULL
- **IPC faltante en período** → Interpolar linealmente desde meses adyacentes
- **Payout > 200%** → empresa pagó de reservas (insostenible), NULL + flag

---

#### **Paso 6: Descargar Precios yfinance (s3_precios.py)**

```bash
Script: s3_precios.py
Entrada: whitelist de tickers BYMA-only
Salida: tabla `precios` con precios ARS

Acciones:
  1. Para cada ticker BYMA:
     a. GET yfinance data (ticker = "{ticker}.BA" para BYMA)
        - Precio cierre (ARS)
        - Max 52w, Min 52w (ARS)
        - Volume
        - Market cap (si disponible)
     b. Guardar en tabla precios:
        (ticker, fecha, precio_ars, market_cap, year_high, year_low, currency=ARS)
  2. Esperar 0.1s entre requests
  3. Si falta precio reciente (> 1 día): flag `dato_desactualizado`
```

**Particularidad BYMA:** Precios en ARS (no USD)

```
Ejemplo:
  TXAR.BA: $28.50 ARS (2024-01-30)
  Max52w: $45.80
  Min52w: $18.20
  Volume: 1.2M acciones
```

---

#### **Paso 7: Ensamblar Screener (s4_ensamblar.py)**

```bash
Script: s4_ensamblar.py
Entrada: ratios_cnv + precios + dividendos
Salida: tabla `screener` con BYMA-only

Acciones:
  1. Para cada empresa BYMA-only:
     a. Tomar último período limpio (ratios_cnv)
     b. Cruzar con último precio (precios)
     c. Calcular valuación:
        PER = Precio / EPS
        P/B = Precio / BVPS (donde BVPS = Equity / shares)
        P/S = MarketCap / Revenue
     d. Detectar outliers (no_significativo):
        si PER > 500 o < 0 → NULL + flag
        si P/B < 0 → NULL + flag (Equity ≤ 0)
        si P/S > 50 → flag (pero no NULL)
     e. Insertar en screener TABLE:
        (cuit, ticker, grupo="byma_only", ratios, precios, flags, provenance)
```

---

### 4.2 Validaciones en BYMA-only

#### **Validación 1: Identidad Contable**

```
A = P + PN

Tolerancia: ≤ 1% (rounding)

Ejemplo (TXAR 2023):
  Assets = 45,234M
  Liabilities = 22,891M
  Equity = 22,343M
  Suma = 22,891 + 22,343 = 45,234M
  Diferencia = 0% ✅ OK

Si falla:
  1. Revisar si hay RECPAM (reexpresión) → suma especial
  2. Revisar si hay cuentas pendiente de imputación
  3. Si sigue fallando → flag `identidad_rota`, excluir de screener
```

#### **Validación 2: Unidad Normalización**

```
CNV cambió UnidadMedida en ~2021

Viejo: MILES de pesos
Nuevo: MILLONES de pesos

Detección en job5_v2:
  factor_unidad() lee UnidadMedida del HTML
  
  Pre-2021: factor = 1,000
  Post-2021: factor = 1,000,000
  
Validación:
  Si factor ≠ esperado → flag `unidad_ambigua`, usar heurística (valores > 1M asumir millones)
```

#### **Validación 3: Series Continuas**

```
Para CAGR, verificar que hay datos de años consecutivos

Regla: Si hay gap > 1 año → flag `vintage_mixto`, CAGR = NULL

Ejemplo OK:
  2019, 2020, 2021, 2022, 2023 (5 años completos) ✅

Ejemplo con gap:
  2019, 2021, 2023 (faltan 2020, 2022) → vintage_mixto
  Si gap < 1 año (ej. solo Q1 faltante) → interpolar, OK
```

---

### 4.3 Errores Posibles & Mitigación (BYMA-only)

| Error | Causa | Detección | Mitigación |
|-------|-------|-----------|-----------|
| **UnidadMedida ambigua** | cambio CNV 2021, o formato raro | factor ∉ {1000, 1000000} | Heurística: si valores > 1M asumir millones |
| **RECPAM doble** | concepto NIC-29 duplicado | Suma RECPAM > cambio EPS | Tomar valor más reciente filing |
| **Identidad contable rota** | error extracción o restatement | A ≠ P + PN > 1% | Flag, investigar manualmente |
| **CAGR negativo** | inflación > ganancias nominales | CAGR < -0.5 | ✅ OK, es válido (Argentina) |
| **Payout > 200%** | empresa pagó de reservas | Payout > 2.0 | NULL + flag `payout_insostenible` |
| **Precio faltante** | yfinance desactualizado | precio = NULL | Flag `dato_desactualizado`, usar último conocido |
| **Empresa sin filings** | nueva emisora o inactiva | num_eeff = 0 | Flag `sin_datos`, excluir de screener |
| **Ticker confundido** | BYMA vs ADR mismo ticker | ticker BYMA = ticker NYSE | Usar CUIT para distinguir (PK) |
| **Dividendo en período futuro** | fecha pago > period_end | fecha_pago > period_end | Ignorar en ventana 12m de período |
| **Datos de 2+ años atrás** | empresa sin reportes recientes | period_end < (hoy - 2 años) | Flag `dato_desactualizado`, excluir |

---

## 5. Convergencia: Screener Unificado

### 5.1 Unificar 3 Universos (s7_unificar.py)

```bash
Script: s7_unificar.py
Entrada: screener TABLE (56 BYMA-only de s4) + ratios TABLE (500 S&P EDGAR)
Salida: screener TABLE con 572 empresas

Acciones:
  1. Preparar S&P desde ratios TABLE:
     a. Para cada S&P (CIK):
        i. Mapear ratios → columnas screener:
           ratios.roe → ROE
           ratios.per → PER
           ratios.p_book → PriceBook
           ratios.eps_anual → EPS
           ... (ver MAP_RATIOS_SCREENER)
        ii. Extraer precios (de tabla precios)
        iii. Crear columnas especiales:
           cuit = cik (10-digit, no colisiona con CUIT 11-digit)
           grupo = "sp500"
           fuente_fund = "edgar"
           sector = sector_gics (de ratios)
        iv. Todos los valores en USD (de EDGAR)
     b. Insertar en screener TABLE:
        INSERT OR REPLACE ... (idempotente por cuit)

  2. ADRs (si aún no en screener):
     a. Mapear ratios EDGAR (ya en s6)
     b. Insertar en screener (grupo = "adr")

  3. Resultado:
     screener TABLE con 572 filas (500 S&P + 16 ADR + 56 BYMA)
```

**Mapeo Ratios → Screener:**

| Columna ratios | Columna screener | Moneda | Origen |
|---|---|---|---|
| roe | ROE | % (S&P USD, BYMA ARS) | EDGAR/CNV |
| roa | ROA | % | EDGAR/CNV |
| margen_neto | MargenNeto | % | EDGAR/CNV |
| deuda_ebitda | DeudaEBITDA | ratio | EDGAR/CNV |
| eps_anual | EPS | USD o ARS | EDGAR/CNV |
| cagr_eps_5y | CAGR_EPS_5y | % (nominal S&P, real BYMA) | EDGAR/CNV |
| fcf | FCF_CE | % | EDGAR/CNV |
| payout | Payout | % | EDGAR/yfinance |
| per | PER | ratio | EDGAR/CNV |
| p_book | PriceBook | ratio | EDGAR/CNV |
| p_sales | PriceSales | ratio | EDGAR/CNV |

---

### 5.2 Completar Ratios Faltantes (s8_calidad.py)

```bash
Script: s8_calidad.py (bonus, opcional)
Entrada: screener TABLE (572)
Salida: screener TABLE con campos extra + flags

Acciones:
  1. Calcular ratios secundarios:
     EV/EBITDA = (MarketCap + Deuda - Cash) / EBITDA
     Margen Operativo = OperatingIncome / Revenue
     payout_status = clasificar en {calculado, no_paga, falta_dato}
  2. Aplicar flags de sanidad:
     - flag_no_significativo: si ratio no tiene sentido
     - dato_desactualizado: si > 1 año
  3. Normalizar NaN → NULL
```

---

### 5.3 Exportar CSV Final (s5_exportar.py)

```bash
Script: s5_exportar.py
Entrada: screener TABLE (572) completo
Salida: 
  - data/screener_export.csv (572 filas × 26 columnas)
  - data/screener_export.json (array plano)
  - data/screener_export_README.md (documentación)

Acciones:
  1. Validar cobertura por ratio:
     Para cada ratio, reportar:
     - Cantidad no-NULL
     - Porcentaje de cobertura
     - Ejemplos de valores
  2. Validar rangos:
     Para cada ratio, verificar gate (ver tabla gates)
     Si fuera de rango: reportar outliers (no eliminar)
  3. Exportar CSV:
     - Encoding: UTF-8 con BOM
     - Separator: coma
     - NaN/NULL → vacío o "N/A"
  4. Exportar JSON:
     - Array plano de 572 objetos
     - Una fila por empresa
     - NaN → null
  5. Escribir README:
     - Documentar limitaciones
     - Explicar cada columna
     - Advertencias (no comparar BYMA vs S&P 1:1)
```

**CSV final (sample rows):**

```csv
cuit,ticker,grupo,sector,ROE,ROA,MargenNeto,DeudaEBITDA,EPS,CAGR_EPS_5y,PER,PriceBook,PriceSales,Precio,Max52w,Min52w,flag_no_significativo,dato_desactualizado,fuente_fund,provenance
320,AAPL,sp500,Technology,130.2,27.5,24.6,0.88,6.13,12.3,31.0,40.1,7.60,189.95,199.62,124.17,1,0,edgar,sec.gov/10-K/2023-12-31
100908,BMA,adr,Financials,18.2,2.3,15.6,1.22,1.85,5.2,5.54,1.32,2.10,10.25,12.50,8.75,0,0,edgar+cnv,sec.gov/20-F/2023+cnv/2023
30546076432,TXAR,byma_only,Energy,9.4,3.2,8.1,2.15,0.93,-9.5,30.6,1.18,1.05,28.50,45.80,18.20,0,0,cnv,cnv/eeff/2023-12-31
```

---

## 6. Matriz de Validaciones

### Resumen: 15+ Validaciones Implementadas

| # | Nombre | Grupo | Etapa | Criterio | Acción Si Falla |
|---|--------|-------|-------|----------|-----------------|
| 1 | CIK válido | S&P | Discovery | CIK ≠ NULL | Skip empresa |
| 2 | HTTP 200 | Todos | Descarga | status = 200 | Reintentar 3x, skip |
| 3 | JSON parseable | Todos | Parseo | JSON válido | Skip GUID |
| 4 | Moneda consistente | Todos | Normalización | moneda ∈ {USD, ARS} | Flag + investigar |
| 5 | Concepto mapeado | Todos | Mapeo | concepto ∈ diccionario | NULL + flag |
| 6 | Identidad contable | Todos | Ratios | A = P + PN ±1% | Flag, revisar |
| 7 | Rango ROE | Todos | Gates | ROE ∈ (-1, 1) | Flag si fuera |
| 8 | Rango PER | Todos | Gates | PER ∈ (0, 500) | Flag si > 500 |
| 9 | Continuidad temporal | S&P | Series | gap ≤ 14 meses | Flag `data_vieja` |
| 10 | TTM válido | S&P | TTM | 12 meses sin duplicar | Usar anual si ambiguo |
| 11 | EPS positivo | Todos | EPS | EPS ≥ 0 o flag | PER = NULL si ≤ 0 |
| 12 | Equity > 0 | Todos | Equity | Equity > 0 | ROE/P/B = NULL |
| 13 | Unidad normalizada | BYMA | CNV | factor ∈ {1k, 1M} | Heurística |
| 14 | Payout sostenible | BYMA | Div | Payout ≤ 2.0 | NULL + flag si > 2 |
| 15 | CAGR serie completa | BYMA | CAGR | ≥ 5 años o flag | CAGR = NULL si < 4 |
| 16 | CCL consistente | ADR | FX | CCL derivado ≈ mercado ±3% | Flag si > 3% |
| 17 | Precio reciente | Todos | Precio | fecha ≤ 1 día | Flag `dato_viejo` |
| 18 | Resume-safe | Todos | ETL | Log de hechos | Skip si ya procesado |

---

## 7. Gestión de Errores

### Estrategia: Flag > Fabricate

**Principio:** Marcar datos problemáticos, nunca inventar.

| Tipo Error | Fabricación | Alternativa (Flag) |
|-----------|------------|-------------------|
| Valor faltante | Inventar ratio (ej. PER = 0) | NULL + flag `dato_faltante` |
| Identidad rota | Ignorar | Flag + investigar = manual |
| Período viejo | Usar último | Flag `dato_desactualizado` |
| EBITDA faltante | Asumir = OI | Calcular = OI + DA (si ambos existen) |
| Equity negativo | Forzar ratio | NULL + flag (ratio no definido) |
| Payout insostenible | Reportar así | NULL + flag `payout_insostenible` |

### Gestión de Timeout / Rate Limit

```
Para EDGAR:
  1. Esperar 1 seg entre requests (recomendación SEC)
  2. Si timeout (429): backoff exponencial (5, 10, 30, 60s)
  3. Máximo 3 reintentos
  4. Si falla: log + continuar (resume-safe)

Para CNV:
  1. Esperar 0.3-1s entre requests (CNV es más lento)
  2. Si timeout: backoff exponencial
  3. Máximo 3 reintentos
  4. Si falla: log + continuar
  5. --max N para limitar requests/sesión

Para yfinance:
  1. Esperar 0.1s entre requests (yfinance es fast)
  2. Si timeout: reintentar 2x
  3. Si falla: usar último precio conocido + flag
```

---

## 8. Guía para Usuario Final

### 8.1 Interpretación de Datos

#### **Sobre CAGR Real (BYMA)**

```
CAGR real BYMA está deflactado por IPC INDEC (base dic-2016=100).

⚠️ PUEDE SER NEGATIVO

Ejemplo TXAR:
  CAGR nominal: +5% (números suben en pesos)
  CAGR real: -15% (pero inflación fue 20%, perdió poder)
  
Interpretación:
  ✅ Correcto y esperado (Argentina 2019-2023)
  No es un bug, es la realidad económica

Vs S&P (USD):
  CAGR S&P está en NOMINAL USD
  No está deflactado (USD es estable)
  
Lección: NO COMPARAR CAGR BYMA vs S&P 1:1
```

#### **Sobre PER de BYMA (34% cobertura)**

```
Muchas BYMA no son rentables (NetIncome ≤ 0).

PER = Precio / EPS
Si EPS ≤ 0 → PER no tiene sentido → NULL + flag

Esto NO es culpa de la extracción.
Es la realidad de BYMA: 66% de empresas no rentables.

Si quieres "PER" de empresa no rentable:
  Usar alternativa: EV/EBITDA, Price/Sales, etc.
  Pero en general, empresa no rentable = mala inversión
```

#### **Sobre Valuación BYMA en ARS**

```
BYMA cotiza en pesos (ARS), no USD.

P/E BYMA = Precio ARS / EPS ARS

NO es comparable directamente con P/E S&P (USD/USD).

Para comparar internacionalmente:
  Convertir a USD: P/E_USD = P/E_ARS / MEP

Pero aún así:
  - Empresas argentinas operan en economía inflacionaria
  - S&P opera en economía estable
  - Valuaciones serán distintas por riesgo país
```

### 8.2 Limitaciones Honestas

#### **Qué CONFIAR:**

- ✅ Ratios de S&P (EDGAR certificado por SEC)
- ✅ Identidad contable (A = P + PN valida estructura)
- ✅ CAGR real BYMA (deflactado con IPC oficial)
- ✅ Precios (yfinance, actualizado diariamente)
- ✅ Flags (honestidad sobre qué no funciona)

#### **Qué USAR CON CUIDADO:**

- ⚠️ PER BYMA (baja cobertura 34%, muchas no rentables)
- ⚠️ Payout (timing issues, puede haber retrasos)
- ⚠️ Comparar BYMA vs S&P (fuentes distintas, monedas, riesgo país)
- ⚠️ CAGR < 5 años (serie incompleta, vintage_mixto)
- ⚠️ EV/EBITDA (CNV tiene problemas de unidad NIC-29)

#### **Qué EVITAR:**

- ❌ Rankear BYMA vs S&P por P/E sin conversión
- ❌ Asumir Payout = 0 donde está NULL
- ❌ Usar datos con flag `dato_desactualizado` > 1 año
- ❌ Promediar ratios sin excluir outliers (flagged)
- ❌ Asumir empresa = crisis porque CAGR < 0 (es inflación)

### 8.3 Cómo Usar el CSV

#### **Filtrar Datos Confiables:**

```python
import pandas as pd

df = pd.read_csv('screener_export.csv')

# 1. Excluir datos viejos
df = df[df['dato_desactualizado'] == 0]

# 2. Excluir outliers
df = df[df['flag_no_significativo'] == 0]

# 3. Filtrar por cobertura (solo empresas con PER)
df = df[df['PER'].notna()]

# 4. Rankear por PER (comparables)
df_rank = df.sort_values('PER')
print(df_rank[['ticker', 'grupo', 'PER', 'ROE', 'Margen']].head(20))

# 5. Segmentar por universo
sp500 = df[df['grupo'] == 'sp500']  # 500 empresas
byma = df[df['grupo'] == 'byma_only']  # 56 empresas
adr = df[df['grupo'] == 'adr']  # 16 empresas
```

#### **Interpretar Flags:**

```python
# Empresas con identidad contable dudosa
suspect = df[df['flag_no_significativo'] == 1]
print(f"Outliers flagged: {len(suspect)} / {len(df)}")

# Empresas con datos viejos
old_data = df[df['dato_desactualizado'] == 1]
print(f"Datos viejos: {len(old_data)} empresas")

# Empresas sin cobertura completa
incomplete = df[df['PER'].isna() | df['ROE'].isna()]
print(f"Cobertura incompleta: {len(incomplete)} empresas")
```

### 8.4 Matriz de Decisión: ¿Usar este dato?

```
Preguntas a hacer:

1. ¿Es S&P o BYMA?
   S&P → puedo comparar con otras S&P (misma fuente)
   BYMA → comparo solo con otras BYMA, NO con S&P 1:1

2. ¿Tiene flag no_significativo?
   Sí → revisar qué field (ROE? PER?) está flageado
        usar alternativa (ej. si PER=NULL, usar P/S)
   No → OK, confiar

3. ¿Tiene flag dato_desactualizado?
   Sí → última actualización > 1 año
        decidir si OK o demasiado viejo
   No → datos frescos

4. ¿Es ratio con baja cobertura?
   PER en BYMA (34%) → verificar que está presente
   Payout (71%) → si NULL, no asumir 0
   CAGR < 5 años → vintage_mixto, usar con cuidado
   No → cobertura alta, confiar

5. ¿Quiero comparar BYMA vs S&P?
   Sí → NUNCA directamente
        convertir a USD primero (usar CCL/MEP)
        aún así, recordar diferencias de riesgo país
   No → OK, solo rankear dentro de grupo
```

---

## Conclusión

Este ETL implementa **3 pipelines paralelos y convergentes** que transforman datos crudos de **3 fuentes** distintas en **572 empresas comparables** con **26 ratios certificados** y **honestidad explícita** via flags.

**Principio fundamental:** Si algo no funciona → marcar → nunca inventar.

**Usuario final:** Confianza en datos bien validados, transparencia en limitaciones.

---

**Versión:** 2.0 | **Fecha:** 2026-08-09 | **Mantenedor:** Catalaxia Team
