# CONTRATO — F-044 · LA POLÍTICA DE AUTORIDAD NO PUEDE SER LA ÚNICA GARANTÍA

**Fecha:** 2026-08-28 · **Escrito antes de modificar nada.**
**Alcance:** exclusivamente F-044. No toca SEC, S03, S04, Market, CNV, M23, BYMA,
backfill, bridges, F-041, F-042, F-043, F-045, F-046 ni F-047.

---

## 0. El problema, reproducido

`identity_v1.source` es una tabla de **datos**, mutable por el owner con un `UPDATE`
ordinario. Todas las garantías de autoridad la consultan. Reproducido en transacción
revertida:

| política | escritura por `catalaxia_engine` | resultado |
|---|---|---|
| **intacta** | `LEGACY_DIM_ENTITY` → CIK / LEI / CUIT | los 3 bloqueados por `tg_fuente_autoritativa_para_el_tipo` |
| **adulterada** | `LEGACY_DIM_ENTITY` → **CIK** | **ENTRA** |
| **adulterada** | `LEGACY_DIM_ENTITY` → **LEI** | **ENTRA** |
| **adulterada** | `LEGACY_DIM_ENTITY` → CUIT | bloqueado por `ck_cuit_exige_evidencia_estructurada` |
| **adulterada** | `CNV_PORTAL` → **CIK** | **ENTRA** |
| **adulterada** | `DERIVED_RULE` → **LEI** | **ENTRA** |

**La asimetría es el hallazgo.** El CUIT sobrevive porque `ck_cuit_exige_evidencia_estructurada`
(F-037) **enumera las fuentes literalmente** (`CASE source_id … ELSE false`) y **no
consulta `source`**. CIK y LEI no tienen nada equivalente.

Ni siquiera el trigger de F-045 ayuda: consulta `source` igual, así que una política
adulterada convence a los dos triggers.

---

## 1. La política, por tipo de identificador

Medida contra la base, no supuesta. Uso real hoy:

| `id_type` | **establece** (`VERIFIED`) | **corrobora** | **descubre** | evidencia estructurada obligatoria |
|---|---|---|---|---|
| **CIK** | `SEC_REGISTRY` (512 filas), `SEC_20F` (1), `HUMAN` (0 hoy, permitido) | `LEGACY_DIM_ENTITY` | — | no exigida hoy (deuda F-041, 1 caso) |
| **LEI** | `GLEIF` (4), `HUMAN` | — | — | no exigida hoy |
| **CUIT** | `GLEIF` (6), `SEC_20F`, `AFIP`, `HUMAN` | `LEGACY_DIM_ENTITY` (53 `CANDIDATE`) | `CNV_PORTAL` | **sí** — `ck_cuit_exige_evidencia_estructurada` |

`CNV_PORTAL`, `DERIVED_RULE` y `MARKET_CATALOG` no establecen **ningún** tipo.

### Rol que puede escribir

Sólo `catalaxia_engine` escribe identidad en operación. Su GRANT: `INSERT` en
`assertion` e `identifier`; `UPDATE (superseded_by, valid_to)` en `assertion` y
`UPDATE (status, valid_to)` en `identifier`. **`SELECT` únicamente sobre `source`.**

### Operaciones permitidas

Insertar assertions e identificadores; retirar identificadores (`valid_to`);
encadenar assertions (`superseded_by`); proponer `CANDIDATE`; ratificar por
`HUMAN_DECISION` con persona y motivo.

### Operaciones que deben ser imposibles **aunque `source.authoritative_for` haya sido adulterado**

> Establecer un `CIK`, `LEI` o `CUIT` autoritativo desde una fuente que el contrato
> no reconoce para ese tipo — **con independencia de lo que diga `source`**.

---

## 2. Regla fundamental

> **La garantía de identidad no puede depender exclusivamente de una tabla mutable
> por el owner.**

Nótese *exclusivamente*: la política sigue viviendo en `source` como documentación
operativa y como primera barrera. Lo que se agrega es una segunda barrera que **no la
consulta**.

---

## 3. Alternativas evaluadas

### A) CHECK estructural — enumerar las fuentes en el constraint

