# RATIO_CONTRACT — contrato canónico de ratios de Catalaxia

**Versión: 1.0-DRAFT** · **Fecha: 2026-09-01** · `formula_version = "1.0"`
**Nada implementado en este ciclo.** Este documento es la especificación que habilita la implementación.

Matriz campo por campo: [`RATIO_CONTRACT_MATRIX.csv`](RATIO_CONTRACT_MATRIX.csv) — 20 filas × 30 columnas
Causa raíz del bloqueo: [`F061_ROOT_CAUSE.md`](F061_ROOT_CAUSE.md)
Contrato anterior (13 ratios, superado): [`RATIO_CONTRACT_v0_13ratios.md`](RATIO_CONTRACT_v0_13ratios.md)

---

# RATIO_CONTRACT_GATE = **PASS_WITH_WARNINGS**

El contrato está completo y es implementable. **No autoriza publicar ningún
ratio todavía**: F-061 sigue abierto y 8 de las 20 filas dependen de decisiones
de producto que no me corresponde tomar.

---

## 1. Source of truth

### S1 es el motor canónico

| | superficie | rol propuesto | por qué |
|---|---|---|---|
| **S1** | Engine PostgreSQL — `ratio_defs.py` + `derived.fact` | **CANONICAL RATIO ENGINE** | es la única con `entity_key`, `source_fact_ids`, `valid_to`, `run_id` y hash del archivo fuente |
| S2 | Legacy EDGAR — `calcular_ratios_base.py` → `ratios` | **REFERENCE ONLY** | 609 empresas, pero **sin ningún puntero de provenance** |
| S3 | Legacy pipeline — `f4_ratios.py` → `screener_gold` | **REFERENCE ONLY — en producción hoy** | alimenta el HTML público; sin provenance |
| S4 | BYMA/CNV — `b5_metricas.py`, `s2_ratios_cnv.py` | **REFERENCE ONLY — en producción hoy** | alimenta la API; sin provenance |

El argumento decisivo no es la cobertura —S1 tiene 8 emisores y S3 tiene 567—
sino que **en S2, S3 y S4 el invariante de pertenencia de F-061 no se puede ni
siquiera evaluar**:

```
fact_financials  punteros de provenance: NINGUNO
facts            punteros de provenance: NINGUNO
ratios           punteros de provenance: NINGUNO
screener_gold    punteros de provenance: NINGUNO
```

No es que fallen el control. Es que no existe control posible. Una superficie
que no puede demostrar de dónde viene un número no puede ser la canónica.

### Qué NO se hace

**Nada se borra.** S2, S3 y S4 siguen corriendo y siguen sirviendo el producto
actual. Lo que cambia es su estatus declarado:

- dejan de ser **fuente** y pasan a ser **referencia de contraste** — el destino
  natural de `ratios_externos`, `gate_roe` y las suites de validación;
- ningún ratio nuevo se implementa ahí;
- cuando S1 cubra un ratio para un emisor, el valor de S1 manda y el de la
  superficie legacy queda como cruce.

### Fuera de producción (propuesto, no ejecutado)

| qué | motivo |
|---|---|
| `backend/calculators/ratios.py` | esqueleto con `NotImplementedError` en las 3 funciones; declara ser el calculador oficial del Job 2 y está vacío. **Retirarlo o implementarlo — hoy engaña al lector.** |
| `/v1/ratios` (API) | sirve `silver_norm`, que son hechos normalizados de TXAR, no ratios. El nombre del endpoint miente. |
| `cedear_ratios`, `adr_ratios` | factores de conversión, no ratios financieros. Excluidos del contrato. |

---

## 2. Semántica de período — la nomenclatura canónica

### El problema, medido

```
AAPL   precio 2026-08-27 = 314.58 USD
       EPS = 7.49 USD  ← accession 0000320193-25-000079, FY cerrado 2025-09-27
       engine: P/E = 42.0        ← es FY
       legacy: per_ttm            ← es TTM
       ambos se llaman "P/E"
```

