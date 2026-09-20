# W-1.3A.2 — Validación multiemisor del modelo de ocurrencias CNV

**Sprint exclusivamente de AUDITORÍA.** No se implementó `econ_key`, no se modificó
ninguna PK, ni `cnv_estados_v2`, ni `cnv_estados_norm`, ni `derived.fact`, ni el
ratio engine, ni Market, ni Identity, ni producción, ni `main`. No se dedujo,
borró ni modificó ningún dato.

**Objetivo declarado del sprint: intentar romper el modelo** `accn ∈ identidad de
ocurrencia` / `accn ∉ econ_key`, derivado en W-1.3A a partir de un solo emisor
(METROGAS).

**Resultado: el modelo no se rompe, pero la clave económica que lo acompañaba sí.**
El corpus multiemisor produce un contraejemplo reproducible y con evidencia
documental, y ese contraejemplo ya está materializado en producción.

---

## 1. Veredicto

| afirmación | estado |
|---|---|
| `accn` pertenece a la identidad de ocurrencia | **DEMOSTRADO** (4.102/4.102 grupos) |
| `accn` NO pertenece a `econ_key` | **SOPORTADO** (no refutado; ver §16) |
| `(cuit, concepto, period_end, tipo_balance)` es identidad económica | **REFUTADO** |
| las colisiones son ocurrencias excedentes descartables | **REFUTADO** (370 de 4.102 no lo son) |

La conclusión de W-1.3A —«colisión = republicación, cero diferencias
económicas»— **es un artefacto de haber mirado un solo emisor**. En METROGAS es
cierta. En el corpus completo no.

---

## 2. Protecciones — antes y después

| protección | antes | después | estado |
|---|---|---|---|
| worktree branch | `feat/cnv-canonical` | `feat/cnv-canonical` | = |
| worktree commit | `4cf1aa5` | `4cf1aa5` | = |
| repo principal | `fix/ttm-ratios-cnv` @ `e9d794b` | idem | = |
| `migrations/` modificadas | ninguna | ninguna | = |
| digest SEC | `63629c0fc2ee76ad8038660c4815b443` / 133.902 | idéntico | = |
| `screener.db` | 1.504.714.752 B · 2026-08-23 13:42:23 | idéntico | = |
| esquemas en producción | `public` | `public` | = |
| ratio engine | sin tocar | sin tocar | = |

Todas las lecturas de `screener.db` se hicieron con `mode=ro`. Ninguna protección
falló; no hubo que detenerse.

---

## 3. Corpus y selección de la muestra

Se auditó sobre `whitelist_eeff_codigos.csv` (2.457 filas, **71 CUIT**), que es la
lista que `job5 --codigos` procesa realmente. La otra lista del repo,
`whitelist_eeff.csv` (32.778 filas, 437 CUIT), es más amplia pero cubre sólo 23 de
esos 71 emisores; auditar sobre ella habría dejado 48 emisores afuera y es un error
que se cometió y se corrigió durante el sprint.

Relevamiento (`ca_w13a2_survey.py` → `W13A2_CORPUS_SURVEY.csv`): de los 71 emisores,
**24 tienen al menos una colisión potencial**.

**No se tomó una muestra: se auditaron los 24**, es decir el 100 % de la población
con colisiones. Esto supera el mínimo pedido (≥5 emisores) y elimina el riesgo de
haber elegido sólo emisores de comportamiento conocido.

---

## 4. Censo (HECHO OBSERVADO)

`ca_w13a2_multiissuer_audit.py`, re-extrayendo desde el RAW con PK de ocurrencia:

| magnitud | valor |
|---|---|
| emisores auditados | 24 |
| documentos | 879 |
| ocurrencias (concepto × documento) | 66.240 |
| grupos de identidad económica | 62.138 |
| **grupos colisionados** | **4.102** |
| ocurrencias excedentes | 4.102 |
| tamaño máximo de grupo | 2 |
| pares de documentos que las producen | **55** |

Que «grupos» y «excedentes» coincidan es consecuencia de que **todos los grupos son
de a dos**, igual que en METR. No es una propiedad garantizada del modelo.

---

## 5. Clasificación global (TABLA OBLIGATORIA 1)

