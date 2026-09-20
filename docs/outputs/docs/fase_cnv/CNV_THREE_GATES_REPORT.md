# CIERRE DEL SUBSISTEMA CNV — TRES GATES

**METR · CUIT 30657863676 · worktree `catalaxia-cnvmig`, rama
`feat/cnv-canonical`**

```
F063_GATE           = PASS
CNV_INGESTION_GATE  = PASS
CNV_SEMANTIC_GATE   = PASS
```

No se avanzó a `econ_key`, supersession, ratio engine, publicación, screener ni
Market. No se tocó SEC ni producción.

---

## 1 · Estado inicial (FASE 0)

| | |
|---|---|
| repo principal | `fix/ttm-ratios-cnv` @ `e9d794b` |
| worktree | `feat/cnv-canonical` @ `e9d794b` |
| producción (5432) | esquema `public` — sin `parsed`/`derived` |
| bases dev (5433) | `catalaxia`, `cnvmig`, `dbgcopy`, `e2e_final`, `f051_check`, `metrgolden` |
| `screener.db` | `2026-08-23 13:42:23` · 1.504.714.752 bytes |
| **F-063 mergeado** | **NO** — `job5` del worktree difería del repo |

Digests de línea base:

```
SEC (cnvmig y metrgolden)   133.902   63629c0fc2ee76ad8038660c4815b443
METR en cnvmig                2.875   84249140c005f834468fbb1a1b993826
METR en metrgolden            2.795   63b9ce0e874153c4558e8c75acdaca45
migraciones                      37
vocabulario worktree             81   (67 conceptos + 14 ratios, con parse_nil)
vocabulario repo principal       51   (39 + 12, sin parse_nil)
```

---

## 2 · GATE 1 — F-063 CLOSED

**Commit `ca78415`** en `feat/cnv-canonical`, 5 archivos, +1.174/−29 líneas.
Todo lo que sigue se re-ejecutó **desde fixture limpio después del commit**; no
se aceptaron los resultados previos del worktree.

| requisito | resultado |
|---|---|
| 81/81 códigos reconocidos | **PASS** — 67 + 14 |
| 4.648 observaciones | **PASS** |
| 0 pérdidas de código | **PASS** |
| 620 observaciones NIL | **PASS** |
| 0 solapamientos NIL/valor | **PASS** |
| 100 % de cobertura en EEFF válidos | **PASS** |
| 42 ratios potencialmente calculables | **PASS** — 38 + 4 |
| auditoría independiente | **PASS** — 0 fallas |
| suite F-063 | **PASS** — 12/12 |
| regresión CNV | **PASS** — 209 tests |
| SEC sin cambios | **PASS** |

### Verificaciones puntuales

```
 1. vocabulario 81/81            OK
 2. parse_nil existe             OK
 3. SQL_INSERT_NIL existe        OK
 4. SQL_INSERT compat (15 cols)  OK    COLUMNAS = 15
 5. 8000008 reconocido           OK -> inmovilizacion_capital
 6. 8000012 reconocido           OK -> endeudamiento_corto_plazo
 7. 1120100 Inventory como NIL   OK
 8. 0 solapamientos NIL/valor    OK
 9. 4.648 observaciones          OK
10. 620 NIL                      OK
11. 60 documentos                OK
12. NIL siempre con valor 0      OK
13. ratios CNV_* sin escala      OK -- 714/714 idénticos al RAW
```

> El check 13 marcó primero un falso positivo (`CNV_deuda_fin_ebitda = −1.184`,
> con `|valor| > 1000` como heurística). La prueba correcta es la comparación
> contra el RAW: **714 de 714 filas `CNV_*` tienen exactamente el valor crudo,
> cero escaladas**. El −1.184 es legítimo: el EBITDA de ese trimestre es −17 M,
> así que el cociente es grande porque el denominador tiende a cero.

### Las 3 fallas de `test_f038_traza_corrida.py`

**Preexistentes, demostrado por dos vías independientes:**

