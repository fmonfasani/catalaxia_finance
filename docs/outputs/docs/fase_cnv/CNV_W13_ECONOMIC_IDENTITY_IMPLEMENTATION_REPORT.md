# CNV W-1.3 — IDENTIDAD ECONÓMICA, OCURRENCIA Y SUPERSESIÓN

**Fecha:** 2026-09-02 · **Worktree:** `catalaxia-cnvmig` · **DB:** `cnvmig`
**Baseline empírico:** `CNV_W13_ECONOMIC_IDENTITY_BASELINE.md`
**Sin commits · sin integración · `catalaxia` intacta**

---

## 1 · Scope

Implementar `econ_key` sobre el fixture, decidir con evidencia si `supersedes` y
`effective_from/to` corresponden, y no inventar nada donde el corpus no alcanza.

**No se hizo:** integración, cobertura de las 72 empresas, fórmulas de ratios,
cambios al ratio engine, Market, Identity, fetch, ni supersesión automática.

---

## 2 · Baseline

Capturado **antes** de tocar nada, y comparado después:

| | valor |
|---|---|
| hechos SEC | 133.902 |
| digest `fact_key` SEC | `b9d03247d74fd0e1…` |
| digest `context_id` SEC | `ae02a04825c662d7…` |
| digest `source_hash` SEC | `a34b919f7d9936f5…` |
| hechos CNV | 2.697 |
| digest `fact_key` CNV | `8afbf67e9e49cebc…` |
| digest `context_id` CNV | `f0d59eb9d26dd676…` |
| digest `source_hash` CNV | `73605a4078589499…` |

---

## 3 · La hipótesis de identidad económica

> Dos hechos con igual `econ_key` representan la misma realidad económica
> aunque tengan distinta ocurrencia documental.

**Intenté romperla y no se rompió** — pero la conclusión honesta es más
matizada: en CNV la hipótesis **no está puesta a prueba por los datos**.

Quitando un componente por vez sobre los 2.697 hechos:

| `econ_key` | claves | colisiones |
|---|--:|--:|
| completa | 2.697 | 0 |
| sin `measurement_date` | 2.697 | **0** |
| sin `start_date` | 2.697 | **0** |
| sin `unit_measure` | 2.697 | **0** |
| sin `perímetro` | 1.398 | 1.299 |

Cuatro de los ocho componentes no discriminan nada en este corpus. Sus
invariantes se sostienen en fixtures sintéticos y en el corpus SEC —580 grupos
donde la unidad separa dos hechos, 43 donde lo hace `start_date`— pero **no en
datos CNV reales**.

---

## 4 · Análisis empírico de colisiones (§4)

```
total facts CNV          2.697
econ_key únicas          2.697
multiplicidad > 1            0
multiplicidad máxima         1
```

**No hay ninguna colisión oculta: no hay ninguna.** Los seis tests T1–T6 del
enunciado están implementados como I1–I7 y M1–M6, y pasan.

### Y por qué ese cero no significa lo que parece

`cnv_estados_v2` tiene `PRIMARY KEY (cuit, concepto, period_end,
fecha_reexpresion, tipo_balance)` con **`INSERT OR IGNORE`**, y
`fecha_reexpresion = period_end` en el 100 % de las 106.421 filas.

> Si la misma identidad económica aparece en dos documentos, **el segundo se
> descarta en silencio al ingestar**.

Medido reconstruyendo desde el RAW: **292 filas en 7 documentos** (0,3 % del
corpus) nunca llegaron a la tabla. Son exactamente la evidencia que W-1.3
necesitaba.

**Esto contradice la interpretación de ciclos anteriores**, que leyeron "0
colisiones" como *no hay republicación en CNV*. La medición era correcta; la
interpretación era demasiado fuerte.

---

## 5 · `qname` (§5)

Búsqueda empírica de alias: pares que coincidan en más del 90 % de las
observaciones, mínimo 50 observaciones.

| par | coincidencia | ¿alias? |
|---|--:|---|
| `EPS_basico` / `EPS_diluido` | 96,0 % | **no** — coinciden sin instrumentos dilutivos |
| `EBIT` / `OperatingIncome` | 49,2 % (56/56 en METR) | **no** |
| `NetIncome` / `ResultadoIntegral` | 39,1 % | no |

