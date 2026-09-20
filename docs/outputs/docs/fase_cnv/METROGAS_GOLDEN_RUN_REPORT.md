# GOLDEN RUN CNV — METROGAS S.A. (METR)

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

**CUIT 30657863676 · fuente CNV · worktree `catalaxia-cnvmig` · fixture
`metr_golden.db` + base `metrgolden`@5433**

No se rediseñó arquitectura, no se tocó SEC, no se creó ningún parser ni motor
de ratios paralelo. Todo lo que sigue sale de correr el pipeline existente y
medirlo.

---

## 1 · Resumen ejecutivo

**Veredicto: `PASS_WITH_WARNINGS`.**

Nueve de los diez criterios de éxito pasan. El que no —"ratios pasan donde
existen inputs"— falla por una razón que el propio código declara: el motor
homologado **excluye emisores CNV a propósito**.

Tres hallazgos ordenan el resultado:

**1 · El corpus no es lo que el conteo de archivos sugiere.** De los 286
documentos EEFF seleccionados para Metrogas, **226 archivos no son documentos**:
son la página de espera del visor de la CNV —"Cargando información…", ~77 KB de
UI, **cero códigos con valor**—. La descarga guardó el shell y nadie lo validó.

**2 · La brecha de procesamiento real era de 4 documentos, no de 230.** Los 4 se
extrajeron en este Golden Run con el extractor existente. **Dos entraron; dos
no pudieron.**

**3 · Y los dos que no entraron revelan un límite del modelo de datos.** La PK
de `cnv_estados_v2` es **económica** —`(cuit, concepto, period_end,
fecha_reexpresion, tipo_balance)`, **sin `accn`**—, así que dos presentaciones
del mismo período compiten por la misma fila. Los dos documentos rechazados son
presentaciones alternativas de períodos ya cubiertos por otro GUID: la tabla no
tiene lugar para ambos.

> **Corrección de un informe anterior.** `RUNBOOK_READINESS_REPORT.md` afirmó
> "230 documentos descargados y nunca procesados". La aritmética era correcta,
> la interpretación no: 226 de esos 230 no contienen ningún dato. Los cuatro
> entregables afectados ya fueron corregidos.

| | |
|---|---|
| documentos con estado | **286 / 286** |
| reconciliación de cobertura | **cierra** |
| SHA256 recomputados | **286 / 286** |
| hechos canónicos | **2.795** (58 documentos) |
| violaciones semánticas | **0** |
| idempotencia | **0 inserts, digests idénticos** |
| auditoría independiente | **PASS, 0 fallas** |
| tests | **18 / 18** |
| producción | **sin cambios** |

---

## 2 · Census completo (FASE 1)

Universo: los **286** documentos de clase `eeff` de Metrogas en
`whitelist_eeff.csv`. Las otras dos fuentes de discovery se usaron como
contraste: `cnv_documents` tiene 1.681 documentos de todo tipo y `cnv_filings`
121 declaraciones sin `docid`.

### Estado final, por documento

| estado | n | % | qué significa |
|---|---:|---:|---|
| `PROCESSED_OK` | **58** | 20,3 % | extraído, con hechos en la capa canónica |
| `REJECTED` | **2** | 0,7 % | intentado y rechazado, **con motivo persistido** |
| `FAILED_FINAL` | **226** | 79,0 % | la descarga no capturó el documento |
| `PENDING` | **0** | 0 % | — |
| **TOTAL** | **286** | | |

### La ecuación

```
DISCOVERED 286 = DOWNLOADED 286 + NOT_DOWNLOADED 0                      OK
DOWNLOADED 286 = PROCESSED_OK 58 + REJECTED 2 + PENDING 0 + FAILED 226  OK
suma de estados == universo                                             OK
ningún documento sin estado                                             OK
```

`METROGAS_GOLDEN_CENSUS.csv` — 286 filas × 24 campos, con `estado`, `motivo`,
`sha256`, `fecha_cierre`, `perimetro`, `codigos_con_valor` y `es_cascara`.

### Los 226 `FAILED_FINAL`

Todos comparten firma: `formulario = "Estados Contables"`, 50–78 KB,
**0 códigos con valor**, sin `FechaCierre`, sin `TipoBalance`, sin
`UnidadMedida`. Su contenido es la UI del visor:

```
"Cargando información. Espera por favor mientras termina de cargar
 la información necesaria."
```

**El sistema no valida que una descarga contenga un documento.** El archivo se
guarda con nombre de EEFF y pasa por bueno. Es un problema de **calidad de
descarga**, distinto del de cobertura, y hasta ahora estaban confundidos.

