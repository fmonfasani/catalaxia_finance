# 21 — Implementation Result F9

Reconciliación (18 puntos): inventario global (runs/stage_runs/checkpoints/certs/publos) ✓ · 16 residuos RUNNING reconstruidos uno a uno ✓ · **0 huérfanas operativas** (`engine.runs` RUNNING=0; detector `corridas_huerfanas`=0) ✓ · residuo = runs ABORTED+`finished_at` muertos, etapa sin gate/report/checkpoint ✓ · clasificación 16=D explicados, 0 NO DETERMINABLE ✓ · causa raíz transversal: `run_scope` cierra solo run-level y el enum de etapa no tiene terminal ABORTED ✓ · comparado contra S03/F-009 (distinto defecto: S03 no cerraba el run; hoy cierra) ✓ · idempotencia de re-run verificada por código+tests (no duplica facts, 1 cert por run, gate bloquea publicación) ✓ · propuesta por caso: NO ACTION + gap mecanismo (sin inventar estados) ✓ · gaps post-F8: 13 con capa/plano/dependencia/severidad/bloqueo/evidencia ✓ · orden propuesto por dependencia/riesgo ✓ · tests nuevos protegen contratos antes desprotegidos (test_f9 6/6 read-only) ✓ · regresión: 101 passed/8 skipped, 9 FAIL preexistentes (family identity/universo CNV stale, autodeclarada en F6) ✓ · cero escrituras (sin UPDATE masivo, sin borrados, sin archivos, sin conversiones de estado) ✓ · producción intacta ✓ · residuo de etapa NO tocado (regla) ✓ · hallazgos sin implementar (Paso 9: DETENER) ✓.

**Hallazgo principal (F9):** la terminalidad está bien garantizada a nivel de corrida (F-040/F-050, 0 huérfanas run-level) pero la **máquina de estados de etapa no modela el aborto** (sin terminal ABORTED; `run_scope` no registra evento de etapa). Consecuencia: residuo informativo stage-RUNNING (hoy 16, reproducido por la propia suite F-040/F-050) sin evidencia ni efectos colaterales. Defecto NO bloqueante de datos/provenance/publicación → candidato a fase de control (F10) con modificación mínima documentada (nuevo `StageState.ABORTED` + cierre de etapa en el path de excepción + sweeper transaccional explícito + actualización de fixtures `limpiar`).

## Resumen de estado requerido

| ESTADO | CANTIDAD | RESULTADO |
|---|---|---|
| RUNNING (engine.runs / nivel corrida) | 0 | RECONCILIADO (sin huérfanas operativas) |
| RESIDUO stage RUNNING (runs ABORTED) | 16 | EXPLICADO (D, NO ACTION sobre datos) |
| FAILED (runs) | 138 (etapa) / BLOCKED 207 (runs) | RECONCILIADO (terminales con evidencia) |
| CHECKPOINTED (etapas terminales) | 593 | RECONCILIADO |
| CERTIFICADA | 239 | RECONCILIADO |
| NEGADA | 317 | RECONCILIADO |
| PUBLICACIONES (staging) | 4 activas + 5 rolled_back | RECONCILIADO (todo staged, sin cutover) |

| GAP | SEVERIDAD | BLOQUEA PRODUCCIÓN | PRÓXIMA ACCIÓN |
|---|---|---|---|
| TLS verify=False | BLOCKER | SÍ | F10 — endurecer fetch (luego del cierre de fase) |
| auth/CORS API | BLOCKER | SÍ | F10 — autorización + tests API |
| cron-VPS | BLOCKER | SÍ | F10 — automatización tras runtime |
| S03 replace/dangling | BLOCKER condicional | SÍ cuando se manifiesta | F10 — no-replace-world + validación |
| runtime legacy | HIGH | condiciona cron | F10 — entorno VPS |
| CNV E2E | HIGH | condiciona alcance | F10 — cadena CNV completa PG |
| M5 / hist-writer | HIGH | condiciona mercado | F10 — schedule + hist |
| ratios equivalence | HIGH | no | F10 — matriz de equivalencias |
| estado terminal de etapa (11) | HIGH | no | F10 — fase de control (StageState.ABORTED) |
| market quality / tests stale | MEDIUM | no | F10 — audits + fixtures |
| 16 residuos stage | NO-BLOCK | no | post-mecanismo: sweeper transaccional |

- Archivos: creados `21_PRE_F9_STATE.md`, `21_F9_STATE_RECONCILIATION.md`, `21_F9_GAP_MATRIX.md`, este resultado, `tests/test_f9_state_reconciliation.py`. Código productivo: intacto. Side effect DEV: +1 residuo stage por reproducción de la suite F-040 (esperado, evidencia del defecto transversal).

STEP_20_STATUS = PASS_WITH_WARNINGS
NEXT_PHASE = F10

DETENIDO — sin implementación en F9; F10 no iniciado.