| categoría | grupos | % | confianza |
|---|---:|---:|---|
| `B_REPUBLICACION` — mismo valor, distinto documento | 3.732 | 91,0 % | ALTA |
| `H_VALOR_DISTINTO` — mismo hecho declarado, valor ≠ | 370 | 9,0 % | ALTA |
| **total** | **4.102** | 100 % | |

Ninguna clasificación quedó forzada ni sin evidencia. No se declaró
`C_RESTATEMENT` en ningún caso (§9).

Columnas que difieren dentro de los grupos:

| columna | naturaleza | difieren |
|---|---|---:|
| `accn` | documental | 4.102 |
| `sha256_documento` | documental | 4.102 |
| `ordinal_presentacion` | documental | 4.102 |
| `n_adjuntos` | documental | 368 |
| `valor` | económica | **370** |
| `es_nil` | económica | **60** |
| `unidad_factor` | económica | **0** |
| `unidad_medida` | económica | **0** |
| `moneda` | económica | **0** |
| `tipo` / `PeriodoBalance` | económica | **0** |

---

## 6. Subclasificación de las republicaciones (PASO 6)

Se separaron por hash de adjunto publicado por la CNV, no por ordinal.

| subcategoría | pares | grupos |
|---|---:|---:|
| `REPUBLICACION_PURAMENTE_IDENTICA` (todos los hashes coinciden) | 4 | 280 |
| `REPUBLICACION_CON_CAMBIO_DOCUMENTAL` (algún hash cambia, valor igual) | 41 | 3.092 |
| `CON_DIFERENCIA_ECONOMICA` | 10 | 730 (370 difieren) |

**HECHO OBSERVADO:** sólo el **6,8 %** de los grupos colisionados es republicación
puramente idéntica. En W-1.3A los 152 de METR se clasificaron en bloque como
republicación con confianza ALTA; esa etiqueta, aplicada al corpus completo,
describe una minoría.

---

## 7. Los 370 con valor distinto: qué son realmente (PASO 5)

Los 370 se concentran en **10 pares de documentos**. Se investigaron uno por uno con
orden documental, ordinal, adjuntos, hashes, campos de cabecera y contenido.

| categoría | pares | conceptos | evidencia decisiva |
|---|---:|---:|---|
| `D_PERIMETRO_DISTINTO` | 3 | 172 | el adjunto declara consolidado vs separado |
| `E_ENTIDAD_DISTINTA` | 3 | 182 | otra sociedad informante bajo el CUIT del padre |
| `F_CORRECCION_DE_FORMULARIO` | 3 | 6 | adjuntos 5/5 idénticos, sólo cambia el formulario |
| `G_CAMBIO_SIN_EVIDENCIA_SUFICIENTE` | 1 | 10 | adjuntos distintos, patrón de reexpresión |

**Ninguno se clasificó como `RESTATEMENT_CONFIRMADO`.** Ver §9.

### 7.1 `D_PERIMETRO_DISTINTO` — la CNV rotula igual dos perímetros distintos

**HECHO OBSERVADO.** Tres pares donde ambos documentos declaran el **mismo**
`TipoBalance` en el campo estructurado, y los adjuntos declaran perímetros opuestos:

| emisor | período | `TipoBalance` (ambos) | adjunto A | adjunto B |
|---|---|---|---|---|
| Bolsas y Mercados Argentinos | 2021-12-31 | `Consolidado` | *Informe Auditores Externos **Consolidados*** | *Informe Auditores Externos **Separados*** |
| Cia. Introductora de Bs.As. | 2021-12-31 | `CONSOLIDADO` | *EECC Ciba SA **separados*** | *EECC Ciba SA **consolidado*** |
| Aeropuertos Argentina 2000 | 2019-12-31 | `CONSOLIDADO` | *EEFF **Consolidados** 31.12.19* | *EEFF **Individuales** 31.12.19* |

Nótese que el orden se invierte entre BYMA y CIBA: el ordinal no dice cuál es cuál.

Confirmación aritmética independiente en BYMA 2021-12-31:

```
Patrimonio A (consolidado) 32.716.716.206
Patrimonio B (separado)    32.707.763.238
diferencia                      8.952.968  ==  InteresesNoControlantes de A
```

