-- =====================================================================
-- 036_staging_schema.sql  ·  schema de publicacion C12
-- =====================================================================
-- C12 (publisher.py) intercambia tablas en `staging` corriendo como
-- catalaxia_engine. Hasta ahora `staging` se creaba a mano en cada
-- instalacion (fuera de migraciones): una base limpia no podia correr la
-- cadena E2E certificada. Se registra aca con los privilegios que el rol
-- de aplicacion ya usa en produccion.
--
-- que se otorga y por que:
--   USAGE, CREATE        publisher crea staging.<target>__new__* y
--                        staging._publications como catalaxia_engine
--   DEFAULT PRIVILEGES   cualquier objeto que cree el owner (catalaxia)
--                        dentro de staging queda accesible al rol; los
--                        que crea el propio rol ya son suyos (owner)
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS staging;

GRANT USAGE, CREATE ON SCHEMA staging TO catalaxia_engine;

ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA staging
    GRANT ALL ON TABLES TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA staging
    GRANT USAGE, SELECT ON SEQUENCES TO catalaxia_engine;