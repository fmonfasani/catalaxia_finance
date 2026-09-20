# 08 — Delete Plan (define, no ejecuta)

**FASE 2 — REINGENIERÍA, PASO 8.** Convierte los candidatos de 07 §12 en un plan verificable. Este paso DEFINE; NO ejecuta ni implementa nada (cero DELETE/ARCHIVE/MOVE/RENAME/cambios de código, DB, migraciones o producción). Base: 01–06 + 07 + 07A (0 contradicciones, D1–D10 confirmadas, READY_FOR_STEP_8, ajustes A1–A12 vigentes).

Definiciones: DEPRECATE = deja de ser recomendado, permanece. ARCHIVE = retiro del camino activo con restore+SHA+provenance. DELETE = eliminación destructiva. Etiquetas (legacy/duplicado/sin-caller/candidato) NO autorizan nada. "DECIDIDO" en 07 ≠ autorización de ejecución.

## Ficha A — engine/s03.py → DELETE_APPROVED_FOR_FUTURE

- Identificación: A · `engine/s03.py` · librería XBRL-parse · C4 · planos EJECUCIÓN (código) sin efecto runtime.
- Función: importa `engine.xbrlparse`+`engine.fetch`; expone parseo por librería. Sin tablas/archivos/efectos propios.
- Ejecución (18 criterios): función verificada `[CÓDIGO]`; import/caller/subprocess/cron/job/API/scheduler: ninguno en todo el repo (grep `engine.s03|import s03`: 0 resultados fuera de definiciones) `[CÓDIGO]`; tests: ninguno lo importa `[CÓDIGO]`; referencias dinámicas (`__import__` por nombre): ninguna coincide `[CÓDIGO]`; ejecución indirecta: descartada por búsqueda exhaustiva (única reserva: un import construido por string no hallado — riesgo residual R0).
- Consumidores/writers/readers: ninguno. Sustituto: innecesario (código sin uso; la vía viva es `s03_parse_ypf`→`engine.xbrlparse`). Provenance/C10/C11/C12: ningún impacto.
- Riesgo: R0 (archivo) / R1 (proceso). Precondiciones: backup git + SHA registrado; ventana formal de no-uso; verificación posterior (py_compile + suites e2e/c11/f054). Rollback: R1 (git restore). Fase: R7.12.
- Caso especial §9: verificado más allá de la ausencia de import (búsqueda dinámica incluida).

## Ficha B — job5_extract_eeff.py / job6_extract_div.py (v1) → DELETE_BLOCKED

- Identificación: B1/B2 · `scripts/tickets/cnv/jobs/job5_extract_eeff.py`, `job6_extract_div.py` · extracción CNV v1 · C3/C4 · plano EJECUCIÓN.
- Función: misma CLI y mismas tablas destino que v2 (`cnv_estados*`, `cnv_dividendos`) `[CÓDIGO]`.
- Ejecución: sin caller productivo (solo docstring de `build_subset.py` + autodoc) `[CÓDIGO]`; cron: no; tests: no directos (`_test_v2` cubre v2). Ejecución indirecta/runtime histórico: `[NO DETERMINABLE]` (pudo correrse manualmente; sin logs propios).
- Consumidores: ninguno productivo. Sustituto: v2 vigente en todos los caminos (run_all, run_update) `[CÓDIGO]`; equivalencia de contenido no comparada numéricamente (innecesaria si v1 no corre, pero consta como reserva).
- D4 manda DEPRECATE→ventana→ARCHIVE: convertirlo en DELETE inmediato violaría la secuencia decidida → **bloqueo por dependencia de fase** (R7.6 + R7.12), no por falta de evidencia.
- Riesgo R1. Rollback R1 (git + SHA). Desbloqueo: deprecate en R7.6 + ventana + archive en R7.12 + re-evaluación. Fase: R7.12.

## Ficha C — construir_catalogo.py → DELETE_PENDING_EVIDENCE

