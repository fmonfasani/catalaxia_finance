# CATALAXIA V1.0 — RELEASE CHECKLIST

**Ejecutado:** 2026-08-28 · **Resultado: 29/29 verificados, sin fallos**
Cada casilla se marcó **por consulta a la base**, no a mano.
Evidencia: `docs/release/_checklist.json`

---

## Homologación

- [x] **homologation gate PASS** — `HOMOLOGATED_WITH_NOTES`, 17 preguntas respondidas
- [x] **estado actual coincide con el baseline** — entities 525 · assertions 614 · CIK 513 · CUIT 3 · bridges 3
- [x] **0 corridas RUNNING** — sobre 241 (OK 61 · ABORTED 132 · BLOCKED 48)
- [x] **findings correctamente clasificados** — 15 CLOSED · 4 CLOSED_WITH_NOTES · 1 OPEN (F-043) · 1 MITIGADO · 1 no reproducible

## Integridad — los siete ceros

- [x] CIK autoritativo duplicado — **0**
- [x] entidad con dos CIK autoritativos — **0**
- [x] identifiers huérfanos — **0**
- [x] contaminación de tipo — **0**
- [x] entidades muertas con identidad — **0**
- [x] `VERIFIED` sin evidencia — **0**
- [x] `HUMAN_DECISION` firmada por proceso — **0**

## Capas

- [x] **SEC cerrado** — units `DIVIDED` sin `numerator`/`denominator`: 0 · `fact_key` duplicados: 0 · checkpoints en corrida ≠ OK: 0
- [x] **Identity: garantías verificadas** — 15 triggers · 27 CHECKs · 11 índices únicos · 6 críticas demostradas por mutación
- [x] **Market documentado** — 584/584 con `venue_ticker` · M23 577 SUCCESS todas con `sha256` · 0 `FAILED` declarando datos
- [x] **CNV: alcance explícito** — 3 empresas con CUIT ratificado; **no se declara cobertura total**
- [x] **backfill CIK idempotente** — 0 duplicados; hash de identidad estable entre corridas

## Congelamiento

- [x] **no existen cambios no documentados** — baseline == estado auditado, campo por campo
- [x] **no existen migraciones pendientes** — 29/29 registradas en `engine.schema_migrations`
- [x] **no existen modificaciones de datos** — este ciclo no escribió una sola fila
- [x] **no existen cambios en `data/raw`** — `git status data/raw` limpio
- [x] **hashout determinista** — 5/5 tablas

## Entregables

- [x] `CATALAXIA_V1_BASELINE.json` — generado desde la base, ningún valor a mano
- [x] `CATALAXIA_V1_MANIFEST.json` — 32 migraciones · 16 módulos engine · 27 scripts · 14 tests · 11 contratos · 20 documentos de auditoría · 7 de evidencia, con sha256
- [x] `CATALAXIA_V1_RELEASE.md` — alcance, exclusiones, baseline, rollback
- [x] `POST_V1_BACKLOG.md` — P0 a P3, nada implementado

---

## Nota de método

Dos verificaciones detectaron desajustes aparentes que **no lo eran**, y se resolvieron
midiendo en vez de suponer:

1. **«29 migraciones registradas vs 32 archivos»** — los 3 restantes son de
   `migrations/market/`, que no usa `engine.schema_migrations`. Engine: **29/29**.
2. **La descripción del encargo lista «614 identifiers / 574 entities»** — los valores
   reales son 614 **assertions**, 574 **identifiers vigentes** y 525 **entities**.
   Corregido en el baseline, que sale de la base.
