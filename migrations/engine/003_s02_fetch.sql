CREATE SCHEMA IF NOT EXISTS fetch_raw;

CREATE TABLE IF NOT EXISTS fetch_raw.download_log (
    log_id           BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES engine.runs(run_id),
    stage_run_id     BIGINT,
    stage_id         TEXT NOT NULL DEFAULT 'S02_fetch',
    entity_id        TEXT,
    cik              TEXT,
    accession_number TEXT,
    form_type        TEXT,
    filing_date      TEXT,
    period_of_report TEXT,
    source           TEXT NOT NULL,
    endpoint         TEXT NOT NULL,
    request_kind     TEXT NOT NULL,
    critical         BOOLEAN NOT NULL DEFAULT FALSE,
    raw_path         TEXT,
    http_status      INT,
    content_type     TEXT,
    bytes            BIGINT,
    sha256           TEXT,
    downloaded_at    TIMESTAMPTZ,
    result           TEXT NOT NULL CHECK (result IN ('DOWNLOADED', 'SIN_CAMBIOS', 'FAILED')),
    fail_reason      TEXT,
    attempt          INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_download_log_run ON fetch_raw.download_log (run_id);
CREATE INDEX IF NOT EXISTS ix_download_log_acc ON fetch_raw.download_log (cik, accession_number);
CREATE INDEX IF NOT EXISTS ix_download_log_result ON fetch_raw.download_log (result);