### Cobertura temporal de los documentos reales (60)

| año | en RAW | con datos | año | en RAW | con datos |
|---|---:|---:|---|---:|---:|
| 2018 | 2 | 2 | 2022 | 8 | 8 |
| 2019 | 8 | 8 | 2023 | 8 | 8 |
| 2020 | 9 | 8 | 2024 | 8 | 8 |
| 2021 | 9 | 8 | 2025 | 8 | 8 |

Los dos huecos de 2020 y 2021 son exactamente los dos `REJECTED` por colisión
de PK.

---

## 3 · Provenance del RAW (FASE 2)

| control | resultado |
|---|---|
| archivos presentes | 286 / 286 |
| SHA256 calculado | 286 / 286 |
| SHA256 distintos | 286 (0 contenidos duplicados) |
| CUIT del documento == METR | 286 / 286 |
| `source_hash` canónico == SHA del archivo | 2.795 / 2.795 |

**`BLOCKED` parcial que hay que declarar:** ninguna tabla de `screener.db`
almacena el SHA256 de un documento EEFF. El hash **sí** queda persistido aguas
abajo, en `parsed.facts.source_hash`, y el adaptador lo verifica al construir la
capa canónica (`58/58 documentos con RAW y sha256`). Pero en la capa de
extracción el hash **se calcula y se descarta**. Es el `SG-02` del informe de
runbooks.

---

## 4 · Extracción (FASE 3)

Se usó **el extractor existente** — `job5_v2_extract_eeff.parse`, `period_end`,
`tipo_balance`, `factor_unidad`, `tipo_periodo`, `CODIGOS`, `RATIOS_CNV` —
importado, no reescrito.

Lo único que se agregó es lo que el extractor no tiene: **estado explícito por
documento, con motivo, persistido** en `golden_run_documento`. El extractor
original llama `_mark_done(guid)` sin distinguir éxito de fracaso y suma a un
contador `err` que se imprime y se pierde.

### Los 4 documentos que estaban sin procesar

| GUID | período | perímetro | resultado |
|---|---|---|---|
| `6e79fb07…` | 2020-06-30 | CONSOLIDADO | **PROCESSED_OK** · 48 filas |
| `47eb2075…` | 2020-06-30 | INDIVIDUAL | **REJECTED** · colisión de PK |
| `5b4d69bf…` | 2021-12-31 | CONSOLIDADO | **REJECTED** · colisión de PK |
| `e04ceaf3…` | 2024-09-30 | CONSOLIDADO | **PROCESSED_OK** · 50 filas |

`e04ceaf3` es el documento **#3277363**, el caso que quedó abierto en el sprint
de runbooks. Se recuperó: extrae 38 conceptos, período `2024-09-30`, perímetro
`CONSOLIDADO`, factor `1.000.000`.

### El hallazgo de la PK económica

`47eb2075` y `5b4d69bf` no fallan al parsear: parsean bien. Fallan al
**escribirse**, porque sus períodos ya están ocupados por otro documento:

```
2020-06-30 INDIVIDUAL   ya ocupado por a6e3351d-9faa-…
2021-12-31 CONSOLIDADO  ya ocupado por 24a37877-f995-…
```

La PK de `cnv_estados_v2` no incluye `accn`, así que **las dos presentaciones
del mismo hecho económico no caben**. Las dos alternativas destruyen una
ocurrencia:

- `INSERT OR IGNORE` (lo que hace job5) → **la nueva se pierde**
- `INSERT OR REPLACE` → **la vieja se pierde y le cambia el `accn`**

Se eligió `IGNORE` por ser el comportamiento real del sistema, y la colisión
quedó **registrada como estado del documento** en vez de pasar inadvertida.

> Durante el desarrollo de este Golden Run usé `REPLACE` por error y sobrescribí
> las ocurrencias existentes de esos dos períodos en el fixture. Se detectó al
> ver que `v2` sumaba 98 filas en vez de 194, se rehízo el fixture desde cero y
> se corrigió. Queda anotado porque es exactamente el modo de falla que la PK
> económica habilita.

### Un segundo defecto propio, corregido

Mi primera versión escribió los ratios de la CNV con el nombre desnudo
(`liquidez`, `roe`) que devuelve `RATIOS_CNV`. El prefijo `CNV_` lo aplica
**el `INSERT` de job5** (`f"CNV_{concepto}"`), no el mapa. Sin él, el adaptador
canónico descartó **39 conceptos** como "sin clasificar". Corregido replicando
el `INSERT` del extractor tal cual.

