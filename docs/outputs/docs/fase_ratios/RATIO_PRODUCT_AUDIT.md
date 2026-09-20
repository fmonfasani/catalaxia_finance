# RATIO_PRODUCT_AUDIT — qué puede mostrar Catalaxia HOY, sin sobredeclarar

**Fecha:** 2026-09-01 · **Rol:** Senior Financial Data Engineer + Quantitative
Validation Engineer + Product Auditor
**Muestra:** YPF, CEPU, TGSU2, GGAL, BMA, AAPL, MSFT, NVDA
**Sin commits · sin tocar SEC/CNV/Market · base homologada verificada intacta
antes y después de cada corrida (control Z de cada auditor)**

Este documento parte de lo que ya existía —`RATIO_CONTRACT.md`,
`RATIO_COVERAGE_MATRIX.md`, `RATIO_VALIDATION_REPORT.md`,
`PRODUCT_DEMO_GATE.md`, todos del 2026-09-01— y responde la pregunta central
del encargo con evidencia nueva, no con la ya existente reformulada.

---

## Resumen ejecutivo

De los 13 ratios pedidos, **10 están implementados** (EPS, P/E, ROE, ROA,
D/E, Current, Quick, Gross/Operating/Net Margin) y **3 no** (P/B, P/S,
EV/EBITDA — los tres por falta de código, no de dato). Sobre las 8 empresas
de la muestra, los 10 implementados dan **66 valores CALCULADO + 1
NULL_VALIDO** de 88 celdas posibles (75%); el resto son `NO_CALCULABLE`
(gaps de dato genuinos, mayormente en balances de banco) o `BLOQUEADO` (1
celda: el P/E de BMA, por falta de enlace de instrumento — no de dato).

**Hallazgo nuevo más importante de este ciclo:** BMA **sí tiene
fundamentals calculables** (14 valores CALCULADO en 2 ejercicios) pese a
que el instrumento de mercado no está enlazado. El ciclo anterior
clasificaba a BMA entera como "cortada en IDENTITY", lo cual es cierto para
la cadena E2E instrumento-primero pero engañoso para el producto: los
ratios fundamentales no necesitan ese enlace. Ver Fase E.

**Segundo hallazgo:** el banco adversario encontró que la capa de ratios
**no verifica el origen de los datos que consume** — un fact de otra
empresa, insertado bajo el CIK correcto con el tag correcto, se usa sin
ninguna alarma (F-061, severidad HIGH). La defensa existe (identidades
contables), pero es un chequeo separado y no obligatorio.

**Tercer hallazgo:** la clasificación "EV/EBITDA no calculable por falta de
D&A" del ciclo anterior era incorrecta — el dato existe para las 8 empresas
bajo tags que no se habían buscado con fallback (F-062, MEDIUM).

---

## FASE A — Inventario

| dónde se calcula | qué produce | DB | notas |
|---|---|---|---|
| `scripts/engine/ratio_defs.py` | declara conceptos → tags candidatos (fallback), y qué ratios son `publicable` | — | fuente única de verdad de la taxonomía; 14 ratios fundamentales + `pe`/`market_cap`/`price_to_book` declarados en `RATIOS_MERCADO` |
| `scripts/engine/ratios_inventario.py` | inventario completo (todos los ejercicios, las 8 empresas) | `catalaxia:5433` vía `engine.db` | usa `ratio_defs` desde F-056 (antes tenía sus propias listas solo-IFRS) |
| `scripts/engine/e2e_producto.py` | cadena EMPRESA→...→PROVENANCE, última cifra por empresa | ídem | idem F-056; requiere el instrumento enlazado ANTES de llegar a fundamentals (por diseño de la cadena, no del cálculo) |
| `scripts/engine/matriz_producto.py` **(nuevo, este ciclo)** | matriz EMPRESA×RATIO de los 13 pedidos, fundamentales por CIK sin pasar por el instrumento | ídem | resuelve la limitación de e2e_producto.py para BMA |
| `scripts/engine/screener_demo.py` | drill-down completo hasta SHA256 | ídem | ya importaba `ratio_defs` correctamente desde su origen |

### Qué está realmente implementado (código existe y produce valores)

EPS, P/E, ROE, ROA, D/E (`debt_to_equity`), Current Ratio, Quick Ratio,
Gross/Operating/Net Margin. También `cash_ratio`, `borrowings_to_equity`,
`equity_ratio`, `interest_coverage` (no pedidos esta vez, pero existen) y
`effective_tax_rate`/`ocf_to_net_income` (implementados, marcados
`publicable=False` — no forman parte de los 13 pedidos).

