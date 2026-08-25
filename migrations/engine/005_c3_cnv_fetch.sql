-- C3 CNV FETCHER. Aditiva: no toca ninguna tabla de SEC (fetch_raw.download_log),
-- de mercado ni del ratio engine.

CREATE SCHEMA IF NOT EXISTS fetch_raw;

-- Inventario de discovery: una fila por presentacion (GUID) de un perfil CNV.
CREATE TABLE IF NOT EXISTS fetch_raw.cnv_presentation (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES engine.runs(run_id),
    cuit                TEXT NOT NULL,
    entity_key          TEXT,
    guid                TEXT NOT NULL,
    presentation_id     TEXT,
    fecha_publicacion   TEXT,
    seccion             TEXT,
    secciones           TEXT,
    titulo              TEXT NOT NULL,
    url                 TEXT NOT NULL,
    clase               TEXT NOT NULL,
    ambito              TEXT NOT NULL CHECK (ambito IN ('PROPIO', 'RELACIONADA', 'NO_FINANCIERO')),
    -- CONTROLADA y VINCULADA son relaciones DISTINTAS y se preservan como tales.
    -- NULL = CNV no la declara (legacy BALANCE SUBSIDIARIA); nunca se asume.
    relacion            TEXT CHECK (relacion IN ('CONTROLADA', 'VINCULADA')),
    relacion_origen     TEXT NOT NULL DEFAULT 'AUSENTE',
    cuit_relacionado    TEXT,
    nombre_relacionado  TEXT,
    sigla_legacy        TEXT,
    norma_contable      TEXT,
    tipo_balance        TEXT,
    periodicidad_raw    TEXT,
    periodicidad_norm   TEXT,
    periodicidad_origen TEXT,
    fecha_cierre        TEXT,
    anio_cierre         INT,
    ocurrencias         INT NOT NULL DEFAULT 1,
    discovered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, guid)
);

CREATE INDEX IF NOT EXISTS ix_cnv_presentation_cuit ON fetch_raw.cnv_presentation (cuit, clase);
CREATE INDEX IF NOT EXISTS ix_cnv_presentation_guid ON fetch_raw.cnv_presentation (guid);
CREATE INDEX IF NOT EXISTS ix_cnv_presentation_rel ON fetch_raw.cnv_presentation (relacion, cuit_relacionado);

-- Log de descargas: una fila por intento resuelto (transporte + validacion de contenido).
CREATE TABLE IF NOT EXISTS fetch_raw.cnv_download_log (
    log_id            BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES engine.runs(run_id),
    stage_run_id      BIGINT,
    stage_id          TEXT NOT NULL DEFAULT 'C3_CNV_fetch',
    entity_key        TEXT,
    cuit              TEXT NOT NULL,
    source            TEXT NOT NULL DEFAULT 'CNV',
    artifact_kind     TEXT NOT NULL,
    artifact_key      TEXT NOT NULL,
    parent_kind       TEXT,
    parent_key        TEXT,
    endpoint          TEXT NOT NULL,
    http_method       TEXT NOT NULL DEFAULT 'GET',
    critical          BOOLEAN NOT NULL DEFAULT FALSE,
    http_status       INT,
    content_type      TEXT,
    bytes             BIGINT,
    sha256            TEXT,
    sha256_b64        TEXT,
    hash_cnv          TEXT,
    hash_cnv_match    BOOLEAN,
    raw_path          TEXT,
    duplicate_of      TEXT,
    attempts          INT NOT NULL DEFAULT 1,
    elapsed_ms        INT,
    downloaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- OK/SIN_CAMBIOS = evidencia utilizable. REVIEW = persistida pero en cola humana.
    result            TEXT NOT NULL CHECK (result IN
                        ('DOWNLOADED', 'SIN_CAMBIOS', 'REVIEW', 'FAILED', 'NOT_FOUND',
                         'BLOCKED', 'SKIPPED')),
    validation_status TEXT CHECK (validation_status IN ('VALID', 'REVIEW', 'INVALID')),
    validation_failed TEXT,
    validation        JSONB,
    fail_reason       TEXT
);

CREATE INDEX IF NOT EXISTS ix_cnv_dl_run ON fetch_raw.cnv_download_log (run_id);
CREATE INDEX IF NOT EXISTS ix_cnv_dl_key ON fetch_raw.cnv_download_log (artifact_kind, artifact_key);
CREATE INDEX IF NOT EXISTS ix_cnv_dl_result ON fetch_raw.cnv_download_log (result, validation_status);

-- Manifest: una fila por artefacto RAW distinto (kind,key,sha256). Idempotente entre runs.
CREATE TABLE IF NOT EXISTS fetch_raw.cnv_artifact (
    artifact_id     BIGSERIAL PRIMARY KEY,
    cuit            TEXT NOT NULL,
    entity_key      TEXT,
    artifact_kind   TEXT NOT NULL,
    artifact_key    TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    sha256_b64      TEXT NOT NULL,
    bytes           BIGINT NOT NULL,
    content_type    TEXT,
    nombre          TEXT,
    raw_path        TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    hash_cnv        TEXT,
    hash_cnv_match  BOOLEAN,
    parent_kind     TEXT,
    parent_key      TEXT,
    first_seen_run  TEXT NOT NULL,
    last_seen_run   TEXT NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    times_seen      INT NOT NULL DEFAULT 1,
    UNIQUE (artifact_kind, artifact_key, sha256)
);

CREATE INDEX IF NOT EXISTS ix_cnv_artifact_sha ON fetch_raw.cnv_artifact (sha256);
CREATE INDEX IF NOT EXISTS ix_cnv_artifact_cuit ON fetch_raw.cnv_artifact (cuit, artifact_kind);