La diferencia de patrimonio es **exactamente** la participación no controlante, que
es la firma contable de consolidado vs separado bajo NIIF (método de la
participación). Activos 101.700 M vs 60.480 M por la misma razón. Esto no es un
cambio de estimación ni una corrección: son dos estados distintos del mismo cierre.

### 7.2 `E_ENTIDAD_DISTINTA` — estados de otra sociedad bajo el CUIT del emisor

**HECHO OBSERVADO.** Longvie (CUIT 30500833781) presenta, en el mismo cierre y con
`TipoBalance=INDIVIDUAL` en ambos documentos:

| período | doc A | doc B | empleados A/B | Activo A | Activo B |
|---|---|---|---:|---:|---:|
| 2018-12-31 | *Estados Financieros Individuales 31 12 2018 CNV* | *EEFF 31 12 2018_**COLOMBIA*** | 681 / 3 | — | — |
| 2019-03-31 | *Notas Estados Financieros 31 03 2019 **Individual*** | *EEFF 31 03 2019_**COLOMBIA*** | 655 / 3 | 1.277.448.945 | 19.728.694 |
| 2020-12-31 | *EEFF 31 12 2020 **L SAS*** | *EEFF 31 12 2020 Longvie SA individual* | 2 / 630 | — | — |

El campo `ODCCantidadEmpleados` —655 contra 3— y el nombre del adjunto coinciden:
el segundo documento son los estados de una **filial colombiana**, presentados por
Longvie bajo su propio CUIT. Cada lado es un balance internamente consistente
(19.728.694 = −6.329.886 + 26.058.580), de dos sociedades distintas.

El CUIT interno del documento coincide con el de la whitelist en **20/20** casos
verificados: no es un error de mapeo guid→CUIT. Es que la CNV identifica la
*presentación* por el CUIT del presentante, no la *entidad informante*.

### 7.3 `F_CORRECCION_DE_FORMULARIO` — adjuntos idénticos, formulario corregido

**HECHO OBSERVADO.** Tres pares con los 5 hashes de adjunto idénticos y diferencia
sólo en el formulario estructurado:

- **Molinos Río de la Plata 2023-06-30**: `Receivables` y
  `OtrosActivosNoFinancierosCorrientes` tienen **los mismos dos números
  permutados** (1.522.570.000 ↔ 21.492.423.000). El activo total no cambia.
- **Distribuidora de Gas Cuyana 2020-12-31**: `IncomeTax` pasa de nil declarado a
  109.110.000. Un campo omitido que después se completa.
- **Fiplasto 2025-06-30**: `ResultadoIntegral` cambia −0,88 % pero el EPS cambia
  −58,9 % (−15,75 → −6,47). Cambió el denominador, no el resultado.

**INFERENCIA:** son correcciones de carga del formulario, no hechos económicos
nuevos. El PDF firmado es bit a bit el mismo.

### 7.4 `G_CAMBIO_SIN_EVIDENCIA_SUFICIENTE`

**Garovaglio y Zorraquín 2022-06-30**, 10 conceptos, adjuntos 0/6 iguales,
ordinales 2941809 → 2942341. `RECPAM` +454 %, `IngresosFinancieros` +205 %,
`InterestExpense` +153 %, con `NetIncome` y `ResultadoIntegral` **bajando** 22 %.

**INFERENCIA (no hecho):** el patrón —resultados financieros que crecen mucho y
resultado neto que baja— es compatible con una corrección del ajuste por inflación
IAS 29. **No hay evidencia suficiente para afirmarlo.** No se dispone de fecha de
publicación ni de nota que lo declare. Se deja explícitamente **NO DIRIMIDO**.

---

## 8. Casos relevantes (TABLA OBLIGATORIA 2)

