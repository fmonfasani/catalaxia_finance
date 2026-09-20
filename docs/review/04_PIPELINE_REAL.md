# 04 — Pipeline REAL

**Relevamiento global — Paso 4.** Reconstrucción del pipeline real cruzando `01_EXECUTION_GRAPH.md` + `02_DEPENDENCY_GRAPH.md` + `03_DATA_OWNERSHIP.md` con inspección directa de código. Cada afirmación lleva `[VERIFICADO POR EJECUCIÓN]`, `[VERIFICADO POR CÓDIGO]`, `[VERIFICADO POR TEST]` o `[NO-DETERMINABLE]`. La documentación sola NO demuestra ejecución. Las contradicciones entre relevamientos se documentan sin resolver.

Regla: EXISTE ≠ SE EJECUTA ≠ SE EJECUTA PRODUCTIVAMENTE ≠ PRODUCE EL PRODUCTO ≠ ES CANÓNICO.

---

## 1. Resumen

- **El producto que consume el usuario sale por dos caminos**: `api/main.py` (lee PG `screener`, `screener_hist`, `silver_norm`) y `data/screener_export.csv` (s5). Ambos caminos están verificados en código y artefactos.
- **El pipeline productivo confirmado por cron+logs es `run_update`** (`P-SCR-UPDATE`): daily (yfinance 571), monthly (IPC INDEC), quarterly (EDGAR incremental + CNV subset + rebuild s0→s8→s5), annual (sec_adr_ratios). Logs `upd_20260709_*.log` y artefactos en disco `[EJECUCIÓN]`.
- **El motor SEC (`P-SEC-E2E`) es un golden case YPF, no un pipeline multiemisor**: s01/s02/s03 tienen `GOLDEN_CIK=0000904851` hardcodeado y gates de volumen YPF; s04 y ratio_engine/c11 son genéricos (por CIK/run). Su producto (`derived.fact`, `derived.ratio`, `certifications`) **no alimenta a `screener` ni a la API** — es una vía paralela con provenance completa pero sin consumidor de producto verificado.
- **Publicación rota en un punto**: PG `screener_hist` (leída por la API) **no tiene ningún writer** en código, migraciones ni docs `[NO-DETERMINABLE]`. PG `screener` solo la escribe `migrate_sqlite_to_pg` (TRUNCATE+swap, desaconsejado en docstring de sync).
- **Legacy verificado como legacy**: `run_pipeline` (f1..f6) no tiene caller, cron ni tests; comparte `screener.db` con el pipeline actual (escribe `fact_*`, `screener_gold`, `dim_*`).

## 2. Criterio de clasificación

| Estado | Criterio mínimo |
|---|---|
| PRODUCTIVO CONFIRMADO | cron/scheduler + logs/outputs recientes, o caller productivo + artefactos |
| PRODUCTIVO PARCIAL | caller real (manual/runbook) + código + algún artefacto/test, sin schedule |
| ALTERNATIVO | produce lo mismo que otro por camino distinto, ejecución manual |
| LEGACY | generación anterior, sin caller/cron/test actual, datos compartidos o huérfanos |
| PILOTO | experimento acotado con artefactos |
| DEMO | sandbox explícito |
| TEST | harness de verificación, no produce datos de producto |
| INFRAESTRUCTURA | soporte (migraciones, docgen, backup, config) |
| NO-DETERMINABLE | existe código pero sin caller/artefacto/schedule que lo ancle |

Evidencia en orden: 1) ejecución real, 2) cron, 3) caller, 4) subprocess/import, 5) logs, 6) outputs, 7) tests, 8) docs.

## 3. SEC / EDGAR

**P-SEC-E2E** — `e2e_orchestrator.py` → s00 → s01 → s02 → s03 → s04 (subprocess, `ENGINE_E2E_RUN_ID`).

