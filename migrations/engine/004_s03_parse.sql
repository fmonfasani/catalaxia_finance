CREATE SCHEMA IF NOT EXISTS parsed;

CREATE TABLE IF NOT EXISTS parsed.facts (
    fact_id          BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id        TEXT NOT NULL,
    cik              TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    form             TEXT,
    filing_date      TEXT,
    report_period    TEXT,
    taxonomy         TEXT,
    namespace        TEXT,
    tag              TEXT NOT NULL,
    qname            TEXT NOT NULL,
    value_text       TEXT,
    value_numeric    NUMERIC,
    is_numeric       BOOLEAN NOT NULL DEFAULT FALSE,
    is_nil           BOOLEAN NOT NULL DEFAULT FALSE,
    unit_ref         TEXT,
    unit_type        TEXT CHECK (unit_type IN ('SIMPLE', 'DIVIDED')),
    measure          TEXT,
    numerator        TEXT,
    denominator      TEXT,
    decimals         TEXT,
    context_id       TEXT,
    start_date       DATE,
    end_date         DATE,
    instant_date     DATE,
    period_kind      TEXT CHECK (period_kind IN ('INSTANT', 'DURATION', 'FOREVER')),
    dimensions       JSONB,
    dim_count        INT NOT NULL DEFAULT 0,
    frame            TEXT,
    source_kind      TEXT NOT NULL,
    source_file      TEXT NOT NULL,
    source_path      TEXT NOT NULL,
    source_hash      TEXT NOT NULL,
    stage_run_id     BIGINT
);
CREATE INDEX IF NOT EXISTS ix_facts_run ON parsed.facts (run_id);
CREATE INDEX IF NOT EXISTS ix_facts_acc ON parsed.facts (accession_number);
CREATE INDEX IF NOT EXISTS ix_facts_tag ON parsed.facts (qname);

CREATE TABLE IF NOT EXISTS parsed.contexts (
    ctx_id           BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id        TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    context_id       TEXT NOT NULL,
    scheme           TEXT,
    identifier       TEXT,
    start_date       DATE,
    end_date         DATE,
    instant_date     DATE,
    period_kind      TEXT CHECK (period_kind IN ('INSTANT', 'DURATION', 'FOREVER')),
    dimensions       JSONB,
    typed_dimensions JSONB,
    dim_count        INT NOT NULL DEFAULT 0,
    has_typed        BOOLEAN NOT NULL DEFAULT FALSE,
    source_file      TEXT NOT NULL,
    source_hash      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ctx_run ON parsed.contexts (run_id);
CREATE INDEX IF NOT EXISTS ix_ctx_acc ON parsed.contexts (accession_number);

CREATE TABLE IF NOT EXISTS parsed.units (
    unit_row_id      BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id        TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    unit_ref         TEXT NOT NULL,
    unit_type        TEXT CHECK (unit_type IN ('SIMPLE', 'DIVIDED')),
    measures         JSONB,
    numerator        JSONB,
    denominator      JSONB,
    fact_count       INT NOT NULL DEFAULT 0,
    source_file      TEXT NOT NULL,
    source_hash      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_units_run ON parsed.units (run_id);

CREATE TABLE IF NOT EXISTS parsed.concepts (
    concept_id    BIGSERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES engine.runs(run_id),
    namespace     TEXT,
    tag           TEXT NOT NULL,
    qname         TEXT NOT NULL,
    label         TEXT,
    documentation TEXT,
    xsd_type      TEXT,
    period_type   TEXT CHECK (period_type IN ('instant', 'duration') OR period_type IS NULL),
    balance       TEXT CHECK (balance IN ('debit', 'credit') OR balance IS NULL),
    abstract      BOOLEAN,
    is_custom     BOOLEAN NOT NULL DEFAULT FALSE,
    taxonomy      TEXT,
    source_schema TEXT
);
CREATE INDEX IF NOT EXISTS ix_concepts_run ON parsed.concepts (run_id);
CREATE INDEX IF NOT EXISTS ix_concepts_qn ON parsed.concepts (qname);

CREATE TABLE IF NOT EXISTS parsed.link_relations (
    rel_id           BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id        TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    linkbase         TEXT NOT NULL CHECK (linkbase IN ('LABEL', 'PRESENTATION', 'CALCULATION', 'DEFINITION')),
    role             TEXT,
    from_qname       TEXT,
    to_qname         TEXT,
    arc_role         TEXT,
    weight           NUMERIC,
    order_num        NUMERIC,
    label_type       TEXT,
    lang             TEXT,
    label_text       TEXT,
    preferred_sign   TEXT,
    dimension_qname  TEXT,
    member_qname     TEXT,
    source_file      TEXT NOT NULL,
    source_hash      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rels_run ON parsed.link_relations (run_id);
CREATE INDEX IF NOT EXISTS ix_rels_acc ON parsed.link_relations (accession_number, linkbase);

CREATE TABLE IF NOT EXISTS parsed.pre_xbrl_filings (
    px_id            BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id        TEXT NOT NULL,
    cik              TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    form             TEXT,
    filing_date      TEXT,
    period_of_report TEXT,
    primary_doc      TEXT,
    index_path       TEXT,
    n_documents      INT NOT NULL DEFAULT 0,
    documents        JSONB,
    bytes_total      BIGINT NOT NULL DEFAULT 0,
    classification   TEXT NOT NULL DEFAULT 'PRE_XBRL',
    note             TEXT
);

CREATE TABLE IF NOT EXISTS parsed.companyfacts_compare (
    cmp_id        BIGSERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id     TEXT NOT NULL,
    taxonomy      TEXT,
    tag           TEXT NOT NULL,
    qname         TEXT NOT NULL,
    in_companyfacts BOOLEAN NOT NULL,
    in_filing       BOOLEAN NOT NULL,
    cf_obs          INT,
    cf_unit_kinds   JSONB,
    cf_first_period TEXT,
    cf_last_period  TEXT,
    filing_obs      INT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS parsed.parse_errors (
    error_id         BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    entity_id        TEXT,
    accession_number TEXT,
    source_file      TEXT,
    severity         TEXT NOT NULL CHECK (severity IN ('ERROR', 'WARNING')),
    code             TEXT NOT NULL,
    message          TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_perr_run ON parsed.parse_errors (run_id);
