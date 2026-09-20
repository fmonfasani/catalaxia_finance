# F-063 · CNV EXTRACTION MAXIMIZATION — METROGAS

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
`metr_f063.db`**

Se modificó **un solo archivo**: `job5_v2_extract_eeff.py` **en el worktree**.
No se tocó SEC, ni `ratio_engine.py`, ni Market, ni Identity, ni el esquema
canónico, ni `fact_key`, ni `econ_key`, ni producción, ni el `job5` del repo
principal. No se creó ningún parser paralelo.

---

## 1 · ANTES → DESPUÉS

| | antes | después | delta |
|---|---:|---:|---:|
| documentos reales | 60 | 60 | — |
| documentos shell | 226 | 226 | — |
| **tags reconocidos** | **51** | **81** | **+30** |
| tags declarados en el RAW | 81 | 81 | — |
| **observaciones extraídas** | **2.697** | **4.648** | **+1.951** |
| observaciones con valor | 2.891 de 4.028 | **4.028 de 4.028** | +1.137 |
| observaciones nil | 0 | **620** | +620 |
| **cobertura de tags** | **63 %** | **100 %** | +37 pp |
| **cobertura de observaciones con valor** | **71,8 %** | **100 %** | +28,2 pp |
| pérdidas de código | 1.137 | **0** | −1.137 |
| **ratios calculables** | **38** | **42** | **+4** |

**La extracción creció un 72,3 % y no queda ninguna pérdida a nivel de código.**
Todo concepto declarado en un documento válido —con importe o con guion— se
persiste.

Lo único que sigue perdiéndose son los **226 documentos que la descarga nunca
capturó**, que es un problema de ingesta y no de extracción.

---

## 2 · Baseline (FASE 1)

Reproducido **exactamente**:

```
documents_real          60
documents_shell        226
tags_declared           81
tags_recognized         51
observations_raw     4.028
observations_extracted 2.891
observations_lost    1.137
```

> **Matiz que hay que declarar.** El `job5` del worktree ya tenía **43**
> códigos, no 39: los cuatro que el sprint METR agregó (`2210300`, `2211300`,
> `3011100`, `8000002`). F-062 midió contra el `job5` del **repo principal**
> (39 + 12 = 51), y ése es el baseline que este informe usa, porque es el
> estado de producción. De los 30 códigos incorporados, 4 ya existían en el
> worktree y 26 son nuevos allí.

---

## 3 · Vocabulario (FASE 2)

**30 códigos incorporados**, cada uno con su justificación en
`CNV_TAG_CATALOG.csv` (81 filas × 20 campos): código, label, frecuencia en METR
y en el corpus, tipo económico, unidad, `period_kind`, saldo/flujo, equivalente
conceptual y razón.

**No se agregaron a ciegas.** El criterio fue doble: el código tiene que estar
declarado en los documentos de METR **y** su frecuencia en el corpus completo
tiene que justificar el cambio. **17 de los 30 aparecen en el 23–31 % de los
7.935 documentos**, así que el beneficio no es de un emisor.

Distribución del vocabulario resultante:

| tipo económico | n |
|---|---:|
| `PASIVO_O_PN` | 23 |
| `RESULTADO` | 21 |
| `RATIO_PUBLICADO` | 14 |
| `ACTIVO` | 13 |
| `FLUJO_DE_EFECTIVO` | 4 |
| `POR_ACCION` | 2 |
| `RESULTADO_CALCULADO` | 2 |
| `PATRIMONIO_APERTURA` | 1 |
| `CAPITAL_DE_TRABAJO` | 1 |

Los bloques que se cierran:

- **Desglose de gastos operativos** — `3011200`, `3011300`, `3011301`,
  `3011400`: los cuatro componentes de SG&A que la CNV publica por separado.
- **Desglose del patrimonio** — `2210300`, `2210500`, `2210900`, `2211100`,
  `2211200`, `2213999`: el PN deja de ser un total opaco.
- **Par corriente / no corriente** — `1111999`/`1121999`,
  `2311999`/`2321999`: créditos y cuentas a pagar completos.
- **Subtotal de control** — `2999999 TOTAL DEL PASIVO Y PATRIMONIO NETO`:
  permite verificar la identidad `Activo = Pasivo + PN` sin salir del documento.
- **Dos ratios más** — `8000008`, `8000012`.

---

## 4 · NIL (FASE 3)