| Campo | Resultado |
|---|---|
| Fuente | EDGAR (companyfacts, submissions, 20-F) |
| Entry point | `scripts/engine/e2e_orchestrator.py` (+ invocación directa por stage) |
| Orden | S00_bootstrap → S01_identity → S02_fetch → S03_parse → S04_normalize (declarado = ejecutado = requerido) |
| Datos | RAW fs + `fetch_raw.download_log` → `parsed.*` → `derived.fact` (+`normalize_conflict`) |
| Persistencia | PG engine |
| Provenance | COMPLETA (run_id, checkpoints, source_fact_ids, report JSONB) |
| C10 | gates por stage (`assert_transition`, ux_checkpoints_reuse) |
| C11 | `c11_certificar --run-id` → `engine.certifications` + boletín JSON |
| C12 | **ninguna** (no alimenta screener/API/export) |
| Consumidor final | tests + auditoría humana (fase_s04: `s04_report_*.json`, `KO_GOLDEN_RUN_REPORT.md`) |
| Evidencia | `[TEST]` 26 passed; `[EJECUCIÓN]` artefactos fase_s04 |
| Estado | **PRODUCTIVO PARCIAL** (golden case operativo, sin schedule, sin consumidor de producto) |

**Especificidad YPF vs genérico** `[CÓDIGO]`:
- YPF-specific: s01 (`check_golden_ypf`, CIK 0000904851, YPF/US+YPFD/BYMA), s02 (`GOLDEN_CIK`, `SCOPE_RULE FAST:YPF:v1`, gate `GOLDEN_CIK != ...`), s03 (`GOLDEN_CIK`, expectativa ≥9 filings, `S03_YPF_PARSE_AUDIT.xlsx`). s03 acepta `--cik` (punto de extensión, no generalización).
- Genérico: s04 (resuelve `entity_key` por `identity_v1.identifier`, `--dry-run`), ratio_engine (por CIK con assertion VERIFIED; lee `market_price_daily`), c11 (por `--run-id`/`--mode`).
- e2e_orchestrator encadena solo stages `_ypf` → el E2E actual es YPF-only. Multiemisor: pendiente por regla (no generalizar).

**P-SEC-RATIO** — `ratio_engine.py [--persist]` → `derived.ratio`. Genérico por CIK, consume `derived.fact` + `market_price_daily`. Estado: PRODUCTIVO PARCIAL (consumidor de `derived.ratio` `[NO-DETERMINABLE]`).

## 4. CNV

Caminos reconstruidos:

| Camino | Nodos | Estado |
|---|---|---|
| P-CNV-MOTOR | `c3_cnv_fetch` → `fetch_raw.cnv_*` + RAW fs + checkpoints | PRODUCTIVO PARCIAL (runbook 03 + código; sin cron; consumidor: validación/auditoría) |
| P-CNV-JOBS (vía run_update quarterly) | job2→job3→job4→job5_v2 (subset 72 cuits, resume-safe) → rebuild | PRODUCTIVO CONFIRMADO (dentro del cron quarterly) |
| P-CNV-JOBS (vía run_all) | job1→...→job7 (universo completo) → assemble | ALTERNATIVO (manual) |
| P-CNV-LEGACY | serie `cnv/scripts/01..07*`, `construir_catalogo` (DROP `empresas`) | LEGACY (sin caller productivo; riesgo documentado en 03 §16.4) |
| P-CNV-IDENTITY | `c3_identity_link` → assertions identity_v1 | PRODUCTIVO PARCIAL (gobernanza append-only) |

¿Cadena CNV completa FUENTE→...→PUBLICACIÓN? **Sí, vía P-SCR-UPDATE quarterly**: CNV portal → RAW → `cnv_estados_v2` (parsed) → `cnv_estados_norm` (normalized, s0) → `fact`? (no: CNV no pasa por `derived.fact`) → `ratios_cnv` (s2) → `screener` (s4) → export/sync. Etapas C6/C11 del motor **ausentes** en el camino CNV (no usa `derived.fact` ni `c11`); validación propia: job7 + gates de assemble `[CÓDIGO]`.

## 5. Market

**P-MARKET** — m1 (mapeo, lee `dim_instrument` de screener.db) → m2 (fetch Yahoo → `market_raw_*` + `market_price_daily` + `market_snapshots`) → m4 (calidad) → m5 (golden XLSX); m6 (escala/backfill), m19 (schema). Tests propios `[TEST]`.

