-- 020_huerfana_f028.sql
-- El intento de S03 con el ANALYZE que Postgres salteaba en silencio
-- (WARNING: permission denied to analyze "facts", skipping it) murio en la
-- validacion de integridad por statement_timeout y quedo en RUNNING, otra vez
-- por F-031 (S03 no usa run_scope). Traza READY|RUNNING, 0 reports.
-- La corrida que SI completo tras la migracion 019 es e4080b82e0eb4ad9b4a142f03c7768dd.
UPDATE engine.runs SET status='ABORTED', finished_at=COALESCE(finished_at, now())
 WHERE status='RUNNING' AND run_id='3acbd1feb6ee4f19aaf468ccf43ed44f';
DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM engine.runs WHERE status='RUNNING';
  IF n > 0 THEN RAISE EXCEPTION 'Quedan % corridas RUNNING sin auditar.', n; END IF;
END $$;
INSERT INTO engine.schema_migrations (filename)
VALUES ('020_huerfana_f028.sql') ON CONFLICT DO NOTHING;
