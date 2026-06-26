# Especificación de Tags y Ratios — Screener SEC EDGAR

> **Estado:** implementado en producción. La sección **§7** documenta el mapeo
> canónico GAAP↔IFRS y los ~35 ratios ya calculados en `data/screener.db`
> (553 empresas). Las secciones §1-§6 son la spec de referencia (us-gaap).

Tabla maestra de los **~40 tags core** de SEC EDGAR (XBRL `us-gaap`) y los
**~45 ratios** que se pueden construir con ellos.

- **Fuente:** `companyfacts/CIK{cik}.json` (SEC EDGAR) + precio de yfinance.
- **Cobertura** medida sobre 7 empresas de sectores distintos (AAPL, KO, WMT,
  XOM, JNJ, GS-banco, NEE-utility). `7/7` = universal; `<7` = depende del sector.
- **Tipo:** `flujo` = se acumula en el período (TTM); `foto` = saldo a una fecha
  (se toma el último). Ver `GUIA_SEC_EDGAR_PARA_DEVS.md` §7.1.
- **Regla de oro:** si falta un componente, el ratio es NULL. Nunca se estima.

> Por empresa hay **400-750 tags XBRL** disponibles; estos ~40 son los que
> alcanzan para casi todos los ratios. El resto es específico de industria.

---

## 1. Estado de Resultados (Income Statement) — flujo

| Concepto | Tag XBRL (primario → fallbacks) | Cob. | Alimenta |
|----------|--------------------------------|------|----------|
| Ingresos | `Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax` → `SalesRevenueNet` | 6/7 | Margen Neto/Op/Bruto, P/S, EV/Sales, Asset Turnover, Crec. Revenue |
| Costo de ventas | `CostOfRevenue` → `CostOfGoodsAndServicesSold` → `CostOfGoodsSold` | 4/7 | Margen Bruto, Inventory Turnover, DIO |
| Ganancia bruta | `GrossProfit` | 3/7 | Margen Bruto |
| Ganancia operativa (EBIT) | `OperatingIncomeLoss` | 5/7 | Margen Op., EBITDA, EV/EBIT, ROCE, Cobertura intereses |
| I+D | `ResearchAndDevelopmentExpense` | 3/7 | Intensidad I+D (solo tech/pharma) |
| Gastos SG&A | `SellingGeneralAndAdministrativeExpense` → `GeneralAndAdministrativeExpense` | 5/7 | Eficiencia operativa |
| Gasto en intereses | `InterestExpense` → `InterestExpenseDebt` | 6/7 | Cobertura de intereses |
| Ganancia antes de impuestos | `IncomeLossFromContinuingOperationsBeforeIncomeTaxes...NoncontrollingInterest` | 7/7 | Tasa impositiva efectiva, NOPAT |
| Impuesto a las ganancias | `IncomeTaxExpenseBenefit` | 7/7 | NOPAT (ROIC), tasa efectiva |
| **Ganancia neta** | `NetIncomeLoss` → `ProfitLoss` | 7/7 | EPS, PER, Margen Neto, ROE, ROA, Payout |
| EPS diluido (reportado) | `EarningsPerShareDiluted` | 7/7 | EPS anual, Crec. EPS 5Y |
| EPS básico (reportado) | `EarningsPerShareBasic` | 7/7 | EPS básico |
| Acciones diluidas (prom.) | `WeightedAverageNumberOfDilutedSharesOutstanding` | 7/7 | EPS, todo ratio per-share |
| Acciones básicas (prom.) | `WeightedAverageNumberOfSharesOutstandingBasic` | 7/7 | EPS básico (fallback) |
| Depreciación y amort. | `DepreciationDepletionAndAmortization` → `DepreciationAndAmortization` → `Depreciation` | 7/7 | EBITDA, Deuda/EBITDA, EV/EBITDA |
| Amort. de intangibles | `AmortizationOfIntangibleAssets` | 5/7 | EBITDA (cuando D&A es el tag estrecho) |

## 2. Balance General (Balance Sheet) — foto

