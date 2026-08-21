-- =====================================================================
-- Fundación de datos v1 — esquema PostgreSQL (medallion)
-- Implementa docs/proyecto/DISENO_implementacion.md
-- Convenciones: NUMERIC (no float) para montos; timestamptz; moneda por-fact.
-- =====================================================================

-- =========================== BRONZE / raw ============================
-- Inmutable. Nada se pisa: correcciones = nueva fila (versionado por descarga).

CREATE TABLE IF NOT EXISTS raw_sec_facts (
    id            BIGSERIAL PRIMARY KEY,
    cik           TEXT        NOT NULL,
    taxonomia     TEXT,
    tag           TEXT        NOT NULL,
    unit          TEXT        NOT NULL,          -- moneda/unidad por-fact (USD, ARS, shares, pure...)
    period_start  DATE,
    period_end    DATE,
    val           NUMERIC     NOT NULL,          -- precisión arbitraria (nada de float)
    fy            INT,
    fp            TEXT,
    form          TEXT,                          -- 10-K, 20-F, 10-Q...
    accession     TEXT,                          -- trazabilidad a la presentación
    filed         DATE,
    downloaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sha256        TEXT
);
CREATE INDEX IF NOT EXISTS ix_rawsec_cik      ON raw_sec_facts(cik);
CREATE INDEX IF NOT EXISTS ix_rawsec_tag      ON raw_sec_facts(tag);
CREATE INDEX IF NOT EXISTS ix_rawsec_unit     ON raw_sec_facts(unit);

CREATE TABLE IF NOT EXISTS raw_cnv_estados (
    id               BIGSERIAL PRIMARY KEY,
    cuit             TEXT        NOT NULL,
    concepto_origen  TEXT        NOT NULL,
    period_end       DATE        NOT NULL,
    tipo             TEXT,                        -- A/P (no confiable para de-acumular; ver contrato)
    valor            NUMERIC     NOT NULL,
    unidad           TEXT,                        -- millones/miles/unidades
    moneda           TEXT        NOT NULL DEFAULT 'ARS',
    fecha_reexpresion DATE,                       -- vintage de reexpresión (NIC-29)
    form             TEXT,
    docid            TEXT,                        -- trazabilidad al doc CNV
    downloaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sha256           TEXT
);
CREATE INDEX IF NOT EXISTS ix_rawcnv_cuit ON raw_cnv_estados(cuit);

CREATE TABLE IF NOT EXISTS raw_prices (
    id            BIGSERIAL PRIMARY KEY,
    ticker        TEXT        NOT NULL,
    fecha         DATE        NOT NULL,
    close         NUMERIC     NOT NULL,
    currency      TEXT        NOT NULL,
    source        TEXT        NOT NULL DEFAULT 'yfinance',
    downloaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticker, fecha, source)
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT        NOT NULL,             -- sec/cnv/yf
    ref         TEXT,                             -- cik/cuit/ticker/url
    http_status INT,
    sha256      TEXT,
    bytes       BIGINT,
    path        TEXT,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    error       TEXT
);

-- =========================== SILVER / parsed =========================

-- Identidad canónica: UNA fila por empresa real (resuelve el lío ticker/razón social).
CREATE TABLE IF NOT EXISTS dim_entity (
    entity_id        BIGSERIAL PRIMARY KEY,
    cuit             TEXT UNIQUE,
    cik              TEXT UNIQUE,
    ticker_canonico  TEXT NOT NULL UNIQUE,
    nombre           TEXT,
    grupo            TEXT CHECK (grupo IN ('byma_only','adr','sp500')),
    moneda_funcional TEXT,                        -- referencial; la real es por-fact
    fy_end_month     INT  CHECK (fy_end_month BETWEEN 1 AND 12),
    es_financiera    BOOLEAN NOT NULL DEFAULT false
);

-- Cada cotización de una entidad (BYMA ordinaria / ADR / CEDEAR).
CREATE TABLE IF NOT EXISTS dim_instrument (
    instrument_id BIGSERIAL PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES dim_entity(entity_id),
    ticker        TEXT   NOT NULL,
    mercado       TEXT   NOT NULL,                -- BYMA/NYSE/NASDAQ
    tipo          TEXT   CHECK (tipo IN ('ordinaria','adr','cedear')),
    moneda        TEXT,
    ratio         NUMERIC,                         -- acciones por ADR / CEDEAR ratio
    UNIQUE (ticker, mercado)
);

-- Mapeo de tag/concepto de origen -> concepto canónico (extensible).
CREATE TABLE IF NOT EXISTS concepto_crosswalk (
    id                BIGSERIAL PRIMARY KEY,
    fuente            TEXT NOT NULL CHECK (fuente IN ('sec','cnv')),
    origen            TEXT NOT NULL,              -- tag XBRL o concepto CNV
    concepto_canonico TEXT NOT NULL,
    signo             INT  NOT NULL DEFAULT 1,    -- +1/-1 si hay que invertir
    nota              TEXT,
    UNIQUE (fuente, origen, concepto_canonico)
);