¿Dónde entra Market en el producto?
1. `ratio_engine` (motor): lee `market_price_daily` para EV/ventas y evidencia `[CÓDIGO]` → entra al producto del motor (no al `screener`).
2. `e2e_producto` (solo lectura): fase MARKET por ticker `[CÓDIGO]`.
3. `screener`/`s5`/API: **no consumen tablas `market_*`** — los precios del producto vienen de yfinance directo (`precios_y_valuacion`, `s3_precios`), no de Market `[CÓDIGO]`.
4. Dependencia temporal: m1 lee `dim_instrument` escrito por pipeline f1 → Market depende del pipeline legacy para el mapeo inicial `[CÓDIGO]`.

Estado: PRODUCTIVO PARCIAL (productor verificado + tests; consumidor-producto solo vía motor).

## 6. Screener

| Camino | Qué genera | Estado |
|---|---|---|
| P-SCR-UPDATE quarterly (cron) | `facts/empresas` (incremental) + CNV subset + rebuild s0→s2→s3→s4→s6→s7→s8→s5 → `screener` + export | PRODUCTIVO CONFIRMADO |
| P-SCR-UPDATE daily | `precios` + 52w + market_cap (571 tickers, yfinance) | PRODUCTIVO CONFIRMADO |
| P-SCR-UPDATE monthly | `ipc_nacional.csv` (INDEC datos.gob.ar) | PRODUCTIVO CONFIRMADO |
| P-SCR-UPDATE annual | `adr_ratios` (sec_adr_ratios vs 20-F) | PRODUCTIVO CONFIRMADO |
| P-SCR-ALL (run_all) | mismo `screener` + export (universo completo, con flags) | ALTERNATIVO |
| P-SCR-SCREENER (run_screener) | mismo `screener` + export (phases por import) | ALTERNATIVO |
| P-SILVER (demo→materia_prima→sync) | `silver_norm/validaciones/certificacion_nueva` → PG → api | PRODUCTIVO PARCIAL |

Qué camino genera `screener`: los tres (UPDATE-rebuild, ALL, SCREENER) — el productivo por schedule es UPDATE-rebuild. Qué genera `screener_gold`: solo pipeline legacy. Qué genera exports: s5 dentro de los tres caminos + ejecución verificada en disco. Qué alimenta API: PG vía migrate (screener), copia (screener_hist, writer ND), sync PLAN (silver_norm + 6).

## 7. Legacy

**P-PIPELINE-LEGACY** — `run_pipeline.py` PASOS: f1_identidad, fix_mapeo, f2_reextract_batch, f2_adr, fix_escala_anchor, fix_single_doc, fix_manual, f3b_from_reextract, f4_ratios, fix_escala_mcap, gate_autoreporte, validar_suite, f5_screener, f6_sec (subprocess en orden declarado).

- Produce: `dim_*`, `cnv_reextract`, `fact_financials`, `fact_ratios`, `screener_gold`, `validacion_suite*`, `gate_roe` (todo en `screener.db`) `[CÓDIGO]`.
- Consumidor verificado: `m1_symbol_mapping` lee `dim_instrument` (único lector cross-familia) `[CÓDIGO]`; resto de outputs sin lector productivo `[NO-DETERMINABLE]`.
- Caller/cron/tests actuales: ninguno encontrado (solo docs de revisión previa) → **LEGACY**.
- Comparte datos con el pipeline actual: sí (`screener.db`, tabla `screener` tocada por fixes, `dim_instrument` leída por market) → convivencia documentada, no eliminada.

## 8. Publicación

| Camino | Mecanismo | Estado |
|---|---|---|
| SQLite → CSV/JSON | s5_exportar → `screener_export.csv/.json` | PRODUCTIVO CONFIRMADO (artefacto 256 KB en disco) |
| SQLite → PG (PLAN) | sync: 7 tablas en reemplazo transaccional (cnv_estados_norm, cnv_estados_v2, ratios_cnv, silver_norm, validaciones, certificacion_nueva, dolarito_cotizaciones). **No toca `screener` ni `facts`** (línea 212) | PRODUCTIVO PARCIAL (manual vía SSH; sin cron) |
| screener_v2 → PG | publicar_screener_v2 → `screener_v2` | ALTERNATIVO (sin lector en api) |
| silver_norm → PG | sync PLAN (reemplazo) ← materia_prima ← demo.db:silver | PRODUCTIVO PARCIAL (cadena completa) |
| full copy → PG | migrate_sqlite_to_pg (TRUNCATE+swap, todas las tablas) | PRODUCTIVO PARCIAL (único writer de PG `screener`; uso desaconsejado en docstring — conflicto registrado) |
| PG → API | api/main.py lee `screener`, `screener_hist`, `silver_norm` | PRODUCTIVO CONFIRMADO (código; consumidores = usuarios) |

