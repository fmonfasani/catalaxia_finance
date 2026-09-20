# F-045 — GATE

**Fecha:** 2026-08-28 · **Instancia:** `catalaxia-engine-dev` 127.0.0.1:5433
**Rol de todas las pruebas:** `catalaxia_engine` (operativo, **nunca** admin)
**Reproducible:** `python scripts/engine/f045_bench.py` · `python scripts/engine/audit_f045.py`

---

## DICTAMEN: **F-045 = CLOSED**

Los 14 ataques por SQL directo son rechazados, **cada uno por la garantía que
declara**, y la mutación demuestra que sin esa garantía pasan.

**F-046 = DEUDA DOCUMENTADA** (6 filas históricas, riesgo residual nulo).

---

## 1. La garantía implementada

`identity_v1.tg_identifier_coherente_con_assertion` — trigger
`BEFORE INSERT OR UPDATE ON identity_v1.identifier`
(`migrations/engine/030_f045_coherencia_assertion_identifier.sql`).

**Sin cambio de schema.** Todo lo necesario ya existía: el tipo en
`identifier.id_type`, el vínculo en `identifier.assertion_id`, la declaración en
`assertion.left_ref` con formato canónico, la política en
`source.authoritative_for`. Lo que faltaba era **evaluarlo donde el tipo existe**.

Cuando la fila resultante es autoritativa y vigente, exige:

| # | verificación | ataque que cierra |
|---|---|---|
| 1 | la assertion es `subject_type='ENTITY_IDENTIFIER'` | — |
| 2 | **`left_ref` no puede ser NULL** | A1, A2, A3, A5 |
| 3 | `left_ref = id_type\|\|':'\|\|id_namespace\|\|':'\|\|id_value` | A4, A6 |
| 4 | `assertion.entity_key = identifier.entity_key` | A14 |
| 5 | la fuente es `AUTHORITATIVE` **para ese `id_type`** | A1b, A2b, A3b, A9, A10 |

No es heurística de texto libre: (3) es igualdad exacta contra el formato que ya
produce `engine/identity_v1.py:ref()` y que **574/574** identificadores vigentes
cumplen.

**Qué no rompe:** retirar un identificador (`valid_to IS NOT NULL`) siempre se
permite —sin eso las 6 filas de F-046 quedarían inmovilizadas y el supersede de
F-041 se rompería—; y los `CANDIDATE` no se validan, porque no establecen
identidad (los 53 CUIT candidatos siguen entrando).

**No se otorgaron privilegios nuevos. El owner no forma parte de la garantía.**

---

## 2. Ataques rechazados — 14/14

| | ataque | garantía que lo rechaza |
|---|---|---|
| A1 | `LEGACY_DIM_ENTITY` → CUIT, sin `left_ref` | `F045:left_ref_obligatorio` |
| A2 | `DERIVED_RULE` → CUIT, sin `left_ref` | `F045:left_ref_obligatorio` |
| A3 | `CNV_PORTAL` → CUIT, sin `left_ref` | `F045:left_ref_obligatorio` |
| A1b | `LEGACY_DIM_ENTITY` → CUIT, con `left_ref` | `fuente_autoritativa_para_el_tipo` |
| A2b | `DERIVED_RULE` → CUIT, con `left_ref` | `fuente_autoritativa_para_el_tipo` |
| A3b | `CNV_PORTAL` → CUIT, con `left_ref` | `fuente_autoritativa_para_el_tipo` |
| **A4** | **assertion que declara CIK usada para establecer CUIT** | `F045:left_ref_coincide` |
| A5 | `GLEIF` con `left_ref` NULL | `F045:left_ref_obligatorio` |
| A6 | `left_ref` apuntando a otro valor | `F045:left_ref_coincide` |
| A9 | `SEC_REGISTRY` (autoritativa CIK) → CUIT | `fuente_autoritativa_para_el_tipo` |
| A10 | `GLEIF` (autoritativa LEI/CUIT) → CIK | `fuente_autoritativa_para_el_tipo` |
| A11 | el CUIT de CEPU sobre otra entidad | `ux_identifier_autoritativo_unico` |
| A12 | el CIK de YPF sobre otra entidad | `ux_identifier_autoritativo_unico` |
| A14 | assertion de otra entidad usada para anclar | `F045:misma_entidad` |

### Nota de método

A1/A2/A3 se **desdoblaron**. Con `left_ref` NULL cortan en el paso (2) y **no
llegan** a ejercitar la política de fuente: declararlos como prueba de esa política
habría sido reportar una garantía por otra. Las variantes `A1b/A2b/A3b`, con
`left_ref` poblado, son las que la prueban.

A9/A10 los captura el trigger sobre `assertion`, que corta antes en el INSERT de la
assertion. Es correcto y se declara así: la garantía temprana es válida, y la
mutación 3 demuestra que el trigger nuevo también los cubre por sí solo.

### Rutas por `UPDATE` (A7, A8, A13)

Cerradas por **GRANT de columna**, no por trigger. `catalaxia_engine` sólo tiene
`UPDATE (status, valid_to)` sobre `identifier` y `UPDATE (superseded_by, valid_to)`
sobre `assertion`. Verificado: `id_type`, `id_value`, `assertion_id`,
`is_authoritative`, `assertion.status`, `assertion.source_id` y `assertion.left_ref`
son todos `permission denied`.

---

## 3. Mutaciones realizadas

Tres, sobre la instancia de desarrollo, todas restauradas y verificadas.

### Mutación 1 — quitar `tg_identifier_coherente_con_assertion`