-- El corazón: fundamentals normalizados, trimestral standalone + anual.
CREATE TABLE IF NOT EXISTS fact_financials (
    id                BIGSERIAL PRIMARY KEY,
    entity_id         BIGINT  NOT NULL REFERENCES dim_entity(entity_id),
    concepto_canonico TEXT    NOT NULL,
    period_end        DATE    NOT NULL,
    period_type       TEXT    NOT NULL CHECK (period_type IN ('Q','A')),
    fiscal_q          INT     CHECK (fiscal_q BETWEEN 1 AND 4),
    valor             NUMERIC NOT NULL,
    moneda            TEXT    NOT NULL,           -- por-fact (ARS/USD)
    unidad_factor     NUMERIC NOT NULL DEFAULT 1, -- a unidades base
    incluye_recpam    BOOLEAN NOT NULL DEFAULT true,   -- doble variante RECPAM
    fecha_reexpresion DATE,
    fuente            TEXT    NOT NULL CHECK (fuente IN ('sec','cnv')),
    source_ref        TEXT,                       -- accession/docid
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, concepto_canonico, period_end, period_type, incluye_recpam, fuente)
);
CREATE INDEX IF NOT EXISTS ix_ff_entity   ON fact_financials(entity_id);
CREATE INDEX IF NOT EXISTS ix_ff_concepto ON fact_financials(concepto_canonico);
CREATE INDEX IF NOT EXISTS ix_ff_period   ON fact_financials(period_end);

-- Cuarentena: lo que NO pasa validación (no entra al gold).
CREATE TABLE IF NOT EXISTS fact_financials_cuarentena (
    LIKE fact_financials INCLUDING DEFAULTS,
    motivo_rechazo TEXT NOT NULL,
    detectado_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================== GOLD / derived ==========================

CREATE TABLE IF NOT EXISTS fact_ratios (
    id             BIGSERIAL PRIMARY KEY,
    entity_id      BIGINT NOT NULL REFERENCES dim_entity(entity_id),
    period_end     DATE   NOT NULL,
    period_type    TEXT   NOT NULL CHECK (period_type IN ('Q','A','TTM')),
    incluye_recpam BOOLEAN NOT NULL DEFAULT true,
    ratio          TEXT   NOT NULL,               -- per, roe, roa, margen_neto...
    valor          NUMERIC,
    built_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, period_end, period_type, incluye_recpam, ratio)
);

CREATE TABLE IF NOT EXISTS prices_daily (
    id           BIGSERIAL PRIMARY KEY,
    ticker       TEXT NOT NULL,
    fecha        DATE NOT NULL,
    precio_ars   NUMERIC,
    precio_usd   NUMERIC,
    ccl          NUMERIC,
    market_cap   NUMERIC,
    max_52s      NUMERIC,
    min_52s      NUMERIC,
    UNIQUE (ticker, fecha)
);

-- Detección de frescura: comparar todos y actualizar lo que falta.
CREATE TABLE IF NOT EXISTS freshness (
    entity_id       BIGINT PRIMARY KEY REFERENCES dim_entity(entity_id),
    ultimo_q        DATE,
    ultimo_a        DATE,
    ultima_revision TIMESTAMPTZ,
    estado          TEXT CHECK (estado IN ('al_dia','desactualizado','sin_datos'))
);

-- Producto final (columnas del contrato §G). Se materializa desde fact_ratios+prices.
CREATE TABLE IF NOT EXISTS screener (
    entity_id     BIGINT PRIMARY KEY REFERENCES dim_entity(entity_id),
    especie       TEXT,
    mercado       TEXT,
    precio        NUMERIC,        -- yf nativo
    precio_usd    NUMERIC,
    per           NUMERIC,
    max_52s       NUMERIC,
    dif_max_52s   NUMERIC,
    min_52s       NUMERIC,
    dif_min_52s   NUMERIC,
    deuda_ebitda  NUMERIC,
    eps_anual     NUMERIC,
    cagr_eps_5y   NUMERIC,
    margen_neto   NUMERIC,
    roe_5y        NUMERIC,
    fcf_ce        NUMERIC,        -- FCFonCE
    payout        NUMERIC,
    market_cap    NUMERIC,
    shares        NUMERIC,
    net_income    NUMERIC,
    revenue       NUMERIC,
    gross_profit  NUMERIC,
    ebitda        NUMERIC,
    operating_income NUMERIC,
    dividendos    NUMERIC,        -- dividendos $
    fcf           NUMERIC,
    assets        NUMERIC,
    equity        NUMERIC,
    deuda         NUMERIC,
    cash          NUMERIC,
    incluye_recpam BOOLEAN NOT NULL DEFAULT true,
    built_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
