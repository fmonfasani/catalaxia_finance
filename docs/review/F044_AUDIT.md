# F-044 — AUDITORÍA

**2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
**Reproducible:** `python scripts/engine/f044_bench.py` · `python scripts/engine/audit_f044.py`

---

## Fase A — Reproducción exacta

Dos estados del mundo, escribiendo siempre con el rol operativo.

### Antes de la corrección

| política | ataque | resultado | garantía |
|---|---|---|---|
| intacta | `LEGACY_DIM_ENTITY` → CIK / LEI / CUIT | bloqueados | `tg_fuente_autoritativa_para_el_tipo` |
| intacta | `CNV_PORTAL` → CIK · `DERIVED_RULE` → LEI | bloqueados | ídem |
| **adulterada** | `LEGACY_DIM_ENTITY` → **CIK** | **ENTRA** | ninguna |
| **adulterada** | `LEGACY_DIM_ENTITY` → **LEI** | **ENTRA** | ninguna |
| **adulterada** | `LEGACY_DIM_ENTITY` → CUIT | bloqueado | `ck_cuit_exige_evidencia_estructurada` |
| **adulterada** | `CNV_PORTAL` → **CIK** | **ENTRA** | ninguna |
| **adulterada** | `DERIVED_RULE` → **LEI** | **ENTRA** | ninguna |

**La asimetría es el hallazgo.** El CUIT sobrevive porque su CHECK **enumera las
fuentes literalmente** y no consulta `source`. CIK y LEI no tenían equivalente.

Ni el trigger de F-045 ayudaba: consulta `source` igual, así que una política
adulterada convence a los dos triggers.

---

## Fase C — Matriz de amenazas

| | ataque | precondición | rol | camino | garantía **antes** | ¿pasa? | garantía **ahora** | ¿pasa? |
|---|---|---|---|---|---|---|---|---|
| 1 | fuente incorrecta → CIK | — | engine | INSERT | `tg_fuente_autoritativa_para_el_tipo` | no | ídem | **no** |
| 2 | fuente incorrecta → LEI | — | engine | INSERT | ídem | no | ídem | **no** |
| 3 | fuente incorrecta → CUIT | — | engine | INSERT | ídem | no | ídem | **no** |
| **4** | **política adulterada → CIK** | UPDATE `source` (owner) | engine | INSERT | **ninguna** | **SÍ** | `ck_politica_estructural_cik_lei` | **no** |
| **5** | **política adulterada → LEI** | ídem | engine | INSERT | **ninguna** | **SÍ** | `ck_politica_estructural_cik_lei` | **no** |
| 6 | política adulterada → CUIT | ídem | engine | INSERT | `ck_cuit_exige_evidencia_estructurada` | no | ídem | **no** |
| 7 | `left_ref` NULL | — | engine | INSERT | F-045 | no | F-045 | **no** |
| 8 | `left_ref` con tipo incorrecto | — | engine | INSERT | F-045 | no | F-045 | **no** |
| 9 | `left_ref` a otro identifier | — | engine | INSERT | F-045 | no | F-045 | **no** |
| 10 | `entity_key` diferente | — | engine | INSERT | F-045 | no | F-045 | **no** |
| 11 | `CANDIDATE` → `VERIFIED` | — | engine | UPDATE | GRANT de columna | no | ídem | **no** |
| 12 | UPDATE para esquivar | — | engine | UPDATE | GRANT de columna | no | ídem | **no** |
| 13 | escritura directa | — | **engine** | INSERT | parcial | **sí (4,5)** | completa | **no** |
| 14 | escritura como owner | política adulterada | **owner** | INSERT | ninguna | **sí** | `ck_politica_estructural_cik_lei` | **no** |
| 15 | eliminar/reemplazar provenance | — | ambos | UPDATE/DELETE | `tg_assertion_inmutable`, `tg_no_borrar_assertion` | no | ídem | **no** |

El ataque 14 es notable: **el CHECK bloquea también al owner al escribir**, porque es
una restricción de tabla, no un permiso.

---

## Fase F — Banco adversario · 19/19

`scripts/engine/f044_bench.py`, dos estados del mundo, cada ataque desde entidad
limpia y en transacción revertida, con la garantía identificada por nombre.

```
OK = 19    BYPASS = 0    OTRA_BARRERA = 0
```

