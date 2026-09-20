# REFERENCIA DE BASES DE DATOS

## 1 · Los dos PostgreSQL

| puerto | contenedor | qué es | esquemas |
|---|---|---|---|
| **5432** | `catalaxia-db` | **PRODUCCIÓN — nunca escribir** | sólo `public` |
| **5433** | `catalaxia-engine-dev` | desarrollo / fixtures | `engine`, `identity_v1`, `identity`, `fetch_raw`, `parsed`, `derived`, `staging` (F12), `market_*` |

Declarado en `engine/manifest.yaml`. El guard es **EXT-010** en
`engine/config.py`.

Bases observadas en 5433: `catalaxia` (base de trabajo del engine), `cnvmig`
(fixture de la migración CNV), `dbgcopy`, `e2e_final`, `f051_check`.

**Producción no tiene los esquemas del engine.** Ésa es la garantía más fuerte
de aislamiento: aunque un script apuntara ahí, `parsed.facts` no existe.

## 2 · SQLite

| archivo | qué es |
|---|---|
| `data/screener.db` | ~1,5 GB, 66 tablas. **Todos los datos CNV del camino legacy.** |
| `data/log_job5_v2_done.txt` | texto plano, un GUID por línea. El registro de "ya procesado" de `job5` |

## 3 · Esquema `engine` — control de corridas

| tabla | contenido |
|---|---|
| `engine.runs` | `run_id` (hex 32), `mode`, `status` (`RUNNING`/`OK`/`BLOCKED`/`ABORTED`), `git_commit`, `pipeline_version`, `started_at`, `finished_at` |
| `engine.stage_runs` | una fila por **transición**: `stage_id`, `state`, `prev_state`, `gate_status`, `gate_reasons` (JSONB), `report` (JSONB) |
| `engine.checkpoints` | `checkpoint_id` (PK), `stage_id`, `run_id`, `input_hash`, `code_version`, `contract_version`, `artifact_ref`. Índice único `(stage_id, input_hash, code_version, contract_version)` |
| `engine.schema_migrations` | `filename` (PK), `applied_at` |
| `engine.certifications` (F12/C11, migración implícita en el rol; ver `c11_certificar.py`) | `certification_id` (PK), `run_id`, `objeto`, `veredicto` (`CERTIFICADA`/`CERTIFICADA_CON_OBSERVACIONES`/`NEGADA`), `cert_rule`, `cert_hash`, `pipeline_version`, `stages_total/pass/warn/block/insuf`, `evidence` (JSONB), `motivo`, `generado_por`, `generado_at`. Única escritura de C11; un `cert_id` por `run_id`, `ON CONFLICT DO NOTHING` |

## 4 · Esquema `fetch_raw` — descargas

### `fetch_raw.download_log` (SEC)

`log_id`, `run_id`, `stage_run_id`, `stage_id`, `entity_id`, `cik`,
`accession_number`, `form_type`, `filing_date`, `period_of_report`, `source`,
`endpoint`, `request_kind`, `critical`, `raw_path`, `http_status`, `sha256`,
`bytes`, …

Estado observado — **el SHA se puebla**:

| `request_kind` | filas | con SHA | HTTP ≥400 |
|---|---:|---:|---:|
| `DOC_HTM` | 728 | 723 | 5 |
| `FILING_INDEX` | 183 | 156 | 0 |
| `XBRL_OTHER` | 146 | 146 | 0 |
| `XBRL_PACKAGE_ZIP` | 66 | 66 | 0 |
| `FILING_SUMMARY` | 64 | 64 | 0 |
| `XBRL_SCHEMA` | 64 | 64 | 0 |

### `fetch_raw.cnv_download_log` (CNV)

`log_id`, `run_id`, `stage_run_id`, `stage_id`, `entity_key`, `cuit`, `source`,
`artifact_kind`, `artifact_key`, `parent_kind`, `parent_key`, `endpoint`,
`http_method`, `critical`, `http_status`, `content_type`, `bytes`, **`hash_cnv`**,
**`hash_cnv_match`**, `raw_path`, `duplicate_of`, `attempts`, `elapsed_ms`,
`downloaded_at`.

Estado observado — **el SHA NO se puebla**:

| `artifact_kind` | filas | con `hash_cnv` | `match=false` | HTTP ≥400 | máx. `attempts` |
|---|---:|---:|---:|---:|---:|
| `VISOR` | 3.936 | **0** | 0 | 0 | 1 |
| `EMPRESA_PAGE` | 69 | **0** | 0 | 0 | 1 |

**No hay ningún `artifact_kind` de estados financieros.** `SG-01`, `SG-02`.

## 5 · Esquemas `parsed` y `derived`

