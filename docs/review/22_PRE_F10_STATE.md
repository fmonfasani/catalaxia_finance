# 22 — Estado pre-F10 (baseline, solo lectura)

F9 cerrado (`STEP_20_STATUS = PASS_WITH_WARNINGS`, `NEXT_PHASE = F10`). Solo
lectura + este documento. Evidencia `[CÓDIGO]`/`[EJECUCIÓN]`/`[TEST]`.

## Git

- HEAD `5b20266709c14ea77ed0655a487ae397ee02090c` — `chore(repo): reorganizar
  documentos y datos sueltos de la raiz`.
- Branch `fix/ttm-ratios-cnv`.
- `git status --porcelain`: 253 entradas (modificados + sin versionar). Incluye
  todo F5–F9 (`docs/review/16_*` a `21_*`, `scripts/engine/c10_evaluate.py`,
  `tests/test_f5_multisource.py` … `test_f9_state_reconciliation.py`). **Nada de
  F5–F9 está commiteado.** `[EJECUCIÓN: git]`.

## `StageState` actual (`engine/states.py`)

```
PLANNED → READY → RUNNING → VALIDATING → {PASSED | FAILED}
FAILED → FIXING → RERUNNING → VALIDATING
PASSED → CHECKPOINTED → CERTIFIED → (terminal, set() vacío)
```

**No existe `StageState.ABORTED`.** `TRANSITIONS` es un `dict[StageState,
set[StageState]]`; `assert_transition()` levanta `ValueError` si el destino no
está en el conjunto permitido. `[CÓDIGO]`.

## `RunState` — no existe como enum

`engine.runs.status` es `TEXT NOT NULL DEFAULT 'RUNNING'`, **sin `CHECK`
constraint** (verificado en `migrations/engine/001_s00_bootstrap.sql`). Los
valores usados en código son literales: `RUNNING`, `OK`, `ABORTED`, `BLOCKED`.
`engine.stage_runs.state` también es `TEXT` libre, sin `CHECK`: la máquina de
estados se aplica **sólo** en la capa Python (`assert_transition`), nunca en
Postgres. `[CÓDIGO]`.

## `run_scope` (`engine/db.py:204-255`)

```python
@contextmanager
def run_scope(engine, settings, pipeline_version, run_id=None):
    if run_id is None:
        run = start_run(...)          # abre un run nuevo
    else:
        run = <reutiliza run existente>   # modo E2E, orquestador es dueño
    run.status = None
    try:
        yield run
    except BaseException as e:
        try:
            if run_id is None:
                finish_run(engine, run.run_id, "ABORTED")   # SOLO run-level
        finally:
            raise e
    else:
        if run_id is None:
            finish_run(engine, run.run_id, run.status or "OK")
```

**No recibe `stage_id`.** El bloque `except` cierra `engine.runs` (y sólo si
`run_id is None`; en modo E2E compartido, ni siquiera eso — el orquestador es
el dueño declarado del cierre de run). **Nunca escribe en
`engine.stage_runs`.** `[CÓDIGO]`.

`record_stage_transition()` (`engine/db.py:284-312`) es un `INSERT`
puro — cada transición es una fila nueva (log append-only, no hay `UPDATE`).
El "estado actual" de una etapa es la última fila por `(run_id, stage_id)`
ordenada por `id`. Ni C10 ni el publisher usan otra cosa: los dos hacen
`... id IN (SELECT max(id) FROM engine.stage_runs WHERE run_id=... GROUP BY
stage_id)`. `[CÓDIGO]`.

## Orquestador (`scripts/engine/e2e_orchestrator.py`)

Corre S00→S04 como subprocesos bajo un `run_id` compartido
(`ENGINE_E2E_RUN_ID`). Cuando un subproceso falla, el orquestador **sí** cierra
el run correctamente (`edb.finish_run(engine, run_id, "ABORTED")`, línea 202).
Pero eso es cierre a nivel *run*; ninguna pieza del sistema cierra la etapa que
estaba corriendo dentro de ese subproceso en el momento del fallo. `[CÓDIGO]`.

## Escritores de `stage_runs`/`run_scope` — mapa transversal (Paso 2 anticipado)

`record_stage_transition` y/o `run_scope` aparecen en **14 scripts**, todos
importando el mismo `engine/db.py`:

| script | patrón |
|---|---|
| `s00_smoke.py` | `run_scope` → READY→RUNNING → trabajo → VALIDATING→{FAILED\|PASSED,CHECKPOINTED} |
| `s01_identity.py` | idem |
| `s02_fetch_ypf.py` | idem |
| `s03_parse_ypf.py` | idem |
| `s04_normalize.py` | idem |
| `c3_cnv_fetch.py` | idem |
| `ratio_engine.py` | `run_scope` (sin stage_runs propio) |
| `identity_v1_backfill_dev.py` | `run_scope` |
| `identity_v1_backfill_piloto.py` | `run_scope` |
| `backfill_cik.py` | `run_scope` |
| `f024_bma.py` | `run_scope` |
| `f041_reafirmacion.py` | `run_scope` |
| `cnv_negative_pilot.py` | menciona `run_scope` en docstring (no abre corrida) |
| `e2e_orchestrator.py` | orquesta los anteriores, cierre de run propio |