```sql
NOT (subject_type='ENTITY_IDENTIFIER' AND status='VERIFIED' AND left_ref LIKE 'CIK:%')
OR source_id IN ('SEC_REGISTRY','SEC_20F','HUMAN')
```

**A favor:** no consulta `source`, así que adulterarla **deja de servir de nada**.
Declarativo, sin código. Es **el patrón que el propio proyecto ya usa y que ya
demostró funcionar**: es exactamente por qué el CUIT sobrevivió al ataque.
**En contra:** la política queda en dos lugares; cambiarla exige una migración.

### B) Trigger con política inmutable en el cuerpo

Equivalente en efecto, pero código imperativo donde alcanza una expresión. Sin
ventaja sobre A y con más superficie.

### C) Tabla de política protegida (trigger de inmutabilidad sobre `source`)

**Hace más difícil adulterar la tabla, pero no elimina la dependencia.** El owner
puede `DISABLE` el trigger igual que puede `DROP` un CHECK. Y sobre todo: no
responde la regla fundamental, porque la garantía **sigue dependiendo de la tabla**.

### D) A + C

C es complementaria (haría visible el intento), no necesaria. Agrega superficie sin
cerrar nada que A no cierre.

### E) Otra

Ninguna alternativa mínima demostrablemente equivalente.

**Elección: A.** No porque sea la más fuerte en abstracto, sino porque es la única que
**elimina la dependencia** en vez de protegerla, y es el mínimo cambio que cierra el
camino reproducido.

---

## 4. Sobre el límite honesto de A

El owner puede hacer `ALTER TABLE … DROP CONSTRAINT`. **Ninguna garantía en PostgreSQL
sobrevive a su propio owner.** La corrección no pretende lo contrario.

Lo que cambia es la **naturaleza del acto**:

| | adulterar `source` | quitar un CHECK |
|---|---|---|
| tipo de operación | `UPDATE` de datos | **DDL** |
| ¿cambia el schema? | no | **sí** |
| ¿lo detecta un diff de schema? | **no** | sí |
| ¿parece operación normal? | **sí** | no |
| ¿podría hacerlo un script de mantenimiento sin querer? | **sí** | prácticamente no |

Esa diferencia es la sustancia de la corrección, y se declara aquí para que el cierre
no se lea como algo que no es.

---

## 5. Lo que la corrección NO debe romper

Verificado contra la base **antes** de escribir el constraint:

```
ENTITY_IDENTIFIER VERIFIED con left_ref .................. 523
  ...que NO cumplirian la regla propuesta ................ 0     <-- se puede VALIDAR
bridges VERIFIED (subject_type distinto, no alcanzados) .. 3
assertions con left_ref NULL (F-046, no alcanzadas) ...... 6
CANDIDATE / REVIEW_REQUIRED (status distinto) ............ 63
```

### El detalle que casi rompe los bridges

Los 3 bridges `VERIFIED` tienen `left_ref = 'CIK:SEC:…'` y `source_id = 'HUMAN'`. Un
CHECK sobre `left_ref LIKE 'CIK:%' AND status='VERIFIED'` **los alcanzaría**.

Por eso el predicado exige además `subject_type = 'ENTITY_IDENTIFIER'`.

> Observación registrada, fuera de alcance: `ck_cuit_exige_evidencia_estructurada`
> **no** condiciona por `subject_type`. Hoy no falla sólo porque ningún bridge tiene
> `left_ref` de tipo `CUIT`. Es frágil, pero corregirlo es tocar F-037, prohibido en
> este ciclo.

### Compatibilidad

- **F-045**: intacto. El CHECK actúa sobre `assertion`; el trigger sobre `identifier`.
- **F-036/F-037**: intactos. No se toca `ck_cuit_exige_evidencia_estructurada`.
- **`CANDIDATE`**: no alcanzados (`status <> 'VERIFIED'`). Los 53 CUIT legacy siguen entrando.
- **Retiros y supersede**: no alcanzados — el CHECK sólo mira columnas inmutables que ya
  existen en la fila; `valid_to` y `superseded_by` no participan del predicado.
- **Ratificaciones humanas**: `HUMAN` está en ambas listas.
- **Datos históricos**: 0 filas incumplen, así que el constraint se puede **VALIDAR**
  sin reescribir nada.
