# CNV W-1.3A — PRESERVACIÓN DE OCURRENCIAS · INFORME DE IMPLEMENTACIÓN

**Fecha:** 2026-09-02 · **Worktree:** `catalaxia-cnvmig`
**Baseline:** `CNV_W13A_OCCURRENCE_BASELINE.md` · **Auditoría:** `CNV_W13A_AUDIT.md`
**Sin commits · sin integración**

---

## 1 · La pregunta del ciclo, respondida

> ¿Puede Catalaxia preservar TODAS las ocurrencias documentales necesarias para
> decidir después qué ocurrió entre ellas?

**Sí.**

```
RAW  (2.364 documentos)
 │
 ├── 103.268 conceptos parseados
 │
 ├── ocurrencia A ──┐
 │                   ├── identidad económica X
 └── ocurrencia B ──┘

103.268 ocurrencias  ->  102.976 identidades económicas   (1,0028 a 1)
      0 pérdidas · 0 duplicados · 292 identidades con dos ocurrencias
```

---

## 2 · El cambio

La clave dejó de ser la identidad económica y pasó a ser la ocurrencia
documental. **En los dos puntos de la cadena**, porque arreglar solo uno no
alcanzaba:

| script | antes | ahora |
|---|---|---|
| `job5_v2_extract_eeff.py` | `PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)` + `INSERT OR IGNORE` | **`PRIMARY KEY (accn, concepto)`** + `INSERT OR REPLACE` |
| `s0_normalizar_cnv.py` | la misma PK + `INSERT OR REPLACE` | **`PRIMARY KEY (accn, concepto)`** |

`s0` era el punto que faltaba: con la clave económica y `OR REPLACE` habría
vuelto a colapsar las ocurrencias recién preservadas, conservando **la última**
en vez de la primera. El mismo defecto, en sentido opuesto.

### Por qué `accn` y no otra cosa (§3)

Candidatos evaluados: `accn`, `Presentación #N`, `sha256` del archivo,
`fecha_publicacion`, `presentation_id`.

| candidato | cobertura | ¿sirve como clave? |
|---|--:|---|
| **`accn` (GUID)** | **2.364/2.364** | **sí** — ya es columna, uno por archivo `eeff_html/{accn}.html`, estable |
| `Presentación #N` | 2.364/2.364 | sirve para **ordenar**, no como clave: es un dato del título, no una columna |
| sha256 del archivo | 2.364/2.364 | redundante con `accn` y cambia si el archivo se recomprime |
| `fecha_publicacion` | 3 de 72 CUITs | insuficiente |

**No se inventó ningún identificador.** `accn` ya estaba.

### Por qué `OR REPLACE` y no `OR IGNORE`

Con la clave por documento, **las dos preservan igual** — medido en el test
`M2b`. Se eligió `REPLACE` por otra razón: que reprocesar un RAW con un parser
corregido actualice el valor en vez de conservar el viejo. Reingerir el mismo
documento deja el mismo estado.

### El valor NO entra en la clave (§4)

Ni para unir ni para separar. Tres documentos con valores `100 / 110 / 100` son
tres ocurrencias (test I5), y dos documentos con el mismo valor siguen siendo
dos (mutación M5). Decidir qué pasó entre ellos es W-1.4.

---

## 3 · Tests: RED antes, GREEN después

Escritos **contra el esquema real extraído del job** (`SCHEMA_V2`, `SQL_INSERT`),
antes de tocar la clave. Ningún umbral ni fixture se ajustó para ocultar nada.

```
antes del arreglo:   5 failed, 5 passed
después:            16 passed
```

