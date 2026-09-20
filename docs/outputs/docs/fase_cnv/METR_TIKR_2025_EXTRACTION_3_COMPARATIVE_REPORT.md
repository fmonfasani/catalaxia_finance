# SPRINT — 3 EXTRACTION GAPS + COMPARATIVO 8000002

**Fecha:** 2026-09-02 · worktree `catalaxia-cnvmig` · fixture `cnvmig` (5433)
**Alcance:** exclusivamente los códigos `2211300`, `2210300`, `3011100` y
`8000002`. Las otras 62 métricas no se tocaron.
**Producción:** no modificada — prueba en §13.

---

## 1 · Cambios realizados

| archivo | cambio |
|---|---|
| `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` | 4 códigos agregados **al diccionario `CODIGOS` existente** — sin mecanismo paralelo |
| `scripts/engine/c4_cnv_semantica.py` | 4 entradas en `NATURALEZA` + `APERTURA_DE_EJERCICIO` + `instante_de_apertura()` |
| `scripts/engine/c4_cnv_adapter.py` | la regla de apertura, cableada en el mismo bucle |
| `scripts/engine/c4_auditoria_metr_e2e.py` | su propia transcripción de códigos, actualizada |
| `scripts/engine/c4_auditoria_w13a.py` | ídem |
| `scripts/engine/c4_metr_tikr_2025.py` · `_ratios.py` | reconciliación con los facts nuevos |
| `data/metr_sprint.db` | fixture SQLite: copia de `cnv_estados_norm` + 178 filas nuevas |

La cadena se respetó entera:

```
RAW → job5 (parser) → cnv_estados_norm → adapter → parsed.facts
    → derived.fact → ratio
```

---

## 2 · Evidencia RAW por concepto

Documento `d96fd259-c5ce-431f-8e14-17af592b99f9.html`, presentación #3487124 ·
SHA-256 `460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191` ·
FY2025 · CONSOLIDADO · `UnidadMedida = "Millones de $"` → escala 10⁶.

| código | etiqueta en el documento | impreso | × escala | normalizado | period_kind | docs |
|---|---|--:|--:|--:|---|--:|
| `2211300` | INTERESES NO CONTROLANTES | 1.880,00 | 10⁶ | 1.880.000.000 | INSTANT | 27/56 |
| `2210300` | AJUSTE DE CAPITAL | 346.707,00 | 10⁶ | 346.707.000.000 | INSTANT | 56/56 |
| `3011100` | OTROS INGRESOS | 10.002,00 | 10⁶ | 10.002.000.000 | DURATION | 44/56 |
| `8000002` | TOTAL PATRIMONIO NETO DEL EJERCICIO ANTERIOR | 829.478,00 | 10⁶ | 829.478.000.000 | INSTANT | 51/56 |

La escala **no se hardcodeó**: sale de `UnidadMedida` por el mismo mecanismo
que el resto (`factor_unidad` en el parser). El `period_kind` sale del primer
dígito del plan de cuentas, igual que los otros 51 conceptos.

---

## 3 · Cómo quedó modelado el 8000002

### Qué período representa — determinado desde el dato, no desde TIKR

La hipótesis obvia —"es el patrimonio del ejercicio anterior"— **es incompleta**.
El valor **crece dentro de cada ejercicio**:

| ejercicio | Q1 | Q2 | Q4 | apertura (cierre anterior) |
|---|--:|--:|--:|--:|
| 2024 | 331.184 | 392.674 | 475.654 | 218.430 |
| factor | 1,5162 | 1,7977 | 2,1776 | |
| 2025 | 684.579 | 728.402 | 829.478 | 630.542 |
| factor | 1,0857 | 1,1552 | 1,3155 | |

**La apertura es fija y el factor crece.** Es el mismo saldo re-expresado a
fechas de medición sucesivas — exactamente lo que `measurement_date` modela.

```
8000002 = patrimonio de APERTURA del ejercicio,
          re-expresado a la fecha de medición del documento
```

### El modelado, reutilizando el mecanismo existente

```
period_kind       INSTANT
instant_date      2024-12-31        ← la apertura, derivada de `periodo_de` − 1 día
measurement_date  2025-12-31        ← la FechaCierre del documento
context_id        CONSOLIDADO|INSTANT||2024-12-31|2025-12-31
unit_measure      iso4217:ARS   ·  unit_ref ars@1e6  ·  decimals NULL
econ_key          8074be2dbf0d…     ← DISTINTA de la del cierre 2024
fact_key          7e1993a6f9d2…
```