1. `git diff ca78415^ ca78415 -- tests/test_f038_traza_corrida.py scripts/market/
   migrations/market/ engine/` está **vacío**: el commit no toca nada de eso.
2. El test tiene **0 referencias** a `job5`, `cnv`, `CNV`, `parse_nil`, `es_nil`
   o `CODIGOS`. Su última modificación es del commit `25756e1`.

---

## 3 · GATE 2 — CNV INGESTION GREEN

### El hallazgo que corrige tres informes

Los 226 documentos que F-062, el Golden Run y F-063 llamaron *"la página de
espera del visor"* **no están vacíos y no fallaron**:

| estado | n | qué son |
|---|---:|---|
| `VALID_EEFF` | **60** | el formulario estructurado |
| `ATTACHMENT_ONLY` | **197** | presentaciones de **2000–2018** cuyo estado contable es un **PDF adjunto**: `TipoDeDocumento` = "Balance Consolidado" (142) / "Balance Subsidiaria" (55), más `NombreDocumento` y `FechaAlta` |
| `OTHER_FORM` | **29** | el **formulario de participaciones en sociedades**: `MetroEnergía S.A.`, 95 % del capital y de los votos |
| `UNKNOWN` | **0** | |
| `FAILED` | **0** | |
| **TOTAL** | **286** | |

**La transición es exacta y explica todo:**

| año | `VALID_EEFF` | `ATTACHMENT_ONLY` |
|---|---:|---:|
| 2000–2017 | **0** | 158 |
| 2018 | 2 | 8 |
| 2019–2025 | **58** | **0** |

La CNV pasó del PDF adjunto al formulario estructurado en **2018-2019**. **El
techo de 60 documentos no es un defecto del downloader: es la frontera del
formato.**

### Reconciliación

```
EXPECTED 286 = suma de estados 286                     OK
descargados 286 + fallidos 0 = 286                     OK
documentos sin estado: 0                               OK
no-válidos sin motivo: 0                               OK
```

Por documento se registra: `url`, `retrieved_at`, `download_state`,
`validation_state`, `sha256`, `content_type`, `bytes`, `motivo`, `retry_status`
y las señales de contenido. `CNV_INGESTION_CENSUS.csv`, 286 × 20.

### Validación por contenido, no por tamaño

Cuatro señales del documento: códigos con valor, `FechaCierre`, `TipoBalance`,
`UnidadMedida`. Los rangos de bytes **no se solapan** hoy (shells 50–78 KB,
válidos 147–173 KB), así que un umbral funcionaría — se descartó igual porque se
rompe con el primer emisor que publique un documento corto.

### Estrategia de recuperación

| población | ¿hay retry legítimo? | estado |
|---|---|---|
| `ATTACHMENT_ONLY` (197) | **sí** — `c3_cnv_fetch.py --adjuntos-presentaciones` | **NO recuperado**: devuelve PDF y el pipeline no parsea PDF. Estado explícito, nunca un éxito |
| `OTHER_FORM` (29) | **no** — nada falló | `NADA_QUE_REINTENTAR`: el documento está completo, sólo que es otro formulario |

**No se inventó ningún documento.** No se ocultó ni eliminó ninguno de los 226.

### Idempotencia

La clasificación es una **función pura del contenido**: no escribe, no descarga,
no muta el RAW. Re-ejecutarla no puede duplicar ni cambiar un SHA.
286/286 con SHA256, 286 distintos, 0 contenidos duplicados.

---

## 4 · GATE 3 — CNV SEMANTIC GREEN

### El hueco que faltaba

F-063 extendió el **vocabulario** del extractor pero no la **naturaleza
económica**. Al correr el adaptador sobre el fixture de F-063, excluyó
**1.428 filas** como *"concepto sin clasificar"*: el hecho llegaba a canonical
sin saber si es un saldo o un flujo, ni en qué unidad está.

Se declararon los **26 conceptos faltantes** en `c4_cnv_semantica.NATURALEZA`,
derivando `period_kind` y clase de unidad **del plan de cuentas**, no de una
decisión nueva:

```
1xxxxxx  Activo               INSTANT   monetario     13 conceptos
2xxxxxx  Pasivo y Patrimonio  INSTANT   monetario     23
3xxxxxx  Resultados y flujos  DURATION  monetario     25
8xxxxxx  Calculados           mixto     enumerado     20  (11 DUR + 9 INST)
```

**81 conceptos con naturaleza** = exactamente el vocabulario del extractor.

Y el adaptador ahora transporta `es_nil` hasta `derived.fact.is_nil` —una
columna que **ya existía** en el modelo y estaba fijada en `false` por
constante—, con lectura condicional para que un fixture anterior a F-063
produzca exactamente lo que producía.

### Resultado

```
filas procesables: 4.496 de 4.496      0 exclusiones
parsed.facts insertados: 4.496
derived.fact insertados: 4.496
segunda corrida: 0 inserts, 4.496 reusados
```

### Los once campos, sobre 4.496 hechos

| campo | violaciones |
|---|---:|
| `entity_id` | 0 |
| perímetro | 0 |
| `period_kind` | 0 |
| `start_date` / `end_date` | 0 |
| `instant_date` | 0 |
| `measurement_date` | 0 |
| `unit_measure` | 0 |
| escala (`unit_ref`) | 0 |
| `decimals` | 0 con valor — es la decisión certificada |
| `currency` | 0 |
| `is_nil` | 602 marcados, 0 con valor ≠ 0 |

### Unidades y escala

| `unit_measure` | `unit_ref` | n | máximo |
|---|---|---:|---:|
| `iso4217:ARS` | `ars@1e6` | 2.052 | 1.390.076.000.000 |
| `iso4217:ARS` | `ars@1e3` | 1.636 | 90.489.436.000 |
| **`xbrli:pure`** | **`pure`** | **692** | **1.184,18** |
| `iso4217:ARS/xbrli:shares` | `ars-por-accion` | 116 | 271,38 |

**I5 confirmado**: los ratios `CNV_*` llegan con `pure` y máximo 1.184 — sin
escala monetaria. Es la regresión explícita contra el bug de F-063.

> **Un error propio, detectado y corregido.** Mi primera propagación a
> `cnv_estados_norm` no incluyó `unidad_factor` en las columnas leídas, y la
> escala se aplanó a `ars@1e0` en los 4.496. Los valores seguían siendo
> correctos —ya venían escalados— pero **se perdía la escala declarada por el
> documento**, que es provenance. Se corrigió y se re-corrió todo.

### Los diez invariantes

`tests/test_cnv_semantic_invariants.py` — **16 tests, todos pasan**.

| id | invariante |
|---|---|
| I1 | `INSTANT` → `instant_date` obligatorio |
| I2 | `DURATION` → `start_date` y `end_date` obligatorios (+ acumulan desde enero) |
| I3 | `start_date <= end_date` |
| I4 | consolidado ≠ individual: el perímetro está en el `context_id`, y 2.248 combinaciones concepto/período tienen ambos sin colisionar |
| I5 | `pure` sin escala monetaria (+ el EPS tampoco recibe la del documento) |
| I6 | `DECLARED_NIL` → `is_nil = true`, valor 0 |
| I7 | `EXPLICIT_ZERO` → `is_nil = false`, valor 0 |
| I8 | `MISSING` → no hay fila; los hechos canónicos nunca exceden el origen |
| I9 | unidad y escala del vocabulario cerrado; `decimals` no duplica la escala |
| I10 | `measurement_date` coherente (+ la apertura se reexpresa) |

> **I10b encontró algo real.** La serie de patrimonio de apertura tiene un 0 en
> Q3-2025 que rompía la monotonía. No es un fallo de reexpresión: **METR declara
> ese concepto con guion en ese documento**, y `is_nil = true`. El test
> comparaba un cero declarado contra importes reexpresados —dos cosas
> distintas—. Se corrigió el test, no el dato.

---

## 5 · METR 2024 · E2E

**Los 4 trimestres × los 2 perímetros, completos:**