Y no es un descuido puntual: **no existe ninguna ocurrencia de `ttm` ni
`trailing` en `scripts/engine/*.py` ni `engine/*.py`.** La capa homologada no
tiene noción de TTM.

### Regla 1 — ningún valor existe sin ventana

**`window` es parte de la identidad del valor, no un atributo opcional.** La
clave de un ratio persistido es:

```
(entity_key, canonical_id, period_end, window, denominator_basis, currency)
```

Dos valores con la misma `canonical_id` y distinta `window` son **dos hechos
distintos**, no dos versiones del mismo. Ninguno supersede al otro.

### Regla 2 — el vocabulario de ventanas

| `window` | qué es | período que lo cierra |
|---|---|---|
| `FY` | ejercicio fiscal completo | `period_end` = cierre fiscal |
| `TTM` | doce meses móviles | `period_end` = cierre del último trimestre incluido |
| `Q` | un trimestre *standalone* | `period_end` = cierre del trimestre |
| `YTD` | acumulado del ejercicio | `period_end` = cierre del último período acumulado |
| `PIT` | *point in time* — sólo balance | `period_end` = fecha del balance |

`LTM` **no se adopta**: es sinónimo de `TTM` y tener dos nombres para lo mismo
es exactamente el problema que este contrato viene a cerrar.

### Regla 3 — los ratios mixtos declaran las dos mitades

`ROE = flujo / stock`. No basta con la ventana del numerador: hay que decir cómo
se toma el denominador.

| `denominator_basis` | qué |
|---|---|
| `CLOSING` | el saldo al `period_end` |
| `AVERAGE` | promedio entre apertura y cierre del período |
| `n/a` | el denominador también es de flujo (márgenes) o no hay (EPS, FCF) |

### Regla 4 — nomenclatura de superficie

El identificador canónico **nunca** lleva la ventana pegada: la ventana es una
columna. Pero el **display name** sí la lleva siempre, y es obligatorio.

```
canonical_id  : roe
display_name  : "ROE (TTM, cierre) · 2025-12-31"
             o  "ROE (FY 2025, promedio)"

PROHIBIDO    : mostrar "ROE 8,4 %" sin decir la ventana
```

Cuando una variante deba coexistir de forma permanente, se le da **id propio**,
no un sufijo del mismo id:

```
roe                      NI / patrimonio de cierre
roe_avg                  NI / patrimonio promedio
roe_5y                   promedio de los ROE anuales de 5 cierres
liabilities_to_equity    pasivo total / patrimonio     ← el actual `debt_to_equity`
debt_to_equity           deuda financiera / patrimonio ← reservado
debt_to_ebitda           deuda BRUTA / EBITDA          ← el publicado hoy
net_debt_to_ebitda       deuda NETA / EBITDA
fcf_yield                FCF / market cap
fcf_to_capital_employed  FCF / capital empleado        ← el actual `FCF_CE`
```

---

## 3. Reglas transversales

Aplican a las 20 filas por igual. Cada una es verificable.

| # | regla |
|---|---|
| **R1 · pertenencia** | ningún insumo entra al cálculo si viola `INVARIANTE_PERTENENCIA` (F-061). **Es condición de arranque, no un chequeo posterior.** |
| **R2 · moneda** | numerador y denominador en la **misma** moneda. Si difieren → `NOT_CALCULABLE` con las dos monedas en el motivo. **Nunca se convierte.** |
| **R3 · denominador cero** | `NOT_CALCULABLE`, motivo `denominador <concepto> = 0`. Jamás una división. |
| **R4 · denominador negativo** | rechaza cuando invierte la lectura (patrimonio, EBITDA, ingresos, EPS). Ver la columna `negative_denominator` de cada fila. |
| **R5 · numerador negativo** | se publica. Una pérdida es información. La única excepción es P/E, por la regla IAMC. |
| **R6 · insumo faltante** | `NOT_CALCULABLE` nombrando el concepto y **la cadena de candidatos consultada**. |
| **R7 · no disponible** | `NULL` con motivo. Nunca `0`, nunca cadena vacía, nunca omitir la fila. |
| **R8 · determinismo** | la selección de insumos debe ser determinista. Ver §7 W3. |
| **R9 · publicabilidad** | un ratio aritméticamente correcto pero financieramente ilegible se calcula y **no se publica** (`publicable = false`). |
| **R10 · provenance** | ningún valor se persiste sin la cadena completa. Ver §6. |

