-- ============================================================================
-- CatalaXia — Módulo Análisis Financiero CEDEARs
-- Migración inicial — 5 tablas, ver docs/03-base-de-datos.md para el contrato
-- PostgreSQL 16
-- ============================================================================

BEGIN;

-- ── 1. cedears — Maestro de tickers ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cedears (
    ticker        VARCHAR(10)  PRIMARY KEY,
    ticker_sec    VARCHAR(10)  NOT NULL,
    cik           VARCHAR(10)  NOT NULL,
    nombre        VARCHAR(150) NOT NULL,
    exchange      VARCHAR(10)  NOT NULL,
    pais          VARCHAR(50),
    activo        BOOLEAN      NOT NULL DEFAULT true,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cedears_cik ON cedears (cik);
CREATE INDEX IF NOT EXISTS idx_cedears_activo ON cedears (activo) WHERE activo = true;

-- ── 2. precios_raw — Datos crudos de Yahoo Finance (Job 1A) ────────────────
CREATE TABLE IF NOT EXISTS precios_raw (
    ticker_sec      VARCHAR(10) PRIMARY KEY REFERENCES cedears (ticker_sec),
    last_price      FLOAT,
    year_high       FLOAT,
    year_low        FLOAT,
    market_cap      FLOAT,
    shares          FLOAT,
    currency        VARCHAR(5),
    exchange_yf     VARCHAR(20),
    previous_close  FLOAT,
    fetched_at      TIMESTAMP NOT NULL
);

-- ── 3. financials_raw — Datos crudos de SEC EDGAR (Job 1B) ─────────────────
CREATE TABLE IF NOT EXISTS financials_raw (
    id             BIGSERIAL PRIMARY KEY,
    cik            VARCHAR(10)  NOT NULL,
    ticker_sec     VARCHAR(10)  NOT NULL,
    metrica        VARCHAR(100) NOT NULL,
    unidad         VARCHAR(20)  NOT NULL,
    periodo_start  DATE,
    periodo_end    DATE         NOT NULL,
    val            FLOAT        NOT NULL,
    fy             INTEGER,
    fp             VARCHAR(5),
    form           VARCHAR(10)  NOT NULL,
    filed          DATE,
    frame          VARCHAR(20),
    fetched_at     TIMESTAMP    NOT NULL,

    -- Evita duplicados entre runs semanales; permite enmiendas (10-K/A)
    CONSTRAINT uq_financials_raw_datapoint
        UNIQUE (cik, metrica, periodo_end, filed, form)
);

-- Índice de performance — el que usa Job 2 para leer por empresa
CREATE INDEX IF NOT EXISTS idx_financials_raw_cik_metrica_periodo
    ON financials_raw (cik, metrica, periodo_end);

-- ── 4. ratios — Ratios calculados (Job 2) — única tabla leída por el frontend
CREATE TABLE IF NOT EXISTS ratios (
    ticker                  VARCHAR(10) PRIMARY KEY REFERENCES cedears (ticker),
    precio_usd              FLOAT,
    year_high               FLOAT,
    year_low                FLOAT,
    dif_max                 FLOAT,
    dif_min                 FLOAT,
    per                     FLOAT,
    eps_anual               FLOAT,
    crec_eps_5y             FLOAT,
    margen_neto             FLOAT,
    roe_5y                  FLOAT,
    fcf_on_ce               FLOAT,
    payout                  FLOAT,
    deuda_ebitda            FLOAT,
    calculated_at           TIMESTAMP,
    prices_updated_at       TIMESTAMP,
    financials_updated_at   TIMESTAMP
);

-- ── 5. jobs + job_errores — Control y auditoría ────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo            VARCHAR(30) NOT NULL CHECK (tipo IN ('precios', 'financials', 'calculo')),
    status          VARCHAR(15) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'done', 'error')),
    processed       INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    errores_count   INTEGER NOT NULL DEFAULT 0,
    duracion_seg    FLOAT,
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_errores (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id    UUID NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    ticker    VARCHAR(10) NOT NULL,
    mensaje   TEXT NOT NULL,
    intento   INTEGER NOT NULL DEFAULT 1,
    ts        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_errores_job_id ON job_errores (job_id);

COMMIT;

-- ============================================================================
-- Notas de uso:
--
-- UPSERT precios_raw (Job 1A):
--   INSERT INTO precios_raw (...) VALUES (...)
--   ON CONFLICT (ticker_sec) DO UPDATE SET ...;
--
-- INSERT financials_raw (Job 1B) — nunca UPSERT, ver docs/02-jobs.md:
--   INSERT INTO financials_raw (...) VALUES (...)
--   ON CONFLICT ON CONSTRAINT uq_financials_raw_datapoint DO NOTHING;
--
-- UPSERT ratios (Job 2):
--   INSERT INTO ratios (...) VALUES (...)
--   ON CONFLICT (ticker) DO UPDATE SET ...;
-- ============================================================================
