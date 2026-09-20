# CNV CANONICAL IDENTITY GATE

**2026-09-02** · solo lectura · **sin migraciones, sin fetch, sin RAW nuevo, sin escrituras**
Todos los experimentos con `BEGIN … ROLLBACK` sobre schema temporal.

---

# GATE = **PASS_WITH_WARNINGS**

Los tres UNKNOWN quedan **resueltos**. Dos con resultado mejor de lo esperado, uno
peor — y ese tercero **refuta una recomendación que yo mismo había dado**.

| UNKNOWN | resultado |
|---|---|
| **1 · colisión de `context_id`** | **RESUELTO — colisión estructuralmente imposible** |
| **2 · determinismo de la extracción** | **RESUELTO CON ADVERTENCIA — las claves sí, la escala no** |
| **3 · semántica de NULL en F-061** | **RESUELTO — y refuta la recomendación previa** |

---

## HECHOS · 1 · Colisión de `context_id`

### Evidencia — universo CNV completo, 106.421 filas

```
clave (accn, concepto, tipo_balance, period_end)
  filas ................. 106.421
  claves distintas ...... 106.421
  COLISIONES ............        0

tupla completa del fact_key simulada
  ('CUIT:'||cuit | accn | 'cnv:'||concepto | tipo_balance@period_end | escala)
  filas ................. 106.421
  fact_keys distintas ... 106.421
  COLISIONES ............        0
```

### Y la razón por la que no es casualidad

```
GUIDs que reportan MÁS DE UN period_end ....... 0 de 2.453
GUIDs que traen LOS DOS perímetros ............ 0
```

**Cada documento CNV cubre exactamente un período y exactamente un perímetro.**
Como el GUID ya está en el `fact_key` (ocupa el lugar del `accession_number`),
**la colisión es estructuralmente imposible**: dos hechos con el mismo
`context_id` sintético sólo pueden venir de documentos distintos, y el documento
está en la clave.

**Inferencia:** el `context_id` sintético `{tipo_balance}@{period_end}` es, para
CNV, **redundante con el GUID**. Incluirlo no agrega poder discriminante — agrega
legibilidad. Es correcto conservarlo, pero no es lo que evita la colisión.

**Colisiones semánticas: 0. Colisiones legítimas: 0. Colisiones totales: 0.**

---

## HECHOS · 2 · Determinismo de la extracción

### El experimento disponible

`job5_v2` no se puede ejecutar dos veces sin generar RAW ni tocar la base. Pero
**existe una segunda extracción ya materializada**: `cnv_reextract`, 65.560 filas
sobre 72 CUIT, producida por una pasada independiente sobre el mismo RAW.

**Salvedad metodológica explícita:** esto compara **dos implementaciones
distintas** (`job5_v2 → s0` contra el reextractor), no dos corridas de la misma.
Es una prueba **más exigente** en cuanto a acuerdo, y **más débil** como respuesta
a «¿`job5_v2` es determinista consigo mismo?». Eso último queda **UNKNOWN
parcial** — ver riesgos.

### Evidencia

```
filas en cnv_reextract ......... 65.560
con par en cnv_estados_norm .... 45.844
VALOR IDÉNTICO ................. 44.645   (97,38 %)
valor distinto .................  1.199   ( 2,62 %)
```

Las claves se emparejaron normalizando mayúsculas y separadores: `assets`↔`Assets`,
`consolidado`↔`CONSOLIDADO`. **Las 45.844 coincidencias de clave demuestran que
`(cuit, concepto, período, perímetro)` es reproducible entre implementaciones.**

### Clasificación de las 1.199 diferencias

| naturaleza | casos | % |
|---|---:|---:|
| factor **/1e6** | 593 | 49,5 % |
| factor **x1e3** | 233 | 19,4 % |
| factor **/1e3** | 129 | 10,8 % |
| factor **/1e9** | 127 | 10,6 % |
| **subtotal escala** | **1.082** | **90,2 %** |
| no es escala | 117 | 9,8 % |

