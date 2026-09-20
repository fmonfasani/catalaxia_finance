# 03 — Data Ownership REAL

**Relevamiento global — Paso 3.** Propiedad real de los datos: quién crea, modifica, consume y tiene autoridad sobre cada objeto. Cada afirmación lleva `[VERIFICADO POR CÓDIGO]`, `[VERIFICADO POR TEST]`, `[VERIFICADO POR EJECUCIÓN]` o `[NO-DETERMINABLE]`. Cuando código y documentación confligen se muestran ambos. Ninguna decisión de DELETE/MERGE/REPLACE (permanecen en RELEVAMIENTO).

Contexto: `01_EXECUTION_GRAPH.md` (grafo real) + `02_DEPENDENCY_GRAPH.md` (dependencias). La columna de decisión del censo NO se usó como evidencia.

Capas: C1 FUENTES · C2 IDENTIDAD · C3 RAW · C4 PARSED · C5 NORMALIZED · C6 ECONOMIC FACTS · C7 FINANCIAL MODEL · C8 RATIOS · C9 PROVENANCE · C10 VALIDACIÓN · C11 CERTIFICACIÓN · C12 PUBLICACIÓN. Planos: DATOS / CONTROL / EJECUCIÓN / INFRAESTRUCTURA.

Vocabulario de rol: SOURCE OF TRUTH · PRODUCER · WRITER · CONSUMER · AUTHORITY · DERIVATION · CACHE · MATERIALIZATION · EXPORT · LEGACY · NO-DETERMINABLE. Estado de ownership: OWNER CONFIRMADO · OWNER PROBABLE · MÚLTIPLES OWNERS · NO-DETERMINABLE.

---

## 1. Resumen

- **PostgreSQL engine** tiene ownership claro y concentrado: cada tabla de control/datos tiene un único productor (s00–s04, c3, c11, ratio_engine) y su DDL vive en `migrations/engine` (34 archivos). La política de borrado también está codificada: solo se elimina lo regenerable (`016_delete_solo_en_lo_regenerable`), y los hechos fuente son inmutables (`029_f042_source_facts_inmutable`).
- **SQLite `screener.db`** (verificada por ejecución: 70 tablas) es el único objeto con MÚLTIPLES OWNERS reales: 4 escritores de `empresas`, 2 de `dolares`, 8+ de `screener`, 2 de `ingesta/ingest_log`, más escrituras cross-familia (`demo_txar` → `ingest_log` en producción, `byma` → `_snap_log`, `carga_externos` → `investing_*`).
- **Conceptos duplicados demostrados**: dos sistemas de identidad (v0 vs v1, sin sincronización entre sí), tres hechos económicos (`derived.fact` vs `facts` vs `fact_financials` + `demo.db:fact_q`), cuatro familias de ratios, cinco objetos de publicación.
- **Cadena de publicación real**: `screener.db:screener` → `s5_exportar` → `screener_export.csv` → API indirecto; PG `screener` NO lo toca `sincronizar_a_produccion` (línea 212) y su único writer encontrado es `migrate_sqlite_to_pg` (vía TRUNCATE+swap, desaconsejado en docstring) — **conflicto código↔documentación registrado**. La cadena `silver_norm` es completa y trazable: `demo.db:silver` → `materia_prima/20_extrae_silver` → `screener.db:silver_norm` → PLAN sync (reemplazo) → PG → `api`.
- **Barrera VALIDACIÓN→CERTIFICACIÓN→PUBLICACIÓN**: efectiva en el motor (gates → checkpoints → c11 → certifications), pero la publicación real (`api`) **no consume `engine.certifications`** — la barrera existe en el motor y no llega a la publicación.

## 2. Inventario de objetos

### 2.1 PostgreSQL — engine (control + datos)

| Objeto | Rol |
|---|---|
| engine.runs | corrida (modo, estado, commit, pipeline_version) |
| engine.stage_runs | evidencia por etapa incl. `report` JSONB |
| engine.checkpoints | re-ejecución idempotente (ux_checkpoints_reuse) |
| engine.certifications | certificados C11 (idempotente por run) |
| engine.schema_migrations | control de migraciones aplicadas |

### 2.2 Identidad

| Objeto | Origen |
|---|---|
| identity.entities / identity.identifiers | `engine/identity.py` (v0) `[CÓDIGO]` |
| identity.identifier_reviews / identity.classifications | leídas por s01 (DDL en `migrations/engine/002`) |
| identity_v1.entity / identifier / source | `engine/identity_v1.py` `[CÓDIGO]` |
| identity_v1.assertion / review / conflict | gobernanza append-only (DDL `008/009/030`) |
| identity_v1.instrument / instrument_symbol | instrumentos y símbolos (DDL `010`) |
| identity_v1.v_entity_resolution | vista de resolución |
| (NO existe tabla `identity_v1.bridges`: los bridges CIK↔LEI se registran como assertions vía `bridge_verificado`) | `[CÓDIGO]` |

### 2.3 RAW

| Objeto | Origen |
|---|---|
| fetch_raw.download_log | s02 |
| fetch_raw.cnv_download_log / cnv_artifact / cnv_presentation | c3 (DDL `005/007`) |
| filesystem RAW SEC (`RAW_ROOT`) | s02 (companyfacts, submissions) |
| filesystem RAW CNV (RawStore por CUIT) | c3 |
| market_raw_files / market_raw_runs | m2 |

### 2.4 PARSED

