# W-1.1 — CONTRATO DE IDENTIDAD DE UN HECHO

**Fecha:** 2026-09-02
**Alcance:** análisis y fixtures. **No se modificó** adaptador, engine, esquema,
migraciones, datos ni la base homologada.
**Fixtures:** `tests/test_w11_invariantes_identidad.py` (11/11) ·
`tests/test_w1_w2_semantica.py` (11/11)
**Corpus:** `cnvmig` — 133.902 hechos SEC · 2.697 hechos CNV · 45.791 contextos

---

## 1 · Definiciones formales

**Hecho económico.** Una magnitud atribuible a un emisor, referida a un
concepto, un perímetro y un período, expresada en una unidad de medida.
Existe con independencia de que alguien la publique. Dos publicaciones del
mismo hecho económico son el mismo hecho.

**Ocurrencia documental.** La aparición de un hecho económico en un documento
determinado, publicado en una fecha determinada. Un hecho económico tiene una o
más ocurrencias, ordenadas por fecha de publicación.

**Medición.** La expresión de un hecho económico en una unidad. Cambiar la
unidad —de dólares a euros, o de moneda de dic-2023 a moneda de dic-2025 bajo
IAS 29— **produce otro hecho**, no una corrección del anterior. Ambas
mediciones son simultáneamente válidas.

**Supersesión.** La relación entre dos ocurrencias del **mismo** hecho
económico —misma unidad, misma medición— cuando la posterior corrige a la
anterior. Sólo una queda efectiva.

**Republicación / comparativo.** Una ocurrencia posterior del mismo hecho
económico con el mismo valor. Es un caso particular de supersesión, en el que
la ocurrencia nueva reafirma en lugar de corregir.

La distinción que este contrato existe para preservar:

> Tratar una **re-expresión** como supersesión borra la serie histórica en
> moneda de origen. Tratar un **restatement** como re-expresión deja dos
> verdades vigentes.

---

## 2 · Tabla de atributos y nivel al que pertenecen

| Atributo | Nivel | Fundamento |
|---|---|---|
| `entity_id` | **identidad económica** | F-061: la pertenencia se verifica por acá |
| `qname` | **identidad económica** | decisión de dominio DD2 · ver §9 |
| perímetro / `dimensions` | **identidad económica** | C11 |
| `period_kind` | **identidad económica** | C1 · I6 |
| `start_date` | **identidad económica** | C1 — contraejemplo real |
| `end_date` / `instant_date` | **identidad económica** | trivial |
| `unit_measure` | **identidad económica** | C2 — 580 grupos |
| `measurement_date` | **identidad económica** (vía unidad) | DD1 · analogía con C2 |
| `accession` | **ocurrencia** | C4 · C5 |
| `context_id` | **ocurrencia** (referencia al contexto) | C7 |
| `filing_date` / publicado | **ocurrencia** | necesario para ordenar |
| `decimals` | **atributo del valor** | C3 — 28.489 desempates |
| `currency` | **proyección derivada** de `unit_measure` | C8 — 0 discrepancias |
| escala documental | **provenance** | W-2 §2.2 |
| `value_numeric` | **contenido** | — |
| `effective_from` / `effective_to` / `supersedes` | **vigencia** | §5 |

Lo que la tabla decide y hoy no está decidido: `decimals` **no** identifica,
`currency` **no** identifica (es redundante), y `start_date` + `period_kind`
**sí** identifican aunque hoy no entren en ninguna clave.

---

## 3 · `econ_key` — identidad del hecho económico

```
econ_key = sha256(
      entity_id
    | qname
    | perimetro            -- dimensiones en SEC, tipo_balance en CNV
    | period_kind          -- INSTANT | DURATION
    | start_date           -- vacío si INSTANT
    | end_date             -- o instant_date
    | unit_measure
    | measurement_date     -- moneda de cierre bajo IAS 29
)
```

No lleva documento. No lleva `decimals`. No lleva `currency` (se deriva de
`unit_measure`). No lleva la escala del documento.

---

## 4 · `fact_key` — identidad de la ocurrencia

Semánticamente:

```
ocurrencia = (hecho económico, documento)
fact_key   = sha256(econ_key | accession)
```

**La implementación actual ya satisface esta definición, y no hace falta
cambiarla:**

```
fact_key = sha256(entity_key | accession | qname | context_id | unit_measure)
```

es equivalente en poder discriminante **si y sólo si** se cumple:

> **INV-CTX.** Dentro de un documento, `context_id` determina inyectivamente
> `(period_kind, start_date, end_date, perímetro/dimensiones, measurement_date)`.

| | INV-CTX | Evidencia |
|---|---|---|
| SEC | **se cumple** | 0 violaciones en 45.791 contextos (C7) |
| CNV | **NO se cumple** | `context_id = PERIMETRO@cierre`: sin duración, sin medición |