| período | perímetro | hechos | INSTANT | DURATION | nil | escalas | docs |
|---|---|---:|---:|---:|---:|---:|---:|
| 2024-03-31 | CONSOLIDADO | 81 | 45 | 36 | 12 | 3 | 1 |
| 2024-03-31 | INDIVIDUAL | 81 | 45 | 36 | 12 | 3 | 1 |
| 2024-06-30 | CONSOLIDADO | 81 | 45 | 36 | 12 | 3 | 1 |
| 2024-06-30 | INDIVIDUAL | 81 | 45 | 36 | 12 | 3 | 1 |
| **2024-09-30** | **CONSOLIDADO** | **81** | 45 | 36 | 12 | 3 | 1 |
| 2024-09-30 | INDIVIDUAL | 81 | 45 | 36 | 12 | 3 | 1 |
| 2024-12-31 | CONSOLIDADO | 81 | 45 | 36 | 12 | 3 | 1 |
| 2024-12-31 | INDIVIDUAL | 81 | 45 | 36 | 12 | 3 | 1 |
| | | **648** | | | **96** | | **8** |

**El 2024-09-30 CONSOLIDADO es el documento #3277363**, el que faltaba desde el
sprint de runbooks. La cadena completa:

```
tag         valor            is_nil  unit_measure               unit_ref         kind      periodo                  sha256
Assets      1.083.917.000.000   f    iso4217:ARS                ars@1e6          INSTANT   ..2024-09-30             66292aff…
CNV_roe                  0,26   f    xbrli:pure                 pure             DURATION  2024-01-01..2024-09-30   66292aff…
EPS_basico             223,96   f    iso4217:ARS/xbrli:shares   ars-por-accion   DURATION  2024-01-01..2024-09-30   66292aff…
Equity        567.796.000.000   f    iso4217:ARS                ars@1e6          INSTANT   ..2024-09-30             66292aff…
Inventory                 0,0   t    iso4217:ARS                ars@1e6          INSTANT   ..2024-09-30             66292aff…
NetIncome     129.096.000.000   f    iso4217:ARS                ars@1e6          DURATION  2024-01-01..2024-09-30   66292aff…
Revenue       670.359.000.000   f    iso4217:ARS                ars@1e6          DURATION  2024-01-01..2024-09-30   66292aff…
```

`Inventory = 0,0` con **`is_nil = true`**: el cero declarado llega marcado hasta
la capa canónica. Antes era indistinguible de un importe cero, y antes de F-063
directamente no existía.

Cadena demostrada: **CNV → RAW → validación de contenido → extracción → parsed →
canonical → contexto → período → unidad → NIL → validación semántica →
auditoría.** Sin ratio engine ni publicación, por alcance.

---

## 6 · Regresión, por suite y por fixture

| suite | fixture | resultado |
|---|---|---|
| F-063 (12) | `metr_f063.db` | **12 passed** |
| Golden Run METR (18) | `metrgolden` + `metr_golden.db` | **18 passed** |
| F-061 + W1.1 (19) | `cnvmig` | **19 passed** |
| W1.2 / W1.3 / W1.3A / W1.4 / W1-W2 (92) | `cnvmig` + `metr_sprint.db` | **92 passed** |
| TIKR + METR E2E (68) | `cnvmig` + `metr_sprint.db` | **68 passed** |
| **Invariantes semánticos (16)** | `metrsem` + `metr_f063.db` | **16 passed** |
| Runbook operability (22) | repo principal | **22 passed** |
| suite completa | `cnvmig` | **489 passed** |
| `test_f038_traza_corrida` | `cnvmig` | **3 failed** · preexistentes |

**Total: 247 tests específicos de CNV, todos verdes**, más las 489 de la suite
completa.

> Las 28 fallas que aparecieron al correr todo contra una sola base eran **de
> entorno**: los tests de TIKR y W-1.3 están escritos contra `cnvmig` y
> `metr_sprint.db`. Con cada suite en su fixture, pasan todas.

---

## 7 · Protección de SEC

