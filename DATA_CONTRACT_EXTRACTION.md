# DATA_CONTRACT_EXTRACTION.md

**Contratos de datos de extracción — Catalaxia Finance**
v1.0 · 2026-08-22 · Complementa EXTRACTION_SPECIFICATION.md §23.
Formato por dataset: owner · source · PK · columnas · semántica · raw_reference · provenance · writer · reader · validación · cardinalidad esperada.
Regla: **tabla compartida sin contrato = riesgo activo** (EXT-002/005). Los campos `[NO DETERMINADO]` son gaps del contrato a cerrar en fase 2.

Convención de claves: `entity_key` = CUIT (CNV/BYMA-only) o CIK (US/ADR). Prefijo `BYMA-{ticker}` solo clasificación sintética, jamás identidad.

---

## 1. `empresas` (catálogo)

| Campo | Valor |
|---|---|
| Owner | tickets/sec_edgar (construir_catalogo.py) + jobs CNV |
| Source | EDGAR company_tickers.json + CNV AutoComplete |
| PK | `cik` ⚠️ convención mixta vigente: CIK numérico vs CUIT vs BYMA-* (deuda documentada) |
| Columnas clave | cik, ticker, nombre, moneda, sector, grupo (sp500/adr/byma_only) |
| Semántica | catálogo maestro; `grupo` es CLASIFICACIÓN, no identidad |
| Raw ref | company_tickers.json cacheado; HTMLs discovery CNV |
| Provenance | fuente por fila `[NO DETERMINADO hoy]` |
| Writers / readers | escribir: catálogo+jobs · leer: todos los pipelines |
| Validación | ticker duplicado/reciclado → revisión manual (GOLD/CHA) |
| Cardinalidad | 571 activos en screener v5 (553 S&P base histórica); universo CNV descubierto ~555 |

## 2. `facts` (hechos XBRL crudos parseados)