---

## 5 · Semántica (FASE 4)

Sobre los 2.795 hechos canónicos, **0 violaciones**:

| control | resultado |
|---|---:|
| `entity_id` distinto de `CUIT:30657863676` | 0 |
| `cik` no nulo | 0 |
| `DURATION` sin `start_date`/`end_date` | 0 |
| `INSTANT` con `start_date` | 0 |
| sin `unit_measure` | 0 |
| sin `measurement_date` | 0 |
| sin `context_id` | 0 |
| monetario sin `currency` | 0 |
| `fact_key` única | sí |

### Flujos vs saldos — el control que más importa

| familia | `period_kind` | n | unidad |
|---|---|---:|---|
| saldos (Assets, Equity, Cash…) | **INSTANT** | 1.070 | `iso4217:ARS` |
| flujos y resultados | **DURATION** | 1.038 | `iso4217:ARS` |
| EPS básico/diluido | **DURATION** | 111 | `iso4217:ARS/xbrli:shares` |
| ratios propios de la CNV | INSTANT 250 / DURATION 326 | 576 | `xbrli:pure` |

**Ningún flujo quedó tratado como INSTANT.** El split de los ratios CNV es
correcto: los de liquidez son puntuales, los de margen son de período.

Además, todo `DURATION` arranca el **1 de enero**: la CNV acumula YTD, así que
un "Q3" son nueve meses. Verificado en los 1.038 + 111.

### Unidades, escala y `decimals`

| `unit_ref` | n |
|---|---:|
| `ars@1e6` | 1.120 |
| `ars@1e3` | 915 |
| `pure` | 576 |
| `ars-por-accion` | 111 |
| `ars@1e0` | 73 |

**`decimals` es NULL en los 2.795.** No es una omisión: es la decisión
certificada de desacoplar precisión de escala. La escala vive en `unit_ref`,
que preserva el factor declarado por cada documento.

`currency = ARS` en 2.219; NULL en los 576 ratios adimensionales, que es lo
correcto.

---

## 6 · Canonical (FASE 5)

Adaptador existente `c4_cnv_adapter.py`, contra `metrgolden`@5433.

```
admitidas                        2.795
EXCLUIDAS · sin perímetro           50   (1 documento)
documentos                          58
documentos con RAW y sha256      58/58
documentos anuales (PB=1)           16  -> cierre de ejercicio 12-31
filas procesables            2.795 de 2.795
entity_key            EY9TRR9RPRVSV916PD0CB9Z93NT
```

| requisito | resultado |
|---|---|
| `entity_id = CUIT:30657863676` | 2.795 / 2.795 |
| `cik = NULL` | 2.795 / 2.795 |
| `fact_key` determinística | recomputada desde sus 5 componentes en las 2.795 |
| unidad correcta | vocabulario cerrado, sin excepciones |
| contexto correcto | `PERIMETRO\|KIND\|inicio\|fin\|medición`, perímetro contra el `TipoBalance` del documento |

Cobertura: **29 períodos por perímetro**, de `2018-12-31` a `2025-12-31`;
1.398 hechos CONSOLIDADO y 1.397 INDIVIDUAL.

### Idempotencia

| | 1ª corrida (en frío) | 2ª corrida |
|---|---:|---:|
| `parsed.facts` insertados | **2.795** | **0** · 2.795 reusados |
| `derived.fact` insertados | **2.795** | **0** · 2.795 sin cambio |

Digests **idénticos** antes y después:

```
derived_metr  2795   63b9ce0e874153c4558e8c75acdaca45
valores       2795   c5fd623fca726dd54f909f6b3b0bc177
parsed_metr   2795   3d69ed07e07e059659f4116ca9d44630
sec_intacto  133902  63629c0fc2ee76ad8038660c4815b443
```

La última fila es el control de que **SEC no se tocó**.

---

## 7 · Ratios (FASE 6)

Se probó el motor existente. **Resultado: no calcula nada para METR, y lo dice
por diseño.**

```
CIK 30657863676   eps       REVIEW_REQUIRED
                  pb        REVIEW_REQUIRED
                  pe        REVIEW_REQUIRED
                  ev_sales  REVIEW_REQUIRED
  motivo: el CIK 30657863676 no resuelve a una entidad con assertion VERIFIED
```

El filtro está documentado en el propio código
(`ratio_engine.py:556-562`):

