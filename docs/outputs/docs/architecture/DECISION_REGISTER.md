# DECISION_REGISTER.md — Catalaxia Financial Data Engine

PHASE 0 deliverable · 2026-08-23 · Registro acumulativo de decisiones arquitectónicas (ADRs).
Convención: toda decisión con impacto estructural vive aquí; las pendientes de aprobación humana viven además en DECISION_QUEUE.md.

## Resueltas (heredadas)

| ID | Tema | Resolución | Origen | Fecha |
|---|---|---|---|---|
| D1 | Base canónica publicable del screener | `screener` M1 + certificación b7; M2 congelado | FASE2_PLAN_CONSOLIDACION §5/§7 | 2026-08-22 |
| O1 | Hardcode DB paths corregido en 32 scripts (`SCREENER_DB`) | EJECUTADA, grep=0 restantes | FASE2 oleada O1 | 2026-08-22 |

## Aceptadas PHASE 0 (gate 2026-08-23)

| ID | Tema | Decisión | Impacto si se cambia después | Reversibilidad |
|---|---|---|---|---|
| D-002 | Artefactos de almacenamiento por capa | **PostgreSQL desde día 1** (elección del humano; difiere de la recomendación Parquet+SQLite). RAW sigue siendo archivo inmutable + índice/manifest en DB; PARSED→PUBLISHED en PG | Alto (todas las capas) | Media |
| D-003 | Hogar del código del engine | Paquete nuevo top-level `engine/`, clean-room, legacy intacto como referencia | Medio | Alta (antes de mucho código) |
| D-004 | Parser XBRL: propio vs arelle | Parser propio lxml portado del piloto YPF; arelle opcional solo validación offline | Alto | Media |
| D-005 | Relación con oleadas FASE2 O2–O5 | Congelar O2–O5 (salvo fixes críticos); el engine absorbe los ports directamente | Bajo | Alta |
| D-006 | Adquisición de benchmarks (PHASE 11) | Drop manual validado en `data/raw/benchmarks/` clase C; sin scraping automatizado | Bajo | Alta |

Implicancia operativa D-002: desarrollo local requiere instancia PG (docker compose `catalaxia-db` PG16); verificación de infra = primer paso de S00 (riesgo R-14).

## Plantilla ADR

```
ADR-xxx | fecha | fase | estado PROPOSED→ACCEPTED→SUPERSEDED
tema / opciones / decisión / consecuencias / revisión-gatillo
```

Regla EXT-NEW-007 aplicada a este registro: una decisión reemplazada no se borra, pasa a SUPERSEDED con link a su reemplazo.
