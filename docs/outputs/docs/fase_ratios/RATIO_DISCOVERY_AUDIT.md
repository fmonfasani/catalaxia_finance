# RATIO DISCOVERY AUDIT — CATALAXIA

**Fecha:** 2026-09-01 · **Rol:** auditor independiente · **Alcance:** inventario, trazabilidad y auditoría
**Nada implementado, nada corregido, nada modificado.** Sólo lectura sobre código, PostgreSQL, SQLite, RAW y tests.

Matriz completa: [`RATIO_COVERAGE_MATRIX.csv`](RATIO_COVERAGE_MATRIX.csv) — 39 filas.

---

# RATIO_DISCOVERY_GATE = **PASS_WITH_WARNINGS**

El inventario se pudo construir por completo con evidencia reproducible. Lo que
aparece no es un sistema de ratios, sino **cuatro sistemas de ratios que no
comparten definición, período, cobertura ni base de datos**, y ninguno con un
solo test unitario.

---

## 0. El número que ordena todo lo demás

```
implementaciones de ratios encontradas ..............  4 superficies + 13 satelites
ratios distintos implementados en alguna superficie .. 33
ratios del pedido (25) implementados ................ 20
ratios calculados por la capa homologada (engine) ... 17
ratios publicados al usuario final ..................  11
tests unitarios de ratios ...........................  0   de 265 tests recolectados
ratios persistidos en la base homologada ............  0
```

Ese último renglón es el hallazgo estructural: **PostgreSQL —la base que pasó
homologación— no tiene ninguna tabla de ratios.** Tiene `derived.fact` (88.789
hechos, 8 CIK, 22 filings) y nada más. Los 17 ratios del engine se calculan en
memoria y se escriben a JSON en `outputs/`. No tienen fila, ni `valid_to`, ni
provenance persistida, ni idempotencia verificable.

---

## 1. Inventario — las cuatro superficies

No son cuatro versiones de lo mismo. Son cuatro sistemas con datos, períodos y
universos distintos.

| # | superficie | base | universo | ratios | persistido | publicado |
|---|---|---|---:|---:|---|---|
| **S1** | **Engine / homologada** — `ratio_defs.py` + `screener_demo.py` | PostgreSQL 5433 `derived.fact` | **8 CIK** | **17** | **NO** (JSON) | no |
| **S2** | **Legacy EDGAR** — `calcular_ratios_base.py` | SQLite `ratios` | 609 empresas | **27** | sí | parcial |
| **S3** | **Legacy pipeline** — `f4_ratios.py` → `screener_gold` | SQLite `fact_ratios` / `screener_gold` | 56–567 | **11** | sí | **sí, 11 en el HTML** |
| **S4** | **BYMA / CNV** — `b5_metricas.py`, `s2_ratios_cnv.py`, `s4_ensamblar.py` | SQLite `byma_pipeline.db`, `screener` | 56–572 | **13** | sí | **sí, vía la API** |

### Clasificación pedida (A–E)

**A · implementado** — los 33 de la matriz.

**B · usado por producción/screener** — 11 en el HTML público
(`gen_screener_html.py` línea 216): `per, p_book, p_sales, roe, roa,
margen_neto, margen_bruto, margen_operativo, margen_ebitda, deuda_ebitda,
ev_ebitda`. La API (`api/main.py:150`) sirve además `eps, fcf_ce, payout,
cagr_eps_5y, div_yield_adr, max_52w, min_52w`.

**C · experimental** — todo S1. Se calcula, se audita, no se publica ni se
persiste. También `ratios_ttm`, `per_ttm`, `ratios_cnv`, `metricas`.

**D · definido pero no calculado** — `backend/calculators/ratios.py`. Declara
`FALLBACK_REVENUE`, `FALLBACK_DA`, `FALLBACK_CAPEX`, `FALLBACK_DIVIDENDOS` y las
firmas de `calcular_ttm_flujo`, `calcular_cagr`, `calcular_ratios_ticker` — y
las tres **levantan `NotImplementedError`**. Es el módulo que la arquitectura
declara como el calculador oficial del Job 2, y está vacío.

