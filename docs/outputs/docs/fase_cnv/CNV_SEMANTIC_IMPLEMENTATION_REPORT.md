# CNV — IMPLEMENTACIÓN SEMÁNTICA (W-1.2)

**Fecha:** 2026-09-02
**Worktree:** `catalaxia-cnvmig` · rama `feat/cnv-canonical` · DB fixture `cnvmig`
**Base homologada `catalaxia`:** **no modificada** — prueba en §13
**Contratos implementados:** `W1_1_FACT_IDENTITY_CONTRACT.md` §4 · `CNV_W1_W2_SEMANTIC_REPORT.md` §2

---

## 1 · Cambios realizados

### Semántica de período (Objetivo 1)

El adaptador escribía `period_kind='INSTANT'` para los 2.697 hechos, sin
`start_date`. **1.002 de ellos eran flujos** aplanados a un instante.

La clasificación **no sale del nombre**. Sale del plan de cuentas de la CNV,
cuyo primer dígito declara el estado al que pertenece la partida:

| prefijo | estado | naturaleza |
|---|---|---|
| `1xxxxxx` | Activo | saldo → `INSTANT` |
| `2xxxxxx` | Pasivo y Patrimonio | saldo → `INSTANT` |
| `3xxxxxx` | Resultados y Flujos | acumulado → `DURATION` |
| `8xxxxxx` | Calculados por la CNV | según sus insumos |

Los 51 conceptos del corpus quedaron clasificados en
`scripts/engine/c4_cnv_semantica.py::NATURALEZA`, cada uno con su código CNV al
lado. Un concepto sin clasificar **no se adivina**: `naturaleza_de()` devuelve
`None` y la fila se excluye y se censa.

### De dónde sale `start_date`

`FechaDesde` y `FechaHasta` **existen como propiedades en el documento y están
vacías en los 56**. La CNV no declara el inicio del período. Pero sí declara:

- **`PeriodoBalance`** — el campo estructurado con la clase de estado. Medido
  sobre 2.453 documentos: `PB=1` se concentra en el mes de cierre anual de cada
  emisor, `PB=3` se reparte por todos los meses. Reemplaza a `tipo` ('A'/'P'),
  que **discrepa con él en 754 documentos** y que el propio parser advierte que
  antes adivinaba.
- **`FechaCierre`** — el cierre del estado.

Con eso, el inicio se **deriva**, no se inventa: el cierre de ejercicio es el
`FechaCierre` de los documentos que el emisor declaró anuales (`PB=1`), y el
inicio de un flujo es el día siguiente al cierre anterior.

```
METR · 16 documentos con PeriodoBalance=1  ->  cierre de ejercicio: 12-31
```

Si un emisor no tuviera documentos anuales, o declarara más de un cierre,
`cierre_fiscal()` devuelve `None` y sus flujos se excluyen. **No se les inventa
una duración.**

### Los flujos son acumulados del ejercicio, no del trimestre

Verificado en METR CONSOLIDADO 2025 y ahora representado así:

```
2025-01-01 -> 2025-03-31      205,2 MM   CONSOLIDADO|DURATION|2025-01-01|2025-03-31|2025-03-31
2025-01-01 -> 2025-06-30      504,2 MM   CONSOLIDADO|DURATION|2025-01-01|2025-06-30|2025-06-30
2025-01-01 -> 2025-09-30      898,6 MM   CONSOLIDADO|DURATION|2025-01-01|2025-09-30|2025-09-30
2025-01-01 -> 2025-12-31    1.217,3 MM   CONSOLIDADO|DURATION|2025-01-01|2025-12-31|2025-12-31
```

### `context_id` (Objetivo 2)

**La fórmula de `fact_key` no cambió.** Sigue siendo
`sha256(entity_key|accession|qname|context_id|unit_measure)`. Lo que cambió es
que el contexto ahora dice lo que un contexto tiene que decir:

```
antes:    CONSOLIDADO@2025-12-31
ahora:    CONSOLIDADO|DURATION|2025-01-01|2025-12-31|2025-12-31
          CONSOLIDADO|INSTANT||2025-12-31|2025-12-31
```

Efecto estructural medido:

| | antes | ahora |
|---|--:|--:|
| contextos distintos | 56 | **112** |
| contextos por documento | 1,0 | **2,0** |
| violaciones de INV-CTX | — | **0** |

Cada documento produce ahora dos contextos —uno de saldos y uno de flujos—
donde antes los colapsaba en uno.

### `measurement_date` (Objetivo 3)

Sale de **`FechaCierre`**, el campo estructurado que el documento declara. No se
deriva ni se infiere. Bajo IAS 29 toda cifra se expresa en el poder adquisitivo
del cierre del estado, y eso es exactamente lo que ese campo dice.

Poblada en **2.697/2.697**, rango 2018-12-31 … 2025-12-31. El auditor la
recalcula releyendo los 56 HTML: **0 desvíos**.

`migrations/engine/035_measurement_date.sql` la agrega como columna nullable en
`parsed.facts` y `derived.fact`. Es aditiva: los 133.902 hechos SEC quedan en
`NULL` y ni su `fact_key` ni su `context_id` cambian. **No crea `econ_key`,
`effective_from/to` ni `supersedes`.**

### Unidades (Objetivo 4) y naturalezas (Objetivo 6)

El vocabulario **no se inventó**: es el que la propia base ya usa para SEC.

| naturaleza | `unit_measure` | `unit_kind` | `currency` | precedente SEC |
|---|---|---|---|---|
| monetaria | `iso4217:ARS` | `SIMPLE` | `ARS` | 122.517 hechos |
| adimensional | `xbrli:pure` | `SIMPLE` | `NULL` | 5.356 hechos |
| por acción | `iso4217:ARS/xbrli:shares` | `DIVIDED` | `ARS` | **114 hechos con esa cadena exacta** |

No se creó ninguna taxonomía nueva.

### `decimals` (Objetivo 5)

`ESCALA_A_DECIMALS` **se eliminó**. `decimals` es una aserción de precisión; la
CNV declara `UnidadMedida`, que es una escala de presentación. No son lo mismo,
y usar una como la otra destruía el dato: con `decimals=-6` un ratio de 0,555 se
redondea a **0**.

La CNV no publica precisión, así que `decimals = NULL` en los 2.697. Es
admisible: 10.819 hechos SEC ya lo tienen.

**La escala no se perdió.** Sobrevive en `unit_ref`, que es donde corresponde
—la referencia a la unidad declarada por el documento—:

```
ars@1e6  1.120     ars@1e3  915     pure  555     ars-por-accion  107
```

---

## 2 · Archivos modificados

| Archivo | Estado |
|---|---|
| `scripts/engine/c4_cnv_semantica.py` | **nuevo** · funciones puras de período y unidad |
| `scripts/engine/c4_cnv_adapter.py` | cableado · `ESCALA_A_DECIMALS` eliminado · v2.0 |
| `migrations/engine/035_measurement_date.sql` | **nuevo** · aditiva, solo fixture |
| `scripts/engine/c4_auditoria_cnv.py` | ampliado · secciones F y G |
| `tests/test_w12_semantica_cnv.py` | **nuevo** · 20 tests |
| `tests/test_w1_w2_semantica.py` | un test invertido — ver §4 |

**No se tocó:** ratio engine, Identity, Market, SEC, publicación, migraciones de
producción, ni la base homologada.

---

## 3 · Tests RED antes de implementar

Escritos **antes** del código, ejecutados contra el adaptador anterior:

```
13 failed, 7 passed
```

