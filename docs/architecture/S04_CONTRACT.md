# S04_normalize — CONTRATO

**Etapa:** `S04_normalize` · **Entrada:** checkpoint `971ce5d999a2499b-s03` · **Salida:** schema `derived`
**Fecha:** 2026-08-26 · **Estado:** contrato cerrado, previo a implementación.

---

## 0. Qué hace S04, y qué NO

**Hace:** convierte los hechos XBRL crudos de `parsed.*` en **un hecho canónico por
(entidad, filing, concepto, período, unidad)**, con la procedencia de cada uno.

**No hace:** no calcula ratios, no arma series temporales, no compara ejercicios, no toca
CNV ni Market. Eso es S05 en adelante. S04 responde una sola pregunta:

> ¿Cuál es **el** valor que YPF reportó para el concepto X, en el período P, en la unidad U,
> en el filing F — y de qué filas exactas de `parsed.facts` sale?

---

## 1. Entradas

| Insumo | Origen | Validación previa |
|---|---|---|
| `parsed.facts` (67.084) | checkpoint S03 | `hash_out` recalculado debe coincidir |
| `parsed.contexts` (23.478) | checkpoint S03 | idem |
| `parsed.units` (369) | checkpoint S03 | idem |
| `parsed.concepts` (13.412) | checkpoint S03 | idem |
| `identity_v1` | ciclo 6, certificado | el CIK debe resolver a una entidad |

**S04 consume un único `run_id`**: el de la corrida dueña del checkpoint
(`971ce5d999a2499ba6af136cb2c87569`). Si `parsed.*` tuviera más de una corrida, S04 **no
elige por su cuenta**: bloquea.

---

## 2. Las tres trampas del insumo, medidas antes de diseñar

No son hipótesis. Se contaron sobre los datos reales.

### T1 · Contextos duplicados — 5.982 grupos

`(accession_number, context_id)` aparece repetido dentro del mismo filing, porque un filing
tiene varios archivos (inline XBRL + instance) y cada uno declara sus contextos.

**Medición:** de los 5.982 grupos duplicados, **5.982 son idénticos y 0 contradictorios**
(misma fecha, mismo `period_kind`, mismas dimensiones).

**Consecuencia si se ignora:** el JOIN ingenuo `facts × contexts` infla 67.084 hechos a
**100.804**. Un 50 % de hechos fantasma.

**Regla:** deduplicar por `(accession_number, context_id)`. Si aparece un grupo con más de
una variante → **BLOCK**, no se elige en silencio.

### T2 · Hechos duplicados — 18.853 grupos, y 98 con valor distinto

`(accession, tag, context_id, unit_ref)` repetido: **18.755 grupos con el mismo valor**
(inocuo) y **98 con valor distinto**.

Los 98 **no son errores**. Son el mismo hecho declarado con distinta precisión:

```
ApplicableTaxRate · P01_01_2019To12_31_2019 · Unit_pure
    0.30    decimals = 2
    0.3000  decimals = INF
```

**Regla de desempate — por precisión declarada, nunca por orden de inserción:**

1. `decimals = 'INF'` gana sobre cualquier valor finito.
2. Entre finitos, gana el `decimals` mayor.
3. Empate en `decimals`: gana el de `value_text` más largo (más dígitos significativos
   conservados).
4. Empate total: gana el `fact_id` menor, **y se registra el empate** en el reporte.

El hecho canónico guarda **todos** los `fact_id` del grupo, no sólo el ganador. La precisión
descartada queda reconstruible.

### T3 · Dimensional vs consolidado — 22.617 / 78.187

Un hecho con dimensiones (`dim_count > 0`) es un **segmento** (una subsidiaria, una línea de
negocio, un tramo). Sumarlo junto al consolidado es la forma clásica de duplicar ingresos.

**Regla:** `is_dimensional` es una columna obligatoria, no un filtro implícito. S04 **no
descarta** los dimensionales — los marca. Quien consuma decide.

---

## 3. Salida — schema `derived`

### `derived.fact`

Un hecho canónico. Clave primaria `fact_key`, determinística:

```
fact_key = sha256( entity_key | accession_number | qname | context_id
                   | COALESCE(unit_ref,'') )
```

Determinística por diseño: **re-ejecutar S04 produce exactamente los mismos `fact_key`.**
Es lo que hace posible el upsert idempotente y lo que permite a un auditor recalcular la
clave sin correr el pipeline.