---

## 4. Las seis definiciones en disputa

Ninguna se resuelve por conveniencia. Para cada una: variantes observadas, cuál
está implementada, cuál documentada, cuál validada, y qué decisión falta.

### D4 · ROE — cuatro variantes conviviendo

| variante | dónde | fórmula |
|---|---|---|
| cierre | S1 `ratio_defs.roe`, S3 `f4_ratios` | NI / patrimonio al cierre |
| promedio | S2 `calcular_ratios_base` | NI / promedio(apertura, cierre) |
| 5 años | S4 `b5_metricas.roe_5y` | promedio de los ROE anuales |
| con/sin RECPAM | S3, doble fila por entidad | NI ajustado o no por inflación |

- **implementada:** las cuatro, todas bajo el nombre `roe`
- **documentada:** ninguna como canónica
- **validada:** `gate_roe` **35/56 verificado, 21/56 DISCREPANCIA**; contra
  investing **7 OK / 17 FAIL / 32 NA**

**Decisión que falta:** (a) cierre o promedio; (b) patrimonio de la controladora
o total; (c) si RECPAM genera una variante publicable o queda interno.

> Recomendación: `roe` = NI(TTM) / patrimonio de la controladora al **cierre**,
> y `roe_avg` como id aparte. El cierre es lo que las cuatro superficies ya
> hacen mayoritariamente y lo que investing usa; el promedio es más correcto
> financieramente pero cambiaría todos los históricos.

### D5 · Debt/Equity — tres numeradores

| variante | dónde | numerador |
|---|---|---|
| pasivo total | S1 `debt_to_equity` | `Liabilities` |
| deuda financiera | S1 `borrowings_to_equity` | `Borrowings` / `LongTermDebt` |
| deuda | S2 `deuda_equity` | `Debt` (current + noncurrent) |

- **implementada:** las tres · **documentada:** las dos de S1, con la
  advertencia de perímetro en el propio `ratio_defs.py` · **validada:** ninguna
  (`ratios_externos.debt_equity` existe, el cruce no)

**Decisión que falta:** cuál se llama `debt_to_equity`.

> Recomendación: renombrar el actual a `liabilities_to_equity` y reservar
> `debt_to_equity` a deuda financiera. Es lo que un usuario espera al comparar
> con cualquier fuente externa. Advertencia que ya está en el código y hay que
> mantener: `Borrowings` (IFRS, corriente + no corriente) **no** es el mismo
> perímetro que `LongTermDebt` (US-GAAP, sin papel comercial corto).

### D7 · FCF — dos definiciones

| variante | dónde | fórmula |
|---|---|---|
| estándar | S2 `calcular_ratios_base` | `CFO − CapEx` |
| BYMA | S4 `b5_metricas` | `CFO + CFI` |

- **implementada:** las dos · **documentada:** ninguna · **validada:**
  `c8_dCaja = CFO+CFI+CFF` **OK 47 / FAIL 5**

`CFI` incluye compras y ventas de activos financieros, no sólo capex. Para un
banco o un holding la diferencia es enorme.

**Decisión que falta:** cuál es `fcf`.

> Recomendación: `fcf = CFO − CapEx`. Es la definición estándar y la única
> comparable con fuentes externas. `CFO + CFI` puede quedar como
> `cash_generation` si se lo quiere conservar, con otro nombre.

### D8 · FCF Yield — el nombre está intercambiado

`s2_ratios_cnv.py` documenta *"7 fundamentales (…, **FCFYield**, Payout)"* pero
la columna que produce, y que **la API sirve en producción**, es
`FCF_CE = FCF / capital empleado`.

El FCF yield de verdad (`FCF / market cap`) existe sólo en `b5_metricas` como
`fcf_market_cap`, y **no se publica**.

- **implementada:** las dos, con los nombres cruzados · **documentada:** mal ·
  **validada:** `c8_dCaja`

