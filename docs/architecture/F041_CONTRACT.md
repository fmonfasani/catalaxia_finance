# CONTRATO — F-041 · EVIDENCIA ESTRUCTURADA EN ASSERTIONS HISTÓRICAS

**Fecha:** 2026-08-28 (ciclo 9, fase C) · **Escrito antes de modificar dato alguno.**

---

## 0. Regla fundamental

> **No se reescribe el pasado para satisfacer un contrato nuevo.**

Las 7 assertions se escribieron cuando `source_facts` no existía. No estaban mal:
estaban completas según el contrato de su momento. Lo que falta se agrega
**afirmando de nuevo**, no editando.

---

## 1. ¿Qué es evidencia estructurada?

La representación **consultable** de la misma evidencia que la cita textual ya
declara: los campos que un tercero necesita para volver al artefacto primario y
verificar el hecho, sin parsear texto libre.

`source_facts` **no es un resumen ni una interpretación**. Cada clave sale
literalmente del artefacto. Si un campo no está en el artefacto, no va.

## 2. ¿Qué fuentes pueden estructurarse, y con qué campos mínimos?

| `source_id` | artefacto primario | campos mínimos |
|---|---|---|
| `SEC_REGISTRY` | `data/raw/submissions/CIK<10>.json` | `cik` (el que el archivo declara), `sec_name`, `artefacto`, `sha256` |
| `SEC_20F` | el documento 20-F del accession | `accession`, `seccion` o `form`, `artefacto`, `sha256` |
| `GLEIF` | registro GLEIF del LEI | `lei`, `registeredAt`, `registeredAs` |
| `LEGACY_DIM_ENTITY` | — | **no aplica**: es `CORROBORATING`, no establece identidad |

El `sha256` del artefacto es obligatorio: es lo que permite decir *«el archivo
que leí es este»* y detectar que cambió.

## 3. Evidencia histórica que existe pero no fue estructurada

Se **re-afirma**. No se enriquece en el lugar.

Motivo: `source_facts` es evidencia, y la evidencia es parte de lo que la
assertion afirma. El modelo ya decidió esto — el propio mensaje del trigger de
inmutabilidad lo dice: *«Para corregir, cree una assertion nueva y supersédala;
no la edite.»*

### El hueco que NO se va a usar (F-042)

`fn_assertion_inmutable` enumera 16 columnas y **`source_facts` no está entre
ellas**: la columna se agregó en F-036, después de escribirse el trigger. Se
verificó empíricamente que el owner **puede** mutar y hasta **borrar**
`source_facts` de una assertion `VERIFIED` histórica.

Ese es el camino barato para cerrar F-041, y es exactamente lo que la regla
fundamental prohíbe. **No se usa, y además se tapa** (§8): mientras el hueco
exista, toda esta disciplina es decorativa.

El rol de aplicación `catalaxia_engine` no llega al hueco — su GRANT sobre
`assertion` es sólo `(valid_to, superseded_by)`. El agujero es del trigger, la
capa que debería ser la última.

## 4. Cuando el artefacto original ya no está

**Se deja como deuda explícita.** No se estructura desde el texto de `evidence`,
y no se inventan `accession`, sección, URL, timestamp ni hash.

Si el hecho es verificable hoy contra **otro** artefacto primario autoritativo,
puede re-afirmarse **declarando esa otra fuente** — nunca fingiendo que el
artefacto ausente lo respalda. La assertion histórica queda intacta y encadenada,
y su falta de artefacto queda registrada.

## 5. ¿Se puede enriquecer una assertion histórica inmutable? **No.**

## 6. Mecanismo de re-afirmación

`catalaxia_engine` puede: `assertion(valid_to, superseded_by)` e
`identifier(status, valid_to)`. **No** puede repuntar `identifier.assertion_id`.
Por lo tanto, dentro de **una** transacción:

```
1. INSERT assertion nueva   -- mismo hecho, con source_facts completos
2. UPDATE identifier viejo  -- valid_to = now(), status = 'RETIRED'
3. INSERT identifier nuevo  -- mismo id_value, apunta a la assertion nueva
4. UPDATE assertion vieja   -- valid_to = now(), superseded_by = nueva
```

El orden importa: `ux_identifier_autoritativo_unico` es parcial sobre
`valid_to IS NULL`, así que el viejo se retira **antes** de insertar el nuevo.

## 7. Cómo se conserva la provenance original

Nada se borra. La assertion vieja conserva su `source_id`, `source_record`,
`evidence`, `resolved_by` y `created_at` originales, y gana `superseded_by`, que
la enlaza con la que la reemplaza. El identifier viejo queda `RETIRED` con su
`valid_to`. La cadena completa es reconstruible hacia atrás.

La assertion nueva declara `resolved_by = 'proc:f041_reafirmacion'` y una cita
que **dice que es una re-afirmación**, con el `assertion_id` de la original. No
se hace pasar por contemporánea del hecho.

## 8. Cerrar el hueco (parte obligatoria de F-041)

`fn_assertion_inmutable` se extiende para incluir `source_facts` entre los hechos
inmutables. Sin esto, cualquiera con el rol owner puede «cerrar» F-041 inventando
facts, y ningún control lo detectaría.

Se aplica **después** de la re-afirmación (si no, la propia re-afirmación sería
imposible… no: la re-afirmación *inserta*, no actualiza; el orden no importa,
pero se documenta igual).

## 9. Clasificación (fase D)

| clase | criterio | qué se hace |
|---|---|---|
| **A** ESTRUCTURABLE | evidencia primaria suficiente y editable en el lugar | **vacía por contrato**: editar está prohibido (§5) |
| **B** REAFIRMABLE | el hecho se verifica hoy contra el artefacto primario presente | re-afirmar (§6) |
| **C** NO ESTRUCTURABLE | el artefacto no está o no declara los campos | deuda explícita, intacta |
| **D** CONFLICTO | el artefacto contradice la assertion | abrir `conflict`, no sobrescribir |

La clase **A queda deliberadamente vacía**. No porque falte evidencia, sino
porque el mecanismo que A supone —enriquecer en el lugar— es justamente el que
este contrato prohíbe. Llamar A a un caso sería usar el hueco de F-042.

## 10. Idempotencia

Re-ejecutar no debe producir nada: una assertion que ya tiene `source_facts` no
se re-afirma. La condición de entrada es
`identifier.is_authoritative AND valid_to IS NULL AND assertion.source_facts IS NULL`,
y la operación la deja de cumplir.

## 11. Lo que este procedimiento NO hace

No toca `data/raw` · no ejecuta SEC, CNV, Market ni M23 · no toca BYMA · no
ratifica bridges · no crea ni retira CUIT autoritativos · no cambia el
`id_value` de ningún identificador · no cambia a qué entidad apunta un CIK.

**El ancla no se mueve.** Después de la re-afirmación, cada CIK designa la misma
entidad que antes, con la misma `entity_key`.
