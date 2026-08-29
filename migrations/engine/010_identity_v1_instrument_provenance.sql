-- =====================================================================
-- 010_identity_v1_instrument_provenance.sql  ·  cierra F-021
-- =====================================================================
-- La 009 ya pobló identity_v1.instrument.assertion_id para las filas que
-- estaban en NULL. Recién ahora se puede exigir la columna.
--
-- Afirmar "este instrumento pertenece a esta entidad" es una afirmación de
-- identidad tan fuerte como cualquier otra: es la que conecta un precio con
-- un emisor. Debe tener fuente, cita y autor, igual que un identificador.
-- =====================================================================

ALTER TABLE identity_v1.instrument
  ALTER COLUMN assertion_id SET NOT NULL;

INSERT INTO engine.schema_migrations (filename)
VALUES ('010_identity_v1_instrument_provenance.sql') ON CONFLICT DO NOTHING;
