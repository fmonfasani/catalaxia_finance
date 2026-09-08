# 16 — Estado pre-F5 (baseline, solo lectura)

F4 cerrado (STEP_15 PASS, NEXT_PHASE=F5). Solo lectura + este documento.

- Git HEAD `2993918` rama `fix/ttm-ratios-cnv`; F4 agrega (untracked): `issuers.py`, s01/s02/s03/e2e hunks, `test_f4_multiemitter.py`, `15_*`. `[EJECUCIÓN: git]`.
- SEC: YPF (47.930 facts) + KO (45.113 facts) en `derived.fact`; parsed 67.084/90.398; identidad v0+v1 resueltas; C11 CERTIFICADA en runs de ambos. `[EJECUCIÓN]`.
- CNV: motor PG sin corridas DEV (`fetch_raw.cnv_artifact`=0); cadena SQLite productiva (`cnv_estados_v2`=102.323, `empresas`=8.077 en `screener.db`) vía jobs/cron (evidencia 01/04). Estado: motor AUSENTE-dev / jobs PARCIAL. `[EJECUCIÓN]`.
- Market: **cero tablas `market_%` en PG DEV** (DDL nunca aplicado aquí; tests usan DB propia `catalaxia_market_test`). DDL real existe (`market_schema.sql`, 10 tablas, sin DROP/TRUNCATE/DELETE). m1 lee `dim_entity(cik,cuit)` (573 entidades; YPF e72 CIK+CUIT) + `dim_instrument` (YPFD/YPF/YPFLUZ, KO/TKO); m2 acepta `--instruments` + `--limit/--stage`. `[CÓDIGO]`+`[EJECUCIÓN]`.
- Bridges verificados: identity(CIK) ↔ `dim_entity.cik/cuit` ↔ `dim_instrument.entity_id` ↔ (vía m1) `market_instruments` ↔ `market_price_daily`. `[CÓDIGO]`.
- Gap S03 (replace huerfaniza provenance en re-parse vacío): vigente, sin impacto previsto en F5 (sin re-parses). Publisher/C11/C12/legacy/producción intactos.
- Veredicto: PROCEED con flujo SEC+Market (mejor evidencia); CNV documentada sin ejecución nueva.