| Concepto | Tag XBRL (primario → fallbacks) | Cob. | Alimenta |
|----------|--------------------------------|------|----------|
| Activos totales | `Assets` | 7/7 | ROA, Asset Turnover, Equity/Assets |
| Activo corriente | `AssetsCurrent` | 6/7 | Current Ratio, Quick Ratio, Working Capital |
| Caja y equivalentes | `CashAndCashEquivalentsAtCarryingValue` | 7/7 | Deuda Neta, EV, Cash Ratio, Cash/acción |
| Inversiones de corto plazo | `ShortTermInvestments` → `MarketableSecuritiesCurrent` | 4/7 | Cash Ratio ampliado |
| Cuentas por cobrar | `AccountsReceivableNetCurrent` | 5/7 | DSO, Receivables Turnover, Quick Ratio |
| Inventario | `InventoryNet` | 6/7 | Inventory Turnover, DIO, Quick Ratio |
| Propiedad, planta y equipo | `PropertyPlantAndEquipmentNet` | 7/7 | Intensidad de capital |
| Goodwill | `Goodwill` | 6/7 | Tangible Book Value |
| Intangibles | `IntangibleAssetsNetExcludingGoodwill` → `FiniteLivedIntangibleAssetsNet` | 5/7 | Tangible Book Value |
| Pasivos totales | `Liabilities` | 5/7 | Deuda/Equity (aprox.), solvencia |
| Pasivo corriente | `LiabilitiesCurrent` | 6/7 | Current Ratio, Quick Ratio, Working Capital |
| Cuentas por pagar | `AccountsPayableCurrent` | 3/7 | Payables Turnover, Cash Conversion Cycle |
| Deuda de largo plazo | `LongTermDebt` → `LongTermDebtNoncurrent` | 7/7 | Deuda/Equity, Deuda/EBITDA, EV |
| Deuda LP corriente | `LongTermDebtCurrent` | 6/7 | Deuda total |
| Deuda de corto plazo | `ShortTermBorrowings` → `DebtCurrent` | 6/7 | Deuda total |
| **Patrimonio neto** | `StockholdersEquity` | 7/7 | ROE, P/B, Deuda/Equity, BVPS |
| Resultados acumulados | `RetainedEarningsAccumulatedDeficit` | 7/7 | Calidad/madurez |
| Acciones en circulación | `CommonStockSharesOutstanding` → `EntityCommonStockSharesOutstanding` | 7/7 | Validación de escala, Market Cap |

## 3. Flujo de Efectivo (Cash Flow) — flujo

