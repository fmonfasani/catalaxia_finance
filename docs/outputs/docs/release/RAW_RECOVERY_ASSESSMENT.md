*# RAW RECOVERY ASSESSMENT — incidente de `data/raw`

**Fecha:** 2026-08-31 · **Rol:** Incident Recovery / Release Auditor
**Alcance:** sólo diagnóstico. No se descargó nada, no se ejecutó S02/S03/S04, backfill,
M23 ni CNV. No se borró, movió ni sobrescribió ningún archivo. Sin commits.

---

# RECOMENDACIÓN: **NO_RESTORE_AVAILABLE**

No existe ninguna copia local de los artefactos de `data/raw`. La pérdida es total y
**los datos sólo pueden re-adquirirse desde las fuentes originales**.

La base PostgreSQL homologada está **intacta** (14/14 controles, DELTA = 0), y F-050 y
F-051 siguen implementados y verdes (30/30).

---

## 1. Alcance del incidente

Durante la limpieza del E2E previo se ejecutó `git worktree remove --force` sobre un
worktree en el que yo había creado un **junction de Windows**
(`e2e/data/raw` → `<repo>/data/raw`). El borrado siguió el enlace y eliminó el
contenido original.

**La causa fue mía y evitable**: enlacé en vez de copiar, y usé `--force` sin
desmontar el junction primero.

## 2. Inventario de pérdida

| directorio | antes | ahora |
|---|---:|---:|
| `data/raw/submissions/` | 8.021 | **0** |
| `data/raw/market/` | 1.196 (598 `history.csv` + 598 `meta.json`) | **0** |
| `data/raw/catalogo_edgar/` | 2 | **0** |
| `data/raw/engine/CIK*/filings/` | 27 directorios | **0** |
| `data/raw/engine/cnv/` | ~3.500 | **2** |
| `data/raw/companyfacts/`, `edgar_pilot_ypf/` | varios | **0** |
| **total en `data/raw`** | **10.000+** | **2** |

Sobrevivieron exactamente dos archivos:

```
data/raw/engine/cnv/CUIT33650305499/empresa/3ac9cc69bbb092f0.html
data/raw/engine/cnv/_index/sha256_index.jsonl          (1 línea)
```

**El resto de `data/` no fue afectado**: `screener.db`, `catalogo/`, `audits/`,
`backups/`, `logs/`, `dolar/`, `redescarga/` están completos. Sólo se perdió lo que
estaba bajo el junction.

## 3. Inventario de copias recuperables — búsqueda exhaustiva

| ubicación | resultado |
|---|---|
| `.claude/worktrees/agent-a25cfd4e58077a90d/data/raw/` | **0 archivos** |
| `D:/…/catalaxia-ctxB/data/raw/` | **0 archivos** |
| `D:/…/catalaxia-ctxC/data/raw/` | **0 archivos** |
| `C:/temp/catalaxia-backups/` | 3 archivos: dumps SQL del **2026-08-21**, sin artefactos |
| `d:/opt/catalaxia/` | sólo `dashboard.html` |
| Papelera de reciclaje | 145 elementos, **ninguno coincide** (`worktree remove` borra directo) |
| Comprimidos en `Porfolio/` | 3 `.tar.gz`/`.zip`, todos de otros proyectos |
| `find … -name "CIK*.json"` fuera de `data/raw` | **0** |
| `find … -name "history.csv"` en todo el proyecto | **0** |
| `find … -path "*market*" -name "meta.json"` | **0** |

### Lo único parcialmente relacionado

| archivo | qué es | ¿sirve? |
|---|---|---|
| `data/catalogo/company_tickers.json` | catálogo SEC del **2026-06-25**, 871 KB | **No**: el usado fue `company_tickers_2026-08-23.json` (796 KB). Otra fecha, otro contenido |
| `scratchpad/c3c/`, `c3d/` | 7 `.htm` de 20-F (CEPU, GGAL, TGSU2) | **No**: descargas ad-hoc de ciclos previos, fuera de `data/raw`, sin `meta.json` ni estructura |
| `outputs/` (130 archivos) | reportes JSON/MD | **No son artefactos**, pero sí evidencia de integridad (§4) |

