# METR FY2025 · MAPA DE DEPENDENCIAS RAÍZ DE LOS 63 NO_INPUT

**Sprint de análisis. No se implementó nada.** No se modificó producción, ni el
modelo de datos, ni conceptos, ni mappings, ni fórmulas, ni tolerancias, ni el
gate. Todo acceso a datos fue *read-only*: `screener.db` abierta con
`mode=ro`, el corpus RAW leído sin escritura, y ninguna conexión a PostgreSQL
de producción.

---

## 1 · Resumen ejecutivo

Las **63 métricas NO_INPUT no son 63 problemas.** Son **11 dependencias raíz**,
y **cinco de ellas explican el 81 %**.

El hallazgo que ordena todo lo demás: **47 de las 63 métricas (75 %) fallan
porque el dato no existe en ningún documento de la CNV** — no porque Catalaxia
lo extraiga mal. Se verificó con un censo completo del corpus RAW: **7.935
documentos, 113 códigos distintos**. En esos 113 códigos **no hay capex, no hay
cantidad de acciones, no hay dividendos, no hay PP&E bruto ni depreciación
acumulada**, y el estado de flujos de efectivo tiene **exactamente seis
códigos, de los cuales los cuatro comunes son subtotales**.

Eso cambia la naturaleza del trabajo pendiente. Ninguna cantidad de mejor
parsing sobre los EEFF resumidos va a producir estas métricas: hacen falta
**fuentes nuevas** (notas contables, nota de segmentos, datos de mercado).

La segunda distinción, igual de importante:

| | métricas | qué significa |
|---|---:|---|
| **Falta el dato: requiere una fuente nueva** | 48 | clases E + D — no está en ningún documento |
| **El dato existe, difiere la definición** | 15 | clases G + F — Catalaxia sí lo tiene; TIKR usa otro concepto |

Las 15 de la segunda fila **no se arreglan agregando datos**. Resolverlas
significaría adoptar una definición de TIKR que el documento no demuestra —
exactamente el tipo de calibración que este sprint tiene prohibido.

Sólo **una** dependencia es atacable hoy con lo ya descargado: **D08**, los tres
códigos de gastos operativos. Es P0 por costo, no por impacto: desbloquea 2
métricas y **agrega cobertura canónica real**, pero **no produce paridad con
TIKR** — y no debe forzarse para que lo haga.

---

## 2 · El universo: las 63 métricas

Punto de partida: los 66 NO_INPUT clasificados en
`METR_TIKR_2025_GAP_CLASSIFICATION.csv`, menos las **3 resueltas** por el sprint
anterior (`Asset Devaluation`, `Minority Interest`,
`Other Comprehensive Income / Other`).

Verificado: **exactamente 63, sin duplicados, ninguna nueva.**

| matriz de origen | métricas |
|---|---:|
| `METR_TIKR_2025_FACT_MATRIX.csv` | 45 |
| `METR_TIKR_2025_RATIO_MATRIX.csv` | 10 |
| `METR_TIKR_2025_SEGMENT_MATRIX.csv` | 8 |
| **total** | **63** |

Todas comparten el mismo `current_status`: **`CATALAXIA_MISSING_INPUT`**. Lo que
las diferencia no es el síntoma sino la causa, y ése es el objeto de este mapa.

---

## 3 · Las 11 dependencias raíz

Una dependencia raíz es un **hecho, concepto o fuente primaria** cuya ausencia
explica una o más métricas. No es una métrica: `Capital Expenditures` es a la
vez una métrica faltante y el insumo de otras cuatro, pero la **raíz** es el
desglose del estado de flujos que lo contendría.

| id | dependencia | métricas | clase | fuerza | prio |
|---|---|---:|---|---|---|
| **D01** | Desglose del estado de flujos de efectivo | 18 | E | HIGH | P2 |
| **D02** | Desglose del balance más allá de los subtotales | 12 | E | HIGH | P2 |
| **D03** | Definición de deuda financiera de TIKR | 9 | G | MEDIUM | P2 |
| **D05** | Segmentación operativa (MetroENERGY / eliminaciones) | 8 | E | HIGH | P2 |
| **D06** | Partidas no operativas e inusuales del resultado | 4 | E | MEDIUM | P2 |
| **D04** | Cantidad de acciones en circulación | 3 | E | HIGH | **P1** |
| **D07** | Desagregación de los resultados financieros | 2 | G | HIGH | P2 |
| **D08** | Desagregación de gastos operativos (SG&A) | 2 | G | MEDIUM | **P0** |
| **D09** | Dividendos declarados y precio de mercado | 2 | E | HIGH | P2 |
| **D10** | FFO de TIKR | 2 | F | HIGH | P2 |
| **D11** | Comparativo de caja de apertura | 1 | D | HIGH | P2 |
| | | **63** | | | |