**Conclusión de diseño: no se toca la fórmula de `fact_key` — se repara el
`context_id` de CNV.** Esto evita re-clavear 133.902 hechos SEC. El
`context_id` de CNV debe pasar a ser una referencia completa, del tipo:

```
CONSOLIDADO|DURATION|2025-01-01|2025-12-31|2025-12-31
```

Que CNV cumpla hoy INV-CTX es un accidente, no una garantía: hay exactamente
**1 contexto por documento** (56 y 56), y se cumple porque cada documento
aporta un solo período, no porque el `context_id` lo codifique.

---

## 5 · Modelo original / republicación / re-expresión / restatement

```
                        ┌──────── econ_key A ────────┐
   DOC-2023 (pub 2024)  │  Revenue 2023  ARS  m2023  │  100   effective 2024→2025
   DOC-2024 (pub 2025)  │  Revenue 2023  ARS  m2023  │  100   effective 2025→2026   supersedes ↑
   DOC-2025 (pub 2026)  │  Revenue 2023  ARS  m2023  │  110   effective 2026→NULL   supersedes ↑
                        └────────────────────────────┘

                        ┌──────── econ_key B ────────┐
   DOC-2025 (pub 2026)  │  Revenue 2023  ARS  m2025  │  315   effective 2026→NULL
                        └────────────────────────────┘
```

| Situación | Misma `econ_key`? | `supersedes` | ¿Conviven vigentes? |
|---|---|---|---|
| Original | — | NULL | — |
| Republicación / comparativo | **sí** | → anterior | no: una sola efectiva |
| **Restatement** | **sí** | → anterior | no: la posterior gana |
| **Re-expresión IAS 29** | **no** (`measurement_date` distinta) | NULL | **sí**, es otra medición |
| Trimestre vs ejercicio | **no** (`start_date` distinta) | NULL | sí, son dos hechos |
| Stock vs flujo mismo cierre | **no** (`period_kind` distinto) | NULL | sí |

**Cómo se identifica la ocurrencia efectiva.** La de mayor fecha de publicación
dentro de su `econ_key`. Es una decisión de dominio (DD3) y **cambia el
comportamiento actual** — ver §6/C6 y §9/O2.

---

## 6 · Invariantes

Los seis están implementados como tests, no como prosa. `tests/test_w11_invariantes_identidad.py`, 11/11.

| | Invariante | Test |
|---|---|---|
| **I1** | un `econ_key` puede tener varias ocurrencias históricas | `test_i1` |
| **I2** | a lo sumo **una** efectiva por `econ_key` (`effective_to IS NULL`) | `test_i2` |
| **I3** | `supersedes` apunta a una ocurrencia del **mismo** `econ_key` | `test_i3` |
| **I4** | una re-expresión no supersede otra medición | `test_i4` |
| **I5** | dos períodos distintos no comparten `econ_key` | `test_i5` |
| **I6** | instantáneo y duración no comparten `econ_key` | `test_i6` |

```sql
-- I2, la condición central, como consulta verificable
SELECT econ_key, count(*)
  FROM derived.fact
 WHERE effective_to IS NULL
 GROUP BY 1 HAVING count(*) > 1;      -- debe dar 0 filas
```

**I4 no se cumple por convención: lo hace cumplir la clave.** Dos tests de
mutación lo demuestran:

| Mutación | Consecuencia |
|---|---|
| quitar `measurement_date` de `econ_key` | la re-expresión (315) cae en la misma clave que el restatement (110) → **I2 se rompe** |
| quitar `start_date` de `econ_key` | Q4 (318.663) y FY (1.217.305) pasan a ser el mismo hecho |

Si alguna de las dos mutaciones **no** rompiera nada, el atributo sería
decorativo y estos invariantes no probarían lo que dicen.

---

## 7 · Contraejemplos encontrados en el corpus

Todos reales. Ninguno construido para el argumento.

**C1 · `start_date` es identidad — 43 grupos.**
`CommonStockDividendsPerShareDeclared`, mismo emisor, mismo cierre 2026-06-30:

```
2025-07-01 → 2026-06-30  (364 d)  =  3,64
2026-04-01 → 2026-06-30  ( 90 d)  =  0,91
```

En SEC tienen `context_id` distintos y la `fact_key` los separa. Con el
`context_id` de CNV serían el mismo hecho.

**C2 · `unit_measure` es identidad — 580 grupos.**
`ExtinguishmentOfDebtAmount`, mismo emisor, **mismo documento, mismo contexto**:

```
iso4217:EUR   2.679.000.000
iso4217:USD   3.815.000.000
```

Es el precedente decisivo: **el corpus ya trata "mismo evento, otra unidad de
expresión" como dos hechos que conviven**, no como uno que supersede al otro.
Es exactamente la estructura de la re-expresión IAS 29.

