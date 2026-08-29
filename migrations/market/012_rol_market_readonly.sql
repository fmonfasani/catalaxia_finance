-- =====================================================================
-- 012_rol_market_readonly.sql  ·  cierra F-001 (barrera de privilegios)
-- =====================================================================
-- Se aplica en la base de PRODUCCION (5432), donde viven los market_*.
--
-- F-001: cada script de Market abria psycopg2.connect(...) con DB_PORT por
-- defecto 5432 y credenciales de escritura. Un `python m2_fetch_engine.py` sin
-- variables de entorno escribia en la base viva. `m6_scale.py` escala a 584
-- instrumentos por esa misma via.
--
-- La guarda de codigo esta en scripts/market/market_db.py. Esto es la segunda
-- barrera, la que no depende de que el codigo este bien escrito.
--
-- ADITIVO: no revoca nada de `catalaxia`. La API y el dashboard siguen igual.
-- Lo que cambia es cual es el rol POR DEFECTO de los scripts de Market.
--
-- La password se asigna aparte, fuera del control de versiones.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalaxia_market_ro') THEN
        CREATE ROLE catalaxia_market_ro NOSUPERUSER NOCREATEDB NOCREATEROLE
                                        NOINHERIT NOLOGIN NOREPLICATION NOBYPASSRLS;
    ELSE
        ALTER ROLE catalaxia_market_ro NOSUPERUSER NOCREATEDB NOCREATEROLE
                                       NOREPLICATION NOBYPASSRLS;
    END IF;
END $$;

GRANT CONNECT ON DATABASE catalaxia TO catalaxia_market_ro;
GRANT USAGE   ON SCHEMA public      TO catalaxia_market_ro;

-- SELECT y nada mas. Ni INSERT, ni UPDATE, ni DELETE, ni TRUNCATE.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO catalaxia_market_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO catalaxia_market_ro;

-- cinturon y tiradores: aunque alguien le otorgue INSERT por error, toda
-- transaccion de este rol nace de solo lectura
ALTER ROLE catalaxia_market_ro SET default_transaction_read_only = on;