**No se creó una segunda representación de comparativos.** El modelo de W-1.3
ya la tenía: `econ_key` incluye `measurement_date`, así que el saldo al
2024-12-31 medido en dic-2024 y el mismo saldo medido en dic-2025 son **dos
hechos distintos**, verificado:

```
Equity@2024-12-31 medido dic-2024   econ_key 90d94d6f85aa…
Apertura@2024-12-31 medida dic-2025 econ_key 8074be2dbf0d…
```

Y la guarda de fecha de `ratio_inputs` lo excluye de la selección de insumos
corrientes: **0 de 51 comparativos la pasan**, que es lo correcto.

> Si el documento no trae el código —5 de 56— **no se inventa nada**: el fact
> simplemente no existe. Verificado por test.

---

## 4 · Fórmula exacta del ROE

```
ROE = NetIncome / ((PatrimonioAperturaEjercicio + Equity) / 2)
    = 132.483 / ((829.478 + 960.345) / 2)
    = 132.483 / 894.912
    = 0,148040
```

**Los tres insumos son facts canónicos con la misma `measurement_date`
(2025-12-31).** Verificado por test.

### Cómo se validó la fórmula — sin usar TIKR

La CNV publica su propio ROE en el código `8000009 RENTABILIDAD PATRIMONIO
NETO`. Contrastando qué fórmula lo reproduce:

| ejercicio | CNV_roe | NI / PN cierre | NI / promedio(8000002, PN) | reproduce |
|---|--:|--:|--:|---|
| 2018 | −0,00 | −0,0000 | −0,0000 | promedio |
| **2023** | 0,56 | 0,4411 | **0,5642** | **promedio** |
| **2024** | 0,28 | 0,2484 | **0,2832** | **promedio** |
| **2025** | 0,15 | 0,1380 | **0,1480** | **promedio** |
| 2019 | 0,20 | 0,0595 | 0,0594 | ninguna |
| 2020 | −0,16 | −0,3751 | −0,2555 | ninguna |
| 2021 | −0,03 | −0,2518 | −0,2236 | ninguna |
| 2022 | 0,29 | 0,1470 | 0,1586 | ninguna |

**En 2023, 2024 y 2025 la fórmula del promedio reproduce el ratio que publica
la propia CNV.** Esa es la justificación primaria. Que además coincida con el
14,8 % de TIKR es **consecuencia, no objetivo**.

> **Limitación reportada:** en 2019–2022 ninguna de las dos variantes reproduce
> el `CNV_roe` publicado. Es la discrepancia de `CNV_roe` ya conocida de ciclos
> anteriores; **este sprint no la resuelve**.

### El factor 1,3155 no quedó en ninguna parte

Un test lo verifica explícitamente: ni `1.3155` ni `160_859` aparecen en
`c4_metr_tikr_ratios.py`, `c4_cnv_semantica.py` ni `c4_cnv_adapter.py`. **El
comparativo re-expresado se lee del documento, no se estima.**

---

## 5 · Resultado antes / después

| | antes | después | Δ |
|---|--:|--:|--:|
| facts de METR | 2.697 | **2.875** | +178 |
| métricas evaluadas | 152 | 153 | +1 |
| **MATCH_EXACT** | 34 | **36** | **+2** |
| MATCH_DERIVED | 8 | 8 | 0 |
| MATCH_ROUNDING | 8 | **9** | **+1** |
| **coincidencias** | **50** | **53** | **+3** |
| DEFINITION_DIFFERENCE | 27 | 27 | 0 |
| INPUT_DIFFERENCE | 1 | 0 | −1 → pasó a MATCH |
| **POSSIBLE_RECLASSIFICATION** | 0 | **2** | **+2** |
| **CATALAXIA_MISSING_INPUT** | **66** | **63** | **−3** |
| TIKR_DEFINITION_UNVERIFIED | 2 | 2 | 0 |
| TIKR_DERIVED_NOT_REPRODUCIBLE | 2 | 2 | 0 |
| UNRESOLVED | 4 | 4 | 0 |
| **CATALAXIA_ERROR** | **0** | **0** | 0 |

*(La métrica +1 es la fila de verificación de la identidad patrimonial, que se
agregó como control explícito.)*

---

## 6 · Nuevos MATCH — con evidencia

### Minority Interest → MATCH_EXACT

```
TIKR       1.880
Catalaxia  1.880   código 2211300 "INTERESES NO CONTROLANTES"
```