**Decisión que falta:** ninguna conceptual — es una **corrección de nombre** en
producción. Requiere decidir si se renombra la columna de la API (rompe
clientes) o se agrega la correcta y se deprecia la otra.

### D6 · Net Debt/EBITDA — se publica la bruta

Se calculan las dos: `deuda_ebitda` (bruta, **318/567 publicada**) y
`deuda_neta_ebitda` (neta, 356/609, **no publicada**). La etiqueta que el
usuario ve, «Deuda/EBITDA», no dice cuál es.

**Decisión que falta:** cuál se publica. Ambas son legítimas y se usan en la
industria; lo que no es legítimo es no decirlo.

> Recomendación: publicar las dos con ids distintos. El costo es cero — ya se
> calculan.

### D3 · EBITDA — el bloqueo real

EBITDA **no existe como tag XBRL**. Siempre se construye. Y los candidatos de
D&A tienen semánticas distintas — medido en `parsed.facts`:

| tag | taxonomía | CIK | qué es |
|---|---|---:|---|
| `DepreciationPropertyPlantAndEquipment` | ifrs-full | 5 | sólo PPE |
| `AmortisationIntangibleAssetsOtherThanGoodwill` | ifrs-full | 4 | sólo intangibles |
| `Depreciation` | us-gaap | 3 | sólo depreciación |
| `DepreciationRightofuseAssets` | ifrs-full | 3 | sólo leasing IFRS-16 |
| `AdjustmentsForDepreciationAndAmortisationExpense` | ifrs-full | 2 | **conciliación del flujo de caja**, no gasto |
| `AdjustmentsForDepreciationExpense` | ifrs-full | 2 | ídem, parcial |
| `AdjustmentsForAmortisationExpense` | ifrs-full | 2 | ídem, parcial |
| `DepreciationAndAmortisationExpense` | ifrs-full | 2 | gasto agregado |
| `DepreciationDepletionAndAmortization` | us-gaap | 2 | agregado, incluye agotamiento |
| `AmortizationOfIntangibleAssets` | us-gaap | 2 | sólo intangibles |

**Doce candidatos, ninguno universal.** Sumarlos duplica (PPE + right-of-use se
solapan); elegir uno subestima; la variante `AdjustmentsFor…` no es el gasto del
ejercicio sino un renglón de conciliación.

- **implementada:** `EBIT + D&A` (S2, S3) · **documentada:** `NetIncome + D&A +
  intereses + impuestos` en `backend/calculators/ratios.py`, que **no está
  implementado** · **validada:** `c6_EBITDA = EBIT + DA` → **OK 28 / FAIL 7 / NA 21**

Falla en 1 de cada 5 empresas evaluables, y de ese EBITDA cuelgan **cuatro
ratios**, tres de ellos publicados hoy.

**Decisión que falta:** la cadena de fallback de D&A, tag por tag, con la regla
de qué hacer cuando hay varios presentes.

> Ésta es la decisión más cara del contrato y la que bloquea más filas.
> Recomendación: no publicar ningún ratio con EBITDA en el denominador hasta
> resolverla, y mientras tanto exponer `operating_margin` y `ev_ebit`, que no
> dependen de D&A.

---

## 5. Cadenas de fallback

**El orden ES la regla.** La pertenencia de un tag a un concepto es una
declaración explícita, nunca una inferencia por parecido de nombre. El tag
elegido va en la provenance de cada celda: saber **cuál** de los candidatos se
usó es parte del resultado.

Conteos de CIK medidos sobre `parsed.facts` (universo de 8 emisores).