De los 117 restantes, la mayoría tiene ratio **1,0000 o 0,9999** (precisión de
redondeo). Uno solo es una diferencia real de valor (`equity`, ratio 0,3914).

Ejemplos verbatim:

```
30501250305 debtcurrent 2020-08-31 consolidado   norm=7.080,0        reext=7.083.862.000   ratio=1e-6
30502112259 cash        2024-12-31 consolidado   norm=13,56          reext=13.567.145.085  ratio=1e-9
30715591231 equity      2024-12-31 individual    norm=2,187e12       reext=5,588e12        ratio=0,3914  ← real
```

### Conclusión

> **La extracción del número es determinista. La resolución de la escala no lo es.**

Es exactamente el problema que el propio esquema anticipa con `escala`,
`escala_origen`, `escala_revisar`, `correccion_factor` y `correccion_motivo`.

**Consecuencia directa para el diseño:** si `unit_ref` —que para CNV sería la
escala o la moneda— entra en el `fact_key`, **el `fact_key` hereda esa
inestabilidad**. Ver riesgo R1.

---

## HECHOS · 3 · Semántica de NULL en la guarda F-061

### El experimento

Schema temporal, `BEGIN … ROLLBACK`. Cuatro emisores: dos SEC (con `cik`) y dos
CNV (con `cik NULL`). El caso adverso aísla la comparación de entidad: **mismo
`accession`, mismo `qname`, sólo cambia el emisor**.

### Evidencia

| guarda | A · SEC propio | B · SEC AJENO | C · CNV propio | D · CNV AJENO |
|---|---|---|---|---|
| **actual** `p.cik <> d.cik` | PASA | **BLOQUEADO** | PASA | ***PASA*** ⛔ |
| `p.cik IS DISTINCT FROM d.cik` | PASA | **BLOQUEADO** | PASA | ***PASA*** ⛔ |
| **propuesta** `p.entity_id IS DISTINCT FROM d.entity_id` | PASA | **BLOQUEADO** | PASA | **BLOQUEADO** ✅ |

### Lo que esto refuta

En `CNV_CANONICAL_ENGINE_ARCHITECTURE.md` recomendé migrar la guarda a
`IS DISTINCT FROM`. **Ese consejo era insuficiente y el experimento lo demuestra.**

```
NULL <>              NULL   →  NULL   → el WHERE no se cumple → PASA
NULL IS DISTINCT FROM NULL   →  false  → el WHERE no se cumple → PASA
```

`IS DISTINCT FROM` arregla el caso *un NULL contra un valor*. **No arregla el caso
*dos NULL*, que es precisamente el caso CNV**: dos emisores argentinos, ambos sin
CIK, se ven como el mismo emisor.

> **La solución no es el operador. Es la columna.** Hay que comparar por una clave
> **siempre presente** — `entity_id` namespaced (`CUIT:30657863676`).

Un `cik` NULL-able **sin** cambiar la columna de comparación deja el sistema
peor que hoy: hoy la contaminación entre emisores CNV es imposible porque no hay
emisores CNV; con `cik` NULL y la guarda actual, sería invisible.

---

## HECHOS · 4 · Regresión SEC

### ¿Cambiar `cik` por `entity_id` altera algo para SEC?

```
filas en parsed.facts .................... 225.475
entity_id = 'CIK:' || cik ................ 225.475      (100,00 %)
DESVIACIONES .............................       0
entity_id NULL ...........................       0
cik NULL .................................       0
```

**La equivalencia es exacta y universal en la base entera.**

### El invariante F-061 medido con las dos claves, sobre datos reales

```
violaciones por cik        (guarda actual)     0
violaciones por entity_id  (guarda propuesta)  0
```

**Idéntico resultado.** Para SEC, el cambio de columna es una identidad
matemática, no una modificación de comportamiento.

---

