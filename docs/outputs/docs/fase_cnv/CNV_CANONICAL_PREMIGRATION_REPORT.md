# CNV CANONICAL — INFORME PRE-MIGRACIÓN

**2026-09-02** · cierre de W1/W2/W3 · **solo lectura**
Sin producción, sin escrituras, sin fetch, sin RAW nuevo, sin migración.

---

```
W1 = PASS
W2 = PASS
W3 = PASS
```

# RECOMENDACIÓN: **READY_FOR_MIGRATION**

Con **cinco prerequisitos**, uno de ellos nuevo y descubierto en este ciclo.

---

## W1 · SEMÁNTICA DE `entity_id` — **PASS**

### Pregunta

¿El CUIT, que sería el `entity_id` CNV (`CUIT:30657863676`), identifica a la
**entidad** o al **documento**?

### Evidencia

```
CUIT distintos ......... 72
GUIDs distintos ...... 2.453          ← ~34 documentos por emisor
períodos distintos ..... 107
```

Si fuera identidad documental la relación sería 1:1. Es 1:34.

| emisor | documentos | períodos |
|---|---:|---:|
| A3 | 59 | 33 |
| RICH | 57 | 30 |
| **METR** | **57** | **30** |
| MOLI | 56 | 32 |
| POLL | 56 | 30 |
| TXAR | 54 | 30 |

### Pruebas de ambigüedad — las tres dan cero

```
un CUIT con MÁS DE UN ticker/nombre .......... 0 casos
un ticker con MÁS DE UN CUIT ................. 0 casos
un GUID que reporte MÁS DE UN cuit ........... 0 de 2.453
filas sin cuit ............................... 0 de 106.421
coincidencia con dim_entity .................. 72 / 72
```

### Veredicto

> **A) IDENTIDAD ESTABLE DE ENTIDAD.**

La correspondencia CUIT↔emisor es **biyectiva** en las 72 empresas, se mantiene
estable a lo largo de 2.453 documentos y 107 períodos, y coincide al 100 % con
`dim_entity`. Ningún documento mezcla emisores.

`entity_id = 'CUIT:' || cuit` es semánticamente equivalente a
`entity_id = 'CIK:' || cik` del lado SEC: **la clave del emisor en el registro de
su fuente, namespaced.**

---

## W2 · SEMÁNTICA DE LA ESCALA — **PASS**

### Qué campo es qué

| campo | poblado | significado |
|---|---:|---|
| `escala` | **106.421 / 106.421** | el factor que se aplicó para llevar el valor a pesos base |
| `escala_origen` | **0** | declarado, **nunca poblado** |
| `escala_revisar` | **0** | declarado, **nunca poblado** |
| `valor` | 106.421 | **el valor YA normalizado a pesos base** |
| `valor_corregido` · `correccion_factor` · `correccion_motivo` | 734 | correcciones puntuales posteriores |
| `fecha_reexpresion` | 106.421 | fecha de reexpresión IAS 29 |

Valores de `escala`: **1** (48.066) · **1.000** (41.081) · **1.000.000** (17.274).

### Qué significa `norm`

`job5_v2.factor_unidad()` extrae la unidad del documento (`MILES DE $`,
`Millones de $`) y **normaliza el valor a pesos base**. `s0_normalizar_cnv` lo
arrastra. Verificado sobre los 56 documentos de METR:

```
extraer_unidad_medida →  'MILES DE $'    25 documentos
                         'Millones de $' 31 documentos
```

> **`valor` está expresado en unidad base. `escala` describe cómo se llegó ahí:
> es provenance de la transformación, no unidad del valor almacenado.**

### ¿La escala está funcionalmente determinada por la clave?

```
claves (accn, concepto, tipo_balance, period_end) con MÁS DE UNA escala .... 0
```

**Cero.** La escala es función de la clave, no un componente independiente.

### CASO A — mismo hecho, distinta escala

```
casos encontrados: 0
```

**No existe** en las 106.421 filas un hecho identificado por la misma clave con
dos escalas distintas. El caso A que el encargo pide construir **no es
construible con los datos reales**, y eso es la demostración.

### CASO B — hechos distintos, misma escala

17.274 filas comparten `escala = 1.000.000`. **No colisionan**, porque la clave
las separa por `(accn, concepto, tipo_balance, period_end)` — que ya se demostró
libre de colisiones (0 en 106.421).

