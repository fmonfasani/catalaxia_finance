# 16 — F5 Multifuente SEC+Market (CNV documentada)

E2E cross-source mínimo con mejor evidencia: **SEC issuer + Market instrument/price** (CNV documentada sin ejecución nueva: motor PG 0 artefactos; SQLite productiva por cron). Solo DEV Docker local (ver hallazgo infra). Sin fusión de cadenas. Evidencia `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`.

## Mapa de cadenas (PASO 1)

SEC (EXISTENTE, F4): EDGAR→RAW fs+download_log→parsed.*→derived.fact→gates→c11→staging. CNV-motor (AUSENTE-dev: 0 artefactos; código+runbook existen) / CNV-jobs (PARCIAL: SQLite `cnv_estados_v2`=102.323 vía cron). Market (PARCIAL→operativa en F5: DDL aplicado en DEV, m1 584 instrumentos, m2 Yahoo 3/3 con 31.276 precios; quality/golden: m4 no corrido en DEV — PARCIAL). Etapas inexistentes marcadas, no inventadas.

## Ownership e issuer/instrument/price (PASO 2)

Issuer = `dim_entity(cik,cuit)` + identity v0/v1 (CIK) · Instrument = `market_instruments` (PG, owner m1) / `dim_instrument` (SQLite, owner f1) · Price = `market_price_daily` (PG motor) / `precios` (SQLite producto) · Corporate Action = `market_corporate_actions` + columnas dividends/stock_splits en price_daily. Tablas canónicas y bridges en §matriz. Verificado: `market_instruments` SIN `cik`, `market_price_daily` SIN `cik/entity`, `derived.fact` SIN instrument/close, `dim_instrument` SIN cik, `dim_entity` CON cik+cuit `[TEST+E]`.

## Bridges (PASO 3)

identity(CIK) → `dim_entity.cik`/`cuit` → `dim_instrument.entity_id` → m1 → `market_instruments(ticker_canonico)` → `market_symbol_mappings` → `market_price_daily`. CIK/CUIT/LEI: bridges LEI-level solo intra-v1 (`bridge_verificado` CIK↔LEI); ISIN/ticker no usados como identidad (venue_ticker es mapeo, no entidad — dual-listing YPFD/BUE+YPF vs YPFD/NYSE+YPF lo demuestra). Sin equivalencia por nombre. Listas: VERIFICADO (cadena YPF/KO extremo a extremo). `[TEST G]`+`[EJECUCIÓN]`.

## Provenance cross-source (PASO 4, sin fusionar)

SEC: run_id/stage_runs/checkpoints/`source_fact_ids`/hashes/C11. Market: `source_run_id`/`source_hash` por precio + raw_runs/files + fetch_log. Join demostrado YPF/KO (facts 47.930/45.113 + closes con fecha/moneda/run) con columnas de provenance de ambos lados en una consulta. `[EJECUCIÓN]`.

## Integración mínima (PASO 5): SEC + Market

Elegida por evidencia (ambas ejecutables en DEV con APIs alcanzables; CNV-portal exigiría inventar extracciones). Alcance: m19(DDL)→m1(mapeo)→m2(precios YPF/YPFD.BA/KO)→join con facts+provenance. Sin tocar SEC/CNV.

## Hallazgo infra F5 (destino market)

`market_db.destino()` mostraba 5433 pero `inet_server_port()`=5432: localhost:5433 reenvía al PG Docker :5432 (172.17.0.2). Investigación read-only con STOP intermedio según protocolo: mismo backend verificado (1141 runs + market visibles en UNA conexión como rol app). Cero contacto productivo (host localhost, allow_prod_write=False, sin SSH, DB con runs DEV). Consecuencia: invisibilidad inicial = gap de privilegios (tablas owner `catalaxia`, rol engine sin grants) → GRANT SELECT DEV-only documentado (precedente staging). F-001 funcionó (bloqueó 5432 sin DB_PORT). `[EJECUCIÓN]`.

## Gap S03 (PASO 8)

Sin impacto en F5 (cero re-parses; market no toca parsed). Permanece GAP R7.x (diseño 016: replace por entidad huerfaniza provenance ante 0 filings; mitigación futura: no reemplazar si 0 filings).

## No-touch (PASO 9)

Producción 0 (solo Docker-DEV) · RAW append-only (sin unlink en stages/market) · V1 1+1 entidades (sin backfills) · C10/C11/C12/publisher código intactos · legacy/CNV/Market código intacto (solo ejecución m19/m1/m2 append-only, verificado sin DROP/DELETE/TRUNCATE) · +certificaciones DEV solo de fixtures de regresión autorizada. STOP no requerido. `[CÓDIGO]`+`[EJECUCIÓN]`.

## Matrices (§10)

FUENTE|CAPA|COMPONENTE|OWNER|INPUT|OUTPUT|PROVENANCE|GATE: SEC C1-C6 s00-s04 (motor/CHECKPOINTED) · CNV C1-C4 jobs (cron/log) + motor C3 (código) · Market C1-C6 m0/m1/m2 (raw_runs/fetch_log) + C10 m4 (código) · bridges (m1+f014+dim) · C11 c11/40 · C12 s5/sync/publisher+gate.
INTEGRACIÓN|EVIDENCIA|RESULTADO: SEC↔Market vía bridge auditado = VERIFICADO (join + 14/14 tests); SEC↔CNV vía dim_entity.cik/cuit = VERIFICADO estructural, sin ejecución conjunta (ND runtime); Market→ratio_engine = VERIFICADO por código (Paso 4), no re-ejecutado.

## Regresión y fallos preexistentes

F5 14/14 + suites históricas verdes (c11/e2e/f050/f054/f055/s03/s04/f2/f3/f4). Suite completa: 867 passed; 32 fallos **PREEXISTENTES** demostrados (no de F5): `derived.ratio` vacía (ratio×19), C3 jamás corrido (f040×3), universo stale autodeclarado (cnv_authority), links CNV ausentes (identity_link), lote market específico ausente (f038; pre-F5 ni existían las tablas), universo assertions de rama (f041), fragilidad de orden (r3 pasa aislado). Ningún fallo en archivos tocados por F4/F5; ningún fallo por ausencia-convertida (todos son ausencia-de-prerrequisito, indemostrable como regresión).
