# PROGRAM_LOG.md — Bitácora del programa autónomo

Fuente de continuidad entre sesiones (mitigación R-13). Consultar SIEMPRE al inicio: DECISION_QUEUE.md → este log → STAGE_GRAPH.md.

## Política de entregables (vigente desde 2026-08-23, instrucción del humano)

- **Todo entregable documental** → `outputs/docs/<area>/` (ej.: `outputs/docs/architecture/`, `outputs/docs/fase_s01/`).
- **Reportes/auditorías con datos** → `outputs/<tema>/` (convención existente: `ypf_yahoo_price_audit/`, `ypf_financial_derivation/`).
- **Código del engine** → permanece en `engine/` (ubicación funcional: los imports dependen de ella); scripts operativos en `scripts/engine/`; migraciones en `migrations/engine/`.
- Especificaciones normativas nuevas que la base documental raíz cite por nombre (ej.: PIPELINE_VALIDATION_SPECIFICATION.md) viven en `outputs/docs/` y así se referencian.

## 2026-08-23 · Reubicación de entregables PHASE 0/1

- Los 8 documentos de arquitectura movidos de `docs/architecture/` → `outputs/docs/architecture/` (referencias internas actualizadas).
- `PIPELINE_VALIDATION_SPECIFICATION.md` movido a `outputs/docs/PIPELINE_VALIDATION_SPECIFICATION.md`.

## 2026-08-23 · PHASE 0 — Architecture Decision Gate ✅ CERRADO

- Auditoría de repo completa (~90 scripts, 7 generaciones); veredictos heredados de FASE2 §4 respetados.
- Entregables creados en `outputs/docs/architecture/`: ARCHITECTURE_PLAN, DECISION_REGISTER, DECISION_QUEUE, DEPENDENCY_GRAPH, STAGE_GRAPH, RISK_REGISTER, AGENT_PLAN.
- **Gate aprobado por el humano**: D-002=PostgreSQL día 1 · D-003=paquete `engine/` clean-room · D-004=parser lxml propio · D-005=congelar FASE2 O2–O5 · D-006=benchmarks drop manual.

## 2026-08-23 · Infraestructura

- Contenedor dev creado: `catalaxia-engine-dev` (postgres:16, puerto 127.0.0.1:5433, db catalaxia). Producción (`catalaxia-db`, 5432) intacta y protegida por guarda en `engine/config.py` (EXT-010).
- Colisión `Engine/` legacy vs paquete `engine/` resuelta: legacy movido a `_legacy/Engine/` (R-15).

## 2026-08-23 · PHASE 1 — Documentación + S00 Bootstrap

- ✅ `PIPELINE_VALIDATION_SPECIFICATION.md` v1.0 autorado (cierra R-02): niveles PASS/WARNING/BLOCK, catálogo C-Sxx-nnn, conciliación EXT-NEW-008, certificación única estilo b7, señales de alarma ⇒ BLOCK, regresión como parte del gate.
- ✅ Esqueleto S00 implementado y verificado (smoke test gate=PASS, run_id=877f70d93b1042f498b72be207064229):
  - `engine/config.py` (guarda anti-prod), `engine/db.py` (migraciones ordenadas + runs), `engine/states.py` (máquina de estados estricta), `engine/report.py` (contrato engine-report-v1 con validación de conciliación).
  - `migrations/engine/001_s00_bootstrap.sql`: schemas engine.runs / stage_runs / checkpoints / schema_migrations (checkpoint reuse-key único).
  - `scripts/engine/s00_smoke.py`: corrida end-to-end PLANNED→…→CHECKPOINTED contra PG dev.
  - `engine/manifest.yaml`: SCRIPT_REGISTRY inicial (todas las piezas clase A, scope UNIVERSAL).

## 2026-08-23 · S01 IDENTITY ✅ CHECKPOINTED (gate PASS 4/4)

- run_id=63d4b9f8a6ad43788738a539b35d0aa5 · git=f51043c2 · diseño completo en `outputs/docs/fase_s01/S01_DESIGN.md`.
- Migración `002_s01_identity.sql`: identity.entities / identifiers / classifications / identifier_reviews.
- Seed fuente de registro SEC: 7.998 entidades, 18.401 identificadores, 10.403 símbolos yahoo derivados; idempotente (2ª corrida=0 inserts).
- Golden YPF verificado: `CIK:0000904851` + YPF/US + YPFD/BYMA + YPF + YPFD.BA/yahoo; CUIT/CNV NULL con motivo (llega con fase CNV).
- **Hallazgo R-16**: 4 CIKs podridos en catálogo legacy (YPF, GGAL, BMA, CRESY) — cola en `IDENTITY_REVIEWS_2026-08-23.csv`; verificar outputs legacy antes de reutilizarlos.
- YPFD no existe en ningún catálogo del repo → incorporado vía resolución manual declarativa (`data/catalogo/engine_identity_resolutions.csv`, pendiente contraste documental BYMA).
- Incidente corregido: hang de conexión psycopg2 sin timeout → connect_timeout 5s + statement_timeout 120s + bulk seed + PYTHONUNBUFFERED.

## Estado actual del stage graph

| Stage | Estado |
|---|---|
| S00 bootstrap | CERTIFIED (smoke PASS; consumido por S01) |
| S01 identity | **CHECKPOINTED** (gate PASS 4/4) |
| S02 fetch | PLANNED — siguiente |
| S03–S12 | PLANNED |

## Próximo paso

**S02 FETCH**: RAW inmutable por (cik, accession) + `_manifest.csv` + `download_log` append-only (http_status, sha256, downloaded_at); portar invalidación por fecha explícita (`_caducidad.py`); UA real + secuencial + sleep 0.3s; modo FAST = solo YPF (20-F FY2017–FY2025 con XBRL); checks C-S02-001..004; entregables documentales en `outputs/docs/fase_s02/`.
