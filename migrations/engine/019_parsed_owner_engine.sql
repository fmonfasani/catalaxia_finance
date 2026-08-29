-- =====================================================================
-- 019_parsed_owner_engine.sql  ·  completa F-028
-- =====================================================================
-- El ANALYZE agregado a S03 no servia: Postgres NO falla cuando un rol sin
-- privilegio analiza una tabla, la SALTEA con un warning y devuelve exito.
--
--     WARNING:  permission denied to analyze "facts", skipping it
--     ANALYZE
--
-- S03 corria las 8 sentencias en 0,01 s creyendo haber actualizado las
-- estadisticas, y la validacion de integridad seguia cayendo por timeout.
-- Un fix que no arregla nada y ademas parece funcionar.
--
-- CRITERIO (continuidad de la 016): `parsed.*` es el area de trabajo de S03.
-- S03 la vacia y la reconstruye entera desde el RAW en cada corrida. Que su
-- dueño sea el rol de la aplicacion es coherente: ANALYZE, DELETE y setval
-- sobre un artefacto regenerable no son privilegios peligrosos.
--
-- Lo que NO cambia de dueño, y sigue siendo de `catalaxia`:
--   identity_v1.*  procedencia de identidad
--   engine.*       bitacora de corridas y checkpoints
--   derived.*      salida de S04 (upsert, nunca replace-all)
--   fetch_raw.*    el RAW
-- =====================================================================

DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'parsed' LOOP
        EXECUTE format('ALTER TABLE parsed.%I OWNER TO catalaxia_engine', t.tablename);
    END LOOP;
    FOR t IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'parsed' LOOP
        EXECUTE format('ALTER SEQUENCE parsed.%I OWNER TO catalaxia_engine', t.sequencename);
    END LOOP;
END $$;

-- el schema sigue siendo de catalaxia: la aplicacion no crea ni borra tablas
GRANT USAGE ON SCHEMA parsed TO catalaxia_engine;
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
