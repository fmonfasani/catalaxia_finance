# CNV W-1.3 — BASELINE EMPÍRICO DE IDENTIDAD ECONÓMICA

**Fecha:** 2026-09-02
**Alcance:** medición previa a cualquier cambio de esquema o adaptador.
**Corpus:** Nivel 1 — METR, 2.697 hechos / 56 documentos · Nivel 2 — 72 empresas,
2.453 documentos, 106.421 filas.
**Estado:** ningún archivo de producción modificado al escribir este informe.

---

## 1 · Colisiones de `econ_key` (§3.1)

Fórmula evaluada, con serialización `entity_id|qname|perímetro|period_kind|start_date|end_date|unit_measure|measurement_date`, NULL → cadena vacía, UTF-8:

| | |
|---|--:|
| total facts CNV | **2.697** |
| `econ_key` únicas | **2.697** |
| `econ_key` con multiplicidad > 1 | **0** |
| multiplicidad máxima | **1** |

**No hay ninguna colisión que ocultar: no hay ninguna.**

Pero el número por sí solo engaña, y lo que sigue es lo que importa.

### 1.1 · Cuánto aporta cada componente

Quitando un componente por vez y contando claves distintas sobre los mismos
2.697 hechos:

| `econ_key` | claves | colisiones que aparecen |
|---|--:|--:|
| completa | 2.697 | 0 |
| sin `measurement_date` | 2.697 | **0** |
| sin `start_date` | 2.697 | **0** |
| sin `unit_measure` | 2.697 | **0** |
| sin `perímetro` | 1.398 | **1.299** |

**Cuatro de los ocho componentes no discriminan nada en este corpus.** Solo
`perímetro` hace trabajo medible más allá de `(entity_id, qname, end_date)`.

Eso **no** los vuelve incorrectos —W-1.2 demostró que sin `start_date` el
trimestre y el ejercicio colapsan, y W-1.1 encontró 580 grupos SEC donde la
unidad separa dos hechos— pero sí significa que **en CNV esos invariantes están
sin ejercitar**. Son protecciones contra casos que este corpus no contiene.

### 1.2 · `measurement_date` está funcionalmente determinada

```
measurement_date = coalesce(end_date, instant_date)   ->   2.697 de 2.697
29 fechas de medición distintas · 29 fines de período distintos
```

Es una consecuencia estructural, no una casualidad: cada documento CNV aporta un
solo período, y `measurement_date` sale de la `FechaCierre` de ese documento.

**Consecuencia que hay que decir:** mientras el comparativo no se ingeste, dos
publicaciones del mismo período tendrían `measurement_date` distintas y por lo
tanto `econ_key` distintas. **La republicación y el restatement son
estructuralmente invisibles para `econ_key` en CNV hoy.**

---

## 2 · Contradicción encontrada — el corpus no puede responder §6 y §7

### El hallazgo

`cnv_estados_v2`, la tabla de la que deriva `cnv_estados_norm`:

```sql
PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
```

insertada con **`INSERT OR IGNORE`**. Y `fecha_reexpresion = period_end` en el
**100 % de las 106.421 filas** (medido en `CNV_W1_W2_SEMANTIC_REPORT` §1.0).

La clave efectiva es, entonces, `(cuit, concepto, period_end, tipo_balance)`.

> **Si la misma identidad económica aparece en dos documentos, el segundo se
> descarta en silencio al ingestar.**

### Por qué importa

Los ciclos anteriores midieron "0 identidades económicas en más de un
documento" y lo interpretaron como *no hay republicación en CNV*. La medición
era correcta; **la interpretación era demasiado fuerte**. Ese cero es, en parte,
el efecto de la propia clave primaria.

### Cuánto se perdió

Reconstruyendo desde el RAW los 51 conceptos conocidos de cada documento y
comparando contra lo atribuido a ese `accn` en la tabla:

| | |
|---|--:|
| documentos con RAW | 2.364 de 2.453 |
| conceptos conocidos presentes en el RAW | 103.268 |
| filas atribuidas en `cnv_estados_norm` | 102.976 |
| **descartadas por el `INSERT OR IGNORE`** | **292** en **7 documentos** |
| pérdida relativa | **0,3 %** |

La pérdida es real, está acotada y es **recuperable**: los 7 documentos están en
disco.

---

## 3 · Los 7 casos, reconstruidos desde el RAW (§6)

Son las únicas tripletas `(cuit, período, perímetro)` con dos documentos en todo
el corpus.

