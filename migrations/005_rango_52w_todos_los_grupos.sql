-- ============================================================================
-- 005 — El rango de 52 semanas, para los tres grupos y en una sola convención
-- PostgreSQL 16
-- ============================================================================
-- EL HUECO
--
--   Medido el 2026-08-22 sobre las 572 filas de `screener`:
--
--       max_52w_ars_yfinance      46 de 572      sp500 0 · adr 0 · byma 46
--       dif_max_52w_pct           46 de 572      sp500 0 · adr 0 · byma 46
--
--   Es el hueco más grande de la tabla: 526 empresas sin el máximo y el mínimo
--   de 52 semanas. Y el dato ya existe -- `precios.year_high` y `year_low` los
--   tienen para las 672 filas, incluidas las 499 del S&P 500. Nunca se
--   copiaron a `screener` porque s9 se escribió para BYMA.
--
-- POR QUE NO ALCANZA CON LLENAR LAS COLUMNAS QUE YA ESTAN
--
--   `max_52w_ars_yfinance` dice ARS en el nombre. Para el S&P 500 el precio es
--   en dólares, y `max_52w_usd_calc_mep_dolarito` promete una conversión por
--   MEP que ahí no existe: el dólar es la moneda nativa, no una traducción.
--
--   Meter dólares en la columna ARS, o un valor sin MEP en la columna MEP,
--   deja un nombre que miente. El nombre de una columna es documentación que
--   se lee mucho después de que uno se olvidó del caso especial.
--
--   Por eso van dos columnas nuevas, en la MONEDA PROPIA de cada fila -- la que
--   ya declara `screener.currency`. Las columnas ARS/MEP quedan como lo que su
--   nombre dice: el caso BYMA.
--
-- LAS DOS CONVENCIONES DE SIGNO QUE CONVIVIAN
--
--   Medido en la misma tabla, el mismo concepto con signo opuesto:
--
--       max_52w          AAPL  +0,0037    = max/precio − 1
--       dif_max_52w_pct  ALUA  −17,22     = precio/max − 1     (finviz/investing)
--
--   Y `min_52w` usa AUN otra: precio/min − 1. O sea `max_52w` mide "cuánto
--   falta para arriba" y `min_52w` mide "cuánto subió desde abajo": las dos dan
--   positivo, y comparar una contra otra no significa nada.
--
--   Se unifica en la convención de s9, que es la de finviz e investing:
--
--       dif_max_52w_pct = precio/máximo − 1     negativo = por debajo del máximo
--       dif_min_52w_pct = precio/mínimo − 1     positivo = por encima del mínimo
--
--   `max_52w` y `min_52w` NO se tocan: las sirve la API hoy y cambiarles el
--   significado por debajo es peor que dejarlas. Quedan como legado, y lo nuevo
--   se lee de las columnas `dif_*`.
--
-- QUE SE PIERDE
--   Nada. Dos ADD COLUMN nulables, sin default, sin reescritura de tabla.
--
-- MARCHA ATRAS
--   ALTER TABLE screener DROP COLUMN max_52w_abs, DROP COLUMN min_52w_abs;
--   (y volver a poner en NULL dif_max_52w_pct / dif_min_52w_pct donde
--    grupo <> 'byma_only', si se quisiera el estado exacto anterior)
--
-- LOS DATOS NO VIENEN DE ACA
--   Los carga scripts/tickets/screener/s9b_rango_52w.py, que lee `precios` y
--   respeta los guards de s9: una fila con el precio anulado por colisión de
--   ticker o por iliquidez tampoco publica rango.
-- ============================================================================

BEGIN;

ALTER TABLE screener
    -- En la moneda que declara `currency` en esa misma fila. Sin conversión.
    ADD COLUMN IF NOT EXISTS max_52w_abs DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS min_52w_abs DOUBLE PRECISION;

COMMENT ON COLUMN screener.max_52w_abs IS
    'Maximo de 52 semanas en la moneda de `currency`. Sin convertir.';
COMMENT ON COLUMN screener.min_52w_abs IS
    'Minimo de 52 semanas en la moneda de `currency`. Sin convertir.';
COMMENT ON COLUMN screener.dif_max_52w_pct IS
    'precio/maximo - 1. Negativo = por debajo del maximo (convencion finviz).';
COMMENT ON COLUMN screener.dif_min_52w_pct IS
    'precio/minimo - 1. Positivo = por encima del minimo.';
COMMENT ON COLUMN screener.max_52w IS
    'LEGADO: max/precio - 1. Otra convencion. Usar dif_max_52w_pct.';
COMMENT ON COLUMN screener.min_52w IS
    'LEGADO: precio/min - 1. Usar dif_min_52w_pct.';

COMMIT;
