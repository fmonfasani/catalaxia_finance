# 11 — Implementation Plan (define, no ejecuta)

**FASE 2→3, PASO 11.** Convierte el target (10) en fases ejecutables con precondiciones, tests, gates y rollback. DEFINE solamente: cero cambios de código/DB/migraciones/producción. Base 01–10 + 07A (sin contradicciones con decisiones anteriores; si apareciera alguna se marcaría CONFLICTO — no apareció ninguna nueva). Capas C1–C12, 4 planos, ciclo DEFINIR→IMPLEMENTAR→VERIFICAR→CERTIFICAR (este doc cierra DEFINIR).

## Orden y primera fase

Se parte de R7.1–R7.12 en orden (sin reordenamientos salvo el justificado abajo). Evaluación de primera modificación (§6/§19): **M7 (dict s04 → StageReport) SÍ es el quick win correcto** — cambio mínimo (un módulo, solo serialización de reporte con contrato ya equivalente), test contractual existente a extender (`test_c11_contract`), rollback R1 (revert), cero impacto en DB (mismo `stage_runs.report`, mismo contenido C10), cero impacto en producción (s04 corre igual; el gate posterior lo verifica). Alternativas descartadas: publisher (nuevo código + toca C12 → no primero), bridge (nuevas tablas), ownership (cambia writers vigentes). Evidencia R7.2 corre en paralelo desde el día 0 por ser solo-lectura (FASE 0).

## FASE 0 — Evidencia R7.2 (solo lectura, inmediata, en paralelo)

- Objetivo: cerrar gaps sin modificar nada. Capa: transversal. Planos: ninguno modificado (lectura).
- Tareas: equivalencia numérica (diseño M5, lectura+comparación) · trazar writer `screener_hist` · censo lectores legacy (tickers/descargas_log/screener_gold/fact_ratios/derived.ratio/boletín/CSV) · verificar reintentos HTTP y TLS (lectura engine.fetch/client) · auditar auth api · confirmar cron VPS · ventana runtime legacy · rol bloqueante de suites · cobertura FX por tipo.
- Tests/ejecución: scripts de comparación en solo-lectura; sin DB de producción (copias/RO donde aplique).
- Riesgo R0. Rollback n/a. Gate: 10 gaps con veredicto documentado (cada uno PASS → habilita su fase; FAIL → mantiene gating).
- Estado: READY.

## FASE 1 — M7 StageReport (primera modificación)

- Objetivo: uniformar reporte s04 a StageReport. Capa C9. Planos CONTROL (+EJECUCIÓN por test).
- Componentes/archivos/tablas: `scripts/engine/s04_normalize.py` (solo bloque de reporte); `stage_runs.report` (mismo contenido, misma tabla — sin DDL).
- Dependencias/precondiciones: ninguna (cero dependencias; contrato C10 ya equivalente verificado en 05 G10).
- Cambios: sustituir dict legacy por StageReport; test contractual comparando contenido viejo vs nuevo (extender `test_c11_contract`).
- Tests: unit (serialización) + contract (C10) + suites e2e/c11/f054 existentes verdes. Ejecución: dev → suites → staging E2E YPF.
- Evidencia: diff acotado + test verde + reporte idéntico. Riesgo R1. Rollback R1 (revert; reportes previos intactos).
- Gate: test contractual PASS + suites verdes + diff revisado (un revisor).
- Estado: READY.

## FASE 2 — R7.1 Publication safety (publisher en paralelo, sin cutover)

- Objetivo: construir publisher staging+swap+gate SIN tocar publishers vigentes. Capa C12. Planos DATOS+EJECUCIÓN+CONTROL.
- Precondiciones: entorno staging (espejo PG) + diseño R7.1 + A2/A3 aplicados. Cambios: código nuevo aislado (no modifica migrate/sync/s5/api).
- Tests: unit + contract (nunca-vacía) + bloqueo-sin-certificado + rollback (swap revertido). Ejecución: staging con snapshot.
- Riesgo R2 (código nuevo, sin efecto prod). Rollback R1 (no desplegado). Gate: suite publisher verde en staging + revisión de diseño gate único.
- Estado: CONDITIONAL (staging + diseño).

## FASE 3 — R7.3 empresas (ownership sin deletes)