| Objeto | Origen |
|---|---|
| parsed.facts / contexts / concepts / units / link_relations / parse_errors / pre_xbrl_filings / companyfacts_compare | s03 (DDL `004/006/017/018/020`) |
| cnv_estados / cnv_estados_suspect | jobs CNV (job7 valida/borra) |
| cnv_estados_v2 (+`_pre_pk`) | job5_v2 |
| cnv_dividendos | job6_v2 |
| cnv_documents / cnv_filings / fiscal_calendar | cnv/metadata/build_fiscal_calendar |

### 2.5 NORMALIZED

| Objeto | Origen |
|---|---|
| derived.fact (columnas de normalización + unidad resuelta) | s04 (DDL `014/015`) |
| cnv_estados_norm (+`_pre_escala`) | s0 |
| mapa_entidades | s0 |
| fact_financials (+`_cuarentena`) / entity_validacion | f3/f3b |
| silver_norm (screener.db) | materia_prima/20_extrae_silver (DDL `00_setup_tables`) |

### 2.6 ECONOMIC FACTS

| Objeto | Origen |
|---|---|
| derived.fact (columnas de valor: value_numeric/text, n_fuentes, source_fact_ids) | s04 |
| facts (+facts_xbrl, facts_pre_redescarga, bronze_raw) | construir_base |
| fact_financials | f3/f3b |
| demo.db:fact_q / fact panel | demo_txar (sandbox) |

### 2.7 RATIOS / MODEL

| Objeto | Origen |
|---|---|
| derived.ratio | ratio_engine (DDL `032/033`) |
| ratios | calcular_ratios_base / precios_y_valuacion / flags_calidad |
| ratios_cnv | s2 |
| fact_ratios | f4 |
| adr_ratios | sec_adr_ratios |
| cedear_ratios | cedear_ratios |
| screener_ratios / screener_ratios_hist | load_screener_ratios |
| ratios_ttm / per_ttm | cnv/metadata |
| ratios_externos / eerr_externos | fix_mapeo (externos) |

### 2.8 MARKET (PG)

market_instruments / market_symbol_mappings (m1, DDL `013_venue_ticker`) · market_price_daily / market_snapshots / market_fetch_log / market_data_quality / market_data_changes / market_corporate_actions / market_raw_files / market_raw_runs (m2/m4).

### 2.9 PUBLICACIÓN

| Objeto | Origen |
|---|---|
| screener (SQLite) | s4 (DROP+CREATE) + updates s6..s9b, cedear/jpm, fixes |
| screener_hist (SQLite) | load/histórico (`_hist`); PG: sync/copia |
| screener_export.csv / .json | s5_exportar |
| silver_norm (SQLite→PG) | materia_prima → sync PLAN (reemplazo) |
| screener_v2 (PG) | publicar_screener_v2 |
| screener_gold (SQLite) | f5/f6 (pipeline) + copias demo DBs |
| screener (PG prod) | writer único encontrado: migrate_sqlite_to_pg (ver §16) |
| validaciones / certificacion_nueva | materia_prima 30/40 → sync PLAN |

### 2.10 Otras DBs verificadas por ejecución

- `byma_pipeline.db`: anomalias, balances_ttm_byma, byma_universo, certificacion, mercado_byma, metricas, partidas_norm, partidas_ratios_cnv, ratios_ttm_byma, validacion_mat — dominio BYMA aislado `[EJECUCIÓN]`.
- `demo*.db` (4): bronce_docs, certificacion, cierre, cnv_raw, dim_entity, fact_q, faltantes, meta, ratios, ratios_panel, screener_gold, silver — sandbox demo con sus propias copias `[EJECUCIÓN]`.
- `screener.db`: 70 tablas (lista completa en §2.11) `[EJECUCIÓN]`.

### 2.11 `screener.db` — inventario físico real

`_bk_screener_pre_iamc, _screener_pre_s8, _snap_log, adr_dividendos, adr_ratios, bronze_raw, cedear_ratios, certificacion_nueva, cnv_dividendos, cnv_documents, cnv_estados, cnv_estados_norm, cnv_estados_norm_pre_escala, cnv_estados_suspect, cnv_estados_v2, cnv_estados_v2_pre_pk, cnv_filings, cnv_reextract, descargas_log, diag_nic29, diag_per_operativo, dim_entity, dim_instrument, dolares, dolarito_cotizaciones, eerr_externos, empresas, entity_validacion, fact_financials, fact_financials_cuarentena, fact_ratios, facts, facts_pre_redescarga, facts_xbrl, fiscal_calendar, gate_roe, ingest_log, ingesta_log, instrumentos, investing_comparacion, investing_estados, investing_full, mapa_entidades, market_cap_derivado, o2_arbitro_roe, o2_gate_roe, o2_m3_checks, per_ttm, precios, precios_diarios, ratios, ratios_cnv, ratios_externos, ratios_pre_ventana, ratios_ttm, screener, screener_gold, screener_nivel, screener_nivel_edgar, silver_norm, tickers, unidad_sospechas, validacion_suite, validacion_suite_edgar, validaciones` `[EJECUCIÓN: sqlite_master]`.

## 3. Ownership real

Formato: objeto | productor | escritores | consumidores | autoridad | source of truth | estado.

### 3.1 Motor (OWNER CONFIRMADO en casi todos)

