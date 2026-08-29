# PRE_HOMOLOGATION_FINDINGS — F-041 / F-043 / F-044 / F-046 / F-047

**2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
Cada conclusión se **reprodujo** contra la base; ninguna se tomó de los documentos.
Toda prueba mutacional corrió en transacción revertida. **No se implementó ningún fix.**
**Reproducible:** `python scripts/engine/audit_pre_homologacion.py`

---

## Fase A — Inventario reproducido

| finding | ¿existe? | instancias medidas |
|---|---|---|
| F-041 | **sí** | 1 CIK autoritativo sin `source_facts` |
| F-043 | **sí** | `EMPTY` emitido **0** veces; 14 filas `FAILED` con `error_type='EMPTY'` |
| F-044 | **sí** | `identity_v1.source`: **0 triggers**, sin historial |
| F-046 | **sí** | 6 assertions autoritativas con `left_ref NULL` |
| F-047 | **sí** | 3 pares con `CANDIDATE` y `VERIFIED` vigentes a la vez |

### Las nueve preguntas

| | F-041 | F-043 | F-044 | F-046 | F-047 |
|---|---|---|---|---|---|
| 1. ¿existe hoy? | sí | sí | sí | sí | sí |
| 2. ¿corrupción nueva? | **no** | **no** | no por `engine` | **no** | **no** |
| 3. ¿identidad incorrecta? | **no** | n/a | **sí, con owner** | **no** | **no** |
| 4. ¿rompe provenance? | **no** | **no** | **no** | **no** | **no** |
| 5. ¿duplica entidades? | **no** | **no** | **no** | **no** | **no** |
| 6. ¿explotable por `catalaxia_engine`? | **no** | **no** | **no** | **no** | **no** |
| 7. ¿sólo datos existentes? | sí | no | no | sí | sí |
| 8. ¿limitación de cobertura/producto? | no | **sí** | no | no | no |
| 9. ¿deuda histórica? | **sí** | no | no | **sí** | no |

---

## Fase B — F-043 · los 7 «FAILED» de M23

### Lo reproducido

```
estados realmente usados en market_raw_runs .... {'SUCCESS': 577, 'FAILED': 14}
`EMPTY` emitido alguna vez ..................... 0
filas FAILED con error_type='EMPTY' ............ 14  (7 instrumentos × 2 intentos)
filas FAILED que declaran datos (sha256/rows) ... 0
precios escritos para los 7 .................... 0
directorios RAW en disco para los 7 ............ 0
instrumentos que --resume reintentaría ......... 7
```

### ¿`EMPTY` debe ser distinto de `FAILED`? **Sí.**

El CHECK del esquema ya define `EMPTY` como estado propio, y el código **nunca lo
emite**: `m2_fetch_engine.py:229` escribe `FAILED` y manda `"EMPTY"` al log. El
esquema modela la distinción; el escritor la descarta.

Y hay una tercera categoría que **ninguno de los dos** representa: los 7 no son
`SUCCESS` (no hay datos), no son `PARTIAL` (la cuarentena filtra por ese estado y no
los toca), y técnicamente no fallaron. Quedan invisibles como categoría.

### ¿Reintentarlos indefinidamente es correcto? **No se puede decidir hoy.**

`m6_scale.ya_exitosos()` filtra por `status='SUCCESS'`, así que `--resume` los
re-pide siempre. Si la ausencia es **transitoria** (la fuente no respondió), reintentar
es correcto; si es **permanente** (el símbolo no existe en Yahoo), es desperdicio
indefinido.

**El sistema no puede distinguir esos dos casos porque no registra la diferencia.**
Ese es el defecto real.

### ¿Clasificación, persistencia o cobertura? **Clasificación.**

La persistencia funciona (F-038 verificado: 591 filas, hashes coincidentes). La
cobertura es un hecho externo. Lo que falla es **cómo se tipifica** ese hecho.

