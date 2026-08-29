-- =====================================================================
-- 018_f031_huerfanas_de_s03.sql
-- =====================================================================
-- F-031: F-009 sigue vivo en S03. Al re-correr S03 para cerrar F-026, cada
-- intento fallido dejo una corrida en RUNNING para siempre, porque S03 usa
-- `start_run`/`finish_run` sueltos y no `run_scope()`.
--
-- Las 3 corridas, con su causa documentada (tenemos el traceback de cada una):
--
--   778bc9718a4844c1ba20a4ce89d52b74  22:08:41
--       psycopg2.errors.InsufficientPrivilege: permission denied for database
--       catalaxia — `apply_migrations` corria DDL con el rol de la aplicacion
--       (F-027, ya corregido).
--
--   875ba2eb6a5a41a0961be2bad6872b18  22:10:35
--       InsufficientPrivilege: permission denied for table facts — la 011 le
--       nego DELETE a `parsed.*`, que es regenerable (corregido en la 016).
--
--   bdb984a38ea4423585a554971e2610ea  22:12:23
--       QueryCanceled: statement timeout — validacion de integridad
--       facts<->contexts sin estadisticas frescas tras el replace-all (F-028).
--
-- Las tres: traza `READY|RUNNING`, 0 reports, 0 checkpoints, sin sesion viva.
-- Evidencia de abandono completa. Se cierran ABORTED.
--
-- Contraste con la corrida que SI completo, e040bd08d04946218d2bfb560168bf24:
-- traza READY|RUNNING|VALIDATING|PASSED|CHECKPOINTED, report poblado, gate PASS.
--
-- La misma sesion produjo 5 corridas de S04 y NINGUNA quedo huerfana: S04 usa
-- run_scope(). La diferencia no es la suerte, es el patron.
-- =====================================================================

UPDATE engine.runs
   SET status = 'ABORTED', finished_at = COALESCE(finished_at, now())
 WHERE status = 'RUNNING'
   AND run_id IN ('778bc9718a4844c1ba20a4ce89d52b74',
                  '875ba2eb6a5a41a0961be2bad6872b18',
                  'bdb984a38ea4423585a554971e2610ea');

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM engine.runs WHERE status = 'RUNNING';
    IF n > 0 THEN
        RAISE EXCEPTION 'Quedan % corridas en RUNNING sin auditar.', n;
    END IF;
END $$;
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
