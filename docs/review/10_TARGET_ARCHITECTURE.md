# 10 — Target Architecture (define, no implementa)

**FASE 2 — REINGENIERÍA, PASO 10.** Cómo queda BYMAStocks cuando 01–09 estén implementados y verificados. Derivado exclusivamente de 01–09; lo no existente se marca OBJETIVO FUTURO (PLANIFICADO/CONDICIONAL), nunca como existente. Estados: EXISTENTE · EN MIGRACIÓN · PLANIFICADO · CONDICIONAL · PENDIENTE_EVIDENCIA · NO_MERGE · LEGACY · ARCHIVE_FUTURO. Evidencia por afirmación: `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`.

## Objetivo

Responder qué estructura tiene el sistema tras R7.1–R7.12 verificados. 12 capas exactas, 4 planos, ciclo DEFINIR→IMPLEMENTAR→VERIFICAR→CERTIFICAR (este documento = DEFINIR).

## HOY vs OBJETIVO

- HOY (04 §19): cron screener → `screener.db` → CSV + PG (3 publicadores); motor SEC-YPF certificado sin llegada a usuario; market autónomo; dualidades v0/v1, facts/derived, precios×2, 4 motores; validación por dominio sin C11 unificada en publicación `[EJECUCIÓN/CÓDIGO]`.
- OBJETIVO: una cadena por dominio con ownership único, provenance transversal, C10 por etapa, C11 como condición necesaria de C12 vía gate único en publisher staging+swap; dualidades con bridge o separadas por dominio; core rebuild con modos; FX servicio C7; YPF Golden Case (no techo).

## Diagrama objetivo (§5)

```
FUENTES C1 (EDGAR · CNV · Yahoo · INDEC · 20-F · demo-seed)
  ↓ (fetch versionado, hash)
IDENTIDAD C2 (v1 objetivo + bridge v0↔v1; empresas owner=base) ──→ CONTROL: assertions versionadas
  ↓
RAW C3 (inmutable: SEC fs · CNV RawStore · market_raw_* · ingesta) ──→ CONTROL: manifests, checkpoints
  ↓
PARSED C4 (parsed.* · cnv_estados* · market canonical) ──→ CONTROL: parser_version, hash salida
  ↓
NORMALIZED C5 (claves canónicas, unidades, períodos, entity_key) ──→ CONTROL: hashout, conflictos
  ↓
ECONOMIC FACTS C6 (facts ⟷ derived.fact con puente; canónicos por dominio)
  ↓
FINANCIAL MODEL C7 (core rebuild con modos · FX-service OFFICIAL/MEP/CCL · s4/screener)
  ↓
RATIOS C8 (4 motores por dominio hasta equivalencia; materializadores)
  ↓
VALIDACIÓN C10 (gates, suites, golden cases) ──┐
  ↓                                              │ controles (C10≠C11)
CERTIFICACIÓN C11 (c11 exclusivo; 40 como atestación de dominio referenciada)
  ↓                                              │
PUBLICACIÓN C12 (publisher staging→swap con GATE único) ◄─┘ C12 exige C10 PASS + C11
  ↓
PRODUCTO (PG prod + CSV + api)
PROVENANCE C9 ═══ transversal (run_id · checkpoints · hashes · manifests · ingesta · source_fact_ids)
```

Sin capa 13. PROVENANCE y CONTROL transversales donde corresponde.

## C1 — Fuentes

SEC/EDGAR (companyfacts, submissions, 20-F) · CNV portal · Yahoo/yfinance · INDEC (IPC) · demo-seed (origen de silver, dominio acotado). Fuente ≠ pipeline ≠ storage: el fetch vive en C1/C3 (s02, c3, m2, fetch_dolarito, jobs-download) y persiste en RAW C3; ningún scraping en capas posteriores (verificado: todos los fetchers residen en ingesta) `[CÓDIGO]`. Estado: EXISTENTE.