¿Qué camino llega al usuario? API (3 tablas) + CSV en disco. `screener_hist` sin writer = hueco de producto registrado.

## 9. Pipelines productivos

| ID | Pipeline | Evidencia |
|---|---|---|
| P-SCR-UPDATE | run_update (daily/monthly/quarterly/annual, cron) | `[EJECUCIÓN]` cron setup_vps.sh + logs upd_20260709 + artefactos |
| P-PUB-CSV | s5_exportar → CSV/JSON | `[EJECUCIÓN]` artefacto en disco |
| P-API | api/main.py → JSON | `[CÓDIGO]` (servicio; consumidores = usuarios) |
| P-SEC-E2E | e2e_orchestrator s00→s04 (YPF) | `[TEST]` + `[EJECUCIÓN]` fase_s04 (parcial: sin schedule, sin consumidor-producto) |
| P-CNV-MOTOR | c3_cnv_fetch | `[CÓDIGO]` + runbook (parcial: sin cron) |
| P-MARKET | m1→m2→m4→m5 | `[CÓDIGO]` + `[TEST]` (parcial: entra al producto solo vía motor) |
| P-PUB-SYNC | sync PLAN 7 tablas | `[CÓDIGO]` (parcial: manual) |
| P-PUB-MIGRATE | migrate full copy (PG screener) | `[CÓDIGO]` (parcial: único camino, uso desaconsejado) |
| P-SILVER | demo→materia_prima→sync→api | `[CÓDIGO]` (parcial: manual vía run_etl) |
| P-SEC-RATIO | ratio_engine --persist | `[CÓDIGO]` (parcial: sin lector verificado) |
| P-C11 | c11_certificar | `[TEST]` (parcial: sin consumidor en publicación) |
| P-CNV-IDENTITY | c3_identity_link → assertions identity_v1 | `[CÓDIGO]` (parcial: gobernanza append-only, sin cron) |

## 10. Pipelines alternativos

| ID | Pipeline | Produce lo mismo que | Diferencia |
|---|---|---|---|
| P-SCR-ALL | run_all | P-SCR-UPDATE rebuild | universo completo + flags (--skip/--only/--offline); manual |
| P-SCR-SCREENER | run_screener | P-SCR-UPDATE rebuild | phases por `__import__` en vez de subprocess CNV |
| P-PUB-V2 | publicar_screener_v2 | P-PUB-MIGRATE | tabla `screener_v2` en vez de `screener`; sin lector |

## 11. Pipelines legacy

| ID | Pipeline | Estado de legado |
|---|---|---|
| P-PIPELINE-LEGACY | run_pipeline f1..f6 + fixes | LEGACY: sin caller/cron/test; comparte `screener.db`; único lector `dim_instrument` (market m1) |
| P-CNV-LEGACY | serie cnv/scripts 01..07, construir_catalogo | LEGACY: `construir_catalogo` DROPEA `empresas` (riesgo si se ejecuta) |

## 12. Pipelines piloto/demo/test