**E · sólo en documentación** — `ROIC` (5 documentos), `PEG` y `Forward P/E`
(`ESPEC_TAGS_RATIOS.md`). Cero implementaciones.

### Dos trampas del inventario

`cedear_ratio`, `cedear_x` y `adr_ratio` **no son ratios financieros**: son
factores de conversión (CEDEARs por acción, ADS por acción). Un inventario que
busque la palabra "ratio" los cuenta. No están en la matriz.

`silver_norm` (1.147 filas, TXAR) tampoco: son hechos normalizados, no ratios,
pese a que el endpoint que los sirve se llama `/v1/ratios`.

---

## 2. Universo de ratios — los 25 pedidos

| ratio | ¿existe? | dónde | estado |
|---|---|---|---|
| P/E | **sí** | S1 S2 S3 S4 | YELLOW |
| Forward P/E | **no** | — | **RED** |
| PEG | **no** | — | **RED** |
| P/B | **sí** | S1 S3 S4 | YELLOW |
| P/S | **sí** | S3 S4 | YELLOW |
| EV/EBITDA | **sí** | S3 S4 | YELLOW |
| EV/EBIT | **no** | — | **ORANGE** |
| EV/Sales | **no** | — | **ORANGE** |
| ROE | **sí** | S1 S2 S3 S4 | YELLOW |
| ROA | **sí** | S1 S2 S3 S4 | YELLOW |
| ROIC | **no** | — | **ORANGE** |
| Gross Margin | **sí** | S1 S2 S3 | YELLOW |
| Operating Margin | **sí** | S1 S2 S3 | YELLOW |
| Net Margin | **sí** | S1 S2 S3 S4 | YELLOW |
| Debt/Equity | **sí** | S1 S2 | YELLOW |
| Net Debt/EBITDA | **sí** | S2 | YELLOW |
| Current Ratio | **sí** | S1 S2 | YELLOW |
| Quick Ratio | **sí** | S1 S2 | YELLOW |
| Asset Turnover | **sí** | S2 | YELLOW |
| Inventory Turnover | **sí** | S2 | YELLOW |
| Interest Coverage | **sí** | S1 | YELLOW |
| FCF Yield | **parcial** | S4 | YELLOW |
| Dividend Yield | **parcial** | S4, fuente externa | YELLOW |
| Payout Ratio | **sí** | S2 S4 | YELLOW |
| EBITDA / margen | **sí** | S2 S3 | YELLOW |

**20 de 25 implementados. 3 ORANGE, 2 RED.**
La matriz agrega 14 ratios más que existen y no estaban en el pedido: `cash_ratio`,
`equity_ratio`, `effective_tax_rate`, `ocf_to_net_income`, `borrowings_to_equity`,
`roce`, `dso`, `capex_revenue`, `fcf_margin`, `bvps`, `eps`, `market_cap`,
`cagr_*`, `roe_5y`, rango 52w.

---

## 3. Grafo de derivación — el caso completo

El único ratio con la cadena entera demostrada extremo a extremo, medida en este
audit sobre `outputs/docs/fase_producto/screener.json`:

```
P/E (CEPU) = 9.3925
│
├── Market Price ─── 2166.00 ARS · instrumento 80 · BUE · 2026-08-27
│     └── market_price_daily  (4.799.938 filas)
│           └── RAW: market_raw_files
│
└── EPS ─────────── 230.61 ARS
      ├── tag ....... ifrs-full:BasicEarningsLossPerShare
      ├── namespace . https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full
      ├── derived.fact
      │     └── source_fact_ids ──► parsed.facts
      │           ├── source_file
      │           ├── source_hash (sha256)
      │           └── context_id + unit_ref
      └── accession . 0001292814-26-002446 (2026-04-22)
            └── https://www.sec.gov/Archives/edgar/data/1717161/...-index.htm
```

**Los 8 eslabones existen.** `screener_demo.evidencia_de()` no infiere: sigue
`source_fact_ids`, que S04 dejó escrito, y marca `SIN_CADENA` o `ROTA` cuando
no puede.

