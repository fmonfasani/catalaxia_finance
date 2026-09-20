# F-062 · CNV TAG & RATIO DISCOVERY — METROGAS

> **CORRECCIÓN (GATE 2).** Este informe caracterizó los 226 documentos no
> extraíbles como *"la página de espera del visor de la CNV"*, es decir como
> descargas que no capturaron nada. **Es incorrecto: ninguno está vacío y
> ninguno falló.** Se parten en dos poblaciones con causa distinta:
>
> | | n | qué son |
> |---|---:|---|
> | `ATTACHMENT_ONLY` | **197** | presentaciones de **2000–2018** cuyo estado contable es un **PDF adjunto**. La página trae la metadata del archivo (`TipoDeDocumento` = "Balance Consolidado" 142 / "Balance Subsidiaria" 55, `NombreDocumento`, `FechaAlta`) y nada más |
> | `OTHER_FORM` | **29** | el **formulario de participaciones en sociedades**, con datos reales: `MetroEnergía S.A.`, 95 % del capital y de los votos |
>
> La transición no es casual: la CNV pasó del PDF adjunto al formulario
> estructurado **en 2018-2019**. Antes de 2019 el 100 % son adjuntos; desde
> 2019, el 100 % son estructurados. Por eso los 60 documentos con datos
> empiezan justo ahí.
>
> **Consecuencia:** el techo de 60 documentos no es un defecto del downloader,
> es la frontera del formato. Existe recuperación (`c3_cnv_fetch.py
> --adjuntos-presentaciones`) pero devuelve PDF, que el pipeline no parsea.
> Evidencia en `CNV_INGESTION_CENSUS.csv`.

**METR · CUIT 30657863676 · worktree `catalaxia-cnvmig` · fixture
`metr_golden.db` · sólo lectura sobre `screener.db` y el RAW**

No se modificó el extractor, ni el ratio engine, ni SEC, ni producción, ni la
`cnvmig` certificada. No se calculó ni persistió ningún ratio. Este sprint es
medición.

---

## 1 · Resumen ejecutivo

El techo de extracción de CNV es **medible y está lejos del 100 %**:

```
DOCUMENTOS      286 seleccionados  ->   60 reales   (226 son shells del visor)
TAGS             81 declarados     ->   51 en canonical      (63 %)
OBSERVACIONES  4.028 con valor     -> 2.891 reconocidas      (71,8 %)
                                      1.137 PERDIDAS         (28,2 %)
RATIOS            57 inventariados ->   38 CALCULABLE        (67 %)
```

**Cada pérdida tiene causa.** No hay residuo sin explicar:

| causa | códigos | observaciones | ¿bug? |
|---|---:|---:|---|
| `NO_ESTA_EN_CODIGOS` | 25 | **1.137** | no — limitación del vocabulario |
| `NIL_DESCARTADO` | 5 | 258 | **sí** — un nil declarado es un dato |
| `RUIDO_REGEX` | (1.082 matches) | — | no — falso positivo del detector |

**El hallazgo que decide el roadmap: 17 de los 25 códigos perdidos son
estructurales.** Aparecen en el 23–31 % de los 7.935 documentos del corpus
completo, no sólo en METR. **Agregarlos al diccionario `CODIGOS` beneficia a
todos los emisores, no a uno.**

Y es barato: son 25 líneas en un diccionario, contra un proyecto de ingesta de
notas contables.

---

## 2 · ¿Cuántos documentos reales tiene METR? (FASE 1)

| clase | n | % |
|---|---:|---:|
| `PROCESSED_OK` | **56** | 19,6 % |
| `REAL_DOCUMENT` sin procesar | **4** | 1,4 % |
| `PARSE_FAILURE` | 0 | — |
| **`EMPTY_SHELL`** | **226** | **79,0 %** |
| `PERSISTENCE_REJECTION` | 0 | — |
| `INVALID_DOWNLOAD` | 0 | — |
| **TOTAL** | **286** | |