```
cnvmig      133.902 | 63629c0fc2ee76ad8038660c4815b443
metrgolden  133.902 | 63629c0fc2ee76ad8038660c4815b443
metrsem     133.902 | 63629c0fc2ee76ad8038660c4815b443
esperado    133.902 | 63629c0fc2ee76ad8038660c4815b443
```

| artefacto | estado |
|---|---|
| `screener.db` | `2026-08-23 13:42:23` · 1.504.714.752 · **sin cambios** |
| producción 5432 | esquema `public` · **sin cambios** |
| `cnvmig` METR (certificado FY2024) | 2.875 · `84249140c005f834…` · **idéntico** |
| `job5` del repo principal | **sin tocar** |
| `ratio_engine.py`, Market, Identity, esquema canónico | **sin tocar** |

Toda escritura cayó en `metr_f063.db` y en la base `metrsem`, creada para GATE 3.

---

## 8 · Archivos modificados y commits

| commit | archivos |
|---|---|
| **`ca78415`** F-063 | `job5_v2_extract_eeff.py` (M) · `c7_f063_maximizar.py` · `c7_f063_catalogo.py` · `c7_f063_auditoria.py` · `test_f063_extraction_maximization.py` |
| **`4cf1aa5`** GATE 2/3 | `c8_cnv_ingestion_gate.py` · `c4_cnv_adapter.py` · `c4_cnv_semantica.py` · `test_cnv_semantic_invariants.py` |

Los dos en `feat/cnv-canonical`. **Nada mergeado a `main` ni a
`fix/ttm-ratios-cnv`**: esa integración es una decisión de ustedes, no de este
sprint.

Digests del resultado:

```
METR en metrsem   4.496 hechos · 602 nil · 58 documentos
METR 2024           648 hechos ·  96 nil ·  8 documentos
fixture             metr_f063.db · cnv_estados_v2 4.648 · cnv_estados_norm 4.496
```

---

## 9 · Riesgos restantes

| # | riesgo | estado |
|---|---|---|
| **R1** | **197 documentos 2000-2018 sin extraer** — el EEFF es un PDF. Requiere un parser de PDF que no existe | fuera de alcance, cuantificado |
| **R2** | **152 filas colapsan en `cnv_estados_norm`** (4.648 → 4.496): esa tabla conserva la PK económica sin `accn`, así que dos presentaciones del mismo período compiten. `cnv_estados_v2` ya tiene la PK por ocurrencia | conocido (W-1.3A), fuera de alcance |
| **R3** | **Nada mergeado.** El `job5` de producción sigue con 51 códigos y sin `parse_nil` | decisión pendiente |
| **R4** | Los 29 `OTHER_FORM` contienen la participación en MetroEnergía (95 %), que es justo el dato de segmentos que falta en el mapa de dependencias. No se explotó | oportunidad identificada |
| **R5** | 3 fallas preexistentes en `test_f038_traza_corrida.py` | ajenas a CNV |

---

## 10 · Decisión de cada gate

```
F063_GATE           = PASS
  81/81 codigos · 4.648 observaciones · 620 NIL · 0 perdidas de codigo
  auditoria independiente 0 fallas · 12 tests · re-ejecutado desde fixture limpio
  commit ca78415

CNV_INGESTION_GATE  = PASS
  286 = 60 VALID_EEFF + 197 ATTACHMENT_ONLY + 29 OTHER_FORM + 0 UNKNOWN
  reconciliacion cierra · 0 sin estado · 0 sin motivo
  ningun documento inventado, ocultado ni declarado exito falsamente

CNV_SEMANTIC_GATE   = PASS
  4.496 de 4.496 procesables · 0 exclusiones · 602 nil en canonical
  11 campos reconstruibles · 0 violaciones · 16 invariantes
  idempotencia: 0 inserts en la segunda corrida

METR 2024 E2E       = COMPLETO
  4 trimestres x 2 perimetros · 648 hechos · documento 3277363 incluido

SEC                 = IDENTICO   133.902 | 63629c0f...
PRODUCCION          = SIN CAMBIOS
```

Los tres gates cierran con evidencia reproducible. **No se avanza a `econ_key`,
supersession, ratios ni publicación.**