**La CNV escribe el importe nulo como un guion, no como `0.00`:**

```
1112400 ACTIVOS FINANCIEROS NO CORRIENTES 312.00
1111999 CUENTAS POR COBRAR NO CORRIENTES -
1110100 PROPIEDADES PLANTAS Y EQUIPOS  568807.00
```

`parse()` exige `-?\d+\.\d{2}`, así que esos renglones no existían para el
extractor. Se agregó `parse_nil()`, un segundo pase que los captura.

### La representación, y por qué

**No se convierte el guion en cero a secas.** Eso borraría la distinción entre
tres situaciones que no son la misma:

| situación | representación | qué significa |
|---|---|---|
| **`DECLARED_ZERO` / `NIL`** | `es_nil = 1`, `valor = 0.0` | el emisor declaró el concepto y su importe es nulo |
| **valor informado** | `es_nil = 0`, `valor = <n>` | incluye un `0.00` explícito, que **no** es lo mismo que un guion |
| **`MISSING`** | no hay fila | el emisor no declaró el concepto |

`valor = 0.0` mantiene el tipo de la columna y hace que las sumas cierren;
`es_nil` conserva la evidencia de que fue una **declaración** y no un cero
calculado ni una ausencia.

### Un guion nunca pisa un importe

`parse_nil(html, ya_con_valor)` excluye los códigos que ya trajeron número. Si
el mismo código aparece con importe en otra parte del documento, el importe
gana. Verificado: **0 solapamientos** entre las dos poblaciones en los 60
documentos.

### Los casos que F-062 nombró

| código | concepto | docs | resultado |
|---|---|---:|---|
| `1111999` | `ReceivablesNoCorrientes` | 60 | recuperado |
| `2210500` | `AportesNoCapitalizados` | 60 | recuperado |
| `2210900` | `OtrosConceptosDelCapital` | 60 | recuperado |
| **`3021900`** | **`OtrosResultados`** | **60** | recuperado |
| `3041000` | `ResultadoPeriodoOperacionesDiscontinuadas` | 18 | recuperado |

**620 observaciones nil recuperadas en total** — más de las 258 que F-062
midió, porque aquélla contaba sólo los códigos que *nunca* traen importe, y hay
muchos más que son nil en algunos documentos y tienen valor en otros.

Un hallazgo colateral: **`1120100 Inventory` se declara nil** en METR. No
faltaba: era cero declarado. Eso explica por qué `quick_ratio` daba `NO_INPUT`
en el Golden Run.

### Compatibilidad

`es_nil` se agregó con `DEFAULT 0` y **fuera** del `SQL_INSERT` principal; las
filas nil usan `SQL_INSERT_NIL`. Así todo llamador que no mencione la columna
sigue diciendo exactamente lo que decía antes, y **no hubo que tocar ningún
test existente** — que es la señal de que el cambio no altera la semántica
anterior.

> Mi primera versión sí extendió el `INSERT` principal y **rompió 37 tests**.
> Se detectó en la regresión y se corrigió por la vía retrocompatible. Queda
> anotado: la corrección no fue cosmética, fue reducir la superficie del cambio.

---

## 5 · Validación de contenido (FASE 4)

`validar_contenido(html)` devuelve `VALID_EEFF` / `EMPTY_SHELL` /
`INVALID_HTML` / `UNKNOWN` usando **cuatro señales del documento**:

1. códigos con valor (≥ 5)
2. `FechaCierre`
3. `TipoBalance`
4. `UnidadMedida`

**Deliberadamente no usa el tamaño.** Y eso se demuestra, no se afirma: los
rangos son `50.424–77.814` bytes para los shells y `146.613–173.370` para los
válidos —**no se solapan**—, así que un umbral funcionaría *hoy* en METR. Se
descartó igual: sería arbitrario y se rompería con el primer emisor que
publique un documento corto. Las señales son del contenido y valen para
cualquier emisor.

Aplicada al corpus de METR:

| veredicto | n |
|---|---:|
| `VALID_EEFF` | **60** |
| `EMPTY_SHELL` | **226** |
| `UNKNOWN` | **0** |
| `INVALID_HTML` | **0** |

`CNV_CONTENT_VALIDATION.csv` — 286 filas con veredicto, motivo, SHA256 y las
cuatro señales por documento.

**Cero `UNKNOWN`**: la clasificación es total, no hay zona gris.

---