- Identificación: C · `scripts/tickets/sec_edgar/scripts/construir_catalogo.py` · catálogo EDGAR legacy · C2/C4 · plano DATOS+EJECUCIÓN.
- Función: construye `tickers`, `descargas_log`, `empresas` con **DROP TABLE `empresas`** + INSERT/UPDATE `[CÓDIGO]` (05 G11, 03 §16.4).
- Ejecución: sin caller/cron/subprocess hallado `[CÓDIGO]`; runtime productivo: `[NO DETERMINABLE]` (gap 07 §10) — criterio 5/7 sin cerrar.
- Consumidores: `tickers` sin lectores hallados `[CÓDIGO]`; `descargas_log` copiada a PG por migrate (downstream existente, lectores PG `[NO DETERMINABLE]`) `[CÓDIGO]`; `empresas` 4 writers (vía productiva = construir_base).
- Sustituto: construir_base cubre `empresas`/`facts`, pero NO `tickers`/`descargas_log` → sustitución incompleta (decidir cobertura antes).
- Provenance: `descargas_log` es log de descargas (valor de auditoría). C10: n/a directo. C11/C12: vía migrate (copia).
- D5 exige no-runtime + ARCHIVE previo. Riesgo R2 (DROP-writer; el archivo en sí es R1, las tablas huérfanas son R2).
- Precondiciones: probar no-runtime (ventana+logs) · resolver lectores PG de `descargas_log` · decidir `tickers`/`descargas_log` (migrar cobertura o archivar tablas) · ARCHIVE primero (R7.12). Rollback: R1 (archivo) + R2 (snapshot tablas si se tocan — el DELETE aquí es solo archivo; las tablas permanecen).
- Nota: eliminar el archivo NO elimina las tablas (quedarían sin writer — registrar como estado aceptado o archivar tablas aparte).

## Ficha D1 — screener_gold (+f5_screener.py, f6_sec.py) → DELETE_PENDING_EVIDENCE

- Identificación: D1 · tabla `screener_gold` + productores `scripts/pipeline/f5_screener.py`, `f6_sec.py` · staging legacy · C7 · plano DATOS.
- Función: ensamble del pipeline legacy (CREATE + INSERT) `[CÓDIGO]`.
- Ejecución: productores sin caller salvo run_pipeline (legacy) `[CÓDIGO]`. Lectores de `screener_gold`: `[NO DETERMINABLE]` (gap 07 §10: demo DBs tienen su propia copia, irrelevante) → criterio 4 sin cerrar.
- Sustituto: `screener` (producto) — equivalencia no demostrada ni necesaria si no hay lectores; primero cerrar el gap.
- Provenance/C10: ausente salvo logs legacy. C11/C12: ninguno.
- Riesgo R2 (lector desconocido). Precondiciones: cerrar gap lectores · R7.9 (core no depende) · backup/SHA · ventana. Rollback R2 (snapshot + git). Fase: R7.12.

## Ficha D2 — fact_ratios (+f4_ratios.py) → DELETE_PENDING_EVIDENCE

- Identificación: D2 · tabla `fact_ratios` + productor `scripts/pipeline/f4_ratios.py` · ratios legacy · C8 · plano DATOS.
- Función: ratios desde `fact_financials` (DROP+CREATE) `[CÓDIGO]`.
- Lectores: `[NO DETERMINABLE]` (gap 07 §10) → criterio 4 sin cerrar. Sustituto: ninguno 1:1 (D7 prohíbe merges sin equivalencia numérica).
- Tensión A4 (07A): archivable solo si f4 se decommissiona (R7.8/R7.12); en caso contrario KEEP.
- Riesgo R2. Precondiciones: gap lectores + decisión f4 (R7.8) + backup/SHA + ventana. Rollback R2. Fase: R7.12.

## Ficha E — f-series restantes → DELETE_BLOCKED