> *"El filtro `cik IS NOT NULL` no es cosmético. Desde la migración 034 la capa
> canónica también aloja emisores sin CIK (CNV). Este motor está homologado
> sólo para el universo SEC: sus cadenas de fallback son tags us-gaap/ifrs y
> `derived.ratio.cik` es NOT NULL. Traer un emisor CNV acá no sería ampliar la
> cobertura, sería producir un ratio que nadie homologó."*

**Es una frontera deliberada, no un defecto.** Y el alcance de este sprint
prohíbe crear un motor CNV separado, así que no se creó.

### Disponibilidad de insumos

Se midió, **sin calcular ni persistir nada**, si los 14 ratios contables de
`ratio_defs.RATIOS` tienen sus conceptos en la capa canónica de METR:

**14 de 14 tienen los insumos completos** — `current_ratio`, `quick_ratio`,
`cash_ratio`, `debt_to_equity`, `borrowings_to_equity`, `equity_ratio`, `roe`,
`roa`, `net_margin`, `gross_margin`, `operating_margin`, `interest_coverage`,
`effective_tax_rate`, `ocf_to_net_income`.

| familia | estado | causa |
|---|---|---|
| 14 contables | `INPUTS_DISPONIBLES` | ningún motor los calcula (`SG-03`) |
| `eps`, `pe`, `pb`, `ev_sales` | `NOT_CALCULABLE` | el motor está homologado sólo para SEC |

`METROGAS_GOLDEN_RATIOS.csv`.

### Los ratios que publica la propia CNV

**576 hechos** `CNV_*` en la capa canónica, unidad `xbrli:pure`: apalancamiento,
cobertura de intereses, deuda financiera/EBITDA, endeudamiento, liquidez, margen
neto, prueba ácida, ROA, ROE, rotación de activos, solvencia. Son **dato**, no
cálculo, y sirven como control independiente cuando exista un motor.

---

## 8 · Auditoría independiente (FASE 7)

`c5_metr_golden_auditoria.py` **no importa** el extractor, ni el adaptador, ni
el módulo semántico, ni el script de census. Tiene su propio parser del HTML, su
propia transcripción del plan de cuentas y su propia implementación de
`fact_key`.

```
A  census: 286 documentos, ecuación cierra, 0 sin estado, 0 sin motivo   0 fallas
B  RAW y SHA256 recomputados: 286                                        0 fallas
C  valor reconstruido desde el HTML: 1.763 hechos                        0 fallas
D  semántica: kind, período, unidad, perímetro, measurement_date         0 fallas
E  fact_key recomputada                                                  0 fallas
F  pertenencia: 0 con CIK, 0 con origen ajeno                            0 fallas
G  provenance: source_hash == SHA del archivo                            0 fallas
H  ratios: 14/14 con insumos; motor NOT_CALCULABLE por diseño

AUDITORIA = PASS   0 fallas
```

Los 1.032 hechos que el auditor no reconstruye son los que su transcripción
propia no incluye (`CNV_*`, `Capital`, `Reservas`, `WorkingCapital`…). No es un
desacuerdo: es el alcance de su plan de cuentas, declarado.

---

## 9 · Tests

`tests/test_metr_golden_run.py` — **18 pasan**.

| # | test | qué fija |
|---|---|---|
| 1 | coverage reconciliation | la ecuación cierra y no hay `PENDING` |
| 2 | SHA/RAW integrity | 286 SHA recomputados + el canónico apunta al correcto |
| 3 | no document without state | 286/286, vocabulario cerrado |
| 4 | rejection persisted, not printed | 0 no-OK sin motivo; motivos con sustancia |
| 5 | idempotencia | `fact_key` única, cardinalidad fija |
| 6 | duplicate protection | + la PK económica pierde ocurrencias (2 colisiones) |
| 7 | entity ownership | `cik IS NULL`, `entity_key` y origen correctos |
| 8 | semantic period correctness | + los flujos acumulan desde el 1 de enero |
| 9 | unit correctness | vocabulario cerrado por familia |
| 10 | canonical bijection | `fact_key` reproducible; sin hechos huérfanos |
| 11 | ratio consistency | + los ratios CNV están en canonical |
| 12 | provenance end-to-end | hecho → `accn` → archivo → SHA recomputado |
| **13** | **mutación del coverage guard** | tres mutaciones, las tres detectadas |

La 13 es la que valida a las demás: desactivar el guard dejando un documento en
`PENDING`, quitándole el estado a otro o inventando un estado `DONE` **tiene que
romper la reconciliación**. Las tres rompen.

---

## 10 · Problemas encontrados