> **Este census mide el estado de producción** (`screener.db`), a diferencia del
> Golden Run, que mide el fixture después de recuperar los 4 pendientes. Los
> mismos 60 documentos reales dan `56 OK + 4 sin procesar` acá y
> `58 OK + 2 rechazados por PK` allá. No son mediciones en conflicto: son dos
> momentos de la misma cadena, y la diferencia es exactamente el trabajo que el
> Golden Run hizo.

**Documentos reales: 60.** Los otros 226 son la página de carga del visor de la
CNV: 50–78 KB de UI, **0 códigos con valor**, sin `FechaCierre`, sin
`TipoBalance`. El sistema no valida que una descarga contenga un documento.

De los 4 sin procesar, el Golden Run demostró que **2 se extraen sin problema**
y **2 chocan con la PK económica** de `cnv_estados_v2`, que no tiene lugar para
dos presentaciones del mismo período (ver `METROGAS_GOLDEN_RUN_REPORT.md` §4).

Cobertura temporal de los 60 reales: **2018 → 2025**, 8 documentos por año
salvo 2018 (2) y 2020/2021 (9).

`CNV_METR_DOCUMENT_CENSUS.csv` — 286 filas × 15 campos.

---

## 3 · ¿Cuántos tags existen? (FASE 3)

**81 conceptos declarados** en los 60 documentos reales: 76 con valor numérico
y 5 más declarados como **nil** (guion).

| familia | conceptos |
|---|---:|
| `BALANCE` | 22 |
| `INCOME_STATEMENT` | 19 |
| `EQUITY` | 11 |
| `LEVERAGE` | 7 |
| `TAX` | 4 |
| `DEBT` | 4 |
| `CASH_FLOW` | 4 |
| `PROFITABILITY` | 3 |
| `EPS` | 2 |
| `LIQUIDITY` | 2 |
| `OTHER` | 2 |
| `EFFICIENCY` | 1 |

De los 81, **20 son del grupo `8xxxxxx`** —los calculados que la CNV publica—,
y ahí está una riqueza que no se estaba aprovechando:

| código | qué es | ¿reconocido? |
|---|---|---|
| `8000000` / `8000001` | EPS básico / diluido | sí |
| `8000003` / `8000004` | **EBIT / EBITDA publicados por el emisor** | sí |
| `8000005` | Capital de trabajo | sí |
| `8000002` | **Patrimonio del ejercicio anterior** (comparativo reexpresado) | **no** |
| `8000006`…`8000029` | **14 ratios que publica la CNV** | 12 sí, 2 no |

`CNV_METR_TAG_COVERAGE.csv` — 81 filas × 20 campos, con `docs_con_valor`,
`docs_nil`, `docs_extraido`, `docs_persistido`, `docs_canonical`,
`coverage_pct` y `loss_reason` por código.

---

## 4 · ¿Cuántos extraemos y cuántos perdemos? (FASE 2 y 4)

### El embudo, código por código

| etapa | códigos | % de los declarados |
|---|---:|---:|
| declarados en el RAW (valor o nil) | **81** | 100 % |
| con valor numérico | 76 | 94 % |
| **reconocidos por el extractor** | **51** | **63 %** |
| persistidos en `cnv_estados_v2` | 51 | 63 % |
| **en la capa canónica** | **51** | **63 %** |

**No hay caída entre reconocido → persistido → canónico.** Todo lo que el
extractor reconoce llega intacto hasta el modelo canónico. **La pérdida está
entera en el primer salto**: el vocabulario.

El vocabulario del extractor son **51 códigos** — 39 en `CODIGOS` y 12 en
`RATIOS_CNV` —, verificado leyendo el archivo fuente.

### El embudo, observación por observación

```
observaciones (código × documento) con valor en el RAW   4.028
                                    reconocidas          2.891   71,8 %
                                    PERDIDAS             1.137   28,2 %
más: observaciones nil descartadas                         258
```

**Se pierde el 28,2 % de lo que los documentos declaran con un número.**

---

## 5 · ¿Por qué? (FASE 5)

### Causa 1 · `NO_ESTA_EN_CODIGOS` — 25 códigos, 1.137 observaciones

El código tiene valor en el RAW y el extractor no lo reconoce. Los 25, con su
presencia en METR y en el corpus completo:

| código | METR | corpus | % corpus | etiqueta |
|---|---:|---:|---:|---|
| `2999999` | 60 | 2.494 | **31 %** | TOTAL DEL PASIVO Y PATRIMONIO NETO |
| `8000008` | 60 | 2.405 | 30 % | INMOVILIZACION DEL CAPITAL |
| `3011300` | 60 | 2.385 | 30 % | OTROS GASTOS DE ADMINISTRACION |
| `2210300` | 60 | 2.375 | 30 % | AJUSTE DE CAPITAL |
| `8000002` | 53 | 2.367 | 30 % | TOTAL PATRIMONIO NETO DEL EJERCICIO ANTERIOR |
| `2322300` | 4 | 2.228 | 28 % | OTROS PASIVOS NO FINANCIEROS CORRIENTES |
| `1122400` | 4 | 2.198 | 28 % | OTROS ACTIVOS NO FINANCIEROS CORRIENTES |
| `8000012` | 60 | 2.189 | 28 % | ENDEUDAMIENTO A CORTO PLAZO |
| `2211100` | 56 | 2.155 | 27 % | RESERVA LEGAL |
| `2322100` | 60 | 2.122 | 27 % | PASIVOS POR IMPUESTOS CORRIENTES |
| `2211200` | 56 | 2.112 | 27 % | OTRAS RESERVAS |
| `1112500` | 60 | 2.083 | 26 % | OTROS ACTIVOS NO FINANCIEROS NO CORRIENTES |
| `2312200` | 51 | 2.049 | 26 % | PASIVOS POR IMPUESTOS NO CORRIENTES |
| `1122300` | 56 | 1.909 | 24 % | ACTIVOS FINANCIEROS CORRIENTES |
| `3011200` | 58 | 1.862 | 23 % | GASTOS DE COMERCIALIZACION Y/O DISTRIBUCION |
| `3011301` | 58 | 1.815 | 23 % | HONORARIOS A DIRECTORES Y SINDICOS |
| `2312400` | 60 | 1.812 | 23 % | OTROS PASIVOS NO FINANCIEROS NO CORRIENTES |
| `3011100` | 47 | 1.481 | 19 % | OTROS INGRESOS |
| `3061999` | 18 | 1.471 | 19 % | OTRO RESULTADO INTEGRAL |
| `2213999` | 9 | 1.318 | 17 % | RESULTADOS INTEGRALES |
| `3011400` | 47 | 1.284 | 16 % | OTROS GASTOS OPERATIVOS |
| `1112400` | 58 | 1.152 | 15 % | ACTIVOS FINANCIEROS NO CORRIENTES |
| `2311999` | 34 | 979 | 12 % | CUENTAS POR PAGAR NO CORRIENTES |
| `2211300` | 30 | 967 | 12 % | INTERESES NO CONTROLANTES |
| `3032000` | 18 | 437 | 6 % | GANANCIA (PERDIDA) DEL PERIODO |

### Causa 2 · `NIL_DESCARTADO` — 5 códigos, 258 observaciones · **BUG**

**La CNV escribe el nil como un guion, no como `0.00`:**

```
… 1112400 ACTIVOS FINANCIEROS NO CORRIENTES 312.00
  1111999 CUENTAS POR COBRAR NO CORRIENTES -
  1110100 PROPIEDADES PLANTAS Y EQUIPOS …
```

El regex del extractor exige `-?\d+\.\d{2}`, así que esos renglones **no
existen para él**. Los 5 códigos afectados en METR:

| código | docs | etiqueta |
|---|---:|---|
| `1111999` | 60 | CUENTAS POR COBRAR NO CORRIENTES |
| `2210500` | 60 | APORTES NO CAPITALIZADOS O CONTRIBUCIONES DE CAPITAL |
| `2210900` | 60 | OTROS CONCEPTOS DEL CAPITAL |
| **`3021900`** | **60** | **OTROS RESULTADOS** |
| `3041000` | 18 | (resultado del período) |

**Es un bug, no una limitación.** Un nil declarado dice "el concepto existe y
vale cero", que es distinto de "el concepto no se informó". Hoy las dos
situaciones son indistinguibles aguas abajo.