- Identificación: E · `scripts/pipeline/` (run_pipeline, f1, f2_reextract_batch, f2_adr, f3_normalizar_cnv, f3b, fix_*, gate_autoreporte, validar_suite*, e2e_ticker, arbitro, scoreboard, triangulacion, gen_screener_html, fetch_dgce, cnv_codes, sec_adr_validar) · pipeline legacy · C2/C4/C5/C7/C8/C10 · planos DATOS+EJECUCIÓN.
- Función: cadena legacy SQLite → `dim_*`, `cnv_reextract`, `fact_financials`, `fact_ratios`, `screener_gold`, suites, gates `[CÓDIGO]` (04 §7).
- Ejecución: caller único run_pipeline (sin cron) `[CÓDIGO]`; menciones externas solo en comentarios/docstrings (c11:15 declara NO acoplarse a f6_sec; s2a:29 cita fix_manual como antecedente) `[CÓDIGO]` — no son dependencias.
- **Bloqueo 1 (dependencia viva)**: market `m1_symbol_mapping` lee `dim_instrument` de f1 (D6/R7.7) `[CÓDIGO]` — eliminar f1 rompe m1.
- **Bloqueo 2 (fase)**: R7.7 (market canónico) + R7.9 (core) pendientes; D6/D3 lo exigen previo.
- **Bloqueo 3 (evidencia)**: rol bloqueante real de `validacion_suite`/`gate_roe`/`o2_*` es `[NO DETERMINABLE]` (gap 07 §10).
- Miembros sin dependencia propia (e2e_ticker, arbitro, scoreboard, triangulacion, gen_screener_html, fetch_dgce, cnv_codes, sec_adr_validar): heredan el bloqueo de grupo (coherencia del directorio); re-evaluación individual en R7.12.
- Riesgo R2–R3 (DB compartida + dependencia viva). Rollback R2 (snapshot `screener.db` + git). Desbloqueo: R7.7 (dim migrado/contratado) + R7.9 + gaps suites cerrados.
- Caso §9: D6 respetado (nada se elimina antes de R7.7/R7.9).

## R4 — análisis

R4 = irreversible. Ningún DELETE propuesto es R4: A es R1 (git restore), B/C/D/E son R1–R2 (git + snapshot + SHA). No se propone ningún DELETE de datos RAW, provenance, control, certificaciones ni publicación vigente. Regla: si en la ejecución futura algún rollback resultara inviable, el estado pasa automáticamente a DELETE_BLOCKED (sin inferir seguridad).

## Relación con R7.1–R7.12

A→R7.12 · B→R7.6 (deprecate) →R7.12 (archive→re-evaluar) · C→R7.3 (ownership) + gaps →R7.12 · D1/D2→R7.8/R7.9 + gaps →R7.12 · E→R7.7+R7.9+gaps →R7.12. Ningún DELETE se adelanta a su fase-precondición. R7.1/R7.10/R7.11 no son precondición de estos candidatos (independientes).

## Matriz global

| ID | Componente | Capa | Plano | Función | Consumidores | Sustituto | Evidencia | Riesgo | Precondiciones | Rollback | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | engine/s03.py | C4 | EJEC | lib XBRL | ninguno | innecesario | 0 refs (incl. dinámicas) | R0/R1 | backup+SHA, ventana, verificación | R1 git | DELETE_APPROVED_FOR_FUTURE |
| B1/B2 | job5/6 v1 | C3/C4 | EJEC | extracción CNV | ninguno prod. | v2 vigente | sin caller; D4 manda archive | R1 | R7.6 deprecate, ventana, R7.12 archive | R1 | DELETE_BLOCKED |
| C | construir_catalogo | C2/C4 | DATOS+EJEC | catálogo EDGAR | tickers:ninguno; descargas_log:migrate | base (parcial) | sin caller; gaps runtime/lectores | R2 | no-runtime, lectores PG, cobertura tablas, ARCHIVE | R1+R2 | DELETE_PENDING_EVIDENCE |
| D1 | screener_gold+f5/f6 | C7 | DATOS | ensamble legacy | ND | screener (no probado) | gap lectores | R2 | gap + R7.9 + backup/SHA + ventana | R2 | DELETE_PENDING_EVIDENCE |
| D2 | fact_ratios+f4 | C8 | DATOS | ratios legacy | ND | ninguno 1:1 | gap lectores + A4 | R2 | gap + decisión f4 R7.8 + backup/SHA | R2 | DELETE_PENDING_EVIDENCE |
| E | f-series (grupo) | C2–C10 | DATOS+EJEC | pipeline legacy | m1←dim_instrument | core D3 (futuro) | caller único legacy; 3 bloqueos | R2–R3 | R7.7 + R7.9 + gaps suites | R2 | DELETE_BLOCKED |

## Matriz de gates