Para el resto de los ratios fundamentales de S1 la cadena es la misma con otro
tag. **Para S2, S3 y S4 no existe** cadena equivalente: `fact_financials` y
`partidas_norm` no llevan puntero al hecho ni al archivo fuente con hash.

---

## 4. Caminos alternativos

Contados sobre lo que el sistema **tiene**, no sobre lo que sería posible con
otra fuente.

### P/E — 5 caminos

| | camino | clase |
|---|---|---|
| A | precio / EPS reportado | **IMPLEMENTED** (S1) |
| B | market_cap / net income | **IMPLEMENTED** (S4, `b5_metricas`) |
| C | precio / (NI / acciones) | POSSIBLE_BUT_NOT_IMPLEMENTED |
| D | precio / EPS diluido | POSSIBLE_BUT_NOT_IMPLEMENTED |
| E | precio / EPS normalizado | **NOT_SUPPORTED** |

A y B **no son la misma cuenta**: A usa el EPS que el emisor reportó, B lo
reconstruye. La verificación de que coinciden está hecha y da **9 de 9 períodos
con diferencia < 0,72 %** (`multipath.json`).

### EPS — el único con acuerdo numérico independiente

```
periodo      reportado    derivado    dif%     veredicto
2025-12-31      -2.11    -2.107401   0.123     COINCIDE
2024-12-31       5.99     5.988444   0.026     COINCIDE
2023-12-31      -3.35    -3.349306   0.021     COINCIDE
2022-12-31       5.67     5.672205   0.039     COINCIDE
2021-12-31       0.65     0.654684   0.721     COINCIDE
2020-12-31    -177.42  -177.424562   0.003     COINCIDE
2019-12-31     -86.85   -86.848810   0.001     COINCIDE
2018-12-31      98.43    98.345685   0.086     COINCIDE
2017-12-31      31.43    31.429460   0.002     COINCIDE
```

Nueve ejercicios, dos monedas (ARS y USD), nueve accessions distintas. Es la
evidencia más fuerte de todo el inventario.

### Los demás

**ROE — 4 caminos, todos IMPLEMENTED en superficies distintas**: equity de
cierre (S1, S3), equity promedio (S2), promedio de ROE anuales 5y (S4), y las
variantes con y sin RECPAM (S3). Cuatro números distintos con el mismo nombre.

**EV/EBIT y EV/Sales — POSSIBLE_BUT_NOT_IMPLEMENTED**: los cuatro insumos
(market cap, deuda, caja, EBIT o revenue) ya se calculan por separado en ambas
capas. Son el hueco más barato del inventario.

**Forward P/E y PEG — NOT_SUPPORTED**: exigen consenso de analistas. Ninguna de
las fuentes ingeridas (SEC XBRL, CNV, precios) lo publica.

---

## 5. Cobertura de tags — medida, no supuesta

`derived.fact`, hechos numéricos no dimensionales, vigentes:

| tag | facts | CIK | filings | ns | períodos |
|---|---:|---:|---:|---:|---|
| `Assets` | 55 | **8** | 22 | 11 | 2017-12 .. 2026-06 |
| `Liabilities` | 55 | **8** | 22 | 11 | 2017-12 .. 2026-06 |
| `EntityCommonStockSharesOutstanding` | 20 | 7 | 20 | 9 | 2017-12 .. 2026-06 |
| `GrossProfit` | 54 | 6 | 18 | 11 | 2017-12 .. 2026-06 |
| `Equity` | 64 | 5 | 16 | 9 | 2017-12 .. 2025-12 |
| `ProfitLossAttributableToOwnersOfParent` | 48 | 5 | 16 | 9 | 2017-12 .. 2025-12 |
| `BasicEarningsLossPerShare` | 31 | 5 | 10 | 3 | **2023-12 .. 2025-12** |
| `Borrowings` | 44 | 3 | 13 | 9 | 2017-12 .. 2025-12 |
| `CurrentLiabilities` | 33 | 3 | 12 | 9 | 2017-12 .. 2025-12 |
| `NetIncomeLoss` | 18 | 3 | 6 | 2 | 2024-09 .. 2026-06 |
| `AssetsCurrent` | 12 | 3 | 6 | 2 | 2024-09 .. 2026-06 |
| `CurrentAssets` | 29 | **2** | 10 | 9 | 2017-12 .. 2025-12 |
| `Revenues` | 6 | **1** | 2 | 2 | 2025-01 .. 2026-01 |