**C3 · `decimals` NO es identidad — 28.489 hechos.**
`desempate = 'POR_PRECISION'` con `n_fuentes = 2,00`: dos hechos parseados que
difieren sólo en precisión producen **un** hecho derivado. El modelo ya decidió
que la precisión no identifica.

**C4 · el `accession` separa ocurrencias — 193 grupos.**
Quitándolo de la clave: SEC pasa de 133.902 claves a 133.709 (**193
colisiones**); CNV pasa de 2.697 a 2.697 (**0**). En CNV el `accession` hoy no
aporta nada — porque el comparativo nunca entra.

**C5 · restatement real.** `ProceedsFromIssuanceOfCommonStock`, mismo emisor,
mismo contexto, misma unidad, mismos `decimals`:

| período real | 10-K de 2009 | 10-K de 2010 |
|---|--:|--:|
| 2009-12-31 | **662.000.000** | **664.000.000** |
| 2008-12-31 | **586.000.000** | **595.000.000** |

Y `PaymentsToAcquireInvestments` 2009-12-31: 2.152.000.000 → 22.000.000.
La supersesión no es hipotética: está en los datos.

**C6 · hoy se elige siempre el original, por accidente.**
La guarda de `ratio_inputs.py:82-83` sólo admite el hecho cuya fecha real
iguala su `report_period`. Medido directamente:

```
hechos que pasan la guarda desde un filing ajeno al período:  0
```

Y de forma concordante: ningún filing declara más de un `report_period` (0
casos), y los 39 pares (emisor, período) reciben hechos de exactamente **1**
filing. De donde:

> Un restatement llega siempre en un filing posterior, cuyo `report_period` es
> otro. **Nunca puede pasar la guarda.** El motor devuelve siempre la
> publicación original.

Es determinista —lo cual es bueno— pero la regla no fue elegida: es un efecto
lateral del filtro de fechas.

**C7 · `context_id` determina el contexto en SEC — 0 de 45.791.**
Ningún par `(accession, context_id)` abarca más de un período ni más de una
combinación dimensional. Es la propiedad de la que depende la `fact_key` actual.

**C8 · `currency` es derivado — 0 discrepancias.**
En los 133.902 hechos SEC, `currency` siempre coincide con la moneda extraída
de `unit_measure`; los 14.846 no monetarios tienen `currency = NULL`.

**C9 · `qname` es el tag reportado, no el concepto económico.**
KO usa **18 qnames distintos** en la familia EPS. Tres tags para el mismo EPS
básico, en épocas distintas: `EarningsPerShareBasic` (2009-2026),
`BasicEarningsLossPerShare` (2023-2025),
`IncomeLossFromContinuingOperationsPerBasicShare` (2017-2018).

**C10 · las dimensiones son identidad.**
96.855 de 133.902 hechos SEC (72,3%) son dimensionales, y la combinación
dimensional vive dentro del `context_id`.

**C11 · CNV no tiene fecha de publicación.**

| | hechos | con `filing_date` |
|---|--:|--:|
| SEC | 133.902 | **133.902** (2010-02-26 … 2026-07-29) |
| CNV | 2.697 | **0** |

El mecanismo existe: `fetch_raw.cnv_presentation` tiene `fecha_publicacion`
poblada al **100%** (82.493 filas) y además `periodicidad_norm`, `fecha_cierre`
y `norma_contable`. Pero cubre **3 de los 72 CUITs**, y METR no está entre
ellos: 0 filas. **La fecha de publicación no falta en el diseño, falta en la
cobertura.**

---

## 8 · Decisiones tomadas

| # | Decisión | Respaldo |
|---|---|---|
| D1 | `period_kind` y `start_date` pertenecen a la identidad económica | C1 |
| D2 | `unit_measure` pertenece a la identidad, no a una capa de medición | C2 |
| D3 | `decimals` **no** pertenece a la identidad | C3 |
| D4 | `currency` **no** pertenece a la identidad: se deriva de `unit_measure` | C8 |
| D5 | el `accession` **permanece** en la clave de ocurrencia | C4, C5 |
| D6 | no se cambia la fórmula de `fact_key`; se repara el `context_id` de CNV | C7 |
| D7 | perímetro y dimensiones pertenecen a la identidad | C10 |
| D8 | la re-expresión IAS 29 **no** es supersesión | C2 (precedente estructural) |
| D9 | el restatement **sí** supersede, dentro de la misma medición | C5 |

**Sobre D5, en detalle.** Las dos alternativas fallan de maneras opuestas y
ninguna clave única resuelve ambas:

| Clave | Modo de falla |
|---|---|
| **sin** `accession` | dos ocurrencias legítimas colapsan; la segunda pisa a la primera. **Pérdida.** |
| **sólo** `accession` (hoy) | dos ocurrencias del mismo hecho conviven sin orden. **Ambigüedad.** |