## C2 — Identidad (D1/M1)

Objetivo: **V1 como arquitectura** (entity/identifier/source + assertions/reviews/conflicts + instruments/symbols) + **bridge v0↔v1** (equivalencias solo-lectura) + migración progresiva de lectores; sin doble escritura; sin dos autoridades permanentes (autoridad transitoria dual → autoridad objetivo: resolución V1+bridge).
Transitorio: v0 (s01/s03) permanece hasta migración verificada. IDENTIDAD≠CLASIFICACIÓN en ambos sistemas (classifications separadas) `[CÓDIGO]`. Entidades: entity · identifiers · assertions · conflicts · reviews · instruments · bridge. Estado: EN MIGRACIÓN (diseño bridge PLANIFICADO/CONDICIONAL R7.4).

## C3 — RAW (inmutable)

RawStore por fuente/CUIT-CIK + hashes canónicos (sha256/canonical_sha256) + manifest por artefacto + provenance (download_log/artifact/presentation, ingesta_log, market_raw_runs) + restore (`_raw_inmutable.restaurar`) + idempotencia (hash-reuse, checkpoints `007`, DONE-file con re-proceso) + **ausencia de DELETE destructivo** (solo descarte documentado de ruido confirmado). R3: RAW nunca se elimina por limpieza (principio adoptado; 07A sin objeción). Estado: EXISTENTE (mecanismos) + CONDICIONAL (uniformar DONE-file con hash, R7.4/R7.6).

## C4 — Parsed (RAW≠PARSED≠NORMALIZED)

Parsers: XBRL (`engine.xbrlparse` vía s03), CNV-extract (jobs v2), market-canonical (m2), catalogación (build_fiscal_calendar). Storage: `parsed.*`, `cnv_estados*`, `market_*` crudos→canónicos. parser_version registrada (contrato C10: s04-fix, c3-manifest) + hash de salida + checkpoint por corrida + `parse_errors` (degradación parcial auditada). Sin normalización dentro del parser (unidad/entidad se resuelven en C5: s04 `unidad_resuelta`/entity_key) `[CÓDIGO]`. Estado: EXISTENTE.

## C5 — Normalized

Claves canónicas (fact_key, entity_key, CIK/CUIT), unidades (`unidad_resuelta`, `unit_kind/measure`), períodos (`period_kind`, fechas, `fiscal_calendar`), dimensiones XBRL. Provenance hacia PARSED (`input_checkpoint_id`, `source_fact_ids`). Integración S04→Identity V1 como contrato (gate C-S04-004: sin resolución autoritativa no hay hecho) `[CÓDIGO]`. Parsear≠normalizar preservado. Estado: EXISTENTE (motor) + CONDICIONAL (puente facts, R7.5).

## C6 — Economic Facts (D2/M2)

`facts` (SQLite, canónico producto) ⟷ `derived.fact` (PG, canónico certificado) con puente de trazabilidad (no fusión: NO_MERGE datos). `fact_financials` CNV-legacy → ARCHIVE_FUTURO (condicionado a f4, A4). Stores separados por dominio con contrato de granularidad declarado. Estado: EXISTENTE + puente CONDICIONAL (R7.5).

## C7 — Financial Model (+ FX futuro, D10/R7.11)

Reconstrucción y cálculo financiero: core rebuild con modos (M3), s4/screener, valuación (precios_y_valuacion), TTM. FX pertenece a C7 como servicio con fx_type {OFFICIAL, MEP, CCL} y columnas value_original/currency_original/value_converted/currency_converted/fx_rate/fx_date/fx_source/fx_method (ARS/USD). MVP objetivo con los tres tipos. NO implementado en este paso (diseño). Estado: modelo EXISTENTE; FX PLANIFICADO (R7.11).

## C8 — Ratios (M5 PENDING_EVIDENCE)