```
QNAME_IDENTITY_FINDINGS = PASS
```

Los 51 conceptos CNV son un conjunto cerrado con código propio. **No se
introdujo taxonomía canónica porque el corpus no la justifica.** El problema
multi-tag existe en SEC (18 `qname` de KO en la familia EPS) y sigue abierto ahí.

---

## 6 · Republicación (§6)

Las 7 tripletas `(cuit, período, perímetro)` con dos documentos, reconstruidas
desde el RAW:

| emisor | período | comunes | idénticos | distintos |
|---|---|--:|--:|--:|
| LONG ×3 | 2018-12 / 2019-03 / 2020-12 | 108 | 0 | 108 |
| INTR | 2021-12 | 46 | 4 | 42 |
| **FIPL** | 2025-06 | 48 | **45** | **3** |
| _ADR_0580 | 2019-12 | 46 | 12 | 34 |
| BYMA | 2021-12 | 45 | 5 | 40 |
| **total** | | **292** | **66** | **226** |

---

## 7 · Restatement (§7)

**Los 226 "distintos" no son restatements.** Las magnitudes lo desmienten:
`PPE` +14.305,9 %, `Inventory` −99,2 %, `PPE` −100,0 %.

**Demostración sobre BYMA 2021-12-31 CONSOLIDADO.** La serie de `PPE`
consolidado del emisor:

```
2021-09-30   1.481.185.590
2021-12-31      11.060.815   <- el documento que SÍ entró
2022-03-31   1.835.280.221
```

El documento descartado trae **1.593.406.319**, el valor que la serie exige. Y
la serie INDIVIDUAL de BYMA se mueve en 11-12 millones: **11.060.815 es la
cifra individual**. Ambos documentos declaran `TipoBalance = Consolidado`, una
sola vez cada uno, misma `FechaCierre`, misma `UnidadMedida`, y el texto se
parsea limpio en los dos.

**Es un perímetro mal declarado en origen**, y el `INSERT OR IGNORE` conservó el
documento equivocado porque llegó primero.

| clase | casos | fundamento |
|---|---|---|
| **D · error de origen** | LONG ×3, INTR, BYMA | diferencias del 50 % al 14.000 %; en BYMA está probado |
| **A/B · indistinguibles** | FIPL, _ADR_0580 | FIPL 45/48 idénticos; _ADR_0580 diferencias de 0,1 %–5,9 % |
| **C · conflicto verdadero** | 0 | ninguno demostrable |

Ninguno se clasificó automáticamente como restatement.

---

## 8 · IAS 29 (§8)

| señal | resultado |
|---|---|
| `fecha_reexpresion` ≠ `period_end` | 0 de 106.421 |
| `valor_comparativo` poblado | 0 filas |
| períodos por documento | 1 en los 2.453 |
| `measurement_date` ≠ fin de período | 0 de 2.697 |

**No existe un solo caso de re-expresión observable.** Y hay una consecuencia
estructural: como `measurement_date` sale de la `FechaCierre` del documento y
cada documento aporta un solo período, **`measurement_date` está funcionalmente
determinada por `end_date` (2.697/2.697)**. Mientras el comparativo no se
ingeste, dos publicaciones del mismo período tendrían medición distinta y por
tanto `econ_key` distinta: **la republicación es estructuralmente invisible para
`econ_key` en CNV hoy**.

```
IAS29 = OPEN: requires publication/re-expression evidence
```

---

## 9 · Fecha de publicación (§9) — corrección de un cierre anterior

`CNV_SEMANTIC_IMPLEMENTATION_REPORT` §14 R-3 y `W1_1_FACT_IDENTITY_CONTRACT`
§O1 concluyeron que ordenar las ocurrencias CNV requería un fetch. **Era
demasiado pesimista.**

| fuente | contenido | cobertura |
|---|---|--:|
| `derived.fact.filing_date` | — | 0 de 2.697 |
| `fetch_raw.cnv_presentation.fecha_publicacion` | fecha real | 3 de 72 CUITs |
| **título del RAW: `Presentación #N`** | **ordinal** | **2.364 de 2.364** |