- Objetivo: owner=`construir_base` operativo (guardarraíles, no borrado). Capa C2. Plano DATOS.
- Precondiciones: snapshot `empresas` + censos writer/reader + impacto `tickers`/`descargas_log` (FASE 0). Cambios: redirigir/excepcionar writers laterales (criterio A6); test no-DROP; catalogo intacto (su archive vive en R7.12).
- Tests: writer-census automatizado + rebuild verde. Riesgo R2. Rollback R2 (snapshot). Gate: un solo writer efectivo + test verde.
- Estado: CONDITIONAL.

## FASE 4 — R7.4 Identity bridge (solo lectura + tests)

- Objetivo: bridge v0↔v1 + migración de lectores nuevos. Capa C2. Planos DATOS (+CONTROL consumidor).
- Precondiciones: diseño + tests cruce (extender `test_cnv_identity_link`); ambos sistemas intactos. Cambios: tabla/función equivalencias (vía framework de migraciones engine, con revisión) + lectores nuevos al bridge. Prohibido: doble escritura, tocar s01/s03/s04 existentes.
- Tests: cruce CIK/CUIT + adversarial. Riesgo R2. Rollback R3 (bridge off). Gate: tests verdes + sistemas intactos verificados.
- Estado: CONDITIONAL.

## FASE 5 — R7.5 Facts puente (solo lectura)

- Objetivo: trazabilidad `source_fact_ids`↔`facts` por muestreo. Capa C6. Plano DATOS.
- Precondiciones: R7.4 (entity_key estable) + muestreo diseñado. Sin fusión de stores. Riesgo R1. Rollback R1. Gate: muestreo documentado + revisión.
- Estado: CONDITIONAL.

## FASE 6 — R7.6 CNV deprecate (anotación + ventana)

- Objetivo: marcar v1 deprecated e iniciar ventana (sin borrar). Capa C3/C4. Plano EJECUCIÓN.
- Precondiciones: jobs v2 verdes (evidencia vigente). Cambios: marcas DEPRECATED + docstring `build_subset` (A11) + inicio de ventana registrada. Riesgo R1. Rollback R1. Gate: marcas + ventana abierta.
- Estado: CONDITIONAL (evidencia v2 ya existe; ventana por transcurrir).

## FASE 7 — R7.7 Market (migración dim, sin fusión)

- Objetivo: `dim_instrument`→`market_instruments` con mapping completo. Capa C3. Plano DATOS.
- Precondiciones: mapping completo probado; m1 adaptado con fallback. Prohibido fusionar precios (M6). Riesgo R2. Rollback R2 (snapshot + fallback). Gate: mapping 100% + market tests verdes.
- Estado: CONDITIONAL.

## FASE 8 — R7.8 Ratios (evidencia primero)

- Objetivo: ejecutar prueba M5 (CIK+período+ratio+unidad+moneda; igualdad exacta canonizada salvo tolerancia justificada). Capa C8. Lectura + cómputo aislado (sin tocar motores).
- Precondiciones: R7.5 + serie IPC fijada (A10). Resultado EQUIVALENT/NON_EQUIVALENT/PENDING (sin merge por defecto). Riesgo R0. Gate: informe de equivalencia.
- Estado: PENDING_EVIDENCE.

## FASE 9 — R7.9 Core + modos (fachadas intactas)

- Objetivo: core rebuild parametrizable; UPDATE/ALL/SCREENER como fachadas. Capa C7. Planos EJECUCIÓN+CONTROL.
- Precondiciones: R7.3 + R7.6 estables + IPC + matriz de modos diseñada. Riesgo R2. Rollback R1 (fachadas = fallback). Gate: matriz de modos verde + outputs comparados.
- Estado: CONDITIONAL.

## FASE 10 — R7.10 Gate C10/C11/C12 (integración)

- Objetivo: gate único operativo en publisher (+export CSV): C10 PASS + C11 CERTIFIED o bloqueo; auditoría de bloqueos; sin bypass salvo emergencia auditada (A3). Capas C10–C12. Plano CONTROL.
- Precondiciones: FASE 2 (publisher) + certificadores vigentes. Riesgo R2. Rollback R1 (gate off → estado anterior, registrado). Gate: bloqueo-sin-certificado probado + auditoría.
- Estado: CONDITIONAL.

## FASE 11 — R7.11 FX (diseño→servicio, último dominio)

