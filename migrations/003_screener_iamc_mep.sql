-- ============================================================================
-- 003 — Las 11 columnas IAMC -> MEP que le faltan a `screener` en produccion
-- PostgreSQL 16
-- ============================================================================
--            *** NO APLICADA. NECESITA AUTORIZACION EXPLICITA. ***
--
-- POR QUE ESTA FRENADA
--
--   api/main.py:100  ->  query = "SELECT * FROM screener WHERE 1=1"
--   api/main.py:151  ->  "SELECT * FROM screener WHERE ticker = %s"
--
--   Los dos usan RealDictCursor y devuelven la fila tal cual, sin response_model
--   ni lista de campos. O sea: los campos del JSON SON las columnas de la tabla.
--
--   Medido el 2026-08-21 contra https://api.catalaxia.webshooks.com :
--       /v2/screener?limit=1   ->  45 campos por fila   (screener: 45 columnas)
--
--   Correr este archivo lleva la tabla a 56 columnas y, sin tocar una linea de
--   Python, la API pasa a devolver 56 campos en /v2/screener y en
--   /v2/screener/{ticker}. Eso es cambiar el contrato publico de la API por la
--   puerta de atras. Por eso queda escrito y sin correr.
--
-- QUE SE PIERDE SI SE APLICA
--
--   De datos, nada: son 11 ADD COLUMN, todas nulables, sin default y sin
--   reescritura de tabla (PostgreSQL 11+). 572 filas intactas.
--   Lo que cambia es el contrato de la API, no la data.
--
-- LAS TRES SALIDAS POSIBLES (decision del dueño de la API)
--
--   a) Aplicar esto Y fijar los campos en la API: cambiar los SELECT * por la
--      lista explicita de las 45 columnas de hoy. La tabla queda completa, la
--      respuesta no se mueve, y migrate_sqlite_to_pg.py deja de abortar.
--      Es la unica que arregla las dos cosas a la vez.
--
--   b) Aplicar esto y aceptar 56 campos: la API cambia para todos los que la
--      consumen hoy. Requiere avisar y versionar.
--
--   c) No aplicar: `screener` se queda como esta y la migracion IAMC -> MEP vive
--      solo en `screener_v2`, que ya tiene las 11 columnas y no la sirve nadie.
--      Es el estado actual y no rompe nada.
--
-- OJO CON EL ORDEN
--   No correr esto para "destrabar" migrate_sqlite_to_pg.py. Ese script hace
--   TRUNCATE + INSERT + swap sobre `screener`, y publicar_screener_v2.py ya dejo
--   medido que ese reemplazo vacia 12 columnas que la API sirve hoy (ccl,
--   precio_ars, precio_usd, precio_fuente, precio_dif_iamc, cusip, dr_level,
--   cedear_ratio, cedear_x, div_adr_12m, div_yield_adr, last_div_date). La
--   guarda de filas no lo detecta: entran 572 y salen 572.
--
-- MARCHA ATRAS
--   ALTER TABLE screener
--       DROP COLUMN max_52w_ars_yfinance,          DROP COLUMN min_52w_ars_yfinance,
--       DROP COLUMN max_52w_usd_calc_mep_dolarito, DROP COLUMN min_52w_usd_calc_mep_dolarito,
--       DROP COLUMN dif_max_52w_pct,               DROP COLUMN dif_min_52w_pct,
--       DROP COLUMN precio_usd_calc_mep_dolarito,  DROP COLUMN valor_mep_dolarito,
--       DROP COLUMN fecha_mep_dolarito,            DROP COLUMN pct_ruedas_operadas,
--       DROP COLUMN guard_motivo;
-- ============================================================================

BEGIN;

ALTER TABLE screener
    ADD COLUMN IF NOT EXISTS max_52w_ars_yfinance          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS min_52w_ars_yfinance          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS max_52w_usd_calc_mep_dolarito DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS min_52w_usd_calc_mep_dolarito DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS dif_max_52w_pct               DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS dif_min_52w_pct               DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS precio_usd_calc_mep_dolarito  DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS valor_mep_dolarito            DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS fecha_mep_dolarito            TEXT,
    ADD COLUMN IF NOT EXISTS pct_ruedas_operadas           DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS guard_motivo                  TEXT;

COMMIT;