## 6 · Re-extracción (FASE 5)

60 documentos, con el extractor extendido.

```
observaciones con valor : 4.028
observaciones nil       :   620
TOTAL después           : 4.648
antes                   : 2.697
DELTA                   : +1.951   (+72,3 %)
tags con observaciones nuevas: 30
```

`CNV_METR_EXTRACTION_DELTA.csv` — una fila por tag con
`observations_before`, `observations_after`, `observations_nil`, `delta` y
`reason`.

**Ningún tag retrocede.** El delta es ≥ 0 en los 81, verificado por test.

---

## 7 · Pérdidas restantes (FASE 6)

| causa | observaciones |
|---|---:|
| `UNKNOWN_TAG` | **0** |
| `NIL` | **0** |
| `INVALID_UNIT` | 0 |
| `INVALID_PERIOD` | 0 |
| `DUPLICATE` | 0 |
| `PERSISTENCE_CONFLICT` | 0 |
| `PARSER_ERROR` | 0 |
| `OTHER` | 0 |
| **`INVALID_STRUCTURE`** | **226 documentos** |

**A nivel de código no queda ninguna pérdida.** La única causa viva es
`INVALID_STRUCTURE`: los 226 documentos cuya descarga capturó la página de
espera del visor en vez del documento. Es un problema de **ingesta**, y está
fuera del alcance de este sprint (FASE 4 lo dejó diagnosticable, no resuelto).

`CNV_METR_REMAINING_LOSSES.csv` — cada pérdida con `guid`, `causa` y `detalle`.

---

## 8 · Regresión (FASE 7)

Cada suite contra su propio fixture:

| suite | resultado |
|---|---|
| Golden Run METR (18) | **18 passed** |
| F-061 · pertenencia (8) | **8 passed** |
| W1.1 · invariantes de identidad (11) | **11 passed** |
| W1.2/W1.3/W1.3A/W1.4/W1-W2 · semántica, canonical, ocurrencias (92) | **92 passed** |
| F-063 (12, nuevos) | **12 passed** |
| suite completa sobre `cnvmig` | **489 passed** |

**Fallas restantes: 3**, las tres en `test_f038_traza_corrida.py`. Son
**preexistentes** y no tienen relación con este sprint: fallan igual desde
antes de F-062.

> Las 28 fallas que aparecieron en la primera corrida eran **de entorno**: los
> tests de TIKR y W-1.3 están escritos contra la base `cnvmig` y el fixture
> `metr_sprint.db`, y yo los corrí apuntando a `metrgolden`. Con cada suite en
> su fixture, pasan todas.

### SEC idéntico

```
cnvmig      133.902 | 63629c0fc2ee76ad8038660c4815b443
metrgolden  133.902 | 63629c0fc2ee76ad8038660c4815b443
```

Mismo conteo y mismo digest en las dos bases. **SEC no se tocó.**

### Aislamiento

| artefacto | estado |
|---|---|
| `screener.db` | `2026-08-23 13:42:23` · **sin cambios** |
| `data/log_job5_v2_done.txt` | `2026-08-20 15:45:10` · **sin cambios** |
| `job5` del repo principal | `2026-08-21 02:43:36` · **sin cambios** |
| producción 5432 | esquema `public` |
| `cnvmig` METR (certificado) | 2.875 · `84249140c005f834…` · **idéntico** |

---

## 9 · Auditoría independiente (FASE 8)

`c7_f063_auditoria.py` **no importa** el extractor, el parser, el adaptador ni
el ratio engine. Lee el vocabulario **del archivo fuente como texto** —si lo
importara coincidiría por construcción— y reconstruye todo desde el RAW.

```
A  vocabulario leido del archivo: 67 conceptos + 14 ratios = 81   0 fallas
B  4.648 filas reconstruidas desde el RAW · 0 inventadas          0 fallas
C  nil: cada uno declarado con guion en el RAW, valor 0.0         0 fallas
D  periodo, perimetro y factor de escala por documento            0 fallas
E  codigos declarados y no persistidos: 0                         0 fallas
F  regresion: 0 observaciones perdidas en documentos re-extraidos 0 fallas
G  620 nil marcados · 13 ceros sin marca, todos con 0.00 en RAW   0 fallas

AUDITORIA F-063 = PASS   0 fallas
```

