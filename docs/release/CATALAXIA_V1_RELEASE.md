# CATALAXIA V1.0.1
## HOMOLOGATED_WITH_NOTES
## RELEASE_READY

> **Actualizado 2026-08-29, ciclo de release freeze.**
>
> **F-048 CERRADO.** El release quedó capturado en commit propio, con los
> **148 archivos** de V1: las 29 migraciones de engine
> registradas, las 3 de market, `engine/identity_v1.py`, `engine/hashout.py`, las
> garantías F-035/036/037/044/045, 11 contratos, 23 auditorías y 14 tests. Ningún
> artefacto ajeno: 413 archivos quedaron fuera por decisión explícita.
>
> **F-049 CERRADO (2026-08-29).** Se retiró el auto-registro de 16 migraciones:
> `engine.schema_migrations` lo escribe únicamente el runner. Instalación desde
> cero verificada sobre base descartable — 29/29 migraciones, 0 duplicados,
> estructura idéntica a la homologada (15 triggers, 27 CHECKs, 11 índices).
> Banco adversario 14/14, auditoría independiente 9/9. Ver `MIGRATIONS_CONTRACT.md`.
>
> **`v1.0.0` (6ac4859) no se movió.** El release distribuible es **`v1.0.1`**.
>
> El defecto original era: la prueba de
> reproducibilidad sobre base descartable reveló que el runner de migraciones **no
> puede aplicar sus propias migraciones**: 16 de las 29 se auto-registran en
> `engine.schema_migrations` con `ON CONFLICT`, y el runner las registra otra vez
> **sin** `ON CONFLICT`. Choca contra su propia PK en `008` y, como corre en una
> sola transacción, revierte todo. Nunca se había visto porque esas 16 siempre se
> aplicaron a mano con `psql -f`.
>
> **La homologación sigue siendo válida.** Ver `docs/review/F049_FINDING.md`.

**Versión:** 1.0.1 · **Fecha:** 2026-08-29 (V1.0.0: 2026-08-28)
**Instancia homologada:** `catalaxia-engine-dev` 127.0.0.1:5433
**Baseline:** `docs/release/CATALAXIA_V1_BASELINE.json` (generado desde la base, no escrito a mano)
**Manifiesto:** `docs/release/CATALAXIA_V1_MANIFEST.json`

---

## 1. Estado

| | |
|---|---|
| Dictamen de homologación | **HOMOLOGATED_WITH_NOTES** (sin cambios) |
| Blockers **funcionales** | **0** |
| Commit de release | **`v1.0.1`** · 148 archivos de V1 + fix de F-049 |
| F-048 | **CLOSED** — el release ya esta capturado en un commit |
| F-049 | **CLOSED** — instalación desde cero verificada |
| Release | **READY** · tag **`v1.0.1`** |
| Cambios de datos en este ciclo | **0** |
| Cambios de schema en este ciclo | **0** |
| Cambios en `data/raw` | **0** |

---

## 2. Baseline congelado

Todos los valores salen de PostgreSQL o del filesystem.

### Identity V1

```
entities ....................... 525   (ACTIVE 513 · MERGED 8 · PROVISIONAL 4)
assertions ..................... 614   (VERIFIED 532 · CANDIDATE 73 · REVIEW_REQUIRED 9)
assertions superseded ...........  6
identifiers totales ............ 583   vigentes 574   autoritativos 520   RETIRED 6
  CIK  autoritativos ........... 513
  LEI  autoritativos ...........   4
  CUIT autoritativos ...........   3      CUIT candidatos 53
  CNV_ENTITY_ID candidato ......   1
reviews ........................  14   (OPEN 11)
conflicts ......................   1
bridges ........................ VERIFIED 3 · CANDIDATE 4
sources ........................   9
```

> **Corrección a la descripción del encargo.** El encargo lista «614 identifiers /
> 574 entities». Los valores reales son **614 assertions**, **574 identifiers
> vigentes** y **525 entities**. Se corrige aquí porque el baseline debe salir de la
> base, no de un resumen.

### SEC