Validación del ordinal contra la fecha real, sobre los 3 CUITs que tienen ambas:

| | |
|---|--:|
| pares `(presentation_id, fecha)` | 9.167 |
| rango | #1103 (2000-06-20) … #3564242 (2026-08-31) |
| **inversiones** | **112 (1,22 %)**, todas de 1–2 días |

**El orden de publicación es reconstruible localmente y sin red.** La *fecha*
solo existe para 3 de 72 CUITs.

---

## 10 · `econ_key` implementada (§10)

`migrations/engine/036_economic_identity.sql` — columna nullable + CHECK de
formato + índice parcial + vista `derived.v_ocurrencias_por_hecho`.

### Serialización canónica (normativa)

```
econ_key = sha256( entity_id | qname | perimetro | period_kind
                 | start_date | end_date | unit_measure | measurement_date )

separador   '|' (U+007C), exactamente uno entre campos
NULL        cadena vacía; NUNCA 'NULL' ni 'None'
fechas      ISO-8601 'YYYY-MM-DD' — se recorta hora y zona
end_date    para INSTANT lleva la fecha del instante
start_date  para INSTANT queda vacío
encoding    UTF-8
digest      sha256 hexadecimal minúscula
```

La regla que sostiene todo: **dos representaciones equivalentes producen el
mismo hash**. `None`, `''` y la ausencia colapsan; `2025-12-31T03:00:00.000Z` y
`2025-12-31` colapsan. Ambas verificadas en I1.

### Resultado

```
CNV: 2.697/2.697 con econ_key · 2.697 distintas · 0 mal formadas
SEC: 0 con econ_key  (calcularlas sería escribir sobre SEC: fuera de alcance)
hechos económicos con más de una ocurrencia: 0
```

---

## 11 · `effective_from` / `effective_to` — **NO IMPLEMENTADOS**

No se implementan por aparecer en W-1.1. Al intentar definirlos aparecen tres
cosas distintas que el nombre confunde:

| noción | qué significa | ¿se puede hoy? |
|---|---|---|
| **validez económica** | el lapso que el hecho describe | ya está: `start_date`/`end_date` |
| **validez de publicación** | desde cuándo esta declaración es la vigente | **no** — requiere saber cuál supersede a cuál |
| **selección de producto** | qué versión se expone al cliente | decisión de producto, no del modelo |

`effective_to` **no es** `superseded_at` ni `publication_date`. Sin resolver la
supersesión, la validez de publicación no tiene contenido: todas las
ocurrencias serían `effective_to IS NULL` y la columna no diría nada.

```
effective_from / effective_to = OPEN
```

---

## 12 · `supersedes` — **NO IMPLEMENTADO**, con el motivo preciso

No se crea la columna. Sí se implementa y prueba el **predicado** que la
gobernaría, para que las condiciones queden escritas y verificadas:

```python
puede_superseder(a, b) -> (bool, motivo)
  1. misma identidad económica   econ_key(a) == econ_key(b)
  2. ocurrencias distintas       fact_key(a) != fact_key(b)
  3. orden establecido           orden(b) > orden(a), demostrable
  4. evidencia de reemplazo      b declara o implica que corrige a a
```

**Por qué no se puede hoy — y el motivo cambió respecto de lo que dije antes.**
No es que falte el orden: el ordinal de presentación existe en el 100 % de los
documentos y está validado (§9). **Lo que falta es la condición 4.** Los 7
candidatos del corpus tienen orden y aun así no son interpretables: en BYMA está
probado que la diferencia es un perímetro mal declarado, no una corrección.

```
supersedes = OPEN — falta el discriminante semántico, no el orden
```

---

## 13 · Tests

`tests/test_w13_economic_identity.py` — **25 passed**.

| | invariante |
|---|---|
| I1 | igual identidad → igual `econ_key`, incluidas equivalencias de representación |
| I2–I6 | `start_date`, `end_date`, unidad, perímetro, medición cambian la clave |
| I7 | misma identidad + distinto documento → misma `econ_key`, distinta `fact_key` |
| I8 | `supersedes` solo dentro del mismo `econ_key` |
| I9 | nada se supersede a sí mismo |
| I10 | sin orden no hay supersesión · I10b: con orden y sin evidencia, tampoco · I10c: con las cuatro, sí |
| I11 | Q4 y FY nunca comparten `econ_key` |
| I12 | INSTANT y DURATION no comparten `econ_key` |
| I13 | SEC sin cambio y sin `econ_key` |
| I14 | CNV conserva cardinalidad y `fact_key`; clave poblada, bien formada y reconstruible |