**7 ataques pasan**: A1, A2, A3, A4, A5, A6, A14. Es la prueba de que el banco
depende de la garantía nueva y no de otra cosa.

### Mutación 2 — deshabilitar `tg_fuente_autoritativa_para_el_tipo`

`BYPASS = 0`. A10 pasa a ser capturado por el trigger nuevo. Defensa en profundidad
confirmada.

### Mutación 3 — quitar **ambas** barreras previas (trigger de `assertion` + `ck_cuit_exige_evidencia_estructurada`)

`BYPASS = 0`, con el trigger nuevo **sosteniendo solo**: A1b/A2b/A3b/A9/A10 pasan a
ser capturados por `F045:fuente_autoritativa_para_el_tipo`.

Hallazgo lateral útil: `ck_cuit_exige_evidencia_estructurada` tiene `ELSE false`, así
que **ninguna fuente fuera de {GLEIF, SEC_20F, AFIP, HUMAN} puede establecer un CUIT**
ni aunque los triggers desaparecieran. Los ataques A1b/A2b/A3b/A9 están triplemente
cubiertos.

**Estado restaurado y verificado:** los dos triggers activos (`tgenabled='O'`) y el
CHECK presente (`convalidated=false`, `NOT VALID` como en su migración original).

---

## 4. Auditoría independiente (fase H)

`scripts/engine/audit_f045.py` — **no importa** `f045_bench` ni la capa de dominio.
Reconstruye las garantías desde `pg_trigger`, `pg_constraint` e
`information_schema.column_privileges`, y ataca con SQL propio.

| pregunta | respuesta | evidencia |
|---|---|---|
| 1. ¿Puede inventar CUIT? | **NO** | 10 caminos probados (5 fuentes × con/sin `left_ref`), 0 abiertos |
| 2. ¿Puede transformar CIK en CUIT? | **NO** | `F-045: tipo declarado distinto del real` |
| 3. ¿`CORROBORATING` establece identidad? | **NO** | `La fuente LEGACY_DIM_ENTITY es CORROBORATING` |
| 4. ¿Puede omitir el tipo con `left_ref` NULL? | **NO** | `F-045: la assertion no declara qué identificador establece` |
| 5. ¿Puede cambiar el tipo por `UPDATE`? | **NO** | 6 columnas probadas, todas `permission denied` |
| 6. ¿Puede promover sin la evidencia requerida? | **NO** | `ck_cuit_exige_evidencia_estructurada` + `tg_identifier_autoritativo` |

---

## 5. Regresión

**Suite completa: 198/198.**

Una regresión, **de fixture, no del sistema**:
`test_02_el_mismo_cik_no_puede_designar_dos_entidades` (banco del ciclo 8) insertaba
una assertion **sin `left_ref`** para llegar al índice único; ahora el trigger nuevo
corta antes. Se corrigió el fixture agregando `left_ref`, no el sistema. Que ese
fixture haya dejado de pasar es evidencia adicional de que el trigger tiene alcance
real.

### Pipeline legítimo

`backfill_cik.py --dry-run` sobre los 512 elegibles: **0 errores**, delta 0 en todas
las métricas, **hash de identidad idéntico** (`f0a38639982cd616`).

### Reconstrucción independiente

| | CIK | CUIT | LEI | autoritativos |
|---|---|---|---|---|
| YPF | 0000904851 | 30546689979 | 5493003N7447U18U5U53 | 3 |
| CEPU | 0001717161 | 33650305499 | 2549005JLIWQ6B7VNR38 | 3 |
| TGS | 0000931427 | 30657862068 | 5299002TRC7IFQYSW596 | 3 |
| **GGAL** | 0001114700 | **—** | 5299008H3AXIXV5G3C23 | 2 |
| **BMA** | **0001347426** | **—** | — | 1 |

GGAL sigue **sin CUIT** (no ratificado). BMA sigue con **CIK correctamente tipado**
y sin CUIT (F-024 intacto).

```
entidades ............................. 525   (sin cambio)
CIK autoritativos ..................... 513   (sin cambio)
CUIT autoritativos .....................  3   (sin cambio)
CUIT CANDIDATE (56 BYMA y otros) ....... 53   (sin cambio)
bridges VERIFIED .......................  3   (sin cambio)
assertions ............................ 614   (sin cambio)
identifiers RETIRED (F-041) ............  6   (sin cambio)
corridas RUNNING .......................  0
```

**Ninguna fila fue modificada en este ciclo.** El único cambio es un trigger.

---

## 6. Findings nuevos

**Ninguno.**

A14 (usar la assertion de otra entidad) apareció durante la fase A, pero es una
variante de la misma raíz —el desacople `assertion` ↔ `identifier`— y quedó dentro
del alcance de F-045 y de su contrato, no como finding separado.

---

## 7. Lo que este ciclo NO cierra

**F-044** sigue abierto: `identity_v1.source` no tiene trigger ni historial, y el
owner puede elevar una fuente a `AUTHORITATIVE` sin dejar rastro. El trigger nuevo
**mitiga parcialmente** —re-verifica la política en el punto de uso, así que una
política adulterada tiene que engañar a dos lugares en vez de uno— pero **no lo
cierra**: si `source.authoritative_for` se altera, ambos triggers la aceptan.

**F-043** (Market tipifica `EMPTY` como `FAILED`) y **F-047** (bridges `CANDIDATE`
vigentes junto a su ratificación) siguen abiertos, fuera del alcance de este ciclo.

**No se declara homologación.** Este gate cierra un bloqueador, no el sistema.