Lo que esta tabla explica sin necesidad de suponer nada:

- **`Assets` y `Liabilities` son los únicos universales** (8/8, 22/22). Por eso
  ROA tiene 566/567 de cobertura en el producto y es el mejor cubierto.
- **`CurrentAssets` sólo aparece en 2 CIK.** Ahí está el techo de
  `current_ratio` y `quick_ratio`: no es un bug, es que la mayoría de los
  emisores IFRS de la muestra no publican el subtotal corriente.
- **`BasicEarningsLossPerShare` arranca en 2023.** Antes de eso el EPS viene con
  otros nombres — es el hallazgo del tag que cambia tres veces.
- **La partición IFRS / US-GAAP es nítida**: los tags `us-gaap` sólo tienen
  2 namespaces y arrancan en 2024-09 (AAPL, MSFT, NVDA); los `ifrs-full`
  tienen 9 y llegan a 2017.

### RAW disponible vs. usado

Consulta directa a `parsed.facts` (135.077 hechos):

| concepto | presente en RAW | ¿extraído a `derived`? | ¿usado por algún ratio? |
|---|---|---|---|
| D&A | **sí** — `DepreciationPropertyPlantAndEquipment` 5 CIK, `AmortisationIntangibleAssetsOtherThanGoodwill` 4, `DepreciationDepletionAndAmortization` 2, `DepreciationRightofuseAssets` 3 | sí | **no en S1** (concepto no declarado) |
| dividendos | **sí** — `DividendsPaidClassifiedAsFinancingActivities` 3 CIK, `CommonStockDividendsPerShareDeclared` 3, `DividendsPaid` 2, `DividendsCommonStockCash` 2 | sí | **no** — el `dividend_yield` publicado viene de JPMorgan |
| capex | **sí** — `PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` 3 CIK | sí | sólo en S2 |
| EBITDA | **no existe como tag** | — | se construye |

Esto reclasifica tres ratios que el ciclo anterior había puesto en `NOT_CALCULABLE`
por falta de datos: **el dato está; lo que falta es la declaración del concepto.**

---

## 6. Conceptos alternativos — sólo los encontrados

Ninguna equivalencia inferida. Estos tags aparecen en RAW o están declarados en
`ratio_defs.CONCEPTOS`.

| métrica | conceptos encontrados | advertencia |
|---|---|---|
| **Ingresos** | `Revenue`, `RevenueFromContractsWithCustomers`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `RevenueFromContractWithCustomerIncludingAssessedTax`, `Revenues` | *Excluding* vs *Including AssessedTax* difieren en impuestos indirectos |
| **Resultado neto** | `ProfitLossAttributableToOwnersOfParent`, `ProfitLoss`, `NetIncomeLoss`, `ProfitLossAttributableToOwnersOfParentDiluted` | `ProfitLoss` incluye minoritarios; `...AttributableToOwnersOfParent` no |
| **Patrimonio** | `Equity`, `EquityAttributableToOwnersOfParent`, `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` | mismo problema de minoritarios |
| **Acciones** | `WeightedAverageShares`, `WeightedAverageNumberOfSharesOutstandingBasic`, `WeightedAverageNumberOfDilutedSharesOutstanding`, `EntityCommonStockSharesOutstanding`, `NumberOfSharesOutstanding`, `CommonStockSharesOutstanding` | **TRES conteos NO intercambiables**: el de `dei` lleva fecha de **carátula**, no de cierre |
| **EPS** | `BasicEarningsLossPerShare`, `BasicAndDilutedEarningsPerShare`, `BasicAndDilutedEarningsLossPerShare`, `EarningsPerShareBasic`, `IncomeLossFromContinuingOperationsPerBasicShare` | el nombre cambia según ejercicio |
| **Efectivo** | `CashAndCashEquivalents`, `CashAndCashEquivalentsAtCarryingValue`, `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` | **el tercero incluye efectivo restringido** |
| **Deuda** | `Borrowings`, `LongTermDebt`, `DebtLongtermAndShorttermCombinedAmount` | **perímetros distintos** — ya advertido en el propio `ratio_defs.py` |
| **Activo/pasivo corriente** | `CurrentAssets` / `AssetsCurrent`, `CurrentLiabilities` / `LiabilitiesCurrent` | equivalencia IFRS↔US-GAAP, declarada |