| Candidato | Evidencia requerida | Fase requerida | Test | Validación | Certificación | Backup | Ventana | Rollback | Gate |
|---|---|---|---|---|---|---|---|---|---|
| A | ventana no-uso formal | R7.12 | suites e2e/c11/f054 | C10 (suites verdes) | n/a | git+SHA | sí | R1 probado | PASS suites + SHA registrado |
| B1/B2 | deprecate + no-uso | R7.6→R7.12 | jobs v2 verdes | job7 + assemble | n/a | git+SHA | sí | R1 probado | archive completo + re-evaluación |
| C | no-runtime + lectores PG + cobertura | R7.3→R7.12 | rebuild verde sin el archivo | C10 rebuild | n/a | git+SHA+snapshot | sí | R1+R2 probado | 3 evidencias + ARCHIVE previo |
| D1/D2 | gap lectores + R7.8/R7.9 | R7.12 | suites dominio | C10 | n/a | git+SHA+snapshot | sí | R2 probado | gaps cerrados + A4 (D2) |
| E | R7.7 + R7.9 + gaps suites | R7.12 | e2e + market tests | C10 | n/a | git+SHA+snapshot DB | sí | R2 probado | dim migrado + core verde + suites |

## Secuencia futura (no ejecutar)

DELETE-0 PREPARACIÓN (backup/SHA/ventana definida) → DELETE-1 EVIDENCIA (cerrar criterios 1–18) → DELETE-2 SUSTITUCIÓN (sustituto vigente verificado) → DELETE-3 VENTANA NO-USO (tramo sin ejecución) → DELETE-4 BACKUP/SHA (snapshot final) → DELETE-5 DELETE FUTURO (solo estado APPROVED) → DELETE-6 VERIFICACIÓN (suites + rebuild) → DELETE-7 C10 (gates verdes) → DELETE-8 C11 si aplica (ningún candidato actual la requiere) → DELETE-9 CIERRE (registro en provenance del cambio).

## Resultado final

- Puede llegar a eliminarse (vía secuencia, tras gates): **A** (engine/s03.py) — único APPROVED_FOR_FUTURE.
- Solo deprecatearse ahora: **B1/B2** (R7.6), resto según fase.
- Debe archivarse antes de cualquier delete: **B** (R7.12), **C** (condicional), **E** (tras R7.7/R7.9).
- Bloqueado: **B** (dependencia de fase D4), **E** (dependencia viva m1←dim + fases + gaps).
- Necesita evidencia: **C** (runtime, lectores PG `descargas_log`, cobertura `tickers`), **D1/D2** (lectores).
- Necesita sustituto verificado: ninguno pendiente salvo cobertura de C (tickers/descargas_log).
- Depende de R7.1–R7.11: E (R7.7/R7.9); D2 (R7.8); C (R7.3). R7.1/R7.10/R7.11 independientes de estos deletes.
- Nunca debe eliminarse (alcance de este plan): RAW físico y su provenance; tablas/escritores de control (`engine.*`, checkpoints, certifications); publishers y API vigentes; migraciones; `.env`; tests de contrato; librerías `engine.*` en uso; jobs v2; stages s00–s04; m1/m2/m4; materia_prima y cadena silver; `build_subset.py` (subconjunto quarterly vigente); `_raw_inmutable`, `_ingesta_log`, `_caducidad`, `_run_manifest`.
- Impacto por capa si se ejecutara: A ninguno · B reduce capacidad de extracción redundante (v2 cubre) · C deja `tickers`/`descargas_log` sin writer (migrate seguiría copiando última foto) · D1/D2 retira staging legacy sin lector · E retira C2/C4/C5/C7/C8/C10 legacy (exige dim migrado o m1 cae).

## Verificación final

- `08_DELETE_PLAN.md` creado; 07/07A intactos (no modificados); código/DB/migraciones/producción intactos; cero DELETE/ARCHIVE/MOVE/RENAME/REFACTOR ejecutados (solo lectura + greps + este documento).

DELETE_PLAN_STATUS = READY_FOR_IMPLEMENTATION

(El plan es implementable exclusivamente a través de sus gates: solo A puede avanzar a DELETE-0…9 cumplidas sus precondiciones; B–E permanecen gated por evidencia/fase. Ningún delete se autoriza por este documento fuera de su gate.)