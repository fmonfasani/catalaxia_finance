-- Schema PostgreSQL replicando el SQLite del screener
-- Tablas con nombres "quote" para evitar colisiones con palabras reservadas

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

BEGIN;

-- ── empresas ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS empresas (
    cik            TEXT PRIMARY KEY,
    nombre         TEXT,
    ticker_ppal    TEXT,
    exchange_ppal  TEXT,
    es_sp500       INTEGER DEFAULT 0,
    grupo          TEXT,
    sector_gics    TEXT,
    sic            TEXT,
    sic_desc       TEXT,
    sector_sic     TEXT,
    pais           TEXT,
    category       TEXT,
    fiscal_year_end TEXT,
    esquema        TEXT,
    moneda         TEXT,
    n_tags         INTEGER,
    n_datapoints   INTEGER,
    fecha_meta     TEXT,
    fecha_facts    TEXT,
    fuente         TEXT
);

-- ── tickers ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tickers (
    cik      TEXT,
    ticker   TEXT,
    exchange TEXT
);

-- ── facts ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS facts (
    cik           TEXT,
    taxonomia     TEXT,
    tag           TEXT,
    concepto      TEXT,
    unit          TEXT,
    period_start  TEXT,
    period_end    TEXT,
    val           DOUBLE PRECISION,
    fy            INTEGER,
    fp            TEXT,
    form          TEXT,
    filed         TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_cik ON facts (cik);
CREATE INDEX IF NOT EXISTS idx_facts_cik_concepto ON facts (cik, concepto);

-- ── ratios ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ratios (
    cik              TEXT PRIMARY KEY,
    ticker           TEXT,
    nombre           TEXT,
    esquema          TEXT,
    moneda           TEXT,
    sector_gics      TEXT,
    grupo            TEXT,
    margen_bruto     DOUBLE PRECISION,
    margen_operativo DOUBLE PRECISION,
    margen_ebitda    DOUBLE PRECISION,
    margen_neto      DOUBLE PRECISION,
    roe              DOUBLE PRECISION,
    roa              DOUBLE PRECISION,
    roce             DOUBLE PRECISION,
    deuda_equity     DOUBLE PRECISION,
    deuda_ebitda     DOUBLE PRECISION,
    deuda_neta_ebitda DOUBLE PRECISION,
    current_ratio    DOUBLE PRECISION,
    quick_ratio      DOUBLE PRECISION,
    asset_turnover   DOUBLE PRECISION,
    inventory_turnover DOUBLE PRECISION,
    dso              DOUBLE PRECISION,
    fcf_margin       DOUBLE PRECISION,
    capex_revenue    DOUBLE PRECISION,
    earnings_quality DOUBLE PRECISION,
    payout           DOUBLE PRECISION,
    fcf_payout       DOUBLE PRECISION,
    eps_ttm          DOUBLE PRECISION,
    eps_anual        DOUBLE PRECISION,
    bvps             DOUBLE PRECISION,
    cagr_revenue_5y  DOUBLE PRECISION,
    cagr_eps_5y      DOUBLE PRECISION,
    cagr_ni_5y       DOUBLE PRECISION,
    cagr_equity_5y   DOUBLE PRECISION,
    _revenue_ttm     DOUBLE PRECISION,
    _netincome_ttm   DOUBLE PRECISION,
    _ebitda_ttm      DOUBLE PRECISION,
    _fcf_ttm         DOUBLE PRECISION,
    _equity          DOUBLE PRECISION,
    _assets          DOUBLE PRECISION,
    _deuda           DOUBLE PRECISION,
    ni_estrategia    TEXT,
    fecha            TEXT,
    precio           DOUBLE PRECISION,
    market_cap       DOUBLE PRECISION,
    fx_a_usd         DOUBLE PRECISION,
    per              DOUBLE PRECISION,
    p_book           DOUBLE PRECISION,
    p_sales          DOUBLE PRECISION,
    ev_ebitda        DOUBLE PRECISION,
    earnings_yield   DOUBLE PRECISION,
    fcf_yield        DOUBLE PRECISION,
    div_yield        DOUBLE PRECISION,
    flag_valuacion   TEXT
);

-- ── precios ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS precios (
    cik        TEXT PRIMARY KEY,
    ticker     TEXT,
    precio     DOUBLE PRECISION,
    market_cap DOUBLE PRECISION,
    year_high  DOUBLE PRECISION,
    year_low   DOUBLE PRECISION,
    currency   TEXT,
    fecha      TEXT
);

-- ── cnv_estados_v2 ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cnv_estados_v2 (
    ticker             TEXT,
    cuit               TEXT,
    concepto           TEXT,
    period_end         TEXT,
    tipo               TEXT,
    valor              DOUBLE PRECISION,
    valor_comparativo  DOUBLE PRECISION,
    fecha_reexpresion  TEXT,
    form               TEXT,
    unidad_factor      INTEGER,
    accn               TEXT,
    fuente             TEXT DEFAULT 'cnv-aif2',
    moneda             TEXT,
    unidad_medida      TEXT,
    tipo_balance       TEXT DEFAULT '',
    PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
);

-- ── cnv_estados_norm ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cnv_estados_norm (
    cuit               TEXT,
    ticker             TEXT,
    concepto           TEXT,
    period_end         TEXT,
    tipo               TEXT,
    valor              DOUBLE PRECISION,
    valor_comparativo  DOUBLE PRECISION,
    fecha_reexpresion  TEXT,
    form               TEXT,
    escala             INTEGER,
    accn               TEXT,
    fuente             TEXT DEFAULT 'cnv-aif2',
    source_type        TEXT,
    -- Perimetro contable: sin el en la PK, individual y consolidado colisionan.
    -- Ver docs/07-homologacion-cnv.md
    tipo_balance         TEXT DEFAULT '',
    perimetro_mixto      INTEGER DEFAULT 0,
    identidad_desvio_pct DOUBLE PRECISION,
    PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
);

-- ── cnv_estados_suspect ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cnv_estados_suspect (
    cik        TEXT,
    period_end TEXT,
    error_pct  DOUBLE PRECISION,
    assets     DOUBLE PRECISION,
    pasivo_pn  DOUBLE PRECISION,
    PRIMARY KEY (cik, period_end)
);

-- ── cnv_dividendos ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cnv_dividendos (
    cuit             TEXT,
    empresa          TEXT,
    guid             TEXT PRIMARY KEY,
    clase            TEXT,
    formulario       TEXT,
    fecha_candidata  TEXT,
    monto_candidato  TEXT,
    por_accion       TEXT,
    snippet          TEXT,
    fuente           TEXT DEFAULT 'cnv-aif2'
);

-- ── cnv_estados ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cnv_estados (
    ticker              TEXT,
    cik                 TEXT,
    concepto            TEXT,
    period_end          TEXT,
    tipo                TEXT,
    valor               DOUBLE PRECISION,
    valor_comparativo   DOUBLE PRECISION,
    fecha_reexpresion   TEXT,
    form                TEXT,
    escala              INTEGER,
    accn                TEXT,
    fuente              TEXT DEFAULT 'cnv-6k',
    PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion)
);