El sistema resuelve esto con **cadenas de fallback ordenadas**, donde el orden
*es* la regla y el tag elegido queda en la provenance de cada celda. Es la
decisión de diseño correcta y está documentada en el propio módulo.

---

## 7. Definición semántica — dónde hay más de una lectura válida

Seis casos donde el sistema tiene, hoy, más de una definición conviviendo.

### 7.1 · P/E: FY en una superficie, TTM en otra

Medido sobre `screener.json`:

```
AAPL   precio 314.58 USD (2026-08-27)
       EPS      7.49 USD  ← accession 0000320193-25-000079, presentada 2025-10-31
                             = ejercicio fiscal cerrado en septiembre de 2025
       P/E = 42.0
```

El engine divide un precio de agosto de 2026 por el EPS del **ejercicio anual
cerrado once meses antes**. No es TTM. El legacy (`f4_ratios`, `per_ttm`) sí
usa TTM.

Y no es un descuido puntual: **no existe ninguna ocurrencia de `ttm` ni de
`trailing` en `scripts/engine/*.py` ni en `engine/*.py`.** `derived.fact` sólo
distingue `DURATION` (50.379) e `INSTANT` (38.410). La capa homologada **no
tiene noción de TTM en absoluto.**

Esto contradice el método documentado del proyecto (PER al estilo IAMC, que es
TTM). La regla que sí está implementada en ambas superficies es la otra mitad
del método: **EPS ≤ 0 ⇒ P/E = NULL**, nunca negativo.

### 7.2 · `debt_to_equity` no divide por deuda

```python
"debt_to_equity": ("pasivo_total", None, "patrimonio", "veces", True)
```

El numerador es `Liabilities` — **pasivo total**, no deuda financiera. Es una
definición válida y está declarada, y el engine tiene la variante estricta al
lado (`borrowings_to_equity`). Pero quien compare contra investing.com, que usa
deuda financiera, verá una diferencia sistemática que no es un error de dato.

### 7.3 · FCF: dos definiciones que no dan lo mismo

- capa EDGAR (`calcular_ratios_base`): `FCF = CFO − CapEx`
- capa BYMA (`b5_metricas`): `FCF = CFO + CFI`

CFI incluye compras y ventas de activos financieros, no sólo capex. Son
métricas distintas publicadas bajo el mismo nombre.

### 7.4 · «FCF Yield» que no es un yield

`s2_ratios_cnv.py` documenta *"7 fundamentales (ROE, ROA, MargenNeto,
DeudaEBITDA, EPS, **FCFYield**, Payout)"*. La columna que produce, y que la API
sirve, es **`FCF_CE` = FCF / capital empleado**. No es FCF/market cap. El FCF
yield de verdad existe sólo en `b5_metricas` como `fcf_market_cap`.

### 7.5 · Deuda/EBITDA: se publica la bruta, se calcula también la neta

`deuda_neta_ebitda` (356/609) se calcula y se guarda. Lo que el producto
etiqueta «Deuda/EBITDA» es la **bruta** (318/567).

### 7.6 · Comportamientos de borde — bien resueltos

| caso | comportamiento | evidencia |
|---|---|---|
| EPS ≤ 0 | `P/E = NULL`, nunca negativo | S1 y S3 |
| denominador = 0 | `NO_CALCULABLE`, motivo explícito | adversarial A3: *"denominador StockholdersEquity = 0"* |
| monedas distintas | `NO_CALCULABLE` | adversarial A1: *"CurrentAssets=USD vs CurrentLiabilities=ARS. Un ratio no mezcla monedas"* |
| dato faltante | `NO_CALCULABLE` con el concepto que falta y los candidatos buscados | S1 |
| valor ilegible | `publicable=False` (`effective_tax_rate`, `ocf_to_net_income`) | `ratio_defs.RATIOS` |