| | invariante | antes |
|---|---|---|
| I1 | dos documentos no se pierden por compartir identidad | **FALLA** — 1 de 2 |
| I2 | reingerir el mismo documento es idempotente | pasa (por el defecto) |
| I3 | dos documentos = dos ocurrencias | **FALLA** — 3 → 1 |
| I4 | misma identidad no implica supersesión | pasa |
| I5 | valores distintos no implican restatement | **FALLA** |
| I6 | el caso BYMA se preserva | **FALLA** — solo `863efe00` |
| I7 | los hechos perdidos son recuperables del RAW | pasa |
| I8 | ninguna ocurrencia se pierde al ingerir | **FALLA** — 866 → 468, **398 perdidas** |
| I9 | el mismo RAW produce el mismo resultado | pasa |

Suite completa: **316 passed · 3 failed · 1 skipped**. Las 3 son
`test_f038_traza_corrida`, preexistentes.

---

## 4 · Mutaciones

| | mutación | esperado | resultado |
|---|---|---|---|
| M1 | reintroducir la PK vieja | preservación falla | ✔ colapsa a 1 |
| M2 | `OR IGNORE` con la PK vieja | falla, y conserva **la primera** | ✔ conserva `DOC-A` = 11.060.815, la que la serie desmiente |
| M3 | quitar el identificador documental | falla | ✔ |
| M4 | usar `econ_key` como identidad de ocurrencia | falla | ✔ |
| M5 | usar el valor para diferenciar ocurrencias | falla | ✔ dos documentos con el mismo valor se vuelven uno |

**Hallazgo de M2b, que corrige una atribución del enunciado.** Con la clave
`(accn, concepto)`, `INSERT OR IGNORE` **ya no pierde nada**. El culpable era la
**clave**, no la cláusula: `OR IGNORE` solo es destructivo cuando la clave es la
equivocada. Se deja escrito porque cambia dónde hay que mirar si el problema
reaparece.

---

## 5 · Los 292 hechos, recuperados y clasificados (§8)

Reingesta desde RAW con la clave corregida, sobre el fixture aislado:

```
conceptos leídos del RAW (incluye códigos no mapeados)   154.623
filas parseadas y mapeadas a concepto                    103.268
  (códigos sin mapeo, descartados por contrato)           51.355
OCURRENCIAS conservadas                                  103.268
identidades económicas distintas                         102.976
```

### El delta contra la tabla vieja, sin nada sin explicar

```
cnv_estados_v2 (clave vieja)   102.323
ocurrencias (clave nueva)      103.268      +945

  (a) 14 documentos que v2 nunca tuvo            653
  (b) ocurrencias recuperadas de los 7 pares     292
  (c) resto                                        0
                                               -----
                                                 945
```

### Clasificación de las 292 (§8)

| clase | casos | qué es |
|---|--:|---|
| **A · duplicado exacto del mismo documento** | **0** | no existe: la clave lo impide por construcción |
| **B · misma identidad, mismo valor** | **66** | compatible con republicación |
| **D · misma identidad, valores distintos** | **226** | requiere decisión |
| **E · conflicto de perímetro** | ⊂ D | 6 de los 7 pares, detectados por el auditor |
| **C / F** | — | no separables todavía |

**No se decidió automáticamente ninguna como restatement.** El objetivo era
preservar y clasificar; interpretar es W-1.4.

---

## 6 · El caso BYMA (§7)

| | |
|---|---|
| serie CONSOLIDADO `PPE` | 2021-06-30 → 1.363 M · **2021-09-30 → 1.481 M** · **2022-03-31 → 1.835 M** |
| serie INDIVIDUAL del mismo emisor | 11–12 millones |
| documento conservado antes (`863efe00`) | **11.060.815** — el orden de la serie individual |
| documento descartado (`ee3e755d`) | **1.593.406.319** — el valor que la serie consolidada exige |
| `TipoBalance` declarado | `Consolidado` en **los dos**, una sola vez cada uno |
| `FechaCierre`, `UnidadMedida`, `PeriodoBalance` | idénticos en los dos |
| presentaciones | #2864462 y #2864443 |

La secuencia demuestra que `INSERT OR IGNORE` había preservado el valor
incorrecto: conserva **el que llega primero**, y acá el primero es el que la
serie desmiente.

