# F-044 — GATE

**2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
Evidencia: `docs/review/F044_AUDIT.md` · `docs/architecture/F044_CONTRACT.md`
Reproducible: `python scripts/engine/audit_f044.py`

---

## DICTAMEN: **F-044 = CLOSED_WITH_NOTES**

El camino reproducido está cerrado y verificado por auditoría independiente en tres
estados del mundo. Las dos notas están abajo y ninguna reabre el finding.

**No es `CLOSED` liso** por la nota 1. **No es `OPEN`** porque la garantía no es
administrativa: es un CHECK en el schema que actúa sobre todos los roles y no consulta
la tabla mutable.

---

## 1. Qué garantía quedó implementada

`identity_v1.ck_politica_estructural_cik_lei` —
`migrations/engine/031_f044_politica_estructural_cik_lei.sql`

```sql
NOT (subject_type='ENTITY_IDENTIFIER' AND status='VERIFIED')
OR left_ref IS NULL
OR CASE split_part(left_ref, ':', 1)
     WHEN 'CIK' THEN source_id IN ('SEC_REGISTRY','SEC_20F','HUMAN')
     WHEN 'LEI' THEN source_id IN ('GLEIF','HUMAN')
     ELSE TRUE
   END
```

**Enumera las fuentes en el schema y no consulta `identity_v1.source`.** Ése es todo
el punto: adulterar la política deja de servir de nada.

Aplicado **validado** (`convalidated = t`), no `NOT VALID`: se midió antes que de las
523 assertions `ENTITY_IDENTIFIER VERIFIED` con `left_ref`, **0 incumplen**. No hay
historia que perdonar.

### El detalle que casi rompe los bridges

Los 3 bridges `VERIFIED` tienen `left_ref = 'CIK:SEC:…'` y `source_id = 'HUMAN'`. Un
CHECK sobre `left_ref LIKE 'CIK:%' AND status='VERIFIED'` **los habría alcanzado y
roto**. Por eso el predicado exige además `subject_type = 'ENTITY_IDENTIFIER'`. Se
detectó midiendo el uso real antes de escribir el constraint, no después.

### Por qué se eligió CHECK y no las otras alternativas

De las cinco evaluadas, sólo A **elimina la dependencia** en vez de protegerla. La
opción C (trigger de inmutabilidad sobre `source`) haría más difícil adulterar la
tabla, pero la garantía **seguiría dependiendo de ella** — que es justo lo que la regla
fundamental prohíbe.

---

## 2. Ataques rechazados

**19/19** en el banco (`f044_bench.py`), dos estados del mundo, cada uno con la
garantía nombrada. Y **12/12** en la auditoría independiente, en tres estados.

Los dos que definen el finding:

| | antes | ahora |
|---|---|---|
| política adulterada → **CIK** (rol operativo) | **ENTRABA** | `ck_politica_estructural_cik_lei` |
| política adulterada → **LEI** (rol operativo) | **ENTRABA** | `ck_politica_estructural_cik_lei` |

Probado además con la política **adulterada y comiteada**, escribiendo con
`catalaxia_engine` desde otra conexión, y con restauración verificada por huella
(`a60ece0c4fdca2fd9000` → idéntica).

Y con el **owner escribiendo**: también bloqueado. El CHECK es una restricción de
tabla, no un permiso.

---

## 3. Mutaciones realizadas

| garantía eliminada | ataques que reaparecen |
|---|---|
| `ck_politica_estructural_cik_lei` | **T1, T2** — exactamente los dos que motivaron F-044, y ningún otro |
| `tg_identifier_coherente_con_assertion` (F-045) | T7–T10, en ambos estados (8 casos) |
| `ck_cuit_exige_evidencia_estructurada` (F-037) | **T3** — política adulterada → CUIT |

Todas restauradas y verificadas: las 4 garantías activas, banco 19/19.

---

## 4. Las dos notas

### Nota 1 — la cobertura del CUIT vive en F-037, no acá

El CHECK nuevo deja pasar el CUIT (`ELSE TRUE`) **deliberadamente**: duplicar la
política del CUIT en dos constraints crearía el riesgo de que diverjan, y F-037 está
fuera del alcance de este ciclo.

La consecuencia, demostrada por la mutación 3: **si alguien toca
`ck_cuit_exige_evidencia_estructurada` pensando que sólo afecta la evidencia, también
está tocando la política de fuente del CUIT.** Ese constraint hace dos trabajos.

No reabre F-044 —el CUIT **está** protegido por algo que no consulta `source`, que era
el requisito— pero es un acoplamiento que conviene conocer antes de modificar F-037.

### Nota 2 — el límite estructural

El owner puede `ALTER TABLE … DROP CONSTRAINT`. **Ninguna garantía en PostgreSQL
sobrevive a su propio owner**, y este cierre no pretende lo contrario.

Lo que cambia es la naturaleza del acto:

| | adulterar `source` | quitar el CHECK |
|---|---|---|
| operación | `UPDATE` de datos | **DDL** |
| ¿cambia el schema? | no | **sí** |
| ¿lo ve un diff de schema? | **no** | sí |
| ¿parece mantenimiento normal? | **sí** | no |

Esa diferencia es la sustancia del cierre. No es una garantía administrativa —no
depende de que nadie haga algo—: es una garantía estructural con el límite que toda
garantía estructural tiene.

---

## 5. Regresiones

**Ninguna.** Suite completa 198/198. `backfill_cik --dry-run`: 512, 0 errores, hash
idéntico. Las 9 operaciones legítimas —CIK, LEI, `CANDIDATE`, `REVIEW_REQUIRED`,
retiro, supersede en dos pasos, ratificación humana— verificadas una por una.

**Datos: cero cambios.** 525 entidades · 614 assertions · 574 identifiers vigentes ·
513 CIK · 3 CUIT · 11 reviews · 1 conflict · 3 bridges `VERIFIED`. El único cambio en
la base es un CHECK.

---

## 6. Findings nuevos

**Ninguno.**

La nota 1 (el acoplamiento de `ck_cuit_exige_evidencia_estructurada`) es una
propiedad del diseño existente que esta auditoría midió, no un defecto nuevo. Se
registra para que una modificación futura de F-037 la tenga en cuenta.

Observación menor ya registrada en el contrato: ese constraint tampoco condiciona por
`subject_type`; hoy no falla sólo porque ningún bridge tiene `left_ref` de tipo `CUIT`.
Es frágil, pero corregirlo es tocar F-037, prohibido en este ciclo.

---

## 7. Alcance

Este ciclo **no decide la homologación integral** y no la declara. Cierra un finding.

El estado de los demás no cambió: F-041 y F-046 siguen como deuda histórica no
reproducible; F-043 como limitación de producto; F-047 como documentación.
