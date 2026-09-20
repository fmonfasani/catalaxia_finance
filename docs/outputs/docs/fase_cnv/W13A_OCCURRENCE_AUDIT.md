# W-1.3A · AUDITORÍA DE LAS 152 OCURRENCIAS COLAPSADAS

**METR · CUIT 30657863676 · worktree `catalaxia-cnvmig` @ `4cf1aa5` · fixture
`metr_f063.db`**

**Sprint de auditoría. No se implementó `econ_key`, no se cambió ninguna PK, no
se dedupló, no se borró nada.** No se tocó el esquema canónico, el ratio engine,
Market, Identity, producción ni `main`.

---

## 1 · Objetivo

Determinar **qué son** las 152 ocurrencias que se pierden entre
`cnv_estados_v2` y `cnv_estados_norm`, antes de decidir si `accn` debe formar
parte de alguna clave.

## 2 · Estado inicial

| | |
|---|---|
| `cnv_estados_v2` | PK `(accn, concepto)` → **identidad de ocurrencia documental** |
| `cnv_estados_norm` | PK `(cuit, concepto, period_end, fecha_reexpresion, tipo_balance)` → **identidad económica, sin `accn`** |
| transformación | `INSERT OR IGNORE` de v2 a norm |
| filas v2 | 4.648 |
| filas norm | 4.496 |

La transformación fija `fecha_reexpresion = period_end`, así que la PK efectiva
de norm es `(cuit, concepto, period_end, tipo_balance)`.

## 3 · Reproducción exacta del censo

```sql
SELECT cuit, concepto, period_end, tipo_balance, count(*) n
  FROM cnv_estados_v2
 GROUP BY 1,2,3,4
HAVING count(*) > 1;
```

```
filas cnv_estados_v2              4.648
filas cnv_estados_norm            4.496
grupos por la PK de norm          4.496
grupos con >1 ocurrencia            152
ocurrencias en esos grupos          304
ocurrencias EXCEDENTES              152
v2 - norm                           152
```

**Reproduce 152.** Y hay que decir por qué el número aparece dos veces:

> **Los 152 grupos son TODOS de tamaño 2.** Por eso «grupos colapsados» y
> «ocurrencias perdidas» dan el mismo número. Es una propiedad de este corpus,
> no una identidad general: con un grupo de tres, los dos números se separarían.
> El **152 del enunciado son ocurrencias perdidas**, y coinciden con los grupos
> sólo porque todas las colisiones son pares.

## 4 · Definición de colapso

Dos filas de `cnv_estados_v2` que comparten `(cuit, concepto, period_end,
tipo_balance)` compiten por una única fila de `cnv_estados_norm`. Con
`INSERT OR IGNORE`, **la primera gana y la segunda desaparece sin registro**.

## 5 · Qué son — el hallazgo central

**Los 152 grupos no son 152 documentos: son 2 pares (4 documentos).**

| período | perímetro | conceptos | sobrevive | se pierde | adjuntos iguales |
|---|---|---:|---|---|---|
| 2020-06-30 | INDIVIDUAL | 76 | `a6e3351d…` #2643030 | `47eb2075…` #2643240 | **5/5** |
| 2021-12-31 | CONSOLIDADO | 76 | `5b4d69bf…` #2860327 | `24a37877…` #2860477 | **4/5** |

76 conceptos × 2 pares = 152.

### `accn` es la única columna que difiere

| tipo de diferencia | grupos |
|---|---:|
| **documentales** | **152** |
| económicas | **0** |
| mixtas | 0 |

```
columnas que difieren, por frecuencia:
  accn    152    documental
```

**Ninguna otra columna difiere en ningún grupo.** Verificado en los 152:

- `valor_a == valor_b` — **152/152**
- `es_nil_a == es_nil_b` — **152/152**
- `unidad_factor` idéntico — **152/152**
- `unidad_medida`, `moneda`, `tipo`, `period_end`, `tipo_balance` — idénticos

### A nivel de documento

Comparando los HTML completos, tras neutralizar el ordinal de presentación:

| | 2020-06-30 IND | 2021-12-31 CONS |
|---|---|---|
| bytes | 146.710 vs 146.710 — **idénticos** | 147.599 vs 147.596 — **3 bytes** |
| códigos con valor | 67 vs 67 | 67 vs 67 |
| códigos nil | 9 vs 9 | 9 vs 9 |
| códigos con valor distinto | **0** | **0** |
| `FechaCierre`, `TipoBalance`, `UnidadMedida`, `NormasContables` | idénticos | idénticos |
| SHA256 del archivo | distinto | distinto |