### Los 29 documentos con más de una escala

29 de 2.453 GUIDs usan dos escalas **dentro del mismo documento**. Inspeccionado:

```
GUID 07b16b3c…
  CNV_roe          escala=1          valor=0.37
  CNV_liquidez     escala=1          valor=2.13
  EPS_basico       escala=1          valor=0.0
  Assets           escala=1000000    valor=307445000000.0
```

**Es correcto**: los ratios de la CNV y el EPS son adimensionales o por acción
(`escala=1`); los importes van en millones. Escalas distintas para **conceptos
distintos**, nunca para el mismo concepto. **No afecta la clave.**

### Veredicto

> **Excluir `escala` del `fact_key` NO genera colisiones indebidas, NO genera
> duplicados indebidos, y NO pierde información económica.**

- **Sin colisiones**: la escala no aporta poder discriminante — está determinada
  por el resto de la clave (0 excepciones).
- **Sin duplicados**: no existe el caso A, así que ningún hecho se desdobla.
- **Sin pérdida**: el valor ya está en unidad base, y la escala se conserva como
  columna de provenance, reconstruible.

**La escala pertenece a la provenance. No a la identidad.**

---

## W3 · AUTODETERMINISMO — **PASS**

### El fixture

`job5_v2` tiene sus funciones **puras separadas de la persistencia**: `parse`,
`tipo_balance`, `factor_unidad`, `extraer_unidad_medida`, `extraer_moneda`,
`period_end`, `tipo_periodo`. La red (`requests`) y SQLite aparecen **sólo dentro
de `main()`** (líneas 216, 236, 331), protegido por `if __name__ == "__main__"`.

Se importó el módulo sin ejecutar `main()`, y se corrió la transformación **dos
veces sobre los mismos 56 archivos HTML de METR ya en disco**. Sin red, sin
SQLite, sin escribir.

### Evidencia

```
documentos procesados ..... 56       errores: 0

  campo                  diferencias pasada 1 vs 2
    tipo_balance              0 / 56
    factor_unidad             0 / 56
    unidad_medida             0 / 56
    moneda                    0 / 56
    period_end                0 / 56
    tipo_periodo              0 / 56
    partidas                  0 / 56      ← el conjunto completo de conceptos y valores
    fact_key candidata        0 / 56
```

Muestra:

```
GUID 01192889-b1ce-46bd-b504-15b4fd809bdd
  tipo_balance   INDIVIDUAL      period_end    2021-09-30
  factor_unidad  1000            tipo_periodo  P
  unidad_medida  MILES DE $      partidas      67 conceptos
  fact_key(Revenue)  9b2b97925024eb520eb47a8b11b0bcfa…
```

### Veredicto

> **Determinismo de identidad: SÍ. Determinismo del valor: SÍ. Determinismo de
> la escala: SÍ.**

Cero diferencias en los ocho campos, incluido el conjunto completo de partidas.

### Esto reclasifica el riesgo R1 del gate anterior

El gate previo midió 1.199 discrepancias de valor y las clasificó como
«la escala no es determinista», con severidad **ALTA**.

W3 demuestra que **esa medición comparaba dos implementaciones distintas**
(`job5_v2` contra el reextractor), no dos corridas de la canónica. **Dentro de
`job5_v2`, la escala es perfectamente determinista.**

**R1 baja de ALTA a BAJA**, y cambia de naturaleza: no es un problema de
estabilidad del `fact_key`, es un desacuerdo entre dos extractores del cual sólo
uno es el camino canónico.

---

## HALLAZGO NUEVO · la moneda no sale del documento

Descubierto al construir el fixture de W3:

```
extraer_moneda() sobre los 56 documentos de METR  →  '7'  en los 56
```

La función es `re.search(r'Moneda[^>]*>\s*([^<]+)', html)` y devuelve un **código
interno de CNV**, no un código de moneda. Es determinista, pero **no es
`iso4217:ARS`**.

Y `cnv_estados_norm` **no tiene columna de moneda** en absoluto — la moneda es
implícita y vive en `dim_entity.moneda_funcional = 'ARS'`.