Clases heredadas de la clasificación forense previa: **D** requiere comparativo ·
**E** no publicado por la CNV · **F** específico de TIKR · **G** semánticamente
ambiguo. (Las clases **A**, **B** y **C** — dato existente, dato en RAW,
derivable — quedaron vacías: **ninguna de las 63 se resuelve con lo que ya
está en casa**, que es precisamente lo que las diferencia de los 3 gaps que el
sprint anterior sí pudo cerrar.)

---

## 4 · Grafo conceptual

Lo que la flecha significa: *B no existe mientras A no exista.*

```
                        ┌─ NOTAS CONTABLES (no descargadas) ─┐
                        │                                     │
              D01 desglose del flujo          D02 desglose del balance
                        │                                     │
        ┌───────────────┼───────────────┐                     │
        │               │               │                     │
     capex        líneas de CFO     líneas de CFF        11 partidas
        │               │               │                +Unearned Revenue
   ┌────┴────┐          │               │
   │         │          └──── 13 métricas ────┘
  FCF   ratios de                                    D05 nota de segmentos
   │    cobertura                                            │
   │    (4 ratios)                                  ┌────────┴────────┐
   │                                          MetroENERGY      eliminaciones
   └── D10 FFO (además necesita                    (4)              (4)
        la definición de TIKR)                      └──── acopladas ────┘

   D04 cantidad de acciones ──► BV/share · TBV/share · CF/share
        (fuente externa: prospecto / BYMA / nota de capital)

   D03 definición de deuda ──► 8 partidas de balance + Return on Capital
        (el dato canónico YA existe; lo que falta es el concepto de TIKR)

   D09 dividendos + precio ──► DPS · Dividend Yield
   D07 split financiero     ──► Interest Income · FX Gains/Losses
   D08 gastos operativos    ──► SG&A Margin · EBITA Margin
   D06 otros resultados     ──► 4 partidas no operativas
   D11 caja de apertura     ──► Cash Beginning
```

Dos acoplamientos que conviene leer antes de planificar:

- **D01 → D10.** El FFO no sólo necesita el flujo desagregado: necesita además
  la definición del numerador, que TIKR no publica. Resolver D01 **no** resuelve
  D10.
- **D05 está internamente acoplada.** `CONSOLIDADO − INDIVIDUAL` da MetroENERGY
  y las eliminaciones **sumados**: una ecuación, dos incógnitas. Las 4 métricas
  de MetroENERGY sólo se resuelven si además se obtienen las eliminaciones. **No
  se puede atacar media dependencia.**

---

## 5 · Agrupación por familia

| familia | métricas | dependencias raíz |
|---|---:|---|
| `balance` | 20 | D02 (12), D03 (8) |
| `cashflow` | 16 | D01 (14), D11 (1), D04 (1) |
| `ratio` | 10 | D01 (4), D08 (2), D10 (2), D03 (1), D09 (1) |
| `segment` | 8 | D05 (8) |
| `income` | 7 | D06 (4), D07 (2), D09 (1) |
| `perhare` | 2 | D04 (2) |
| **total** | **63** | |

La lectura útil no es la familia sino la **fuente que haría falta**:

| fuente necesaria | dependencias | métricas | % |
|---|---|---:|---:|
| Notas contables (flujo + balance detallados) | D01, D02 | 30 | 48 % |
| Una definición de TIKR, no un dato | D03, D07, D08, D10 | 15 | 24 % |
| Nota de segmentos | D05 | 8 | 13 % |
| El emisor no lo declara (existe en el plan) | D06 | 4 | 6 % |
| Fuente externa (acciones, dividendos, precio) | D04, D09 | 5 | 8 % |
| Reexpresión IAS 29 de un comparativo | D11 | 1 | 2 % |
| **total** | | **63** | |

**Casi la mitad del backlog es un único proyecto de ingesta**: descargar y
parsear las notas contables.