Cuatro motores NO fusionados: cada uno con fuente/ventana/moneda/unidad/fórmula/redondeo declarados; catálogo canónico de definiciones (ratio_defs como referencia, no como fusión). Equivalencia numérica por CIK+período+ratio+unidad+moneda con tolerancia solo justificada (hoy TBD → igualdad exacta canonizada). M5 no convierte el diseño en merge. Estado: EXISTENTE + PENDIENTE_EVIDENCIA (R7.8).

## C9 — Provenance (transversal)

Todo derivado responde: fuente, RAW originario, parser+versión, normalizador, run, input checkpoint, transformación, entidad, evidencia. Mecanismos únicos por función (sin duplicar por pipeline): run_id/stage_runs/checkpoints (motor), hashes (archivos/filas/ratios), manifests (CNV/FASE4), ingesta_log (SQLite). DONE-file converge a hash-manifest (objetivo). Estado: EXISTENTE (motor completa) + CONDICIONAL (uniformidad, R7.4–R7.6).

## C10 — Validación (autoridad de validación, no certifica)

Verifica schema, integridad, invariantes, gates, consistencia, outputs, provenance, golden cases. Autoridad: framework de gates contractuales (`assert_transition`, contratos por stage) + suites registradas por dominio (job7, m4/m5, suites pipeline, o2_*, 30_validaciones). VALIDACIÓN≠CERTIFICACIÓN. Estado: EXISTENTE (distribuida) + CONDICIONAL (registro único de suites, R7.10).

## C11 — Certificación (autoridad exclusiva)

Autoridad exclusiva: `c11_certificar.py` + `engine.certifications` (inmutable por run, INV1/INV5). Consume evidencia C10: regla C10 PASS → puede CERTIFICAR; sin PASS no hay CERTIFIED. Incluye `cert_hash`, stage evidence, acto inmutable. `40_certificar.py`, `validar_suite.py`, `f6_sec`: NO son autoridades C11 (quedan como atestación de dominio/referencia legacy según 08/09; 40 referenciada por período, sin fusionar). Estado: EXISTENTE (motor) + CONDICIONAL (referencia cruzada 40↔c11, R7.10).

## C12 — Publicación (D8/D9 obligatorios)

Publisher objetivo: BUILD STAGING → CHECK SCHEMA → LOAD → VALIDATE → C10 PASS → C11 CERTIFIED → ATOMIC SWAP → PUBLICACIÓN; con staging, snapshot, rollback R2, tabla-nunca-vacía, gate único, bloqueo sin certificación. D8=mecanismo, D9=regla. Estado: PLANIFICADO/CONDICIONAL (R7.1+R7.10); hoy EN MIGRACIÓN (s5/sync/migrate/publicar_v2/api vigentes).

## Pipeline objetivo SEC (§18)

FUENTE SEC→RAW→PARSED→NORMALIZED→FACTS→MODEL→RATIOS→C10→C11→C12 con el motor genérico (s04/ratio/c11 por CIK/run) + Golden Cases como casos (YPF entre otros). YPF no es el pipeline: s01–s03 golden permanecen como caso YPF; la arquitectura no se hardcodea a YPF (prohibición expresa).

## Core + modos (§19, M3)

Core común incremental-subset/full-universe/phases-import; s9 opcional; CNV subprocess/pre-extraído; EDGAR incremental/full; IPC mensual prerrequisito. UPDATE/ALL/SCREENER como fachadas hasta equivalencia funcional. Sin pérdida de capacidades. Estado: PLANIFICADO/CONDICIONAL (R7.9).

## Market (§20, D6/M6)

`market_instruments` (canónico PG, owner m1), `market_symbol_mappings` (mapeo), `market_price_daily` (serie motor) separados de `precios`/`precios_diarios` (producto SQLite): cadenas/consumidores/granularidades distintas (NO_MERGE). Definiciones: issuer (emisor, C2/empresas-identity) ≠ instrument (`market_instruments`/`dim_instrument`→migrado) ≠ price (serie por instrumento/fecha/fuente). Estado: EXISTENTE + CONDICIONAL (migración dim, R7.7).