- Objetivo: servicio C7 OFFICIAL/MEP/CCL con 8 columnas; consume C6, alimenta C8, con provenance. Capa C7. Plano DATOS.
- Precondiciones: C7 estable (FASE 9) + alcance A12 + serie FX por tipo verificada (FASE 0). Sin tocar valores actuales hasta cutover gateado (fase propia posterior, fuera de este plan detallado).
- Tests: cobertura por tipo/fecha + provenance. Riesgo R1 (nuevo, sin efecto hasta cutover). Rollback n/a→R1. Gate: diseño + cobertura.
- Estado: CONDITIONAL.

## FASE 12 — R7.12 Cleanup (último, nunca antes)

- Objetivo: ejecutar secuencia 08 (MERGE/MIGRATE→TEST→VERIFICAR→VENTANA→ARCHIVE→DELETE) solo para candidatos con gate verde. Sin declarar deletes listos por estar listados.
- Precondiciones: todas las fases previas que cada candidato exige (matriz 08 §gates). Riesgo por candidato (R1–R3; R4 prohibido). Rollback por candidato (08).
- Estado: CONDITIONAL (se habilita por candidato, no en bloque).

## Matriz global (§21)

| Fase | R7.x | Capa | Plano | Dependencias | Riesgo | Tests | Rollback | Gate | Estado |
|---|---|---|---|---|---|---|---|---|---|
| F0 | R7.2 | transv. | — | ninguna | R0 | comparación/lectura | n/a | 10 gaps veredicto | READY |
| F1 | M7 | C9 | CTRL | ninguna | R1 | contract+suites | R1 | test+suites+revisión | READY |
| F2 | R7.1 | C12 | D+E+C | staging+diseño+A2/A3 | R2 | suite publ.+bloqueo | R1 | suite staging | CONDITIONAL |
| F3 | R7.3 | C2 | DATOS | snapshot+censos (F0) | R2 | writer-census+rebuild | R2 | un writer + verde | CONDITIONAL |
| F4 | R7.4 | C2 | DATOS | diseño+tests | R2 | cruce+adversarial | R3 | verdes + intactos | CONDITIONAL |
| F5 | R7.5 | C6 | DATOS | R7.4+muestreo | R1 | muestreo doc. | R1 | muestreo+revisión | CONDITIONAL |
| F6 | R7.6 | C3/C4 | EJEC | v2 verdes | R1 | jobs+assemble | R1 | marcas+ventana | CONDITIONAL |
| F7 | R7.7 | C3 | DATOS | mapping+F0 | R2 | market tests | R2 | 100% + verdes | CONDITIONAL |
| F8 | R7.8 | C8 | DATOS | R7.5+IPC | R0 | prueba M5 | n/a | informe | PENDING_EVIDENCE |
| F9 | R7.9 | C7 | EJEC+CTRL | R7.3/R7.6/IPC | R2 | matriz modos | R1 | modos+fachadas | CONDITIONAL |
| F10 | R7.10 | C10-12 | CTRL | F2+certs | R2 | bloqueo+auditoría | R1 | bloqueo probado | CONDITIONAL |
| F11 | R7.11 | C7 | DATOS | F9+A12+F0 | R1 | cobertura+prov | R1 | diseño+cobertura | CONDITIONAL |
| F12 | R7.12 | — | — | por candidato (08) | R1–R3 | suites dominio | por candidato | gates 08 | CONDITIONAL |

## Dependencias (§22)

F0 ─┬→ F1 (independiente; arranca ya) · F0 → F3/F7/F8 (censos, mapping, IPC) · F2 → F10 (publisher→gate) · F3 → F9 (ownership→core) · F6 → F9 (jobs→core) · F4 → F5 (bridge→puente) · F5 → F8 (facts→prueba) · F9 → F10/F11 (core→gate/FX) · todo → F12. Ninguna fase antes de sus precondiciones (criterio §29).

## Componentes (§23, extracto)

identity v0/v1: HOY dual → sin cambio hasta F4 → bridge+lecturas (F4, R2/R3) · bridge: no existe → nuevo solo-lectura (F4) · facts/derived: dual → puente (F5) · CNV v1/v2: v2 vigente → deprecate v1 (F6) · dim_instrument→market_instruments: migración (F7) · UPDATE/ALL/SCREENER: 3 caminos → core+fachadas (F9) · publisher: no existe → nuevo sin cutover (F2) · migrate: vigente → REPLACE tras F2+F10 · sync: vigente → tras gate (F10) · publicar_v2: vigente → criterio A7 (F2) · s5: vigente → +gate (F10) · C10/C11/C12: distribuido → gate único (F10) · ratios: 4 motores → sin cambio hasta F8 · FX: disperso → servicio (F11) · legacy (08): vigente → F12 por candidato.

