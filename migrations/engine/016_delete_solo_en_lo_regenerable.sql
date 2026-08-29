-- =====================================================================
-- 016_delete_solo_en_lo_regenerable.sql
-- =====================================================================
-- Ajuste de criterio sobre la migracion 011 (F-025).
--
-- La 011 le nego DELETE a `catalaxia_engine` en TODOS los schemas, bajo el
-- lema "la procedencia no se borra". El lema es correcto; la aplicacion fue
-- demasiado ancha. S03 es replace-all por diseno: vacia `parsed.*` y lo
-- reconstruye desde el RAW. Con la 011 puesta, S03 no arranca:
--     psycopg2.errors.InsufficientPrivilege: permission denied for table facts
--
-- EL CRITERIO, explicito:
--   se puede borrar   lo que se reconstruye desde el RAW y no registra
--                     ni quien afirmo algo ni que paso
--   NO se puede       la procedencia de identidad, la bitacora de corridas,
--                     y el RAW mismo
--
--   parsed.*      DELETE SI   materializacion del XBRL; el RAW es la verdad
--   derived.*     DELETE NO   S04 hace upsert por fact_key; no necesita borrar
--   identity_v1.* DELETE NO   procedencia de identidad (F-017)
--   engine.*      DELETE NO   bitacora: runs, stage_runs, checkpoints
--   fetch_raw.*   DELETE NO   es el RAW
--
-- Borrar `parsed.facts` no destruye evidencia: destruye una copia. Borrar una
-- assertion o una corrida si destruye evidencia, y eso sigue prohibido.
-- =====================================================================

GRANT DELETE ON ALL TABLES IN SCHEMA parsed TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA parsed
    GRANT DELETE ON TABLES TO catalaxia_engine;

-- se reafirma lo que NO se otorga, para que quede en el registro
REVOKE DELETE ON ALL TABLES IN SCHEMA identity_v1, engine, fetch_raw, derived
    FROM catalaxia_engine;

INSERT INTO engine.schema_migrations (filename)
VALUES ('016_delete_solo_en_lo_regenerable.sql') ON CONFLICT DO NOTHING;