> **Corrección de un informe anterior.** `METR_TIKR_2025_DEPENDENCY_MAP.md`
> afirmaba que METR **no declara** `3021900 OTROS RESULTADOS` (0 de 57
> documentos). **Lo declara en 60 de 60, como nil.** La medición previa sólo
> contaba códigos con valor numérico. El informe ya fue corregido.

### Causa 3 · `RUIDO_REGEX` — no es pérdida

Buscar cualquier número de 7 dígitos que empiece con 1–8 devuelve **1.082
matches** que no son conceptos: son ids del JSON de la interfaz
(`"id":"1column1128901"`). Se descartan porque incluyen primeros dígitos 4–7,
fuera del plan de cuentas, y 516 aparecen en un solo documento. **Es un límite
de la medición, no del extractor**, y se declara para que el 81 no se confunda
con el 733 de la primera pasada.

### Causas buscadas y NO encontradas

Se buscaron explícitamente y **no aparecieron** en METR:

| causa candidata | resultado |
|---|---|
| HTML incompleto / truncado | 0 — los 60 reales parsean entero |
| cambio de estructura HTML entre años | 0 — el mismo regex funciona de 2018 a 2025 |
| unidades desconocidas | 0 — sólo "Millones de $" y "Miles de $" |
| monedas distintas de ARS | 0 |
| períodos indeterminables | 0 — los 60 tienen `FechaCierre` |
| perímetros ausentes | 0 en los reales; 1 documento fuera del universo |
| conceptos reconocidos que no se persisten | **0** |
| `_mark_done` ocultando un fallo de parseo | 0 en METR — los 2 rechazos son de PK |

---

## 6 · Qué es bug y qué es límite del modelo

| # | pérdida | naturaleza | costo de arreglarlo |
|---|---|---|---|
| **L1** | 25 códigos fuera de `CODIGOS` | **limitación del vocabulario** | 25 líneas en un diccionario |
| **L2** | nil descartado por el regex | **BUG** | una alternancia en el regex + decidir cómo se representa un nil |
| **L3** | 226 descargas sin documento | **BUG de descarga** | validar contenido antes de guardar |
| **L4** | PK económica sin `accn` | **límite del modelo** | cambio de esquema + supersession (fuera de alcance) |
| **L5** | el ratio engine excluye CNV | **frontera deliberada** | un motor homologado para CNV |

---

## 7 · Universo de ratios (FASE 6)

**57 ratios inventariados.** No se calculó ninguno.

| estado | n |
|---|---:|
| **`CALCULABLE`** | **38** |
| `INPUT_MISSING` | 9 |
| `MARKET_REQUIRED` | 6 |
| `NOT_DEFINED` | 4 |

| fuente | n |
|---|---:|
| **C · tags CNV ya en canonical** | **26** |
| **B · publicado por la propia CNV** | **14** |
| E · requiere Market | 6 |
| F · requiere otra fuente | 5 |
| A · ya existe en Catalaxia | 4 |
| D · en RAW, no extraído | 2 |

### Los 38 calculables, por familia

| familia | n |
|---|---:|
| `LEVERAGE` | 12 |
| `PROFITABILITY` | 11 |
| `EFFICIENCY` | 7 |
| `LIQUIDITY` | 6 |
| `PER_SHARE` | 2 |

**26 son ratios contables** cuyos insumos ya están en la capa canónica:
`current_ratio`, `quick_ratio`, `cash_ratio`, `working_capital_ratio`,
`debt_to_equity`, `equity_ratio`, `borrowings_to_equity`, `net_debt_to_ebitda`,
`interest_coverage`, `ebitda_interest_coverage`, `roa`, `roe`, `net_margin`,
`gross_margin`, `operating_margin`, `ebitda_margin`, `ebit_margin`,
`effective_tax_rate`, `asset_turnover`, `receivables_turnover`,
`inventory_turnover`, `ocf_to_net_income`, `ocf_to_revenue`, `ocf_to_debt`,
`eps_basico`, `eps_diluido`.

**12 son ratios que la CNV ya publica** y están en canonical.

### Sólo 2 ratios se desbloquean agregando códigos al extractor

| ratio | insumo que falta | código |
|---|---|---|
| `roe_promedio` | patrimonio de apertura | `8000002` |
| `sga_margin` | los 3 gastos operativos | `3011200`, `3011300`, `3011301` |