### Declarado pero no implementado

`price_to_book` está en `RATIOS_MERCADO` de `ratio_defs.py` — **declarado,
sin código que lo calcule.** `price_to_sales` **ni siquiera está
declarado.**

### Imposible con los datos actuales

Ninguno de los 13. El único caso "imposible" del ciclo anterior
(EV/EBITDA por falta de D&A) se corrigió: el dato existe, el código no
(F-062).

### Taxonomías y fallback soportados

`ratio_defs.CONCEPTOS` declara `ifrs-full` y `us-gaap` para cada concepto
financiero. `taxonomia_de()` clasifica cada filing por sus namespaces
declarados (nunca por país o formulario). Verificado empíricamente en las 8
empresas (Fase D).

---

## FASE B — Matriz EMPRESA × RATIO

**Entregable:** `RATIO_PRODUCT_MATRIX.csv` (104 filas = 8 empresas × 13
ratios), generado por `scripts/engine/matriz_producto.py`, solo lectura.

| estado | filas | qué significa |
|---|---:|---|
| CALCULADO | 66 | valor real, con provenance completa |
| NO_IMPLEMENTADO | 24 | P/B + P/S + EV/EBITDA × 8 empresas — código no existe |
| NO_CALCULABLE | 12 | dato ausente para esa empresa/ratio (mayormente bancos: balance sin clasificación corriente/no-corriente, sin "revenue") |
| BLOQUEADO | 1 | P/E de BMA — instrumento sin enlazar, no falta de dato |
| NULL_VALIDO | 1 | P/E de YPFD — EPS≤0, regla IAMC, resultado correcto |

Cada fila trae: valor, período, moneda, fuente, provenance (tag usado +
accession, cuando aplica) y método (fórmula por concepto). El estado
`NO_CALCULABLE` siempre cita qué tags se buscaron y no se encontraron —
nunca "no disponible" a secas.

### Por qué GGAL y BMA concentran los `NO_CALCULABLE`

Ambos son bancos. Un banco no publica `CurrentAssets`/`CurrentLiabilities`
(su balance no se clasifica en corriente/no-corriente de la forma que un
industrial lo hace) ni `GrossProfit`/`Revenue` en el sentido de una
empresa que vende bienes. Esto es correcto financieramente, no un defecto
de ingesta — pero el sistema hoy lo representa igual que cualquier otro
dato ausente (`NO_CALCULABLE` con motivo "falta X"), sin distinguir "no
aplica por sector" de "debería estar y no está". Es una limitación de
expresividad del estado, no del dato: se documenta para el próximo
contrato, no se corrige en este ciclo.

---

## FASE C — Validación financiera

Cada fórmula usada, exacta, está en `RATIO_CONTRACT.md` (ya existente, sin
tocar). Resumen de lo verificado **de nuevo, con evidencia fresca** en este
ciclo — ver `RATIO_INDEPENDENT_AUDIT.json`:

| validación | definición exacta usada | resultado |
|---|---|---|
| EPS | tag directo (`BasicEarningsLossPerShare` y 4 variantes) vs. `resultado_neto/acciones_promedio` | 8/8 empresas, dif. máx. 0.12% (redondeo del publicado a 2 decimales) |
| Balance | `Assets = Liabilities + Equity` (identidad, no ratio) | 8/8 empresas, 0.0000% desvío, ambas taxonomías |
| Margins | `resultado_neto / ingresos` (net), `resultado_bruto / ingresos` (gross), `resultado_operativo / ingresos` (operating) — **tres fórmulas distintas, nunca intercambiadas** | recalculadas independientemente, 0 divergencias donde había dato |
| ROE | `resultado_neto / patrimonio` (patrimonio de CIERRE, no promedio con el inicial — convención declarada) | ídem |
| ROA | `resultado_neto / activo_total` | ídem |
| D/E | `pasivo_total / patrimonio` (pasivo TOTAL, no solo deuda financiera — distinto de `borrowings_to_equity`) | ídem |
| Current | `activo_corriente / pasivo_corriente` | ídem |
| P/E | `precio / EPS`, con el precio del instrumento cuya moneda coincide con la del EPS, ajustado por `ratio_underlying` | validado por separado — depende de mercado, no de `derived.fact` solo (ver `ratios_multipath.py`, ya existente) |

