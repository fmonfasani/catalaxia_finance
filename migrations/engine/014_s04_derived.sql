-- =====================================================================
-- 014_s04_derived.sql  ·  schema de salida de S04_normalize
-- =====================================================================
-- Contrato: docs/architecture/S04_CONTRACT.md
--
-- Un hecho canonico por (entidad, filing, concepto, periodo, unidad), con la
-- procedencia de cada uno. No calcula ratios ni arma series: eso es S05.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS derived;

-- ---------------------------------------------------------------------
-- derived.fact — el hecho canonico
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS derived.fact (
    fact_key            TEXT PRIMARY KEY
        CHECK (fact_key ~ '^[0-9a-f]{64}$'),          -- sha256 determinista

    -- IDENTIDAD: sale de identity_v1, no de dim_entity ni identity.entities
    entity_key          TEXT NOT NULL REFERENCES identity_v1.entity(entity_key),
    cik                 TEXT NOT NULL,

    -- el filing
    accession_number    TEXT NOT NULL,
    form                TEXT,
    filing_date         TEXT,
    report_period       TEXT,

    -- el concepto
    qname               TEXT NOT NULL,
    namespace           TEXT,
    tag                 TEXT NOT NULL,
    is_custom           BOOLEAN,

    -- el periodo, del contexto YA deduplicado (T1)
    context_id          TEXT NOT NULL,
    period_kind         TEXT CHECK (period_kind IN ('INSTANT','DURATION','FOREVER')),
    start_date          DATE,
    end_date            DATE,
    instant_date        DATE,

    -- T3: dimensional vs consolidado. Obligatorio, no es un filtro implicito.
    is_dimensional      BOOLEAN NOT NULL,
    dim_count           INTEGER NOT NULL DEFAULT 0,
    dimensions          JSONB,

    -- la unidad
    unit_ref            TEXT,
    unit_kind           TEXT,
    unit_measure        TEXT,
    currency            TEXT,

    -- el valor ganador
    value_numeric       NUMERIC,
    value_text          TEXT,
    is_nil              BOOLEAN NOT NULL DEFAULT false,
    is_numeric          BOOLEAN NOT NULL DEFAULT false,
    decimals            TEXT,

    -- T2: procedencia del desempate
    n_fuentes           INTEGER NOT NULL,
    source_fact_ids     BIGINT[] NOT NULL,
    desempate           TEXT NOT NULL
        CHECK (desempate IN ('UNICO','IDENTICO','POR_PRECISION','POR_FACT_ID')),

    -- procedencia de la corrida
    input_checkpoint_id TEXT NOT NULL,
    run_id              TEXT NOT NULL REFERENCES engine.runs(run_id),
    valid_to            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- SIN INVENCION: un hecho canonico sin fila de origen no existe (C-S04-006)
    CONSTRAINT ck_fact_tiene_origen CHECK (
        n_fuentes >= 1 AND array_length(source_fact_ids, 1) = n_fuentes),

    -- un hecho numerico no-nil necesita unidad (C-S04-007)
    CONSTRAINT ck_numerico_con_unidad CHECK (
        NOT (is_numeric AND NOT is_nil) OR unit_measure IS NOT NULL),

    -- coherencia del periodo con su tipo
    CONSTRAINT ck_periodo_coherente CHECK (
        period_kind IS NULL
        OR (period_kind = 'INSTANT'  AND instant_date IS NOT NULL)
        OR (period_kind = 'DURATION' AND start_date IS NOT NULL AND end_date IS NOT NULL)
        OR (period_kind = 'FOREVER')),

    CONSTRAINT ck_dimensional_coherente CHECK ((dim_count > 0) = is_dimensional)
);

CREATE INDEX IF NOT EXISTS ix_dfact_entidad   ON derived.fact (entity_key, qname);
CREATE INDEX IF NOT EXISTS ix_dfact_filing    ON derived.fact (accession_number);
CREATE INDEX IF NOT EXISTS ix_dfact_concepto  ON derived.fact (qname, period_kind);
CREATE INDEX IF NOT EXISTS ix_dfact_run       ON derived.fact (run_id);
-- para C-S04-005 (sin perdida): buscar un fact_id de origen
CREATE INDEX IF NOT EXISTS ix_dfact_fuentes   ON derived.fact USING GIN (source_fact_ids);

-- ---------------------------------------------------------------------
-- derived.normalize_conflict — lo que S04 NO pudo resolver sin elegir
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS derived.normalize_conflict (
    conflict_id     BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES engine.runs(run_id),
    kind            TEXT NOT NULL
        CHECK (kind IN ('CONTEXTO_CONTRADICTORIO','VALOR_SIN_DESEMPATE',
                        'UNIDAD_DESCONOCIDA','IDENTIDAD_SIN_RESOLVER')),
    accession_number TEXT,
    qname           TEXT,
    context_id      TEXT,
    detalle         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dconf_run ON derived.normalize_conflict (run_id, kind);

-- ---------------------------------------------------------------------
-- Permisos del rol de la aplicacion (F-025: no es superusuario, no borra)
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA derived TO catalaxia_engine;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES    IN SCHEMA derived TO catalaxia_engine;
GRANT USAGE, SELECT           ON ALL SEQUENCES IN SCHEMA derived TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA derived
    GRANT SELECT, INSERT, UPDATE ON TABLES TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA derived
    GRANT USAGE, SELECT ON SEQUENCES TO catalaxia_engine;
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