| emisor | período | `TipoBalance` | conceptos ≠ | adj. iguales | Δ ordinal | categoría | en producción |
|---|---|---|---:|---|---:|---|---|
| Longvie | 2019-03-31 | INDIVIDUAL | 62 | 1/5 | 7 | `E_ENTIDAD_DISTINTA` | **sí, ambos** |
| Longvie | 2018-12-31 | INDIVIDUAL | 61 | 0/5 | 49 | `E_ENTIDAD_DISTINTA` | **sí, ambos** |
| Cia Introductora de Bs As | 2021-12-31 | CONSOLIDADO | 61 | 3/5 | 5 | `D_PERIMETRO_DISTINTO` | **sí, ambos** |
| Bolsas y Mercados Argentinos | 2021-12-31 | CONSOLIDADO | 59 | 4/5 | 19 | `D_PERIMETRO_DISTINTO` | **sí, ambos** |
| Longvie | 2020-12-31 | INDIVIDUAL | 59 | 0/5 | 35 | `E_ENTIDAD_DISTINTA` | **sí, ambos** |
| Aeropuertos Argentina 2000 | 2019-12-31 | CONSOLIDADO | 52 | 0/5 | 1 | `D_PERIMETRO_DISTINTO` | **sí, ambos** |
| Garovaglio y Zorraquín | 2022-06-30 | CONSOLIDADO | 10 | 0/6 | 532 | `G_SIN_EVIDENCIA` | no |
| Fiplasto | 2025-06-30 | CONSOLIDADO | 3 | 5/5 | 12.213 | `F_CORRECCION` | **sí, ambos** |
| Molinos Río de la Plata | 2023-06-30 | CONSOLIDADO | 2 | 5/5 | 109 | `F_CORRECCION` | no |
| Distribuidora de Gas Cuyana | 2020-12-31 | INDIVIDUAL | 1 | 5/5 | 422 | `F_CORRECCION` | no |

---

## 9. Por qué ningún caso se declara `RESTATEMENT_CONFIRMADO`

La regla del sprint es explícita: un valor distinto no basta. Para afirmar
restatement haría falta que el emisor declarara que reexpresa un período ya
publicado. La CNV **no publica fecha de publicación** de la presentación (§15) y el
formulario estructurado no tiene campo de reexpresión ni de motivo.

De los 370: 354 se explican por perímetro o entidad (no son el mismo hecho
económico), 6 por corrección de carga con PDF idéntico, y 10 quedan
`NO DIRIMIDO`. **Cero restatements confirmados.**

---

## 10. Perímetro (PASO 7)

| señal de perímetro en los adjuntos | pares | grupos |
|---|---:|---:|
| ambos consolidados | 20 | 1.517 |
| ambos separados/individuales | 3 | 228 |
| **A consolidado / B separado** | **2** | **152** |
| **B consolidado / A separado** | **1** | **76** |
| sin señal legible en el nombre del adjunto | 29 | 2.129 |

**HECHO OBSERVADO:** el perímetro real sólo es recuperable del **nombre de archivo
del adjunto**, que es texto libre escrito por el emisor. En 29 de 55 pares no hay
señal alguna. El campo estructurado `TipoBalance` existe una sola vez por documento
y en los 3 pares críticos declara lo mismo en ambos lados.

**SOFTWARE GAP:** `job5.tipo_balance()` lee la primera ocurrencia de
`claveinformativa="TipoBalance"`. Se verificó que hay exactamente una por documento,
así que la función no tiene bug: **el dato de origen es insuficiente.**

---

## 11. Período (PASO 8)

`period_end` forma parte de la clave de agrupamiento, así que por construcción no
puede diferir dentro de un grupo. Lo que sí se verificó:

- `PeriodoBalance` difiere en **0** de 4.102 grupos (valores observados: `1` anual,
  `3` trimestral).
- `tipo` (A/P) difiere en **0**.
- La CNV acumula YTD: todo hecho DURATION arranca el 1 de enero, de modo que
  `period_start` es función de `period_end` y `PeriodoBalance` y no aporta
  discriminación independiente.

**No se observó ningún caso de mismo `period_end` con `period_start` distinto.**
Estado: **NO DIRIMIDO** — no hay contraejemplo en el corpus, pero tampoco prueba
positiva de que no pueda existir.

---

## 12. Unidad y escala (PASO 9)

`unidad_factor` difiere en **0** de 4.102 grupos. El corpus contiene tres escalas
(`1`: 2.652 grupos, `1000`: 1.298, `1000000`: 152) y cuatro literales de unidad
(`$`, `Miles de $`, `MILES DE $`, …), pero **nunca dos escalas distintas para la
misma clave económica**. `moneda` es constante (`7` = ARS) en los 4.102.

