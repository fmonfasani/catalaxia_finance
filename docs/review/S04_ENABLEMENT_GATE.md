# SEC S04 — GATE DE HABILITACIÓN

**Fecha:** 2026-08-26
**Veredicto:** `S04_ENABLED` — habilitado desde el checkpoint S03 existente.
**Alcance:** se habilita el gate. **S04 no se ejecutó: no existe todavía como script.**

---

## 1. Precondición F-009 — CERRADA

### Evidencia previa (auditoría, no suposición)

`pg_stat_activity`: **0 sesiones** sobre la base. Ninguna corrida seguía viva.
`engine.runs`: 28 corridas · OK 8 · ABORTED 7 · BLOCKED 6 · **RUNNING 7**.

Las 7 en RUNNING **no eran un grupo homogéneo**. Auditadas una por una aparecen dos causas
distintas, y marcarlas todas igual habría borrado esa diferencia.

### Grupo A — 5 corridas que murieron en el arranque

| run_id | etapa | inicio | sin actividad |
|---|---|---|---|
| `e004ed88…` | S03_parse | 2026-08-24 21:37 | 27,4 h |
| `e65a3c6a…` | S03_parse | 2026-08-25 04:13 | 20,8 h |
| `eccd5fb3…` | S03_parse | 2026-08-25 04:17 | 20,7 h |
| `b4a2b220…` | S03_parse | 2026-08-25 04:26 | 20,6 h |
| `973b7e9e…` | S03_parse | 2026-08-25 04:36 | 20,4 h |

Evidencia idéntica en las cinco: traza completa `READY | RUNNING`, la última transición a
**milisegundos** del arranque, 0 checkpoints, `report IS NULL`, `finished_at IS NULL`.
Nunca produjeron nada.

### Grupo B — 2 corridas que hicieron el trabajo y murieron al persistir

| run_id | etapa | traza | gate |
|---|---|---|---|
| `f8b8c389…` | S03_parse | `READY\|RUNNING\|VALIDATING\|PASSED\|CHECKPOINTED` | **PASS** |
| `39d072db…` | C3_CNV_fetch | `READY\|RUNNING\|VALIDATING\|PASSED\|CHECKPOINTED` | **PASS** |

Llegaron a `CHECKPOINTED` con gate `PASS`, **pero `report IS NULL` y `finished_at IS NULL`
en todas sus filas.** El contraste lo da una corrida que sí cerró (`971ce5d9…`): su fila
`CHECKPOINTED` tiene report y `finished_at` poblados.

**Causa raíz.** En `s03_parse_ypf.py` las transiciones `PASSED` y `CHECKPOINTED` se registran
(~línea 620) **antes** del bloque `with engine.begin()` que persiste el report y el
checkpoint (~646) y **antes** de `finish_run` (~665). El proceso murió en ese tramo. El
estado de **etapa** quedó adelantado respecto del estado de **corrida**.

Además, sus checkpoints fueron **reasignados** a corridas posteriores por el
`ON CONFLICT … DO UPDATE SET run_id = EXCLUDED.run_id`:

```
checkpoint 971ce5d999a2499b-s03  -> run 971ce5d9… (OK, 13:56)
checkpoint 8db8692ebce9439c…     -> run eb05375b… (OK, 13:52)
```

Aunque hubieran cerrado, no son dueñas de ningún artefacto.

**Se marcaron `ABORTED`, no `OK`.** Llegar a `CHECKPOINTED` sin persistir el report no es
completar el contrato de la etapa; declararlas `OK` sería afirmar un cierre que no ocurrió.
**Ninguna corrida con evidencia de estar viva fue tocada — no la había.**

### Estado posterior

```
ABORTED 14 · BLOCKED 6 · OK 8 · RUNNING 0
corridas sin finished_at: 0
```

`migrations/engine/013_f009_cierre_corridas_huerfanas.sql` incluye una guarda que **falla la
migración** si queda alguna `RUNNING` sin auditar, en vez de cerrarlas en bloque.

### Prevención de recurrencia

`engine/db.py` gana dos piezas:

- **`run_scope()`** — context manager con el cierre en `finally`. Si el cuerpo explota, la
  corrida queda `ABORTED` con su motivo. **Obligatorio para S04 en adelante.**
- **`corridas_huerfanas()`** — detecta corridas `RUNNING` sin actividad reciente cruzando
  contra `pg_stat_activity`. Se llama al arrancar una etapa: si el pipeline dejó huérfanas,
  hay que verlo antes de generar más, no 20 horas después.

