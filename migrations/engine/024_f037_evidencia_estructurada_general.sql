-- =====================================================================
-- 024_f037_evidencia_estructurada_general.sql  ·  cierra F-037
-- =====================================================================
-- Contrato: docs/architecture/F037_CONTRATO.md
--
-- F-037 resulto ser MAS ANCHO que el finding original. Reproducido con el rol
-- operativo `catalaxia_engine`:
--
--   SEC_20F           + source_facts NULL -> ACEPTADO
--   AFIP              + source_facts NULL -> ACEPTADO
--   SEC_REGISTRY      + CUIT autoritativo -> ACEPTADO  (!! su authoritative_for
--                                                        es {CIK}, no incluye CUIT)
--   LEGACY_DIM_ENTITY + CUIT autoritativo -> ACEPTADO  (!! es CORROBORATING)
--
-- La matriz fuente x tipo de identificador vivia SOLO en Python
-- (`source_authority()`). La base guardaba `identity_v1.source.authoritative_for`
-- y no la usaba para nada.
--
-- DOS MECANISMOS, porque son dos preguntas distintas:
--   (1) ¿puede esta fuente establecer este tipo? -> depende de otra tabla
--       => TRIGGER. General: aplica a CIK, LEI y CUIT, no solo a CUIT.
--   (2) ¿declaro la evidencia minima?            -> depende solo de la fila
--       => CHECK.
--
-- La base valida LA ESTRUCTURA DECLARADA de la evidencia, nunca la verdad
-- externa del documento. No sabe si el 20-F dice lo que la assertion afirma;
-- si puede exigir que la assertion diga EN QUE accession y EN QUE seccion lo
-- dice, para que un tercero lo abra y lo verifique.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. La autoridad de la fuente se verifica CONTRA EL CATALOGO, no en Python.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.fn_fuente_autoritativa_para_el_tipo()
RETURNS TRIGGER AS $$
DECLARE
    tipo  TEXT;
    nivel TEXT;
    para  TEXT[];
BEGIN
    -- solo interesa lo que ESTABLECE identidad
    IF NEW.status <> 'VERIFIED' OR NEW.subject_type <> 'ENTITY_IDENTIFIER'
       OR NEW.left_ref IS NULL THEN
        RETURN NEW;
    END IF;
    tipo := split_part(NEW.left_ref, ':', 1);

    -- una ratificacion humana no publica un registro: lo decide una persona,
    -- y eso ya lo gobiernan ck_humano_exige_autor y ck_humano_no_es_proceso
    IF NEW.method = 'HUMAN_DECISION' THEN
        RETURN NEW;
    END IF;

    SELECT authority_level, COALESCE(authoritative_for, '{}')
      INTO nivel, para
      FROM identity_v1.source WHERE source_id = NEW.source_id;

    IF nivel IS DISTINCT FROM 'AUTHORITATIVE' THEN
        RAISE EXCEPTION
          'La fuente % es % : no puede establecer el identificador % . '
          'Una fuente que no es autoritativa propone (CANDIDATE), no establece.',
          NEW.source_id, COALESCE(nivel, 'desconocida'), NEW.left_ref;
    END IF;

    IF NOT (tipo = ANY (para)) THEN
        RAISE EXCEPTION
          'La fuente % es autoritativa para % pero NO para % . No puede establecer % . '
          'La autoridad es propiedad de la fuente POR TIPO de identificador.',
          NEW.source_id, para, tipo, NEW.left_ref;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_fuente_autoritativa_para_el_tipo
    BEFORE INSERT OR UPDATE ON identity_v1.assertion
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_fuente_autoritativa_para_el_tipo();

-- ---------------------------------------------------------------------
-- 2. Evidencia estructurada minima por fuente, para todo CUIT establecido.
--    Reemplaza al CHECK de F-036, que solo cubria GLEIF. No lo relaja:
--    conserva su regla textual y le suma SEC_20F, AFIP y el caso humano.
-- ---------------------------------------------------------------------
ALTER TABLE identity_v1.assertion DROP CONSTRAINT IF EXISTS ck_gleif_cuit_declara_autoridad;

ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_cuit_exige_evidencia_estructurada CHECK (
    NOT (left_ref LIKE 'CUIT:%' AND status = 'VERIFIED')
    OR CASE source_id
         WHEN 'GLEIF' THEN
              COALESCE(source_facts ->> 'registeredAt', '') IN ('RA000009', 'RA000010')
              AND COALESCE(source_facts ->> 'registeredAs', '') <> ''
         WHEN 'SEC_20F' THEN
              COALESCE(source_facts ->> 'accession', '') <> ''
              AND COALESCE(source_facts ->> 'seccion', '') <> ''
         WHEN 'AFIP' THEN
              COALESCE(source_facts ->> 'constancia', '') <> ''
         WHEN 'HUMAN' THEN
              COALESCE(source_facts ->> 'reviewer', '') <> ''
              AND COALESCE(source_facts ->> 'decision_ref', '') <> ''
         ELSE false      -- ninguna otra fuente establece un CUIT
       END
  ) NOT VALID;
-- NOT VALID: hay 3 assertions GLEIF VERIFIED historicas sin source_facts
-- (assertion_id 4, 8, 16). Son inmutables por tg_assertion_inmutable y no se
-- reescribe el pasado para que encaje en un contrato nuevo. Igual que en F-036.

INSERT INTO engine.schema_migrations (filename)
VALUES ('024_f037_evidencia_estructurada_general.sql') ON CONFLICT DO NOTHING;
