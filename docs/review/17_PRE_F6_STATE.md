# 17 — Estado pre-F6 (baseline, solo lectura)

F5 cerrado (STEP_16 PASS, NEXT_PHASE=F6). Solo lectura + este documento.

- Git HEAD `2993918` rama `fix/ttm-ratios-cnv`; F5 agrega `test_f5_multisource.py` + `16_*` (cero cambios de código productivo en F5). `[EJECUCIÓN: git]`.
- C10 existente: gates S00–S04 + c3 (`GateStatus`/`assert_transition`/`StageReport`, autoridad motor); m4 `gates_*` + `veredicto` PASS/WARN/FAIL consumido por m5 (autoridad market); job7 (limpieza suspects, SQLite); suites informativas (validar_suite, o2_*, gate_roe); `30_validaciones` (insumo, no bloqueo). C11: `c11_certificar` + `engine.certifications` (443+DEV). C12: s5/sync/publisher+gate. `[CÓDIGO]`.
- `stage_runs` con gates PASS (YPF/KO) y BLOCK (L/M/N e2e + fixtures); certificaciones CERTIFICADA (runs E2E) y NEGADA (cb2a7fd5, demo F6: motivo evidencia C10 insuficiente). `[EJECUCIÓN]`.
- Tests: 14/14 F5 + suites históricas verdes; suite completa con 32 fallos preexistentes documentados (derivados de prerrequisitos ausentes, no de regresiones). `[EJECUCIÓN]`.
- Gaps: S03-replace (BLOCKER condicional), M5 numérica, hist-writer, TLS/auth, cron-VPS, runtime legacy. Publisher/C11/C12/legacy/producción intactos.
- Veredicto: PROCEED (F6 solo-lectura + evaluador C10 nuevo; sin tocar autoridades existentes).