---

## 6 · Métricas por dependencia

Detalle completo en `METR_TIKR_2025_DEPENDENCY_MATRIX.csv` (63 filas, una por
métrica, con el rol que cumple dentro de su raíz).

**D01 · Desglose del flujo — 18 métricas**
`Capital Expenditures` · `Cash Interest Paid` · `Cash Taxes Paid` ·
`Change in Accounts Payable` · `Change in Accounts Receivable` ·
`Change in Other Net Operating Assets` · `Debt Issued` · `Debt Repaid` ·
`Free Cash Flow` · `Investment in Securities/Equity` ·
`Levered FCF Margin` · `Net Debt / (EBITDA - Capex)` ·
`Other Financing Activities` · `Other Investing Activities` ·
`Other Operating Activities` · `Purchase/Sale of Intangibles` ·
`Unlevered FCF Margin` · `(EBITDA - Capex) / Interest Expense`

De las 18, **13 son líneas del estado de flujos** y **5 son derivadas que
dependen del capex**. El capex es el nodo con más carga individual del mapa.

**D02 · Desglose del balance — 12 métricas**
`Accrued Expenses` · `Accumulated Depreciation` · `Buildings` ·
`Construction in Progress` · `Current Portion Capital Leases` ·
`Current Unearned Revenue` · `Gross PP&E` · `Land` · `Other Current Assets` ·
`Other Current Liabilities` · `Other Receivables` · `Prepaid Expenses`

**D03 · Definición de deuda — 9 métricas**
`Current Income Taxes Payable` · `Current Portion Long-Term Debt` ·
`Long-Term Debt` · `Long-Term Investments` ·
`Non-Current Deferred Tax Liabilities` · `Other Long-Term Assets` ·
`Other Non-Current Liabilities` · `Return on Capital` · `Short-Term Investments`

**D05 · Segmentos — 8 métricas**  ·  4 de MetroENERGY Marketing y 4 de
Eliminations, sobre `Operating Revenue`, `Operating Income`,
`Net Income Common Stockholders` y `Total Assets`.

**D06 · Partidas no operativas — 4** · `EBT excl. Unusual Items` ·
`Gain/Loss on Sale of Investments` · `Legal Settlements` ·
`Other Non-Operating Income/Expense`

**D04 · Acciones — 3** · `Book Value / Share` · `Cash Flow per Share` ·
`Tangible Book Value / Share`

**D07** `FX Gains/Losses` · `Interest Income` — **D08** `EBITA Margin` ·
`SG&A Margin` — **D09** `Dividend Yield` · `Dividends per Share` —
**D10** `FFO / Interest Expense` · `FFO / Total Debt` —
**D11** `Cash Beginning`

---

## 7 · Leverage

| dependencia | métricas | leverage | ¿atacable hoy? |
|---|---:|---|---|
| D01 | 18 | 29 % del backlog en una fuente | no — falta la fuente |
| D02 | 12 | 19 % en la misma fuente que D01 | no — falta la fuente |
| D03 | 9 | 14 %, pero es definicional | **no debe atacarse** |
| D05 | 8 | 13 %, acoplada internamente | no — falta la fuente |
| D08 | 2 | 3 % | **sí — ya está descargado** |

El leverage y la accionabilidad **apuntan en direcciones opuestas**. Las
dependencias que más desbloquean son las que menos se pueden atacar hoy, y la
única atacable desbloquea dos métricas. Planificar por leverage crudo llevaría
a un sprint que no puede terminar.

El leverage real de D01+D02 no está en el conteo de métricas sino en que
**comparten fuente**: un solo proyecto de ingesta de notas contables toca 30 de
las 63.

---

## 8 · Conjunto mínimo

Cobertura acumulada tomando las raíces de mayor a menor:

| raíces | acumulado | cobertura |
|---:|---:|---:|
| 1 (D01) | 18 | 29 % |
| 2 (+D02) | 30 | 48 % |
| 3 (+D03) | 39 | 62 % |
| 4 (+D05) | 47 | 75 % |
| 5 (+D06) | 51 | 81 % |
| 6 (+D04) | 54 | 86 % |
| 11 (todas) | 63 | 100 % |