**Ninguna de estas copias reconstruye `data/raw`.**

## 4. Hashes y controles de integridad que SÍ sobrevivieron

La evidencia de integridad está en PostgreSQL, y **está completa**:

```
market_raw_runs con sha256 .................... 577   (todos los SUCCESS de M23)
parsed.facts con source_hash .................. 67.084
fetch_raw.cnv_artifact con sha256 ............. 3.514
identity assertions con source_facts.sha256 ...      6   (re-afirmaciones de F-041)
fetch_raw.download_log ........................    553
parsed.pre_xbrl_filings con index_path ........     18
```

**Esto es importante y hay que enunciarlo con precisión:** los hashes permiten
**verificar** una futura re-descarga —comprobar que el artefacto re-adquirido es
byte-idéntico al que produjo el estado homologado—, pero **no reconstruyen nada**. Un
hash prueba identidad; no contiene el contenido.

> Una base de datos **no sustituye** al artefacto primario. `parsed.facts` conserva el
> dato extraído; el XBRL del que salió ya no está. La provenance quedó **verificable
> pero no re-derivable**.

## 5. Qué evidencia del E2E puede recuperarse sin nuevo fetch

| control del E2E | ¿recuperable? |
|---|---|
| Instalación limpia (29+3 migraciones) | **Sí** — no depende de RAW |
| Comparación estructural de schema | **Sí** |
| Banco de migraciones (14 escenarios) | **Sí** |
| F-050 lifecycle (19 tests + mutación) | **Sí** — verificado, 19/19 |
| F-051 instalación Market (11 tests + mutación) | **Sí** — verificado, 11/11 |
| Bancos adversarios de Identity (F-044 19/19, F-045 14/14) | **Sí** |
| Backfill CIK + idempotencia | **Sí** — usa `screener.db` y el catálogo, **pero el catálogo EDGAR se perdió** → ver §6 |
| Cross-workstream (10 controles) | **Sí** — es sobre PostgreSQL |
| CNV eligibility | **Sí** — es sobre PostgreSQL |
| Determinismo de `hash_out` | **Sí** — recalcula sobre tablas |

## 6. Qué quedó irrecuperable sin re-adquisición

| | por qué |
|---|---|
| **S02 fetch** | no hay artefactos de origen |
| **S03 parse** (27 filings) | requiere `data/raw/engine/CIK*/filings/` y `submissions/` |
| **S04** | depende del checkpoint de S03 |
| **Backfill CIK** | `backfill_cik.py` exige `data/raw/catalogo_edgar/company_tickers*.json`; sin él aborta con `BLOCK: no hay catalogo de SEC` |
| **Verificación de hashes contra disco** | F-038 (577 artefactos de Market) y F-041 (6 `submissions`) |
| **CNV re-fetch / verificación RAW** | 3.514 artefactos |

**4 tests fallan hoy por esta causa**, no por regresión de código:
`test_f038_traza_corrida::test_el_hash_de_la_base_es_el_del_artefacto_en_disco` y
tres de `test_f041_reafirmacion`. La suite da **223 passed / 4 failed**.

## 7. Estado de PostgreSQL — **INTACTO**

14/14 controles contra el baseline previo al incidente, **DELTA = 0**:

```
entities 525 · assertions 614 · identifiers vigentes 574
CIK 513 · CUIT 3 · bridges VERIFIED 3
parsed.facts 67.084 · derived.fact 47.930
market instrumentos 584 · M23 591 filas · CNV 9.165 GUIDs
reviews OPEN 11 · conflicts 1 · RUNNING 0
```

El único cambio respecto del baseline es el registro de las 3 migraciones de Market
(32 en vez de 29), consecuencia de F-051. Son idempotentes y se verificó que no
alteraron datos: 584 instrumentos, los mismos 6 `venue_ticker` divergentes, 591 filas
de M23.