## HECHOS · 5 · Conservación canónica

```
parsed.facts (SEC) .............................. 225.475
grupos canónicos (cik|acc|qname|ctx|unit) ....... 133.902
derived.fact vigentes ........................... 133.902   ← 1:1 con los grupos
factor de deduplicación SEC .....................   1,684
```

**SEC deduplica 1,68 filas parsed por hecho canónico** — el mismo hecho aparece en
varios estados del mismo filing.

### Proyección CNV

Como la tupla canónica **no colisiona en ninguna de las 106.421 filas** (§1), la
proyección CNV sería **1:1, sin deduplicación**:

```
pérdidas ....... 0        (ninguna fila se agrupa con otra)
duplicados ..... 0
colisiones ..... 0
```

**Transformaciones necesarias**, ninguna destructiva:

| origen CNV | destino canónico |
|---|---|
| `cuit` | `entity_id = 'CUIT:'\|\|cuit` |
| `accn` (GUID) | `accession_number` |
| `concepto` | `qname = 'cnv:'\|\|concepto` · `tag = concepto` |
| `tipo_balance` + `period_end` | `context_id` |
| `escala` / moneda | `unit_ref`, `unit_measure`, `currency` |
| archivo `{guid}.html` | `source_file` + `source_path` + **`source_hash` (a calcular)** |
| — | `source_kind = 'CNV_EEFF'` |

---

## HECHOS · 6 · `source_kind`

Separado en los tres planos que el encargo pide, porque **no coinciden**:

### a · Lo que el esquema permite físicamente

```
constraints de parsed.facts:
  facts_pkey · facts_run_id_fkey
  facts_period_kind_check   (INSTANT|DURATION|FOREVER)
  facts_unit_type_check     (SIMPLE|DIVIDED)
```

**No hay CHECK sobre `source_kind`.** Físicamente, `'CNV_EEFF'` entra.

### b · Lo que el contrato semántico permite

**NO lo permite.** El gate `C-S03-002` de S03 valida explícitamente:

```python
prov_viol = conn.execute(text("""
    SELECT count(*) FROM parsed.facts WHERE run_id=:r AND
      (source_hash IS NULL OR source_path IS NULL OR source_file IS NULL
       OR source_kind IS NULL OR entity_id IS NULL OR cik IS NULL
       OR accession_number IS NULL OR accession_number='N/A')"""))
```

`cik IS NULL` está enumerado como **violación de provenance**, y el check es
**bloqueante**. Una fila CNV con `cik NULL` haría fallar el gate de S03.

> **La ausencia de CHECK NO equivale a soporte contractual.** El contrato vive en
> el código del gate, no en el esquema. Ésta era la advertencia del encargo y se
> confirma.

### c · Qué código consumidor asume XBRL

| lugar | qué asume | ¿bloquea? |
|---|---|---|
| `s03_parse_ypf.py:646` · `C-S03-002` | `cik NOT NULL` | **sí, bloqueante** |
| `s03_parse_ypf.py:271-314` | ramas `XBRL_PACKAGE_ZIP` / `XBRL_INSTANCE` / `XBRL_SCHEMA` | no — es despacho de **fetch**, no de `parsed.facts` |
| `engine/s03.py:334-409` | `INLINE_XBRL`, `XSD_SCHEMA` | no — ídem |
| `audit_f054_f055.py:234` | agrupa por `cik` contando `source_kind` distintos | auditoría, no bloqueante |

**Las ramas `if kind == …` operan sobre el tipo de archivo descargado, no sobre
`parsed.facts.source_kind`.** El único acoplamiento contractual real es
`C-S03-002`.

---

## UNKNOWN resueltos

