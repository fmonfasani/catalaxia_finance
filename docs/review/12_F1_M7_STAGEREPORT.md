# 12 — F1 M7 StageReport (implementación + verificación)

## Estado previo

`s04_normalize.py` (working tree, baseline §12_PRE): dict legacy s04:640-666, sin import `engine.report`; fix `parser_version` vigente; resto del archivo con trabajo concurrente de rama (F-031/F-055) en regiones distintas. Consumidores del contenido del reporte: solo s04 (integrity.hash_in/hash_out :698/716-717) + humanos/c11-filas — cero lectores externos de claves `[CÓDIGO]`. Contenido idéntico demostrable vía mapeo documentado (§9 Paso 12: SÍ procede).

## Archivo modificado (único de producción)

`scripts/engine/s04_normalize.py`, 3 hunks atribuibles F1 (resto preexistente):
1. `+from engine.report import StageReport # noqa: E402` (1 línea).
2. `+build_s04_report(...)` (~60 líneas, pura, antes de `main`): mapea expected=filas_entrada, parsed=emitidos, rejected=expected-parsed (número honesto; desglose en `coverage_detail` porque las categorías se solapan), `by_reason={}` (no inventado), `by_null_reason` exacta, extras legacy (`normalizer_version`, `input.stage/run_id`, `coverage_detail`, `hash_out_v1/spec/por_tabla`); llama `sr.validate()`. Único cambio de conducta posible: PASS con cero checks ahora falla (norma del proyecto; tests lo fijan).
3. Construcción legacy (27 líneas) → llamada (10 líneas). Lógica de normalización, SQL, identidad, facts, provenance, checkpoints, hashes, lifecycle, DDL: intactos.

Más: `tests/test_c11_contract.py` (untracked, solo extensión: 4 tests M7 DB-free + import).

## Razón

M7 (09-M7, 11-FASE 1): uniformar reporte al contrato C10 con preservación total (superset: todas las claves legacy presentes + `coverage_detail`).

## Tests

- Nuevos M7: 4/4 PASS (uso StageReport, válido+equivalente, BLOCK con reasons, PASS-sin-checks falla).
- Regresión: `test_c11_contract` + `test_e2e_orchestrator` + `f050` + `f054` + `f055` + `test_s04_normalize` → **96 passed, 2 skipped, 1 xfailed, 0 failed** `[EJECUCIÓN]`. Fallos nuevos/preexistentes: n/a (cero fallos).
- py_compile s04 + test: exit 0 `[EJECUCIÓN]`.

## E2E DEV (YPF golden, DB local 127.0.0.1:5433 `catalaxia`, allow_prod=False)

- Corrida 1 `ede1e691…`: S00→S04 todas PASS→CHECKPOINTED, mismo run_id, gates PASS `[EJECUCIÓN]`.
- Reporte S04 persistido: shape StageReport + extras; code{script, git_commit 2993918, parser_version, normalizer_version}; coverage{expected 67084, parsed 47930, rejected 19154}; gate PASS 9 checks; input/checkpoint E2E; integrity 5 claves `[EJECUCIÓN]`.
- `derived.fact`: 47.930 filas del run; checkpoints: 1 (modo E2E, F-031); identidad V1 (gate C-S04-004 PASS).
- C11 `--run-id ede1e691…`: **CERTIFICADA** (`c11-ede1e6…`, hash f41b96c5…), 5/5 etapas PASS con expected/parsed/rejected coherentes (S04 67084/47930/19154) — sin modificar C11, sin forzar veredicto `[EJECUCIÓN]`.
- Idempotencia (corrida 2 `0d9a2987…` también PASS): hash_out idéntico, coverage idéntica, total 47.930 filas ambos runs, **0 duplicados fact_key** — convergencia por ON CONFLICT (run_id = último escritor; histórico en stage_runs). VERIFICADA `[EJECUCIÓN]`.

## Impacto / rollback

Impacto: solo serialización del reporte (superset compatible); sin lectores externos afectados; DB schema intacto (cero DDL); producción intacta (DEV local; allow_prod=False).
Rollback (sin tocar trabajo ajeno; prohibido `checkout` del archivo): revertir quirúrgicamente los 3 hunks (quitar import, quitar `build_s04_report`, restaurar bloque dict legacy documentado en este informe §Estado-previo) + quitar bloque M7 del test (líneas finales desde `# M7 (FASE 1`). Verificado por construcción (hunks disjuntos de los preexistentes).

## Resultado

F1 = PASS (las 10 condiciones §20 cumplidas; detalle en 12_IMPLEMENTATION_RESULT.md). `[EJECUCIÓN]` global del paso.