Las únicas diferencias reales en el HTML son:

1. el **ordinal de presentación** (`#2643030` vs `#2643240`), 4 apariciones;
2. el **`RequestVerificationToken`** — un antiforgery de ASP.NET, por petición,
   sin contenido semántico;
3. el **GUID interno del uploader**.

### La evidencia que decide: los hashes de adjunto

La CNV publica, **dentro del propio documento**, el hash de contenido de cada
archivo adjunto. No depende de una fecha de publicación, que la CNV **no
expone** (`NO DISPONIBLE`).

| par | hashes de adjunto |
|---|---|
| 2020-06-30 INDIVIDUAL | **5 de 5 idénticos** — la re-presentación no aporta contenido nuevo por ningún lado |
| 2021-12-31 CONSOLIDADO | **4 de 5 idénticos**, 1 reemplazado — los hechos estructurados no cambian, pero el emisor sustituyó un documento adjunto que este pipeline no parsea |

## 6 · Clasificación primaria

| categoría | grupos | ocurrencias v2 | pérdida actual | evidencia | acción futura |
|---|---:|---:|---|---|---|
| **B · REPUBLICACIÓN** | **152** | **304** | la identidad documental de la 2ª presentación | `accn` es la única columna distinta; 0 valores cambiados; hashes de adjunto 5/5 y 4/5 iguales | preservar la ocurrencia; **no** desdoblar el hecho económico |
| A · duplicado técnico | 0 | — | — | los SHA de archivo difieren | — |
| C · restatement | 0 | — | — | **cero valores cambiados** | — |
| D · perímetro distinto | 0 | — | — | `tipo_balance` idéntico | — |
| E · período distinto | 0 | — | — | `period_end` idéntico | — |
| F · unidad/escala distinta | 0 | — | — | factor y unidad idénticos | — |
| G · medición distinta | 0 | — | — | `fecha_reexpresion` idéntica | — |
| H · valor distinto | 0 | — | — | — | — |
| I · otro | 0 | — | — | — | — |

**Confianza: ALTA en los 152.** Ninguno queda `AMBIGUO`.

## 7 · Tabla de grupos (muestra; los 152 en `W13A_OCCURRENCE_GROUPS.csv`)

| grupo | entity | concepto | período | perímetro | accn(s) | valores | clasificación | confianza | explicación |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `CUIT:30657863676` | `ActivosFinancierosCorrientes` | 2020-06-30 | INDIVIDUAL | `a6e3351d…` / `47eb2075…` | idénticos | `B_REPUBLICACION` | ALTA | idénticos salvo `accn`; los 5 hashes de adjunto coinciden |
| 2 | ídem | `ActivosFinancierosCorrientes` | 2021-12-31 | CONSOLIDADO | `5b4d69bf…` / `24a37877…` | idénticos | `B_REPUBLICACION` | ALTA | hechos idénticos; 1 de 5 adjuntos cambió |
| 5 | ídem | `AjusteDeCapital` | 2020-06-30 | INDIVIDUAL | `a6e3351d…` / `47eb2075…` | idénticos | `B_REPUBLICACION` | ALTA | ídem grupo 1 |
| … | | 76 conceptos × 2 períodos | | | | | | | |

`W13A_OCCURRENCE_GROUPS.csv` — 152 filas × 30 campos, con ordinales, SHA de
documento, hashes de adjunto y las columnas que difieren.

## 8 · Casos ambiguos

**Ninguno.** Los 152 tienen evidencia suficiente y una sola categoría.

El único matiz que merece registro es el par de 2021: **1 de 5 adjuntos
cambió**. Los hechos estructurados son idénticos, así que a nivel de los datos
que Catalaxia extrae es una republicación pura. Pero el emisor **sí cambió
algo** en un documento que este pipeline no lee. No es un restatement de los
hechos; es un cambio fuera de nuestro alcance de extracción, y se declara como
tal en vez de esconderlo.

## 9 · Impacto

### Impacto actual