**El conjunto mínimo que cubre ≥ 80 % es {D01, D02, D03, D05, D06} — cinco
raíces.** Pero D03 y D06 no son proyectos de ingesta: D03 es definicional y D06
es un gap del emisor. **El conjunto mínimo *ejecutable* es {D01, D02, D05}**:
tres raíces, una sola clase de fuente (notas contables y nota de segmentos), 38
de 63 métricas — **60 %**.

> Estas 38 quedarían **POTENTIALLY_UNLOCKED**, no en MATCH. Tener el insumo es
> condición necesaria, no suficiente: cada métrica seguiría teniendo que pasar
> por la reconciliación semántica contra TIKR.

---

## 9 · Prioridades

### P0 — atacable ahora, con lo que ya está descargado

**D08 · Desagregación de gastos operativos.** Los tres códigos ya están en el
RAW de METR: `3011200` GASTOS DE COMERCIALIZACION Y/O DISTRIBUCION (128.411, en
54 de 57 documentos), `3011300` OTROS GASTOS DE ADMINISTRACION (87.580, en 56) y
`3011301` HONORARIOS A DIRECTORES Y SINDICOS (772, en 54). Es la misma cadena de
extracción que el sprint anterior ya ejercitó con éxito sobre cuatro códigos.

**Advertencia que debe acompañar a este P0:** desbloquea **cobertura canónica**,
**no paridad con TIKR**. Los tres suman 216.763; el SG&A Margin de TIKR (13,0 %
sobre 1.217.305) implica 158.250. **Ninguna combinación evidente de los tres
reproduce esa cifra — NO DEMOSTRADO.** El entregable correcto es publicar el
desglose propio de la CNV, no calibrar hacia 158.250.

### P1 — máxima relación métricas / esfuerzo, pero exige una fuente externa

**D04 · Cantidad de acciones en circulación.** Es un **único número por
ejercicio** y desbloquea 3 métricas directamente, más cualquier métrica *per
share* futura. No está en la CNV (verificado sobre los 7.935 documentos), así
que requiere prospecto, BYMA o la nota de capital.

> **Prohibido explícitamente:** usar `Capital = 569` como cantidad de acciones.
> La coincidencia con las 569 acciones de TIKR ya fue investigada y descartada;
> `2210999` es capital social expresado en moneda. El test
> `test_v9_capital_no_es_cantidad_de_acciones` bloquea esa reintroducción.

### P2 — todo lo demás

D01, D02, D05 esperan un proyecto de ingesta de notas. D03, D06, D07, D09, D10 y
D11 **no deberían implementarse** (§10).

---

## 10 · Lo que NO hay que implementar

| dependencia | por qué no |
|---|---|
| **D03** deuda | El dato canónico **ya existe y es correcto**: el desglose de pasivos financieros de la CNV **cierra exacto** (`2312200` 290 + `2312300` 73.480 + `2312400` 108.506 = `2319999` 182.276; `2321999` 145.428 + `2322100` 30.948 + `2322200` 71.079 = `2339999` 247.455). La diferencia con TIKR (144.559 vs 86.550 = **58.009**) es de **definición**, no de extracción. Cerrarla exigiría adoptar un concepto de deuda que el documento no demuestra. |
| **D07** split financiero | `3021400` y `3021500` ya están en Catalaxia y son correctos. Separarlos en intereses vs FX no es posible desde el documento. |
| **D06** otros resultados | **CORREGIDO (F-062):** METR **sí declara** `3021900 OTROS RESULTADOS` — en **60 de 60** documentos, **con valor nil (guion)**. La medición anterior sólo contaba códigos con valor numérico y por eso lo dio por ausente. El concepto existe y vale cero, así que no hay nada que extraer *como importe*, pero la conclusión es distinta: no es un gap del emisor sino un cero declarado. |
| **D10** FFO | TIKR publica los dos ratios pero **no el FFO ni su definición**. Reconstruir el numerador sería calibrar contra el resultado. |
| **D11** caja de apertura | Exigiría reexpresar el cierre 2024 bajo IAS 29 con un índice que Catalaxia no tiene — o inventar el saldo. |
| **D09** dividend yield | El rendimiento no es un dato del estado financiero. |

**Regla general:** cuando el dato canónico ya existe y lo que difiere es la
definición, la acción correcta es **documentar la diferencia**, no ajustar el
dato. Ajustarlo convertiría una diferencia semántica legítima en una
calibración, y haría que el score contra TIKR dejara de medir nada.

---

