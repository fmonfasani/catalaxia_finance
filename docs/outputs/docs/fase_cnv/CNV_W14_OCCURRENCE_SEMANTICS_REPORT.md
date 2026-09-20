# CNV W-1.4 — SEMÁNTICA DE OCURRENCIAS

**Fecha:** 2026-09-02 · **Worktree:** `catalaxia-cnvmig` · fixture aislado
**Matriz:** `CNV_W14_CLASSIFICATION_MATRIX.md` · **Auditoría:** `CNV_W14_AUDIT.md`
**Sin commits · sin integración · sin schema nuevo**

---

## 1 · Resultado

| clasificación | pares | identidades |
|---|--:|--:|
| `CONFIRMED_REPUBLICATION` | 0 | 0 |
| `PROBABLE_REPUBLICATION` | 0 | 0 |
| `CONFIRMED_RESTATEMENT` | 0 | 0 |
| **`PROBABLE_RESTATEMENT`** | **1** | **48** |
| **`PERIMETER_CONFLICT`** | **2** | **80** |
| `IAS29_REEXPRESSION` | 0 | 0 |
| **`UNKNOWN`** | **4** | **164** |
| **total** | **7** | **292** |

**No se generó ninguna relación `supersedes`.** Ninguna de las 292 identidades
cumple las cuatro condiciones.

---

## 2 · Lo primero que cambió el análisis: los 292 son 7

Los 292 grupos no son 292 situaciones. Son **7 pares de documentos** (14
documentos), cada uno aportando entre 35 y 48 identidades económicas. Analizar
292 casos habría sido analizar 7 siete veces cada uno.

---

## 3 · La evidencia que resultó decisiva: la distancia temporal

El ordinal `Presentación #N` está en **2.364 de 2.364** documentos. Convertido a
tiempo con la tasa de presentaciones **de su propia época** —la CNV recibe ~495
presentaciones diarias en 2025 y muchas menos en 2018—:

| par | distancia | tiempo |
|---|--:|---|
| _ADR_0580 2019-12-31 | 1 ordinal | **~0,1 h** |
| INTR 2021-12-31 | 5 | ~0,3 h |
| LONG 2019-03-31 | 7 | ~0,5 h |
| BYMA 2021-12-31 | 19 | ~1,1 h |
| LONG 2020-12-31 | 35 | ~2,3 h |
| LONG 2018-12-31 | 49 | ~3,2 h |
| **FIPL 2025-06-30** | **12.213** | **~27 días** |

**Seis de siete se presentaron el mismo día, con horas de diferencia.** Eso
cambia la lectura de todo: no son republicaciones posteriores ni correcciones,
son dos documentos de **una misma sesión de presentación**. Sin posterioridad
no hay reemplazo posible, y por eso cuatro caen en `UNKNOWN`.

FIPL es el único par con separación temporal real.

---

## 4 · Republicación (§3)

Hipótesis: misma `econ_key`, mismo valor, distinta ocurrencia.

**Ningún par la satisface.** Los 66 pares "con mismo valor" que W-1.3A contó no
son 66 casos: son las identidades coincidentes **dentro** de pares que, en el
resto de sus conceptos, difieren. Ningún par tiene sus conceptos comunes todos
iguales.

El más cercano es FIPL: **45 de 48 iguales**. Pero cambian 3, así que no es una
republicación.

```
CONFIRMED_REPUBLICATION = 0
PROBABLE_REPUBLICATION  = 0
```

---

## 5 · Restatement (§4)

Hipótesis: misma `econ_key`, distinto valor. **No alcanza**, y el corpus lo
muestra: 226 identidades tienen valores distintos y ninguna es un restatement
confirmado.

**FIPL 2025-06-30** es el único candidato: 27 días de separación, 45 de 48
conceptos idénticos, 3 que cambian (`ResultadoIntegral` +0,9 %, `EPS_basico` y
`EPS_diluido` de −6,47 a −15,75). Es compatible con una corrección puntual.

Pero **el documento no declara que corrija al anterior**. Sin esa evidencia
queda en `PROBABLE_RESTATEMENT` con confianza 0,60, no en confirmado.

```
CONFIRMED_RESTATEMENT = 0
PROBABLE_RESTATEMENT  = 1 par · 48 identidades
```

---

## 6 · Conflicto de perímetro (§5) — detector general

El detector **no tiene ninguna regla para BYMA ni para ningún emisor**. Compara
el contenido de cada documento contra las series del propio emisor en cada
perímetro, excluyendo los documentos en disputa, y mide el desvío en órdenes de
magnitud.