| Objeto | Productor | Escritores | Consumidores | Autoridad | SoT | Estado |
|---|---|---|---|---|---|---|
| engine.runs | e2e_orchestrator / db.create_run | e2e, stages (update estado) | s03, s04, c11, tests | engine.db | Sí (DDL `001`, cierre huérfanas `013`) | canónico |
| engine.stage_runs | s03, s04 | s03, s04 | c3, c11, s03 | stage que lo emite | Sí | canónico |
| engine.checkpoints | s00–s04, c3 | 6 escritores (mismo contrato) | s04, c11 | contrato ux_checkpoints_reuse | Sí | canónico |
| engine.certifications | c11 | c11 (único, INV1) | boletín JSON, tests | c11 | Sí (DDL `034`) | canónico |
| parsed.facts/contexts | s03 | s03 | s04, c11 | s03 + DDL `004` | Sí | canónico |
| derived.fact | s04 | s04 (único; ON CONFLICT fact_key) | ratio_engine, c11 | s04 + inmutabilidad `029` | Sí | canónico |
| derived.ratio | ratio_engine | ratio_engine (`--persist`) | (consumidor actual `[NO-DETERMINABLE]`) | ratio_engine + DDL `032` | Sí | canónico |
| fetch_raw.download_log | s02 | s02 | s03 | s02 | Sí | canónico |
| fetch_raw.cnv_* | c3 | c3 | c3, auditoría | c3 + DDL `005` | Sí | canónico |
| identity.identifiers | s01 | s01 (vía engine.identity) | s03, identity_v1_backfill_dev | s01 | Probable (v0) | canónico-v0 |
| identity_v1.* | c3_identity_link, backfills, pilots | varios (append-only) | c3_validation, f024, benches | convención append-only | Probable (v1) | canónico-v1 |

### 3.2 Screener.db (MÚLTIPLES OWNERS)

| Objeto | Productor | Escritores | Consumidores | Autoridad | Estado |
|---|---|---|---|---|---|
| empresas | construir_base | construir_base, construir_catalogo (DROP+recreate), cargar_argentina_cnv, cargar_byma_yfinance | f1, s-series | NO único | MÚLTIPLES OWNERS |
| facts | construir_base | construir_base (DELETE+INSERT) | calcular_ratios, s-series | construir_base | OWNER PROBABLE |
| ratios | calcular_ratios_base | calcular_ratios_base (DROP), precios_y_valuacion, flags_calidad | s4, s6..s9, api(indirecto) | convención de orden run_all | MÚLTIPLES OWNERS |
| precios | precios_y_valuacion | precios_y_valuacion, s3_precios, s3c, rangos_52w | s4, valuación | precios_y_valuacion (creador) | MÚLTIPLES OWNERS |
| screener | s4_ensamblar | s4 (DROP+CREATE), s6..s9b, cedear_ratios, jpm_adr, fix_manual, fix_mapeo | s5, sync-lee-no-escribe, api(indirecto) | run_all/run_screener (orden ASSEMBLE) | MÚLTIPLES OWNERS |
| dolares | dolares/actualizar | actualizar_dolares, materia_prima/10b | sync PLAN | — | MÚLTIPLES OWNERS |
| ingesta_log | _ingesta_log | construir_base, _raw_inmutable | auditoría RAW | _raw_inmutable | OWNER PROBABLE |
| ingest_log | demo_txar/41 + cnv/metadata | 41_fetch_nuevo (**demo→prod**), fetch_cnv_pages | diagnóstico | — | MÚLTIPLES OWNERS |
| fiscal_calendar | build_fiscal_calendar | build_fiscal_calendar, s2a_calendario | s2 | build_fiscal_calendar | MÚLTIPLES OWNERS |
| silver_norm | materia_prima/20 | 20_extrae_silver (INSERT OR REPLACE) | 30_validaciones, sync PLAN, api | materia_prima | OWNER CONFIRMADO |
| validaciones | materia_prima/30 | 30_validaciones | sync PLAN | materia_prima | OWNER CONFIRMADO |
| certificacion_nueva | materia_prima/40 | 40_certificar | sync PLAN | materia_prima | OWNER CONFIRMADO |
| screener_gold | f5/f6 | f5, f6 | (consumidor `[NO-DETERMINABLE]`) | pipeline | OWNER PROBABLE |
| dim_entity/dim_instrument | f1 | f1, fix_mapeo, fix_manual | market m1 (dim_instrument) | pipeline | OWNER PROBABLE |
| _snap_log | byma/snapshot | snapshot_byma | — | byma | OWNER PROBABLE |
| investing_* | carga_externos | carga_* (INSERT OR REPLACE) | comparaciones | carga_externos | OWNER PROBABLE |
| validacion_suite(_edgar) | pipeline | validar_suite(_edgar) | gate_autoreporte | pipeline | OWNER PROBABLE |
| gate_roe | gate_autoreporte | gate_autoreporte | run_pipeline | pipeline | OWNER PROBABLE |

## 4. Multi-writer

### 4.1 `screener.db` — el objeto compartido crítico

**Orden de escritura productivo (run_all, intencional)**: `construir_base(facts,empresas)` → `calcular_ratios_base(ratios DROP)` → `precios_y_valuacion(ratios.per,precios)` → `s0(cnv_estados_norm,mapa_entidades)` → `s2(ratios_cnv)` → `s3(precios)` → `s4(screener DROP+CREATE)` → `s6..s9b(screener UPDATE)` → `s5(export)` `[CÓDIGO]`. Clasificación: **COMPARTIDO INTENCIONAL** (cada etapa posee su tabla; `screener` se construye por capas y nadie re-escribe lo anterior salvo su columna).

