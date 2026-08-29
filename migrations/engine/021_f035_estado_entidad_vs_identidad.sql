-- =====================================================================
-- 021_f035_estado_entidad_vs_identidad.sql  ·  cierra F-035
-- =====================================================================
-- F-035 se descubrio con una escritura DIRECTA a la base (mutacion M7 del
-- ciclo 4B) y se reprodujo asi:
--
--   INSERT INTO identity_v1.identifier (...) VALUES (<entidad MERGED>, 'CIK', ...)
--   -> ACEPTADO
--
-- Una entidad fusionada en otra volvia a adquirir identidad propia. No producia
-- contaminacion entre entidades activas —los indices unicos lo siguen
-- impidiendo— pero dejaba evidencia colgada de una entidad muerta, invisible
-- para cualquier consulta que filtre por ACTIVE.
--
-- POLITICA (documentada en IDENTITY_V1_SCHEMA.md seccion 8):
--   ACTIVE       si   la entidad operativa
--   PROVISIONAL  si   existe sin identidad; adquirirla es su transicion esperada
--   MERGED       NO   su identidad ya migro a merged_into_key
--   DISSOLVED    NO   dejo de existir; conserva los historicos, no adquiere nuevos
--
-- Se implementa como TRIGGER y no como CHECK porque la condicion depende de
-- otra tabla. Y por eso mismo resiste la escritura directa, que es como se
-- encontro el defecto.
--
-- DOS guardas, porque una sola deja la otra puerta abierta:
--   (1) sobre identifier -> una entidad muerta no adquiere identidad
--   (2) sobre entity     -> una entidad con identidad vigente no se puede matar
--                           sin retirar o migrar esa identidad primero
-- Sin (2) se llega al mismo estado incoherente por el otro lado: primero se
-- cargan los identificadores y despues se fusiona la entidad.
-- =====================================================================

CREATE OR REPLACE FUNCTION identity_v1.fn_identidad_exige_entidad_viva()
RETURNS TRIGGER AS $$
DECLARE estado TEXT; destino TEXT;
BEGIN
    IF NOT NEW.is_authoritative THEN
        RETURN NEW;                      -- una propuesta CANDIDATE no establece identidad
    END IF;
    SELECT entity_status, merged_into_key INTO estado, destino
      FROM identity_v1.entity WHERE entity_key = NEW.entity_key;
    IF estado IN ('MERGED', 'DISSOLVED') THEN
        RAISE EXCEPTION
          'La entidad % esta en estado %: no puede adquirir el identificador '
          'autoritativo %:%:%. %',
          NEW.entity_key, estado, NEW.id_type, NEW.id_namespace, NEW.id_value,
          CASE WHEN destino IS NOT NULL
               THEN 'Su identidad ya migro a ' || destino || '; afirmelo alli.'
               ELSE 'Una entidad disuelta conserva sus identificadores historicos '
                    'pero no adquiere nuevos.' END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_identidad_exige_entidad_viva
    BEFORE INSERT OR UPDATE ON identity_v1.identifier
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_identidad_exige_entidad_viva();

-- ---------------------------------------------------------------------
-- Guarda simetrica: no se mata una entidad que todavia sostiene identidad.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.fn_no_matar_entidad_con_identidad()
RETURNS TRIGGER AS $$
DECLARE n INT;
BEGIN
    IF NEW.entity_status NOT IN ('MERGED', 'DISSOLVED')
       OR OLD.entity_status = NEW.entity_status THEN
        RETURN NEW;
    END IF;
    SELECT count(*) INTO n FROM identity_v1.identifier
     WHERE entity_key = NEW.entity_key AND is_authoritative AND valid_to IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION
          'La entidad % sostiene % identificador(es) autoritativo(s) vigente(s): '
          'no puede pasar a %. Retirelos (valid_to) o migrelos a la entidad '
          'destino antes de fusionarla.', NEW.entity_key, n, NEW.entity_status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_no_matar_entidad_con_identidad
    BEFORE UPDATE ON identity_v1.entity
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_no_matar_entidad_con_identidad();

INSERT INTO engine.schema_migrations (filename)
VALUES ('021_f035_estado_entidad_vs_identidad.sql') ON CONFLICT DO NOTHING;