### Qué debería hacer `--resume` (propuesta, no aplicada)

Registrar `EMPTY` cuando la fuente responde sin filas, y que `--resume` lo trate como
terminal-por-ahora: reintentable bajo `--force` o tras una ventana temporal, no en
cada corrida.

### ¿Pérdida, duplicación o corrupción? **Ninguna.**

0 filas `FAILED` declaran datos · 0 precios escritos · 0 RAW en disco. Las 2 filas por
instrumento son los dos intentos, que es el diseño de bitácora, no duplicación.

**Clasificación: `PRODUCT LIMITATION` + `DOCUMENTATION DEBT`.** No es blocker.

---

## Fase C — F-044 · la política de autoridad

### ¿Puede `catalaxia_engine` adulterarla? **No.**

Probadas las tres rutas, todas `permission denied`:

```
UPDATE identity_v1.source ... -> permission denied for table source
INSERT INTO identity_v1.source -> permission denied for table source
DELETE FROM identity_v1.source -> permission denied for table source
```

Su GRANT sobre `source` es **`SELECT`** y nada más.

### ¿F-045 impide la explotación, o sólo agrega una barrera? **Sólo agrega una barrera.**

Éste es el experimento que importa. Con la política **ya adulterada** por el owner
(`LEGACY_DIM_ENTITY → AUTHORITATIVE para {CUIT, CIK}`), en transacción revertida:

| intento | resultado |
|---|---|
| CUIT autoritativo desde `LEGACY_DIM_ENTITY` | **bloqueado** por `ck_cuit_exige_evidencia_estructurada` |
| **CIK autoritativo desde `LEGACY_DIM_ENTITY`** | **ENTRÓ** |

Los dos triggers de F-045 consultan `source`, así que **una política adulterada los
convence a ambos**. Lo que salva al CUIT es el CHECK de F-037, que enumera las fuentes
**literalmente** (`ELSE false`) y por eso es inmune a la adulteración.

**Hay una asimetría: el CUIT tiene esa red; el CIK no.**

### Respuestas

| pregunta | respuesta |
|---|---|
| ¿puede generar identidad incorrecta? | **sí, para CIK**, con rol owner |
| ¿puede convertir una fuente no autoritativa en autoritativa? | **sí**, con rol owner |
| ¿puede generar CUIT incorrecto? | **no** — el CHECK de F-037 lo impide |
| ¿puede crear un bridge incorrecto? | no por esta vía: exige `HUMAN_DECISION` y persona |
| ¿afecta datos existentes? | **no** — las 520 filas actuales no cambian |
| ¿requiere fix antes de homologar? | **no según la regla del encargo** (no es alcanzable por `catalaxia_engine` ni en operación normal), **sí para homologación integral con garantía completa** |

**Clasificación: `NON-BLOCKING` con riesgo residual explícito.**

---

## Fase D — F-047 · los bridges

### Reconstrucción de las tres ratificaciones

| CIK | LEI | `VERIFIED` | `CANDIDATE` |
|---|---|---|---|
| 0000904851 (YPF) | …U18U5U53 | **#342** Federico, `STRONG`, con motivo | #96 `proc:identity_v1_pilot`, `WEAK` |
| 0001717161 (CEPU) | …6B7VNR38 | **#343** Federico, `STRONG`, con motivo | #98 ídem |
| 0000931427 (TGS) | …FQYSW596 | **#344** Federico, `STRONG`, con motivo | #101 ídem |
| 0001114700 (GGAL) | …XV5G3C23 | — | #100 ídem — **sin ratificar, correcto** |

Verificado: bridges `VERIFIED` **contradictorios entre sí: 0** · `VERIFIED` mal
formados (sin `HUMAN_DECISION`, firmados por proceso, o sin motivo): **0**.

### Qué significa que los candidatos no estén superseded