Suite completa: **300 passed · 3 failed · 1 skipped**. Las 3 son
`test_f038_traza_corrida`, preexistentes desde `DAY3_IMPLEMENTATION_REPORT`.

---

## 14 · Mutation tests

| | mutación | esperado | resultado |
|---|---|---|---|
| M1 | quitar `start_date` | Q4/FY colisionan | ✔ |
| M2 | quitar `unit_measure` | ARS/USD colisionan | ✔ |
| M3 | quitar `perímetro` | INDIVIDUAL/CONSOLIDADO colisionan | ✔ |
| M4 | quitar `measurement_date` | dos mediciones colisionan | ✔ |
| M5 | quitar la condición de `econ_key` del predicado | supersede un hecho ajeno | ✔ |
| M6 | usar `fact_key` como identidad económica | un hecho se parte en dos | ✔ |

Cada mutación verifica primero su precondición: si el caso no estuviera separado
*antes* de mutar, la mutación no probaría nada.

---

## 15 · Idempotencia

| corrida | `parsed.facts` | `derived.fact` |
|---|---|---|
| 1ª | 2.697 insertados | 2.697 insertados |
| 2ª | 0 · 2.697 reusados | 0 · **2.697 sin cambio** |
| 3ª, con un valor mutado | 0 · 2.697 reusados | 0 · 2.696 sin cambio · **1 CONFLICTO** |

El conflicto se reporta y **no sobrescribe**. La segunda corrida no genera
identidades económicas duplicadas: 2.697 `econ_key`, todas distintas.

---

## 16 · Auditoría independiente

`scripts/engine/c4_auditoria_cnv.py` — **38 verificaciones OK · 0 fallas · 1 aviso**.

No importa `c4_cnv_adapter` ni `c4_cnv_semantica`. Para W-1.3 se le agregó la
sección H, donde **recalcula las 2.697 `econ_key` con su propia implementación
de la serialización**, escrita aparte a propósito:

```
la econ_key persistida coincide con la recalculada por el auditor
    2.697 recalculadas · 0 difieren
Q4 y ejercicio no comparten econ_key          0 grupos mezclados
perímetros distintos no comparten econ_key    0 grupos mezclados
unidades distintas no comparten econ_key      0 grupos mezclados
INSTANT y DURATION no comparten econ_key      0 grupos mezclados
SEC sin econ_key                              0 hechos
orden de publicación disponible en el RAW     56/56 documentos
```

Sigue midiendo el `period_kind` contra el comportamiento del dato en las 72
empresas —no contra una tabla de conceptos— y sigue dando 37 conceptos
monetarios medidos, 0 discrepan.

---

## 17 · SEC sin cambio

| | resultado |
|---|---|
| hechos SEC | **IGUAL** — 133.902 |
| digest `fact_key` | **IGUAL** — `b9d03247d74fd0e1…` |
| digest `context_id` | **IGUAL** — `ae02a04825c662d7…` |
| digest `source_hash` | **IGUAL** — `a34b919f7d9936f5…` |
| ratios | **SIN_CAMBIO 36** |
| `econ_key` en SEC | 0 (por alcance) |

```
SEC_UNCHANGED = PASS
```

---

## 18 · Cardinalidad CNV

```
2.747 origen  =  2.697 admitidas  +  50 excluidas (sin perímetro, 1 documento)
```

Sin cambios respecto de W-1.2. Ninguna exclusión nueva. Y **la `fact_key` CNV
tampoco cambió**: digest `8afbf67e9e49cebc…` idéntico antes y después de
agregar `econ_key`. Agregar identidad económica no reescribió la identidad
documental.

---

## 19 · `catalaxia` intacta

```
migraciones                                     34
derived.fact                               133.902
parsed.facts                               225.475
hechos CNV                                       0
columnas entity_id / measurement_date / econ_key  0
```