| emisor | período | perímetro | comunes | idénticos | distintos |
|---|---|---|--:|--:|--:|
| LONG | 2018-12-31 | INDIVIDUAL | 36 | 0 | 36 |
| LONG | 2019-03-31 | INDIVIDUAL | 36 | 0 | 36 |
| LONG | 2020-12-31 | INDIVIDUAL | 36 | 0 | 36 |
| INTR | 2021-12-31 | CONSOLIDADO | 46 | 4 | 42 |
| **FIPL** | 2025-06-30 | CONSOLIDADO | 48 | **45** | **3** |
| _ADR_0580 | 2019-12-31 | CONSOLIDADO | 46 | 12 | 34 |
| BYMA | 2021-12-31 | CONSOLIDADO | 45 | 5 | 40 |
| **TOTAL** | | | **292** | **66** | **226** |

### 3.1 · Los 226 "distintos" NO son restatements

Las magnitudes lo desmienten solas: `PPE` **+14.305,9 %**, `Inventory`
**−99,2 %**, `PPE` **−100,0 %**. Ningún restatement contable se ve así.

**Demostración sobre BYMA 2021-12-31 CONSOLIDADO.** La serie de `PPE`
consolidado del emisor:

```
2021-09-30   1.481.185.590
2021-12-31      11.060.815    <- el valor del documento que SÍ entró
2022-03-31   1.835.280.221
```

El documento descartado trae **1.593.406.319**, que es exactamente el valor que
la serie exige. Y la serie INDIVIDUAL de BYMA se mueve en el orden de los 11-12
millones: **11.060.815 es la cifra individual**.

Los dos documentos declaran `TipoBalance = Consolidado`, una sola vez cada uno, y
ambos declaran la misma `FechaCierre` y la misma `UnidadMedida`. El texto se
parsea limpio en los dos:

```
A:  1110100 PROPIEDADES PLANTAS Y EQUIPOS    11060815.00
B:  1110100 PROPIEDADES PLANTAS Y EQUIPOS  1593406319.00
```

**No es un restatement: es un perímetro mal declarado en origen.** Y el
`INSERT OR IGNORE` conservó el documento equivocado, porque llegó primero.

### 3.2 · Clasificación de los 7, sin forzar ninguno

| clase | casos | fundamento |
|---|---|---|
| **D · error del modelo/origen** | LONG ×3, INTR, BYMA | diferencias del 50 % al 14.000 %; en BYMA está probado que es confusión de perímetro |
| **A/B · republicación o corrección, indistinguibles** | FIPL, _ADR_0580 | FIPL: 45 de 48 idénticos, 3 distintos (`ResultadoIntegral` +0,9 %, EPS −6,47 → −15,75). _ADR_0580: diferencias de 0,1 % a 5,9 % |
| **C · conflicto verdadero** | 0 | ninguno demostrable |

**Ningún caso se clasifica automáticamente como restatement.** Dos son
compatibles con una corrección, y ninguno de los dos trae evidencia que permita
afirmarlo frente a la alternativa de que sean dos declaraciones con distinto
alcance.

> METR **no está entre los 7**. Sus 56 documentos tienen `(período, perímetro)`
> únicos. Los datos migrados en W-1.2 no están afectados.

---

## 4 · IAS 29 / re-expresión (§7)

Evidencia buscada, evidencia encontrada:

| señal | resultado |
|---|---|
| `fecha_reexpresion` ≠ `period_end` | **0 de 106.421** |
| `valor_comparativo` poblado | **0 filas** |
| períodos por documento | **1** en los 2.453 |
| `measurement_date` ≠ fin de período | **0 de 2.697** |

**No existe un solo caso de re-expresión observable en el corpus.** No porque no
ocurra —la CNV re-expresa por norma— sino porque el comparativo nunca se
extrae y el campo que lo registraría está vacío.

```
IAS29 = OPEN: requires publication/re-expression evidence
```

---

## 5 · `qname` vs concepto canónico (§5)

Los 51 conceptos CNV son un conjunto cerrado, cada uno con su código de plan de
cuentas. Busqué alias empíricamente: pares de conceptos que valgan lo mismo en
más del 90 % de las observaciones (mínimo 50 observaciones).

| par | coincidencia | ¿es alias? |
|---|--:|---|
| `EPS_basico` = `EPS_diluido` | 1767/1841 (96,0 %) | **no** — coinciden cuando no hay instrumentos dilutivos. Es economía, no sinonimia |
| `EBIT` = `OperatingIncome` | 885/1797 (49,2 %) | **no** — coinciden cuando no hay resultados no operativos entre ambos. En METR 56/56, en el corpus la mitad |
| `NetIncome` = `ResultadoIntegral` | 913/2336 (39,1 %) | no |
| `EBITDA` = `EBIT` | 130/1931 (6,7 %) | no |