Por eso el contrato tiene **dos claves y una relación de vigencia**, no una
clave mejor.

---

## 9 · Decisiones de dominio y decisiones abiertas

### Decisiones de dominio — marcadas como tales

**DD1 · `measurement_date` pertenece a la identidad, por la vía de la unidad.**
No hay evidencia directa en el corpus: SEC no tiene IAS 29 y CNV no registra la
fecha de medición. Se decide por analogía con C2 —el corpus ya hace convivir el
mismo evento en EUR y USD— y por la norma: bajo IAS 29 toda cifra se expresa en
el poder adquisitivo del cierre, luego dos re-expresiones son dos mediciones.

**DD2 · `econ_key` se construye sobre `qname`, no sobre un concepto canónico.**
Mapear tags a conceptos canónicos es una derivación con cadena de fallback y
prioridad; congelarla dentro de una clave primaria la volvería inmutable. Esa
resolución ya vive en el motor de ratios y ahí debe quedarse.
**Límite que esto impone, declarado:** un restatement que además cambie el tag
—posible, por C9— **no es detectable por la clave**. Requiere la capa de
conceptos.

**DD3 · La ocurrencia efectiva es la del documento publicado más
recientemente.** Cambia el comportamiento actual, que devuelve siempre el
original (C6).

### Decisiones abiertas

**O1 · CNV no puede computar `supersedes` hoy.** Sin fecha de publicación no
hay orden entre ocurrencias. Requiere extender la cobertura de
`fetch_raw.cnv_presentation` de 3 a 72 CUITs — un fetch, prohibido en este
ciclo.

**O2 · ¿El producto muestra el original o la cifra corregida?** DD3 propone la
corregida, que es lo que hacen los proveedores de referencia. Hoy se muestra el
original (C6). Es una decisión de producto con efecto comercial, no una
ambigüedad conceptual: el contrato define la supersesión con precisión; qué
ocurrencia se expone es política.

**O3 · Restatements con cambio de tag** — el límite declarado en DD2.

**O4 · `desempate = 'POR_FACT_ID'`: 8.610 hechos**, con hasta 12 fuentes,
resueltos por un criterio arbitrario. Es resolución *intra*-documento y queda
fuera de W-1.1, pero toca la identidad y merece su propio análisis.

**O5 · `measurement_date` para SEC.** Si se adopta como columna, hay que
definir su valor en los 133.902 hechos SEC (NULL, o el cierre del período).
Afecta si incorporarla a `econ_key` es neutral para SEC.

---

## 10 · Dictamen

Las cuatro nociones que el criterio de PASS exige quedan definidas sin
ambigüedad, y cada una con su discriminante explícito:

| Noción | Discriminante | Estado |
|---|---|---|
| **hecho económico** | `econ_key` (§3) | definido · 8 atributos, cada uno justificado |
| **ocurrencia** | `econ_key` + `accession` (§4) | definido · fórmula actual conservada bajo INV-CTX |
| **medición** | `unit_measure` + `measurement_date` | definido · C2 da el precedente estructural |
| **supersesión** | `supersedes` + `effective_from/to` dentro de una `econ_key` | definido · I2/I3/I4, con restatement real en C5 |

Nueve decisiones respaldadas por contraejemplos reales del corpus; tres
decisiones de dominio marcadas explícitamente como tales, con su fundamento y,
en DD2, con el límite que imponen. Los seis invariantes están escritos como
tests que pasan, y dos mutaciones demuestran que `measurement_date` y
`start_date` cargan el peso en vez de decorar la clave.

Las cinco cuestiones abiertas son de **implementación, cobertura de datos o
política de producto** — ninguna es una ambigüedad conceptual sobre hecho,
ocurrencia, medición o supersesión.

```
W1_1 = PASS
```

**Consecuencia inmediata para la integración.** El contrato deja el trabajo
acotado y en un orden que no depende de decisiones pendientes:

1. **Reparar el `context_id` de CNV** para que satisfaga INV-CTX. No cambia
   `fact_key` ni re-clavea ningún hecho SEC.
2. **Llevar `period_kind`, `start_date` y `measurement_date` al adaptador.**
   Sin ellos `econ_key` no se puede construir, y hoy 1.002 de 2.697 hechos CNV
   son flujos grabados como instantes.
3. **Extender la cobertura de `fetch_raw.cnv_presentation`** a los 72 CUITs
   (O1). Es la única pieza que necesita red.
4. **Recién entonces** `econ_key`, `effective_from/to`, `supersedes` y el
   invariante I2.

Los pasos 1 y 2 son el adaptador y no dependen de O2. El paso 3 es un fetch. El
paso 4 es una migración cuyo diseño ya está cerrado por este documento.