**Es un resultado importante y va contra la intuición**: los 25 códigos
perdidos aportan **cobertura de conceptos**, no ratios nuevos. Los ratios
clásicos ya tienen sus insumos.

### Los 11 que necesitan una fuente que no es la CNV

| ratio | qué falta |
|---|---|
| `book_value_per_share`, `tangible_bv_per_share`, `cash_flow_per_share` | cantidad de acciones |
| `dividends_per_share` | acciones + dividendos |
| `free_cash_flow` | capex |
| `pe`, `pb`, `ps`, `ev_ebitda`, `ev_sales`, `dividend_yield` | precio / market cap |

---

## 8 · Potencial de expansión (FASE 7)

Qué hace falta exactamente para cada bloque:

| bloque | ratios | requiere |
|---|---:|---|
| **ACCOUNTING** (liquidez, apalancamiento, rentabilidad, eficiencia) | **26** | **nada — los insumos ya están** |
| **CNV publicados** | 12 | nada — ya están en canonical |
| CNV publicados no reconocidos | 2 | agregar `8000008`, `8000012` |
| PER_SHARE | 4 | **cantidad de acciones** (una cifra por ejercicio) |
| VALUATION / MARKET_BASED | 6 | precio y market cap, más el puente instrumento↔emisor |
| FCF | 1 | capex (no existe en el plan de cuentas de la CNV) |

**El techo con lo que hay hoy es 38 ratios.** Con la cantidad de acciones sube
a 42. Con Market, a 48. El capex no se alcanza desde los EEFF resumidos.

`CNV_METR_RATIO_INVENTORY.csv` — 57 filas × 11 campos, con fórmula, insumos,
disponibilidad, unidad, requisito de período, estado y causa.

---

## 9 · SEC vs CNV (FASE 8)

Comparación **conceptual**; no se tocó ninguna taxonomía.

| relación | n |
|---|---:|
| equivalentes | 15 |
| sólo CNV | 5 |
| sólo SEC | 5 |
| perímetro distinto | 1 |

**Sólo CNV** — conceptos que SEC no tiene y que son una ventaja de la fuente
argentina:

- `3021800 RECPAM` — resultado por exposición a la inflación (IAS 29)
- `8000003 EBIT` / `8000004 EBITDA` — **publicados por el emisor**, no derivados
- `8000005 CAPITAL DE TRABAJO`
- `8000006…8000029` — **14 ratios calculados por el emisor**
- `8000002` — patrimonio de apertura ya reexpresado

**Sólo SEC** — lo que la CNV no publica: cantidad de acciones, capex, PP&E
bruto, depreciación acumulada, dividendos.

**Perímetro distinto** — `Borrowings` (SEC) vs `2322200 + 2312300 PASIVOS
FINANCIEROS` (CNV): la CNV es más amplia. Documentado, no ajustado.

`CNV_METR_SEC_CONCEPT_MAP.csv`.

---

## 10 · Auditoría independiente (FASE 9)

`c6_metr_auditoria_f062.py` **no importa** el extractor, el adaptador, el ratio
engine ni el script de discovery. Reconstruye el vocabulario **leyendo el
archivo fuente como texto** —si lo importara, coincidiría por construcción y no
podría detectar el error más probable del sprint: haber medido mal el
vocabulario—.

```
A  vocabulario verificado contra el codigo fuente: 51 codigos     0 fallas
B  286 documentos reclasificados, SHA recomputado                 0 fallas
C  embudo recontado: 81 declarados, 76 con valor, 51 reconocidos  0 fallas
   4.028 observaciones, 2.891 reconocidas (71,8 %)
D  canonical: 51 codigos, ninguno fuera del vocabulario           0 fallas
E  57 ratios, todos con estado y causa                            0 fallas

AUDITORIA F-062 = PASS   0 fallas
```

---

## 11 · Las doce preguntas