Ningún otro par supera el 50 %.

```
QNAME_IDENTITY_FINDINGS = PASS
```

`qname` es suficiente para la identidad económica **dentro de CNV**: no hay dos
conceptos distintos que representen la misma realidad. **No se introduce una
taxonomía canónica porque el corpus no la justifica.**

*Límite declarado:* esto vale para CNV. El problema de multi-tag sí existe en
SEC —KO usa 18 `qname` en la familia EPS, `W1_1_FACT_IDENTITY_CONTRACT` §C9— y
sigue abierto ahí.

---

## 6 · Fecha de publicación (§8) — corrección de un cierre anterior

`CNV_SEMANTIC_IMPLEMENTATION_REPORT` §14 R-3 y `W1_1_FACT_IDENTITY_CONTRACT`
§O1 concluyeron que el orden de las ocurrencias CNV requería un fetch. **Eso era
demasiado pesimista.**

### Lo que existe localmente

| fuente | contenido | cobertura |
|---|---|--:|
| `derived.fact.filing_date` | — | **0 de 2.697** |
| `fetch_raw.cnv_presentation.fecha_publicacion` | fecha real | 82.493 filas · **3 de 72 CUITs** |
| **título del RAW: `Presentación #N`** | **ordinal** | **2.364 de 2.364 documentos** |

### El ordinal, validado

`presentation_id` y `fecha_publicacion` conviven en `fetch_raw.cnv_presentation`
para 3 CUITs. Ordenando **numéricamente** por el ordinal y observando la fecha:

| | |
|---|--:|
| pares `(presentation_id, fecha)` | 9.167 |
| rango | #1103 (2000-06-20) … #3564242 (2026-08-31) |
| **inversiones** | **112 (1,22 %)** |
| magnitud de cada inversión | 1 a 2 días |

Las inversiones son de un día o dos, compatibles con que el número se asigne al
crear el trámite y la fecha al publicarlo.

**Conclusión:** el orden de publicación **sí es reconstruible localmente y sin
red**, con un ordinal presente en el 100 % de los documentos. La *fecha* solo
existe para 3 de 72 CUITs.

```
ORDEN DE OCURRENCIAS   = DISPONIBLE (ordinal, 2.364/2.364, 1,22 % de inversiones)
FECHA DE PUBLICACIÓN   = PARCIAL (3 de 72 CUITs)
```

---

## 7 · Qué habilita y qué no habilita este baseline

| | |
|---|---|
| `econ_key` implementable | **sí** — 0 colisiones, serialización determinista |
| Q4/FY, unidades, perímetro, medición separados | **sí**, por construcción |
| ordenar ocurrencias | **sí** — ordinal validado |
| distinguir republicación de restatement | **no** — los 2 casos candidatos no traen evidencia suficiente |
| detectar re-expresión IAS 29 | **no** — 0 casos observables |
| `supersedes` automático | **no** — falta el discriminante semántico, no el orden |
| `effective_from/to` | **no** — ver informe de implementación §11 |

---

## 8 · Riesgos que este baseline deja a la vista

**B-1 · La clave primaria del origen destruye evidencia.** 292 filas en 7
documentos. Es 0,3 %, pero es exactamente la evidencia que W-1.3 necesitaba.
Corregirlo es un cambio en `job5_v2_extract_eeff.py`, fuera del alcance de este
ciclo.

**B-2 · `tipo_balance` no es confiable en el 100 % de los casos.** Probado en
BYMA 2021-12-31: dos documentos declaran `Consolidado` y uno trae cifras
individuales. W-1.2 tomó el perímetro como dimensión de primera clase; sigue
siendo lo correcto, pero **la etiqueta de origen tiene errores**. METR no está
afectado.

**B-3 · Un valor incorrecto está en la tabla para BYMA 2021-12-31 CONSOLIDADO**
(`PPE = 11.060.815` donde la serie exige ~1.593 M). No es un dato migrado —BYMA
no se migró— pero está en `cnv_estados_norm` y cualquier consumidor lo leería.

**B-4 · Cuatro de los ocho componentes de `econ_key` están sin ejercitar** en
CNV. Sus invariantes se sostienen en fixtures sintéticos y en el corpus SEC, no
en datos CNV reales.