### Nota de método

La primera pasada declaró una sola garantía esperada por ataque y reportó 3
`OTRA_BARRERA`. **La expectativa estaba mal, no el resultado**: con política intacta
la primera barrera es el trigger; con política adulterada el trigger queda convencido
y tiene que actuar el CHECK. Declarar una sola para ambos estados habría sido reportar
una garantía por otra. Corregido con expectativa **por estado**.

### La prueba decisiva: cross-role

El encargo pide escribir con `catalaxia_engine` bajo política adulterada. Eso no puede
hacerse en una sola transacción (el `UPDATE` no comiteado no lo ve la otra conexión).
Se hizo con **commit de la adulteración**, ataque con el rol operativo, y restauración
verificada por huella:

```
política original,   huella a60ece0c4fdca2fd9000
política ADULTERADA y COMMITEADA (owner)
  OK  LEGACY_DIM_ENTITY -> CIK    <- ck_politica_estructural_cik_lei
  OK  CNV_PORTAL        -> CIK    <- ck_politica_estructural_cik_lei
  OK  DERIVED_RULE      -> LEI    <- ck_politica_estructural_cik_lei
  OK  LEGACY_DIM_ENTITY -> CUIT   <- ck_cuit_exige_evidencia_estructurada
política restaurada, huella a60ece0c4fdca2fd9000  -> IDÉNTICA
```

---

## Fase G — Mutación

| mutación | ataques que reaparecen |
|---|---|
| quitar `ck_politica_estructural_cik_lei` | **T1** (política adulterada → CIK) y **T2** (→ LEI) |
| quitar `tg_identifier_coherente_con_assertion` (F-045) | T7, T8, T9, T10 — en **ambos** estados (8 casos) |
| quitar `ck_cuit_exige_evidencia_estructurada` (F-037) | **T3** (política adulterada → CUIT) |

La primera es la prueba exigida: **sin la garantía nueva, exactamente los dos ataques
que motivaron F-044 vuelven a pasar**, y ningún otro.

La tercera confirma algo que hay que declarar: **la cobertura del CUIT sigue viviendo
en F-037**, no en el CHECK nuevo, que lo deja pasar deliberadamente (`ELSE TRUE`) para
no duplicar la política en dos lugares que podrían divergir.

---

## Fase H — Regresión

**Suite completa: 198/198.** Cero regresiones.

`backfill_cik --dry-run`: 512 procesados, 0 errores, delta 0, hash de identidad
idéntico (`f0a38639982cd616`).

### Operaciones legítimas verificadas una por una

```
OK  CIK legítimo desde SEC_REGISTRY        OK  retirar el identifier
OK  anclar el identifier                   OK  supersede: assertion nueva
OK  LEI legítimo desde GLEIF               OK  supersede: encadenar la vieja
OK  CUIT CANDIDATE desde LEGACY            OK  ratificación humana (bridge)
OK  REVIEW_REQUIRED desde GLEIF
```

### Datos: cero cambios

```
entidades 525 · assertions 614 · identifiers vigentes 574 · CIK 513 · CUIT 3
reviews OPEN 11 · conflicts 1 · bridges VERIFIED 3
```

Idénticos al inicio del ciclo. **El único cambio es un CHECK.**

---

## Fase I — Auditoría independiente

`scripts/engine/audit_f044.py` — no importa `f044_bench` ni la capa de dominio.
Reconstruye desde `pg_trigger`, `pg_constraint`, `column_privileges` e
`identity_v1.source`, y reproduce en tres estados.

| pregunta | respuesta |
|---|---|
| 1. ¿política adulterada produce **CIK** incorrecto? | **NO** |
| 2. ¿produce **LEI** incorrecto? | **NO** |
| 3. ¿produce **CUIT** incorrecto? | **NO** |
| 4. ¿lo puede hacer `catalaxia_engine`? | **NO** |
| 5. ¿lo puede hacer el **owner**? | **NO** |
| 6. ¿la garantía depende de Python? | **NO** — es un CHECK declarativo |
| 7. ¿depende de una tabla mutable? | **NO** — enumera las fuentes en el schema |
| 8. ¿bypass por INSERT? | **NO** — 12 casos en 3 estados |
| 9. ¿bypass por UPDATE? | **NO** — 5 columnas, todas GRANT |