`tests/test_engine_run_lifecycle.py` (5 tests) incluye uno que mata el cuerpo a propósito y
verifica que la corrida quede `ABORTED`.

---

## 2. Precondición: el checkpoint S03 está íntegro

Verificación **independiente**: se reimplementó la especificación de `hash_out` desde el
código fuente (`s03_parse_ypf.py:637` — `sha256` del JSON ordenado de los cinco totales) y se
recalculó contra la base actual.

```
conteos actuales parsed.*  facts 67.084 · contexts 23.478 · units 369
                           concepts 13.412 · relations 146.028
hash_out en el checkpoint  60ff8e1aecd373acd537c92770038877fc4b2ec6412add648302784a08a4652e
hash_out recalculado       60ff8e1aecd373acd537c92770038877fc4b2ec6412add648302784a08a4652e
COINCIDE                   True
gate                       PASS (9/9 checks)
cobertura                  27 esperados / 27 parseados / 0 rechazados
violaciones de provenance  0
git_commit del artefacto   444ee1ad0e1b092c79ce055ded0b993fbc55822d
corrida dueña              971ce5d999a2499ba6af136cb2c87569 · status OK
```

El artefacto que S04 va a consumir es el que dice ser. **No hace falta repetir S01–S03.**

---

## 3. Precondición: el cruce CNV → Identity v1 está validado

`9.305/9.305` presentaciones (100 %) atribuidas a Central Puerto — **por el CIK embebido en
la clave legacy `CIK:0001717161`, no por CUIT.**

`tests/test_cnv_identity_link.py` (9 tests) valida que el cruce **no mienta**:

| Verifica | Resultado |
|---|---|
| Toda atribución CNV es `CANDIDATE` / `WEAK` / no autoritativa | ✔ |
| `CNV_PORTAL` sigue siendo `DISCOVERY_ONLY` con `authoritative_for` vacío | ✔ |
| Ningún bridge quedó `VERIFIED` | ✔ (0) |
| Ningún CUIT fue inventado | ✔ (0 entidades con CUIT; reviews siguen abiertas) |
| Ninguna decisión humana escrita por un proceso | ✔ (0) |
| La vía declarada coincide con la evidencia (el CIK está realmente en la clave) | ✔ |
| Una vía débil no se disfraza de fuerte | ✔ |
| El resolver es idempotente y no crea entidades | ✔ |
| El cruce no modifica CNV | ✔ |

**Suite completa: 63 passed.**

---

## 4. Qué queda habilitado, y qué NO

**Habilitado:** S04 puede construirse y ejecutarse tomando como entrada el checkpoint
`971ce5d999a2499b-s03` (`artifact_ref: pg://parsed.* + fs://outputs/docs/fase_s03`).
**No se repiten S01, S02 ni S03.**

**No habilitado, y hay que decirlo con todas las letras: S04 no existe.**
`scripts/engine/` tiene `s00`, `s01`, `s02`, `s03` y los de CNV/Identity. No hay `s04_*.py`.
Este documento **habilita el gate**, no ejecuta una etapa. Construir S04 es trabajo pendiente
con especificación propia.

### Condiciones que S04 debe cumplir al escribirse

1. **Usar `run_scope()`.** No repetir el patrón de `finish_run` suelto al final: es la causa
   raíz de F-009.
2. **Persistir el report en la MISMA transacción que la transición a `CHECKPOINTED`.** Hoy
   van separadas y esa grieta es por donde se colaron las 2 corridas del grupo B.
3. **Llamar `corridas_huerfanas()` al arrancar** y abortar si encuentra alguna.
4. **Declarar `input_checkpoint_id = '971ce5d999a2499b-s03'`** y validar su `hash_out` antes
   de consumir `parsed.*`.
5. **Correr como `catalaxia_engine`** (no superusuario, F-025).
6. **Resolver identidad contra `identity_v1`**, no contra `identity.entities` ni `dim_entity`.

---

## 5. Estado de los otros dos workstreams

**MARKET — bloqueado por decisión, no por defecto.** M23 masivo no se ejecuta hasta resolver
F-014 (`ticker_canonico` repite el ticker local en la fila del ADR) y F-013 (semántica de
checkpoint divergente), y después un smoke test antes de escalar a los 584 instrumentos.
F-001 ya está cerrado: Market no puede escribir en producción por accidente.

**IDENTITY — sin backfill masivo.** Los 4 CUIT pendientes siguen pendientes; ratificarlos es
un acto humano (`identity_v1_ratificar.py`). D-I-04 sigue abierta (F-020) y F-024 (el CIK de
Banco Macro en la columna `cuit`) bloquea la Fase 2.
