# ÍNDICE — AUDITORÍA DE REINGENIERÍA BYMAStocks

Estado general: **FASE 1 (auditoría) completada para conjunto 01-10 sin ejecución de cambios**. Veredictos: execution graph, dependency graph, data ownership, pipeline real, duplication map, deep audit y plan de reingeniería con DELETE/MERGE pendientes y target architecture documentado.

## Orden de lectura

1. **01_EXECUTION_GRAPH.md** — quién toca qué, mapa de call sites. Hallazgo central: `scan.py` (200 lineas) mapea las dependencias reales.
2. **02_DEPENDENCY_GRAPH.md** — hub en `/scripts/engine/config.py` (67 in) y `/scripts/pipeline/run_pipeline.py` (1089); `engine/db.py` es el punto de acoplamiento para datos/hash. DANGER en caso de rediseño.
3. **03_DATA_OWNERSHIP.md** — `screener` la tabla más pública tiene 11 escritores; `stage_runs` 6 escritores; ownership fragmentado sin autor canónico.
4. **04_PIPELINE_REAL.md** — lo que corre HOY: 3 pipelines + API; no hay capa 11 real (validar y f6 autocertifican).
5. **05_DUPLICATION_MAP.md** — 266 filas de duplicación declarada en censo; prioridad: identity_v1 vs f1, ratio_engine vs f4, engine vs legacy.
6. **06_DEEP_AUDIT.md** — 6 fichas (f1=FAIL, f4=FAIL, f6=DANGER, run_all=ATTENTION, identity_v1=PASS, identity_v1 enfoque=PASS_WITH_WARNINGS).
7. **07_REENGINEERING_PLAN.md** — orden R1..R13 propuesto; P0 gobierno, P1 capa 11, P2 consolidación, P3 nivelación, P4 higiene.
8. **08_DELETE_PLAN.md** — candidatos SIN ejecutar; checklist de 10 pasos vacío; nada se borra.
9. **09_MERGE_PLAN.md** — 10 candidatos priorizados SIN ejecutar (M1 identidad, M2 ratios, M3 pipeline, M4 sec fetch).
10. **10_TARGET_ARCHITECTURE.md** — estado final deseado: 1 dominio por dato, capa 11 independiente, RAW inmutable, ownership único, cero secretos.

## Decisión abierta para el owner

- La **fase 1 (auditoría)** está completa: no se ha ejecutado ningún cambio.
- El siguiente paso es **fase DEFINIR**: convertir estas fichas en entregables (contratos por R1..R13 con checks y gates).

## Regla de seguridad aplicada

> Toda modificación futura (DELETE/MERGE/rewrite) requiere 10 pasos: dependencias reales, ownership, duplicación semántica, comportamiento, consumidores, impacto, alternativa, plan de migración, verificación, certificación. Nada de todo esto se ejecuta en fase 1.