## Publication legacy (§21)

HOY: s5→CSV (vigente) · sync 7 tablas (vigente, tras gate en objetivo) · migrate full-copy (vigente hasta REPLACE) · publicar_v2→screener_v2 (sin lector; criterio A7) · api (vigente). OBJETIVO: publisher+gate; s5 con gate; api con hist resuelto. Retiros solo vía MERGE→TEST→VERIFICAR→VENTANA→ARCHIVE→DELETE futuro. Nada declarado eliminado.

## CNV (§22, D4)

v2 = camino objetivo (jobs 1–8 + c3-RAW + assemble). v1: DEPRECATE(R7.6)→ventana→ARCHIVE(R7.12)→eventual DELETE (08-B bloqueado hasta entonces). Gates 08/09 vigentes.

## Empresas (§23, D5)

`construir_base` = owner (C2-registro). Catálogo solo tras evidencia runtime+lectores (08-C). Sin-caller ≠ sin-impacto (tickers/descargas_log huérfanos si cae sin cobertura).

## Ratios / IPC (§24)

IPC transversal (no capa): serie mensual INDEC fijada (A10) como prerrequisito de s2/TTM/CAGR y de la equivalencia M5. Sin capa nueva.

## Golden cases (§25, matriz no-definitiva)

Dimensiones: industria, jurisdicción, filing (20-F/F-6/EEFF-CN V…), moneda, estructura societaria, fuente, rasgos contables. YPF = un caso (SEC 20-F, ADR+BYMA, ARS/USD). Sin hardcodear arquitectura; equivalencias futuras multi-emisor.

## Matriz de componentes (§26, solo relevantes)

| Componente | Capa primaria | Plano | HOY | OBJETIVO | Estado | Readers | Writers | Provenance | C10 | C11 | C12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EDGAR/CNV/Yahoo/INDEC | C1 | DATOS | vigentes | mismos | EXISTENTE | fetchers | — | n/a | n/a | n/a | n/a |
| s01/s03 (golden) | C2/C4 | DATOS | YPF-only | Golden Case YPF | EXISTENTE→KEEP | s04-motor | s01 | completa | gates | vía c11 | no |
| s04/ratio_engine/c11 | C5/C8/C11 | DATOS+CTRL | genéricos sin llegada a usuario | reutilizables por CIK + llegada vía publisher | EN MIGRACIÓN | publisher/test | propios | completa | gates | c11 | vía gate |
| identity v1+bridge | C2 | DATOS | v1 sin bridge | resolución unificada | CONDICIONAL | s04/ratio/c3 | convención | assertions | suite | n/a | n/a |
| c3/RawStore | C3 | DATOS+EJEC | vigente | mismo + DONE→hash | EXISTENTE | auditoría | c3 | completa | checkpoint | n/a | n/a |
| construir_base/facts | C6 | DATOS | owner empresas+facts | mismo + puente | EXISTENTE | ratios/s4 | base | parcial | gates | n/a | no |
| core rebuild (futuro) | C7 | EJEC+CTRL | 3 caminos | core+modos+fachadas | PLANIFICADO | s5/sync | core | parcial→comp. | suite/modo | n/a | vía publ. |
| s5_exportar | C12 | DATOS | vigente | mismo + gate | EN MIGRACIÓN | disco/usuario | s5 | artefacto | checks | exigida | export |
| publisher (futuro) | C12 | D+E+C | no existe | staging+swap+gate | PLANIFICADO | PG,api | publisher | boletín | suite | exigida | el objeto |
| sync/migrate/pub_v2 | C12 | DATOS | vigentes | transporte gateado / reemplazado / criterio A7 | EN MIGRACIÓN | PG | propios | ausente | parcial | no | parcial |
| api | C12 | DATOS | sirve 3 tablas (1 sin writer) | mismo + hist resuelto | EN MIGRACIÓN | usuarios | — | n/a | n/a | consume | sirve |
| market m1/m2/m4 | C3/C10 | DATOS | vigentes | mismos + dim migrado | EXISTENTE | ratio/e2e_p | propios | parcial | m4 | n/a | no |
| materia_prima 20/30/40 | C5/C10/C11-dom | DATOS | vigente | mismo + referencia c11 | EXISTENTE | sync | propios | cadena | 30_valid | 40 (dominio) | vía sync |
| FX-service (futuro) | C7 | DATOS | disperso | servicio OFFICIAL/MEP/CCL | PLANIFICADO | C8 | servicio | completa | suite | n/a | no |

