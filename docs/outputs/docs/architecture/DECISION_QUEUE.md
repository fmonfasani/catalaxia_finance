# DECISION_QUEUE.md — Decisiones que requieren aprobación humana

Actualizado: 2026-08-23 · PHASE 0 Architecture Decision Gate.
Regla del programa: el pipeline NO escribe código de etapas hasta vaciar esta cola. Consultar este archivo AL INICIO de cada fase.

## Cola activa (0)

_(vacía — las 5 decisiones del gate fueron aprobadas el 2026-08-23; ver Log de consultas y DECISION_REGISTER.md)_

### D-002 · Almacenamiento de artefactos por capa
- **Opciones**: (A) Parquet por capa + SQLite `state.db` para registries/runs/gates/checkpoints `[RECOMENDADA]` · (B) todo SQLite · (C) PostgreSQL desde día 1.
- **Por qué A**: capas analíticas grandes (PARSED ~millones de filas) fluyen mejor en columnar; el estado transaccional (gates, checkpoints, runs) en SQLite; espeja la cadena vigente SQLite local → PG prod; clase A reproducible.
- **Impacto**: todas las capas. **Reversibilidad media** (wrapper de IO aísla).

### D-003 · Hogar del código
- **Opciones**: (A) paquete nuevo `engine/` top-level, sin imports de legacy; adapters explícitos donde reutilice lógica portada `[RECOMENDADA]` · (B) extender `backend/`.
- **Por qué A**: legacy queda intacto como fallback consultable (regla maestra §1.4); evita mezclar generaciones (lección EXT-NEW-007 / segunda entry point).
- **Impacto**: estructura del repo. **Reversibilidad alta ahora, baja después.**

### D-004 · Parser XBRL
- **Opciones**: (A) parser propio lxml portado del piloto YPF (ya cubre los 4 layouts FY2017–FY2025), arelle como herramienta opcional de validación offline `[RECOMENDADA]` · (B) adoptar arelle como dependencia dura.
- **Por qué A**: control total de provenance por fact, cero dependencia pesada, código ya probado contra YPF.
- **Impacto**: S03 completo. **Reversibilidad media.**

### D-005 · Relación con oleadas FASE2 O2–O5 (ports/unificación/bajas/correction_log sobre legacy)
- **Opciones**: (A) congelar O2–O5 salvo fix crítico; el engine absorbe esos ports directamente y legacy queda congelado read-only `[RECOMENDADA]` · (B) terminar O2–O5 primero y construir el engine después.
- **Por qué A**: evitar doble migración (portar controles a M1 y luego al engine); O1 ya ejecutada elimina el riesgo más grave (hardcodes).
- **Impacto**: plan de trabajo paralelo. **Reversibilidad alta.**

### D-006 · Adquisición de benchmarks (PHASE 11)
- **Opciones**: (A) drop manual exportado (TIKR/StockAnalysis CSV) en `data/raw/benchmarks/{source}/{YYYY-MM-DD}/`, loader con estándar admisión §2.2, clase C documentada `[RECOMENDADA]` · (B) intentar scraping automatizado.
- **Por qué A**: precedente Cloudflare (investing fallido); contraste conserva ambos valores + diferencia (EXT-NEW-006).
- **Impacto**: PHASE 11. **Reversibilidad alta.**

## Resueltas

| ID | Resolución | Fecha |
|---|---|---|
| D-002 | **PostgreSQL día 1** (opción C — decisión del humano, difiere de la recomendación A). Todas las capas PARSED→PUBLISHED en PG; RAW sigue siendo archivo inmutable + índice en DB | 2026-08-23 |
| D-003 | Paquete nuevo `engine/` top-level, clean-room (recomendación aprobada) | 2026-08-23 |
| D-004 | Parser propio lxml portado del piloto YPF; arelle solo validación offline opcional (aprobada) | 2026-08-23 |
| D-005 | Congelar O2–O5 de FASE2; engine absorbe los ports; legacy read-only (aprobada) | 2026-08-23 |
| D-006 | Benchmarks por drop manual validado en `data/raw/benchmarks/`, clase C documentada (aprobada) | 2026-08-23 |

## Log de consultas

| Fecha | Decisión | Resultado |
|---|---|---|
| 2026-08-23 | D-002…D-006 presentadas al humano | **APROBADAS** (D-002=C, D-003=A, D-004=A, D-005=A, D-006=A) → gate cerrado, programa continúa autónomamente |