| Falla | Por qué |
|---|---|
| T1, T2, T2b | `contexto()` no existía; el `PERIMETRO@cierre` no separaba Q4 de FY |
| T4, T4b | no había un solo hecho `DURATION`: los 2.697 eran `INSTANT` |
| T5, T6, T9 | los 12 ratios y los 2 EPS estaban marcados `iso4217:ARS` |
| T7, T8 | `decimals` valía −3 / −6 (la escala del documento) |
| T14, T15, T15b | `unidad_de()` no existía |

Los 7 que pasaban lo hacían por razones triviales —T3 "INSTANT sin start_date"
se cumplía porque *todo* era INSTANT— o eran los controles de SEC intacto.

---

## 4 · Tests GREEN después

```
tests/test_w12_semantica_cnv.py     20 passed
suite completa                      275 passed · 3 failed · 1 skipped
```

Las 3 fallas son `test_f038_traza_corrida.py`, **preexistentes** y registradas
como tales desde `DAY3_IMPLEMENTATION_REPORT.md`.

**Un test cambió de sentido, y hay que decirlo.**
`test_w2_medida_real_de_los_hechos_mal_unificados` medía el defecto: los 662
hechos adimensionales marcados como pesos. Al corregirse, empezó a fallar —
correctamente. Se invirtió en `test_w2_ningun_adimensional_quedo_en_unidad_monetaria`,
que ahora exige la propiedad en vez de describir la falla. Un test que solo
documenta un defecto deja de servir apenas se arregla.

> Nota de método: una corrida arrojó un `ERROR` en `test_f035_entidad_muerta`.
> No se reprodujo ni en aislamiento (23/23) ni al repetir la suite. Fue una
> colisión entre dos corridas de pytest simultáneas contra el mismo fixture,
> no un efecto de estos cambios.

---

## 5 · Mutation tests

| Mutación | Resultado esperado | Resultado |
|---|---|---|
| **T14** · sacar `start_date` de la construcción del contexto | Q4 y FY deben colapsar en el mismo contexto | colapsan ✔ |
| **T15** · reemplazar `xbrli:pure` por unidad monetaria en un ratio | la comprobación de T5 debe fallar | falla ✔ |
| **T15b** · los 14 conceptos, uno por uno | cada uno con su unidad declarada | 14/14 ✔ |

Si T14 no colapsara, T1 estaría pasando por otra razón y no probaría lo que dice.

---

## 6 · Cardinalidades antes / después

| | antes | después |
|---|--:|--:|
| filas en el origen | 2.747 | 2.747 |
| admitidas | 2.697 | 2.697 |
| excluidas (sin perímetro) | 50 | 50 |
| excluidas (concepto sin clasificar) | — | **0** |
| excluidas (flujo sin ejercicio) | — | **0** |
| `parsed.facts` | 2.697 | 2.697 |
| `derived.fact` | 2.697 | 2.697 |
| `fact_key` distintas | 2.697 | 2.697 |

---

## 7 · Distribución de `period_kind`

| | monetario | adimensional | por acción | total |
|---|--:|--:|--:|--:|
| `DURATION` | 1.002 | 314 | 107 | **1.423** |
| `INSTANT` | 1.033 | 241 | — | **1.274** |

Duraciones producidas: 89–90 días (354), 180–181 (331), 272–273 (331),
364–365 (407). El ±1 día son los años bisiestos.

Antes: 2.697 `INSTANT`, 0 `DURATION`.

---

## 8 · Distribución de unidades

| `unit_measure` | `unit_kind` | `currency` | hechos |
|---|---|---|--:|
| `iso4217:ARS` | `SIMPLE` | ARS | 2.035 |
| `xbrli:pure` | `SIMPLE` | `NULL` | 555 |
| `iso4217:ARS/xbrli:shares` | `DIVIDED` | ARS | 107 |

Antes: 2.697 en `iso4217:ARS`.

---

## 9 · Distribución de `decimals`

| valor | hechos |
|---|--:|
| `NULL` | **2.697** |

Antes: −3 y −6 según la escala del documento. Escalas presentes en el origen:
1.000 y 1.000.000 — ahora en `unit_ref`, no en `decimals`.