## Matriz de transición (§27)

| Actual | Objetivo | Tipo | Dependencia | Evidencia requerida | Riesgo | Rollback | Estado |
|---|---|---|---|---|---|---|---|
| 3 rebuilds | core+modos | MERGE | R7.3/R7.6/IPC | matriz de modos | R2 | R1 | CONDICIONAL |
| v0+v1 | v1+bridge | BRIDGE | R7.4 | tests cruce | R2 | R3 | CONDICIONAL |
| facts/derived | puente trazabilidad | BRIDGE | R7.5 | muestreo | R1 | R1 | CONDICIONAL |
| sync/migrate | publisher+gate | MERGE/REPLACE | R7.1/R7.10/hist | suite+bloqueo | R3 | R2 | CONDICIONAL |
| dim_instrument | market_instruments | MERGE(datos, migrar) | R7.7 | mapeo completo | R2 | R2 | CONDICIONAL |
| jobs v1 | archive | DEPRECATE/ARCHIVE | R7.6/ventana | no-uso+SHA | R1 | R1 | CONDICIONAL |
| f-series | archive tras core | ARCHIVE | R7.7/R7.9 | gaps+ventana | R2–R3 | R2 | CONDICIONAL |
| 4 motores | equivalencia o keep | PENDIENTE_EVIDENCIA | R7.8 | prueba numérica | — | — | PENDING_EVIDENCE |
| precios dual | separados | NO_MERGE | — | — | — | — | NO_MERGE |
| s04-dict | StageReport | ADAPT | test C10 | contrato | R1 | R1 | CONDICIONAL |

## Matriz de autoridad (§28, un owner por responsabilidad)

IDENTIDAD: resolución V1+bridge (transitorio dual) · RAW: fetcher por fuente + framework inmutable · PARSED: s03/jobs/m2 por dominio · NORMALIZED: s04/s0/materia_prima por tabla · FACTS: base (SQLite) + s04 (PG) por dominio + puente · FINANCIAL MODEL: core rebuild · RATIOS: motor por dominio (hasta equivalencia) · PROVENANCE: framework transversal (run/checkpoint/hash/manifest) · VALIDACIÓN: framework C10 (gates + suites registradas) · CERTIFICACIÓN: c11/`engine.certifications` (exclusiva) · PUBLICACIÓN: publisher canónico (hoy fragmentada → EN MIGRACIÓN).

## Matriz de datos (§29)

| Dato | Store canónico | Writer | Readers | Provenance | Capa |
|---|---|---|---|---|---|
| entities/identifiers | identity_v1 (+v0 transitorio) | convención/s01 | s03/s04/ratio/c3 | assertions/parcial | C2 |
| facts | SQLite `facts` | construir_base | calcular_ratios/s4 | parcial | C6 |
| derived.fact | PG `derived.fact` | s04 | ratio_engine/c11 | completa | C6 |
| market_instruments | PG | m1 | m2 | parcial | C3 |
| market_price_daily | PG | m2 | m4/ratio/e2e_p | parcial | C6 |
| precios | SQLite | precios_y_val/s3 | s4 | parcial | C8 |
| ratios | por motor (4) | 4 motores | s4/ND | mixta | C8 |
| certifications | PG `engine.certifications` | c11 | boletín/publisher-gate | completa | C11 |
| publication stores | PG prod + CSV | publisher/s5 | api/usuarios | boletín/artefacto | C12 |