## 8. Estado de F-050 — **IMPLEMENTADO, NO CERRADO**

```
s00_smoke        run_scope=1  start_run=0  finish_run=0  corridas_huerfanas=1
s01_identity     run_scope=1  start_run=0  finish_run=0  corridas_huerfanas=1
s02_fetch_ypf    run_scope=1  start_run=0  finish_run=0  corridas_huerfanas=1
s03_parse_ypf    run_scope=1  start_run=0  finish_run=0  (F-031)
s04_normalize    run_scope=1  start_run=0  finish_run=0
c3_cnv_fetch     run_scope=1  start_run=0  finish_run=0  (F-040)
```

**Las seis etapas usan el mismo mecanismo.** Banco `test_f050_lifecycle_s00_s02.py`:
**19/19**, contra el `main()` real, con inyección en 5 puntos más `SystemExit` y
`KeyboardInterrupt`. **Mutación demostrada**: revertir S01 al patrón viejo hace fallar
4 tests y reaparecer las huérfanas.

**No se declara CLOSED**: falta la auditoría independiente, que exige ejercitar las
etapas sobre una instalación limpia — y S02 necesita RAW.

## 9. Estado de F-051 — **IMPLEMENTADO, NO CERRADO**

El runner de `engine/db.py` aplica ahora `migrations/engine` **y** `migrations/market`,
con registro prefijado por directorio y lectura de ambos formatos para no re-aplicar
las 29 de bases existentes. Guarda de dependencia: las de Market se saltean si sus
tablas no existen.

Verificado sobre base limpia: `ck_estado_coherente_con_artefacto` **= 1**,
`venue_ticker` **= 1**, rol `catalaxia_market_ro` **= 1**, 32 migraciones, **0
duplicados**. Banco `test_f051_market_installation.py`: **11/11**, con mutación (sin
`025` el CHECK no existe; restaurada, vuelve).

**No se declara CLOSED**: falta la auditoría independiente sobre el E2E completo.

## 10. Recomendación

# **NO_RESTORE_AVAILABLE**

No hay copia local, parcial ni completa. La búsqueda cubrió los tres worktrees, los
backups, la papelera, los comprimidos y todo el árbol del proyecto por nombre de
artefacto. El resultado fue cero en todos.

## 11. Próxima acción mínima para poder emitir `E2E_RELEASE_GATE`

Sólo hace falta re-adquirir **lo que el E2E necesita**, no todo `data/raw`. En orden de
costo creciente:

| # | qué | cómo | por qué es necesario |
|---|---|---|---|
| 1 | `data/raw/catalogo_edgar/company_tickers*.json` | 1 request a SEC | desbloquea **backfill CIK** y **S01** |
| 2 | `data/raw/submissions/CIK*.json` | S02, con rate limit | desbloquea **S03**, **F-041** y la verificación de las 6 re-afirmaciones |
| 3 | `data/raw/engine/CIK0000904851/filings/` | S02 | desbloquea **S03 (27 filings) y S04** |
| 4 | `data/raw/market/` | M23 | sólo para re-verificar los 577 hashes de F-038 |
| 5 | `data/raw/engine/cnv/` | C3 | sólo para re-verificar los 3.514 hashes de CNV |

**Los pasos 1–3 son el mínimo** para un E2E equivalente al anterior. Los pasos 4 y 5
son verificación de integridad de datos ya persistidos: se pueden diferir, y su ausencia
es una **limitación de evidencia**, no un defecto del sistema.

**Ventaja que queda del incidente:** los 577 + 3.514 + 6 hashes están en PostgreSQL, así
que cualquier re-adquisición puede **verificarse contra ellos**. Si los artefactos
re-descargados no coinciden byte a byte, se sabrá — y eso es exactamente lo que la
provenance existe para permitir.

### Medida preventiva propuesta (no aplicada)

Nunca enlazar `data/raw` en un worktree. Copiar lo necesario, o exponerlo por variable
de entorno de sólo lectura. Y no usar `git worktree remove --force` sobre un árbol que
contenga enlaces: desmontarlos primero.