**Estado: NO DIRIMIDO.** El corpus no ofrece ningún caso donde el mismo hecho se
exprese en dos escalas, así que **no permite decidir** si la escala es propiedad
económica o de presentación. Lo único demostrado es que **no discrimina
ocurrencias**: incluirla en `econ_key` no separaría ninguna colisión actual.

---

## 13. `es_nil` (PASO 10)

**HECHO OBSERVADO:** 60 grupos con `es_nil` distinto. En **los 60**, el `valor`
también difiere. **Cero casos de mismo valor con `es_nil` distinto.**

Los 60 caen íntegramente dentro de los 10 pares de §7 —Longvie 45, CIBA 5, AA2000 5,
BYMA 4, Cuyana 1—, es decir dentro de los pares donde el perímetro o la entidad ya
son distintos. Ejemplo: `InteresesNoControlantes`, nil en el separado y 8.952.968 en
el consolidado, que es precisamente lo esperado.

**INFERENCIA:** `es_nil` no es un discriminante independiente. Es parte del **valor
aseverado**, no de la identidad: un documento que dice «guion» y otro que dice
8.952.968 están aseverando cosas distintas sobre el mismo hecho, exactamente como
dos valores numéricos distintos.

**RECOMENDACIÓN:** `es_nil` **NO** debe entrar en `econ_key`. Ponerlo ahí convertiría
dos aseveraciones sobre un hecho en dos hechos, que es el error simétrico al que
este sprint investiga. Confianza: ALTA (los 60 casos tienen causa identificada).

---

## 14. `measurement_date` / reexpresión (PASO 11)

En la transformación actual `fecha_reexpresion` se fija igual a `period_end`, así
que no discrimina: es una función de otra columna de la clave.

Bajo IAS 29 cada cifra está en poder adquisitivo de la fecha de cierre del
documento, de modo que dos documentos del **mismo** cierre comparten
`measurement_date` por definición. Eso es coherente con lo observado.

**Estado: NO DIRIMIDO.** El caso que lo pondría a prueba —el mismo `period_end`
reexpresado a dos fechas de medición distintas— es exactamente el caso comparativo
(la columna del ejercicio anterior dentro de un EEFF), que **esta extracción no
persiste** como hecho independiente. Sin ese dato el corpus no puede dirimirlo.

---

## 15. Orden documental vs orden temporal (PASO 14)

**HECHO OBSERVADO.** Lo único disponible para ordenar es el **ordinal de
presentación** (`Presentación #NNNNNNN`), legible en 55/55 pares. Δ entre pares:
mínimo 1, mediana 1.793, máximo 330.410.

**La CNV no publica fecha de publicación de la presentación.** No hay ningún campo
temporal en el documento que ordene dos presentaciones.

**Por lo tanto:**
- `ORDEN_DOCUMENTAL` = ordinal de presentación. **Disponible y total.**
- `ORDEN_TEMPORAL` = **NO DISPONIBLE.**

**INFERENCIA:** el ordinal es monótono con el tiempo de carga (Δ=1 en AA2000 entre
consolidado e individual del mismo cierre indica carga consecutiva). Pero es un
contador de la plataforma, no un sello de tiempo.

**RECOMENDACIÓN — no afirmar supersesión.** Un ordinal mayor **no** prueba que un
documento supersede a otro. Los casos de §7.1 lo demuestran: en BYMA el ordinal
mayor es el separado y en CIBA es el consolidado. Si se ordenara por ordinal y se
tomara «el último», se elegiría el consolidado en un emisor y el separado en el
otro. Cualquier mecanismo de supersesión debe construirse sobre orden documental
**explícitamente declarado como tal**, y nunca sobre la suposición de que ordena
en el tiempo.

---

## 16. Matriz de atributos de `econ_key` (PASO 12)

Un atributo sólo puede justificarse en `econ_key` si separa ocurrencias que hoy
colisionan y que **no deberían** colisionar.

