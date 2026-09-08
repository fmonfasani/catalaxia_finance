# 21 — F9: Reconciliación del estado operacional

Auditoría de control/ejecución sobre `engine.runs`, `engine.stage_runs`, `engine.checkpoints`, `engine.certifications` y registros de publicación (DEV `127.0.0.1:5433`). **Sin escrituras.** Evidencia `[EJECUCIÓN]`/`[CÓDIGO]`/`[TEST]`.

## S1 — Inventario global de estados

- `engine.runs` (run-level): OK=627 · ABORTED=487 · BLOCKED=207. **Sin RUNNING vivo** (0) → el detector operativo `corridas_huerfanas()` reporta **0 huérfanas** incluso con umbral 0h `[EJECUCIÓN]`. Sin estados desconocidos (invariante cubierto por F-040/F-050).
- `engine.stage_runs` (último evento por run+etapa): CHECKPOINTED=593 · PASSED=509 · FAILED=138 · READY=50 · RUNNING=16.
- `engine.checkpoints`: 92.939, ≤1 por (run,stage); todos con input_hash/code_version/contract_version/artifact_ref `[EJECUCIÓN]`.
- Certificaciones: CERTIFICADA=239 · NEGADA=317 · CON_OBSERVACIONES=40. Publicaciones staging: 4 activas + 5 rolled_back.
- Distribución por pipeline: el residuo RUNNING vive solo en `test-f040-lifecycle` (11) y `s2-fetch-v1` (5). Etapas productivas/golden (e2e-sec-edgar-v1, runs con facts) quedan todas terminales `[EJECUCIÓN]`.

**¿Son realmente huérfanos?** No en el sentido operativo: los 16 residuos de etapa pertenecen a runs cuyo nivel `engine.runs` es **ABORTED con `finished_at`** (corridas muertas, ~10–50 ms después del RUNNING). No se aceptó "RUNNING antiguo" como huérfano: se verificó el run-level terminal para cada uno `[EJECUCIÓN]`.

## S2 — Reconstrucción individual (16 casos)

Patrón idéntico en los 16: timeline `READY→RUNNING` (2 eventos) · `gate_status/captura NULL` · `report NULL` · sin checkpoint · sin certificación · sin publicación · run `engine.runs` ABORTED+`finished_at` · sin facts en `derived.fact`. Origen: git `2993918f` y pipeline `test-f040-lifecycle` → producto de `tests/test_f040_lifecycle_c3.py` (inyección `donde=1`); pipeline `s2-fetch-v1` → producto de `tests/test_f050_lifecycle_s00_s02.py`/`test_engine_run_lifecycle.py` sobre el `main()` real de S02 con fallo inyectado. La corrida de la suite en F9 **reprodujo el patrón** (16º residuo `58f10a99…`, 2026-09-08 11:31) `[EJECUCIÓN]`.

Clasificación: **A=legítimos: 0 · B=terminalizables con evidencia: 0 · C=NO DETERMINABLE: 0 · D=inconsistentes/explicados: 16.** Todos D, todos con evidencia sólida (run ABORTED + finished_at + ejecutante test + sin gate/report/checkpoint). Procesos vivos: no existen (terminalidad + antigüedad) `[EJECUCIÓN]`.

## S3 — Contrato de estados vs. hallazgo S03

Contrato formal `engine/states.py`: `PLANNED→READY→RUNNING→VALIDATING→{PASSED|FAILED}→(FIXING→RERUNNING→VALIDATING)→CHECKPOINTED→CERTIFIED` `[CÓDIGO]`. `run_scope()` (cierre garantizado F-040/F-050): en excepción hace solo `finish_run(run_id,'ABORTED')` sobre `engine.runs`; **no registra evento terminal de etapa** `[CÓDIGO]`. El enum de etapa **no tiene estado terminal "ABORTED"** → RUNNING no tiene salida legal para aborto.

Comparación con el hallazgo S03 ("RUNNING sin FAILED"): S03 murió **sin cerrar siquiera el run** (estado de SETA adelantado) → causa raíz de F-009, resuelta por `run_scope`. Los 16 actuales mueren **con el run cerrado (ABORTED)** pero **sin evento terminal de etapa** → defecto **transversal** de la state machine (corridas vs etapas desacopladas), no de una implementación individual: aplica a S00–S04, C3 y orquestador por igual, porque el cierre de excepción está centralizado en `run_scope`. Impacto: cosmético/de auditoría (fila de etapa dice "running" pero el run dice "aborted"); **sin datos, gate, report, checkpoint o certificación asociados** → no contamina provenance ni publicación.

## S4 — Idempotencia / qué pasa si se re-ejecuta

- Re-ejecutar = run nuevo (`start_run` genera nuevo `run_id`): no colisiona con el residuo; hechos desempeñan POR `fact_key` (ON CONFLICT) → convergen al último escritor sin duplicar (cubierto F5) `[CÓDIGO]`+`[TEST]`.
- No se puede "reanudar" el run ABORTED: `run_scope` E2E exige run existente y el orquestador usa runs frescos.
- Certificación: 1 acta por run (test_f7 `N`); C11 sobre estos runs → NEGADA por `evidencia incompleta` (sin reports) → **sin doble certificación** `[TEST]`.
- Publicación: C10 exige gates PASS (estos runs tienen gates NULL → `BLOCK:C10_NO_PASS`, verificado en F8) → **sin publicación cruzada** `[TEST]`.
- El residuo no posee checkpoints/facts/certs/publos → **provenance intacta** (test_f9 3–6 verificados) `[TEST]`.

## S5 — Propuesta de reconciliación (por caso)

Para los 16: **NO ACTION sobre los datos** (el run ya es terminal ABORTED; convertir el estado de etapa inventaría un estado que el enum no tiene — prohibido). Documentar el **GAP** de mecanismo: etapa sin estado terminal para aborto + `run_scope` sin cierre de etapa. Ningún caso pide FAILED/ABORTED/REVIEW a nivel de datos.

## S8 — Tests

Nuevo `tests/test_f9_state_reconciliation.py` (solo lectura, 6/6 PASS): terminalidad del run (terminal ⇒ `finished_at`), sin estados desconocidos, residuo de etapa ⇒ run ABORTED, residuo sin gate/report, sin checkpoint/cert/publicación, sin facts → **contrato previamente no protegido, ahora sí** `[TEST]`.

Regresión F9 (state machine/S00–S04/CNV): **101 passed · 8 skipped · 9 failed**. Los 9 fallos son **PREEXISTENTES** (familia identidad/universo CNV stale tras autoridad identity: `c3_real…[3]`, `f038_traza[5]`, `cnv_authority T8[1]` — "el universo viejo ya no incluye autoritativos", mantenimiento autodeclarado en F6) `[TEST]`. Regresión relacionada cerrada previamente en F8: 114/114 (f2/f6/f7/f8/c11/e2e/f050) `[TEST]`.

**Reconciliado no quiere decir limpiado:** el residuo de etapa queda como está (no modificar RUNNING por regla); se propone resolver en F10 el mecanismo (estado terminal de etapa) y luego sí un sweeper explícito y transaccional que solo cierre lo que ya es resoluble.