-- ── adr_ratios ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS adr_ratios (
    edgar_ticker TEXT PRIMARY KEY,
    cuit         TEXT,
    ratio        INTEGER,
    clase        TEXT,
    source_url   TEXT,
    filing_form  TEXT,
    filing_date  TEXT
);

-- ── adr_dividendos ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS adr_dividendos (
    cuit               TEXT,
    ticker             TEXT,
    cusip              TEXT,
    announcement_date  TEXT,
    record_date        TEXT,
    payment_date       TEXT,
    rate_per_dr        DOUBLE PRECISION,
    source             TEXT
);

-- ── cedear_ratios ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cedear_ratios (
    ticker              TEXT PRIMARY KEY,
    empresa             TEXT,
    ratio               TEXT,
    cedears_por_accion  DOUBLE PRECISION,
    isin_cedear         TEXT,
    isin_subyacente     TEXT,
    pais                TEXT,
    source_url          TEXT,
    fecha               TEXT
);

-- ── iamc_precios ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iamc_precios (
    ticker      TEXT PRIMARY KEY,
    cierre_ars  DOUBLE PRECISION,
    "mcap_M_ars"  DOUBLE PRECISION,
    fecha       TEXT
);

-- ── mapa_entidades ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mapa_entidades (
    cuit         TEXT,
    ticker       TEXT,
    nombre       TEXT,
    grupo        TEXT,
    cik_byma     TEXT,
    es_primario  INTEGER DEFAULT 1,
    PRIMARY KEY (cuit, ticker)
);