## 11 · Gaps de cobertura de la CNV

Censo completo del corpus: **7.935 documentos, 113 códigos distintos**. Lo que
**no existe en ninguno de los 113**:

| concepto buscado | patrón sobre las etiquetas | resultado |
|---|---|---|
| capex | `ADQUISIC` `COMPRA` `INCORPORAC` `BIENES DE USO` | **0** — sólo `1110100 PROPIEDADES PLANTAS Y EQUIPOS`, que es el saldo **neto** del balance |
| cantidad de acciones | `ACCION` `ACCIONES` | **0** — sólo `8000000` y `8000001`, que son el **EPS** |
| dividendos | `DIVIDEND` | **0** |
| PP&E bruto / depre. acumulada | `ACUMULAD` `VALOR DE ORIGEN` | **0** |
| terrenos / edificios / obras en curso | `TERRENO` `EDIFICIO` `OBRAS EN CURSO` | **0** |
| leasing | `LEASING` `ARRENDAM` | **0** |
| ingresos diferidos / anticipos | `DIFERID` `ANTICIPO` | sólo `1122900` (activo por impuesto diferido) |

El estado de flujos completo del plan de cuentas de la CNV:

| código | etiqueta | documentos | METR |
|---|---|---:|---|
| `3240000` | INCREMENTO (DISMINUCION) NETA DE EFECTIVO Y EQUIVALENTES | 2.463 | 56 |
| `3241100` | TOTAL CAMBIOS EN ACTIVOS Y PASIVOS OPERATIVOS | 2.462 | 56 |
| `3241200` | TOTAL DE ACTIVIDADES DE INVERSION | 2.383 | 56 |
| `3241300` | TOTAL DE ACTIVIDADES DE FINANCIACION | 2.333 | 56 |
| `3241400` | EFECTO DE LAS VARIACIONES DEL TIPO DE CAMBIO | 89 | **0** |
| `3241500` | EFECTO DEL RESULTADO MONETARIO DE EFECTIVO Y SUS EQUIVALENTES | 87 | **0** |

**Seis códigos, y los cuatro comunes son subtotales.** El estado de flujos de la
CNV no es un estado de flujos: es su renglón final. Todo lo que TIKR publica
como línea de flujo vive en las notas.

### Un matiz que corrige una afirmación anterior

En un informe previo di por sentado que la CNV no tenía ningún desglose de
resultados financieros. **Sí lo tiene**, y conviene dejarlo asentado:
`3021501 RDOS FINANCIEROS GENERADOS POR ACTIVOS` (21 documentos) y
`3021502 … POR PASIVOS` (25). No cambia la conclusión — lo usan 21 y 25 de
7.935 documentos, METR no está entre ellos, y separan por **origen**, no en
intereses vs FX — pero la afirmación absoluta era incorrecta.

### Gap de emisor, no de formato

Distinto de todo lo anterior: **`3021900 OTROS RESULTADOS` existe** (1.551 de
7.935 documentos) y **METR simplemente no lo declara** (0 de 57). El dato
existiría si METR lo presentara. Al ampliar la cobertura a otras empresas, esta
dependencia **se cierra sola para los emisores que sí lo declaran**.

Lo mismo con `2311600 OBLIGACIONES NEGOCIABLES EMITIDAS`: existe en el plan,
METR no lo declara.

---

## 12 · Gaps específicos de TIKR

**15 de las 63** (clases G y F) no son un problema de cobertura: el dato existe
en Catalaxia — o, en el caso de D08, en el RAW ya descargado — y lo que difiere
es qué se considera parte del concepto.

| dependencia | Catalaxia tiene | TIKR usa | Δ |
|---|---|---|---|
| D03 | Pasivos financieros 144.559 | Deuda 86.550 | 58.009 |
| D07 | Ingresos financieros 43.721 / Costos 52.522 | Interest Income 17.052, FX −3.121 | — |
| D08 | 3 códigos de gastos = 216.763 | SG&A implícito 158.250 | 58.513 |
| D10 | — | FFO (definición no publicada) | — |

**Ninguna de estas Δ está demostrada como error.** Marcarlas como fallas de
Catalaxia sería tan incorrecto como cerrarlas por calibración. La acción es
documentar la diferencia de definición y dejar la métrica fuera del score de
paridad, no dentro del backlog de implementación.

---

## 13 · Comparativos

