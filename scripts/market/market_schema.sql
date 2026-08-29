-- ============================================================
-- MARKET DATA SCHEMA -- Catalaxia fase Market Data (M19)
-- PostgreSQL 16+. Idempotente (IF NOT EXISTS).
-- Convenciones:
--   * identidad = instrument_id / entity_id (NUNCA ticker Yahoo)
--   * precios NUMERIC(18,8) (ARS grandes y centavos USD conviven)
--   * hashes SHA256 hex -> CHAR(64)
--   * timestamps en UTC (TIMESTAMPTZ)
--   * RAW vive en disco (data/raw/market/) y se registra aqui por hash
-- ============================================================

-- Instrumentos del universo market data -----------------------
CREATE TABLE IF NOT EXISTS market_instruments (
    instrument_id      TEXT PRIMARY KEY,
    entity_id          TEXT NOT NULL,
    ticker_canonico    TEXT NOT NULL,
    instrument_type    TEXT NOT NULL CHECK (instrument_type IN ('ADR','LOCAL','US','OTHER')),
    exchange           TEXT,
    country            TEXT,
    currency           TEXT NOT NULL,
    security_type      TEXT,
    ratio_adr          NUMERIC(14,8),
    source             TEXT NOT NULL DEFAULT 'dim_instrument',
    active             BOOLEAN NOT NULL DEFAULT TRUE,
    first_trade_date   DATE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- F-014: venue_ticker es el simbolo de ESTA fila en `exchange` (nivel
    -- instrumento); ticker_canonico sigue siendo la clave del EMISOR (nivel
    -- issuer, igual entre todas las filas del mismo entity_id). No confundir
    -- ninguno de los dos con market_symbol_mappings.ticker_yahoo (proveedor).
    venue_ticker        TEXT,
    venue_ticker_source TEXT
);

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

-- Mapping canonico <-> Yahoo (estado explícito, sin fallback silencioso) --
CREATE TABLE IF NOT EXISTS market_symbol_mappings (
    instrument_id     TEXT NOT NULL REFERENCES market_instruments(instrument_id),
    ticker_yahoo      TEXT,
    exchange_expected TEXT,
    currency_expected TEXT,
    status            TEXT NOT NULL CHECK (status IN ('MAPPED','UNMAPPED','NOT_FOUND','AMBIGUOUS','CONFLICT')),
    conflict_detail   TEXT,
    source            TEXT NOT NULL DEFAULT 'dim_instrument',
    resolved_at       TIMESTAMPTZ,
    PRIMARY KEY (instrument_id)
);

-- OHLC diario: una fila por instrumento+rueda -----------------
CREATE TABLE IF NOT EXISTS market_price_daily (
    instrument_id    TEXT NOT NULL REFERENCES market_instruments(instrument_id),
    trading_date     DATE NOT NULL,
    open             NUMERIC(18,8),
    high             NUMERIC(18,8),
    low              NUMERIC(18,8),
    close            NUMERIC(18,8),
    adj_close        NUMERIC(18,8),
    volume           BIGINT,
    dividends        NUMERIC(18,8) NOT NULL DEFAULT 0,
    stock_splits     NUMERIC(18,8) NOT NULL DEFAULT 0,
    currency         TEXT NOT NULL,
    exchange         TEXT,
    source_run_id    TEXT NOT NULL,
    source_hash      CHAR(64) NOT NULL,
    fetched_at_utc   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (instrument_id, trading_date)
);
CREATE INDEX IF NOT EXISTS idx_mpd_date ON market_price_daily(trading_date);

-- Corporate actions separadas de la serie de precios ----------
CREATE TABLE IF NOT EXISTS market_corporate_actions (
    action_id     BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES market_instruments(instrument_id),
    action_date   DATE NOT NULL,
    action_type   TEXT NOT NULL CHECK (action_type IN ('DIVIDEND','STOCK_SPLIT')),
    value         NUMERIC(18,8),
    ratio         NUMERIC(18,8),
    source        TEXT NOT NULL DEFAULT 'yahoo_history',
    source_hash   CHAR(64) NOT NULL,
    run_id        TEXT NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mca_inst_date_type_val
    ON market_corporate_actions (instrument_id, action_date, action_type, COALESCE(value, 0));

-- Snapshots actuales (fast_info/info): NUNCA historico --------
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id          BIGSERIAL PRIMARY KEY,
    instrument_id        TEXT NOT NULL REFERENCES market_instruments(instrument_id),
    ticker_yahoo         TEXT,
    fetched_at_utc       TIMESTAMPTZ NOT NULL,
    market_state         TEXT,
    regular_market_time  TIMESTAMPTZ,
    last_price           NUMERIC(18,8),
    previous_close       NUMERIC(18,8),
    open                 NUMERIC(18,8),
    day_high             NUMERIC(18,8),
    day_low              NUMERIC(18,8),
    volume               BIGINT,
    year_high            NUMERIC(18,8),
    year_low             NUMERIC(18,8),
    fifty_day_average    NUMERIC(18,8),
    two_hundred_day_average NUMERIC(18,8),
    currency             TEXT,
    exchange             TEXT,
    timezone             TEXT,
    payload_json         JSONB
);
CREATE INDEX IF NOT EXISTS idx_msnap_inst ON market_snapshots(instrument_id, fetched_at_utc DESC);