| ID | Pipeline | Clase |
|---|---|---|
| P-E2E-PROD | e2e_producto (solo lectura, 8 tickers → fase_producto/fase_ratios) | TEST (auditoría) |
| P-AUDIT | idempotencia_engine, mut_f054_f055, reparse_universo | TEST (f050/f054/f055: 42 passed) |
| P-DEMO | demo_txar (23 scripts, demo*.db) | DEMO (pero escribe `ingest_log` en screener.db prod — ver 03 §16.9) |
| P-BYMA | byma/* → byma_pipeline.db | PRODUCTIVO PARCIAL (artefactos con datos; sin caller verificado) |
| P-CARGA-EXT | carga_externos → investing_* | PRODUCTIVO PARCIAL (datos presentes en screener.db) |
| P-DOLARES | dolares/* → dolares | PRODUCTIVO PARCIAL (datos presentes) |
| P-INFRA | migraciones, docgen, backup.sh, setup_vps.sh | INFRAESTRUCTURA |

## 13. NO-DETERMINABLE

- Writer de PG `screener_hist` (leída por api:215/229; cero apariciones en código/migraciones/docs).
- Lector productivo de `derived.ratio`, `fact_ratios`, `screener_gold`, `screener_v2`, boletín C11, `screener_export.csv`.
- Si `run_pipeline` / `construir_catalogo` se ejecutaron alguna vez en este entorno (sin logs/outputs propios).
- Si el cron VPS está activo ahora (existe la definición; última evidencia local de corridas: logs manuales 09/07/2026).
- `fundamentals_universo`, `homologacion_slice`, `cnv_pilot2` (pilotos sin anclaje).
- Qué validaciones (`validacion_suite`, `gate_roe`, `o2_*`) bloquean publicación realmente.

## 14. Orden real

| Pipeline | Orden declarado | Orden ejecutado | Orden requerido | Diferencia |
|---|---|---|---|---|
| P-SEC-E2E | STAGES s00→s04 | mismo (subprocess) | lineal por checkpoints | ninguna |
| P-SCR-UPDATE rebuild | s0→s8→s5 (docstring) | s0,s2,s3,s4,s6,s7,s8,s5 (rebuild_screener:592-606; s1/s2a fuera) | calcular_ratios_base antes que precios_y_valuacion (col `per`) | s1_unidades y s2a_calendario no están en el rebuild ejecutado |
| P-SCR-ALL assemble | s0→s2→s3→s4→s6→s7→s8→s9 | mismo (`__import__`) | mismo | ninguna |
| P-PIPELINE-LEGACY | PASOS (14) | mismo (loop subprocess) | f1 antes que f2 (dim_*) | ninguna |
| cron | daily 18:30 lun-vie, monthly, quarterly, annual | logs locales 09/07/2026 en horario manual (12:41–17:16) | — | **ejecución local manual, no evidencia de tick de cron en este entorno** |
| migraciones | engine 001→034 + market | orden numérico por `apply_migrations` | F-051 corrigió market no aplicadas | histórico resuelto en código |

## 15. Data Flow

**P-SEC-E2E** (provenance completa, sin C12):
```
EDGAR ─► RAW fs/download_log ─► parsed.* ─► derived.fact ─► [ratio_engine ─► derived.ratio] ─► c11 ─► certifications
  C1      C3                      C4            C5/C6              C8                          C11
```

**P-SCR-UPDATE quarterly** (producto principal):
```
EDGAR ─► facts/empresas ─► ratios ─►┐
yfinance ─► precios ────────────────┤
CNV ─► cnv_estados_v2 ─► cnv_estados_norm ─► ratios_cnv ─┤
adr_20F ─► adr_ratios ──────────────────────────────────┤
                                                         ▼
                                    s4 ─► screener ─► s5 ─► export.csv ─► (usuario lago CSV)
                                     │                    └► sync PLAN ─► PG ─► api ─► (usuario API)
                                     └► fixes pipeline (acoplado, fuera de orden)
```

**P-MARKET** (entra al producto solo vía motor):
```
Yahoo ─► market_raw_* ─► market_price_daily ─► ratio_engine/e2e_producto
dim_instrument (pipeline) ─► m1 ─► market_instruments ─► m2 ...
```

**P-SILVER**:
```
demo.db:silver ─► materia_prima/20 ─► silver_norm ─► 30_validaciones ─► 40_certificar ─► sync ─► PG ─► api
```

**P-PIPELINE-LEGACY** (sin C11/C12 propios):
```
empresas/cnv ─► dim_*/cnv_reextract ─► fact_financials ─► fact_ratios ─► screener_gold (sin lector)
```

Etapas inexistentes marcadas: CNV no usa C6-motor ni C11-motor; screener no usa C9-motor (checkpoints) ni C11; motor no tiene C12.

## 16. Provenance Flow

| Pipeline | Alcance | Clasificación |
|---|---|---|
| P-SEC-E2E + P-SEC-RATIO + P-C11 | RAW→parsed→derived.fact→ratio→certification (run_id, checkpoints, source_fact_ids, ratio_key, report, boletín) | COMPLETA |
| P-CNV-MOTOR | portal→RAW→manifest→artifact→checkpoint | COMPLETA (en su dominio) |
| P-SCR-UPDATE/ALL | EDGAR/CNV→tablas→screener→export (orden + ingesta_log + upd logs; sin run_id por fila) | PARCIAL |
| P-SILVER | demo.db→silver_norm→sync→PG (3 pasos trazables, sin hashes) | PARCIAL |
| P-MARKET | Yahoo→raw→price_daily (run_id en raw_runs, sha) | PARCIAL |
| P-PIPELINE-LEGACY | tablas intermedias sin run_id | AUSENTE salvo logs |
| P-PUB-MIGRATE/v2 | copia sin provenance adicional | AUSENTE |

## 17. C10/C11/C12

| Pipeline | C10 valida / dónde se registra | C11 certifica / consumidor | C12 publica / depende del certificado |
|---|---|---|---|
| P-SEC-E2E | gates por stage → stage_runs/checkpoints | c11 → certifications / tests+boletín | no publica — N/A |
| P-SCR-UPDATE | job7, gates de assemble, o2_*, validacion_suite → tablas + logs | **no hay C11** en este camino | s5 + sync — **NO depende de certificado** |
| P-SILVER | 30_validaciones (9 cruces) → validaciones | 40_certificar → certificacion_nueva / sync | sync → PG — depende de `certificacion_nueva` (no de c11) |
| P-MARKET | m4_quality → market_data_quality; m5 golden | no hay C11 | no publica directo |
| P-PIPELINE-LEGACY | gate_autoreporte, validar_suite → gate_roe/suite | no hay C11 | no publica |
| P-CNV-MOTOR | validación c3 → manifest | no hay C11 | no publica |

`validar_*` no es certificación: solo `c11` (motor) y `40_certificar` (materia_prima) emiten objetos de certificación; únicamente el segundo alimenta publicación.

## 18. Producto real

**¿Qué pipeline produce actualmente el producto que consume el usuario?** Dos productos, dos caminos:

1. **API (`api/main.py`)** — sirve PG `screener` (vía migrate, único camino, manual), `screener_hist` (**writer desconocido**), `silver_norm` (vía P-SILVER + sync). Consumidor: usuarios HTTP.
2. **CSV (`data/screener_export.csv`, 256 KB)** — producido por s5 dentro de P-SCR-UPDATE/ALL. Consumidor directo `[NO-DETERMINABLE]`; artefacto verificado en disco.

El pipeline que más producto genera es **P-SCR-UPDATE** (quarterly rebuild + daily precios + monthly IPC + annual ADR). El motor SEC produce el producto con mejor provenance (`derived.fact`, `certifications`) pero **sin llegada al usuario**: es un golden case YPF de referencia y certificación, no el alimentador del producto.

## 19. Grafo global

```
                        ┌─ P-SEC-E2E (YPF golden) ──► derived.fact ──► ratio_engine ──► derived.ratio
                        │        │                              └─► c11 ──► certifications (sin llegada a usuario)
                        │        └─ e2e_orchestrator (subprocess, sin cron)
                        │