| atributo | ¿en `econ_key`? | separa | estado | fundamento |
|---|---|---:|---|---|
| `entity_id` (emisor) | **sí** | — | **DEMOSTRADO** | sin él no hay identidad |
| `qname` / concepto | **sí** | — | **DEMOSTRADO** | idem |
| `period_end` | **sí** | — | **DEMOSTRADO** | idem |
| `period_kind` / `PeriodoBalance` | sí | 0/4.102 | **NO DIRIMIDO** | constante en las colisiones |
| `period_start` | sí | 0 | **NO DIRIMIDO** | función de `period_end`+`PeriodoBalance` (YTD) |
| **`perimetro`** | **sí** | **228/4.102** | **DEMOSTRADO NECESARIO, NO COMPUTABLE** | §7.1: el campo declarado no lo distingue |
| **entidad informante** | **sí** | **182/4.102** | **DEMOSTRADO NECESARIO, AUSENTE** | §7.2: no existe campo alguno |
| `unit_measure` / `moneda` | sí | 0 | **NO DIRIMIDO** | constante |
| escala (`unidad_factor`) | ? | 0 | **NO DIRIMIDO** | §12 |
| `measurement_date` | sí | 0 | **NO DIRIMIDO** | §14 |
| `es_nil` | **no** | 0 independientes | **DEMOSTRADO** | §13: es valor, no identidad |
| `valor` | **no** | — | **DEMOSTRADO** | es lo aseverado |
| **`accn`** | **no** | 4.102 | **SOPORTADO** | ver abajo |
| `sha256_documento` | no | 4.102 | **SOPORTADO** | idem `accn` |
| `ordinal_presentacion` | no | 4.102 | **SOPORTADO** | §15 |

### El hallazgo que rompe el diseño

**HECHO OBSERVADO:** de todos los atributos estructurados disponibles en el
formulario CNV —`unidad_factor`, `unidad_medida`, `moneda`, `tipo`,
`PeriodoBalance`— **ninguno separa una sola de las 4.102 colisiones.** Los dos
atributos que la evidencia demuestra necesarios —perímetro real y entidad
informante— **no son computables desde el formulario**: el primero está mal
declarado en los casos críticos, el segundo no existe.

**`econ_key` para CNV no puede computarse de forma correcta y completa a partir de
los campos estructurados que hoy se extraen.** Esto no invalida `econ_key` como
concepto; invalida la clave concreta
`(cuit, concepto, period_end, fecha_reexpresion, tipo_balance)` que se está usando.

### Sobre `accn ∉ econ_key`

El sprint pedía intentar romperlo. **No se rompió, pero tampoco se confirmó.**
Los 4.102 grupos donde `accn` difiere se explican todos por otra causa
(republicación, perímetro, entidad, corrección). No apareció ningún caso donde
`accn` fuera *en sí mismo* el discriminante económico.

Pero eso es precisamente lo que no se puede verificar mientras el perímetro y la
entidad no sean computables: hoy `accn` es el **único proxy disponible** de esas
dos dimensiones. Estado: **SOPORTADO**, no `DEMOSTRADO`.

---

## 17. Impacto en producción (HECHO OBSERVADO)

`screener.db`, tabla `cnv_estados_v2`, PK
`(cuit, concepto, period_end, fecha_reexpresion, tipo_balance)`: 102.323 filas,
**cero duplicados** bajo esa clave.

De los 55 pares colisionados, **7 tienen ambos documentos presentes en producción**.
Los 7 son exactamente los de diferencia económica. Los 48 pares inocuos
(republicaciones) tienen un solo documento cargado y no producen daño.

### 17.1 Longvie 2019-03-31 INDIVIDUAL — se publica la filial colombiana

```
produccion  Assets  INDIVIDUAL   =     19.728.694   (doc ae6025b3 = EEFF COLOMBIA)
raw         Assets  Longvie SA   =  1.277.448.945   (doc e0caf38b = Individual)
```

**36 de los conceptos de Longvie INDIVIDUAL 2019-03-31 en producción provienen del
documento de la filial colombiana** —una sociedad de 3 empleados, 64 veces más
chica—, incluidos `Assets`, `AssetsCurrent`, `Capital`, `COGS`, `CF_Operativo` y
siete ratios `CNV_*` derivados de ellos (`CNV_roe` = 0,37, `CNV_solvencia` = −0,24).

El registro se armó con **tres** documentos distintos; ganó el que llegó primero al
`INSERT OR IGNORE`.

### 17.2 BYMA 2021-12-31 CONSOLIDADO — el balance no cierra