**Pisadas reales (reemplazo, no merge)**:
- `ratios`: DROP+recreate por calcular_ratios_base (borra `per`, recreado después). Si se corre sin precios_y_valuacion, `s6/s7` rompen `[CÓDIGO]`.
- `screener`: DROP+CREATE por s4; luego UPDATEs por columna/familia. `fix_mapeo`/`fix_manual` (pipeline) también hacen UPDATE `screener` fuera del orden ASSEMBLE → **COMPARTIDO CON ACOPLAMIENTO**.
- `empresas`: DROP por construir_catalogo (legacy) vs INSERT/UPDATE por construir_base (productivo) + UPDATEs laterales (cargar_argentina_cnv, cargar_byma_yfinance) → **COMPARTIDO CON CONFLICTO POTENCIAL**.
- `dolares`: INSERT OR REPLACE por dos familias → **COMPARTIDO CON CONFLICTO POTENCIAL** (último escritor gana).
- `facts`: DELETE+INSERT por construir_base en cada corrida (regenerable desde EDGAR) → COMPARTIDO INTENCIONAL (único writer productivo).

**Dependencia cruzada de resultado**: `m1_symbol_mapping` (market) lee `dim_instrument` escrito por `f1_identidad` (pipeline). Si el pipeline no corrió, market mapea sobre datos viejos — dependencia temporal implícita `[CÓDIGO]`.

### 4.2 Motor (sin multi-writer conflictivo)

Cada tabla PG tiene un único writer productivo; `engine.checkpoints` tiene 6 escritores pero bajo el mismo contrato de idempotencia (ON CONFLICT) → COMPARTIDO INTENCIONAL. `derived.fact` tiene escritura exclusiva de s04 con ON CONFLICT fact_key + inmutabilidad declarada (`029`) → OWNER CONFIRMADO.

## 5. Conceptos duplicados

### 5.1 Identidad: `identity.*` vs `identity_v1.*` — MISMO concepto, dos autoridades

- Ambos resuelven "qué entidad es este emisor" por CIK/CUIT/LEI. v0: `identifiers/entities` + reviews, consumido por s01/s03. v1: `entity/identifier/source` + `assertion/review/conflict` (append-only), consumido por c3/cnv-validation/backfills.
- Bridges CIK↔LEI existen solo en v1 (`bridge_verificado`, decisión `BRIDGE_RATIFICADO`); **no hay sincronización v0↔v1** ni tabla puente entre ambos sistemas `[CÓDIGO]`.
- Autoridad actual: **dividida** (s01 para v0, convención de assertions para v1). Conclusión de relevamiento: dos fuentes de verdad paralelas sin bridge. NO se decide cuál eliminar.

### 5.2 Hechos: `derived.fact` vs `facts` vs `fact_financials` (+`fact_q`)

- `derived.fact` (PG): hechos SEC normalizados con provenance completa (source_fact_ids, input_checkpoint_id, run_id). Consumidor: ratio_engine/c11. Productor: s04.
- `facts` (SQLite): hechos EDGAR crudos/parseados por construir_base. Consumidor: calcular_ratios_base, s-series. Sin `run_id` ni checkpoint por fila (provenance vía `ingesta_log` + logs).
- `fact_financials` (SQLite): hechos CNV normalizados por f3/f3b. Consumidor: f4.
- `demo.db:fact_q`: hechos del sandbox demo. Aislado.
- Representan el mismo concepto ("hecho económico por emisor/período") en tres stores sin sincronización entre sí `[CÓDIGO]`.

### 5.3 Ratios: `derived.ratio` vs `ratios` vs `fact_ratios` vs `ratios_cnv` (+`adr_ratios`, `cedear_ratios`, `screener_ratios`)

- `derived.ratio` (PG, ratio_engine): consumidor actual `[NO-DETERMINABLE]` — producido pero sin lector productivo verificado.
- `ratios` (SQLite): el consumido por el ensamble (`s4..s9`) y la publicación indirecta.
- `fact_ratios` (SQLite): producido por f4 del pipeline legacy; consumidor `[NO-DETERMINABLE]`.
- `ratios_cnv`, `adr_ratios`, `cedear_ratios`, `screener_ratios(_hist)`: insumos especializados por fuente (CNV, ADR oficial, CEDEARs, histórico).
- Mismo concepto ("ratio por emisor/período"), 4+ materializaciones sin bridge común.

### 5.4 Publicación: `screener` vs `screener_gold` vs `screener_hist` vs `screener_v2` vs `silver_norm`

- `screener` (SQLite): el ensamblado canónico; leído por s5.
- `screener_gold` (SQLite): ensamblado del pipeline legacy; consumidor `[NO-DETERMINABLE]`.
- `screener_hist` (PG): histórico publicado; poblado vía copia (writer exacto: copia genérica `migrate_sqlite_to_pg`, ver §16).
- `screener_v2` (PG): publicado por `publicar_screener_v2`; **no es leído por `api`** (api lee `screener`) → publicado sin consumidor verificado.
- `silver_norm` (SQLite→PG): cadena completa demo→materia_prima→sync→api; es el único publicado con provenance extremo a extremo.

## 6. Cross-family ownership

| Dependencia | Dato ajeno consumido | Owner real del dato | Clasificación |
|---|---|---|---|
| market m1 → screener.db | `dim_instrument` | pipeline (f1) | dependencia de familia ajena, lectura sin contrato |
| sec_edgar construir_base → helpers screener/ | `_caducidad`, `_ingesta_log` (código, no dato) | screener family | dependencia de código compartido |
| pipeline fixes → `screener` | tabla del ensamble canónico | screener family (run_all orden) | escritura ajena fuera de orden |
| demo_txar/41 → `ingest_log` (screener.db prod) | tabla de log productiva | diagnóstico/CNV | **escritura de sandbox en DB productiva** |
| byma/snapshot → `_snap_log` (screener.db) | log propio en DB ajena | byma | escritura aislada por tabla (sin conflicto) |
| carga_externos → `investing_*` | tablas propias en DB compartida | carga_externos | escritura aislada por tabla |
| engine s01/s03 → identity v0 | identidad | engine (s01) | ownership interno del motor |
| c3/cnv-validation → identity_v1 | identidad v1 | convención append-only | ownership interno del motor |
| deploy sync → screener.db | 7 tablas PLAN + lectura general | sync (solo sync, reemplazo) | EXPORT con reemplazo transaccional |
| api → PG prod | `screener`, `screener_hist`, `silver_norm` | publicación | solo lectura |