Los 6 primeros comparten **el mismo patrón exacto**: escriben READY→RUNNING
al principio del bloque `with run_scope(...)`, hacen el trabajo real, y sólo
escriben el tramo terminal (VALIDATING→…) si el trabajo no lanzó excepción.
Si algo revienta entre esos dos puntos, la etapa queda en RUNNING para
siempre — el defecto es **transversal por construcción**, porque todos pasan
por el mismo `run_scope`. `[CÓDIGO]` — confirmado leyendo los 6 archivos
línea por línea, no por inferencia.

## Tests de lifecycle existentes

| archivo | qué cubre | toca `stage_runs.state`? |
|---|---|---|
| `tests/test_engine_run_lifecycle.py` | `run_scope` cierra el *run* en 3 escenarios | no |
| `tests/test_f040_lifecycle_c3.py` | ídem para C3, en los 3 tramos del ciclo de vida | escribe manualmente 2 transiciones en un test, no asegura nada sobre ellas al final |
| `tests/test_f050_lifecycle_s00_s02.py` | ídem para S00/S01/S02, inyecta fallos contra el `main()` real | no |

**Ninguno de los tres asegura nada sobre el valor final de
`engine.stage_runs.state`.** Los tres verifican exclusivamente
`engine.runs.status`. Consecuencia directa: agregar un cierre de etapa en
`run_scope` no puede romper ninguno de estos tests, porque ninguno mira esa
columna. Verificado por lectura completa de los tres archivos (no supuesto).
`[CÓDIGO]`.

## Los 16 casos de F9 — re-verificados en esta corrida (no repetido de memoria)

```sql
WITH ult AS (SELECT DISTINCT ON (sr.run_id,sr.stage_id)
               sr.run_id, sr.stage_id, sr.state, sr.started_at
             FROM engine.stage_runs sr ORDER BY sr.run_id, sr.stage_id, sr.id DESC)
SELECT u.*, r.status, r.finished_at, r.pipeline_version, r.git_commit
  FROM ult u JOIN engine.runs r ON r.run_id = u.run_id
 WHERE u.state = 'RUNNING'
```

**16 filas**, idéntico a F9 (el 16º, `58f10a99…`, es el que la propia
regresión de F9 reprodujo el 2026-09-08 11:31, con `git_commit=5b20266…` — el
commit de la reorganización de raíz, posterior al `2993918…` de los otros 15).
`[EJECUCIÓN]`.

| stage_id | n | pipeline_version |
|---|---:|---|
| `C3_CNV_FETCH` | 11 | `test-f040-lifecycle` (10) + 1 con HEAD actual |
| `S02_fetch` | 5 | `s2-fetch-v1` |

Patrón común, verificado en las 16 filas: `engine.runs.status='ABORTED'` con
`finished_at` fijado 10–30 ms después de `started_at` — corridas muertas, no
vivas. **0 casos** con el run padre todavía en `RUNNING` (0 huérfanas
operativas reales). **0 stage_ids adicionales** fuera de `C3_CNV_FETCH` y
`S02_fetch` — S00/S01/S03/S04 no tienen ningún residuo hoy (coincidencia de
timing en las suites de test, no ausencia estructural del defecto: el código
de los 6 es idéntico). `[EJECUCIÓN]`.

## Otros casos RUNNING/ABORTED buscados y no encontrados

- Ningún `stage_runs.state='RUNNING'` con `engine.runs.status` distinto de
  `ABORTED` (es decir, cero casos de huérfana viva). `[EJECUCIÓN]`.
- `engine.runs.status`: `OK=628`, `ABORTED=504`, `BLOCKED=209`. Sin valores
  fuera de ese conjunto (cubierto por
  `test_todo_estado_es_terminal_o_vive` de F-050). `[EJECUCIÓN]`.

## Side effects actuales (heredados de F5–F9, no de este paso)

- Esquema `market_*` (10 tablas) instalado en DEV, 584 instrumentos, 31.276
  precios.
- `engine.certifications`: `CERTIFICADA=239`, `NEGADA=317`,
  `CERTIFICADA_CON_OBSERVACIONES=40`.
- `staging._publications`: 4 activas + 5 `rolled_back` (incluye
  `f8_ypf_fact`, 47.930 filas, del E2E de F8).
- Producción (puerto 5432): **0 escrituras** — verificado en cada cierre de
  fase F5–F9, no reverificado en este documento porque ninguna acción de
  auditoría de F10 hasta ahora tocó una conexión a 5432.

## Veredicto

`PROCEED`. El defecto es transversal (14 escritores del mismo `run_scope`,
6 con el patrón exacto), está acotado a un solo punto de cierre en
`engine/db.py`, y ningún test existente depende del comportamiento actual de
`stage_runs.state` ante un aborto. No hay huérfanas operativas que reconciliar
de urgencia — los 16 son residuo histórico inerte, consistente con F9.