45 de 46 conceptos vienen del documento **separado**; uno,
`LiabilitiesNonCurrent`, del **consolidado**:

```
LiabilitiesCurrent      27.772.795.821   (separado)
LiabilitiesNonCurrent      301.665.607   (consolidado)   <-- otro perímetro
                        --------------
suma                    28.074.461.428
Liabilities             27.772.795.821   (separado)
desvío                          +1,1 %
```

**La identidad contable se rompe** porque un renglón viene de otro perímetro.

**Aclaración honesta:** en los otros seis casos la identidad contable **sí cierra**,
porque la abrumadora mayoría de los conceptos vino de un único documento. El daño
es real pero no uniforme: no es «producción está rota», es «producción contiene
registros compuestos por documentos de perímetros y entidades distintos, y en al
menos un caso eso rompe la aritmética, y en al menos otro publica la entidad
equivocada».

---

## 18. Corrección a W-1.3A

W-1.3A concluyó, sobre METROGAS, «152 filas colapsadas, 100 % republicación, cero
diferencias económicas». Hay que matizar dos cosas:

1. **METROGAS tiene 0 colisiones dentro de la selección de producción.** De los 4
   documentos que producían las 152, sólo `a6e3351d` y `24a37877` están en
   `whitelist_eeff_codigos.csv` (48 filas cada uno en `screener.db`); `47eb2075` y
   `5b4d69bf` sólo están en la lista amplia y tienen **0 filas** en producción. Las
   152 provenían de documentos fuera de producción.
2. **La generalización no se sostiene.** METR es un emisor sin estados separados
   diferenciados en el corpus y sin filiales presentadas bajo su CUIT. Es el mejor
   caso posible, no el caso típico.

W-1.3A no está mal en sus números; está mal en su alcance. Este sprint existe
porque esa distinción importaba.

---

## 19. HECHOS OBSERVADOS (resumen, sin interpretación)

1. 24 emisores, 879 documentos, 66.240 ocurrencias, 4.102 grupos colisionados, todos de tamaño 2, producidos por 55 pares de documentos.
2. 370 grupos tienen `valor` distinto; 60 tienen `es_nil` distinto y en los 60 el valor también difiere.
3. `unidad_factor`, `unidad_medida`, `moneda`, `tipo` y `PeriodoBalance` difieren en 0 de 4.102 grupos.
4. `accn`, `sha256_documento` y `ordinal_presentacion` difieren en 4.102 de 4.102.
5. Tres pares declaran el mismo `TipoBalance` mientras sus adjuntos declaran consolidado y separado respectivamente.
6. En BYMA 2021-12-31 la diferencia de patrimonio entre los dos documentos es exactamente el valor de `InteresesNoControlantes`.
7. Tres pares de Longvie tienen `ODCCantidadEmpleados` de 655/3, 681/3 y 2/630, y adjuntos que nombran «COLOMBIA» y «L SAS».
8. El CUIT interno del documento coincide con el de la whitelist en 20/20 casos verificados.
9. Cada documento contiene exactamente una ocurrencia de `claveinformativa="TipoBalance"`.
10. En Molinos, dos conceptos intercambian exactamente los mismos dos valores, con los 5 hashes de adjunto idénticos.
11. Sólo 4 de 55 pares (280 grupos) tienen los adjuntos completamente idénticos.
12. La CNV no publica fecha de publicación; el ordinal es el único ordenador.
13. En producción, 7 de 55 pares tienen ambos documentos; son los 7 de diferencia económica.
14. En producción, `LiabilitiesCurrent + LiabilitiesNonCurrent` de BYMA 2021-12-31 excede `Liabilities` en 1,1 %.
15. En producción, 36 conceptos de Longvie INDIVIDUAL 2019-03-31 provienen del documento de la filial colombiana.

## 20. INFERENCIAS (no son hechos)

1. Los pares de §7.1 son consolidado y separado del mismo cierre — muy alta confianza (nombre de adjunto + aritmética de NCI).
2. Los pares de §7.2 son entidades informantes distintas — muy alta confianza (empleados + nombre de adjunto).
3. Los tres casos de §7.3 son correcciones de carga del formulario — alta confianza (PDF idéntico).
4. Garovaglio podría ser una corrección del ajuste IAS 29 — **NO DIRIMIDO**, se declara así.
5. El ordinal es monótono con el tiempo de carga — plausible, no verificable.
6. Los 29 pares «sin señal de perímetro» probablemente contienen más casos como §7.1 que la heurística del nombre de archivo no detecta — no verificado.