Estos cinco están bien. El que no está es el signo: ver §8.

---

## 8. Validación — qué hay y qué falta

### Lo que NO existe

```
$ python -m pytest tests/ --collect-only -q
265 tests collected

tests con cálculo de ratios ............ 0
fixtures de ratios ..................... 0
golden outputs de ratios ............... 0   (los golden existen sólo para Market)
mutation tests de ratios ............... 0
```

**Ni un solo test unitario sobre ningún ratio, en ninguna de las cuatro
superficies.** Los 265 tests cubren identidad, CNV, lifecycle, parseo y
normalización. La capa que produce el número que el cliente ve no tiene ninguno.

### Lo que sí existe

| tipo | dónde | resultado medido |
|---|---|---|
| **Suite de identidades contables (BYMA, 56)** | `validacion_suite` | `c1_activo=pas+pn` **56/56 OK** · `c4_GP=Vtas−Costo` 51 OK · `c5_NI=Pretax−Tax` 52 OK 1 FAIL · `c8_dCaja=CFO+CFI+CFF` 47 OK 5 FAIL · **`c6_EBITDA=EBIT+DA` 28 OK 7 FAIL 21 NA** |
| **Suite EDGAR (512)** | `validacion_suite_edgar` | `c10_EPS_vs_NI/Shares` 435 OK 20 FAIL · `c1_activo=pas+pn` 350 OK 7 FAIL · `c16_P/B_sano` 426 OK 31 FAIL |
| **Gate de ROE** | `gate_roe`, `o2_gate_roe` | **35/56 verificado, 21/56 DISCREPANCIA** |
| **Cruce contra investing** | `ratios_externos` (27 filas) + `f4_ratios` | PER y ROE, tolerancia 20 % · `c15_ROE_vs_investing` **7 OK, 17 FAIL, 32 NA** |
| **Bandas de sanidad** | `c16_P/B_sano`, `c17_P/S_sano` | 50/56 y 50/56 OK |
| **Multipath** | `ratios_multipath.py` | EPS **9/9 COINCIDE** |
| **Banco adversario** | `adversario_ratios.py` | 7 ataques, todos con el resultado esperado |
| **Auditoría independiente** | `independent_audit_matrix.py`, `screener_auditoria.py` | tabla propia, sin importar `ratio_defs` |
| **Sello por empresa** | `screener_gold.nivel_certificacion` | CERTIFICADO-SEC 226 · SEC-ok 273 · CERTIFICADO 54 · triangulado-SEC 12 · interno-ok 2 |

### Lo que la validación dice, y que conviene leer sin adornos

- **ROE es el ratio más publicado y el peor respaldado.** `gate_roe` marca
  discrepancia en 21 de 56, y contra investing coincide en **7 de 24
  evaluables**. Es el ratio por el que el screener ordena por defecto.
- **ROA tiene la mejor cobertura (566/567) y ninguna validación externa.**
  `ratios_externos` no trae ROA: no hay contra qué cruzarlo.
- **`c6_EBITDA=EBIT+DA` falla en 7 de 35 evaluables (20 %)** — y de ese EBITDA
  cuelgan `ev_ebitda`, `margen_ebitda`, `deuda_ebitda` y `deuda_neta_ebitda`,
  tres de ellos publicados.
- **164 de 567 empresas (28,9 %) llevan `mcap_confiable = 0`** — y de market cap
  cuelgan P/E, P/B, P/S y EV/EBITDA.

### F-061 sigue abierto y es el riesgo mayor

El ataque A7 del banco adversario clonó `AssetsCurrent`/`LiabilitiesCurrent` de
AAPL bajo el CIK de GGAL, re-etiquetados a nombres `ifrs-full` coherentes con la
taxonomía que GGAL declara. Resultado: el `current_ratio` de GGAL pasó de
`NO_CALCULABLE` a **`0.893293`** — el `current_ratio` de Apple, dígito por
dígito. Nada en la salida lo delata.

