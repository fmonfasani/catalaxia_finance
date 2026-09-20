# 02 — Grafo de Dependencias REAL

**Relevamiento global — Paso 2.** Dependencias reales de código, datos, control, ejecución e infraestructura. Cada afirmación lleva `[VERIFICADO POR CÓDIGO]`, `[VERIFICADO POR TEST]`, `[VERIFICADO POR EJECUCIÓN]` o `[NO-DETERMINABLE]`. Cuando documentación y código confligen se muestran ambos, sin resolver el conflicto.

Uso de `docs/review/01_EXECUTION_GRAPH.md` como **contexto** (nunca como sustituto de la inspección). La columna de decisión del censo NO se usó como evidencia de dependencia.

Capa primaria: cada componente se asigna a UNA de las 12 capas, inferida de su función real (no por nombre). Planos: DATOS, CONTROL, EJECUCIÓN, INFRAESTRUCTURA.

Mapa de capas: C1 FUENTES · C2 IDENTIDAD · C3 RAW · C4 PARSED · C5 NORMALIZED · C6 ECONOMIC FACTS · C7 FINANCIAL MODEL · C8 RATIOS · C9 PROVENANCE · C10 VALIDACIÓN · C11 CERTIFICACIÓN · C12 PUBLICACIÓN.

---

## 1. Resumen

- El paquete `engine/` (10 módulos) es el corazón compartido de la familia SEC/CNV-motor: `engine/db.py` y `engine/config.py` son los componentes más reutilizados (30+ consumidores). `engine/report.py` (StageReport) y `engine/states.py` son la base del contrato de control.
- La **familia engine** (s00–s04, c3, c11) escribe en PostgreSQL (`engine.*`, `fetch_raw.*`, `parsed.*`, `derived.*`, `identity.*`); la **familia screener/pipeline** trabaja sobre SQLite `data/screener.db` (env `SCREENER_DB`). Hay cruces reales entre ambas: `m1_symbol_mapping.py` (market) lee `dim_instrument` de `screener.db` (tabla creada por pipeline `f1_identidad`); `construir_base.py` (sec_edgar/scripts) importa helpers de `scripts/tickets/screener` (`_caducidad`, `_ingesta_log`).
- **Sistemas duplicados de hecho** (no resueltos, solo documentados): `engine/identity.py` (identidad v0, tablas `identity.identifiers/entities`, usada por s01/s03) vs `engine/identity_v1.py` (v1, tablas `identity_v1.*`, usada por c3/cnv-validation/backfills) `[VERIFICADO POR CÓDIGO]`. Y `engine/s03.py` sin consumidores de script: `s03_parse_ypf.py` importa `engine.xbrlparse` directamente, no `engine.s03` `[VERIFICADO POR CÓDIGO]`.
- **Ciclos**: 0 ciclos de import detectados a nivel de paquete; el acoplamiento circular potencial vive en el plano DATOS (SQLite `screener.db` compartido por 3 familias con lectura/escritura entrecruzada) — ver sección 12.
- Infraestructura: PostgreSQL (+admin), SQLite, filesystem RAW, cron (VPS), Docker (compose `run pipeline`), `.env`, y servicios externos SEC/EDGAR, CNV, Yahoo/yfinance, INDEC (ver sección 13).

## 2. Dependencias de código

IMPORT directo (estático) verificado por patrón `^\s*(from|import)`.

### 2.1 Paquete `engine/`

| Módulo | Depende de (import) | Tipo |
|---|---|---|
| engine/config.py | `os`, `.env` (load_env) | IMPORT + CONFIG |
| engine/states.py | `enum` (sin deps de proyecto) | hoja |
| engine/report.py | engine.states | IMPORT-DIRECTA |
| engine/db.py | engine.config, engine.states, sqlalchemy, subprocess (migraciones admin) | IMPORT |
| engine/fetch.py | requests; SEC/EDGAR HTTP | IMPORT + API |
| engine/hashout.py | sqlalchemy; DB arbitraria | IMPORT |
| engine/identity.py | engine.config; DB identity.* | IMPORT |
| engine/identity_v1.py | sqlalchemy; DB identity_v1.* | IMPORT |
| engine/s03.py | engine.xbrlparse, engine.fetch | IMPORT |
| engine/xbrlparse.py | lxml (sin deps de proyecto) | hoja |

### 2.2 Familia engine (stages + orquestadores)

| Componente | Imports propios | Clase de dependencia |
|---|---|---|
| s00_smoke.py | engine.db, engine.config, engine.report, engine.states | IMPORT-DIRECTA |
| s01_identity.py | + engine.identity | IMPORT-DIRECTA |
| s02_fetch_ypf.py | engine.db, engine.config, engine.fetch, engine.report, engine.states | IMPORT-DIRECTA |
| s03_parse_ypf.py | engine.db, engine.hashout, engine.config, engine.fetch, engine.identity, engine.report, engine.states, engine.xbrlparse | IMPORT-DIRECTA |
| s04_normalize.py | engine.db, engine.hashout, engine.config, engine.states | IMPORT-DIRECTA |
| e2e_orchestrator.py | engine.db, engine.config | IMPORT + SUBPROCESS (s00..s04 ×5) |
| c11_certificar.py | engine.db, engine.config, engine.report, engine.states | IMPORT-DIRECTA |
| ratio_engine.py | engine.db, engine.config, ratio_defs, ratio_inputs | IMPORT-DIRECTA |
| c3_cnv_fetch.py | engine.cnv.{rawstore,discovery,validate,client}, engine.db, engine.config, engine.report, engine.states | IMPORT-DIRECTA |

Nota: `s03_parse_ypf.py` NO importa `engine/s03.py`; `engine/s03.py` queda como librería sin consumidor `[VERIFICADO POR CÓDIGO]`.

### 2.3 Screener / sec_edgar / CNV

- `run_update.py`: `_raw_inmutable` + `construir_base.descargar_empresa` + yfinance + requests + subprocess `job2/3/4/5_v2` (cwd=`cnv/jobs`) + `__import__` rebuild (`s0..s8,s5`). IMPORT dinámico + SUBPROCESS.
- `run_all.py`: `_run_manifest.escribir` + `__import__` (`construir_base`, `sec_adr_ratios`, `calcular_ratios_base`, `precios_y_valuacion`, `s0..s9`, `s5`) + subprocess jobs `job1..job7` (cwd=`CNV_JOBS`). Ejecución dinámica por **convención de nombre**.
- `run_screener.py`: `__import__` phases `s0/s2/s3/s4/s6/s7/s8/s5`. Idem.
- `construir_base.py` (sec_edgar/scripts): imports `_ingesta_log` y `_caducidad` **del directorio screener** — dependencia cross-directorio real `[VERIFICADO POR CÓDIGO]`.
- Subprocess de CNV jobs corre con `cwd=CNV_JOBS` (paths relativos dentro de jobs) → dependencia de ejecución por directorio `[VERIFICADO POR CÓDIGO]`.