| # | pregunta | respuesta |
|---|---|---|
| 1 | ¿Cuántos documentos reales tiene METR? | **60** de 286 seleccionados |
| 2 | ¿Cuántos son shells? | **226** (79 %) |
| 3 | ¿Cuántos tags distintos existen? | **81** declarados (76 con valor + 5 nil) |
| 4 | ¿Cuántos extraemos? | **51** códigos · **2.891** observaciones (71,8 %) |
| 5 | ¿Cuántos perdemos? | **30** códigos · **1.395** observaciones (25 sin reconocer + 5 nil) |
| 6 | ¿Por qué? | 1.137 por vocabulario, 258 por nil con guion |
| 7 | ¿Qué pérdidas son bugs? | el **nil descartado** (258 obs) y las **226 descargas vacías** |
| 8 | ¿Qué es límite del modelo? | la **PK económica sin `accn`** y el vocabulario cerrado |
| 9 | ¿Qué ratios ya tienen todos sus inputs? | **38** — 26 contables + 12 publicados por la CNV |
| 10 | ¿Qué ratios adicionales son posibles? | +2 agregando códigos, +4 con acciones, +6 con Market |
| 11 | ¿Qué requiere Market? | `pe`, `pb`, `ps`, `ev_ebitda`, `ev_sales`, `dividend_yield` |
| 12 | ¿Qué es estructural? | **17 de los 25 códigos** aparecen en 23–31 % del corpus de 7.935 documentos |

---

## 12 · Qué arreglar primero

Ordenado por universo desbloqueado sobre esfuerzo.

| # | acción | desbloquea | esfuerzo |
|---|---|---|---|
| **1** | **Agregar los 25 códigos a `CODIGOS`** | **1.137 observaciones en METR; 17 de los 25 afectan al 23–31 % de los 7.935 documentos del corpus** | 25 líneas en un diccionario |
| **2** | **Aceptar el nil (`-`) como valor cero** | 258 observaciones y la distinción entre "cero declarado" y "no informado" | una alternancia en el regex + una decisión de representación |
| **3** | **Validar el contenido al descargar** | recuperar hasta 226 documentos por emisor | un check de "0 códigos con valor ⇒ reintentar" |
| **4** | Conseguir la cantidad de acciones | 4 ratios *per share* | una cifra por ejercicio, fuente externa |
| **5** | Puente instrumento ↔ emisor | 6 ratios de valuación | migración de `market_instruments.entity_id` |
| **6** | Motor de ratios homologado para CNV | los 38 calculables pasan de potencial a publicado | diseño + homologación |

**Las tres primeras son de bajo riesgo semántico**: no inventan datos, no
cambian definiciones, no tocan SEC. Sólo dejan de tirar información que los
documentos ya declaran.

---

## 13 · Gate

| criterio | resultado |
|---|---|
| cuantificar RAW → EXTRACTED → LOST → CANONICAL | **PASS** — 81 → 51 → 30 → 51; 4.028 → 2.891 → 1.137 |
| cada pérdida con causa explícita | **PASS** — 3 causas, sin residuo |
| universo de inputs de ratios | **PASS** — 57 inventariados con insumos y estado |
| ratios existentes / CNV / potenciales | **PASS** — 4 / 14 / 38 calculables |
| auditoría independiente | **PASS** — 0 fallas |
| no se modificó extractor, ratio engine, SEC ni producción | **PASS** |

```
F-062 = PASS
```

Todas las afirmaciones son números medidos y reproducibles. Ninguna dice
"parece completo" ni "la mayoría se extrae".

---

### Entregables

```
outputs/docs/fase_cnv/
├── CNV_METR_TAG_DISCOVERY_REPORT.md    este informe
├── CNV_METR_TAG_COVERAGE.csv            81 filas × 20 campos
├── CNV_METR_EXTRACTION_LOSSES.csv       31 filas
├── CNV_METR_RATIO_INVENTORY.csv         57 filas × 11 campos
├── CNV_METR_DOCUMENT_CENSUS.csv        286 filas × 15 campos
└── CNV_METR_SEC_CONCEPT_MAP.csv         26 filas

worktree catalaxia-cnvmig/scripts/engine/
├── c6_metr_tag_discovery.py            FASE 1-5
├── c6_metr_ratio_inventory.py          FASE 6-8
└── c6_metr_auditoria_f062.py           FASE 9
```