353 ratios tienen valor absoluto menor que 1. **Ninguno se anula** al aplicar
sus propios `decimals`.

---

## 10 · Casos excluidos

```
filas CNV en origen: 2.747
  admitidas                                    2.697
  EXCLUIDAS · sin perímetro declarado             50   (1 documento)
  EXCLUIDAS · concepto sin clasificar              0
  EXCLUIDAS · flujo sin ejercicio determinable     0
```

Las 50 se conservan excluidas y declaradas, como pedía el ciclo. Son un solo
documento sin `tipo_balance`: asignarlo a INDIVIDUAL o CONSOLIDADO sería
inventar de qué estado viene. Un `assert` verifica que el censo cierre.

---

## 11 · Idempotencia

| corrida | `parsed.facts` | `derived.fact` |
|---|---|---|
| 1ª | 2.697 insertados | 2.697 insertados |
| **2ª** | **0 insertados · 2.697 reusados** | **0 insertados · 2.697 sin cambio** |

La rama de conflicto sigue vigente: ante un `fact_key` presente con otro valor,
reporta y **no sobrescribe**.

---

## 12 · Auditoría independiente

`scripts/engine/c4_auditoria_cnv.py` — **no importa** `c4_cnv_adapter` ni
`c4_cnv_semantica`. Vuelve al SQLite y a los HTML y reconstruye por su cuenta.

```
30 verificaciones OK  ·  0 fallas  ·  1 aviso
```

**Lo que lo hace capaz de detectar una regresión que el adaptador no vería:**
para la parte más delicada —si un hecho es de saldo o de flujo— el auditor no
consulta ninguna tabla de conceptos. **Lo mide.** Un flujo publicado como
acumulado vale en marzo una fracción de lo que vale en diciembre; un saldo no.

```
flujos   Q1/FY  0,17 – 0,29     COGS, Revenue, EBITDA, NetIncome, CF_*, EPS…
saldos   Q1/FY  0,58 – 0,71     Assets, Equity, Cash, Liabilities, Inventory…
```

37 conceptos monetarios medidos, **0 discrepan** con lo persistido.

> **El auditor encontró algo y no se lo silenció.** En su primera versión medía
> el discriminante solo sobre METR y marcó `Inventory` como discrepante
> (Q1/FY = 0,408, clasificado `INSTANT`). Investigado: en METR el inventario es
> el **0,004% del activo** y aporta 6 observaciones que son 3 pares duplicados
> — ruido, no señal. Sobre el corpus completo aporta 273 observaciones y da
> 0,693, inequívocamente un saldo. **La corrección fue ampliar la muestra a las
> 72 empresas, no mover el umbral hasta que coincidiera**: la naturaleza de un
> concepto es una propiedad del plan de cuentas de la CNV, no del emisor.

El auditor además re-deriva el cierre de ejercicio releyendo `PeriodoBalance` de
los 56 HTML con sus propias expresiones regulares, y recalcula
`measurement_date` desde `FechaCierre`: **0 desvíos**.

**Límite declarado:** el discriminante no aplica a los 12 ratios ni al EPS. En
un cociente de dos flujos la acumulación se cancela —`EBIT/Intereses` vale casi
lo mismo en marzo que en diciembre—, así que ahí la prueba no discrimina y el
auditor lo dice en vez de forzarla.

---

## 13 · `catalaxia` no fue modificada

| | `catalaxia` | `cnvmig` |
|---|--:|--:|
| migraciones | **34** | 36 |
| `derived.fact` | **133.902** | 136.599 |
| `parsed.facts` | **225.475** | 228.172 |
| hechos CNV | **0** | 2.697 |
| columna `entity_id` | **no existe** | existe |
| columna `measurement_date` | **no existe** | existe |

### SEC intacto — seis digests contra la línea de base

Capturada **antes** de implementar y comparada después:

| | resultado |
|---|---|
| hechos SEC | **IGUAL** — 133.902 |
| digest de `fact_key` | **IGUAL** — `b9d03247d74fd0e1…` |
| digest de `context_id` | **IGUAL** — `ae02a04825c662d7…` |
| digest de `source_hash` | **IGUAL** — `a34b919f7d9936f5…` |
| ratios vigentes | **IGUAL** — 36 |
| digest de ratios | **IGUAL** — `45036e13c5b1fdee…` |

El motor de ratios re-ejecutado devolvió `SIN_CAMBIO 36`.

---

## 14 · Riesgos restantes

**R-1 · El `period_kind` de los 12 ratios no tiene validación empírica.** Se
clasificó desde las fórmulas verificadas en W-2 (cociente de saldos → `INSTANT`;
con algún flujo → `DURATION`), pero el discriminante del auditor no puede
confirmarlo porque la acumulación se cancela. Es la clasificación mejor
fundada disponible, no una medición.

**R-2 · `CashFlowNeto` queda cerca del borde** (Q1/FY = 0,437 contra un umbral
de 0,45). Clasificado `DURATION` por su código `3240000` y por ser la variación
de caja del período. El auditor lo acepta pero el margen es angosto.

**R-3 · CNV sigue sin fecha de publicación** (0 de 2.697 con `filing_date`).
Es la O1 de W-1.1: sin ella no hay orden entre ocurrencias y `supersedes` no se
puede computar. Requiere extender `fetch_raw.cnv_presentation` de 3 a 72 CUITs
— un fetch, fuera del alcance de este ciclo.

**R-4 · `econ_key`, `effective_from/to` y `supersedes` no están implementados**,
por instrucción explícita del ciclo. `measurement_date` y el período completo
—sus insumos— ya están.

**R-5 · La fórmula de `roe`, `roa`, `margen_neto` y `cobertura_intereses` sigue
sin reproducir** el valor publicado en la mayoría de los documentos. Es un
problema de fórmula, no de unidad ni de período, y quedó fuera del ciclo.

**R-6 · Un solo emisor.** METR. Los otros 55 `byma_only` no se migraron. La
clasificación de conceptos sí cubre el corpus completo: los 51 conceptos de
METR son **todos** los que existen en las 72 empresas.

**R-7 · `tipo` ('A'/'P') sigue en el origen y sigue siendo poco confiable.** El
adaptador ya no lo usa —usa `PeriodoBalance`—, pero cualquier otro consumidor de
`cnv_estados_norm` lo seguirá leyendo.

---

## 15 · Criterio de PASS

| Condición | Estado |
|---|---|
| Q4/FY inequívocamente separados | ✔ contextos distintos · `fact_key` distintas · T1/T2/T14 |
| duration tiene duración real | ✔ 1.423 hechos, 0 mal formados, 89–365 días |
| instant permanece instant | ✔ 1.274 hechos, 0 con `start_date` |
| ratios son `pure` | ✔ 555 hechos, `currency NULL` |
| EPS es `DIVIDED` | ✔ 107 hechos, `iso4217:ARS/xbrli:shares` |
| `decimals` no deriva de la escala | ✔ 2.697 en `NULL`; escala en `unit_ref` |
| `fact_key` SEC no cambia | ✔ digest idéntico sobre 133.902 |
| entity ownership correcto | ✔ `CUIT:30657863676`, 0 violaciones F-061 |
| adaptador idempotente | ✔ 2ª corrida: 0 insertados |
| las mutaciones prueban protecciones reales | ✔ T14, T15, T15b |
| el auditor independiente coincide | ✔ 30/30, y detectó un caso que investigar |
| sin pérdida silenciosa | ✔ censo cierra: 2.747 = 2.697 + 50 |
| `catalaxia` intacta | ✔ 34 migraciones, 0 hechos CNV |

```
CNV_SEMANTIC_IMPLEMENTATION = PASS
```

No se hizo commit ni integración. Los cambios viven en el worktree
`catalaxia-cnvmig` y en el fixture `cnvmig`.