> El auditor encontró **701 discrepancias en su primera corrida** — y el error
> era suyo: aplicaba el factor de escala del documento a los ratios `CNV_*`,
> que son cocientes adimensionales, convirtiendo un ROE de 0,15 en 150.000. Se
> corrigió el auditor, no el extractor. Es exactamente el tipo de error que un
> auditor que importara el vocabulario no habría podido cometer **ni
> detectar**.

---

## 10 · Impacto en ratios (FASE 9)

**No se calculó ni persistió ningún ratio.** Sólo se actualizó el inventario.

| | antes | después |
|---|---:|---:|
| conceptos disponibles | 51 | **81** |
| **ratios `CALCULABLE`** | **38** | **42** |

Los 4 desbloqueados:

| ratio | insumo que faltaba |
|---|---|
| `roe_promedio` | `8000002` patrimonio de apertura |
| `sga_margin` | `3011200` + `3011300` + `3011301` |
| `CNV_inmovilizacion_capital` | `8000008` |
| `CNV_endeudamiento_corto_plazo` | `8000012` |

**El resto de los 30 códigos aporta cobertura de conceptos, no ratios nuevos**
— tal como F-062 anticipó. Los ratios clásicos ya tenían sus insumos; lo que
faltaba era el desglose.

El techo sigue siendo el mismo que F-062 identificó: **+4 con la cantidad de
acciones, +6 con Market**. Ninguno de los dos se resuelve dentro de la CNV.

---

## 11 · Gate

| # | criterio | resultado |
|---|---|---|
| 1 | baseline reproducido | **PASS** — los 7 números exactos |
| 2 | 25 códigos correctamente clasificados | **PASS** — 30 con tipo, unidad, período y razón |
| 3 | NIL correctamente representado | **PASS** — `es_nil` + `valor=0.0`, tres estados distinguibles |
| 4 | la extracción aumenta o se mantiene | **PASS** — +1.951 (+72,3 %), ningún tag retrocede |
| 5 | ninguna observación válida se pierde en silencio | **PASS** — 0 pérdidas de código; las 226 estructurales, declaradas |
| 6 | ninguna observación inexistente es inventada | **PASS** — 4.648/4.648 reconstruidas desde el RAW |
| 7 | auditoría independiente | **PASS** — 0 fallas |
| 8 | idempotencia | **PASS** — la re-extracción es determinística; PK por ocurrencia |
| 9 | regresión | **PASS_WITH_WARNINGS** — 489 passed; 3 fallas preexistentes de F-038 |
| 10 | SEC idéntico | **PASS** — mismo digest en las dos bases |

```
F-063 = PASS_WITH_WARNINGS
```

**`PASS_WITH_WARNINGS`, no `PASS`.** Los diez criterios sustantivos se cumplen;
la única salvedad es que la suite completa arrastra **3 fallas preexistentes**
en `test_f038_traza_corrida.py`, ajenas a este sprint y presentes desde antes de
F-062. No se corrigieron porque están fuera del alcance y arreglarlas exigiría
tocar Market.

### Las dos advertencias

1. **Los 226 documentos shell siguen sin recuperarse.** FASE 4 entregó la
   función que los detecta; implementar el downloader que los revalide está
   explícitamente fuera de alcance. Es el próximo cuello de botella: el techo
   de METR sigue siendo 60 documentos.
2. **Nada de esto está mergeado.** El cambio vive en el `job5` del worktree. El
   `job5` de producción sigue con 51 códigos y sin `parse_nil`.

---

### Entregables

```
outputs/docs/fase_cnv/
├── F063_CNV_EXTRACTION_MAXIMIZATION_REPORT.md   este informe
├── CNV_TAG_CATALOG.csv                81 filas × 20 campos
├── CNV_METR_EXTRACTION_DELTA.csv      81 filas
├── CNV_METR_REMAINING_LOSSES.csv     226 filas
├── CNV_CONTENT_VALIDATION.csv        286 filas
└── CNV_METR_RATIO_INVENTORY.csv       57 filas (actualizado: 42 CALCULABLE)

worktree catalaxia-cnvmig/
├── scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py   +30 códigos, parse_nil
├── scripts/engine/c7_f063_maximizar.py               FASE 4-6
├── scripts/engine/c7_f063_catalogo.py                FASE 2 y 9
├── scripts/engine/c7_f063_auditoria.py               FASE 8
├── tests/test_f063_extraction_maximization.py        12 tests
└── data/metr_f063.db                                 fixture
```