| # | antes | ahora |
|---|---|---|
| 1 | ¿puede colisionar el `context_id` sintético? | **NO. 0 de 106.421. Estructuralmente imposible: cada GUID = 1 período + 1 perímetro** |
| 2 | ¿es determinista la extracción? | **Las claves sí (45.844 pares). Los valores 97,38 %. La escala NO — 90,2 % de las diferencias son factores de escala puros** |
| 3 | ¿basta `IS DISTINCT FROM` para el NULL? | **NO. Con dos NULL devuelve `false`. Hay que comparar por `entity_id`** |

---

## Riesgos restantes

| # | riesgo | evidencia | severidad |
|---|---|---|---|
| **R1** | **`fact_key` inestable por la escala.** Si `unit_ref` codifica la escala y la escala no es determinista, el mismo hecho produce dos `fact_key` distintos entre corridas → duplicados silenciosos en `derived.fact` | 1.082 discrepancias de escala medidas | **ALTA** |
| **R2** | **`cik` NULL-able sin cambiar la guarda deja pasar contaminación entre emisores CNV**, invisible | experimento §3, caso D | **ALTA** — mitigable en el mismo commit |
| **R3** | `C-S03-002` rechaza cualquier fila con `cik NULL` | código citado en §6b | **MEDIA** — hay que condicionar el check por `source_kind` |
| **R4** | **UNKNOWN parcial**: no se demostró que `job5_v2` sea determinista *consigo mismo*. Sólo que concuerda al 97,38 % con otra implementación | no ejecutable sin generar RAW | **MEDIA** |
| **R5** | Un caso real de diferencia de valor no explicada por escala (`equity`, ratio 0,3914) | §2 | **BAJA** — 1 de 45.844 |

---

## Prerequisitos para la migración

En este orden, y **ninguno es opcional**:

**P1 · Resolver la escala antes que el `fact_key`.** Decidir si la escala entra
en la clave. **Recomendación basada en R1: NO.** El `fact_key` debería usar
`unit_measure` (la moneda, `iso4217:ARS` — estable) y **no** la escala. El valor
ya viene normalizado a pesos base por `job5_v2`; la escala es provenance, no
identidad.

**P2 · La guarda migra a `entity_id` en el MISMO commit que hace `cik`
NULL-able.** Demostrado en §3: separarlos abre una ventana de contaminación
indetectable. Y el test de mutación va **antes** de la migración.

**P3 · `C-S03-002` condicionado por `source_kind`:** exigir `cik NOT NULL` sólo
cuando `source_kind` empiece con `XBRL_`. Sin esto, el gate de S03 rechaza toda
fila CNV.

**P4 · Calcular los sha256** de los documentos CNV antes de cualquier inserción.
`source_hash` es `NOT NULL` y `C-S03-002` lo exige.

**P5 · Identidad de METR** en `identity_v1` con evidencia AFIP o HUMAN, previa a
cualquier `derived.fact` (FK sobre `entity_key`).

**P6 · Test de determinismo de `job5_v2` consigo mismo** sobre fixture aislado,
para cerrar R4 antes de confiar en la estabilidad del `fact_key`.

---

## Dictamen

# GATE = **PASS_WITH_WARNINGS**

**PASS** porque los tres UNKNOWN se cerraron con evidencia reproducible, la
regresión SEC es una identidad exacta sobre 225.475 filas, y la conservación
canónica proyecta 1:1 sin pérdidas.

**WITH_WARNINGS** por dos hallazgos que cambian el plan de implementación:

**El primero corrige mi propia recomendación.** `IS DISTINCT FROM` sobre `cik` no
alcanza: con dos NULL devuelve `false`. La guarda tiene que comparar `entity_id`,
no el operador. Si esto se hubiera implementado como estaba escrito, habría
quedado un agujero de contaminación entre emisores CNV, invisible y sin test que
lo detectara.

**El segundo es nuevo:** la escala no es determinista (1.082 casos medidos), y si
entra en el `fact_key`, la identidad canónica de un hecho CNV se vuelve
inestable entre corridas. **P1 tiene que decidirse antes de escribir el
adaptador**, no después.

**No se implementa nada.** Deteniéndome acá, como pide el encargo.