-- Cabecera de cada corrida de fetch ---------------------------
CREATE TABLE IF NOT EXISTS market_raw_runs (
    run_id            TEXT PRIMARY KEY,
    stage_run_id      TEXT NOT NULL,
    entity_id         TEXT NOT NULL,
    instrument_id     TEXT NOT NULL REFERENCES market_instruments(instrument_id),
    ticker_canonico   TEXT NOT NULL,
    ticker_yahoo      TEXT,
    source            TEXT NOT NULL DEFAULT 'yahoo',
    source_version    TEXT NOT NULL,
    request_parameters JSONB NOT NULL,
    query_start       TEXT,
    query_end         TEXT,
    interval          TEXT NOT NULL DEFAULT '1d',
    auto_adjust       BOOLEAN NOT NULL DEFAULT FALSE,
    actions           BOOLEAN NOT NULL DEFAULT TRUE,
    fetched_at_utc    TIMESTAMPTZ NOT NULL,
    timezone          TEXT,
    currency          TEXT,
    exchange          TEXT,
    row_count         INTEGER,
    min_date          DATE,
    max_date          DATE,
    bytes             BIGINT,
    sha256            CHAR(64),
    status            TEXT NOT NULL CHECK (status IN ('SUCCESS','EMPTY','PARTIAL','FAILED'))
);
CREATE INDEX IF NOT EXISTS idx_mruns_inst ON market_raw_runs(instrument_id, fetched_at_utc DESC);

-- Registro de archivos RAW en disco (payload fuera de la base) -
CREATE TABLE IF NOT EXISTS market_raw_files (
    file_id       BIGSERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES market_raw_runs(run_id),
    kind          TEXT NOT NULL CHECK (kind IN ('HISTORY_CSV','SNAPSHOT_JSON','META_JSON')),
    rel_path      TEXT NOT NULL,
    bytes         BIGINT NOT NULL,
    sha256        CHAR(64) NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, kind)
);

-- Quality checks por instrumento/fecha/check ------------------
CREATE TABLE IF NOT EXISTS market_data_quality (
    quality_id    BIGSERIAL PRIMARY KEY,
    check_code    TEXT NOT NULL,
    instrument_id TEXT,
    trading_date  DATE,
    severity      TEXT NOT NULL CHECK (severity IN ('VALID','WARNING','INVALID','NOT_APPLICABLE')),
    detail        TEXT,
    run_id        TEXT NOT NULL,
    checked_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mdq_check ON market_data_quality(check_code, instrument_id);

-- Deteccion de cambios retrospectivos (append-only) -----------
CREATE TABLE IF NOT EXISTS market_data_changes (
    change_id     BIGSERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL,
    trading_date  DATE NOT NULL,
    change_type   TEXT NOT NULL CHECK (change_type IN ('NEW','UNCHANGED','CHANGED','DELETED','MISSING')),
    old_hash      CHAR(64),
    new_hash      CHAR(64),
    old_value     JSONB,
    new_value     JSONB,
    reason        TEXT NOT NULL DEFAULT 'UNKNOWN',
    detected_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_run_id   TEXT,
    curr_run_id   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mchg_inst ON market_data_changes(instrument_id, trading_date DESC);

-- Log de cada request HTTP logico -----------------------------
CREATE TABLE IF NOT EXISTS market_fetch_log (
    log_id         BIGSERIAL PRIMARY KEY,
    run_id         TEXT NOT NULL,
    instrument_id  TEXT,
    ticker_yahoo   TEXT,
    source         TEXT NOT NULL DEFAULT 'yahoo',
    requested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    status         TEXT NOT NULL CHECK (status IN ('REQUESTED','SUCCESS','SIN_CAMBIOS','PARTIAL','FAILED','RATE_LIMITED','NOT_FOUND','INVALID_SYMBOL')),
    http_status    INTEGER,
    rows_received  INTEGER,
    bytes_received BIGINT,
    first_date     DATE,
    last_date      DATE,
    sha256         CHAR(64),
    retry_count    INTEGER NOT NULL DEFAULT 0,
    error_type     TEXT,
    error_message  TEXT
);
CREATE INDEX IF NOT EXISTS idx_mflog_run ON market_fetch_log(run_id);