**Consecuencia para el modelo canónico:** `currency` y `unit_measure` de
`derived.fact` **no pueden derivarse del documento CNV**. Tienen que venir de la
metadata de la entidad. Es un prerequisito, no un bloqueo — pero si se hubiera
asumido que el documento trae la moneda, el `fact_key` habría llevado `'7'`.

---

## Separación hechos / inferencias

### Hechos medidos

- 72 CUIT ↔ 72 tickers, biyección exacta, 0 ambigüedad en ambas direcciones
- 2.453 GUIDs, 0 con más de un CUIT, 0 con más de un período, 0 con dos perímetros
- 0 claves con más de una escala en 106.421 filas
- `escala_origen` y `escala_revisar`: 0 filas pobladas
- 56/56 documentos: 0 diferencias en 8 campos entre dos pasadas
- `extraer_moneda` devuelve `'7'` en 56/56

### Inferencias

- El CUIT es identidad de entidad **porque** la relación con documentos es 1:34 y
  la biyección con ticker es exacta — no porque el nombre lo sugiera.
- La escala puede salir del `fact_key` **porque** está funcionalmente determinada
  y el caso A no es construible — no por conveniencia.
- R1 se reclasifica **porque** W3 aísla la variable que el gate anterior no podía
  aislar.

### UNKNOWN que quedan

- **Ninguno de los tres originales.** Los tres cerraron.
- Persiste, fuera de alcance: qué código interno de CNV es `'7'` y si hay
  emisores CNV que reporten en otra moneda. Para las 72 conocidas, `dim_entity`
  declara ARS en todas — **UNKNOWN para el padrón de 554**.

---

## Riesgos restantes

| # | riesgo | severidad | estado |
|---|---|---|---|
| **R1** | escala no determinista | **BAJA** ↓ | **reclasificado por W3** — era desacuerdo entre implementaciones |
| **R2** | `cik` NULL-able sin migrar la guarda deja pasar contaminación CNV | **ALTA** | vigente · mitigable en el mismo commit |
| **R3** | `C-S03-002` rechaza `cik NULL` | **MEDIA** | vigente · condicionar por `source_kind` |
| **R6** | `currency`/`unit_measure` no derivables del documento | **MEDIA** | **NUEVO** |
| R5 | 1 diferencia de valor no explicada (`equity`, ratio 0,3914) | BAJA | vigente · 1 de 45.844 |

---

## Prerequisitos para la migración

**P1 · `fact_key` sin escala, con moneda de la entidad.** Confirmado por W2. La
tupla propuesta:

```
sha256( 'CUIT:'||cuit | guid | 'cnv:'||concepto
        | tipo_balance@period_end | moneda_de_la_entidad )
```

**La moneda sale de `dim_entity.moneda_funcional`, NO de `extraer_moneda()`** —
ver el hallazgo nuevo. La escala queda como columna de provenance.

**P2 · La guarda migra a `entity_id` en el mismo commit que hace `cik`
NULL-able.** Sin cambios respecto del gate anterior. Test de mutación antes.

**P3 · `C-S03-002` condicionado por `source_kind`:** exigir `cik NOT NULL` sólo
para `source_kind LIKE 'XBRL_%'`.

**P4 · Calcular los sha256** de los documentos CNV. `source_hash` es `NOT NULL` y
`C-S03-002` lo exige.

**P5 · Identidad de METR** en `identity_v1` con evidencia AFIP o HUMAN, previa a
cualquier `derived.fact` por la FK sobre `entity_key`.

---

## Dictamen

```
W1 = PASS      CUIT = identidad estable de entidad · biyección exacta · 0 ambigüedad
W2 = PASS      escala funcionalmente determinada · caso A no construible · excluible
W3 = PASS      0 diferencias en 8 campos × 56 documentos · 0 errores
```

# READY_FOR_MIGRATION

Los tres warnings cierran con evidencia reproducible, y **uno de ellos mejora el
diseño**: W3 demuestra que la extracción canónica es autodeterminista, lo que
baja R1 de ALTA a BAJA y elimina la duda que más pesaba sobre la estabilidad del
`fact_key`.

El ciclo además **encontró un problema que nadie había pedido buscar**: la moneda
no sale del documento CNV. Si la migración se hubiera escrito asumiendo lo
contrario, el `fact_key` de todos los hechos CNV habría llevado el literal `'7'`.

**No se implementa nada.** Deteniéndome acá.
