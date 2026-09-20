# 13 — F2 Publication Safety (staging, sin cutover)

CAPA → C12 · PLANOS → DATOS+CONTROL+EJECUCIÓN · CICLO → IMPLEMENTAR→VERIFICAR→CERTIFICAR · HOY → publishers intactos · OBJETIVO → publisher staging+swap+gate · DECISIÓN → ver resultado · EVIDENCIA → abajo (cada afirmación `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`).

## Baseline

Rama `fix/ttm-ratios-cnv`@2993918 + F1 (s04-StageReport, STEP_12 PASS_WITH_WARNINGS). Publishers legacy, C11, cron y producción intactos (verificación §diff). `[EJECUCIÓN: git]`.

## Diseño y archivos

- Nuevo `scripts/engine/publisher.py` (~330 líneas, C12): `PublishInput` versionado (fuente+target+run+PKs+filtro+min_rows) → BUILD (`CREATE TABLE staging.<t>__new__ AS SELECT`, origen solo-lectura) → CHECK SCHEMA (nombres+tipos) → LOAD → VALIDATE (nunca-vacía, mínimo, PK sin duplicados) → C10 (lee `stage_runs`, exige PASS en últimas por etapa) → C11 (lee `engine.certifications`, exige `CERTIFICADA`; sin modificar c11 ni tabla) → SNAPSHOT (`__prev__`) + ATOMIC SWAP (RENAMEs en una transacción; PG transaccional = sin estado vacío/parcial observable) → provenance (`staging._publications`) → ROLLBACK (rename inverso). Regla única `gate_decide` (pura). Rechazo duro fuera de `staging` + validación de identificadores/filtro anti-inyección. Sin lógica financiera/ratios/identidad. `[CÓDIGO]`.
- Nuevo `tests/test_f2_publisher.py` (12 tests). Sin tocar otro código productivo. `[CÓDIGO]`.

## Arquitectura y staging

Staging = schema `staging` en PG DEV local (127.0.0.1:5433, `allow_prod=False`), con GRANT USAGE/CREATE + default privileges al rol app (`catalaxia_engine`); publisher usa app-role (mínimo privilegio; admin solo creó schema/grants). Aislado de producción por host/usuario/configuración; duda de destino no ocurrió (verificado cada conexión: localhost:5433). `[EJECUCIÓN]`.

## Tests (12/12 PASS) + regresión (96/0)

Contract (identificadores/filtro) · gates puros (ALLOW/BLOCK:C10/BLOCK:C11) · schema puro · never-empty puro · dry-run (sin target residual) · swap real (47.930 filas, provenance completa) · idempotencia (mismo hash, sin duplicados) · rollback (restaura contenido A verificado por hash) · bloqueo sin-C10/sin-C11/NEGADA (sin swap) · input inexistente/vacío · rollback sin snapshot · regresión c11+e2e+f050/f054/f055+s04 intacta. `[TEST]`+`[EJECUCIÓN]`.

## E2E DEV (YPF golden, sin publicar a producción)

S00→S04 (Paso 12, 2 runs PASS) → C10 (gates PASS) → C11 CERTIFICADA (run `0d9a29…`, cert `593b802d…`; run previo `ede1e6…` con 47.930 facts convergentes por ON CONFLICT, 0 duplicados) → publisher CLI: dry-run OK → PUBLISHED (47.930, swap_ts, provenance_id 11) → re-publish idempotente (mismo hash) → subset B (100) → ROLLBACK a A (hash verificado) → bloqueos (C10 ausente, target inválido con JSON limpio). `[EJECUCIÓN]`.
Nota: el run `ede1e6…` quedó con 0 filas `derived.fact` tras la convergencia del segundo run (run_id = último escritor; histórico en stage_runs) — comportamiento idempotente documentado, no pérdida (total 47.930, 0 duplicados).

## C10/C11/gates

C10 consumido (no reemplazado): últimas `stage_runs` del run con gate PASS. C11 consumida (no modificada): `CERTIFICADA` exigida; NEGADA/ausente bloquea. Combinaciones probadas: PASS+CERTIFIED→continúa; PASS+NEGADA→bloquea; FAIL+CERTIFIED→bloquea (lógica `gate_decide` + tests). Sin bypass implementado (ni heredado en el publisher). Compatibilidad C11 verificada (columnas certification_id/veredicto/cert_hash/certificación por run; orden por `generado_at` — corrección de `ORDER BY id` inexistente detectada por test). `[TEST]`+`[CÓDIGO]`.

## Atomic swap, rollback, idempotencia, failures, provenance

Swap: RENAMEs en una transacción + verificación post (conteo == staged > 0) → sin ventana vacía/parcial (PG transaccional; justificado, no inventado). Rollback A→B→A demostrado con hash. Idempotencia: mismo input → mismo hash, conteo estable. Failures 1–10 cubiertos (input/schema/vacío/incompleto/C10/C11×2/swap-vía-validación-previa/rollback/sin-snapshot/target-protegido). Provenance por publish: run_id, input+filtro, input_hash, staging, snapshot (`__prev__`), C10-detail, certification_id+cert_hash, swap_ts, publisher_v1, git (env/`dev-unknown`). `[EJECUCIÓN]`.

## Producción, diff, riesgos, gaps

Producción intacta (cero conexiones de escritura fuera de DEV; migrate/sync/s5/publicar_v2/api/cron/C11 sin tocar; CUTOVER no ejecutado). Diff: F2-autorizado = `publisher.py` + `test_f2_publisher.py` + schema/grants DEV + 13_*.md; preexistente = resto (rama); autogenerado = `.pyc` ignorados. Riesgos: R2 residual (código nuevo sin prod; swap solo-staging) → R1 tras gates; sin R3/R4 activos. Gaps: umbral cuantitativo de volumen (estructural=1 implemented, cuantitativo PENDING_EVIDENCE); hist-writer (no afecta staging); TLS/auth (fuera de F2, registrados en F0).