| # | pregunta | respuesta |
|---|---|---|
| 1 | ¿Se pierde información económica? | **No.** Los 152 valores son idénticos |
| 2 | ¿Se pierde sólo información documental? | **Sí.** El `accn` de la 2ª presentación y su SHA |
| 3 | ¿Se pierde una versión anterior del dato? | **No.** No hay versiones distintas |
| 4 | ¿Se pierde una versión corregida? | **No** en los hechos. En el par de 2021 se pierde el rastro de que un adjunto fue reemplazado |
| 5 | ¿Se pierde provenance? | **Sí, parcialmente.** No se puede responder «¿qué documentos declararon este hecho?»: sólo queda uno de los dos |
| 6 | ¿Afecta ratios? | **No.** Mismo valor, mismo período, mismo perímetro |
| 7 | ¿Afecta TTM? | **No**, por lo mismo |
| 8 | ¿Afecta la selección de *latest*? | **No hoy.** Con valores idénticos, cualquier criterio da el mismo número |
| 9 | ¿Afecta auditoría/reproducibilidad? | **Sí.** Una auditoría que parta de norm no puede reconstruir que hubo dos presentaciones |

### Riesgo futuro

El impacto es nulo **hoy** porque los 152 casos resultaron ser republicaciones
sin cambio. **Eso no es una propiedad del modelo: es una propiedad de este
corpus.** El mismo colapso, con valores distintos, destruiría una de las dos
versiones sin dejar rastro — y no habría forma de notarlo, porque
`INSERT OR IGNORE` no informa.

Los riesgos concretos:

1. **Un restatement real se perdería igual.** Si un emisor corrige una cifra en
   una segunda presentación, la PK actual descarta una de las dos y el criterio
   de cuál sobrevive es el **orden de lectura**, no la fecha.
2. **`latest` sería indeterminado.** Con dos valores distintos, hoy no hay
   ningún atributo en norm que permita elegir.
3. **La provenance ya está incompleta**, aunque no duela: `derived.fact` cita
   un `accn` que es uno de dos posibles.

## 10 · Recomendación de modelo de ocurrencia

`cnv_estados_v2` **ya lo resuelve bien** con PK `(accn, concepto)`. Una
ocurrencia documental es:

```
entity      quién declara            CUIT / entity_key
document    dónde lo declara         accn  (+ SHA256 del archivo)
concept     qué declara              concepto / código CNV
context     bajo qué supuestos       perímetro, period_kind, período, medición
unit        en qué está expresado    unit_measure + escala
value       el importe               valor + es_nil
```

**`accn` pertenece a la identidad de ocurrencia. Sin discusión: es lo único que
distingue las dos declaraciones.**

## 11 · Recomendación preliminar de `econ_key`

**No se implementa en este sprint.** Lo que la auditoría **sí demuestra**:

### Atributos que deben formar parte

| atributo | por qué lo demuestra esta auditoría |
|---|---|
| `entity_id` | trivial, pero necesario |
| concepto / `qname` | trivial |
| **perímetro** | CONSOLIDADO e INDIVIDUAL describen el mismo concepto en el mismo período y **son hechos distintos**. 2.248 combinaciones concepto/período tienen los dos |
| `period_kind` | un saldo y un flujo del mismo concepto no son el mismo hecho |
| `start_date`, `end_date` | los flujos acumulan YTD: el mismo concepto con distinto inicio es otro hecho |
| `unit_measure` | un importe y un cociente no son el mismo hecho |
| **`measurement_date`** | bajo IAS 29 el mismo saldo del 31-12-2023 vale distinto medido a marzo, junio o diciembre. **Ya se observó** en `PatrimonioAperturaEjercicio` |

### Atributos que NO deben formar parte

| atributo | por qué |
|---|---|
| **`accn`** | **La prueba está en estos 152 casos**: dos `accn` distintos declaran el mismo valor, del mismo concepto, del mismo período, del mismo perímetro, en la misma unidad. Si `accn` entrara en `econ_key`, existirían **dos hechos económicos donde hay uno**, y el conteo de hechos dependería de cuántas veces el emisor presentó el mismo balance |
| SHA256 del documento | ídem, y además cambia con un token de sesión |
| fecha de descarga | es del pipeline, no del hecho |
| ordinal de presentación | documental |
| `es_nil` | **caso a discutir**: un cero declarado y un importe cero son el mismo hecho económico con distinta evidencia. Los datos actuales no lo dirimen — no hay ningún grupo donde uno sea nil y el otro traiga importe |
| `escala` / `unit_ref` | **no** debería: 1.000.000 y 1.000 expresan la misma magnitud. La escala es de presentación. *Este corpus no lo prueba* —no hay grupos con escala distinta— así que queda como recomendación, no como hallazgo |