**Dos condiciones, no una:**

```
AJUSTE_MAXIMO     = 0,15   el mejor encaje tiene que ser bueno (factor < 1,4)
SEPARACION_MINIMA = 0,15   y tiene que separarse claramente del otro
```

La segunda condición se agregó tras encontrar que la primera versión inferían
perímetro en FIPL cuando **las dos series estaban a 2,5 órdenes de magnitud**.
Que una encaje "mejor" que otra no es una inferencia si las dos encajan pésimo.

### Salida: evidencia, no corrección

```
declared_perimeter · inferred_perimeter · confidence · reason
```

**El dato de origen queda intacto** — verificado por el test I7, que compara la
tabla antes y después de correr el detector.

### Casos detectados

| par | documento | declarado | inferido | confianza |
|---|---|---|---|--:|
| BYMA 2021-12-31 | `863efe00` | CONSOLIDADO | **INDIVIDUAL** | 0,32 |
| | `ee3e755d` | CONSOLIDADO | CONSOLIDADO | 0,36 |
| LONG 2019-03-31 | `e0caf38b` | INDIVIDUAL | **CONSOLIDADO** | 0,31 |

---

## 7 · IAS 29 (§7) — medido, no supuesto

Una re-expresión multiplica **todos** los conceptos por el mismo factor. La
prueba es directa: ¿el cociente B/A es constante?

| par | mediana B/A | dispersión |
|---|--:|--:|
| LONG 2018-12-31 | 52,110 | 66,1 % |
| LONG 2019-03-31 | 59,278 | 50,5 % |
| LONG 2020-12-31 | 0,009 | 80,4 % |
| INTR 2021-12-31 | 0,821 | 23,5 % |
| FIPL 2025-06-30 | 1,000 | 0,0 % |
| _ADR_0580 2019-12-31 | 1,001 | 0,2 % |
| BYMA 2021-12-31 | 1,931 | 48,2 % |

Los dos con dispersión baja tienen **factor ≈ 1**: los valores son los mismos,
no re-expresados. Los otros cinco tienen dispersiones del 23 % al 80 %,
incompatibles con un factor único de inflación.

```
IAS29_REEXPRESSION = 0 casos
```

Y ninguna re-expresión se convirtió en restatement, porque no hay ninguna.

---

## 8 · `supersedes` (§8) — no se generó ninguna

Las cuatro condiciones, conjuntivas:

```
1. A.econ_key = B.econ_key
2. A.fact_key != B.fact_key
3. B es posterior a A, demostrable
4. existe evidencia semántica de reemplazo
```

**Ningún par del corpus cumple la 4.** Y seis de siete tampoco cumplen la 3 de
forma significativa: presentados con horas de diferencia, la "posterioridad" es
el orden de subida de dos archivos en una misma sesión.

### Por qué las condiciones fáciles no alcanzan — con el contraejemplo del corpus