**Ahora están los dos.** Queda como fixture de regresión (test I6) y **no se
codificó ninguna excepción para BYMA**: la corrección es estructural.

---

## 7 · Presentación #N, medida (§9)

No se asumió monotonicidad: se midió.

| | |
|---|--:|
| documentos con `Presentación #N` | **2.364 / 2.364** |
| duplicados | **0** |
| reinicios de la numeración | **0** |
| rango | #2.409.231 … #3.529.130 |
| densidad | 0,21 % (los huecos son presentaciones de otros emisores) |
| **monotonicidad global** vs `period_end` | **NO** — 133 inversiones de 2.363 (5,6 %) |
| **monotonicidad dentro de cada emisor** | 34 inversiones de 2.292 pares (**1,48 %**) |
| emisores con alguna inversión | 25 de 72 |

**Globalmente no es monótono, y no tiene por qué serlo**: emisores distintos
presentan en momentos distintos. Dentro de cada emisor, el 1,48 % de inversiones
corresponde a presentaciones con número mayor sobre períodos anteriores — que es
exactamente la señal que W-1.4 va a necesitar.

**Sirve para ordenar ocurrencias de una misma identidad: 292 de 292 grupos son
ordenables.**

---

## 8 · Fecha de publicación (§10)

Sin fetch externo. Todo local.

| fuente | contenido | cobertura |
|---|---|--:|
| `derived.fact.filing_date` | — | 0 de 2.697 |
| `fetch_raw.cnv_presentation.fecha_publicacion` | fecha real | **3 de 72 CUITs** |
| título del RAW `Presentación #N` | ordinal | **2.364 de 2.364** |

Relación entre ambos, sobre los 3 CUITs que tienen las dos: 9.167 pares,
**112 inversiones (1,22 %)**, todas de 1 a 2 días.

**No se corrigieron.** Son compatibles con que el número se asigne al crear el
trámite y la fecha al publicarlo. Quedan reportadas.

---

## 9 · Las cuatro cardinalidades (§14)

| nivel | cantidad |
|---|--:|
| conceptos leídos del RAW | 154.623 |
| filas parseadas y mapeadas | 103.268 |
| **ocurrencias documentales** | **103.268** |
| **identidades económicas** | **102.976** |

La reducción `ocurrencias → identidades` es **1,0028 a 1** y está modelada como
relación muchos-a-uno explícita: cada ocurrencia conserva su `accn` y la
identidad se obtiene agrupando, nunca sobrescribiendo.

Los 51.355 códigos leídos del RAW y no mapeados son códigos CNV fuera de los 51
del contrato. Se descartan por contrato, no en silencio: el número está acá.

---

## 10 · W-1.2 y W-1.3 no se rompieron (§15)

Este ciclo **no tocó** el adaptador, ni la capa canónica de Postgres, ni ninguna
migración. Verificado:

| | |
|---|---|
| hechos CNV en `derived.fact` | **2.697** — digest `fact_key` **idéntico** |
| `context_id` | digest **idéntico** |
| `period_kind` | 1.423 DURATION · 1.274 INSTANT |
| `measurement_date` | 2.697 pobladas |
| `econ_key` | 2.697 pobladas |
| `decimals` no nulos | **0** |
| 50 exclusiones | sin cambios |

```
W1.2 = PASS  ·  W1.3 = PASS
```

---

## 11 · SEC intacto (§16)

| | resultado |
|---|---|
| hechos SEC | **IGUAL** — 133.902 |
| digest `fact_key` | **IGUAL** |
| digest `context_id` | **IGUAL** |
| digest `source_hash` | **IGUAL** |
| digest de ratios | **IGUAL** |

```
SEC_UNCHANGED = PASS
```

---

## 12 · `catalaxia` intacta (§17)

```
migraciones      34
derived.fact     133.902
hechos CNV            0
```