| tabla | notas |
|---|---|
| `parsed.facts` | `fact_id`, `run_id`, `entity_id` (namespaced), `cik`, `accession_number`, `qname`, `value_numeric`, `unit_ref`, `context_id`, `start_date`, `end_date`, `instant_date`, `period_kind`, `source_hash`, `source_path`, `measurement_date` |
| `parsed.contexts` | `context_id` y su período/dimensiones |
| `parsed.units`, `parsed.concepts`, `parsed.link_relations` | vocabulario |
| `parsed.parse_errors`, `parsed.pre_xbrl_filings` | rechazos SEC |
| `derived.fact` | `fact_key` (PK), `entity_key`, `entity_id`, `qname`, `context_id`, `unit_measure`, `value_numeric`, `source_fact_ids` (array), **`valid_to`**, `measurement_date`, `econ_key` |
| `derived.ratio` | `ratio_key` (PK), `entity_key`, `canonical_id`, `period_end`, `period_window`, `value`, `status`, `motivo`, `publicable`, `formula`, `formula_version`, `inputs` (JSONB), `valid_to` |
| `derived.normalize_conflict` | conflictos de normalización |
| `derived.v_fact_pertenencia`, `derived.v_ocurrencias_por_hecho` | vistas de control |

**`valid_to IS NULL` = fila vigente.** Toda consulta de estado actual lo filtra.

`period_window` se llama así porque **`window` es palabra reservada** en
PostgreSQL.

## 5.1 · Esquema `staging` — publicación C12 (F12, migración `036_staging_schema.sql`)

Creado por la migración 036; el rol `catalaxia_engine` tiene `USAGE,
CREATE` sobre él (antes se creaba a mano en cada instalación).

| tabla | contenido |
|---|---|
| `staging._publications` | bitácora de `publisher.py`: `id`, `ts`, `target`, `run_id`, `input_hash`, `content_hash`, `c10_pass`, `certification_id` |
| `staging.<target>` | snapshot vigente publicado (nombre lógico, definido por `--target`) |
| `staging.<target>__new__<attempt>` | tabla de trabajo transitoria durante un swap; no persiste tras un swap exitoso |

Ningún `<target>` productivo está definido hoy: es la "decisión de
integración" que la ADR de F12 deja diferida (ver
`docs/review/26_F12_ARCHITECTURE_DECISION.md`).

## 6 · Tablas `market_*`

| tabla | filas observadas |
|---|---:|
| `market_price_daily` | 4.799.938 |
| `market_corporate_actions` | 51.917 |
| `market_data_quality` | 8.322 |
| `market_fetch_log` | 601 |
| `market_instruments` | 584 |
| `market_symbol_mappings` | 584 |
| `market_snapshots`, `market_raw_files`, `market_raw_runs`, `market_data_changes` | trazabilidad |

`market_instruments`: `instrument_id`, **`entity_id`** (entero legacy),
`ticker_canonico`, `instrument_type`, `exchange`, `country`, `currency`,
`security_type`, **`ratio_adr`**, `source`, `active`, `first_trade_date`,
`venue_ticker`, `venue_ticker_source`.

**`market_instruments.entity_id` no es el `entity_id` del engine.** Ver
`02A_SEC_EDGAR_ADR_ANNEX.md` §3 (`SG-10`).

## 7 · Tablas CNV en `screener.db`

| tabla | qué es |
|---|---|
| `cnv_filings` | lo que la CNV declara publicado: `cuit`, `ticker`, `norma`, `tipo_balance`, `periodicidad`, `fecha_cierre`, `source_file`. **Sin `docid`**: no se puede unir a un documento |
| `cnv_documents` | discovery: `cuit`, `docid` (GUID), `url`, `source_file` |
| `cnv_estados` | extracción v1 |
| `cnv_estados_v2` | extracción v2. **PK `(cuit, concepto, period_end, fecha_reexpresion, tipo_balance)` — no incluye `accn`** |
| `cnv_estados_norm` | normalizada, con escala aplicada |
| `cnv_estados_suspect` | sospechosos por descuadre |
| `cnv_dividendos`, `cnv_reextract`, `ratios_cnv` | derivados |
| `ingest_log` | 56 filas, con `sha256` — **no cubre los EEFF** |
| `descargas_log` | **0 filas** |

**Ninguna tabla guarda el SHA256 de un documento EEFF de CNV.** `SG-02`.

## 8 · Consultas de diagnóstico

```bash
# cardinalidades generales
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT (SELECT count(*) FROM parsed.facts)  AS parsed_facts,
       (SELECT count(*) FROM derived.fact WHERE valid_to IS NULL) AS derived_vigentes,
       (SELECT count(*) FROM derived.ratio WHERE valid_to IS NULL) AS ratios,
       (SELECT count(*) FROM engine.runs)   AS corridas,
       (SELECT count(*) FROM engine.checkpoints) AS checkpoints"

# digest de un emisor (para comparar entre corridas)
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT count(*), md5(string_agg(fact_key,'|' ORDER BY fact_key))
  FROM derived.fact WHERE entity_id='CIK:0000904851' AND valid_to IS NULL"
```
