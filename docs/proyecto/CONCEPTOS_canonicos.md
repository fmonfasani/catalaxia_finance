# Esquema canónico de conceptos (Q5) — DRAFT para revisión

Set de conceptos de la **capa derived/gold**. Cada concepto canónico se mapea desde CNV y SEC, y
se compara contra la línea de investing. Basado en lo que **realmente existe** (CNV: 51 conceptos;
SEC: `facts.concepto` normalizado + `facts.tag` crudo).

**Convenciones:** `snake_case`. Valores en moneda nativa del dato (`unit`/`moneda`). Nada se
inventa: si una fuente no tiene el concepto, queda nulo (no se rellena con 0).

## A. Estado de Resultados (Income Statement)
| Canónico | investing | CNV (`concepto`) | SEC (`concepto`/tag) |
|---|---|---|---|
| `revenue` | Total Revenues | `Revenue` | `Revenues` / RevenueFromContractWithCustomer |
| `cogs` | Cost of Revenues | `COGS` | CostOfRevenue |
| `gross_profit` | Gross Profit | `GrossProfit` | `GrossProfit` |
| `operating_expenses` | Other Operating Expenses | *(derivado)* | OperatingExpenses |
| `operating_income` | Operating Income | `OperatingIncome` | `OperatingIncome` (OperatingIncomeLoss) |
| `da` | *(en EBITDA)* | `DA` | DepreciationDepletionAndAmortization |
| `ebit` | EBIT | `EBIT` | *(derivado)* |
| `ebitda` | EBITDA | `EBITDA` | *(derivado EBIT+DA)* |
| `interest_expense` | Interest Expense, Total | `InterestExpense` | InterestExpense |
| `financial_income` | Interest & Invest. Income | `IngresosFinancieros` | InvestmentIncomeInterest |
| `recpam` ⚠️AR | *(dentro de resultados)* | `RECPAM` | *(no estándar; result. por posición monetaria)* |
| `pretax_income` | EBT, Incl. Unusual Items | `PretaxIncome` | `PretaxIncome` (IncomeLossBeforeTax) |
| `income_tax` | Income Tax Expense | `IncomeTax` | IncomeTaxExpenseBenefit |
| `minority_interest` | Minority Interest | *(rev.)* | MinorityInterest |
| `net_income` | Net Income | `NetIncome` | `NetIncome` (NetIncomeLoss) |
| `comprehensive_income` | *(—)* | `ResultadoIntegral` | ComprehensiveIncomeNetOfTax |

## B. Balance (Balance Sheet)
| Canónico | investing | CNV | SEC |
|---|---|---|---|
| `assets` | Total Assets | `Assets` | `Assets` |
| `assets_current` | *(—)* | `AssetsCurrent` | AssetsCurrent |
| `assets_noncurrent` | *(—)* | `AssetsNonCurrent` | AssetsNoncurrent |
| `cash` | *(en CF)* | `Cash` | `Cash` (CashAndCashEquivalents) |
| `receivables` | *(—)* | `Receivables` | ReceivablesNetCurrent |
| `inventory` | *(—)* | `Inventory` | InventoryNet |
| `ppe` | *(—)* | `PPE` | PropertyPlantAndEquipmentNet |
| `intangibles` | *(—)* | `Intangibles` | IntangibleAssetsNetExcludingGoodwill |
| `liabilities` | *(—)* | `Liabilities` | `Liabilities` |
| `liabilities_current` | Total Current Liabilities | `LiabilitiesCurrent` | LiabilitiesCurrent |
| `liabilities_noncurrent` | *(—)* | `LiabilitiesNonCurrent` | LiabilitiesNoncurrent |
| `payables` | *(—)* | `Payables` | AccountsPayableCurrent |
| `debt_current` | *(—)* | `DebtCurrent` | DebtCurrent / ShortTermBorrowings |
| `debt_noncurrent` | *(—)* | `DebtNonCurrent` | LongTermDebtNoncurrent |
| `debt_total` | *(en Debt/Equity)* | *(derivado)* | `Debt` |
| `equity` | Total Equity | `Equity` | `Equity` (StockholdersEquity) |
| `capital` | *(—)* | `Capital` | CommonStockValue |
| `reserves` | *(—)* | `Reservas` | *(varios)* |
| `retained_earnings` | *(—)* | `ResultadosNoAsignados` | RetainedEarnings |
| `working_capital` | *(—)* | `WorkingCapital` | *(derivado)* |

## C. Flujo de Efectivo (Cash Flow)
| Canónico | investing | CNV | SEC |
|---|---|---|---|
| `cfo` | Cash from Operations | `CF_Operativo` | `CFO` (NetCashProvidedByOperating) |
| `cfi` | Cash from Investing | `CF_Inversion` | NetCashProvidedByInvesting |
| `cff` | Cash from Financing | `CF_Financiacion` | NetCashProvidedByFinancing |
| `net_change_cash` | Net Change in Cash | `CashFlowNeto` | CashPeriodIncreaseDecrease |
| `capex` | *(en FCF)* | *(de CFI)* | PaymentsToAcquirePPE |
| `fcf` | Levered Free Cash Flow | *(derivado CFO−capex)* | *(derivado)* |