| Columna | Qué es |
|---|---|
| `fact_key` | PK, sha256 de la tupla canónica |
| `entity_key` | **FK a `identity_v1.entity`** — no `dim_entity`, no `identity.entities` |
| `cik`, `accession_number`, `form`, `filing_date`, `report_period` | el filing |
| `qname`, `namespace`, `tag`, `is_custom` | el concepto |
| `period_kind`, `start_date`, `end_date`, `instant_date` | el período, del contexto deduplicado |
| `is_dimensional`, `dim_count`, `dimensions` | T3 |
| `unit_ref`, `unit_kind`, `unit_measure`, `currency` | la unidad |
| `value_numeric`, `value_text`, `is_nil`, `decimals` | el valor ganador |
| `n_fuentes`, `source_fact_ids[]` | T2: cuántas filas de `parsed.facts` y cuáles |
| `desempate` | `UNICO` / `IDENTICO` / `POR_PRECISION` / `POR_FACT_ID` |
| `input_checkpoint_id`, `run_id`, `created_at` | procedencia de la corrida |

### `derived.normalize_conflict`

Todo lo que S04 **no pudo resolver sin elegir arbitrariamente**. Si tiene filas, el gate
las cuenta; si supera el umbral, bloquea. La ambigüedad se registra, no se resuelve sola.

---

## 4. Identidad

`entity_key` sale de **`identity_v1`**, resolviendo el CIK como identificador autoritativo
vigente. No de `dim_entity` (que tiene el CIK de Banco Macro en la columna `cuit`, F-024) ni
de `identity.entities` (clave derivada `CIK:0000904851`, el acoplamiento que Identity v1
existe para romper).

**Si el CIK no resuelve a una entidad certificada, S04 bloquea.** No crea la entidad, no la
infiere por nombre, no usa el CIK como clave.

---

## 5. Idempotencia

| Propiedad | Cómo se garantiza |
|---|---|
| Mismo insumo → mismo `fact_key` | hash determinístico de la tupla canónica |
| Re-ejecutar no duplica | `INSERT … ON CONFLICT (fact_key) DO UPDATE` |
| Re-ejecutar no cambia el conteo | verificado por `C-S04-008` comparando antes/después |
| Un hecho que desaparece del insumo | se marca `valid_to`, **no se borra** (coherente con F-017) |

---

## 6. Ciclo de vida de la corrida — requisito de F-009

**Obligatorio, y es la razón por la que S04 no copia el patrón de S03:**

1. **`run_scope()`** — el cierre va en `finally`. Si el proceso muere, la corrida queda
   `ABORTED`, nunca `RUNNING` para siempre.
2. **Operación consistente**: la transición a `CHECKPOINTED`, el `report` y la fila de
   `engine.checkpoints` se escriben en **una sola transacción**. En S03 iban separadas y por
   esa grieta se colaron 2 corridas que llegaron a `CHECKPOINTED` sin report.
3. **`corridas_huerfanas()`** al arrancar: si el pipeline dejó huérfanas, se ve antes de
   generar más.
4. Corre como `catalaxia_engine` (no superusuario, F-025).

**S03 no se modifica.** S04 no depende de que S03 cambie: lee su checkpoint, que está
verificado.

---

## 7. Gate — 9 checks

| ID | Verifica | BLOCK si |
|---|---|---|
| `C-S04-001` | El checkpoint S03 existe, su corrida es `OK` y su `hash_out` recalculado coincide | no coincide |
| `C-S04-002` | `parsed.*` tiene exactamente una corrida, la del checkpoint | hay más de una |
| `C-S04-003` | Contextos duplicados: 0 contradictorios (T1) | hay ≥1 contradictorio |
| `C-S04-004` | El CIK resuelve a una entidad autoritativa en `identity_v1` | no resuelve |
| `C-S04-005` | **Sin pérdida**: todo `parsed.facts.fact_id` aparece en algún `source_fact_ids` | falta ≥1 |
| `C-S04-006` | **Sin invención**: todo `derived.fact` tiene `n_fuentes ≥ 1` | hay ≥1 con 0 |
| `C-S04-007` | Todo hecho numérico no-nil tiene unidad resuelta | hay ≥1 sin unidad |
| `C-S04-008` | **Idempotencia**: segunda pasada en seco no cambia conteo ni `fact_key` | cambia |
| `C-S04-009` | `is_dimensional` poblado en el 100 % | hay ≥1 NULL |

`C-S04-005` y `C-S04-006` son las dos mitades del contrato de fidelidad: **no se pierde nada
y no se inventa nada.** Ambas se verifican contra la base, no contra un contador interno.

---

## 8. Reporte

Mismo contrato que S03 (`engine-report-v1`): `code`, `gate`, `input`, `coverage`,
`integrity` (`hash_in` / `hash_out`), `nulls`, `stage`, `run_id`, tiempos.

```
hash_in  = sha256( checkpoint_id de S03 )
hash_out = sha256( json ordenado de { facts, entidades, filings, dimensionales, conflictos } )
```

Un auditor puede recalcular `hash_out` desde la base sin correr el pipeline — igual que se
hizo con S03 en el gate de habilitación.

---

## 9. Qué NO se declara hasta que exista evidencia

S04 **no se declara `CHECKPOINTED`** hasta que:
1. el script exista,
2. haya una ejecución real contra el checkpoint S03,
3. y un auditor pueda reconstruir el resultado desde la base y los artefactos.