## 21. RECOMENDACIONES DE DISEÑO (PASO 13)

Ninguna se implementa en este sprint.

1. **`cnv_estados_norm` debe ser ocurrencias normalizadas, no identidad económica.**
   Mientras el perímetro y la entidad no sean computables, colapsar por identidad
   económica **destruye hechos reales y conserva uno arbitrario**. Retener `accn`
   como discriminante en `norm` es hoy la única forma de no perder datos.
2. **No promover `econ_key` a CNV todavía.** La clave actual está demostrada
   incorrecta. Promoverla congelaría el defecto de §17 en el esquema canónico.
3. **Extraer `perimetro_declarado` y `perimetro_evidenciado` por separado**, el
   segundo derivado del nombre del adjunto, y marcar los 29 pares sin señal como
   `PERIMETRO_INDETERMINADO`. Un dato marcado como indeterminado es honesto; uno
   inventado no.
4. **Introducir `entidad_informante` distinta de `cuit_presentante`**, aunque en la
   mayoría de los documentos coincidan. Sin esa separación, el caso Longvie no tiene
   representación posible.
5. **No construir supersesión sobre el ordinal** (§15).
6. **`es_nil` y `valor` fuera de `econ_key`**; van del lado de la aseveración.
7. **Guard de coherencia contable en la publicación**: `AC+ANC=A`, `LC+LNC=L`,
   `A=L+PN`. Habría detectado BYMA sin necesidad de esta auditoría.
8. **Registrar el defecto de producción de §17 como ticket propio.** Está fuera del
   alcance de este sprint y **no se corrigió**.

## 22. Criterios de éxito

| # | pregunta | respuesta |
|---|---|---|
| 1 | ¿≥5 emisores? | 24 — la población completa con colisiones |
| 2 | ¿la selección evita sesgo? | sí: no es muestra, es censo |
| 3 | ¿se reprodujo el censo? | sí, 4.102 grupos, determinista |
| 4 | ¿todos los grupos son pares? | sí, máximo 2 — igual que METR |
| 5 | ¿`accn` = ocurrencia? | **DEMOSTRADO** |
| 6 | ¿`accn` ∉ `econ_key`? | **SOPORTADO**, no demostrado (§16) |
| 7 | ¿grupos = excedentes descartables? | **NO** — 370 no lo son |
| 8 | ¿hay restatements confirmados? | **no**, cero (§9) |
| 9 | ¿hay cambio de perímetro? | **sí**, 228 grupos, 3 pares |
| 10 | ¿hay cambio de entidad? | **sí**, 182 grupos, 3 pares |
| 11 | ¿la escala discrimina? | no, 0/4.102 — **NO DIRIMIDO** |
| 12 | ¿`es_nil` discrimina? | no independientemente — fuera de `econ_key` |
| 13 | ¿`measurement_date` discrimina? | 0/4.102 — **NO DIRIMIDO** |
| 14 | ¿hay orden temporal? | **NO DISPONIBLE**; sólo documental |
| 15 | ¿se rompió el modelo? | **sí, la clave económica**; el rol de `accn` no |

---

### Artefactos

| archivo | contenido |
|---|---|
| `W13A2_CORPUS_SURVEY.csv` | 71 emisores relevados, 24 con colisiones |
| `W13A2_ISSUER_CENSUS.csv` | censo por emisor |
| `W13A2_MULTIISSUER_GROUPS.csv` | los 4.102 grupos, columna por columna |
| `W13A2_VALOR_DISTINTO_EVIDENCIA.csv` | los 10 pares con diferencia económica, con evidencia |
| `W13A2_PARES_DOCUMENTALES.csv` | los 55 pares: subcategoría, perímetro, ordinales |

Scripts (worktree `catalaxia-cnvmig`, sólo lectura):
`scripts/engine/ca_w13a2_survey.py`, `scripts/engine/ca_w13a2_multiissuer_audit.py`.