## D. Por acción / dividendos
| Canónico | investing | CNV | SEC |
|---|---|---|---|
| `eps_basic` | Basic EPS | `EPS_basico` | `EPS_basic` |
| `eps_diluted` | Diluted EPS | `EPS_diluido` | `EPS_diluted` |
| `shares_basic` | Basic Wtd Avg Shares | *(—)* | `Shares_basic` |
| `shares_diluted` | Diluted Wtd Avg Shares | *(—)* | `Shares_diluted` |
| `dividend_per_share` | Dividend Per Share | *(cnv_dividendos)* | `Dividends` |

## E. Ratios derivados (comparables a investing — `ratios_externos`)
Se calculan sobre los canónicos (TTM para flujos, snapshot para balance):
| Canónico | Fórmula | investing |
|---|---|---|
| `per` | precio / `eps_ttm` | P/E Ratio |
| `p_book` | precio / bvps | Price/Book |
| `p_sales` | mcap / `revenue_ttm` | Price/Sales |
| `ev_ebitda` | EV / `ebitda_ttm` | *(—)* |
| `roe` | `net_income_ttm` / `equity` | Return on Equity |
| `roa` | `net_income_ttm` / `assets` | Return on Assets |
| `gross_margin` | `gross_profit` / `revenue` | Gross margin |
| `operating_margin` | `operating_income` / `revenue` | Operating margin |
| `net_margin` | `net_income` / `revenue` | Net Profit margin |
| `ebitda_margin` | `ebitda` / `revenue` | EBITDA margin |
| `debt_equity` | `debt_total` / `equity` | Debt/Equity |
| `debt_ebitda` | `debt_total` / `ebitda_ttm` | *(—)* |
| `current_ratio` | `assets_current` / `liabilities_current` | Current Ratio |
| `quick_ratio` | (`assets_current`−`inventory`) / `liabilities_current` | Quick Ratio |
| `dividend_yield` | `dividend_per_share` / precio | Dividend Yield |
| `fcf_yield` | `fcf_ttm` / mcap | *(—)* |
| `asset_turnover` | `revenue_ttm` / `assets` | Asset Turnover |
| `earnings_yield` | `eps_ttm` / precio | *(inversa PER)* |

## F. Tratamiento de RECPAM — doble variante (decisión del usuario)
RECPAM (resultado por posición monetaria, NIC-29) distorsiona la comparación. Por eso **todo
concepto afectado por RECPAM se guarda en DOS variantes**: `incluye_recpam=true` (tal cual
reportado) y `incluye_recpam=false` (neto del efecto RECPAM). Si varios tags están afectados, se
**replica cada uno en ambas variantes**.
- **Afectados** (2 variantes cada uno): `pretax_income`, `net_income`, `comprehensive_income`, y
  todos los ratios que dependen de ellos: `net_margin`, `roe`, `roa`, `per`, `earnings_yield`,
  `payout`, `eps_basic`, `eps_diluted`.
- **No afectados** (1 variante): `revenue`, `cogs`, `gross_profit`, `operating_income`, `ebit`,
  `ebitda`, y todo el balance y flujo (RECPAM está por debajo del resultado operativo).
- Cálculo: `net_income_ex_recpam = net_income − recpam` (ajustando efecto impositivo donde aplique).
- Implementación: columna dimensión **`incluye_recpam` (bool)** en la capa derived. El screener
  muestra la elegida (default: reportado; con toggle a ex-RECPAM).

## G. Columnas del screener (producto) — set prioritario del usuario
Orden y columnas que el screener debe exponer:
`especie` · `mercado` · `precio_usd` · `per` · `max_52s` · `dif_max_52s` · `min_52s` ·
`dif_min_52s` · `deuda_ebitda` · `eps_anual` · `cagr_eps_5y` · `margen_neto` · `roe_5y` ·
`fcf_ce` (FCFonCE) · `payout` · **+** `market_cap` · `shares` · `precio` (yf) · `net_income` ·
`revenue` · `gross_profit` · `ebitda` · `operating_income` · `dividendos_$` · `fcf` · `assets` ·
`equity` · `deuda` · `cash`.
> Todo derivable del esquema canónico A–E. `roe_5y` y `cagr_eps_5y` necesitan **5 años de
> historia** → refuerza el requisito de máxima cobertura temporal.

## Notas de mapeo
- **`recpam`** es específico de AR (NIC-29, resultado por posición monetaria). No tiene tag SEC
  estándar; en SEC ARS aparece dentro de resultados financieros. **Clave** para reconciliar NetIncome.
- **SEC tiene miles de tags crudos** (`facts.tag` con `concepto=None`): se **conservan en raw** y se
  mapean progresivamente. La lista de arriba es el **núcleo comparable**, no un límite.
- Las líneas `*(—)*` de investing existen en el detalle (EERR completo) aunque no en el "Summary".
- **Períodos:** todo se guarda **trimestral standalone** + **anual**; TTM se deriva.

## Revisión del usuario (RESUELTO 2026-07-14)
1. **¿Falta algún concepto/ratio?** → No por ahora, pero el **procedimiento queda ABIERTO/
   extensible** (se pueden agregar conceptos/tags sin rehacer el esquema).
2. **¿Nombres?** → Sin objeción (a definir si surge).
3. **¿Prioridad screener?** → Definida: ver sección G (columnas del producto).