La CNV publica **un solo comparativo de apertura**: `8000002 TOTAL PATRIMONIO
NETO DEL EJERCICIO ANTERIOR`, presente en 51 de los 57 documentos de METR. El
sprint anterior ya lo incorporó, y con él resolvió `ROE` exactamente contra el
propio ratio `8000009` de la CNV.

**No existe el equivalente para la caja.** Se buscó en los 113 códigos y ninguno
tiene un valor cercano a los 160.859 que informa TIKR. `3241400` y `3241500` son
efectos **sobre** el efectivo, no el saldo inicial — y METR no los declara.

Consecuencia para el diseño: **`8000002` es la excepción, no el patrón.** No hay
un mecanismo general de comparativos en el EEFF de la CNV que se pueda extender
a otras cuentas. `Cash Beginning` queda como **NO DEMOSTRADO / no implementable**
sin reexpresar el cierre 2024 bajo IAS 29.

---

## 14 · Acciones

`D04` es la dependencia con mejor relación entre esfuerzo y métricas
desbloqueadas del mapa: **un número por ejercicio**, que desbloquea
`Book Value / Share`, `Tangible Book Value / Share` y `Cash Flow per Share` —
y habilita cualquier métrica *per share* futura, incluida la validación cruzada
del EPS que la CNV sí publica.

Verificación negativa, sobre los 7.935 documentos: los **únicos dos** códigos
cuya etiqueta menciona ACCION son `8000000 GANANCIA (PERDIDA) BASICA POR ACCION`
(2.278 documentos) y `8000001` diluida (1.998). Ambos son el **cociente**, no el
denominador.

> **`Capital = 569` no es una cantidad de acciones.** `2210999` es capital social
> expresado en moneda. Que coincida con las 569 acciones que informa TIKR es una
> coincidencia numérica ya investigada y descartada, y este mapa la deja
> explícitamente prohibida: D04 queda registrada como `derivable = no`, y hay un
> test que falla si alguien la marca derivable.

---

## 15 · Cash flow

La dependencia de mayor leverage del mapa (18 métricas, 29 %) y **la más lejos
de estar resuelta**.

Catalaxia tiene los cuatro subtotales que METR declara. TIKR publica ~13 líneas
de detalle que **no existen en ningún documento del corpus**. La brecha no es de
extracción: es que el EEFF resumido de la CNV **no contiene un estado de flujos
desagregado**.

El capex merece mención aparte porque concentra el acoplamiento: además de ser
una métrica faltante, es el insumo de `Free Cash Flow`, `Levered FCF Margin`,
`Unlevered FCF Margin`, `(EBITDA − Capex) / Interest Expense` y
`Net Debt / (EBITDA − Capex)`. **Un solo dato desbloquearía 6 de las 18** — pero
ese dato no está en el corpus.

---

## 16 · Deuda

El caso más instructivo del mapa, porque **Catalaxia no tiene un problema de
datos aquí**. El desglose de pasivos de la CNV está completo y **cierra exacto**:

```
no corriente   2312200      290
             + 2312300   73.480   PASIVOS FINANCIEROS NO CORRIENTES
             + 2312400  108.506
             = 2319999  182.276   ✓

corriente      2321999  145.428
             + 2322100   30.948
             + 2322200   71.079   PASIVOS FINANCIEROS CORRIENTES
             = 2339999  247.455   ✓

total          2399999  429.731   ✓
```

Catalaxia deriva Total Debt = 71.079 + 73.480 = **144.559**. TIKR informa
**86.550**. La diferencia de **58.009** es la distancia entre *pasivos
financieros* (concepto de la CNV) y *debt* (concepto de TIKR, más estrecho).

Las 8 partidas de balance de D03 son todas del mismo tipo: TIKR corta el pasivo
y el activo por líneas que la CNV no expone. **No son extraíbles y no son
derivables**; y `Return on Capital` cuelga de ellas porque el capital invertido
necesita justamente esa definición de deuda.

---

## 17 · Segmentos

Ninguno de los 113 códigos lleva dimensión de segmento — el plan de cuentas de
la CNV es plano. Lo único reconstruible es la diferencia de perímetros:

```
Revenue   CONSOLIDADO 1.217.305 − INDIVIDUAL 959.320 = 257.985
TIKR      MetroENERGY 309.208 + Eliminations (−51.223) = 257.985   ✓
```

