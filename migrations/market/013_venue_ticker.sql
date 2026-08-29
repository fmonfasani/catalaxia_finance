-- =====================================================================
-- 013_venue_ticker.sql  ·  cierra F-014 (simbolo del venue vs. del emisor)
-- =====================================================================
-- Se aplica en la base de PRODUCCION (5432), donde viven los market_*.
--
-- F-014: market_instruments.ticker_canonico copia el ticker LOCAL (BYMA)
-- del emisor en la fila del ADR -- para YPF dice 'YPFD' en la fila de NYSE,
-- donde el simbolo real es 'YPF'. Root cause: m1_symbol_mapping.py prefiere
-- dim_entity.ticker_canonico (nivel EMISOR, igual en todas las filas del
-- mismo entity_id) sobre dim_instrument.ticker (nivel INSTRUMENTO, correcto
-- por fila). Detalle y evidencia completa:
-- outputs/docs/fase_market/F014_VENUE_TICKER_CONTRACT.md.
--
-- Esta migracion NO reasigna ticker_canonico (sigue siendo la clave del
-- emisor, ya correcta para eso -- lo confirma la revision independiente).
-- Agrega dos columnas nuevas. El backfill lo hace `m1_symbol_mapping.py`
-- (ya actualizado para F-014), no esta migracion -- una sola fuente de
-- verdad para la logica de derivacion, no SQL duplicado.
--
-- ADITIVO: no borra ni reasigna ninguna columna existente.
-- =====================================================================

ALTER TABLE market_instruments ADD COLUMN IF NOT EXISTS venue_ticker TEXT;
ALTER TABLE market_instruments ADD COLUMN IF NOT EXISTS venue_ticker_source TEXT;

COMMENT ON COLUMN market_instruments.ticker_canonico IS
  'Clave canonica del EMISOR (issuer-level). Identica entre todas las filas '
  'del mismo entity_id. NO es el simbolo de mercado de ESTA fila -- para eso, '
  'venue_ticker. Ver F-014 (outputs/docs/fase_market/F014_VENUE_TICKER_CONTRACT.md).';

COMMENT ON COLUMN market_instruments.venue_ticker IS
  'Simbolo con el que ESTA fila cotiza en `exchange`, segun venue_ticker_source. '
  'NO confundir con market_symbol_mappings.ticker_yahoo (clave de consulta al '
  'proveedor de datos, no simbolo de mercado). Ver F-014.';

COMMENT ON COLUMN market_instruments.venue_ticker_source IS
  'De donde salio venue_ticker. Hoy siempre el literal ''dim_instrument.ticker'' '
  '(sin sufijo) -- ese dato ES legado (data/screener.db), pero no es un registro '
  'de mercado independiente (NYSE symbol directory, EDGAR company tickers). '
  'Ver F-014 seccion 7.';
