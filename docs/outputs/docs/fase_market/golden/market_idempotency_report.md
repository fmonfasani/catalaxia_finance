# IDEMPOTENCY REPORT — Market Data

Una corrida es idempotente cuando **no escribe una sola fila**: no basta con que el UPSERT deje los mismos valores, porque reescribir `source_run_id`/`fetched_at_utc` destruye la provenance (la fila diria que la produjo una corrida que en realidad no la cambio).

Regla implementada: se persisten unicamente las filas NEW o CHANGED.

## 83 — YPFD.BA

| run_id | estado | ruedas recibidas | reintentos | error | desde | hasta |
|---|---|---|---|---|---|---|
| golden-83-20260824T121230Z | SUCCESS | 6633 | 0 |  | 2000-01-03 | 2026-08-21 |
| golden-retest-83-20260824T121325Z | PARTIAL | 6633 | 0 |  | 2000-01-03 | 2026-08-21 |
| golden-v3-83-20260824T214015Z | REQUESTED |  | 0 |  |  |  |
| golden-v3-83-20260824T214105Z | SUCCESS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-retest2-83-20260824T214132Z | SUCCESS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-retest3-83-20260824T214323Z | SUCCESS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-v4-83-20260824T214714Z | SUCCESS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-retest4-83-20260824T214742Z | SIN_CAMBIOS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-v5-83-20260824T222632563307Z | SIN_CAMBIOS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-v5-retest-83-20260824T222714192051Z | SIN_CAMBIOS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |
| golden-v5-retest5-83-20260825T042727797783Z | SIN_CAMBIOS | 6634 | 0 |  | 2000-01-03 | 2026-08-24 |

Cambios registrados (append-only) por tipo y motivo:

| tipo | motivo | n | desde | hasta | clasificacion |
|---|---|---|---|---|---|
| NEW | YAHOO_UPDATE | 6634 | 2000-01-03 | 2026-08-24 | REVISAR |

Filas vivas por corrida de origen (provenance efectiva):

| corrida | filas |
|---|---|
| golden-retest4-83-20260824T214742Z | 6634 |

## 84 — YPF

| run_id | estado | ruedas recibidas | reintentos | error | desde | hasta |
|---|---|---|---|---|---|---|
| golden-84-20260824T121247Z | SUCCESS | 8344 | 0 |  | 1993-06-29 | 2026-08-21 |
| golden-retest-84-20260824T121335Z | PARTIAL | 8344 | 0 |  | 1993-06-29 | 2026-08-21 |
| golden-v3-84-20260824T214115Z | SUCCESS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-retest2-84-20260824T214143Z | SUCCESS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-retest3-84-20260824T214335Z | SUCCESS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-v4-84-20260824T214724Z | SUCCESS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-retest4-84-20260824T214752Z | SIN_CAMBIOS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-v5-84-20260824T222644819597Z | SIN_CAMBIOS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-v5-retest-84-20260824T222724322764Z | SIN_CAMBIOS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |
| golden-v5-retest5-84-20260825T042739898974Z | SUCCESS | 8345 | 0 |  | 1993-06-29 | 2026-08-24 |

Cambios registrados (append-only) por tipo y motivo:

| tipo | motivo | n | desde | hasta | clasificacion |
|---|---|---|---|---|---|
| NEW | YAHOO_UPDATE | 8345 | 1993-06-29 | 2026-08-24 | REVISAR |
| CHANGED | VOLUME_RESTATEMENT | 1 | 2026-08-24 | 2026-08-24 | REVISAR |

Filas vivas por corrida de origen (provenance efectiva):

| corrida | filas |
|---|---|
| golden-retest4-84-20260824T214752Z | 8344 |
| golden-v5-retest5-84-20260825T042739898974Z | 1 |