`superseded_by` significa **«reemplazado por»**. El candidato no fue reemplazado: fue
**confirmado**. Ambas assertions afirman **el mismo par** — no se contradicen.

Y el código lo dice explícitamente (`engine/identity_v1.py:578-580`):

> *«idempotencia (F-023): una propuesta automática ya vigente no se duplica. Una
> ratificación humana sí se registra siempre: es un acto nuevo.»*

La única consulta de bridges **sin filtro de `status`** es justamente la de
idempotencia, y filtra por `method`, así que nunca confunde una propuesta con una
ratificación. Todos los demás consumidores (`smoke_cross_cnv`, `audit_cross_cnv`,
`impacto_y_byma`, `audit_backfill_cik`, `identity_v1.py:616`) filtran por
`status='VERIFIED'`.

### Corrección de mi propio informe de homologación

Registré F-047 como *«el candidato no se supersedió»*, insinuando un defecto de
higiene. **Reproducido, no lo es.** La coexistencia es intencional, está documentada
en el código y no produce ambigüedad para ningún consumidor actual.

- inconsistencia histórica: **no**
- defecto funcional actual: **no**
- riesgo de nuevas duplicaciones: **no** (`assert_bridge` es idempotente por método)
- problema meramente documental: **sí** — el modelo no distingue «supersedido» de
  «confirmado», y un consumidor futuro que cuente bridges vigentes sin filtrar vería
  7 donde hay 3 establecidos

**Clasificación: `DOCUMENTATION DEBT`.**

---

## Fase E — F-041 / F-046

### ¿Siguen intactas? Sí, y no hay camino operativo para tocarlas

| intento | `catalaxia_engine` | owner |
|---|---|---|
| `UPDATE left_ref` de las 6 | permission denied | `tg_assertion_inmutable` |
| `UPDATE source_facts` de F-041 | permission denied | `tg_assertion_inmutable` |
| `DELETE` una de las 6 | permission denied | `tg_no_borrar_assertion` |
| retirar su identifier (legítimo) | **ACEPTADO** | ACEPTADO |

**Doble barrera**: GRANT de columna para la aplicación, trigger para el owner. Y el
retiro legítimo sigue disponible — sin esa excepción, las 6 quedarían inmovilizadas y
el supersede de F-041 se rompería.

### ¿F-045 impide nuevos casos? Sí

```
INSERT identifier autoritativo con assertion de left_ref NULL
  -> F-045: la assertion 1613 no declara que identificador establece
```

### ¿Riesgo de corrupción nueva? Ninguno

Incoherencias de tipo en toda la base: **0**. Las 6 declaran `SEC_REGISTRY` y
sostienen `CIK`, y `SEC_REGISTRY` **es** autoritativa para `CIK`: con `left_ref`
habrían pasado igual. El defecto es de procedimiento, no de contenido.

**Clasificación: `NON-BLOCKING` (deuda histórica no reproducible).**

---

## Fase F — Auditoría independiente

`scripts/engine/audit_pre_homologacion.py` — reconstruye desde `pg_trigger`,
`pg_constraint`, `information_schema.column_privileges`, `identity_v1`,
`market_raw_runs` y los artefactos en disco.

Hallazgo lateral de la propia auditoría: **`catalaxia_engine` no tiene permisos sobre
las tablas de Market** (`permission denied for table market_raw_runs`). La separación
de roles entre Identity y Market es real y verificada; para leer el estado de M23 se
usó el rol admin, sólo `SELECT`.

| finding | veredicto | riesgos activos |
|---|---|---|
| F-041 | `PASS_WITH_NOTES` | ninguno |
| F-043 | `PASS_WITH_NOTES` | ninguno |
| F-044 | `PASS_WITH_NOTES` | ninguno *por `catalaxia_engine`* |
| F-046 | `PASS_WITH_NOTES` | ninguno |
| F-047 | `PASS_WITH_NOTES` | ninguno |

**BLOCKERS: ninguno.**