## Matriz de gates (§30, sin gates inventados)

FUENTE→(fetch ok+hash) RAW →(manifest+checkpoint) PARSED→(volumen/schema+versión) NORMALIZED→(entidad+unidad resueltas) FACTS→(checkpoint-reuse) MODEL→(gates assemble) RATIOS→(rangos/columnas) C10→(suites+goldens) C11→(certificado vigente) C12→(swap verificado, tabla-no-vacía). Cada gate con responsabilidad existente o planificada con dueño (§28).

## Relaciones delete/merge (§31–§32)

Todo DELETE posterior al target y a su gate (08-secuencia; bloqueados permanecen). M1→bridge · M2→puente/sin-data-merge · M3→core+modos · M4→publisher · M5→pending · M6→no-merge · M7→contrato común. Ningún MERGE_CONDITIONAL convertido en DONE.

## Infraestructura (§33) y seguridad (§34)

DB: PG engine/market/prod + SQLite screener + staging futuro (mismo motor PG, esquema espejo) + dev/test (ya usados por suites) + cron VPS vigente (scheduler; sin inventar orquestador nuevo). Secrets: env/.env, cero hardcodeados (06); producción separada (SSH+docker, acceso registrado); sin writes destructivos sin gate; RAW inmutable; rollback por cambio (R0–R4); audit trail (logs/manifests/stage_runs); certification immutable (INV1/INV5). Sin tocar producción en este paso.

## Resultado (§37)

### ARQUITECTURA OBJETIVO
Sistema por dominios (SEC/CNV/Market) con identidad V1+bridge, RAW inmutable con provenance, parsed→normalized→facts con canónicos por dominio y puente, modelo con core+modos y FX-servicio, ratios por dominio hasta equivalencia, C10 distribuido con registro único, C11 exclusiva en c11 con gate obligatorio, C12 vía publisher staging+swap, provenance transversal y API/CSV como superficies.

### TRANSICIONES NECESARIAS (por dependencia)
R7.1 publisher → R7.2 gaps → R7.3 empresas → R7.4 bridge → R7.5 facts-puente → R7.6 deprecate v1 → R7.7 market → R7.8 ratios-prueba → R7.9 core → R7.10 gate → R7.11 FX → R7.12 cleanup (07 §7 intacto).

### BLOQUEOS
M5 sin evidencia numérica · hist sin writer · dim sin migrar · IPC sin fijar · suites sin rol bloqueante probado · fases R7 pendientes (todo lo anterior calendarizado, no invalidante del target).

### EVIDENCIA FALTANTE
10 gaps de 07 §10 (vigentes como precondiciones).

### COMPONENTES QUE PERMANECEN (incl. NO_MERGE)
Stages s00–s04, e2e, c3, c11, jobs v2, market, s-series/s5, api, sync-transporte, materia_prima, M6-precios duales, M2-stores duales, FX actual disperso hasta R7.11.

### COMPONENTES LEGACY (temporal + condición)
f-series (hasta R7.7/R7.9) · jobs v1 (hasta R7.6/R7.12) · construir_catalogo (hasta evidencia) · migrate (hasta publisher) · publicar_v2 (hasta A7) · fact_ratios/screener_gold (hasta gaps) · engine/s03.py (hasta ventana R7.12).

TARGET_ARCHITECTURE_STATUS = READY_FOR_IMPLEMENTATION

(La definición está completa y es implementable por fases con gates; los bloqueos listados condicionan la ejecución, no la validez del target. Ninguna implementación en este paso.)