## 7. Identity ownership

### 7.1 Sistema v0 (`identity.*`, engine/identity.py)

- Objetos: `entities`, `identifiers`, `identifier_reviews`, `classifications`. DDL: `migrations/engine/002_s01_identity.sql`.
- Productor/autoridad: **s01_identity** (único writer vía `engine.identity`). Consumidores: s03 (`resolve_por_cik`), `identity_v1_backfill_dev` (lee `SEC_CATALOG_DIR`, no las tablas).
- Separación interna: IDENTIDAD (entities/identifiers) vs CLASIFICACIÓN (classifications) vs REVISIÓN (identifier_reviews). Los tickers viven solo en `identifiers` (s01:73) `[CÓDIGO]`.

### 7.2 Sistema v1 (`identity_v1.*`, engine/identity_v1.py)

- Objetos: `source`, `entity` (entity_key opaco), `identifier`, `instrument`, `instrument_symbol`, `assertion`, `review`, `conflict`, vista `v_entity_resolution`. DDL: `008/009/010/030/031`.
- Semántica: **append-only** — corregir es emitir una assertion nueva (`c3_identity_link:16`); los conflictos se resuelven con decisiones (`BRIDGE_RATIFICADO`) sin UPDATE destructivo.
- Separación interna: IDENTIDAD (entity/identifier) · INSTRUMENTO (instrument) · SÍMBOLO (instrument_symbol) · BRIDGE (assertions CIK↔LEI vía `bridge_verificado`) · REVISIÓN/CONFLICTO (review/conflict).
- Productores: `c3_identity_link`, backfills (`backfill_cik`, `identity_v1_backfill_*`), pilots, `f024_bma`. Consumidores: `cnv_validation_adversario/auditor`, benches f044/f045.

### 7.3 ¿Quién es autoridad de identidad?

**No hay una única autoridad**: v0 la decide s01 (motor SEC), v1 la decide la convención de assertions (motor CNV). Ningún componente sincroniza ambos sistemas. Pregunta registrada para pasos 7–10, sin resolución.

## 8. RAW ownership

| RAW | Fuente | Writer | Mutabilidad | Hash | Archivado/restore | Provenance |
|---|---|---|---|---|---|---|
| SEC companyfacts/submissions (fs) | EDGAR API | s02 (vía engine.fetch) | inmutable tras descarga | sha256 (`write_raw_new`, `raw_existing_hash`) | `_raw_inmutable.archivar/restaurar` (usado por run_update) | download_log + ingesta_log |
| CNV RAW (fs, RawStore/CUIT) | CNV portal | c3 (+jobs job2) | inmutable (canonical_sha256) | canonical_sha256 | manifest + `fetch_raw.cnv_artifact` | download_log + artifact + presentation |
| market_raw_files/runs | Yahoo | m2 (+`_raw_inmutable` registrar) | versionado por run | sha256 | market_raw_runs | fetch_log |
| screener.db ingesta | EDGAR/CNV | construir_base, jobs | regenerable | sha en ingesta_log | `_raw_inmutable.registrar` | ingesta_log |

Framework `_raw_inmutable` (`archivar(path, razon)`, `restaurar(prov)`, `registrar(con, cik, tipo, sha_previo, razon, evento)`): consumidores verificados **run_update.py y `m2_fetch_engine.py`** (market) — ownership compartido del mecanismo de inmutabilidad entre dos familias `[CÓDIGO]`.

**Violaciones de inmutabilidad**: ninguna detectada en RAW físico. Los DELETE/DROP verificados (`facts`, `ratios`, `screener`, `cnv_estados`) operan sobre tablas **regenerables**, consistente con la política `migrations/engine/016` (borrar solo lo regenerable) y la inmutabilidad de hechos fuente (`029`). `construir_catalogo` DROPEA `empresas` — tabla también escrita por el path productivo → riesgo registrado en §16, no violación confirmada de RAW (no es RAW físico).

## 9. Provenance ownership

Cadena reconstruible por objeto derivado:

| Derivado | Input | Transformador | run_id | checkpoint | hash | source_fact_ids | Clasificación |
|---|---|---|---|---|---|---|---|
| derived.fact | parsed.facts | s04 | sí | input_checkpoint_id | fact_key | sí (+n_fuentes) | COMPLETA |
| derived.ratio | derived.fact | ratio_engine (+sql_insumos) | `[NO-DETERMINABLE]` en fila | — | ratio_key c/provenance | heredado | PARCIAL |
| ratios (SQLite) | facts | calcular_ratios_base | no (sqlite sin run) | no | no | no | PARCIAL (vía ingesta_log+logs) |
| screener | ratios/precios/cnv/adr | s4..s9 | no | no | no | no | PARCIAL (orden ASSEMBLE + `_snap`/logs) |
| silver_norm | demo.db:silver | materia_prima/20 | no | no | no | no | PARCIAL (cadena de 3 pasos trazable) |
| engine.certifications | stage_runs/checkpoints | c11 | sí | sí | sí | n/a | COMPLETA |
| market_price_daily | market_raw_* | m2 | run_id (raw_runs) | — | sha raw | n/a | PARCIAL |

