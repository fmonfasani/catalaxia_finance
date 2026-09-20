# CNV W-1.4 — MATRIZ DE CLASIFICACIÓN

**Fecha:** 2026-09-02 · CSV completo en `CNV_W14_CLASSIFICATION.csv`

---

## 1 · Resumen

Los 292 grupos con múltiples ocurrencias son **7 pares de documentos**
(14 documentos), no 292 situaciones distintas. Cada par aporta entre 35 y 48
identidades económicas.

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

**El 56 % queda en `UNKNOWN`, y eso es el resultado, no una falla.**

---

## 2 · Los 7 pares, uno por uno

### 2.1 · Orden y distancia temporal

El ordinal `Presentación #N` convertido a tiempo con la tasa de presentaciones
**de su propia época** (no un promedio global):

| par | ordinal A | ordinal B | distancia | tiempo transcurrido |
|---|--:|--:|--:|---|
| _ADR_0580 2019-12-31 | #2582644 | #2582645 | **1** | ~0,1 h |
| INTR 2021-12-31 | #2853682 | #2853687 | 5 | ~0,3 h |
| LONG 2019-03-31 | #2473321 | #2473328 | 7 | ~0,5 h |
| BYMA 2021-12-31 | #2864443 | #2864462 | 19 | ~1,1 h |
| LONG 2020-12-31 | #2728103 | #2728138 | 35 | ~2,3 h |
| LONG 2018-12-31 | #2449473 | #2449522 | 49 | ~3,2 h |
| **FIPL 2025-06-30** | #3412983 | #3425196 | **12.213** | **~27 días** |

**Seis de los siete se presentaron el mismo día, con horas de diferencia.** No
son republicaciones posteriores: son dos documentos de una misma sesión de
presentación. FIPL es el único con separación temporal real.

### 2.2 · Contenido y clasificación

| par | comunes | iguales | difieren | perímetro inferido | clasificación |
|---|--:|--:|--:|---|---|
| LONG 2018-12-31 INDIVIDUAL | 36 | 0 | 36 | sin inferencia concluyente | `UNKNOWN` |
| **LONG 2019-03-31 INDIVIDUAL** | 35 | 0 | 35 | `e0caf38b` → **CONSOLIDADO** (0,31) | **`PERIMETER_CONFLICT`** |
| LONG 2020-12-31 INDIVIDUAL | 36 | 0 | 36 | *los dos métodos discrepan* — §4 | `UNKNOWN` |
| INTR 2021-12-31 CONSOLIDADO | 46 | 4 | 42 | sin inferencia concluyente | `UNKNOWN` |
| **FIPL 2025-06-30 CONSOLIDADO** | 48 | **45** | **3** | ninguna serie encaja | **`PROBABLE_RESTATEMENT`** |
| _ADR_0580 2019-12-31 CONSOLIDADO | 46 | 12 | 34 | los dos perímetros encajan igual | `UNKNOWN` |
| **BYMA 2021-12-31 CONSOLIDADO** | 45 | 5 | 40 | `863efe00` → **INDIVIDUAL** (0,32) | **`PERIMETER_CONFLICT`** |

---

## 3 · Firma IAS 29 — medida, no supuesta

Una re-expresión multiplica **todos** los conceptos por el mismo factor de
inflación. Si el cociente B/A es constante entre conceptos, es re-expresión; si
no, es otra cosa.

| par | mediana B/A | dispersión mediana | ¿re-expresión? |
|---|--:|--:|---|
| LONG 2018-12-31 | 52,110 | **66,1 %** | no |
| LONG 2019-03-31 | 59,278 | **50,5 %** | no |
| LONG 2020-12-31 | 0,009 | **80,4 %** | no |
| INTR 2021-12-31 | 0,821 | **23,5 %** | no |
| FIPL 2025-06-30 | **1,000** | 0,0 % | **no** — factor 1 es "sin cambio", no re-expresión |
| _ADR_0580 2019-12-31 | **1,001** | 0,2 % | **no** — ídem |
| BYMA 2021-12-31 | 1,931 | **48,2 %** | no |

```
IAS29_REEXPRESSION = 0 casos
```

Los dos con dispersión baja tienen factor ≈ 1: los valores son esencialmente
los mismos, no re-expresados a otra moneda de cierre. Los cinco restantes
tienen dispersiones del 23 % al 80 %, incompatibles con un factor único.

---

## 4 · Dónde los dos métodos discrepan

El clasificador infiere el perímetro por **mediana de los dos períodos
vecinos**; el auditor independiente, por **interpolación lineal entre los
períodos que enmarcan**. Coinciden en 6 de 7:

| par | clasificador | auditor | |
|---|---|---|---|
| LONG 2018-12-31 | `UNKNOWN` | `UNKNOWN` | ✔ |
| LONG 2019-03-31 | `PERIMETER_CONFLICT` | `PERIMETER_CONFLICT` | ✔ |
| **LONG 2020-12-31** | **`UNKNOWN`** | **`PERIMETER_CONFLICT`** | **✗** |
| INTR 2021-12-31 | `UNKNOWN` | `UNKNOWN` | ✔ |
| FIPL 2025-06-30 | `PROBABLE_RESTATEMENT` | `PROBABLE_RESTATEMENT` | ✔ |
| _ADR_0580 2019-12-31 | `UNKNOWN` | `UNKNOWN` | ✔ |
| BYMA 2021-12-31 | `PERIMETER_CONFLICT` | `PERIMETER_CONFLICT` | ✔ |

**Regla aplicada, decidida antes de mirar cuál preferir:** donde dos métodos
independientes discrepan, el caso queda **`UNKNOWN`**. Una clasificación que
depende del método no es una clasificación.

Por eso LONG 2020-12-31 figura como `UNKNOWN` en la matriz consolidada, aunque
un método lo marque como conflicto de perímetro.

---

## 5 · Detalle por identidad

El CSV `CNV_W14_CLASSIFICATION.csv` tiene una fila por par con:

```
ticker · period_end · perimetro_declarado · doc_A · doc_B
ordinal_A · ordinal_B · distancia_ordinal · horas
conceptos_comunes · iguales · distintos
clasificacion · confianza · evidencia · perimetro_inferido
```

Las 292 identidades heredan la clasificación de su par: cada identidad
`(cuit, concepto, period_end, tipo_balance)` pertenece a exactamente uno de los
7 pares.