La identidad **cierra**, y confirma que la lectura de perímetros de Catalaxia es
correcta. Pero es **una ecuación con dos incógnitas**: no permite separar
MetroENERGY de las eliminaciones.

Por eso las 8 métricas son una sola dependencia y no dos. Obtener sólo la nota
de segmentos con las cifras de MetroENERGY permitiría además despejar las
eliminaciones por diferencia — pero **hasta entonces las 4 y las 4 están
acopladas**, y un sprint que ataque la mitad no cierra ninguna.

---

## 18 · Conclusiones

1. **63 NO_INPUT se reducen a 11 dependencias raíz.** Cinco explican el 81 %.

2. **La causa dominante no es Catalaxia.** 47 de 63 (75 %) fallan porque el dato
   no existe en ninguno de los 7.935 documentos del corpus. Ningún sprint de
   parsing las resuelve.

3. **Casi la mitad del backlog es un único proyecto de ingesta.** D01+D02 = 30
   métricas comparten una sola fuente: las notas contables. Es la decisión de
   mayor consecuencia del roadmap, y es una decisión de **ingesta**, no de
   cálculo — coherente con lo que ya sabemos del cuello de botella del producto.

4. **15 métricas no deben implementarse** (D03, D07, D08, D10). El dato existe;
   lo que difiere es la definición de TIKR. Cerrarlas sería calibrar. A ellas se
   suman D06 (4) y D11 (1), que tampoco son implementables, por razones
   distintas: el emisor no declara el concepto, y el comparativo no existe.

5. **Sólo D08 es atacable hoy**, y desbloquea 2 métricas de **cobertura**, no de
   paridad. Su valor es que es barato y correcto, no que mueva el score.

6. **D04 (acciones) es el mejor candidato para el sprint siguiente** si se acepta
   incorporar una fuente externa: un número por ejercicio, 3 métricas, y
   habilita toda la familia *per share*.

7. **Leverage y accionabilidad apuntan en direcciones opuestas.** Priorizar por
   conteo de métricas produciría un sprint que no puede terminar. La
   priorización de este mapa es por **fuente disponible**, no por impacto.

### Lo que queda NO DEMOSTRADO

- Que alguna combinación de `3011200/3011300/3011301` reproduzca el SG&A de
  TIKR (158.250). Suman 216.763; la diferencia no tiene explicación documental.
- Qué define exactamente TIKR como *debt* (86.550) frente a los pasivos
  financieros de la CNV (144.559).
- La definición del FFO de TIKR: el benchmark publica los ratios, no el
  numerador.
- La separación de MetroENERGY y eliminaciones: una ecuación, dos incógnitas.

Ninguno de estos huecos se rellenó con suposiciones.

---

## Método y reproducibilidad

| | |
|---|---|
| script | `scripts/engine/c4_metr_tikr_dependencias.py` (read-only, sin escritura a DB) |
| tests | `tests/test_metr_tikr_2025_dependency_mapping.py` — **23 pasan** |
| censo del corpus | 7.935 documentos HTML, 113 códigos, mismo aplanado de texto que `job5.parse` |
| acceso a datos | `screener.db` abierta con `?mode=ro`; PostgreSQL de producción **no consultado** |
| entregables | `METR_TIKR_2025_DEPENDENCY_MAP.csv` (11 filas × 17 campos) · `METR_TIKR_2025_DEPENDENCY_MATRIX.csv` (63 filas) · este informe |

**Mutaciones adversariales** (todas detectadas): borrar una asignación · duplicar
una métrica en dos raíces · inflar `metric_count` · marcar P0 algo sin insumo ·
inyectar el token de garantía de match · vaciar la evidencia · declarar extraíble una clase
E · reintroducir `Capital → acciones`.

---

```
DEPENDENCY_MAPPING = COMPLETE
UNIVERSO           = 63 / 63 asignadas, particion verificada
DEPENDENCIAS_RAIZ  = 11
CONJUNTO_MINIMO    = {D01, D02, D03, D05, D06} -> 81 %
CONJUNTO_EJECUTABLE= {D01, D02, D05}           -> 60 %  (una sola fuente)
P0 = D08   P1 = D04   P2 = las 9 restantes
IMPLEMENTADO       = NADA (sprint de analisis)
PRODUCCION_TOCADA  = NO
```
