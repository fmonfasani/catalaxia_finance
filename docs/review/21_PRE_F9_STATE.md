# 21 — Estado pre-F9 (baseline, solo lectura)

F8 cerrado (STEP_19 PASS, NEXT_PHASE=F9). Solo lectura + este documento. Conteos a 2026-09-08 ~10:40 UTC sobre `catalaxia_engine@127.0.0.1:5433/catalaxia` (DEV). Evidencia `[EJECUCIÓN]`.

## Git

- HEAD `5b20266709c14ea77ed0655a487ae397ee02090c` — `chore(repo): reorganizar documentos y datos sueltos de la raiz`.
- Branch `fix/ttm-ratios-cnv`. Working tree con modificaciones y archivos untracked de F2–F8 (incluye `20_F8_*`, `tests/test_f8_e2e.py`). Nada commiteado de las fases `[EJECUCIÓN]`.

## Registro (conteos globales)

- `engine.runs`: OK=627, ABORTED=487, BLOCKED=207 (total 1.321; sin status desconocidos, sin RUNNING vivo). Pipeline versions: `e2e-sec-edgar-v1` (233 OK/36 BLOCKED/19 ABORTED), `s0-bootstrap-v1`, `s1-identity-v1`, `s2-fetch-v1`, `test-c11-contract`, `test-f040-lifecycle`, `test-lifecycle`, `identity-backfill-dev-v1`, `engine-v1`.
- `engine.stage_runs` (último evento por run+etapa): CHECKPOINTED=593, PASSED=509, FAILED=138, READY=50, **RUNNING=15**.
- `engine.checkpoints`: 92.939 filas; 1 por (run,stage) (sin duplicados), con input_hash/code_version/contract_version/artifact_ref/created_at.
- `engine.certifications`: CERTIFICADA=239, NEGADA=317, CERTIFICADA_CON_OBSERVACIONES=40.
- `staging._publications`: 4 activas + 5 rolled_back.

## Los 15 RUNNING (identificados en F8) — detalle

| # | run_id | stage_id | started_at (UTC) | engine.runs | git_commit | pipeline_version |
|---|---|---|---|---|---|---|
| 1 | d12b9050… | C3_CNV_FETCH | 09-06 15:21:32 | ABORTED (fin 15:21:32) | 2993918f | test-f040-lifecycle |
| 2 | baeb032c… | C3_CNV_FETCH | 09-06 16:42:24 | ABORTED (fin 16:42:24) | 2993918f | test-f040-lifecycle |
| 3 | 792eb653… | C3_CNV_FETCH | 09-06 17:39:04 | ABORTED (fin 17:39:04) | 2993918f | test-f040-lifecycle |
| 4 | c7930f9e… | C3_CNV_FETCH | 09-06 17:39:05 | ABORTED (fin 17:39:05) | 2993918f | test-f040-lifecycle |
| 5 | 2c85235c… | C3_CNV_FETCH | 09-06 17:39:05 | ABORTED (fin 17:39:05) | 2993918f | test-f040-lifecycle |
| 6 | 5d65433c… | C3_CNV_FETCH | 09-06 17:39:52 | ABORTED (fin 17:39:52) | 2993918f | test-f040-lifecycle |
| 7 | 8de48c9b… | C3_CNV_FETCH | 09-06 17:46:28 | ABORTED (fin 17:46:28) | 2993918f | test-f040-lifecycle |
| 8 | 98c79b53… | C3_CNV_FETCH | 09-07 21:32:34 | ABORTED (fin 21:32:34) | 2993918f | test-f040-lifecycle |
| 9 | c60aefa7… | C3_CNV_FETCH | 09-07 21:37:39 | ABORTED (fin 21:37:39) | 2993918f | test-f040-lifecycle |
| 10 | ecf4138b… | C3_CNV_FETCH | 09-07 21:41:46 | ABORTED (fin 21:41:46) | 2993918f | test-f040-lifecycle |
| 11 | 574458c1… | S02_fetch | 09-07 21:39:17 | ABORTED (fin 21:39:17) | 2993918f | s2-fetch-v1 |
| 12 | 5083eba9… | S02_fetch | 09-07 05:43:52 | ABORTED (fin 05:43:52) | 2993918f | s2-fetch-v1 |
| 13 | f673ed9c… | S02_fetch | 09-07 05:45:20 | ABORTED (fin 05:45:20) | 2993918f | s2-fetch-v1 |
| 14 | 9a4da626… | S02_fetch | 09-07 21:34:08 | ABORTED (fin 21:34:08) | 2993918f | s2-fetch-v1 |
| 15 | f0c143ec… | S02_fetch | 09-07 23:10:01 | ABORTED (fin 23:10:01) | 2993918f | s2-fetch-v1 |

Común a los 15: timeline READY→RUNNING (2 eventos) sin VALIDATING/PASSED/FAILED/CHECKPOINTED; **sin gate_status, sin report, sin checkpoint, sin certificación, sin publicación**. `engine.runs` ABORTED con `finished_at` (termina ~10-50 ms después del RUNNING). Ninguno tiene facts/artefactos asociados.

## Procesos, cron, DEV vs producción

- Proceso vivo: NO verificable por DB; los 15 tienen `finished_at` ≠ NULL hace horas/días → corridas muertas `[EJECUCIÓN]`. Sin sesiones activas asociadas (detector `corridas_huerfanas()` por pg_stat_activity aplica a runs `engine.runs.status='RUNNING'`, que hoy es 0).
- Cron/job asociado: pipeline versions `test-f040-lifecycle` y `s2-fetch-v1` con git `2993918f` identifican **residuo de ejecución de tests** (F-040 lifecycle + F-050 lifecycle), no producción. Producción CNV corre por cron SQLite (sin artefactos PG) — no tocar.
- DEV/prod: todo lo anterior es `catalaxia_engine@127.0.0.1:5433` (DEV). Producción intacta; no expuesta.