| concepto | cadena (en orden) | advertencia |
|---|---|---|
| **ingresos** | `Revenue` · `RevenueFromContractsWithCustomers` · `RevenueFromContractWithCustomerExcludingAssessedTax` · `RevenueFromContractWithCustomerIncludingAssessedTax` · `Revenues` | *Excluding* vs *Including AssessedTax* difieren en impuestos indirectos. **No mezclar en una serie.** |
| **resultado_neto** | `ProfitLossAttributableToOwnersOfParent` · `ProfitLoss` · `NetIncomeLoss` · `ProfitLossAttributableToOwnersOfParentDiluted` | `ProfitLoss` **incluye minoritarios**; el primero no. Cambiar de uno a otro dentro de una serie rompe la comparabilidad. |
| **patrimonio** | `Equity` · `EquityAttributableToOwnersOfParent` · `StockholdersEquity` · `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` | mismo problema de minoritarios. Para P/B y ROE hay que fijar **una** postura y mantenerla. |
| **D&A** | 12 candidatos — ver §D3 | **SIN CADENA DECLARADA. Es la decisión D3.** |
| **dividendos** | `DividendsPaidClassifiedAsFinancingActivities` (5) · `DividendsPaid` (4) · `CommonStockDividendsPerShareDeclared` (3) · `DividendsCommonStockCash` (2) · `PaymentsOfDividends` (2) | los tres primeros son **importes**; `...PerShareDeclared` es **por acción**: no son intercambiables sin multiplicar por acciones. **Y 4 de los 6 grupos ambiguos de §7-W3 son tags de dividendos.** |
| **capex** | `PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` (4) · `PaymentsToAcquirePropertyPlantAndEquipment` (2) · `PaymentsToAcquireProductiveAssets` | ¿se incluye la compra de intangibles? Decisión abierta. |
| **acciones** | *circulación:* `EntityCommonStockSharesOutstanding` (dei) · `NumberOfSharesOutstanding` · `CommonStockSharesOutstanding` — *promedio:* `WeightedAverageShares` · `WeightedAverageNumberOfSharesOutstandingBasic` · `WeightedAverageNumberOfDilutedSharesOutstanding` | **TRES conteos NO intercambiables.** El de `dei` lleva la fecha de **carátula**, no la del cierre. Market cap usa circulación; EPS usa promedio ponderado. **Nunca cruzarlos.** |
| **deuda** | `Borrowings` (4, IFRS) · `LongTermDebt` (3) + `LongTermDebtCurrent` (3) · `DebtLongtermAndShorttermCombinedAmount` | **perímetros distintos**, ya advertido en `ratio_defs.py`. `Borrowings` abarca corriente y no corriente; `LongTermDebt` no incluye papel comercial de corto plazo. |
| **efectivo** | `CashAndCashEquivalents` · `CashAndCashEquivalentsAtCarryingValue` · `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` | **el tercero incluye efectivo restringido.** No es el mismo perímetro para `cash_ratio` ni para EV. |

### Regla de estabilidad de cadena

Dentro de una **serie temporal de un mismo emisor**, si el tag elegido cambia
entre períodos, el valor se marca `tag_switch = true` y se registran ambos tags.
No se bloquea —el emisor cambió de etiqueta, no nosotros— pero el consumidor
tiene que poder verlo. Es exactamente el caso del EPS, cuyo tag cambia tres
veces.

---

## 6. Persistencia

Hoy PostgreSQL **no tiene ninguna tabla de ratios**: los 17 del engine se
calculan en memoria y se escriben a JSON. Sin fila no hay `valid_to`, ni
provenance persistida, ni idempotencia verificable.

### `derived.ratio` — propuesta