-- ── ratios_cnv ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ratios_cnv (
    cuit              TEXT PRIMARY KEY,
    ticker            TEXT,
    ultimo_periodo    TEXT,
    roe               DOUBLE PRECISION,
    roa               DOUBLE PRECISION,
    margen_neto       DOUBLE PRECISION,
    deuda_ebitda      DOUBLE PRECISION,
    eps               DOUBLE PRECISION,
    fcf_yield         DOUBLE PRECISION,
    payout            DOUBLE PRECISION,
    cnv_roe           DOUBLE PRECISION,
    cnv_roa           DOUBLE PRECISION,
    cnv_margen_neto   DOUBLE PRECISION,
    cnv_deuda_ebitda  DOUBLE PRECISION,
    cagr_eps_5y       DOUBLE PRECISION,
    cagr_flag         TEXT,
    provenance        TEXT
);

-- ── screener ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS screener (
    cuit                 TEXT PRIMARY KEY,
    ticker               TEXT,
    ultimo_periodo       TEXT,
    grupo                TEXT,
    roe                  DOUBLE PRECISION,
    roa                  DOUBLE PRECISION,
    margen_neto          DOUBLE PRECISION,
    deuda_ebitda         DOUBLE PRECISION,
    eps                  DOUBLE PRECISION,
    fcf_ce               DOUBLE PRECISION,
    payout               DOUBLE PRECISION,
    cagr_eps_5y          DOUBLE PRECISION,
    cagr_flag            TEXT,
    per                  DOUBLE PRECISION,
    price_book           DOUBLE PRECISION,
    price_sales          DOUBLE PRECISION,
    precio               DOUBLE PRECISION,
    market_cap_usd       DOUBLE PRECISION,
    currency             TEXT,
    max_52w              DOUBLE PRECISION,
    min_52w              DOUBLE PRECISION,
    flag_cnv_fallback    INTEGER DEFAULT 0,
    flag_no_significativo INTEGER DEFAULT 0,
    dato_desactualizado  INTEGER DEFAULT 0,
    payout_source        TEXT,
    provenance           TEXT,
    es_financiera        INTEGER DEFAULT 0,
    sector               TEXT,
    adr_ratio            INTEGER,
    fuente_fund          TEXT,
    payout_status        TEXT,
    ev_ebitda            DOUBLE PRECISION,
    margen_operativo     DOUBLE PRECISION,
    precio_ars           DOUBLE PRECISION,
    precio_usd           DOUBLE PRECISION,
    ccl                  DOUBLE PRECISION,
    precio_dif_iamc      DOUBLE PRECISION,
    precio_fuente        TEXT,
    cedear_ratio         TEXT,
    cedear_x             DOUBLE PRECISION,
    cusip                TEXT,
    dr_level             TEXT,
    div_adr_12m          DOUBLE PRECISION,
    last_div_date        TEXT,
    div_yield_adr        DOUBLE PRECISION
);

-- ── instrumentos ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instrumentos (
    instrumento_id    SERIAL PRIMARY KEY,
    company_id        TEXT,
    ticker_empresa    TEXT,
    nombre            TEXT,
    tipo              TEXT,
    ticker            TEXT,
    mercado           TEXT,
    moneda            TEXT,
    isin              TEXT,
    cusip             TEXT,
    ratio             TEXT,
    fuente_precio     TEXT,
    precio            DOUBLE PRECISION
);

-- ── descargas_log ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS descargas_log (
    cik     TEXT,
    capa    TEXT,
    estado  TEXT,
    error   TEXT,
    ts      TEXT
);

COMMIT;


-- Metadatos declarados por la CNV en cada documento (salida de job8_doc_meta.py).
-- TipoBalance tiene cobertura del 100%. Ver docs/07-homologacion-cnv.md
CREATE TABLE IF NOT EXISTS cnv_doc_meta (
    accn         TEXT PRIMARY KEY,
    tipo_balance TEXT,
    fecha_cierre TEXT,
    moneda_cod   TEXT,
    norma        TEXT,
    parsed_at    TEXT
);