```
filings .................... 27 = 18 PRE_XBRL + 9 con XBRL
  parseados (S03) ..........  9        normalizados (S04) ..... 9
parsed.facts ............... 67.084    contexts 23.478   concepts 13.412
parsed.units ............... 369       DIVIDED 44   sin numerator/denominator: 0
facts sin source_hash ......  0
derived.fact ............... 47.930    conflictos registrados 1.180
  sin source_fact_ids ......  0        fact_key duplicados .... 0
checkpoints ................ S00 1 · S01 1 · S02 1 · S03 1 · S04 4 · C3_CNV 3
checkpoints en corrida ≠ OK   0
```

### Market

```
instrumentos ............... 584       con venue_ticker 584
venue divergente ...........   6       (CRES, TGSU2, PAMP, IRSA, TECO2, YPFD — ADR/NYSE)
M23 `smoke-real-2026-08-28`  591 filas · 584 instrumentos
  SUCCESS ..................  577      todas con sha256
  FAILED ...................   14      (7 instrumentos × 2 intentos), 0 declarando datos
run_id duplicados ..........    0
RAW en disco ............... 598 history.csv + 598 meta.json = 1.196 artefactos
```

### CNV

```
empresas con datos ......... 3
presentaciones (GUID únicos) 9.165
filas versionadas .......... 21.528    <- UNIQUE(run_id, guid): RAW inmutable por corrida
artefactos ................. 3.511
```

### Lifecycle y seguridad

```
runs ....................... OK 61 · ABORTED 132 · BLOCKED 48 · RUNNING 0
triggers activos ........... 15        CHECKs 27        índices únicos 11
migraciones aplicadas ...... 29 engine (29/29 registradas) + 3 market
hashout determinista ....... 5/5 tablas
```

### Integridad — los siete ceros

```
CIK autoritativo duplicado ................ 0
entidad con dos CIK autoritativos ......... 0
identifiers huérfanos ..................... 0
contaminación de tipo ..................... 0
entidades muertas con identidad ........... 0
VERIFIED sin evidencia .................... 0
HUMAN_DECISION firmada por proceso ........ 0
```

---

## 3. HOMOLOGATED SCOPE

### Identity V1

Modelo de identidad (entidad ≠ identificador ≠ instrumento, `entity_key` opaco);
tipos de identificador con formato validado; estados de entidad y su lifecycle;
`assertion` como objeto de primera clase con FK `NOT NULL` desde `identifier`;
provenance completa (fuente, registro, cita, autor, evidencia estructurada);
autoridad como propiedad de la **fuente por tipo**; bridges sólo por
`HUMAN_DECISION` firmada por persona; y el **aislamiento de `catalaxia_engine`**,
que no puede introducir identidad inválida por ningún camino probado.

### SEC

S03 (parsing XBRL, unidades `DIVIDED` con `numerator`/`denominator`, provenance por
`source_hash`), S04 (normalización, conflictos explícitos, sin facts inventados),
checkpoints ligados a corridas OK, `hashout-v2` determinista e insensible al orden,
lifecycle protegido por `run_scope()`, y reproducibilidad verificada recalculando.

### Market

M23 sobre 584 instrumentos con RAW íntegro y verificado (60/60 hashes cotejados
contra disco en la auditoría), provenance completa, `venue_ticker` poblado 584/584,
F-014 mitigado, idempotencia por `run_id` único.

### CNV — alcance textual

> **Identity → CNV funciona correctamente para entidades que poseen CUIT demostrado
> y cuyos datos CNV fueron efectivamente fetcheados.**

Hoy son tres: YPF (4.919 GUIDs), TGSU2 (2.385), CEPU (1.861). **No se declara
cobertura total.**

### Backfill CIK

512 elegibles medidos contra la base · 505 entidades creadas · 7 reutilizadas ·
514 identificadores · **0 CUIT autoritativos producidos** · **0 bridges automáticos** ·
idempotente (hash de identidad idéntico entre corridas).

---

## 4. NOT HOMOLOGATED

Ninguno de estos es un bug. En varios casos, **bloquear es el comportamiento correcto**.