FUENTES ────────────────┼─ P-SCR-UPDATE (cron) ──► screener.db ──► s5 ──► export.csv ──► usuario CSV
(EDGAR/CNV/             │        │  daily/monthly/quarterly/annual        └─► sync PLAN ─► PG ─┐
 Yahoo/INDEC/           │        └─ rebuild s0→s8→s5 (+CNV subset, EDGAR incr.)                │
 20-F/demo)             │                                                                     ▼
                        ├─ P-MARKET ──► market_* ──► (solo vía ratio_engine) ──► motor ──► usuario API
                        │                                                              ▲
                        ├─ P-SILVER ──► silver_norm ──► sync ──► PG ────────────────────┤
                        │                                                              │
                        ├─ P-PUB-MIGRATE ──► PG:screener ───────────────────────────────┤
                        │                                                              │
                        └─ P-PIPELINE-LEGACY ──► screener_gold (sin lector) ──► (aislado, comparte DB)
```

Convergencias: `screener.db` (4 caminos escriben), PG prod (3 publicadores), `dim_instrument` (pipeline→market). Divergencia mayor: el camino con mejor provenance (motor) no llega al usuario; el camino que llega (screener) no tiene C11 del motor.

## 20. Divergencias

| # | Divergencia | Clasificación |
|---|---|---|
| 1 | Tres caminos generan `screener` (UPDATE-rebuild, ALL, SCREENER) | CONFIRMADO (alternativos documentados) |
| 2 | Motor termina en PG engine; producto sale de SQLite/PG-prod (stores distintos) | CONFIRMADO |
| 3 | CNV salta C6/C11 del motor; screener salta C9/C11 del motor | CONFIRMADO (capas ausentes marcadas) |
| 4 | P-SCR-UPDATE no tiene C11; publica directamente | CONFIRMADO |
| 5 | `migrate` publica PG `screener` con TRUNCATE+swap pese a docstring en contra | CONFIRMADO (código↔documentación) |
| 6 | P-MARKET depende de P-PIPELINE-LEGACY (`dim_instrument`) | CONFIRMADO (dependencia temporal implícita) |
| 7 | Fixes del pipeline escriben `screener` fuera del orden ASSEMBLE | RIESGO |
| 8 | `screener_hist` servida sin writer | NO-DETERMINABLE (hueco) |
| 9 | Cron definido vs corridas locales manuales (este entorno) | RIESGO (producción real no observable desde aquí) |

## 21. Evidencia

- `[VERIFICADO POR EJECUCIÓN]`: cron (`setup_vps.sh:127-151`), logs `data/logs/upd_20260709_*.log` (8 corridas mismo día), `outputs/docs/fase_s04/s04_report_*.json` + `KO_GOLDEN_RUN_REPORT.md`, `data/screener_export.csv` (256 KB), `sqlite_master` (03 §2.11), tests 68 passed.
- `[VERIFICADO POR CÓDIGO]`: GOLDEN_CIK/gates YPF (s01:76-90, s02:29-30, s03:43-45), s04 genérico (identity_v1, --dry-run), ratio_engine por CIK + `market_price_daily:116`, rebuild_screener (run_update:589-623), quarterly (629-656), PLAN sync (7 tablas), `sincronizar:212`, `publicar_screener_v2:63`, `screener_hist` solo en api:215/229, callers (solo docs/tests/cron).
- `[VERIFICADO POR TEST]`: test_e2e_orchestrator, test_c11_contract, f050/f054/f055, tests/market.
- `[NO-DETERMINABLE]`: §13 + writers/lectores sin anclaje.

**Contradicciones entre relevamientos (documentadas)**:
- C1: 01 §12 decía que sync publica `screener`/`screener_hist`; 03 §11 + este paso verifican que sync NO toca `screener` (línea 212) y su PLAN cubre otras 7 tablas. Vale la lectura de código (03/04).
- C2: 02 §14.1 registraba que s04 escribe `engine.stage_runs` (report) — confirmado aquí (report JSONB s04:676); sin contradicción.
- C3: 01 atribuía `fase_s04` a FASE 4; aquí se precisa: son reports de corridas s04 (`s04_report_<hash>.json`), no del assemble.

## 22. Conteos finales

- Pipelines encontrados: 24 (12 productivos, 3 alternativos, 2 legacy, 7 piloto/demo/test/infra).
- Productivos confirmados: 3 (P-SCR-UPDATE, P-PUB-CSV, P-API). Parciales: 9.
- Alternativos: 3. Legacy: 2. Piloto/demo/test/infra: 7.
- NO-DETERMINABLE: 6 ítems (§13).
- Producto real identificado: API (3 tablas PG) + CSV (§18).
- Divergencias: 9 (6 confirmadas, 2 riesgos, 1 no-determinable).
- Evidencia: §21 (4 clases).