**Tolerancia usada y por qué:** criterio combinado — OK si la diferencia
relativa ≤ 0.01% **o** la absoluta ≤ 1e-6. Una tolerancia puramente
relativa falla artificialmente cerca de cero (GGAL ROA ≈ 0.0047: una
diferencia absoluta de 5×10⁻⁷, puro redondeo a 6 decimales del motor, da
0.0103% relativo — por encima de un 0.01% relativo solo). La absoluta es la
misma que `ratios_auditoria.py` ya validó sobre 274 ratios sin
divergencias. Resultado con el criterio combinado: **60/60 OK, 0
divergencias.**

**No se comparan fórmulas distintas como si fueran equivalentes.**
`debt_to_equity` (pasivo total) y `borrowings_to_equity` (solo deuda
financiera) son dos ratios separados en el código y en este documento —
nunca se usa uno para validar el otro.

---

## FASE D — Multitaxonomía

| taxonomía | empresas | verificado |
|---|---|---|
| `ifrs-full` | CEPU, TGSU2, GGAL, BMA | Assets=Liabilities+Equity 0.0000%; EPS 0.00-0.00% |
| `us-gaap` | AAPL, MSFT, NVDA | Assets=Liabilities+Equity 0.0000%; EPS 0.02-0.04% |
| `IFRS+US-GAAP` | YPF | reporta 20-F bajo IFRS con elementos `us-gaap`/`srt` accesorios; EPS 0.12% |

Ninguna fórmula usa un tag rígido: cada concepto tiene su cadena de
candidatos en `ratio_defs.CONCEPTOS`, y el tag efectivamente usado queda en
la provenance de cada celda (columna `provenance` del CSV).

### Períodos fiscales — verificado, no calendario

| empresa | último `report_period` | ¿calendario? |
|---|---|---|
| AAPL | 2025-09-27 | NO — cierre a fines de septiembre |
| MSFT | 2026-06-30 | NO — cierre a fin de junio |
| NVDA | 2026-01-25 | NO — cierre a fines de enero |
| YPFD/CEPU/TGSU2/GGAL/BMA | 2025-12-31 | SÍ — coincide con diciembre |

El sistema usa el `report_period` que cada filing declara — no asume
diciembre para ninguna empresa. Los tres US-GAAP de la muestra confirman
que el mecanismo maneja años fiscales no calendario correctamente, no solo
en teoría.

---

## FASE E — Validación de mercado

**Separación central del encargo, y el hallazgo más importante de este
ciclo:**

| capa | qué necesita | ratios que dependen de ella |
|---|---|---|
| Fundamentalmente calculable | solo `derived.fact` por CIK | EPS, ROE, ROA, D/E, Current, Quick, los 3 márgenes |
| Requiere market data | precio de `market_price_daily` | P/E (P/B y P/S también lo requerirían, si estuvieran implementados) |
| Requiere Identity/Instrument link | `identity_v1.instrument` enlazando `MKT:<id>` → `entity_key` | el paso PREVIO a poder usar el precio — sin esto, un precio existente no se puede atribuir a la entidad |

`e2e_producto.py` encadena estas tres capas en orden IDENTITY→SEC_XBRL→
MARKET, así que si el enlace de instrumento falta, **toda la fila queda en
blanco aunque los fundamentals existan.** Eso es correcto para una cadena
end-to-end pero **incorrecto como retrato del producto**: BMA (Macro Bank
Inc., CIK `0001347426`) tiene sus filings ingeridos y **14 ratios
fundamentales calculables** en 2 ejercicios (2024, 2025) — ROE, ROA, D/E,
`effective_tax_rate`, `interest_coverage`, `ocf_to_net_income` — pero su
único P/E queda `BLOQUEADO`, no por falta de EPS (que sí tiene: 452.75 ARS)
sino porque el instrumento `584` no está en `identity_v1.instrument`.

### BYMA, ADRs y ticker local vs. estadounidense

4 de las 8 empresas (CEPU, GGAL, TGSU2, YPFD) tienen **2 instrumentos cada
una** bajo el mismo `ticker_canonico`: uno local (BUE, ARS) y un ADR
(NYSE, USD). El `ticker_canonico` **es ambiguo por diseño** — confirmado
por consulta directa (`market_instruments` agrupado por ticker da count=2
para las 4). La resolución de identidad nunca usa el ticker solo: enlaza
por `instrument_key='MKT:<instrument_id>'`, una clave que sí es única. El
código de cálculo (`e2e_producto.py`, `matriz_producto.py`) siempre itera
por `instrument_id`, nunca resuelve "dame el instrumento de CEPU" sin
especificar cuál. **No se detectó ningún punto donde el sistema resuelva
una identidad de instrumento por ticker ambiguo sin desambiguar** — ver
ataque A11 en la Fase F.