| | qué | por qué queda fuera |
|---|---|---|
| 1 | CNV universo completo | 3 de 512 elegibles. Limitación de cobertura, no de corrección |
| 2 | 56 emisores BYMA | sin CIK no hay ancla; su CUIT legacy es `CORROBORATING` y nunca llega a autoritativo |
| 3 | **GGAL** sin CUIT demostrable | tiene bridge propuesto, **no ratificado**. El sistema lo bloquea: correcto |
| 4 | **BMA** sin CUIT demostrable | GLEIF devuelve dos LEI para la razón social; elegir sería inferencia (F-024) |
| 5 | bridges CIK↔LEI no ratificados | 4 `CANDIDATE`. G5: ninguna fuente publica el puente |
| 6 | automatización de ratificaciones | por diseño: una decisión humana la firma una persona |
| 7 | **F-043** | deuda operativa; ver §5 |
| 8 | **F-041 / F-046** | deuda histórica documentada |
| 9 | cobertura no ejecutada | incluye el universo EDGAR completo, no auditado |
| 10 | fuentes sin evidencia suficiente | AFIP (captcha), `CNV_PORTAL` (no declara el CUIT del emisor) |

---

## 5. Findings

| finding | estado | clasificación |
|---|---|---|
| F-009, F-024, F-026, F-028, F-029, F-031, F-032, F-034, F-035, F-036, F-037, F-038, F-040, F-042, F-045 | **CLOSED** | 15 |
| F-041, F-044, F-046, F-047 | **CLOSED_WITH_NOTES** | 4 |
| F-014 | **MITIGADO** | deuda semántica |
| **F-043** | **OPEN** | **POST_V1 / OPERATIONAL** |
| F-027 | no reproducible | sin rastro en base ni contratos |

### F-043 — POST_V1 / OPERATIONAL

Los 7 instrumentos `EMPTY` se registran como `FAILED`. `EMPTY` existe en el CHECK del
esquema y el código **nunca lo emite**.

**Impacto:** reintentos innecesarios (7 requests por corrida, porque `ya_exitosos()`
filtra por `SUCCESS`) y clasificación operacional incorrecta.

**No es** corrupción · **no es** pérdida de datos · **no es** bypass · **no es**
contaminación de identidad. Verificado: 0 filas `FAILED` declarando datos, 0 precios
escritos, 0 RAW en disco para esos 7.

**No se corrige en este release.**

### F-041 / F-046 — HISTORICAL DEBT

1 assertion sin `source_facts` (YPF, `SEC_20F`, cuyo documento nunca se archivó) y
6 sin `left_ref` (las re-afirmaciones del ciclo 9).

**No se modifican assertions históricas sólo para adaptar la evidencia a reglas
posteriores.** Riesgo residual nulo: 0 incoherencias de tipo, y ningún rol puede
modificarlas (GRANT para la aplicación, `tg_assertion_inmutable` para el owner).
F-045 impide casos nuevos.

### F-044 — limitación administrativa

El owner puede `ALTER TABLE … DROP CONSTRAINT`. **Ninguna garantía en PostgreSQL
sobrevive a su propio owner.**

Esto **no es un bypass del rol operativo**: `catalaxia_engine` tiene sólo `SELECT`
sobre `identity_v1.source` y no puede tocar el DDL. La garantía estructural
(`ck_politica_estructural_cik_lei`) está demostrada por mutación: sin ella, con la
política adulterada, `LEGACY_DIM_ENTITY → CIK` entra; con ella, no.

---

## 6. Garantías verificadas

15 triggers activos, 27 CHECKs, 11 índices únicos. Seis garantías críticas
demostradas **por su ausencia**:

| garantía eliminada en la mutación | ataques que reaparecen |
|---|---|
| `tg_identifier_coherente_con_assertion` | A4, A6, A7, A8 |
| `ux_identifier_autoritativo_unico` | A15, A16 |
| `tg_assertion_inmutable` | A13, C3 |
| `ck_politica_estructural_cik_lei` | `LEGACY → CIK` |
| `ck_cuit_exige_evidencia_estructurada` | `LEGACY → CUIT` |
| `tg_identidad_exige_entidad_viva` | `MERGED` adquiere identidad |

