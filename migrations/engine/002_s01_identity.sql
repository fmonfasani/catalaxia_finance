CREATE SCHEMA IF NOT EXISTS identity;

CREATE TABLE IF NOT EXISTS identity.entities (
    entity_id   TEXT PRIMARY KEY,
    legal_name  TEXT NOT NULL,
    country     TEXT,
    cik         TEXT UNIQUE,
    cuit        TEXT UNIQUE,
    cnv_id      TEXT UNIQUE,
    id_source   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_entity_id_format CHECK (entity_id ~ '^(CIK|CUIT|CNV):[0-9]+$')
);

CREATE TABLE IF NOT EXISTS identity.identifiers (
    identifier_id BIGSERIAL PRIMARY KEY,
    entity_id     TEXT NOT NULL REFERENCES identity.entities(entity_id),
    id_type       TEXT NOT NULL CHECK (id_type IN ('CIK', 'CUIT', 'CNV_ID', 'TICKER', 'YF_SYMBOL')),
    id_value      TEXT NOT NULL,
    marketplace   TEXT NOT NULL DEFAULT 'US',
    source        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RETIRED', 'DISPUTED')),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at    TIMESTAMPTZ,
    UNIQUE (id_type, id_value, marketplace)
);

CREATE INDEX IF NOT EXISTS ix_identifiers_lookup
    ON identity.identifiers (id_type, id_value, marketplace) WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS identity.classifications (
    classification_id BIGSERIAL PRIMARY KEY,
    entity_id         TEXT NOT NULL REFERENCES identity.entities(entity_id),
    class_type        TEXT NOT NULL CHECK (class_type IN ('INSTRUMENT_TYPE', 'EXCHANGE_LISTING', 'GROUP')),
    value             TEXT NOT NULL,
    source            TEXT NOT NULL,
    UNIQUE (entity_id, class_type, value)
);

CREATE TABLE IF NOT EXISTS identity.identifier_reviews (
    review_id            BIGSERIAL PRIMARY KEY,
    id_type              TEXT NOT NULL,
    id_value             TEXT NOT NULL,
    marketplace          TEXT,
    candidate_values     JSONB NOT NULL DEFAULT '[]'::jsonb,
    detected_by_run      TEXT NOT NULL,
    reason               TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED', 'REJECTED')),
    resolved_entity_id   TEXT REFERENCES identity.entities(entity_id),
    resolved_at          TIMESTAMPTZ,
    resolved_note        TEXT
);