```sql
CREATE TABLE derived.ratio (
  ratio_key           text PRIMARY KEY,   -- hash de la clave de identidad
  -- ── identidad del valor ────────────────────────────────────────────
  entity_key          text NOT NULL REFERENCES identity_v1.entity(entity_key),
  canonical_id        text NOT NULL,      -- 'roe', 'pe', 'ev_ebitda', ...
  period_end          date NOT NULL,
  window              text NOT NULL,      -- FY | TTM | Q | YTD | PIT
  denominator_basis   text NOT NULL,      -- CLOSING | AVERAGE | n/a
  currency            text,               -- NULL si la unidad es adimensional
  -- ── el valor ───────────────────────────────────────────────────────
  value               numeric,            -- NULL cuando status <> 'CALCULADO'
  unit                text NOT NULL,      -- veces | fraccion | moneda | moneda_por_accion
  status              text NOT NULL,      -- CALCULADO | NOT_CALCULABLE | REVIEW_REQUIRED
  motivo              text,               -- obligatorio si status <> 'CALCULADO'
  publicable          boolean NOT NULL,
  -- ── cómo se obtuvo ─────────────────────────────────────────────────
  formula_version     text NOT NULL,      -- '1.0'
  formula             text NOT NULL,      -- la expresión, legible
  inputs              jsonb NOT NULL,     -- ver abajo
  -- ── provenance y ciclo de vida ─────────────────────────────────────
  input_checkpoint_id text NOT NULL,      -- estado de derived.fact que se leyó
  run_id              text NOT NULL REFERENCES engine.runs(run_id),
  calculated_at       timestamptz NOT NULL DEFAULT now(),
  valid_from          timestamptz NOT NULL DEFAULT now(),
  valid_to            timestamptz,        -- NULL = vigente
  UNIQUE (entity_key, canonical_id, period_end, window,
          denominator_basis, currency, valid_to)
);
```

### `inputs` — la provenance, obligatoria

Un elemento por insumo. Sin esto la fila no se inserta.

```json
[{
  "rol":              "numerador",
  "concepto":         "resultado_neto",
  "tag_elegido":      "ProfitLossAttributableToOwnersOfParent",
  "cadena_evaluada":  ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss", "NetIncomeLoss"],
  "qname":            "https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full#ProfitLoss...",
  "namespace":        "ifrs-full",
  "valor":            -1234567890,
  "moneda":           "USD",
  "unit_ref":         "usd",
  "fact_key":         "…",
  "accession_number": "0001193125-26-126363",
  "source_fact_ids":  [12841, 12842],
  "source_file":      "…",
  "source_hash":      "…",
  "pertenencia_ok":   true
}]
```

`pertenencia_ok` es el resultado de R1 **por insumo**. Si alguno es `false`, la
fila entera se persiste con `status = 'REVIEW_REQUIRED'` y `value = NULL` — el
hecho queda registrado, nunca silenciado.

### Reglas de escritura

| | |
|---|---|
| **inmutable** | un valor no se actualiza. Se cierra con `valid_to = now()` y se inserta el nuevo. |
| **idempotencia** | recalcular con el mismo `input_checkpoint_id` y la misma `formula_version` no debe producir fila nueva. Se compara por `ratio_key`. |
| **trazabilidad de fórmula** | cambiar una fórmula obliga a subir `formula_version`. Valores de versiones distintas **nunca** se comparan en una serie. |
| **ciclo de vida** | escritura dentro de `run_scope()`, como el resto del engine (F-050). |
| **NOT_CALCULABLE se persiste** | «no se pudo» es información. Sin la fila, un hueco es indistinguible de un emisor no procesado. |

---

## 7. Contrato de tests

Doce familias. Ninguna escrita todavía salvo T1, que ya existe.

| # | familia | qué debe demostrar | estado |
|---|---|---|---|
| **T1** | **identity isolation** | insumos de la entidad A no entran al ratio de B; la selección filtra por pertenencia, no por texto | **`tests/test_f061_ownership.py` — 4 verdes, 2 rojos** |
| **T2** | **formula correctness** | cada fórmula contra un caso a mano, con los números escritos en el test | por escribir |
| **T3** | **unit consistency** | monedas distintas ⇒ `NOT_CALCULABLE`; unidades incompatibles (por acción vs total) nunca se dividen entre sí | parcial: adversarial A1 |
| **T4** | **period correctness** | numerador y denominador del mismo `period_end`; un comparativo mal etiquetado no entra | parcial: adversarial A5 |
| **T5** | **TTM / FY distinction** | el mismo `canonical_id` con distinta `window` produce **dos filas**, y ninguna se publica sin ventana | por escribir — **el más importante del contrato** |
| **T6** | **missing inputs** | falta un concepto ⇒ `NOT_CALCULABLE` nombrando el concepto **y la cadena consultada** | parcial: adversarial A10 |
| **T7** | **zero denominator** | jamás una división por cero; motivo explícito | parcial: adversarial A3 |
| **T8** | **negative earnings** | EPS ≤ 0 ⇒ P/E `NULL`, nunca negativo; ROE negativo **sí** se publica; EBITDA ≤ 0 ⇒ los ratios que lo tienen de denominador se rechazan | parcial |
| **T9** | **mutation** | quitar cada garantía hace fallar su test, y **el test identifica cuál garantía cayó**. Mínimo: R1, R2, R3, la cadena de fallback y `window` | por escribir |
| **T10** | **idempotency** | recalcular con el mismo checkpoint no inserta filas; el `ratio_key` coincide; distinguir idempotencia **semántica** de identidad física de fila | por escribir |
| **T11** | **provenance** | toda fila `CALCULADO` tiene `inputs` completo y cada `source_fact_id` resuelve a `parsed.facts` con `source_hash` presente | por escribir |
| **T12** | **cross-entity contamination** | a escala: **cero** filas de `derived.ratio` cuyos insumos violen R1 — control de invariante sobre toda la tabla | por escribir |