Adversarial final: **20 ataques con el rol operativo + 6 con owner y política
adulterada → `BYPASS = 0`.**

---

## 7. Riesgos residuales

1. **Administrativo (F-044).** El owner puede quitar constraints. No alcanzable por el
   rol operativo.
2. **Acoplamiento en `ck_cuit_exige_evidencia_estructurada`.** Ese constraint hace dos
   trabajos: exige evidencia **y** enumera qué fuentes establecen CUIT. Modificarlo
   pensando sólo en la evidencia tocaría también la política.
3. **Operativo (F-043).** 7 requests inútiles por corrida de Market.
4. **Deuda histórica (F-041, F-046).** 7 assertions que cumplen el contrato de su
   momento, no los posteriores.

---

## 8. Procedimiento de rollback

El release **no introduce cambios de datos ni de schema**: es un congelamiento. No hay
nada que revertir de este ciclo.

Para revertir el estado homologado al anterior:

1. **Garantías**: `ALTER TABLE identity_v1.assertion DROP CONSTRAINT
   ck_politica_estructural_cik_lei` (F-044) y `DROP TRIGGER
   tg_identifier_coherente_con_assertion ON identity_v1.identifier` (F-045).
   **Reabre los caminos que esas migraciones cerraron** — verificado por mutación.
2. **Datos**: no revertir. `identity_v1` prohíbe el `DELETE` de provenance
   (`tg_no_borrar_*`) y las assertions son inmutables. Revertir datos significa
   **retirar** (`valid_to`) y **encadenar** (`superseded_by`), nunca borrar.
3. **Verificación post-rollback**: `python scripts/engine/release_baseline.py` y
   comparar contra `CATALAXIA_V1_BASELINE.json`.

---

## 9. Artefactos de auditoría y evidencia

| documento | qué contiene |
|---|---|
| `docs/review/HOMOLOGATION_FINAL_REPORT.md` | dictamen y alcance |
| `docs/review/HOMOLOGATION_FINAL_GATE.md` | las 17 preguntas con su garantía |
| `docs/review/HOMOLOGATION_FINDINGS.md` | los 22 findings verificados uno por uno |
| `docs/review/F044_AUDIT.md` · `F044_GATE.md` | política estructural |
| `docs/review/F045_GATE.md` · `F046_FINDING.md` | coherencia assertion↔identifier |
| `docs/review/PRE_HOMOLOGATION_*.md` | clasificación de findings residuales |
| `docs/architecture/*_CONTRACT.md` / `*_CONTRATO.md` | 11 contratos, escritos antes de implementar |
| `outputs/docs/homologacion/*.json` | 7 archivos de evidencia reproducible |

Reproducibles: `homologacion_final.py` · `audit_f044.py` · `f044_bench.py` ·
`f045_bench.py` · `audit_backfill_cik.py` · `audit_cross_cnv.py` · `release_baseline.py`

---

## 10. Criterios de aceptación

| criterio | resultado |
|---|---|
| Dictamen de homologación emitido | `HOMOLOGATED_WITH_NOTES` |
| Estado actual == estado homologado | **sí**, verificado campo por campo |
| Blockers técnicos | **0** |
| Camino de corrupción por `catalaxia_engine` | **ninguno** (20 ataques, 0 bypass) |
| Garantías críticas demostradas por mutación | **6/6** |
| Integridad | **7 controles en 0** |
| `RUNNING` | **0** |
| Migraciones pendientes | **0** (29/29 registradas) |
| Cambios de datos, schema o RAW en este ciclo | **0** |
| Exclusiones explícitas | **10, enumeradas** |
| Roadmap post-V1 | `docs/release/POST_V1_BACKLOG.md` |

**El release NO se acepta todavia**: los criterios tecnicos se cumplen, pero
falta el criterio de distribucion. Ver `RELEASE_FREEZE_AUDIT.md`.