Cadena completa extremo a extremo solo en el motor: `RAW → PARSED → NORMALIZED → ECONOMIC FACT (derived.fact) → RATIO (derived.ratio) → CERTIFICACIÓN`. La familia screener reconstruye provenance por convención de orden + logs, sin identificadores por fila.

## 10. Control ownership

| Objeto | Escritores | Consumidores | Autoridad | Canónico vs histórico |
|---|---|---|---|---|
| engine.runs | e2e_orchestrator, stages | s03/s04/c11/e2e | engine.db (DDL `001`, cierre huérfanas `013`) | canónico (estado actual) |
| engine.stage_runs | s03/s04 | c11, c3 | stage emisor | histórico append-only |
| engine.checkpoints | s00–s04, c3 | s04, c11 | contrato de idempotencia | canónico (último por ux) |
| engine.certifications | c11 | boletín, tests | c11 | histórico append-only |
| StageReport/GateStatus/StageState | engine.report/states (definición) | s00–s04, c3, c11 | contrato de código | canónico (definición) |
| manifests (cnv_artifact, _run_manifest, upd logs) | c3, run_all, run_update | auditoría | productor | histórico |
| hashout | engine.hashout | s03/s04/release_baseline | función determinista | n/a |

Evidencia histórica vs estado: `stage_runs`/`certifications`/`manifests` son históricos (nunca se reescriben); `runs.status` y `checkpoints` son estado mutable canónico.

## 11. Publication ownership

Cadena real verificada:

```
screener.db:screener --(s5_exportar)--> screener_export.csv/.json   [C12, EXPORT]
screener.db:{cnv_estados_norm,cnv_estados_v2,ratios_cnv,silver_norm,validaciones,certificacion_nueva,dolarito_cotizaciones}
   --(sincronizar_a_produccion PLAN reemplazo)--> PG prod            [C12, EXPORT]
screener.db --(migrate_sqlite_to_pg, TRUNCATE+swap)--> PG prod:screener   [único writer encontrado]
screener.db --(publicar_screener_v2)--> PG prod:screener_v2           [sin consumidor verificado]
PG prod:{screener,screener_hist,silver_norm} --(api/main.py)--> JSON  [C12, solo lectura]
```

¿Dónde se vuelve publicable un dato? En `s5_exportar` (validación final + export CSV) para el camino CSV; en el PLAN de sync (reemplazo transaccional) para el camino PG. No hay gate de certificación en ninguno de los dos caminos: `api` no lee `engine.certifications` y `s5` no exige certificado `[CÓDIGO]`.

¿Barrera VALIDACIÓN→CERTIFICACIÓN→PUBLICACIÓN efectiva? **En el motor: sí** (gates→checkpoints→c11→certifications). **En la publicación real: no** — la certificación existe pero ningún publicador la consume. Registrado como hallazgo, sin corrección.

## 12. Database ownership

| DB | Owner | Escritores | Lectores | Propósito | Aislamiento |
|---|---|---|---|---|---|
| PG engine | engine.db + migrations/engine | s00–s04, c3, c11, ratio_engine, identity-writers | stages, c11, tests, api(no) | control + hechos SEC/CNV | alta (roles `011`, market readonly `012`) |
| PG market | market_db (guarda F-001) | m1, m2, m4, m19 | m2/m4/m5, ratio_inputs | precios y calidad market | alta |
| PG producción | deploy (sync PLAN + migrate) | sincronizar (7 tablas), migrate (full copy), publicar_screener_v2 (screener_v2) | api | servir API | media (múltiples publicadores, ver §16) |
| SQLite screener.db | **nadie único** | 20+ componentes de 6 familias | todas las familias + sync | hechos/ratios/ensamble/publicación staging | **nulo** (origen de §16) |
| SQLite byma_pipeline.db | byma family | byma scripts | byma | dominio BYMA | alta |
| SQLite demo*.db | demo_txar | demo_txar | materia_prima/20 (lee silver) | sandbox + semilla de silver_norm | baja (demo alimenta prod vía silver) |

## 13. File ownership