### La recomendación sobre `accn`, en una línea

> **`accn` SÍ en la identidad de ocurrencia. `accn` NO en `econ_key`.**
> Es exactamente la distinción que estos 152 casos vuelven verificable: son
> **una** identidad económica declarada **dos** veces.

## 12 · Restatement / supersession

### Qué evidencia existe

| evidencia | disponible | sirve para |
|---|---|---|
| ordinal de presentación | **sí**, en los 4 documentos | **ordenar** dos presentaciones; nada más |
| SHA256 del archivo | **sí**, calculable | detectar duplicado byte a byte |
| **hash de contenido de cada adjunto** | **sí**, la CNV lo publica en el HTML | **distinguir republicación pura de re-presentación con contenido nuevo** — es la evidencia más fuerte disponible |
| valor de cada concepto | sí | detectar un cambio económico |

### Qué evidencia falta

| falta | consecuencia |
|---|---|
| **fecha de publicación real** | **`NO DISPONIBLE`.** La CNV no la expone en el documento. El ordinal es monótono pero no es una fecha: no se puede afirmar «B supersede a A» con rigor, sólo «B se presentó después» |
| declaración explícita de corrección | no hay ningún campo que diga «esta presentación reemplaza a aquélla» |
| enlace entre presentaciones | ninguna presentación referencia a otra |

### Se puede distinguir hoy

- **Republicación** ⇐ 0 valores cambiados. **Sí, con certeza.**
- **Restatement** ⇐ algún valor cambió **y** hay orden temporal. **Parcialmente**:
  el orden existe (ordinal) pero no la fecha. En este corpus la pregunta es
  vacía: **no hay ningún caso con valor cambiado**.

### Modelo futuro necesario

Para construir `supersedes` haría falta, como mínimo:

1. `econ_key` — para agrupar las ocurrencias del mismo hecho;
2. un **orden total** entre ocurrencias del mismo `econ_key` — el ordinal
   alcanza, aunque una fecha sería preferible;
3. una **regla declarada** de cuál es vigente, y por qué;
4. que **ninguna ocurrencia se borre**: la relación es entre filas que existen.

**Ninguno de los cuatro se implementa en este sprint.**

## 13 · Riesgos

| # | riesgo |
|---|---|
| R1 | **`INSERT OR IGNORE` es silencioso.** Hoy no duele porque los valores coinciden; el día que no coincidan, la pérdida será igual de invisible |
| R2 | **El criterio de supervivencia es el orden de lectura**, no una regla declarada |
| R3 | **La muestra es chica**: 2 pares de un emisor. Que los 152 sean republicaciones **no permite afirmar** que todos los colapsos del corpus lo sean |
| R4 | El par de 2021 tiene un adjunto reemplazado que el pipeline no parsea: hay un cambio del emisor que no podemos leer |
| R5 | `escala` fuera de `econ_key` es una recomendación **sin evidencia en este corpus** |

## 14 · Qué NO debe cambiarse todavía

- **No agregar `accn` a la PK de `cnv_estados_norm`** sólo para que el 152
  desaparezca. El número no es el problema: la pregunta es qué representa esa
  tabla. Si es la identidad económica, `accn` no va; si va a alojar ocurrencias,
  entonces es otra tabla.
- **No implementar `econ_key`** — falta decidir `es_nil` y `escala`.
- **No implementar `supersedes`** — falta el orden total declarado.
- **No deduplicar ni borrar** ninguna de las 304 ocurrencias.
- **No tocar** `derived.fact`, ratio engine, Market, Identity ni producción.

## 15 · Próximo paso recomendado

**W-1.3B debería empezar por una decisión de modelo, no de código:**

> ¿`cnv_estados_norm` es la **capa de identidad económica** o la **capa de
> ocurrencias normalizadas**?

No puede ser las dos. Hoy tiene la PK de la primera y recibe los datos de la
segunda, y de ahí sale el colapso.

Las dos salidas coherentes:

| opción | qué implica |
|---|---|
| **A · norm = identidad económica** | El colapso es **correcto**, pero necesita ser **explícito**: registrar cuántas ocurrencias respaldan cada fila y cuáles. Sustituir `INSERT OR IGNORE` por una agregación que cuente y liste los `accn` |
| **B · norm = ocurrencias normalizadas** | La PK pasa a incluir `accn`, y la identidad económica se resuelve arriba con `econ_key` sobre `derived.fact` — que ya tiene la columna |

**La opción B es la coherente con el resto del sistema**: `derived.fact` ya
tiene `econ_key`, `parsed.facts` conserva la ocurrencia, y `cnv_estados_v2` ya
migró su PK a `(accn, concepto)` por esta misma razón. Pero es una decisión de
arquitectura y este sprint no la toma.

Antes de decidir conviene **repetir esta auditoría sobre otro emisor**: 2 pares
de un solo emisor no alcanzan para generalizar (R3).

---

## Protecciones

| control | resultado |
|---|---|
| branch | `feat/cnv-canonical` |
| commit | `4cf1aa5` |
| archivos nuevos | `c9_w13a_occurrence_audit.py`, `test_w13a_occurrence_audit.py` — sin trackear |
| archivos modificados de este sprint | **ninguno** |
| ratio engine | **sin tocar** — mtime del 02-09, anterior a este sprint |
| esquema canónico / migraciones | sin modificar |
| SEC en `cnvmig` | 133.902 · `63629c0fc2ee76ad8038660c4815b443` |
| SEC en `metrgolden` | 133.902 · `63629c0fc2ee76ad8038660c4815b443` |
| SEC en `metrsem` | 133.902 · `63629c0fc2ee76ad8038660c4815b443` |
| METR en `cnvmig` (certificado) | 2.875 · `84249140c005f834468fbb1a1b993826` |
| `screener.db` | `2026-08-23 13:42:23` · 1.504.714.752 bytes |
| producción 5432 | esquema `public` |

**Tests: `tests/test_w13a_occurrence_audit.py` — 14 pasan.** Fijan el censo de
152, su estabilidad, que `accn` es la única diferencia, que son 2 pares de
documentos, que ninguna clasificación se apoya sólo en el ordinal, y las cinco
protecciones.

> Un test propio falló primero y estaba mal planteado: comparaba el ratio engine
> del worktree contra el del repo principal, pero **difieren a propósito desde
> F-061**, que migró la selección de insumos de `cik` a `entity_id`. La
> referencia correcta es temporal: ninguno se modificó **durante este sprint**.

---

## Las diez preguntas

| # | pregunta | respuesta |
|---|---|---|
| 1 | ¿Qué son exactamente las 152? | **76 conceptos × 2 pares de documentos**. Dos presentaciones que repiten lo que otra ya declaró para el mismo período y perímetro |
| 2 | ¿Cuántas son duplicados técnicos? | **0** — los SHA de archivo difieren |
| 3 | ¿Cuántas son republicaciones? | **152** (100 %), confianza ALTA |
| 4 | ¿Cuántas son potenciales restatements? | **0** — cero valores cambiados |
| 5 | ¿Cuántas son diferencias económicas reales? | **0** |
| 6 | ¿Qué se pierde? | **Sólo la identidad documental** de la 2ª presentación: su `accn` y su SHA. Cero información económica |
| 7 | ¿`accn` en la identidad de ocurrencia? | **SÍ** — es lo único que las distingue |
| 8 | ¿`accn` en `econ_key`? | **NO** — crearía dos hechos económicos donde hay uno |
| 9 | ¿Qué define la identidad económica? | `entity_id`, concepto, **perímetro**, `period_kind`, `start_date`, `end_date`, `unit_measure`, **`measurement_date`**. Pendientes de decidir: `es_nil` y `escala` |
| 10 | ¿Qué modelo hace falta? | Ocurrencia con `accn` + identidad económica sin él + un orden total declarado entre ocurrencias del mismo hecho. **Falta la fecha de publicación**, que la CNV no expone |

---

### Entregables

```
outputs/docs/fase_cnv/
├── W13A_OCCURRENCE_AUDIT.md          este informe
└── W13A_OCCURRENCE_GROUPS.csv        152 grupos × 30 campos

worktree catalaxia-cnvmig/
├── scripts/engine/c9_w13a_occurrence_audit.py
└── tests/test_w13a_occurrence_audit.py        14 tests
```