### Dos exigencias sobre los tests, aprendidas en los ciclos anteriores

1. **Control positivo obligatorio.** Todo test que verifica un rechazo necesita
   su gemelo que verifica que el caso válido **sí** pasa. Sin eso, un fixture
   roto hace pasar el test sin probar nada (fue el rol de T5b en el ciclo CNV,
   y de `test_control_positivo_…` en T1).
2. **Unión causal con el código.** Los tests no copian el SQL: lo **extraen** del
   módulo. Si alguien cambia la consulta, el test cambia de resultado.
   `test_f061_ownership.py` usa `inspect.getsource` para esto.

---

## 8. Dictamen

# RATIO_CONTRACT_GATE = **PASS_WITH_WARNINGS**

**PASS**: el contrato está completo y es implementable sin reinterpretar nada.
20 filas con los 19 campos pedidos; las cuatro superficies con rol asignado; la
nomenclatura de período resuelta; las seis definiciones en disputa disecadas con
variantes, implementación, documentación y validación por separado; nueve
cadenas de fallback con conteos medidos; el esquema de persistencia; las doce
familias de test. F-061 tiene causa raíz, invariante, fix demostrado y test de
aceptación rojo.

**WITH_WARNINGS**, no PASS limpio, por lo que sigue.

### BLOCKERS — impiden publicar ratios

| # | blocker | evidencia |
|---|---|---|
| **B1** | **F-061 abierto.** La capa de ratios no verifica la pertenencia de sus insumos. Afecta a **los 17 ratios de S1** y a los 4 módulos. | `test_f061_ownership.py` — 2 rojos; `F061_ROOT_CAUSE.md` |
| **B2** | **No hay persistencia.** Sin `derived.ratio` no hay idempotencia, ni `valid_to`, ni provenance guardada. T10, T11 y T12 no se pueden escribir. | PostgreSQL sin tabla de ratios |
| **B3** | **P/E se publica sin ventana.** S1 emite FY y S3 emite TTM con el mismo nombre. | AAPL: precio 2026-08-27 ÷ EPS FY 2025-09 = 42.0 |
| **B4** | **EBITDA sin cadena de D&A declarada.** Bloquea `ev_ebitda`, `net_debt_to_ebitda`, `debt_to_ebitda` y `margen_ebitda` — tres publicados hoy. | 12 candidatos de D&A; `c6` FAIL 7/35 |

### WARNINGS