| criterio tentador | por qué falla |
|---|---|
| valor distinto ⇒ supersedes | convertiría las 226 identidades divergentes en 226 supersesiones sin una sola evidencia |
| ordinal mayor ⇒ supersedes | **en BYMA el ordinal mayor (`863efe00`, #2864462) es el que tiene la cifra individual**, y la serie consolidada lo desmiente |
| fecha posterior ⇒ supersedes | seis de siete pares tienen la misma fecha |

El caso BYMA es el argumento más fuerte: **el documento posterior es el
equivocado**.

```
supersedes = 0 relaciones creadas
```

---

## 9 · `effective_from` / `effective_to` (§10) — **NO IMPLEMENTADOS**

Al intentar definirlos aparecen tres nociones distintas bajo un nombre:

| noción | qué significa | ¿existe hoy? |
|---|---|---|
| **validez económica** | el lapso que el hecho describe | **sí** — es `start_date` / `end_date` |
| **validez de publicación** | desde cuándo esta declaración es la vigente | **no** — requiere resolver la supersesión, y hay 0 |
| **vigencia de producto** | qué versión se expone al cliente | decisión de producto, no del modelo |

`effective_to` **no es** `superseded_at` ni `publication_date`. Sin supersesión
resuelta, la validez de publicación no tiene contenido: las 292 identidades
tendrían las dos ocurrencias con `effective_to IS NULL` y la columna no diría
nada.

```
effective_from / effective_to = OPEN
```

---

## 10 · Modelo de relaciones (§11)

```
                 identidad económica (econ_key)
                            │
              ┌─────────────┴─────────────┐
              │                           │
        ocurrencia A                ocurrencia B
        (accn, concepto)            (accn, concepto)
              │                           │
              └─────────────┬─────────────┘
                            │
                   relación · CLASIFICADA
                            │
    ┌──────────┬────────────┼────────────┬──────────┐
    │          │            │            │          │
republicación  corrección  restatement  IAS 29   UNKNOWN
                            │
                      supersedes  ← solo con las 4 condiciones
```

**Dos propiedades deliberadas:**

1. **La relación es un atributo del par, no una jerarquía en la tabla.** No hay
   columna `supersedes` ni `es_vigente`: las dos ocurrencias son pares, y la
   interpretación vive aparte y es revisable.
2. **`UNKNOWN` es un nodo del modelo**, no la ausencia de uno. El 56 % del
   corpus está ahí.

Nada de esto es irreversible: si mañana aparece evidencia —una declaración
textual de corrección, la fecha de publicación de los 69 CUITs restantes— la
clasificación cambia sin tocar el dato.

---

## 11 · Valor corriente para el producto (§12) — especificado, no implementado

Si existen `A = 100` y `B = 110`, ¿qué lee el consumidor?

### Política propuesta

| campo | definición | disponible hoy |
|---|---|---|
| `original_value` | la ocurrencia de menor ordinal | **sí** |
| `historical_occurrence` | todas, con su documento y ordinal | **sí** — es lo que W-1.3A preservó |
| `current_value` | la ocurrencia vigente | **no** — requiere supersesión resuelta |
| `superseded_value` | la reemplazada | **no** — ídem |

### La regla que sí se puede aplicar hoy

> Mientras una identidad tenga más de una ocurrencia sin clasificar,
> **no se expone ningún valor**: se expone el conflicto.

Es más útil y más honesto que elegir uno. **En BYMA, cualquier regla
automática —el primero, el último, el de mayor ordinal— habría elegido mal**,
salvo la que mira la serie, que es justamente la que no es automática.

Las 292 identidades afectadas son el 0,28 % de las 102.976. Suprimirlas cuesta
poco; publicar la equivocada cuesta la confianza en las otras 102.684.

**No se modificó ninguna publicación.** Esto es una especificación.

---

## 12 · Tests

`tests/test_w14_occurrence_semantics.py` — **20 passed**.

| | invariante |
|---|---|
| I1 | una identidad económica admite varias ocurrencias — 292, todas con 2 |
| I2 | la republicación no cambia la `econ_key` |
| I3 | el restatement tampoco: el valor no participa de la identidad |
| I4 | `supersedes` solo entre el mismo `econ_key` |
| I5 | `supersedes` requiere evidencia temporal |
| I6 | un valor distinto no implica `supersedes` · I6b: ni las tres primeras condiciones juntas |
| I7 | el detector de perímetro no modifica el origen · I7b: no infiere cuando ninguna serie encaja |
| I8 | BYMA conserva las dos ocurrencias · I8b: el detector lo encuentra sin regla especial |
| I9 | FIPL se clasifica solo hasta donde la evidencia sostiene |
| I10 | `UNKNOWN` es una salida válida y efectivamente usada |

Suite completa: **336 passed · 3 failed · 1 skipped** (las 3 son F-038,
preexistentes).

---

## 13 · Mutaciones (§9)

| | mutación | resultado |
|---|---|---|
| M1 | quitar `same econ_key` | ✔ superseería un hecho ajeno |
| M2 | quitar la posterioridad | ✔ el anterior superseería al posterior |
| M3 | `value != value` suficiente | ✔ 226 supersesiones sin evidencia |
| M4 | `#N` mayor suficiente | ✔ **en BYMA elegiría el documento equivocado** |
| M5 | `publication_date` mayor suficiente | ✔ seis pares comparten fecha: orden arbitrario |
| M6 | quitar la comprobación de perímetro | ✔ BYMA dejaría de detectarse y caería en la rama de valores |

Cada mutación verifica primero su precondición.

---

## 14 · Cardinalidad (§15)

```
103.268 ocurrencias  ->  102.976 identidades económicas   (1,0028 a 1)
```

Sin cambios respecto de W-1.3A. **Ninguna ocurrencia se eliminó ni se
sobrescribió** para producir un valor limpio. La relación es N:1 y está
verificada por el auditor.

---

## 15 · W-1.3A, W-1.2, SEC y `catalaxia`

| | resultado |
|---|---|
| tests W-1.3A | **16 passed** |
| auditor W-1.3A | **13 OK · 0 fallas** |
| cardinalidad e idempotencia | sin cambios |
| W-1.2: `period_kind`, `start/end`, `measurement_date`, `unit_measure`, `decimals`, `context_id`, `fact_key` | **idénticos** — 1.423 DURATION, 2.697 `econ_key`, 0 `decimals` no nulos |
| SEC: 5 digests | **IGUAL** |
| `catalaxia` | 34 migraciones · 0 hechos CNV |

```
W1.3A = PASS   ·   W1.2 = PASS   ·   SEC_UNCHANGED = PASS
```

---

## 16 · Auditoría independiente (§13)

`c4_auditoria_w14.py` — **11 OK · 0 fallas**. Detalle en `CNV_W14_AUDIT.md`.

Usa un **método distinto** para inferir el perímetro: interpolación lineal en
vez de mediana de vecinos. **Coincide en 6 de 7 pares**, incluido BYMA.

**Discrepa en LONG 2020-12-31** — clasificador `UNKNOWN`, auditor
`PERIMETER_CONFLICT`. No se ajustó ningún umbral para hacerlos coincidir. La
regla aplicada, decidida antes de saber cuál método preferiría: **donde dos
métodos independientes discrepan, el caso queda `UNKNOWN`.** Una clasificación
que depende del método no es una clasificación.

---

## 17 · Riesgos y cuestiones abiertas

**R-1 · El 56 % del corpus múltiple queda en `UNKNOWN`.** Es el resultado
correcto dado lo que hay, no una deuda de análisis. Para reducirlo hace falta
evidencia que no existe localmente: la fecha de publicación de los 69 CUITs
restantes, o señal textual de corrección en los documentos.

**R-2 · Seis de siete pares no tienen posterioridad significativa.** Presentados
con horas de diferencia, ninguna evidencia podrá convertirlos en supersesión:
**probablemente sean pares individual/consolidado con una etiqueta mal puesta**,
y la solución no es semántica sino de calidad de origen.

**R-3 · La confianza del detector de perímetro es baja en términos absolutos**
(0,31–0,36). Separa bien, pero no es una prueba: es evidencia.

**R-4 · Hay valores incorrectos en la tabla de producción.** BYMA 2021-12-31
CONSOLIDADO tiene la cifra individual. En el fixture están las dos ocurrencias;
en producción sigue solo la equivocada.

**R-5 · `supersedes` y `effective_*` siguen OPEN**, ahora con el motivo
precisado: no falta el orden —está— falta la evidencia de reemplazo.

**R-6 · La política de valor corriente está especificada y no implementada.**
Hoy un consumidor que lea la tabla de ocurrencias vería dos valores sin ninguna
indicación de cuál usar.

---

## 18 · Dictamen

| condición de PASS | estado |
|---|---|
| todas las ocurrencias preservadas | ✔ 103.268, sin cambios |
| las 292 identidades múltiples analizadas | ✔ 7 pares, una por una |
| no se confunde valor distinto con restatement | ✔ 226 divergentes, 0 restatements confirmados · M3 |
| no se confunde orden con supersesión | ✔ M4 con el contraejemplo de BYMA |
| conflictos de perímetro explícitos | ✔ detector general, evidencia sin modificar el origen |
| BYMA preservado | ✔ las dos ocurrencias · I8 |
| `supersedes` solo con evidencia suficiente | ✔ **0 relaciones creadas** |
| auditor independiente coincide | ✔ 6 de 7, con la discrepancia declarada |
| mutaciones fallan | ✔ M1–M6 |
| W-1.3A sigue PASS | ✔ |
| W-1.2 sigue PASS | ✔ |
| SEC intacto | ✔ |
| `catalaxia` intacta | ✔ |

```
W1.4 OCCURRENCE SEMANTICS = PASS_WITH_WARNINGS
```

**PASS** en las trece condiciones.

**WITH_WARNINGS** por los `UNKNOWN` legítimos, que es exactamente la causal que
el enunciado prevé: **164 de 292 identidades (56 %) no se pueden clasificar con
la evidencia disponible**, y una discrepancia declarada entre los dos métodos.

La prioridad se respetó en su orden: **preservar** (103.268 intactas) >
**clasificar** (7 pares, con `UNKNOWN` donde corresponde) > **interpretar**
(0 supersesiones) > **publicar** (nada se publicó).

No se sacrificó una sola pieza de evidencia documental para producir un valor
limpio.