Y el ataque A2a: se invirtió el signo de `Equity` de GGAL y **ROE se calculó
igual**, con el signo cambiado, sin ninguna señal.

La capa de ratios **no verifica el origen ni la coherencia interna de los facts
que consume**. La única defensa que sí detectó la corrupción fue la identidad
`Activo = Pasivo + PN` (A2b), que es un chequeo de la capa de datos, no del
ratio.

---

## 9. Gap analysis estilo TIKR

| | ratios | cuáles |
|---|---:|---|
| 🟢 **GREEN** | **1** | EPS |
| 🟡 **YELLOW** | **33** | todo lo demás implementado |
| 🟠 **ORANGE** | **3** | EV/EBIT, EV/Sales, ROIC |
| 🔴 **RED** | **2** | Forward P/E, PEG |
| ⚪ UNKNOWN | 0 | — |

**Por qué sólo EPS es GREEN.** Es el único con las tres condiciones: está
implementado, tiene datos suficientes, y está validado por **dos caminos
independientes que coinciden numéricamente** en 9 ejercicios y por un chequeo
sobre 512 empresas. Ningún otro ratio del sistema tiene eso.

**Por qué todo lo demás es YELLOW y no GREEN.** No por falta de cobertura —
varios superan el 90 %. Por tres razones que se repiten:

1. **cero tests** en los 33;
2. **definiciones múltiples** conviviendo bajo un nombre (P/E, ROE, D/E, FCF,
   Deuda/EBITDA);
3. **validación que existe y no cierra** (ROE 21/56 discrepante; EBITDA 7/35
   fallando; ROA sin cruce posible).

**Por qué los 3 ORANGE lo son.** Los datos están, medidos en `derived.fact` y
`parsed.facts`. Falta la declaración del concepto y el cableado. En el caso de
EV/EBIT y EV/Sales, los cuatro insumos ya se calculan por separado.

**Por qué los 2 RED lo son.** Forward P/E y PEG exigen consenso de analistas.
Ninguna fuente ingerida lo publica. No es un problema de cálculo: falta una
fuente. El propio repositorio ya lo advierte
(`GUIA_RATIOS_EDGAR_vs_INVESTING.md` desaconseja el PEG de terceros por ser
estimación propietaria).

---

## 10. Correcciones a documentos anteriores

Tres afirmaciones vigentes en `outputs/docs/fase_ratios/` no resisten la
verificación directa.

### 10.1 · «P/B no está implementado en el engine» — **FALSO**

`RATIO_PRODUCT_MATRIX.csv` y `RATIO_COVERAGE_MATRIX.md` declaran
`price_to_book | NOT_IMPLEMENTED | "no existe código que lo calcule"`.

`screener_demo.py` líneas 241–270 **sí lo calcula**, y
`outputs/docs/fase_producto/screener.json` trae valor en **6 de 8**:

```
YPFD 1.8360   CEPU 1.2851   TGSU2 2.1912   GGAL —
BMA  —        AAPL 63.0297  MSFT  8.4792   NVDA 35.2261
```

El origen del error: `matriz_producto.py` mapea la tupla `("P/B", None)`, es
decir, **no cablea P/B a ningún id de `ratio_defs`**, y reporta como no
implementado lo que otro script del mismo directorio sí implementa. Es un fallo
del inventario, no del motor.

### 10.2 · «ROIC no es calculable: falta NOPAT y capital invertido» — **impreciso**

Los componentes están en `derived.fact`: impuesto (5 CIK), EBIT (5+3), deuda
(3+3), caja (5+3), patrimonio (5+3). Lo que falta es **la decisión de perímetro
del capital invertido**, no el dato. Reclasificado RED → **ORANGE**.

### 10.3 · «dividend yield, FCF y payout: NOT_CALCULABLE por falta de datos» — **impreciso**