---

## FASE F — Adversarial

**Entregable:** `RATIO_ADVERSARIAL.json`, 13 ataques, banco extendido
`scripts/engine/adversario_ratios.py` (ATK1-ATK6 del ciclo anterior +
ATK7-ATK11 nuevos, cubriendo los 10 vectores del encargo). Corre sobre una
copia descartable de la base; la homologada se verificó bit a bit idéntica
antes y después (control Z).

| # | vector del encargo | ataque | veredicto |
|---|---|---|---|
| 1 | cambiar taxonomía | A7 | produce resultado — ver F-061 |
| 2 | eliminar tag preferido | A8 | correcto: cae al segundo candidato con valor medible distinto |
| 3 | forzar fallback | A8 | mismo ataque que el 2 |
| 4 | cambiar período | A5 | correcto: filtro de período lo excluye |
| 5 | EPS negativo | evidencia existente (YPFD real) | correcto: P/E → NULL, nunca negativo |
| 6 | revenue inexistente | A9 | correcto: NO_CALCULABLE con motivo, nunca 0 |
| 7 | denominador = 0 | A3 | correcto: NO_CALCULABLE "denominador=0", nunca infinito |
| 8 | shares inexistentes | A10 | correcto: no crashea |
| 9 | ticker ambiguo | A11 | correcto: resuelto por `instrument_id`, nunca por ticker solo |
| 10 | fact de otra empresa | A2 + A7 | **produce resultado incorrecto — F-061, severidad HIGH** |

**2 findings registrados** (ninguno corregido en este ciclo, salvo lo
estrictamente necesario para completar la prueba — ver política del
encargo):

- **F-061 (HIGH):** la capa de ratios no verifica el origen de sus
  insumos. Un fact insertado bajo el CIK correcto, con el tag correcto,
  se usa sin ninguna alarma — incluso cuando ese fact pertenece
  literalmente a otra empresa (A7: `current_ratio` "de GGAL" resultó ser,
  dígito por dígito, el de AAPL). La defensa existe (identidad contable),
  pero es un control separado y no obligatorio antes de publicar.
- **F-062 (MEDIUM):** la clasificación "EV/EBITDA no calculable, falta
  D&A" del ciclo anterior era incorrecta — el dato existe, el código no.

---

## FASE G — Auditoría independiente

**Entregable:** `RATIO_INDEPENDENT_AUDIT.json`, `scripts/engine/independent_audit_matrix.py`
— no importa `ratio_defs.py` ni `matriz_producto.py`; declara su propia
tabla de tags candidatos y recalcula con `Decimal` vía `psql` directo.

**60 comparaciones `engine_result` vs. `independent_result`, 60 OK, 0
divergentes.** Cobertura: los 9 fundamentales (ROE, ROA, D/E, Current,
Quick, 3 márgenes) donde había CALCULADO, más EPS, en las 8 empresas. P/E,
P/B, P/S y EV/EBITDA quedan `FUERA_DE_ALCANCE` de este recálculo puntual
(P/E ya se valida por camino doble en `ratios_multipath.py`/
`ratios_auditoria.py`; los otros tres no tienen `engine_result` que
reproducir por estar `NO_IMPLEMENTADO`).

Esto se suma, sin reemplazarlo, a lo ya existente: `ratios_auditoria.py`
(274/274 reproducidos sobre el inventario completo, todos los ejercicios)
y `audit_provenance_ratios.py` (8/8 controles de identidad conceptual,
contextos y SHA256).

---

## Correcciones de contrato registradas en este ciclo

Por la regla del encargo ("no modificar contratos existentes sin registrar
primero el cambio"):

1. **EV/EBITDA**: `RATIO_CONTRACT.md` §13 y `RATIO_COVERAGE_MATRIX.md`
   §1.4/§6/§7 corregidos de `NOT_CALCULABLE` a `NO_IMPLEMENTADO`, con la
   justificación completa en `docs/review/F062_FINDING.md`.

Nada más se modificó en los documentos de contrato existentes.

---

## Siguiente sección: ver `PRODUCT_DEMO_READINESS.md`

Ese documento traduce todo lo anterior en la tabla DEMO
READY/WARNING/NOT_READY por empresa y por ratio, y el veredicto de si se
puede mostrar un screener de las 8.
