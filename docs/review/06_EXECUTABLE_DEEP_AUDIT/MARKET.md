# Ficha: MARKET — m1/m2/m4/m5 (+m6/m19/base) · precios · FX

### COMPONENTES núcleo (PG market, guarda F-001 `market_db`)

#### m2_fetch_engine.py (fetch → RAW + price_daily + snapshots)
- IMPORT market_source (YahooSource)/core/db; yfinance vía source. Escribe: `market_raw_runs/files`, `market_fetch_log`, `market_data_quality`, **`market_price_daily`**, `market_snapshots`. Lee: `market_instruments/price_daily/corporate_actions/raw_runs`.
- Idempotencia: no re-fetch si existe raw_run (AND NOT EXISTS). Destructividad: ninguna (append).
- Tests: conftest + test_m23_checkpoint + test_market_matrix (fixtures, MARKET_TEST_*). TEST PASA (suite market).
- PRODUCTIVO PROBABLE. Riesgo R2 (I/O Yahoo; `_raw_inmutable.registrar` compartido con screener).

#### m1_symbol_mapping.py (mapeo venue/ticker → instruments)
- IMPORT f014_venue_ticker + market_db + sqlite3. Lee **`dim_instrument` (SQLite screener.db — cross-familia)**; escribe `market_instruments`, `market_symbol_mappings`.
- Dependencia temporal implícita de pipeline f1. PRODUCTIVO PROBABLE. Riesgo R2 (acoplamiento cross-familia sin contrato).

#### m4_quality.py / m5_golden_case.py (calidad + caso dorado)
- m4: lee raw/price/changes/actions → INSERT `market_data_quality` (C10 market). m5: importa m4, lee todas las market_* → XLSX golden (WRITE_FILE). Tests cubren m4. PRODUCTIVO PROBABLE (m4) / TEST-AUDITORÍA (m5). Riesgo R1.

#### m6_scale.py / m19_apply_schema.py / base (market_db/core/source/f014)
- m6: importa m2 (reuso fetch) + backfill de escala. m19: DDL market.* (INFRA). market_db: guarda de conexión + `es_produccion()` + env MARKET_TEST_*. market_core: hoja. market_source: YahooSource + FixtureSource (tests). f014: derivación venue_ticker (hoja). Riesgo R1 (infra) / R0 (hojas).

### COMPONENTES precio-producto (SQLite, yfinance directo)
- `precios_y_valuacion.py` (sec_edgar): crea `precios` + escribe `ratios.per`; universo + valuación (per/p_book/p_sales/ev_ebitda). Orden obligatorio tras calcular_ratios_base.
- `s3_precios.py` (screener): FASE 3 subset CNV (+FX), mapping manual ADR (`_ADR_XXXX`).
- Ambos escriben `precios` (D2 confirmada); el producto NO consume `market_*`. PRODUCTIVO PROBABLE (vía rebuild). Riesgo R2 (doble writer + mapping manual ADR).

### Separación EMISOR/INSTRUMENTO/SÍMBOLO/PRECIO/FX (auditoría §12)
- EMISOR: `empresas`/`dim_entity` (SQLite) + identity (PG) — tres materializaciones, sin writer múltiple intra-market.
- INSTRUMENTO: `market_instruments` (PG, owner m1) vs `dim_instrument` (SQLite, owner f1) — D2 parcial; m1 puentea (lee SQLite → escribe PG).
- SÍMBOLO: `market_symbol_mappings` + f014 (derivación) — mapeo ≠ entidad (D8 confirmado).
- PRECIO: `market_price_daily` (canónico PG) vs `precios` (producto SQLite) — cadenas separadas (D2 parcial).
- FX: ver abajo. Sin divergencia de fuente intra-market (todo Yahoo vía market_source).

### FX (auditoría §14, solo relevo)
- Productores: `dolares/fetch_dolarito_historico` → `dolarito_cotizaciones` (API autenticada `DOLARITO_AUTH_CLIENT`, histórico desde 2018-10-29); `actualizar_dolares` + `materia_prima/10b` → `dolares` (curada, 2 writers).
- Consumidores: byma/b4 (MEP pareado + estimado con `mezcla_temporal`), validar_suite_edgar, screener/_mep, sync PLAN.
- Representación: fecha/compra/venta/ts_ms (crudo); fecha/tipo/valor/cruce/fuente/es_referencia (curada). bid/ask: compra/venta presentes en crudo. Oficial/CCL: tipos nominales, productor por tipo `[NO-DETERMINABLE]`.
- Conversiones: byma/b4 (ARS→USD con MEP pareado/actual + staleness FRESCO/VIEJO/STALE), s3_precios (+FX subset). Sin motor central (hueco, no duplicación).

### Contratos / Seguridad / Producción
- Contratos market: INPUT/OUTPUT/STATE IMPLEMENTADOS (guarda F-001 + raw_runs); ERROR PARCIAL; PROVENANCE PARCIAL; IDEMPOTENCIA PARCIAL-VERIFICADA (m2 no re-fetch).
- Seguridad: sin secretos (Yahoo sin auth; dolarito por env). R0.
- Producción: sin cron verificado; vía manual + tests + consumo motor. PRODUCTIVO PROBABLE (m1/m2/m4), TEST (m5).