| Campo | Valor |
|---|---|
| Owner | tickets/sec_edgar/scripts (construir_base.py) |
| Source | SEC EDGAR companyfacts |
| PK | `[NO DETERMINADO]` — dedup efectiva por (cik, concepto, end) tras fix EXT-003 |
| Columnas clave | cik, concepto canónico, source_tag, taxonomy, start, end, val, fy, fp, form, filed, unidad, moneda |
| Semántica | hecho financiero tal como vino; flujo(start+end) vs foto(end); dedup SIEMPRE por end |
| Raw ref | data/raw/*.json (fuente de verdad) |
| Provenance presente | form/filed/fy/fp/unidad/moneda · **ausente: accn, decimals, es_restatement** (gaps 1-3) |
| Writers/readers | calcular_ratios_base lee; construir_base escribe |
| Validación | escala de shares antes de per-share; ambas taxonomías buscadas |
| Cardinalidad | ~4.600.000 filas |

## 3. `ratios`

| Campo | Valor |
|---|---|
| Owner | calcular_ratios_base.py + precios_y_valuacion.py (**apareados obligatorios** — EXT-005) |
| Source | derivada de facts + precios |
| PK | `cik` |
| Columnas | ~35 fundamentales + valuación (per, p_book, p_sales, ev_ebitda…) + `flags` texto |
| Semántica | NULL si falta componente (jamás estimar); flags ni_fy/roe_ns/fx/mktcap_rev |
| Provenance | formula_version ausente → gap |
| Validación | post-transform: columna `per` presente y cobertura PER esperada |
| Cardinalidad | 553 empresas |

## 4. `precios`

Owner precios_y_valuacion.py / s3* · source yfinance (+FX) · PK `cik` (+moneda como discriminador — EXT-006) · columnas last_price, market_cap, year_high/low, per/p_book/p_sales/ev_ebitda, staleness_dias · validación guards s9 · regla NULL ante dato dudoso · cardinalidad 571.

## 5. `cnv_estados` / `cnv_estados_v2` / `cnv_estados_norm`

| Campo | Valor |
|---|---|
| Owner | jobs CNV (job5_v2) + capa normalización (s0/f3) |
| Source | CNV aif2 publicview |
| PK norm (post-migr 002) | `(cuit, concepto, period_end, tipo_balance)` — la PK vieja sin tipo_balance mutiló 13,7% docs (EXT-002) |
| Columnas clave | cuit, concepto (7 dígitos), period_end, valor, valor_comparativo, UnidadMedida→factor aplicado, tipo_balance, fecha_presentacion, fecha_reexpresion(vacía al 100%), guid, ticker, cik |
| Semántica | partida contable por documento; vintage NIC-29 = period_end |
| Raw ref | eeff/eeff_html/{guid}.html — **columna raw_ref pendiente (gap 10)** |
| Provenance | guid/fecha_presentación/ticker/cuit presentes · falta parser_version/job_id |
| Writers/readers | job5_v2 + normalizador escriben; ratios_cnv/b-series leen |
| Validación | identidad contable job7 + cross-período (marca, no borra) + INSERT OR IGNORE con log de descartes |
| Cardinalidad | norm **106.421** · v2 **102.323** (post migración 003, 2026-08-22) |

## 6. `ratios_cnv`

Owner s2/f4 · source derivada de cnv_estados_norm · PK (cik, ratio) `[NO DETERMINADO]` · semántica: último período limpio por empresa; CAGR deflactado IPC con flag NOMINAL_sin_deflactar · cardinalidad documentada **72** · validación: cobertura reportada por ratio, no solo conteo.

## 7. `cnv_dividendos` / `cnv_estados_suspect`

- `cnv_dividendos`: PK `guid` · form 339 SIN UnidadMedida (monto total directo) · parser local sobre HTML ya guardado (job6_v2) · payout cash-basis ventana 12m alineada a cierre fiscal.
- `cnv_estados_suspect`: PK (cik, period_end) · filings que violan identidad contable → excluir del screener (21 detectados: 11 purgados, 10 bancos preservados).

## 8. Audit v3 — `data/byma_pipeline.db` (10 tablas)

Snapshot certificado SHA256 → b0–b9. Contratos:

| Tabla | PK/clave | Columnas críticas | Cardinalidad | Notas contrato |
|---|---|---|---|---|
| byma_universo | entity_key | grupo (adr/byma_only), flag SIN_CNV | **73** (17+56) | clasificación en columna propia |
| partidas_norm | (entity_key, concepto, period_end) | valor normalizado, unidad, perimetro, guid | **85.370** | hereda reglas §5 |
| partidas_ratios_cnv | (entity_key, ratio, period_end) | ratio, tipo(A\|P), valor | — | ratios CNV crudos |
| anomalias | check_id como columna ⚠️ | empresa, severidad | 234 filas | columnas = checks, NO columna "tipo" |
| ratios_ttm_byma | (entity_key, concepto) | ttm_desde, ttm_hasta | — | fechas TTM SOLO aquí |
| balances_ttm_byma | (entity_key, partida) | valores TTM | — | sin fechas (están en ratios_ttm) |
| mercado_byma | entity_key | mcap_ars, dif_check, staleness_dias | **56** (ARS×MEP pareado) | dif_check 56/56 OK exigido |
| metricas | (entity_key, metrica) | valor, periodo ⚠️ (no periodo_hasta) | 13×56 | numéricos a veces TEXT → CAST REAL |
| validacion_mat | (empresa, ratio) | status OK/WARN/INFO/FAIL, desvio | 56×13 | FAIL=10 PER_2PATH |
| certificacion | entity_key×ratio | status L5, motivos[] | 487 CERTIFIED / 72 NOT_CERTIFIED | motivos citan check fallado |

Writers: b0–b9 secuenciales. Readers: b8 reporte, b9 traza. Regla: orden de ejecución ES información.

## 9. Entregables exportables

| Artefacto | Contrato |
|---|---|
| data/screener_export.csv | 571 filas × 26 cols; versionado en git; README propio con limitaciones (payout 34/72 cash-basis, CAGR 64%, flags no_significativo) |
| data/export_llm/traza_13ratios.csv | **728 filas = 56×13**; capas L0_fuente_cruda→L1_normalizado→L2_ttm→L3_valor→L4_validacion→L5_status + inputs + anomalias_empresa + staleness_dias; patrón MRR de facto |
| docs/10-auditoria-*.md | reporte vivo generado (b8), nunca editado a mano |

## 10. `download_log` — contrato NUEVO propuesto `[EXT-NEW]`

| Campo | Tipo | Nivel |
|---|---|---|
| cik/entity_key, form_type, filed_at, downloaded_at, http_status, raw_ref, raw_hash, job_id, git_commit | mixto | OBLIGATORIO |

Cierra gaps 6-8 (histórico de descargas pisado por fecha_facts; http no persistido). Append-only, jamás UPDATE.

---
*Regla transversal: todo writer declara rows_inserted/rejected/duplicated con motivos; toda lectura crítica verifica contra la cardinalidad esperada de este documento.*