| Archivo | Productor | Consumidor | Rol |
|---|---|---|---|
| data/screener_export.csv + .json | s5_exportar | (consumidor directo `[NO-DETERMINABLE]`; artefacto verificado en disco) | EXPORT |
| RAW SEC (RAW_ROOT/*.json) | s02 | s03 | SOURCE materializado |
| RAW CNV (RawStore/*) | c3, job2 | job3..job8, c3 | SOURCE materializado |
| market raw files | m2 | m4/m5 | SOURCE materializado |
| data/logs/upd_YYYYMMDD.log | run_update | auditoría humana | PROVENANCE (log) |
| data/logs/runs/ (0 manifests) | (diseño: runners) | — | CONTROL ausente |
| boletín C11 JSON | c11_certificar | (consumidor `[NO-DETERMINABLE]`) | CERTIFICACIÓN materializada |
| golden case XLSX | m5_golden_case | revisión humana | VALIDACIÓN materializada |
| .env | operador | engine.config | CONFIG |

## 14. Matriz central

| Objeto | Capa | Plano | Owner | Writers | Consumers | Source of Truth | Derivado de | Provenance | Estado | Evidencia |
|---|---|---|---|---|---|---|---|---|---|---|
| engine.runs | C9 | CONTROL | e2e/engine.db | e2e+stages | s03,s04,c11 | Sí | — | run_id | canónico | [CÓDIGO] |
| engine.stage_runs | C9 | CONTROL | stage emisor | s03,s04 | c3,c11 | Sí | checkpoints | report JSONB | canónico | [CÓDIGO] |
| engine.checkpoints | C9 | CONTROL | contrato idempotencia | s00–s04,c3 | s04,c11 | Sí | gates | ux reuse | canónico | [CÓDIGO] |
| engine.certifications | C11 | CONTROL | c11 | c11 | boletín,tests | Sí | stage_runs | completa | canónico | [CÓDIGO]+[TEST] |
| identity.identifiers | C2 | DATOS | s01 | s01 | s03 | Probable | SEC catalog | parcial | canónico-v0 | [CÓDIGO] |
| identity_v1.entity/identifier | C2 | DATOS | convención append-only | c3_link,backfills | c3_validation | Probable | CNV/SEC | assertions | canónico-v1 | [CÓDIGO] |
| fetch_raw.download_log | C3 | DATOS | s02 | s02 | s03 | Sí | EDGAR API | completa | canónico | [CÓDIGO] |
| fetch_raw.cnv_* | C3 | DATOS | c3 | c3 | c3 | Sí | CNV API | completa | canónico | [CÓDIGO] |
| parsed.facts/contexts | C4 | DATOS | s03 | s03 | s04,c11 | Sí | RAW SEC | completa | canónico | [CÓDIGO] |
| derived.fact | C5/C6 | DATOS | s04 | s04 | ratio_engine,c11 | Sí | parsed | completa | canónico | [CÓDIGO] |
| derived.ratio | C8 | DATOS | ratio_engine | ratio_engine | [NO-DET] | Sí | derived.fact | parcial | canónico | [CÓDIGO] |
| facts (sqlite) | C6 | DATOS | construir_base | construir_base | calcular_ratios,s-series | Probable | EDGAR | parcial | canónico-sqlite | [CÓDIGO] |
| empresas (sqlite) | C2 | DATOS | — (múltiple) | base,catalogo,cargar_* ×2 | f1,s-series | No | EDGAR/CNV | parcial | MÚLTIPLE | [CÓDIGO] |
| ratios (sqlite) | C8 | DATOS | orden run_all | calc_ratios,precios,flags | s4,s6..s9 | No | facts | parcial | MÚLTIPLE | [CÓDIGO] |
| precios (sqlite) | C8 | DATOS | precios_y_valuacion | precios_y_val,s3*,rangos | s4 | Probable | yfinance | parcial | MÚLTIPLE | [CÓDIGO] |
| cnv_estados_norm | C5 | DATOS | s0 | s0 | s2,sync | Probable | cnv_estados_v2 | parcial | canónico | [CÓDIGO] |
| mapa_entidades | C5 | DATOS | s0 | s0 | s2 | Probable | cnv | parcial | canónico | [CÓDIGO] |
| fact_financials | C5/C6 | DATOS | f3/f3b | f3,f3b | f4 | Probable | cnv_reextract | parcial | canónico-legacy | [CÓDIGO] |
| screener (sqlite) | C7 | DATOS | orden ASSEMBLE | s4,s6..s9b,cedear,jpm,fixes | s5 | No único | ratios/precios/cnv | parcial | MÚLTIPLE | [CÓDIGO] |
| screener_gold | C7 | DATOS | pipeline | f5,f6 | [NO-DET] | Probable | fact_* | parcial | legacy | [CÓDIGO] |
| screener_hist (PG) | C12 | DATOS | copia | migrate | api | No | screener | — | publicado | [CÓDIGO] |
| screener_v2 (PG) | C12 | DATOS | publicar_screener_v2 | publicar_v2 | [NO-DET] | Probable | screener.db | — | publicado-sin-lector | [CÓDIGO] |
| silver_norm | C5 | DATOS | materia_prima | 20_extrae_silver | 30_valid,sync,api | Sí | demo.db:silver | cadena 3 pasos | canónico | [CÓDIGO] |
| validaciones | C10 | DATOS | materia_prima | 30_validaciones | sync | Sí | silver_norm | cadena | canónico | [CÓDIGO] |
| certificacion_nueva | C11 | DATOS | materia_prima | 40_certificar | sync | Sí | validaciones | cadena | canónico | [CÓDIGO] |
| market_price_daily | C6 | DATOS | m2 | m2 | m4,ratio_inputs | Sí | Yahoo raw | parcial | canónico | [CÓDIGO] |
| market_instruments | C3 | DATOS | m1 | m1 | m2 | Sí | dim_instrument+venue | parcial | canónico | [CÓDIGO] |
| dolares | C6 | DATOS | — (múltiple) | dolares/,materia_prima | sync | No | BCRA/MEP | [NO-DET] | MÚLTIPLE | [CÓDIGO] |
| ingesta_log/ingest_log | C9 | DATOS | _raw_inmutable | base,jobs,demo,cnv_meta | auditoría | No único | raw físico | sí (es provenance) | MÚLTIPLE | [CÓDIGO] |
| screener_export.csv | C12 | DATOS | s5_exportar | s5 | [NO-DET] | Sí | screener | — | EXPORT | [CÓDIGO]+[EJECUCIÓN] |

## 15. Mapas

### 15.1 DATOS

```
EDGAR ──► s02 ──► RAW SEC ──► s03 ──► parsed.* ──► s04 ──► derived.fact ──► ratio_engine ──► derived.ratio
EDGAR ──► construir_base ──► facts/empresas ──► calcular_ratios_base ──► ratios ──┐
yfinance ──► precios_y_valuacion ──► precios ────────────────────────────────────┤
CNV ──► jobs ──► cnv_estados_v2 ──► s0 ──► cnv_estados_norm ──► s2 ──► ratios_cnv ┤
                                                                                 ▼
SEC-20F ──► sec_adr_ratios ──► adr_ratios ──► s6 ──► s4 ──► screener ──► s5 ──► export
demo.db:silver ──► materia_prima ──► silver_norm/validaciones/certificacion_nueva ──► sync ──► PG ──► api
```

### 15.2 CONTROL

```
run ──► stages ──► stage_runs ──► c11 ──► certifications ──► boletín
         └─► checkpoints (idempotencia, 6 escritores, 1 contrato)
```

### 15.3 PUBLICACIÓN

```
screener ──► s5 ──► CSV/JSON (EXPORT sin gate de certificación)
{7 tablas} ──► sync PLAN reemplazo ──► PG prod ──► api (lectura)
screener.db ──► migrate (TRUNCATE+swap) ──► PG:screener ──► api
screener.db ──► publicar_v2 ──► PG:screener_v2 (sin lector)
```

## 16. Conflictos

| # | Conflicto | Clasificación |
|---|---|---|
| 1 | Dos autoridades de identidad (v0 vs v1) sin bridge | CONFLICTO CONFIRMADO (coexistencia) |
| 2 | Tres hechos económicos sin sincronización (derived.fact/facts/fact_financials) | CONFLICTO CONFIRMADO (coexistencia) |
| 3 | Cuatro+ materializaciones de ratios sin bridge | RIESGO POTENCIAL |
| 4 | `empresas`: 4 escritores incl. DROP legacy (construir_catalogo) | CONFLICTO CONFIRMADO (pisada posible) |
| 5 | `dolares`: 2 escritores INSERT OR REPLACE (último gana) | RIESGO POTENCIAL |
| 6 | `screener`: escritores pipeline (fixes) fuera del orden ASSEMBLE | RIESGO POTENCIAL |
| 7 | PG `screener`: único writer = migrate (TRUNCATE+swap) vs docstring que lo desaconseja | CONFLICTO CONFIRMADO (código↔documentación) |
| 8 | `screener_v2` publicado sin lector; `derived.ratio` producido sin lector | RIESGO POTENCIAL (objetos huérfanos) |
| 9 | demo (sandbox) escribe `ingest_log` en screener.db productiva | CONFLICTO CONFIRMADO (aislamiento roto) |
| 10 | PG producción con 3 publicadores (sync PLAN, migrate, publicar_v2) | RIESGO POTENCIAL |
| 11 | Certificación existe (c11) pero ningún publicador la exige | RIESGO POTENCIAL (barrera incompleta) |

## 17. NO-DETERMINABLE

- Consumidor productivo de `derived.ratio`, `fact_ratios`, `screener_gold`, `screener_v2`, boletín C11 JSON, `screener_export.csv`.
- Escritor productivo actual de PG `screener_hist` (vía copia; corrida exacta no confirmada).
- Autoridad del contenido de `dolares` (fuente BCRA/MEP exacta por fila).
- Alcance runtime de `construir_catalogo` (¿sigue corriendo el DROP de `empresas` en prod?).
- Orden de ejecución relativo demo_txar/41 vs pipeline productivo sobre `ingest_log`.
- Qué filas de `validacion_suite(_edgar)`/`gate_roe`/`o2_*` bloquean publicación (gates reales vs informativos).

## 18. Evidencia

- `[VERIFICADO POR CÓDIGO]`: greps de DDL (migrations/engine 001–034, migrations 001–005, market 012/013/025), INSERT/UPDATE/DROP por tabla en ~90 archivos, columnas de `derived.fact` (s04:426), funciones `_raw_inmutable` + callers (run_update, m2), PLAN de sync (7 tablas), `sincronizar:212` (no toca screener), `publicar_screener_v2:63` (DESTINO screener_v2), materia_prima (setup/20/30/40), `bridge_verificado` (identity_v1:612).
- `[VERIFICADO POR TEST]`: suites del Paso 2 (68 passed) que fijan contratos de control (c11, e2e, f050/f054/f055).
- `[VERIFICADO POR EJECUCIÓN]`: `sqlite_master` de `data/*.db` (screener 70 tablas, byma 10, demo 10–12 c/u), `screener_export.csv` (256 KB), logs, artefactos `outputs/docs`.
- `[NO-DETERMINABLE]`: §17 + celdas marcadas en §3/§14.

## 19. Conteos finales

- Archivo creado: 1 — `docs/review/03_DATA_OWNERSHIP.md`.
- Objetos analizados: 30 filas en matriz central (§14) + 70 tablas físicas en `screener.db` + 10 en `byma_pipeline.db` + 10–12 c/u en `demo*.db` (§2.10–2.11).
- Writers distintos registrados: ~45 componentes (6 familias + motor + market + deploy + demo + byma + carga_externos + materia_prima).
- Consumers distintos registrados: ~30 componentes + `api` + auditoría humana.
- Owners confirmados/probables únicos: 28 filas (§14, estados canónico* + publicado + legacy + EXPORT).
- Owners múltiples / sin owner: 6 filas en estado MÚLTIPLE + 2 sin owner único (`empresas`, `dolares`).
- Conflictos: 11 (5 CONFLICTO CONFIRMADO, 6 RIESGO POTENCIAL) — §16.
- Conceptos duplicados: 4 grupos (identidad, hechos, ratios, publicación) — §5.
- Provenance COMPLETA: 4 objetos (derived.fact, engine.certifications, RAW SEC, RAW CNV); PARCIAL: 7+ (derived.ratio, ratios, screener, silver_norm, market_price_daily, facts/empresas sqlite, market raw).
- NO-DETERMINABLE: 6 ítems (§17) + celdas marcadas en §3/§14.
- Principales hallazgos: §1 (5 bullets).
- Evidencia utilizada: §18.