Es el **mismo concepto contable**, traducción literal — no una coincidencia
numérica.

### ROE → MATCH_ROUNDING

```
TIKR       0,1480
Catalaxia  0,148040
```

Cadena primaria completa, validada contra el ratio de la propia CNV.

### La identidad patrimonial cierra sin residuo

```
Capital                       569
Reservas                  480.533
ResultadosNoAsignados     130.656
AjusteDeCapital           346.707   ← nuevo
InteresesNoControlantes     1.880   ← nuevo
                        ─────────
suma                      960.345
Equity                    960.345   diferencia 0
```

Los cinco son facts canónicos. **El residuo de 348.587 que arrastraban los
informes anteriores desapareció.**

---

## 7 · Nuevos EXPLAINED — dos reclasificaciones, no matches

Aquí el valor coincide pero **el concepto no es el mismo**, y no se afirma
equivalencia:

| TIKR | valor | concepto CNV | clasificación |
|---|--:|---|---|
| Other Comprehensive Income / Other | 346.707 | `AJUSTE DE CAPITAL` — la re-expresión del capital por IAS 29, que **no es** el OCI de IFRS | `POSSIBLE_RECLASSIFICATION` |
| Asset Devaluation | 10.002 | `OTROS INGRESOS` — un renglón de ingresos operativos | `POSSIBLE_RECLASSIFICATION` |

**Catalaxia conserva el concepto primario de la CNV.** La coincidencia numérica
queda registrada como evidencia de que TIKR reclasificó, no como prueba de
equivalencia. Es la misma disciplina que descartó
`ResultadosNoAsignados ↔ Net Income`.

---

## 8 · NO_INPUT restantes: 63

| clase | antes | ahora |
|---|--:|--:|
| A · EXTRACTION_GAP | 3 | **0** |
| B · DERIVATION_GAP | 10 | 10 |
| C · COMPARATIVE_GAP | 4 | **3** |
| D · CNV_COVERAGE_GAP | 34 | 34 |
| E · TIKR_NORMALIZATION | 4 | 4 |
| F · SEMANTIC_AMBIGUITY | 11 | 11 |

**Los tres extraction gaps quedaron cerrados y ninguna otra clase se movió**,
que es exactamente lo que el sprint pedía.

Los 3 COMPARATIVE_GAP que quedan son los per-share, que necesitan el número de
acciones. El de `Cash Beginning` sigue abierto: **se buscó y la CNV no publica
un comparativo de caja**, sólo el de patrimonio.

---

## 9 · Tests

`tests/test_metr_tikr_2025_extraction_3_comparative.py` — **26 passed**.

| | qué exige |
|---|---|
| T1–T4 | cada concepto se extrae del RAW y `valor = impreso × escala del documento` |
| T5 | la ausencia de `8000002` **no** genera un valor: 51 facts sobre 56 documentos |
| T6 | `iso4217:ARS` · `ars@1e6` · `decimals NULL` |
| T7 | conservan `entity_id` y `entity_key` |
| T8 | `fact_key` y `econ_key` reproducen sus fórmulas |
| T9–T10 | 2.875 hechos = 2.875 claves; 0 evidencias duplicadas |
| — | el comparativo apunta a la apertura, no al cierre |
| — | no colisiona con el cierre 2024: `econ_key` distintas |
| — | no entra a la selección de insumos: 0 de 51 pasan la guarda |
| — | la identidad patrimonial cierra sin residuo |
| — | el ROE sale de insumos con la misma medición y coincide con `CNV_roe` |
| — | **no quedó hardcodeado ningún factor de re-expresión ni ningún valor de TIKR** |

Suite completa: **426 passed · 3 failed (F-038, preexistentes) · 1 skipped**.

> **Dos tests había que actualizar y se hicieron más estrictos, no más laxos.**
> `test_i4` y `test_i14` fijaban la cardinalidad en 2.697. Ahora exigen que el
> **digest de los 2.697 preexistentes siga idéntico** y que la diferencia sean
> exactamente 178 conceptos incorporados.

---

## 10 · Mutation tests

| | mutación | resultado |
|---|---|---|
| M1–M4 | alterar el valor de cada uno de los 4 conceptos | **FALLA** — no reproduce el RAW |
| M5 | cambiar la unidad a `xbrli:pure` | **FALLA** — unidad incorrecta |
| M6 | cambiar la escala (÷1000) | **FALLA** |
| M7 | usar la minoritaria del otro perímetro | **la identidad patrimonial no cierra** |
| M8 | cambiar `measurement_date` | **FALLA** |
| M9 | cambiar `entity_id` | sale del conjunto auditado; la transacción revierte |
| M10–M11 | `fact_key` / `econ_key` con el contexto del cierre | **dan claves distintas** |
| M12 | períodos sin comparativo | existen: ahí el ROE promedio es `NOT_CALCULABLE`, no un número inventado |