Y el repo principal tampoco se tocó: `job5_v2_extract_eeff.py` y
`s0_normalizar_cnv.py` siguen con la PK vieja allí (`git status` limpio para
ambos), y `screener.db` conserva su mtime original — se abrió **solo en modo
lectura**. Todo el cambio vive en el worktree y en
`catalaxia-cnvmig/data/w13a_fixture.db`.

**Reversible eliminando los artefactos del fixture.**

---

## 13 · Auditoría independiente (§13)

`scripts/engine/c4_auditoria_w13a.py` — **13 OK · 0 fallas · 1 aviso**. Detalle
en `CNV_W13A_AUDIT.md`.

Lo relevante: con **su propio parser y su propia lista de códigos**, leyó
exactamente los mismos 103.268 conceptos, y **marcó por su cuenta 6 de los 7
pares** como divergencia de perímetro probable — dejando fuera FIPL, que es el
único compatible con una republicación real.

---

## 14 · Riesgos y cuestiones abiertas

**R-1 · La corrección vive en el worktree, no en el pipeline real.** El repo
principal sigue perdiendo ocurrencias en cada ingesta. Integrarlo requiere,
además del cambio de PK, **recrear las dos tablas** —SQLite no permite alterar
una PRIMARY KEY— y reprocesar el RAW.

**R-2 · 89 documentos sin RAW en disco** (2.453 conocidos − 2.364 con archivo).
Quedan fuera de toda la cadena y no se pueden auditar.

**R-3 · Hay un valor incorrecto en la tabla de producción** para BYMA
2021-12-31 CONSOLIDADO. En el fixture están las dos ocurrencias; en producción
sigue solo la que la serie desmiente.

**R-4 · `tipo_balance` tiene errores en origen**, confirmado por el auditor en 6
pares: el documento declara un perímetro que su contenido contradice.

**R-5 · El 1,48 % de inversiones del ordinal dentro de cada emisor** no se
corrigió. Puede ser ruido de numeración o presentaciones tardías sobre períodos
anteriores; distinguirlo es W-1.4.

**R-6 · Las 292 quedan preservadas y sin interpretar.** Es el objetivo del
ciclo, pero significa que hoy hay 292 identidades con dos valores y **nada dice
cuál exponer**. Ningún consumidor debe leer esa tabla hasta que W-1.4 decida.

---

## 15 · Dictamen

| condición de PASS | estado |
|---|---|
| el defecto queda reproducido por test antes | ✔ 5 failed / 5 passed |
| queda corregido después | ✔ 16 passed |
| dos ocurrencias documentales pueden coexistir | ✔ 292 identidades con 2 |
| la reingesta del mismo documento es idempotente | ✔ I2, I9 |
| los 292 hechos perdidos son recuperables | ✔ recuperados y clasificados |
| el caso BYMA queda preservado | ✔ los dos valores, sin excepción codificada |
| no hay pérdida silenciosa | ✔ 0 descartadas · delta explicado 653 + 292 = 945 |
| Presentación #N queda medida | ✔ incluida la NO monotonicidad global |
| publication date queda medida | ✔ 3 de 72 CUITs, inversiones reportadas |
| W-1.2 sigue PASS | ✔ digests idénticos |
| SEC intacto | ✔ 5 digests |
| `catalaxia` intacta | ✔ |
| auditor independiente coincide | ✔ 13 OK |
| las mutaciones fallan donde deben | ✔ M1–M5 |

```
CNV_W13A_OCCURRENCE_PRESERVATION = PASS_WITH_WARNINGS
```

**PASS** en las catorce condiciones de aceptación.

**WITH_WARNINGS** por lo que el propio enunciado admite como causal: quedan
contradicciones en el ordenamiento por publicación —1,48 % de inversiones dentro
de emisor, 1,22 % contra la fecha real— y quedan **292 casos cuya relación
semántica no puede determinarse todavía**, que es exactamente lo que W-1.4 va a
resolver.

La evidencia documental está preservada. Ahora se puede decidir qué ocurrió
entre las ocurrencias, porque por primera vez están las dos.