| Concepto | Tag XBRL (primario → fallbacks) | Cob. | Alimenta |
|----------|--------------------------------|------|----------|
| Flujo de caja operativo (CFO) | `NetCashProvidedByUsedInOperatingActivities` | 7/7 | FCF, P/CF, Earnings Quality |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` → `PaymentsToAcquireProductiveAssets` | 6/7 | FCF, CapEx/Revenue, CapEx/D&A |
| Dividendos pagados | `PaymentsOfDividendsCommonStock` → `PaymentsOfDividends` | 6/7 | Payout, Dividend Yield, FCF Payout |
| Recompras de acciones | `PaymentsForRepurchaseOfCommonStock` | 7/7 | Buyback Yield, Shareholder Yield |
| Stock-based compensation | `ShareBasedCompensation` | 4/7 | FCF ajustado, Earnings Quality |

## 4. Metadatos de entidad (`dei`) y precio (yfinance)

| Concepto | Origen | Alimenta |
|----------|--------|----------|
| Public Float | `dei:EntityPublicFloat` | Tamaño / liquidez |
| Precio actual | yfinance `last_price` | PER, P/B, P/S, EV, yields |
| Market Cap | yfinance `market_cap` (o precio × acciones) | P/S, EV, FCF Yield |
| Máx/Mín 52 semanas | yfinance `year_high` / `year_low` | Dif. 52w |

---

## 5. Catálogo de ratios → tags que requiere

`✓` = ya implementado · `＋` = a agregar

### Valuación
| Ratio | Fórmula | Tags / fuentes |
|-------|---------|----------------|
| ✓ PER | Precio / EPS_TTM | precio + NetIncome + Shares |
| ＋ P/Book | Precio / (Equity/acciones) | precio + Equity + Shares |
| ＋ P/Sales | MarketCap / Revenue_TTM | precio + Revenue + Shares |
| ＋ P/FCF | MarketCap / FCF_TTM | precio + CFO + CapEx + Shares |
| ＋ EV/EBITDA | (MktCap+Deuda−Caja) / EBITDA | precio + Deuda + Cash + OperatingIncome + D&A |
| ＋ EV/EBIT · EV/Sales | EV / EBIT · EV / Revenue | idem + OperatingIncome / Revenue |
| ＋ Earnings Yield · FCF Yield | 1/PER · FCF/MktCap | — |
| ＋ Dividend Yield | Div/acción / Precio | Dividends + Shares + precio |
| ＋ PEG | PER / Crec. EPS | PER + Crec. EPS |

### Rentabilidad / márgenes
| Ratio | Fórmula | Tags |
|-------|---------|------|
| ＋ Margen Bruto | GrossProfit / Revenue | GrossProfit (o Revenue−CostOfRevenue) |
| ＋ Margen Operativo | OperatingIncome / Revenue | OperatingIncome + Revenue |
| ＋ Margen EBITDA | EBITDA / Revenue | OperatingIncome + D&A + Revenue |
| ✓ Margen Neto | NetIncome / Revenue | NetIncome + Revenue |
| ✓ ROE | NetIncome / Equity_prom | NetIncome + Equity |
| ＋ ROA | NetIncome / Assets | NetIncome + Assets |
| ＋ ROIC | NOPAT / Capital invertido | OperatingIncome + tax + Deuda + Equity − Cash |
| ＋ ROCE | EBIT / Capital empleado | OperatingIncome + Equity + Deuda |

### Crecimiento (CAGR 3/5/10 años)
| Ratio | Tags |
|-------|------|
| ✓ Crec. EPS | EarningsPerShareDiluted (serie anual) |
| ＋ Crec. Revenue · NetIncome · FCF · Dividendo · Book Value | series anuales respectivas |
| ✓ ROE 5 años (CAGR) | NetIncome + Equity (series anuales) |

### Solvencia / apalancamiento
| Ratio | Fórmula | Tags |
|-------|---------|------|
| ＋ Deuda/Equity | DeudaTotal / Equity | Deuda + Equity |
| ✓ Deuda/EBITDA (LP y total) | Deuda / EBITDA | Deuda + OperatingIncome + D&A |
| ＋ Deuda Neta/EBITDA | (Deuda−Caja) / EBITDA | + Cash |
| ＋ Cobertura de intereses | EBIT / InterestExpense | OperatingIncome + InterestExpense |
| ＋ Current Ratio | AssetsCurrent / LiabilitiesCurrent | AssetsCurrent + LiabilitiesCurrent |
| ＋ Quick Ratio | (AssetsCurrent−Inventory) / LiabilitiesCurrent | + Inventory |
| ＋ Cash Ratio · Equity/Assets | (Cash+STInv) / LiabCte · Equity / Assets | Cash + Equity + Assets |

### Eficiencia / actividad
| Ratio | Fórmula | Tags |
|-------|---------|------|
| ＋ Asset Turnover | Revenue / Assets | Revenue + Assets |
| ＋ Inventory Turnover · DIO | CostOfRevenue / Inventory | CostOfRevenue + Inventory |
| ＋ Receivables Turnover · DSO | Revenue / Receivables | Revenue + Receivables |
| ＋ Cash Conversion Cycle | DIO + DSO − DPO | Inventory + Receivables + Payables |
| ＋ Working Capital | AssetsCurrent − LiabilitiesCurrent | AssetsCurrent + LiabilitiesCurrent |

### Flujo de caja / calidad
| Ratio | Fórmula | Tags |
|-------|---------|------|
| ✓ FCF | CFO − CapEx | CFO + CapEx |
| ＋ FCF Margin | FCF / Revenue | + Revenue |
| ✓ FCFonCE (2 variantes) | FCF / Capital empleado | CFO + CapEx + Equity + Deuda (+Cash) |
| ＋ CapEx/Revenue · CapEx/D&A | intensidad de inversión | CapEx + Revenue / D&A |
| ＋ **Earnings Quality** | CFO / NetIncome | CFO + NetIncome |

### Por acción y retorno al accionista
| Ratio | Fórmula | Tags |
|-------|---------|------|
| ✓ EPS (básico/diluido) | NetIncome / Shares | NetIncome + Shares |
| ＋ BVPS · FCF/acción · Sales/acción · Cash/acción | (rubro) / Shares | rubro + Shares |
| ✓ Payout | Dividendos / NetIncome | Dividends + NetIncome |
| ＋ FCF Payout | Dividendos / FCF | Dividends + CFO + CapEx |
| ＋ Buyback Yield · Shareholder Yield | (Div+Recompras) / MktCap | Dividends + Buybacks + precio |

---

## 6. Aplicabilidad por sector (qué NO calcular)

La cobertura `<7/7` no es un bug: es que el ratio **no aplica** a ese tipo de
empresa. Calcular por sector (usar el `SIC`) y dejar NULL lo que no corresponde.

| Sector | No tienen (→ NULL) | Métricas propias |
|--------|--------------------|------------------|
| **Bancos** (SIC 60-62) | GrossProfit, CostOfRevenue, Inventory, CapEx clásico, EBITDA | NIM, eficiencia, Tier-1, ROA |
| **Utilities** (SIC 49) | Margen Bruto típico | base de tarifa, FFO |
| **REITs / Inmobiliario** (SIC 65) | EPS estándar como métrica clave | **FFO**, AFFO, NAV |
| **Seguros** (SIC 63-64) | COGS, Inventory | combined ratio, float |
| **Tech/Software** | Inventory casi nulo | métricas SaaS (ARR) fuera de EDGAR |

> Implementación sugerida: un diccionario `RATIOS_POR_SECTOR` que active/desactive
> familias de ratios según el primer dígito del SIC, manteniendo la regla de
> "NULL si no aplica".

---

## 7. Implementación en producción (GAAP + IFRS unificados)

> Esto es lo que **realmente corre** en `scripts/tickets/` y puebla
> `data/screener.db`. Ver `scripts/tickets/README.md`.

### 7.1 Mapeo canónico GAAP ↔ IFRS

Cada concepto se mapea a sus tags en **las dos taxonomías**. Los tags `ifrs-full`
fueron descubiertos empíricamente sobre ADRs reales (GGAL, ABEV, VIV, PAM, UGP,
NU, GGB, LOMA). Definido en `construir_base.py` (`CANONICO`) y
`calcular_ratios_base.py` (`PRIORIDAD`).

| Concepto | us-gaap | ifrs-full |
|----------|---------|-----------|
| Revenue | `Revenues` → `RevenueFromContract…` → `SalesRevenueNet` | `Revenue` → `RevenueFromSaleOfGoods` |
| NetIncome | `NetIncomeLoss` → `ProfitLoss` | `ProfitLossAttributableToOwnersOfParent` → `ProfitLoss` |
| OperatingIncome | `OperatingIncomeLoss` | `ProfitLossFromOperatingActivities` |
| GrossProfit | `GrossProfit` | `GrossProfit` |
| Equity | `StockholdersEquity` | `EquityAttributableToOwnersOfParent` → `Equity` |
| Assets / AssetsCurrent | `Assets` / `AssetsCurrent` | `Assets` / `CurrentAssets` |
| Liabilities / LiabilitiesCurrent | `Liabilities` / `LiabilitiesCurrent` | `Liabilities` / `CurrentLiabilities` |
| Cash | `CashAndCashEquivalentsAtCarryingValue` | `CashAndCashEquivalents` |
| Inventory / Receivables | `InventoryNet` / `AccountsReceivableNetCurrent` | `Inventories` / `TradeAndOtherCurrentReceivables` |
| Debt | `LongTermDebt` → `LongTermDebtNoncurrent` | `Borrowings` → `LongtermBorrowings` |
| D&A | `DepreciationDepletionAndAmortization` → … | `DepreciationAndAmortisationExpense` → … |
| CFO | `NetCashProvidedByUsedInOperatingActivities` | `CashFlowsFromUsedInOperatingActivities` |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` | `PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` |
| Dividends | `PaymentsOfDividendsCommonStock` | `DividendsPaidClassifiedAsFinancingActivities` → `DividendsPaid` |
| EPS diluido | `EarningsPerShareDiluted` | `DilutedEarningsLossPerShare` |
| Shares (prom.) | `WeightedAverageNumberOfDilutedSharesOutstanding` | `AdjustedWeightedAverageShares` → `WeightedAverageShares` |

