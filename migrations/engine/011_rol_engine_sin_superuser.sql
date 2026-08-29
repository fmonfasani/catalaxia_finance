-- =====================================================================
-- 011_rol_engine_sin_superuser.sql  ·  cierra F-025
-- =====================================================================
-- Las garantias de F-015 (inmutabilidad) y F-017 (no se borra) son TRIGGERS.
-- Un superusuario los desactiva con `SET session_replication_role = replica`.
-- Mientras el engine se conecte como `catalaxia` (superusuario), todo lo que
-- se certifico en el ciclo 6 es revocable por accidente: alcanza un script que
-- copie el patron de limpieza de los tests.
--
-- Esto no se arregla con mas constraints. Es un problema de privilegios.
--
-- Se separan tres identidades de conexion:
--
--   catalaxia          superusuario. SOLO migraciones y arnes de tests.
--   catalaxia_engine   la aplicacion. NOSUPERUSER, sin DELETE, sin TRUNCATE.
--   catalaxia_market_ro lectura de los market_* en 5432 (ver F-001, migracion 012).
--
-- La password se asigna aparte, fuera del control de versiones:
--   ALTER ROLE catalaxia_engine WITH LOGIN PASSWORD '...';
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalaxia_engine') THEN
        CREATE ROLE catalaxia_engine NOSUPERUSER NOCREATEDB NOCREATEROLE
                                     NOINHERIT NOLOGIN NOREPLICATION NOBYPASSRLS;
    ELSE
        ALTER ROLE catalaxia_engine NOSUPERUSER NOCREATEDB NOCREATEROLE
                                    NOREPLICATION NOBYPASSRLS;
    END IF;
END $$;

GRANT CONNECT ON DATABASE catalaxia TO catalaxia_engine;

-- ---------------------------------------------------------------------
-- identity_v1 — el schema que se acaba de certificar.
-- SELECT/INSERT/UPDATE. NUNCA DELETE, NUNCA TRUNCATE.
-- (TRUNCATE no se puede GRANTear en Postgres: es privilegio del owner, y el
--  owner sigue siendo `catalaxia`. catalaxia_engine no puede truncar.)
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA identity_v1 TO catalaxia_engine;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES    IN SCHEMA identity_v1 TO catalaxia_engine;
GRANT USAGE, SELECT           ON ALL SEQUENCES IN SCHEMA identity_v1 TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA identity_v1
    GRANT SELECT, INSERT, UPDATE ON TABLES TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA identity_v1
    GRANT USAGE, SELECT ON SEQUENCES TO catalaxia_engine;

-- el catalogo de fuentes es de solo lectura para la aplicacion: agregar una
-- fuente (y con ella un nivel de autoridad) es una decision de arquitectura
REVOKE INSERT, UPDATE ON identity_v1.source FROM catalaxia_engine;

-- ---------------------------------------------------------------------
-- Resto de los schemas del engine: la aplicacion escribe, pero no borra.
-- El DELETE se reserva para operaciones administrativas explicitas.
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA engine, fetch_raw, parsed, identity, public TO catalaxia_engine;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA engine, fetch_raw, parsed, identity
    TO catalaxia_engine;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA engine, fetch_raw, parsed, identity
    TO catalaxia_engine;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO catalaxia_engine;

ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA engine, fetch_raw, parsed, identity
    GRANT SELECT, INSERT, UPDATE ON TABLES TO catalaxia_engine;
ALTER DEFAULT PRIVILEGES FOR ROLE catalaxia IN SCHEMA engine, fetch_raw, parsed, identity
    GRANT USAGE, SELECT ON SEQUENCES TO catalaxia_engine;

-- ---------------------------------------------------------------------
-- Lo que NO se otorga, y por que:
--   DELETE      la procedencia no se borra (F-017)
--   TRUNCATE    idem, y ademas evade los triggers de fila
--   CREATE      el schema lo cambian las migraciones, no la aplicacion
--   SUPERUSER   sin el, `SET session_replication_role` falla y los triggers
--               de F-015/F-017 dejan de ser opcionales
-- ---------------------------------------------------------------------
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