---

## 20 · Riesgos y cuestiones abiertas

**R-1 · La clave primaria del origen destruye evidencia.** 292 filas en 7
documentos (0,3 %). Es exactamente la evidencia que W-1.3 necesitaba. Corregirlo
es un cambio en `job5_v2_extract_eeff.py`, fuera de alcance.

**R-2 · `tipo_balance` tiene errores en origen.** Probado en BYMA 2021-12-31:
dos documentos declaran `Consolidado` y uno trae cifras individuales. El
perímetro sigue siendo la dimensión correcta, pero **la etiqueta no siempre lo
es**. METR no está afectado.

**R-3 · Hay un valor incorrecto en `cnv_estados_norm`** para BYMA 2021-12-31
CONSOLIDADO (`PPE = 11.060.815` donde la serie exige ~1.593 M). No es dato
migrado, pero cualquier consumidor de esa tabla lo leería.

**R-4 · Cuatro de los ocho componentes de `econ_key` están sin ejercitar** en
CNV: `start_date`, `unit_measure`, `measurement_date` y —parcialmente— el propio
`period_kind` aportan 0 poder discriminante en este corpus.

**R-5 · `measurement_date` está funcionalmente determinada por `end_date`.**
Mientras eso siga así, `econ_key` no puede reconocer dos publicaciones del mismo
período como el mismo hecho.

**R-6 · `supersedes` y `effective_*` quedan OPEN**, por falta del discriminante
semántico (no del orden).

**R-7 · Un solo emisor migrado.** El análisis de colisiones nivel 2 sí cubrió
las 72 empresas y los 2.453 documentos.

---

## 21 · Dictamen

| | resultado |
|---|---|
| `econ_key` | **PASS** — 2.697/2.697, 0 colisiones, serialización normativa, reconstruible por un tercero |
| occurrence | **PASS** — `fact_key` intacta, I7 y M6 lo prueban en las dos direcciones |
| Q4/FY | **PASS** — I11 + M1 |
| units | **PASS** — I4 + M2 |
| perimeter | **PASS** — I5 + M3 |
| measurement_date | **PASS** con reserva — I6 + M4, pero funcionalmente determinada por `end_date` (R-5) |
| republication | **WARN** — 7 candidatos, 2 compatibles, ninguno demostrable |
| restatement | **WARN** — 226 diferencias, ninguna es un restatement; en BYMA está probado que es error de perímetro |
| IAS29 | **WARN** — 0 casos observables en todo el corpus |
| supersedes | **OPEN** — falta el discriminante semántico, no el orden |
| effective dates | **OPEN** — tres nociones distintas bajo un nombre; sin supersesión no tienen contenido |
| SEC | **PASS** — 4 digests idénticos, 36 ratios sin cambio |
| CNV cardinality | **PASS** — 2.747 = 2.697 + 50, `fact_key` idéntica |
| idempotence | **PASS** — 2ª corrida 0 insertados; conflicto detectado sin sobrescribir |
| independent audit | **PASS** — 38 OK, 0 fallas; recalcula `econ_key` por su cuenta |
| mutation testing | **PASS** — M1–M6, cada una con su precondición |
| catalaxia untouched | **PASS** |

```
W1.3 ECONOMIC IDENTITY = PASS_WITH_WARNINGS
```

**PASS** en todo lo que el ciclo definió como condición de aceptación: la
identidad económica está implementada, es determinista, reconstruible por un
tercero, y separa lo que tiene que separar; la identidad documental no cambió;
SEC y `catalaxia` están intactas.

**WITH_WARNINGS** por lo que el corpus no permite cerrar, y que el propio
enunciado admite como causal de esta calificación: republicación y restatement
sin evidencia suficiente, IAS 29 sin un solo caso observable, y `supersedes` /
`effective_*` abiertos.

**Y una advertencia que no estaba prevista y conviene leer entera:** el corpus
no puede responder la pregunta de republicación **porque la clave primaria del
origen borra la evidencia antes de que llegue**. Son 292 filas, el 0,3 %, y
están recuperables en disco. Mientras eso no se corrija, ningún ciclo posterior
va a poder cerrar `supersedes` por más modelo que se le agregue.