| # | hallazgo | evidencia | ¿corregido? |
|---|---|---|---|
| **P1** | **226 de 286 descargas no contienen el documento** — son la página de espera del visor | 0 códigos con valor, sin `FechaCierre`, 50–78 KB | **no**: fuera de alcance. Requiere validar contenido al descargar |
| **P2** | **La PK de `cnv_estados_v2` es económica y pierde ocurrencias** | 2 documentos rechazados; sus períodos ya ocupados por otro `accn` | **no**: el sprint prohíbe implementar supersession |
| **P3** | **El SHA256 de un EEFF no se persiste en la capa de extracción** | ninguna tabla de `screener.db` lo guarda | **no**: `SG-02` |
| **P4** | **El motor de ratios excluye CNV por diseño** | `ciks_del_universo` filtra `cik IS NOT NULL` | **no**: es una frontera deliberada |
| **P5** | El extractor no registra por qué descarta un documento | `err` es un contador impreso | **mitigado** en este Golden Run con `golden_run_documento` |
| **P6** | *(propio)* `INSERT OR REPLACE` destruyó ocurrencias en el fixture | `v2` sumó 98 filas en vez de 194 | **sí**: fixture rehecho, `IGNORE` como job5 |
| **P7** | *(propio)* ratios escritos sin el prefijo `CNV_` | 39 conceptos "sin clasificar" | **sí** |
| **P8** | *(propio)* el informe de runbooks decía "230 sin procesar" | 226 son cáscaras; la brecha real era 4 | **sí**: 4 entregables corregidos |

---

## 11 · Aislamiento

| artefacto | antes | después |
|---|---|---|
| `data/screener.db` | `2026-08-23 13:42:23` · 1.504.714.752 | **idéntico** |
| `data/log_job5_v2_done.txt` | `2026-08-20 15:45:10` · 93.366 | **idéntico** |
| producción 5432 | esquema `public` | **`public`** |
| homologada `catalaxia`@5433 | 0 hechos CUIT | **0** |
| `cnvmig` (certificación FY2024) | 2.875 · `84249140c005f834…` | **idéntico** |
| SEC en `metrgolden` | 133.902 | **133.902** |

Todas las escrituras cayeron en `metr_golden.db` (fixture del worktree) y en la
base `metrgolden`, creada para este Golden Run.

---

## 12 · Gate

| criterio | resultado |
|---|---|
| todos los documentos tienen estado | **PASS** — 286/286 |
| coverage reconcilia | **PASS** |
| RAW/SHA verificables | **PASS** — 286 recomputados; ver P3 sobre persistencia |
| extracción reproducible | **PASS** |
| semántica pasa | **PASS** — 0 violaciones |
| canonical pasa | **PASS** |
| **ratios pasan donde existen inputs** | **FALLA** — 14/14 tienen insumos, 0 se calculan |
| provenance llega hasta RAW | **PASS** |
| idempotencia pasa | **PASS** — 0 inserts, digests idénticos |
| auditoría independiente pasa | **PASS** — 0 fallas |

```
METROGAS_GOLDEN_RUN = PASS_WITH_WARNINGS
```

**`PASS_WITH_WARNINGS`, no `PASS`.** El criterio de ratios no se cumple: hay
insumos para los 14 contables y ninguno se calcula, porque el motor homologado
excluye CNV explícitamente y este sprint tiene prohibido crear uno paralelo.

**No es `BLOCKED`** porque ninguna condición de integridad falla: la extracción,
la semántica, la capa canónica, la provenance y la idempotencia pasan todas, y
el caso que estaba abierto desde el sprint anterior quedó recuperado y
certificado.

Las tres advertencias, en orden de impacto:

1. **P1** — el 79 % de las descargas no trajo el documento. Es el techo real de
   cobertura de METR: hay 60 documentos, no 286.
2. **P4** — sin un motor homologado para CNV, la capa canónica de Metrogas es
   correcta y no produce ningún ratio.
3. **P2** — dos hechos económicos existen en el RAW y no caben en el modelo.

---

### Entregables

```
outputs/docs/fase_cnv/
├── METROGAS_GOLDEN_RUN_REPORT.md      este informe
├── METROGAS_GOLDEN_CENSUS.csv         286 filas × 24 campos
└── METROGAS_GOLDEN_RATIOS.csv         18 filas

worktree catalaxia-cnvmig/
├── scripts/engine/c5_metr_golden_census.py      FASE 1-2
├── scripts/engine/c5_metr_golden_extract.py     FASE 3
├── scripts/engine/c5_metr_golden_auditoria.py   FASE 6-7
├── tests/test_metr_golden_run.py                18 tests
└── data/metr_golden.db                          fixture
```