**Moneda:** IFRS reportan en moneda local (ARS/BRL). Ratios *puros* (margen, ROE,
payout) no la necesitan; los de *valuación* usan **market cap (USD) + FX**
(`precios_y_valuacion.py`). ARS se marca con flag por la inflación.

### 7.2 Ratios calculados hoy (~35)

**Fundamentales** (`calcular_ratios_base.py`, sin precio):
margen_bruto, margen_operativo, margen_ebitda, margen_neto, roe, roa, roce,
deuda_equity, deuda_ebitda, deuda_neta_ebitda, current_ratio, quick_ratio,
asset_turnover, inventory_turnover, dso, fcf_margin, capex_revenue,
earnings_quality (CFO/NI), payout, fcf_payout, eps_ttm, eps_anual, bvps,
cagr_revenue_5y, cagr_eps_5y, cagr_ni_5y, cagr_equity_5y.

**Valuación** (`precios_y_valuacion.py`, con market cap + FX):
per, p_book, p_sales, ev_ebitda, earnings_yield, fcf_yield, div_yield.

**Pendientes** (faltan conceptos en el mapeo): cobertura de intereses
(`InterestExpense`), ROIC (`IncomeTaxExpenseBenefit`), cash ratio.

### 7.3 Flags de calidad (`flags_calidad.py`)

| Flag | Marca |
|------|-------|
| `ni_fy` | el "TTM" salió del último año fiscal (estrategia C), no rodante |
| `roe_ns` | equity < 5% de activos (recompras) → ROE no interpretable |
| `fx` | reporta en ARS (inflación) o sin FX disponible |
| `mktcap_rev` | market cap de yfinance inconsistente con precio×acciones (solo US) |

Columna `flags` (texto) en la tabla `ratios`. **429/553 empresas quedan limpias.**
Para screening confiable: `WHERE flags IS NULL`.