| # | warning |
|---|---|
| **W1** | **ROE es el ratio más publicado y el peor respaldado**: `gate_roe` 21/56 discrepante, investing 7 OK / 17 FAIL. Y es el orden por defecto del screener. |
| **W2** | **ROA tiene la mejor cobertura (566/567) y cero validación externa.** Ninguna fuente ingerida lo trae. |
| **W3** | **La selección de insumos no es determinista.** `facts_ultimo_ejercicio` construye `disp[tag]` con *last-write-wins* sobre una consulta **sin `ORDER BY`**. Medido: 6 grupos `(cik, period, tag)` con más de un valor sobre 6.882 — y **cero** son tags de ratio hoy, así que no afecta a ningún número publicado. Pero **4 de los 6 son tags de dividendos**: en cuanto se cablee `payout` o `dividend_yield`, la ambigüedad pasa a ser real. R8 lo exige resuelto antes. |
| **W4** | **`mcap_confiable = 0` en 164/567 (28,9 %)**, y de market cap cuelgan P/E, P/B, P/S, EV/EBITDA y EV/Sales. |
| **W5** | **`backend/calculators/ratios.py` engaña.** Declara ser el calculador oficial y sus tres funciones levantan `NotImplementedError`. |
| **W6** | **`fcf_ce` se documenta como «FCFYield» en producción.** La API sirve hoy una métrica con el nombre de otra. |

### DECISIONS_REQUIRED — de producto, no de ingeniería

| id | decisión | bloquea |
|---|---|---|
| **D1** | Enterprise Value: ¿minoritarios y leasing dentro o fuera? | `ev_ebitda`, `ev_sales` |
| **D2** | Market cap: ¿cuál de los tres conteos de acciones? ¿qué hacer si la fecha del `dei` no es la del cierre? | los 5 múltiplos |
| **D3** | **EBITDA: la cadena de D&A, tag por tag** | 4 ratios · **el más caro** |
| **D4** | ROE: cierre o promedio · controladora o total · RECPAM | `roe` |
| **D5** | Debt/Equity: ¿cuál de los tres numeradores lleva el nombre? | `debt_to_equity` |
| **D6** | Deuda/EBITDA: ¿bruta, neta, o ambas con ids distintos? | `net_debt_to_ebitda` |
| **D7** | FCF: `CFO − CapEx` o `CFO + CFI` | `fcf`, `fcf_yield` |
| **D8** | `fcf_ce` en producción: ¿renombrar (rompe clientes) o agregar y depreciar? | corrección de nombre |
| **D9** | P/B y ROE: patrimonio de la controladora o total | `pb`, `roe` |
| **D10** | P/S para `es_financiera = 1`: ¿se publica o queda NULL por no significativo? | `ps` |
| **D11** | ROIC: perímetro del capital invertido y origen de la tasa efectiva | `roic` |
| **D12** | Ventana canónica de publicación: ¿TTM o FY como default del producto? | todos los de flujo |

### IMPLEMENTATION_NEXT — en este orden

| paso | qué | por qué primero |
|---|---|---|
| **1** | **Cerrar F-061.** Aplicar `GUARDA_PERTENENCIA` en un único punto de selección de insumos del que dependan los 4 módulos. Criterio: los 6 tests de `test_f061_ownership.py` en verde. | ningún ratio debe publicarse antes; el fix ya está demostrado por el test verde `test_la_correccion_propuesta_…` |
| **2** | **Crear `derived.ratio`** con la migración y el `run_scope`. Sin persistencia no hay T10/T11/T12. | habilita todo lo demás |
| **3** | **Implementar los que NO tienen decisión pendiente**: `eps` (LISTO), `roa`, los tres márgenes, `current_ratio`, `ev_sales`. | `ev_sales` es el ratio nuevo más barato: los cuatro insumos ya se calculan y no depende de D&A |
| **4** | **Escribir T5 (TTM/FY)** y migrar los ratios existentes a llevar `window` obligatoria. | es B3, y es el que impide que el contrato se degrade solo |
| **5** | **Resolver D3 (EBITDA)** con evidencia, no por elección. Recién ahí `ev_ebitda` y los de deuda. | 4 ratios bloqueados, 3 publicados hoy |
| **6** | Resolver D4/D5/D6/D7 e implementar `roe`, `debt_to_equity`, `net_debt_to_ebitda`, `fcf`, `fcf_yield`. | requieren decisión de producto |
| **7** | **T9 (mutación) y T12 (contaminación a escala)** sobre lo implementado. | ninguna garantía cuenta hasta que una mutación demuestre que la sostiene |

**Ningún ratio queda homologado por este documento.** El contrato define qué
debe cumplirse; la homologación exige, además, que se cumpla y que un test lo
demuestre.
