# `hash_out` — CONTRATO (cambio de contrato F-029)

**Fecha:** 2026-08-27 · **Alcance:** S03_parse, S04_normalize · **Versión:** `hashout-v2`

---

## 1. El problema, demostrado

Tres corridas de S03 declararon **el mismo `hash_out`**, y una de ellas tenía contenido
distinto — es la que corrigió el parser de unidades (F-026) y cambió 44 unidades y 436 facts:

```
a1a37b1986a14f8c…  60ff8e1aecd373ac…
971ce5d999a2499b…  60ff8e1aecd373ac…
e040bd08d0494621…  60ff8e1aecd373ac…   ← parser corregido, datos distintos
```

La especificación vigente (`hashout-v1`) es:

```python
hash_out = sha256(json({facts, contexts, units, concepts, relations}))
```

Cinco **cantidades de filas**. Nada más.

**Consecuencia:** un cambio en el parser que altera los valores sin cambiar la cantidad de
filas produce un checkpoint indistinguible del anterior. Si la corrección de F-026 hubiera
sido una regresión en lugar de un arreglo, el checkpoint no lo habría notado. Un checkpoint
que no distingue contenido **no sirve para lo que se lo usa**: detectar que algo cambió.

---

## 2. Qué debe representar `hash_out`

> `hash_out` es la **huella del contenido semántico** que la etapa publica: si dos corridas
> declaran el mismo `hash_out`, un consumidor puede tratar sus artefactos como equivalentes.

De ahí se siguen tres propiedades, y las tres son verificables:

| # | Propiedad | Prueba |
|---|---|---|
| **P1** | **Sensible al contenido.** Cambiar un valor publicado cambia el hash. | mutación semántica → hash distinto |
| **P2** | **Insensible al orden.** Reordenar filas no cambia el hash. | permutar → hash idéntico |
| **P3** | **Determinista y reconstruible.** Un tercero lo recalcula desde la base, sin correr el pipeline. | recálculo independiente |

**P2 no es un detalle de comodidad.** Postgres no garantiza orden sin `ORDER BY`; un digest
sensible al orden daría falsos positivos en cada corrida y el `hash_out` se volvería ruido
que nadie mira.

---

## 3. Qué entra en el digest, y qué no

Entra **lo que la etapa publica como hecho**. No entra lo que es circunstancia de la corrida.

| Entra | No entra | Por qué |
|---|---|---|
| valores, identificadores, períodos, unidades | `run_id` | dos corridas idénticas deben coincidir |
| composición de unidades (numerator/denominator) | `created_at`, `updated_at` | el reloj no es contenido |
| clasificación (dimensional, tipo de período) | claves autoincrementales (`fact_id`, `ctx_id`) | dependen del orden de inserción |
| cantidad de filas por tabla | rutas de archivo, `source_file` | describen de dónde vino, no qué dice |

La exclusión de las claves seriales es la que hace que P2 se cumpla: si `fact_id` entrara,
recargar los mismos datos en otro orden daría otro hash.

---

## 4. Especificación `hashout-v2`

Digest de dos niveles. El primero resume cada fila; el segundo agrega las filas de forma
conmutativa.

```
fila_i   = sha256( campo_1 ⧺ '|' ⧺ campo_2 ⧺ … )      -- campos semánticos, en orden fijo
tabla    = sha256( concat( sort( fila_1 … fila_n ) ) )  -- el sort da P2
hash_out = sha256( json_ordenado( { tabla: digest_tabla, … , '_conteos': {…} } ) )
```

- El `sort` de los hashes de fila es lo que hace el agregado **conmutativo**: mismo conjunto
  de filas, mismo digest, sin importar en qué orden vinieron.
- Se conservan los conteos dentro del digest: una tabla que pierde filas cambia el hash por
  dos vías independientes.
- `NULL` se codifica como `\N` y se distingue de la cadena vacía. Un `NULL` que se vuelve
  `''` es un cambio semántico y debe verse.
- Los `NUMERIC` se serializan con su **texto declarado**, no como float — misma razón que en
  el desempate por precisión de S04: `0.30` y `0.3000` son declaraciones distintas.

### Campos por tabla

| Tabla | Campos del digest |
|---|---|
| `parsed.facts` | `accession_number, qname, context_id, unit_ref, value_text, value_numeric, is_numeric, is_nil, decimals, unit_type, measure, numerator, denominator, period_kind, start_date, end_date, instant_date` |
| `parsed.contexts` | `accession_number, context_id, period_kind, start_date, end_date, instant_date, dimensions, typed_dimensions, dim_count` |
| `parsed.units` | `accession_number, unit_ref, unit_type, measures, numerator, denominator` |
| `parsed.concepts` | `qname, namespace, tag, period_type, balance, abstract, is_custom, taxonomy` |
| `derived.fact` (S04) | `fact_key, entity_key, qname, context_id, unit_measure, currency, unidad_resuelta, value_text, value_numeric, is_nil, is_dimensional, period_kind, start_date, end_date, instant_date, desempate, n_fuentes` |

`parsed.link_relations` entra sólo por conteo: es voluminosa (146k) y su contenido no se
publica hacia S04.

---

## 5. Compatibilidad

`hashout-v2` **cambia el valor** de `hash_out` para todas las etapas. No es un bug: es el
punto. Por eso:

- el reporte declara `integrity.hash_spec = "hashout-v2"` junto al hash, para que nunca se
  comparen dos hashes calculados con especificaciones distintas;
- se conserva `hash_out_v1` (los conteos) en el reporte como campo aparte, para poder
  contrastar con los checkpoints históricos;
- el `input_hash` de `engine.checkpoints` **no cambia** — es `sha256(checkpoint_id)` de la
  etapa anterior y no participa de este contrato.

---

## 6. Criterio de aceptación

1. **Mutación semántica** (cambiar un valor de una fila) → `hash_out` **distinto**.
2. **Permutación** (reordenar las filas) → `hash_out` **idéntico**.
3. **NULL vs cadena vacía** → `hash_out` **distinto**.
4. **Precisión** (`0.30` vs `0.3000`) → `hash_out` **distinto**.
5. **Recálculo independiente** desde la base coincide con el declarado.
6. Las corridas de S03 anteriores y posteriores a F-026, que compartían `hashout-v1`,
   deben declarar **`hashout-v2` distinto** — es la prueba de que el problema quedó resuelto.