Los tags están en RAW, verificados por consulta directa a `parsed.facts`:
`DividendsPaidClassifiedAsFinancingActivities` (3 CIK),
`CommonStockDividendsPerShareDeclared` (3), `DividendsPaid` (2),
`DividendsCommonStockCash` (2), y para capex
`PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` (3).

Es el mismo error que F-062 ya documentó para el D&A: buscar un solo nombre de
tag sin declarar la cadena de fallback que el resto del contrato ya usa.

---

## 11. Dictamen

# RATIO_DISCOVERY_GATE = **PASS_WITH_WARNINGS**

**PASS** porque el objetivo del ciclo se cumplió íntegro y con evidencia
reproducible: se localizaron las cuatro superficies y los trece satélites, se
inventariaron 33 ratios implementados y 39 filas de matriz, se construyó el
grafo de derivación completo hasta el documento RAW para el caso demostrable, se
clasificaron los caminos alternativos, se midió la cobertura de tags contra la
base en vez de contra la documentación, y se inventarió la validación existente.

**WITH_WARNINGS** por cinco hallazgos, ninguno introducido por este ciclo:

1. **Cero tests unitarios de ratios** sobre 265 tests. La capa que produce el
   número que el cliente ve es la única sin cobertura de test.

2. **F-061 abierto (HIGH).** La capa de ratios no verifica el origen de los
   facts. Un hecho de otra empresa produce un ratio plausible, publicable y sin
   ninguna marca. Demostrado, no hipotético.

3. **La capa homologada no tiene TTM ni persiste ratios.** Cero ocurrencias de
   `ttm` en el engine; cero tablas de ratios en PostgreSQL. Su P/E es FY, el del
   legacy es TTM, y ambos se llaman igual.

4. **Definiciones múltiples bajo un solo nombre** en cinco ratios: P/E (FY vs
   TTM), ROE (4 variantes), Debt/Equity (3 numeradores), FCF (CFO−capex vs
   CFO+CFI), Deuda/EBITDA (bruta publicada, neta calculada). Y un nombre
   directamente intercambiado: «FCFYield» que es FCF/capital empleado.

5. **La validación existente no cierra donde más importa.** ROE —el ratio por
   el que ordena el screener— discrepa en 21 de 56 contra el autorreporte y
   coincide en 7 de 24 contra investing. ROA, el mejor cubierto, no tiene
   ninguna fuente externa contra la cual cruzarse.

**No se declara ningún ratio homologado.** El gate de este ciclo certifica que
el inventario es correcto y completo, no que los números lo sean.

---

### Anexo · comandos ejecutados

```bash
# inventario
grep -rn "ratio_defs" --include=*.py .
grep -rlE "safe_div|def div\(|/ *equity|/ *assets|/ *rev\b" --include=*.py scripts/ backend/ api/ engine/
grep -rniE "\bpeg\b|forward_pe|ev_ebit\b|ev_sales|\broic\b" --include=*.py --include=*.md .

# PostgreSQL (5433, homologada)
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "\dt *.*"
   -> derived.fact 88789 · parsed.facts 135077 · 8 CIK · 22 accessions
   -> NINGUNA tabla de ratios
docker exec ... -c "SELECT tag, count(*), count(DISTINCT cik), count(DISTINCT accession_number) FROM derived.fact ..."
docker exec ... -c "SELECT qname, count(*), count(DISTINCT cik) FROM parsed.facts WHERE qname ILIKE '%Depreciation%' OR ILIKE '%Dividend%' ..."
docker exec ... -c "SELECT period_kind, count(*) FROM derived.fact GROUP BY 1"
   -> DURATION 50379 · INSTANT 38410  (sin TTM)

# SQLite
sqlite data/screener.db     -> ratios 609 · fact_ratios 679 · screener_gold 567 · screener 572 · ratios_cnv 72
sqlite data/byma_pipeline.db -> metricas 559 · ratios_ttm_byma 731

# tests
python -m pytest tests/ --collect-only -q   -> 265 collected, 0 de ratios
grep -rln "roe\|current_ratio\|margen_neto" tests/*.py   -> (vacio)

# TTM en el engine
grep -rniE "\bttm\b|trailing" scripts/engine/*.py engine/*.py   -> (vacio)
```
