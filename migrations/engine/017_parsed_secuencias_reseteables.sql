-- =====================================================================
-- 017_parsed_secuencias_reseteables.sql
-- =====================================================================
-- Continuacion del criterio de la 016. S03 es replace-all: vacia parsed.* y
-- reinicia las secuencias con setval(), que exige UPDATE sobre la secuencia,
-- no alcanza con USAGE+SELECT.
--
--     psycopg2.errors.InsufficientPrivilege:
--         permission denied for sequence facts_fact_id_seq
--
-- Se completa el permiso SOLO en `parsed`, que es el unico schema regenerable
-- desde el RAW. Las secuencias de identity_v1, engine, derived y fetch_raw
-- siguen sin UPDATE: ahi un setval reescribiria la numeracion de la evidencia.
-- =====================================================================

GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA parsed TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA parsed
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO catalaxia_engine;

REVOKE UPDATE ON ALL SEQUENCES IN SCHEMA identity_v1, engine, fetch_raw, derived
    FROM catalaxia_engine;

INSERT INTO engine.schema_migrations (filename)
VALUES ('017_parsed_secuencias_reseteables.sql') ON CONFLICT DO NOTHING;