## Datos (§24, extracto)

`stage_runs.report`: writer s04 → mismo writer, distinto serializador (F1; sin migración) · `empresas`: 4 writers → 1 efectivo (F3; sin migración de datos) · equivalencias bridge: escrituras nuevas acotadas (F4; rollback off) · dim→market: migración con mapping (F7; snapshot) · PG prod: sin cambios hasta F10/F12 (prohibido asumir equivalencia en todos los casos).

## Tests (§25)

Por fase: unit+contract (F1,F2,F4,F7,F9,F10) · integration (F2,F9,F10) · E2E YPF (F1,F9; golden inicial, expansión multi-emisor posterior) · idempotency (F2,F3,F9) · adversarial (F4) · rollback (F2,F3,F7,F9,F10) · comparación (F0,F8). Existentes verificados: e2e/c11/f050/f054/f055/market/s03/s04/ratio/identity suites `[TEST]`; a crear: contract-M7, suite-publisher, writer-census, cruce-bridge, matriz-modos, bloqueo-gate, equivalencia-M5 (diseño 09-M5). Nada declarado existente sin evidencia.

## Riesgo (§26)

R0: F0, F8 (lectura). R1: F1 (revert), F5/F6/F11 (acotados). R2: F2 (nuevo sin prod), F3 (writers), F4 (dual temporal), F7 (migración), F9 (core), F10 (gate). R3: ninguno activo en fases (el R3 de publicación se mitiga por staging; el cutover futuro requerirá autorización específica). R4: prohibido (ninguna fase lo contiene; cualquier irreversibilidad emergente → BLOCKED + autorización posterior específica).

## Producción (§27)

NINGUNA fase modifica producción sin DEV→TEST→EVIDENCIA→C10→C11 (cuando corresponda)→autorización operacional. En Paso 11: NO TOCAR PRODUCCIÓN (explícito). Cron/API/DB prod intactos.

## Golden cases (§28)

Verificación inicial con YPF en F1/F9 (golden existente); YPF≠arquitectura; expansión multi-emisor posterior (dimensiones 10 §25) como criterio de salida de F9.

## Avance (§29) y HOY/OBJETIVO (§30)

Cada fase avanza solo con precondiciones PASS + evidencia + tests + rollback + riesgo aceptado + gate; nunca por clasificación nominal. Transiciones HOY→OBJETIVO por componente en §23 (CAMBIO explícito; objetivo jamás presentado como existente).

## Resultado (§31)

### PRIMERA FASE IMPLEMENTABLE
**FASE 1 — M7 StageReport** (única primera modificación; FASE 0 evidencia corre en paralelo desde el día 0 por ser solo-lectura).

### FASES POSTERIORES
F0 (continua) → F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8 → F9 → F10 → F11 → F12 (dependencias en §22; R7.1–R7.12 preservados con M7 como quick win previo justificado).

### BLOQUEOS
Ningún bloqueo duro a nivel plan; bloqueos por candidato en 08 (E, B) y por evidencia en F8/M5. R4 ausente.

### EVIDENCIA FALTANTE
10 gaps (07 §10) como tareas F0 (tabla 07 §10 vigente).

### COMPONENTES QUE NO SE TOCAN
RAW y provenance; c11 y certificaciones; api y superficies; fetchers vigentes; jobs v2; stages s01–s03 golden; migraciones aplicadas; `.env`/secretos; tests de contrato (solo extender).

### COMPONENTES QUE NO SE BORRAN
Todos (deletes solo en F12 vía gates 08; nada listo por estar listado).

### COMPONENTES NO_MERGE
M6 precios, M2-datos, FX actual (hasta R7.11), motores ratios (hasta F8).

### PRODUCCIÓN
NO TOCAR PRODUCCIÓN EN PASO 11 (ni en ninguna fase de este plan hasta su gate operacional).

IMPLEMENTATION_PLAN_STATUS = READY_FOR_IMPLEMENTATION

(Plan ejecutable por fases con gates; F0/F1 READY, resto CONDITIONAL/PENDING_EVIDENCE. Ninguna implementación en este paso.)