### 2.4 Market

- `m1_symbol_mapping.py` → `f014_venue_ticker` + `market_db` + sqlite3 (+ `psycopg2`).
- `m2_fetch_engine.py` → `market_source` (YahooSource), `market_core`, `market_db`.
- `m5_golden_case.py` → `m4_quality`, `market_core`, `market_db` (módulo compartido de calidad).
- `m6_scale.py` → `m2_fetch_engine` (módulo compartido de fetch), `market_source`.
- `m19_apply_schema.py` → `market_db`.
- Tests `scripts/market/tests/*` → `conftest`, `market_source`, `m2_fetch_engine`, `market_core`, `m6_scale`, `m4_quality`.
- Ninguno importa `engine.*` → market es autónomo del motor salvo `market_db`.

### 2.5 API / Deploy

- `api/main.py`: psycopg2 + FastAPI; **sin imports de engine/**.
- `scripts/deploy/sincronizar_a_produccion.py`: sqlite3 + psycopg2 (COPY). Sin imports de engine/.
- `migrate_sqlite_to_pg.py` documentado como NO elegido (TRUNCATE+swap) `[VERIFICADO POR CÓDIGO]`.

Clasificación: DIRECTA (mayoría), INDIRECTA (`m6→m2`, `m5→m4`), DINÁMICA (`__import__` en run_all/run_screener/run_update-rebuild; subprocess por nombre de módulo), NO-DETERMINABLE (sección 16).

## 3. Dependencias de datos

### 3.1 Mapa de escritura (WRITE_DB / WRITE_FILE) — confirmado en código

PostgreSQL (engine):

| Componente | Escribe |
|---|---|
| s00_smoke | `engine.checkpoints` |
| s01_identity | `identity.identifiers` (+ `engine.checkpoints`) |
| s02_fetch_ypf | `fetch_raw.download_log` + archivos RAW (fs) + `engine.checkpoints` |
| s03_parse_ypf | `parsed.*` (facts/contexts) + `engine.checkpoints` + `engine.stage_runs` |
| s04_normalize | `derived.fact` (ON CONFLICT fact_key), `derived.normalize_conflict`, `engine.stage_runs.report` (JSONB), `engine.checkpoints` |
| c3_cnv_fetch | `fetch_raw.cnv_download_log`, `fetch_raw.cnv_artifact`, `fetch_raw.cnv_presentation` + archivos RAW CNV |
| c11_certificar | `engine.certifications` (SIN otra escritura — INV1) |
| ratio_engine | `derived.ratio` (solo con `--persist`) |
| c3_identity_link / identity_v1_* | `identity_v1.*` |
| db.apply_migrations | `engine.schema_migrations` + DDL (migrations/engine + migrations/market) |

SQLite `screener.db`:

| Componente | Escribe |
|---|---|
| construir_base | `facts`, `empresas` |
| calcular_ratios_base | `ratios` (DROP + recreate) |
| precios_y_valuacion | `ratios` (columna `per`), `precios` (CREATE+INSERT) |
| sec_adr_ratios | `adr_ratios` |
| flags_calidad | `ratios` (flags) |
| s0_normalizar_cnv | `cnv_estados_norm`, `mapa_entidades` |
| s2_ratios_cnv | `ratios_cnv` |
| s3_precios / s3c_refrescar_precios | `precios` (UPDATE) |
| s4_ensamblar | `screener` (DROP+CREATE) |
| s6_ajustes, s7_unificar, s7b..s7d, s8_calidad, s9_guards, s9b | `screener` (UPDATE) |
| cedear_ratios / instrumentos / jpm_adr | `cedear_ratios`, `instrumentos`, `adr_dividendos` + UPDATE screener |
| load_screener_ratios | `screener_ratios`, `screener_ratios_hist` |
| f1_identidad | `dim_entity`, `dim_instrument` |
| f2_reextract_batch | `cnv_reextract` |
| f3_normalizar_cnv / f3b | `fact_financials` (+`_cuarentena`, `entity_validacion`) |
| f4_ratios | `fact_ratios` |
| f5_screener / f6_sec | `screener_gold` |
| fix_mapeo / fix_escala_anchor / fix_escala_mcap / fix_manual | UPDATE `dim_entity`, `cnv_reextract`, `screener`, `eerr_externos`, `ratios_externos`, `market_cap_derivado` |
| _raw_inmutable / _ingesta_log | `ingesta_log` |
| s5_exportar | `data/screener_export.csv` + `.json` (WRITE_FILE) |

PostgreSQL market:

| Componente | Escribe |
|---|---|
| m1_symbol_mapping | `market_instruments`, `market_symbol_mappings` |
| m2_fetch_engine | `market_raw_runs`, `market_raw_files`, `market_fetch_log`, `market_data_quality`, `market_price_daily`, `market_snapshots` |
| m4_quality | `market_data_quality` |
| m19_apply_schema | DDL `market.*` |

PostgreSQL publicada (producción):

| Componente | Escribe |
|---|---|
| sincronizar_a_produccion | `screener` + `screener_hist` (COPY, sin TRUNCATE ciego) |
| migrate_sqlite_to_pg (no usado) | `screener` (TRUNCATE+INSERT+swap) |
| api/main.py | (sin escritura) |

### 3.2 Mapa de lectura (READ_DB / READ_FILE / API)

| Componente | Lee de |
|---|---|
| c11_certificar | `engine.runs`, `engine.stage_runs`, `engine.checkpoints` |
| ratio_engine / ratio_inputs | `derived.fact` (joins sobre `source_fact_ids`), `market_price_daily` (vía `sql_insumos`) |
| c3_cnv_fetch | `engine.stage_runs` (validación de corrida previa) |
| s02_fetch_ypf / s03_parse_ypf | `fetch_raw.download_log` + RAW_ROOT (fs) |
| s03_parse_ypf | `engine.runs`, `engine.stage_runs` (gate), `engine.identity.resolve_por_cik` |
| s04_normalize | `engine.checkpoints` + `engine.runs` (JOIN run_id) |
| e2e_orchestrator | `engine.runs` (historial / reuso de run_id) |
| s01_identity | `identity.identifiers`, `identity.identifier_reviews`, `identity.classifications` |
| calcular_ratios_base | `facts` (WHERE cik=? AND concepto IS NOT NULL) |
| s4_ensamblar / s6..s9 | `screener.db`: `cnv_estados_norm`, `ratios_cnv`, `ratios`, `precios`, `adr_ratios`, `cedear_ratios`, `instrumentos` |
| s5_exportar | `screener` |
| m1_symbol_mapping | `dim_instrument` (**SQLite screener.db**) — dependencia cross-familia `[VERIFICADO POR CÓDIGO]` |
| m2_fetch_engine | `market_instruments`, `market_price_daily`, `market_raw_runs`, `market_corporate_actions` |
| m4_quality | `market_raw_files`, `market_price_daily`, `market_data_changes`, `market_instruments`, `market_corporate_actions` |
| m5_golden_case | `market_*` (raw_runs/raw_files/price_daily/snapshots/fetch_log/data_changes/corporate_actions) |
| api/main.py | PG prod `screener`, `screener_hist`, `silver_norm` |
| sec_adr_ratios | EDGAR 20-F/F-6 (API) |
| precios_y_valuacion | yfinance (API) |
| run_update (--daily) | yfinance 571; (--monthly) INDEC IPC |

## 4. Dependencias entre capas

Lectura adelante (OK) y saltos/mezclas (documentados, NO corregidos).

### 4.1 Cadena canónica SEC/EDGAR (motor)

```
C1 FUENTES(EDGAR) → C2 IDENTIDAD(s01) → C3 RAW(s02) → C4 PARSED(s03) → C5 NORMALIZED(s04)
   → C6 ECONOMIC FACTS(derived.fact) → C8 RATIOS(ratio_engine) → C9 PROVENANCE(checkpoints/stage_runs)
   → C10 VALIDACIÓN(gates en cada stage) → C11 CERTIFICACIÓN(c11) → C12 PUBLICACIÓN(s5/sync/api)
```
`[VERIFICADO POR CÓDIGO]`: los stages s00–s04 ejecutan `StageReport` + gates TRANSITION (`assert_transition`) y escriben `engine.checkpoints`, que es la base de `c11`.

### 4.2 Anomalías / mezclas de capa (solo documentar)

| Componente | Capa primaria asignada | Observación |
|---|---|---|
| s00_smoke | C10 VALIDACIÓN | escribe checkpoints (control) y sirve de bootstrap; mezcla VALIDACIÓN+PROVENANCE |
| s03_parse_ypf | C4 PARSED | además emite gates (C10) y lee identidad (C2) |
| s04_normalize | C5 NORMALIZED | además escribe `engine.stage_runs` (C9) y usa `hashout` (control) |
| c3_cnv_fetch | C3 RAW | además emite gates y manifiesto (C9) |
| run_all / run_update | C7 FINANCIAL MODEL / C8 o C10 | orquesta EXTRACT(3-4)-TRANSFORM(5-6)-ASSEMBLE(7-8)-EXPORT(12) en un solo ejecutor |
| pipeline f-series + fixes | C7/C8 alt | escribe tablas `fact_*`, `screener_gold` y a la vez parchea (`fix_mapeo` UPDATE `screener`) |
| s0/s2/s3/s4 | C4/C8 | `s0` normaliza CNV (C5), `s2` ratios (C8), `s4` ensambla (C7) — cada script mezcla 2 subcapas por convención |

No se detectó ningún caso de capa consumiendo una capa **posterior** dentro de la familia engine (todas respetan el orden lineal). En la familia screener se documenta una restricción temporal: `calcular_ratios_base` (C8) debe correr ANTES de `precios_y_valuacion` porque el primero DROPEA la columna `per` que el segundo recrea — romper el orden destruye datos `[VERIFICADO POR CÓDIGO]`.

## 5. Dependencias de control

Productor → Consumidor de evidencia (control):

| Evidencia | Producida por | Consumida por |
|---|---|---|
| `engine.runs` | e2e_orchestrator (INSERT), db.create_run | s03, s04, c11, e2e_orchestrator (reuso) |
| `engine.stage_runs` | s03, s04 (report JSONB) | c11, c3_cnv_fetch, s03 (gate previo) |
| `engine.checkpoints` | s00, s01, s02, s03, s04, c3_cnv_fetch (ON CONFLICT ux_checkpoints_reuse) | s04 (read), c11 (checkpoint por run) |
| `engine.schema_migrations` | db._apply_migrations | engine.db (todas las conexiones) |
| `engine.certifications` | c11_certificar | test_c11_contract, boletines C12 (JSON) |
| `GateStatus`/`StageState`/`assert_transition` | engine.states | s00–s04, c3, c11 (transiciones) |
| `StageReport` | engine.report | s00–s03, c3, c11 |
| hashes / `hashout` | engine.hashout | s03, s04, release_baseline |
| manifest CNV (`cnv_artifact/download_log`) | c3_cnv_fetch | c3 (validación) y auditoría de raw |
| `ingesta_log` | _ingesta_log / _raw_inmutable / construir_base | auditorías (RAW inmutable) |
| `_run_manifest` | run_all | registro de corridas FASE 4 (control) |
| cron `setup_vps.sh` | infraestructura | run_update (control productivo) |

Cadena de certificación verificada: `gates (C10) → engine.checkpoints (C9) → c11 (C11) → engine.certifications → boletín JSON → publicaciòn (C12)` `[VERIFICADO POR CÓDIGO]`.

## 6. Dependencias de infraestructura

| Recurso | Usado por | Detalle |
|---|---|---|
| PostgreSQL (app + admin) | s00–s04, c3, c11, ratio_engine, market (market_db), api (lectura), sync (escritura) | URL vía `.env` (DB_TYPE/DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD/ENGINE_DB_NAME/CATALAXIA_*) |
| SQLite `data/screener.db` | screener/E2E R family, pipeline f-series, market m1 (lectura), deploy sync (origen) | env `SCREENER_DB` |
| Filesystem RAW | s02/s03 (SEC RAW), c3 (CNV RawStore), cnv/jobs, market raw files | directorio sin librería externa |
| `.env` + `load_env` | engine.config (todo el motor) | merge env `.env` + `os.environ` |
| Cron VPS (`/etc/cron.d/catalaxia`) | run_update daily/monthly/quarterly/annual + backup.sh | `setup_vps.sh:127-151` |
| Docker (compose `run pipeline python .../run_update.py`) | run_update en prod | `setup_vps.sh` |
| SEC/EDGAR API | engine.fetch, s02, construir_base, sec_adr_ratios | companyfacts, submissions, 20-F |
| CNV portal API | engine.cnv.client, cnv/jobs1-8, c3 | descargas CNV |
| Yahoo / yfinance | market_source, m0, precios_y_valuacion, s3_precios, run_update --daily, __precios | precios |
| INDEC | run_update --monthly | IPC |

## 7. SEC / EDGAR

Dependencias del flujo EDGAR y qué comparte con las otras familias:

| Componente | Depende de | Lo comparte con |
|---|---|---|
| engine.fetch | SEC API (requests), RAW_ROOT fs | s02, s03, engine.s03 — solo 2 consumidores |
| engine.xbrlparse | lxml | s03_parse_ypf (directa), engine.s03 (indirecta) |
| engine.identity | engine.config, DB identity.* | s01, s03 |
| engine.identity_v1 | DB identity_v1.* | c3_identity_link, cnv_validation_*, f024_bma, backfills — **separado de identity v0** |
| s04_normalize | derived.fact + hashout | ratio_engine/c11 leen derived.fact; release_baseline usa hashout |
| ratio_engine | ratio_defs + ratio_inputs | ratio_inputs SQL también referenciado implícitamente por e2e_producto/ratio_api |
| construir_base | EDGAR companyfacts + `_ingesta_log`/`_caducidad` (screener/) | screener.db facts/empresas usados por calcular_ratios_base, s-series y flags_calidad |

Dependencia compartida REAL entre motor y screener: **`derived.fact` (PG) NO es consumido por la familia screener**; la familia screener mantiene su propio `facts` en SQLite (construir_base). `[VERIFICADO POR CÓDIGO]` — dos hechos paralelos (PG `derived.fact` vs SQLite `facts`).

## 8. CNV

| Componente | Depende de | Escribe | Lee |
|---|---|---|---|
| c3_cnv_fetch | engine.cnv.client (CNV API), engine.cnv.rawstore | `fetch_raw.cnv_*` (PG) + RAW fs | `engine.stage_runs` |
| job1_universo | CNV API (requests) | universo | — |
| job2_download | CNV API (requests) | RAW fs | universo |
| job3_formtype | RAW fs | — | archivos descargados |
| job4_clasificar | RAW fs | `cnv_estados` (vía job7 DELETE previo)/clasificación | archivos |
| job5_extract_eeff / job5_v2 | CNV portal | `cnv_estados_v2` / eeff | RAW |
| job6_extract_div / job6_v2_reparse_div | portal | `cnv_dividendos` | RAW eeff |
| job7_validar | — | DELETE `cnv_estados`, `cnv_estados_suspect` + validaciones | tablas CNV |
| job8_doc_meta | — | metadatos documentos | RAW |
| run_update --quarterly | subprocess job2→3→4→5_v2 (cwd=CNV_JOBS) | screener.db (via rebuild) | CNV + EDGAR |
| run_all EXTRACT | subprocess job1..job7 (cwd=CNV_JOBS) | screener.db | CNV + EDGAR + yfinance |

Dependencia clave: los jobs CNV usan **paths relativos** (cwd=CNV_JOBS) — `cnv/jobs` no es invocable desde otro directorio sin romper `raw/` y `db` `[VERIFICADO POR CÓDIGO]` (oculta, sección 13).

## 9. Market

Cadena: `m1 (mapeo) → m2 (fetch) → m4 (calidad) → m5 (golden case)` con `m6 (escala/backfill)` y `m19 (schema)`; `market_db` es la guarda única de conexión (F-001).

| Componente | Depende de | Escribe | Lee / API |
|---|---|---|---|
| market_db | psycopg2, env MARKET_TEST_* | conexión PG (guarda) | — |
| market_core | — (hoja) | — | — |
| market_source | yfinance | — | Yahoo API |
| m0_discovery_yahoo | yfinance | — | descubrimiento Yahoo |
| f014_venue_ticker | — (hoja) | — | — |
| m1_symbol_mapping | f014, market_db, sqlite3 | `market_instruments`, `market_symbol_mappings` | `dim_instrument` (**SQLite screener.db — cross-familia**) |
| m2_fetch_engine | market_source, market_core, market_db | `market_raw_runs`, `market_raw_files`, `market_price_daily`, `market_snapshots`, `market_fetch_log`, `market_data_quality` | `market_instruments`, `market_price_daily`, `market_corporate_actions` |
| m4_quality | market_core, market_db | `market_data_quality` | `market_raw_files`, `market_price_daily`, `market_data_changes`, `market_instruments`, `market_corporate_actions` |
| m5_golden_case | m4_quality, market_core, market_db | XLSX (WRITE_FILE) | todas las `market_*` |
| m6_scale | m2_fetch_engine, market_source | escala/backfill precio | `market_raw_runs` |
| m19_apply_schema | market_db | DDL `market.*` | — |
| tests/market/* | conftest, m2, m4, m6, core, source | — | market_*, MARKET_TEST_* |

Dependencia externa e infra: sólo conexión a PG + yfinance. Los módulos market **no dependen de `engine/`** (autonomía) salvo el esquema de tablas.

## 10. Publicación

| Componente | Produce | Consume | DB |
|---|---|---|---|
| s5_exportar | `data/screener_export.csv` + `.json` | `screener` (SQLite) | SQLite |
| sincronizar_a_produccion | `screener` + `screener_hist` en PG prod | `data/screener.db` (SQLite) | origen SQLite → destino PG |
| migrate_sqlite_to_pg (no usado) | `screener` PG (TRUNCATE+swap) | `data/screener.db` | — |
| api/main.py | JSON API (lectura) | `screener`, `screener_hist`, `silver_norm` | PG prod |

Cadena: `s4_build → s5_exportar → (SQLite) → sincronizar_a_produccion → PG prod → api` `[VERIFICADO POR CÓDIGO]`. `silver_norm` es tabla legacy leída por la API; su escritor actual NO se encuentra en los nodos productivos verificados `[NO-DETERMINABLE]`.

## 11. Dependencias transversales

| Módulo | Consumidores (conteo real) | Capa | Plano | Criticidad |
|---|---|---|---|---|
| engine.config | ~30+ (todas las familias del motor) | INFRA | CONFIG | alta |
| engine.db | 30+ (s00–s04, c3, c11, ratio_engine, audit_, f0*_bench, homologacion_*, cnv_*) | C9/CONTROL | CONTROL+INFRA | crítica |
| engine.states | s00–s04, c3, c11, engine.db, engine.report | C10 | CONTROL | alta |
| engine.report | s00–s03, c3, c11 | C9 | CONTROL | media |
| engine.hashout | s03, s04, release_baseline | C9 | CONTROL | media |
| engine.fetch | s02, s03, engine.s03 | C1 | DATOS+EJECUCIÓN | media |
| engine.identity (v0) | s01, s03, identity_v1_backfill_dev (SEC_CATALOG_DIR) | C2 | DATOS | media |
| engine.identity_v1 | c3_identity_link, cnv_validation_*, identity_v1_*, f024_bma, backfill_cik | C2 | DATOS | media |
| engine.xbrlparse | s03_parse_ypf, engine.s03 | C4 | DATOS | media |
| `_ingesta_log` / `_caducidad` (screener/) | construir_base (sec_edgar), run_all | C9/RAW | DATOS | media — **cross-dir**: sec_edgar depende de helpers de screener |
| `_raw_inmutable` | run_update | C9 | DATOS | alta (inmutabilidad RAW) |
| `_run_manifest` | run_all | C9 | CONTROL | media |
| screener.db (SQLite) | screener family + pipeline f-series + market m1 + sync | C6/C7/C8 | DATOS | crítica — **la más compartida** |
| `data/screener_export.csv` | sync + api (indirecto) | C12 | DATOS | alta |

## 12. Dependencias circulares

- **Código (imports)**: 0 ciclos cerrados detectados entre módulos del paquete `engine/` ni entre scripts inspeccionados `[VERIFICADO POR CÓDIGO]`.
- **Datos (acoplamiento circular por DB compartida — potencial)**: SQLite `screener.db` es leída y escrita por las tres familias (pipeline `dim_entity`→ market m1; sec_edgar `facts`→ screener s-series; screener `screener`→ sync). No es un ciclo cerrado de A→B→A pero es un **punto de convergencia de escritura múltiple con riesgo de reescritura cruzada** (p.ej. `construir_catalogo.py` DROPEA `empresas`, tabla que otros crean). `[VERIFICADO POR CÓDIGO]` + `[NO-DETERMINABLE]` para el impacto runtime.
- **Ejecución**: cadenas lineales verificadas; ninguna llama de vuelta. Subprocess de jobs CNV es one-way.
- **Infraestructura**: no hay ciclo (DB←script, script→DB).

## 13. Dependencias ocultas

| # | Ocultamiento | Evidencia |
|---|---|---|
| 1 | Resolución de módulos por **convención de nombre**: `run_all`/`run_screener`/`run_update-rebuild` hacen `__import__(mod_name)` con strings (`s0…s9`, `construir_base`, `calcular_ratios_base`…). Renombrar un archivo rompe el pipeline sin error de import estático. | `[VERIFICADO POR CÓDIGO]` |
| 2 | Incremento de `cwd` en subprocess CNV: jobs se ejecutan con `cwd=CNV_JOBS`; dependencia de directorio no capturada por import estático. | `[VERIFICADO POR CÓDIGO]` `[NO-DETERMINABLE]` el alcance |
| 3 | Paths absolutos hardcodeados a `data/screener.db` en ~10 scripts de diagnóstico (`_check_*`, `_tmp_*`). No herméticos. Solo diagnóstico. | `[VERIFICADO POR CÓDIGO]` |
| 4 | `sys.path.insert(...)` para resolver imports del paquete `engine/` y de `scripts/engine` (ratio_defs/ratio_inputs): dependencia de ubicación-física de archivo. | `[VERIFICADO POR CÓDIGO]` |
| 5 | Variables de entorno (unicas del repo): `API_HOST, API_PORT, CATALAXIA_DB, CATALAXIA_DB_CONTAINER, CATALAXIA_PG_DB, CATALAXIA_PG_USER, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_TYPE, DB_USER, DEMO_HASTA, DEMO_HTML, DOLARITO_AUTH_CLIENT, ENGINE_DB_NAME, ENGINE_E2E_RUN_ID, ENGINE_STATEMENT_TIMEOUT_MS, MARKET_TEST_DB, MARKET_TEST_DB_HOST, MARKET_TEST_DB_PORT, MARKET_TEST_KEEP, S03_SIMULAR_FALLO, SCREENER_DB, SCREENER_DB_ORIGEN, SCREENER_TICKER`. | `[VERIFICADO POR CÓDIGO]` |
| 6 | Migraciones implícitas en dos dirs: `migrations/engine` + `migrations/market` aplicadas desde engine/db.py (F-051: market no las aplicaba antes). | `[VERIFICADO POR CÓDIGO]` |
| 7 | `.env` cargado por `engine.config.load_env`; se hace merge con `os.environ`. | `[VERIFICADO POR CÓDIGO]` |
| 8 | Cron y Docker declaran la ejecución de `run_update.py` y `backup.sh` — no visibles en el árbol estático de scripts. | `[VERIFICADO POR CÓDIGO]` (setup_vps.sh:127-151) |
| 9 | `silver_norm` (PG prod) leída por api — tabla legacy, escritor actual `[NO-DETERMINABLE]`. | `[NO-DETERMINABLE]` |
| 10 | `SCREENER_DB_ORIGEN` + `SCREENER_DB` + `SCREENER_TICKER`: mecanismos de redirección de DB/emisor usados por f-series para no tocar producción. | `[VERIFICADO POR CÓDIGO]` |

## 14. Matriz de dependencias

Incluye las aristas principales por familia. Capas: C1..C12 (ver mapa inicial). Planos: DATOS/CONTROL/EJECUCIÓN/INFRA.

### 14.1 Motor / engine

| Componente | Depende de | Tipo | Capa orig | Capa dest | Plano | Evidencia |
|---|---|---|---|---|---|---|
| engine/config.py | `.env`, `os.environ` | CONFIG+ENV | INFRA | INFRA | INFRA | [CÓDIGO] |
| engine/db.py | engine.config, engine.states | IMPORT | INFRA | INFRA | INFRA | [CÓDIGO] |
| engine/db.py | migrations/engine, migrations/market | READ_FILE | INFRA | INFRA | INFRA | [CÓDIGO] |
| engine/states.py | — | hoja | C10 | — | CONTROL | [CÓDIGO] |
| engine/report.py | engine.states | IMPORT | C9 | C10 | CONTROL | [CÓDIGO] |
| engine/fetch.py | SEC/EDGAR (requests) | API | C1 | C1 | EJECUCIÓN | [CÓDIGO] |
| engine/hashout.py | DB arbitraria (SELECT) | READ_DB | C9 | C9 | CONTROL | [CÓDIGO] |
| engine/identity.py | DB identity.identifiers | READ/WRITE_DB | C2 | C2 | DATOS | [CÓDIGO] |
| engine/identity_v1.py | DB identity_v1.* | READ/WRITE_DB | C2 | C2 | DATOS | [CÓDIGO] |
| engine/s03.py | engine.xbrlparse, engine.fetch | IMPORT | C4 | C4 | EJECUCIÓN | [CÓDIGO] |
| engine/xbrlparse.py | lxml | IMPORT | C4 | — | EJECUCIÓN | [CÓDIGO] |
| s00_smoke | engine.db/config/report/states | IMPORT | C10 | INFRA | EJECUCIÓN | [CÓDIGO] |
| s00_smoke | engine.checkpoints | WRITE_DB | C10 | C9 | CONTROL | [CÓDIGO] |
| s01_identity | engine.identity | IMPORT | C2 | C2 | EJECUCIÓN | [CÓDIGO] |
| s01_identity | identity.identifiers | WRITE_DB | C2 | C2 | DATOS | [CÓDIGO] |
| s01_identity | identity.identifier_reviews/classifications | READ_DB | C2 | C2 | DATOS | [CÓDIGO] |
| s02_fetch_ypf | engine.fetch + SEC API | IMPORT+API | C3 | C1 | EJECUCIÓN | [CÓDIGO] |
| s02_fetch_ypf | fetch_raw.download_log | WRITE_DB | C3 | C3 | DATOS | [CÓDIGO] |
| s02_fetch_ypf | RAW fs | WRITE_FILE | C3 | C3 | DATOS | [CÓDIGO] |
| s03_parse_ypf | engine.xbrlparse/hashout/fetch/identity | IMPORT | C4 | C4 | EJECUCIÓN | [CÓDIGO] |
| s03_parse_ypf | parsed.* | WRITE_DB | C4 | C4 | DATOS | [CÓDIGO] |
| s03_parse_ypf | fetch_raw.download_log | READ_DB | C4 | C3 | DATOS | [CÓDIGO] |
| s04_normalize | engine.hashout | IMPORT | C5 | C9 | EJECUCIÓN | [CÓDIGO] |
| s04_normalize | derived.fact | WRITE_DB | C5 | C6 | DATOS | [CÓDIGO] |
| s04_normalize | engine.stage_runs (report) | WRITE_DB | C5 | C9 | CONTROL | [CÓDIGO] |
| e2e_orchestrator | s00..s04 (subprocess ×5) | SUBPROCESS | C10 | C3..C5 | EJECUCIÓN | [CÓDIGO]+[TEST] |
| e2e_orchestrator | engine.runs | WRITE_DB+READ_DB | C10 | C9 | CONTROL | [CÓDIGO] |
| c11_certificar | engine.runs/stage_runs/checkpoints | READ_DB | C11 | C9 | CONTROL | [CÓDIGO] |
| c11_certificar | engine.certifications | WRITE_DB | C11 | C11 | CONTROL | [CÓDIGO]+[TEST] |
| ratio_engine | ratio_inputs.sql_insumos | IMPORT | C8 | C6 | EJECUCIÓN | [CÓDIGO] |
| ratio_engine | derived.fact | READ_DB | C8 | C6 | DATOS | [CÓDIGO] |
| ratio_engine | derived.ratio (--persist) | WRITE_DB | C8 | C8 | DATOS | [CÓDIGO] |
| c3_cnv_fetch | engine.cnv.client (CNV API) | IMPORT+API | C3 | C1 | EJECUCIÓN | [CÓDIGO] |
| c3_cnv_fetch | fetch_raw.cnv_artifact/presentation/download_log | WRITE_DB | C3 | C3 | DATOS | [CÓDIGO] |
| c3_cnv_fetch | engine.stage_runs | READ_DB | C3 | C9 | CONTROL | [CÓDIGO] |

### 14.2 Screener / sec_edgar / CNV

| Componente | Depende de | Tipo | Capa orig | Capa dest | Plano | Evidencia |
|---|---|---|---|---|---|---|
| construir_base | `_ingesta_log`, `_caducidad` (screener/) | IMPORT | C5 | C9 | DATOS | [CÓDIGO] |
| construir_base | EDGAR companyfacts | API | C5 | C1 | EJECUCIÓN | [CÓDIGO] |
| construir_base | facts, empresas | WRITE_DB | C5 | C6 | DATOS | [CÓDIGO] |
| calcular_ratios_base | facts | READ_DB | C8 | C6 | DATOS | [CÓDIGO] |
| calcular_ratios_base | ratios (DROP+create, col `per`) | WRITE_DB | C8 | C8 | DATOS | [CÓDIGO] |
| precios_y_valuacion | yfinance | API | C8 | C1 | EJECUCIÓN | [CÓDIGO] |
| precios_y_valuacion | ratios (col `per`), precios | WRITE_DB | C8 | C8 | DATOS | [CÓDIGO] |
| calcular_ratios_base → precios_y_valuacion | orden de ejecución obligatorio | EXECUTION_ORDER | C8 | C8 | EJECUCIÓN | [CÓDIGO] |
| sec_adr_ratios | EDGAR 20-F/F-6 | API | C8 | C1 | EJECUCIÓN | [CÓDIGO] |
| sec_adr_ratios | adr_ratios | WRITE_DB | C8 | C8 | DATOS | [CÓDIGO] |
| s0_normalizar_cnv | cnv_estados_norm, mapa_entidades | WRITE_DB | C5 | C5 | DATOS | [CÓDIGO] |
| s2_ratios_cnv | ratios_cnv | WRITE_DB | C8 | C8 | DATOS | [CÓDIGO] |
| s3_precios | yfinance | API | C8 | C1 | EJECUCIÓN | [CÓDIGO] |
| s3_precios | precios | WRITE_DB | C8 | C8 | DATOS | [CÓDIGO] |
| s4_ensamblar | screener (DROP+CREATE) | WRITE_DB | C7 | C7 | DATOS | [CÓDIGO] |
| s4_ensamblar | ratios_cnv/ratios/precios | READ_DB | C7 | C8 | DATOS | [CÓDIGO] |
| s6_ajustes | adr_ratios | READ_DB | C7 | C8 | DATOS | [CÓDIGO] |
| s6_ajustes..s9b | screener | WRITE_DB | C7 | C7 | DATOS | [CÓDIGO] |
| s5_exportar | screener | READ_DB | C12 | C7 | DATOS | [CÓDIGO] |
| s5_exportar | screener_export.csv/.json | WRITE_FILE | C12 | C12 | DATOS | [CÓDIGO]+[EJECUCIÓN] |
| run_update | construir_base (IMPORT) + yfinance + requests | IMPORT+API | C7 | C5 | EJECUCIÓN | [CÓDIGO] |
| run_update | _raw_inmutable | IMPORT | C7 | C9 | CONTROL | [CÓDIGO] |
| run_update | subprocess job2→3→4→5_v2 | SUBPROCESS | C7 | C3 | EJECUCIÓN | [CÓDIGO] |
| run_update | __import__ rebuild s0..s8,s5 | CALL-DINÁMICO | C7 | C5 | EJECUCIÓN | [CÓDIGO] |
| run_update | screener.db + upd_YYYYMMDD.log | WRITE_DB+WRITE_FILE | C7 | C7 | DATOS | [CÓDIGO]+[EJECUCIÓN] |
| run_all | _run_manifest | IMPORT | C7 | C9 | CONTROL | [CÓDIGO] |
| run_all | subprocess jobs job1..job7 | SUBPROCESS | C7 | C3 | EJECUCIÓN | [CÓDIGO] |
| run_all | __import__ construir_base/sec_adr_ratios/calcular_ratios_base/precios_y_valuacion/s0..s9/s5 | CALL-DINÁMICO | C7 | C8 | EJECUCIÓN | [CÓDIGO] |
| run_screener | __import__ s0/s2/s3/s4/s6/s7/s8/s5 | CALL-DINÁMICO | C7 | C8 | EJECUCIÓN | [CÓDIGO] |
| job2_download..job5_extract | CNV portal (requests) | API | C3 | C1 | EJECUCIÓN | [CÓDIGO] |
| job7_validar | cnv_estados, cnv_estados_suspect | WRITE_DB | C10 | C4 | DATOS | [CÓDIGO] |
| job6_v2_reparse_div | cnv_dividendos | WRITE_DB | C4 | C4 | DATOS | [CÓDIGO] |

### 14.3 Market / Publicación

| Componente | Depende de | Tipo | Capa orig | Capa dest | Plano | Evidencia |
|---|---|---|---|---|---|---|
| market_db | psycopg2, MARKET_TEST_* | IMPORT+ENV | INFRA | INFRA | INFRA | [CÓDIGO] |
| market_source | yfinance | API | C1 | C1 | EJECUCIÓN | [CÓDIGO] |
| m1_symbol_mapping | f014_venue_ticker, market_db, sqlite3 | IMPORT | C3 | C2 | EJECUCIÓN | [CÓDIGO] |
| m1_symbol_mapping | dim_instrument (SQLite screener.db) | READ_DB | C3 | C2 | DATOS | [CÓDIGO] — cross-familia |
| m1_symbol_mapping | market_instruments, market_symbol_mappings | WRITE_DB | C3 | C3 | DATOS | [CÓDIGO] |
| m2_fetch_engine | market_source/core/db | IMPORT | C3 | C1 | EJECUCIÓN | [CÓDIGO] |
| m2_fetch_engine | market_price_daily, market_snapshots, market_raw_* | WRITE_DB | C3 | C6 | DATOS | [CÓDIGO] |
| m4_quality | market_core/db | IMPORT | C10 | INFRA | EJECUCIÓN | [CÓDIGO] |
| m4_quality | market_data_quality | WRITE_DB | C10 | C10 | DATOS | [CÓDIGO] |
| m5_golden_case | m4_quality | IMPORT | C10 | C10 | EJECUCIÓN | [CÓDIGO] |
| m6_scale | m2_fetch_engine | IMPORT | C6 | C3 | EJECUCIÓN | [CÓDIGO] |
| m19_apply_schema | market_db | IMPORT | INFRA | INFRA | INFRA | [CÓDIGO] |
| tests/market | conftest, m2/m4/m6/source/core | IMPORT | C10 | C3 | EJECUCIÓN | [TEST] |
| s5_exportar | screener (SQLite) | READ_DB | C12 | C7 | DATOS | [CÓDIGO] |
| sincronizar_a_produccion | screener.db (origen) | READ_DB | C12 | C12 | DATOS | [CÓDIGO] |
| sincronizar_a_produccion | PG prod screener/screener_hist | WRITE_DB | C12 | C12 | DATOS | [CÓDIGO] |
| migrate_sqlite_to_pg (no usado) | screener (TRUNCATE+swap) | WRITE_DB | C12 | C12 | DATOS | [CÓDIGO] |
| api/main.py | screener/screener_hist/silver_norm | READ_DB | C12 | C7 | DATOS | [CÓDIGO] |

## 15. Grafo

### 15.A Código (imports)

```
engine.config ← engine.db ← s00..s04, c3, c11, ratio_engine, audits, f0*_bench, homologacion_*, cnv_*, identity_*
engine.states ← engine.report ← s00..s03, c3, c11
engine.fetch ← s02, s03, engine.s03 ;  engine.xbrlparse ← s03_parse_ypf, engine.s03
engine.identity ← s01, s03 ;  engine.identity_v1 ← c3_identity_link, cnv_validation_*, f024_bma, backfills
market_core/market_db/market_source ← m1, m2, m4, m5, m6, m19, tests/market
screener(_helpers) ← construir_base (sec_edgar)   [cross-dir]
```

### 15.B Datos (DB/tablas)

```
[screener.db SQLite]  ← construir_base(facts,empresas,ingesta_log) ; sec_adr_ratios(adr_ratios) ; calcular_ratios_base(ratios)
   ← precios_y_valuacion(ratios.per,precios) ; s0(cnv_estados_norm,mapa_entidades) ; s2(ratios_cnv) ; s3(precios)
   ← s4(screener) ; s6..s9b(screener) ; pipeline f1..f5/fixes(dim_entity,dim_instrument,cnv_reextract,fact_*,screener_gold)
   → s5 → screener_export.csv → sincronizar_a_produccion → PG prod screener/screener_hist → api
   ← market m1 (lee dim_instrument)
[PG engine]  engine.runs ← e2e_orchestrator ; engine.stage_runs ← s03,s04 ; engine.checkpoints ← s00..s04,c3
   parsed.* ← s03 ; derived.fact ← s04 → ratio_engine, c11 ; derived.ratio ← ratio_engine
   fetch_raw.download_log ← s02 ; fetch_raw.cnv_* ← c3 ; identity.* ← s01 ; identity_v1.* ← c3_identity_link/backfills
   engine.certifications ← c11
[PG market]  market_* ← m1,m2,m4,m5,m6
```

### 15.C Control

```
+------> engine.runs -------------> engine.stage_runs/[checkpoints] ---+------> c11 ---> engine.certifications --> boletín JSON
|        (e2e_orchestrator INSERT)  (s03/s04 WRITE; c3/s04 READ)      |      (READ ok; C10 gates)          (WRITE única)
+-------- Sovereign gates: StageReport/assert_transition en s00..s04, c3, c11
+-------- hashout → s03/s04/release_baseline ; _raw_inmutable → run_update ; _run_manifest → run_all ; cron → run_update
```

### 15.D Infraestructura

```
.env ──► engine.config ──► engine.db ──► PostgreSQL (app+admin) + migrations/engine + migrations/market
SCREENER_DB ──► screener/pipeline/m1/sync ──► data/screener.db
[EDGAR/CNV/Yahoo/INDEC APIs] ──► engine.fetch / requests / yfinance
[cron VPS + docker compose run pipeline] ──► run_update.py + backup.sh
RAW fs ──► s02/s03/c3/jobs ; logs upd_*.log ──► run_update
```

## 16. Componentes no determinables

Componentes con `__main__`/entrypoint pero sin caller/consumer/input/output demostrable (NO clasificados como muertos; estado `[NO-DETERMINABLE]`):

| Componente | Observación |
|---|---|
| engine/s03.py | sin import desde scripts (s03_parse_ypf importa engine.xbrlparse directo) |
| engine/cnv/rawstore + discovery/validate/client | consumidos ÚNICAMENTE por c3 (bien acotado) — detalle de paths `[NO-DETERMINABLE]` |
| scripts/engine/fundamentals_universo.py | docstring "conduce S02→S03→S04 por emisor"; targets de subprocess no confirmados |
| scripts/engine/cnv_pilot2.py, homologacion_slice.py, release_baseline.py, cnv_validation_*, identity_v1_pilot/dryrun/* | pilotos/auditorías; invocación productiva `[NO-DETERMINABLE]` |
| scripts/tickets/screener/crear_pdf_guia.py, actualizar_seguimiento.py, gen_screener_html.py | utilitarios con entrypoint sin orquestador |
| scripts/tickets/cnv/scripts/{01..07}* (auditorías autocomplete/empresa, descargar_html, etc.) | serie CNV v1; integración con jobs v2 `[NO-DETERMINABLE]` |
| `silver_norm` (PG prod) | leída por api; escritor productivo `[NO-DETERMINABLE]` |
| scripts/docgen/build.py + cli.py | generadores de documentación; invocación manual |
| `data/logs/runs` (0 manifests) | run-manifest registrado por diseño pero sin artefactos `[EJECUCIÓN]` |

## 17. Evidencia

- `[VERIFICADO POR CÓDIGO]`: lecturas estáticas de engine package, s00–s04, e2e_orchestrator, c11, ratio_engine, c3, sec_edgar/scripts, screener family (run_update/run_all/run_screener/s0–s9/s5 + helpers), pipeline f-series, market (m1/m2/m4/m5/m6/m19/market_db/market_core/market_source/f014), api/main.py, deploy/sincronizar, setup_vps.sh:cron, y greps de imports/SUBPROCESS/`__import__`/SQL/tablas/env-vars/sys.path.
- `[VERIFICADO POR TEST]`: test_e2e_orchestrator + test_c11_contract (26 passed); test_f050/f054/f055 (42 passed, 2 skipped, 1 xfail); 32 archivos `test_*.py` en repo; tests/market (conftest/market_matrix/m23_checkpoint/f014).
- `[VERIFICADO POR EJECUCIÓN]`: `data/screener_export.csv` (256 KB, 07/10/2026) + `.json`; logs `data/logs/upd_*.log` (32); `outputs/docs/fase_*`; `outputs/runbook/RUNBOOK_READINESS_MATRIX.csv`; docs/review/R2-R4_{EVIDENCIA,CERTIFICACION}.md; censo (índice de existencia, sin valor decisorio).
- `[NO-DETERMINABLE]`: ver secciones 13 y 16.

## 18. Conteos finales

- Archivos creados: 1 — `docs/review/02_DEPENDENCY_GRAPH.md` (+ `docs/review/01_EXECUTION_GRAPH.md` usado como contexto).
- Componentes analizados: 70 (paquete engine 10 + stages/orquestadores 9 + screener/sec_edgar/cnv 24 + market 10 + pipeline 8 + api/deploy/tests 9).
- Filas (aristas) en la matriz de la sección 14: **85**.

| Tipo | Cantidad |
|---|---|
| WRITE_DB | 27 |
| IMPORT | 23 |
| READ_DB | 15 |
| API | 10 |
| SUBPROCESS | 3 |
| WRITE_FILE | 3 |
| CALL-DINÁMICO (`__import__`) | 3 |
| ENV | 2 |
| CONFIG | 1 |
| EXECUTION_ORDER | 1 |
| READ_FILE | 1 |
| CHECKPOINT/PROVENANCE/CONTRACT (tipo) | 0 (cubiertas vía READ_DB/WRITE_DB sobre `engine.*` en sección 5) |
| **Total aristas (tokens)** | **89** |

- Dependencias circulares: 0 ciclos en código; 1 candidato de acoplamiento circular en plano DATOS (screener.db multi-familia).
- Dependencias ocultas: 10 (sección 13).
- NO-DETERMINABLE: 11 componentes (sección 16) + 2 aristas señaladas (sección 13, ítems 2 y 9).
- Evidencia: `[CÓDIGO]` mayoritaria con 89 aristas de matriz verificadas; `[TEST]` en 4 conjuntos; `[EJECUCIÓN]` en 5 conjuntos; `[NO-DETERMINABLE]` documentado sin resolución de conflictos.