> **Las mutaciones encontraron un problema real:** el auditor E2E no conocía los
> conceptos nuevos y fallaba **en la línea de base**, no sólo bajo mutación. Se
> actualizó su transcripción propia de códigos —manteniendo su independencia— y
> volvió a dar 0 fallas sobre 2.875 facts.

---

## 11 · Idempotencia

```
2ª corrida:  parsed.facts 0 insertados · 2.875 reusados
             derived.fact 0 insertados · 2.875 sin cambio
             0 conflictos
```

---

## 12 · Regresión

| | resultado |
|---|---|
| **digest `fact_key` de los 2.697 preexistentes** | **IGUAL** |
| SEC: hechos · `fact_key` · `context_id` · `source_hash` · ratios | **IGUAL** (5 digests) |
| documentos CNV | 56, sin cambios |
| las 62 métricas fuera de alcance | sin cambios en su clasificación |

---

## 13 · Producción no fue modificada

| | |
|---|---|
| `screener.db` | mtime **2026-08-23 13:42:23**, sin cambios. Se abrió **sólo en lectura** |
| `job5_v2_extract_eeff.py` (repo principal) | `git status` limpio · **0 códigos nuevos** |
| `s0_normalizar_cnv.py` (repo principal) | `git status` limpio |
| worktree | 2 códigos nuevos presentes |
| `catalaxia` | 34 migraciones · 0 hechos CNV |
| destino verificado antes de escribir | `catalaxia_engine@127.0.0.1:5433/cnvmig` |

El adaptador conserva su guarda: se niega a correr si `db_name == "catalaxia"`.

---

## 14 · Ambigüedades que quedaron deliberadamente sin resolver

**A-1 · `AJUSTE DE CAPITAL` ↔ "Other Comprehensive Income".** El valor coincide
exacto, pero son conceptos contables distintos. Queda como
`POSSIBLE_RECLASSIFICATION`; Catalaxia guarda `AjusteDeCapital`.

**A-2 · `OTROS INGRESOS` ↔ "Asset Devaluation".** Ídem.

**A-3 · El `CNV_roe` no reconcilia en 2019–2022.** La fórmula del promedio
reproduce el ratio publicado por la CNV en 2018, 2023, 2024 y 2025, y no en los
otros cuatro. No se investigó: está fuera del alcance.

**A-4 · No hay comparativo de activo.** La CNV publica `8000002` para el
patrimonio y **nada equivalente para el activo**. Por eso el ROA sigue en
`TIKR_DEFINITION_UNVERIFIED` y el gap continúa abierto.

**A-5 · `Capital` = 569 sigue sin ser el número de acciones.** No se creó
ningún mapping de acciones, como el sprint exigía.

**A-6 · Los 5 documentos sin `8000002`.** No se les inventó apertura; en esos
períodos el ROE promedio no es calculable.

---

## 15 · Criterio de éxito

| | |
|---|---|
| 1 · los tres códigos se extraen desde RAW | ✔ |
| 2 · `8000002` se extrae desde RAW | ✔ 51/56 |
| 3 · no se inventan valores | ✔ T5, M12 |
| 4 · no se usa TIKR como input | ✔ test explícito |
| 5 · claves canónicas correctas | ✔ T8 |
| 6 · unidades y escalas correctas | ✔ T6 |
| 7 · comparativo correctamente identificado | ✔ §3, evidencia primaria |
| 8 · el ROE se modifica con cadena primaria reproducible | ✔ validado contra `CNV_roe` |
| 9 · sin mappings semánticamente dudosos | ✔ 2 reclasificaciones declaradas |
| 10 · tests | ✔ 26 + 426 en la suite |
| 11 · mutaciones | ✔ 12 |
| 12 · E2E | ✔ auditor: 2.875 facts, 0 fallas |
| 13 · idempotencia | ✔ |
| 14 · sin regresiones | ✔ digest de los 2.697 idéntico |
| 15 · producción no modificada | ✔ |

```
SPRINT = PASS
```

El gate de `METR_TIKR_2025` **no se modificó**: sigue en `PASS_WITH_WARNINGS`.
