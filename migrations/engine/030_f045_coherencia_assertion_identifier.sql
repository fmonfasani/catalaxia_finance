-- =====================================================================
-- 030_f045_coherencia_assertion_identifier.sql  ·  F-045
-- =====================================================================
-- Contrato: docs/architecture/F045_CONTRACT.md
--
-- EL BLOQUEADOR
-- La politica "la autoridad es propiedad de la fuente, por tipo de
-- identificador" se verificaba en `assertion`, donde el tipo es una DECLARACION
-- OPCIONAL (`left_ref`, nullable). El tipo REAL se decide al insertar en
-- `identifier`, donde nadie lo volvia a mirar.
--
-- Reproducido con el rol OPERATIVO `catalaxia_engine` -- no admin -- sobre una
-- entidad limpia: 6 bypass sobre 10 ataques.
--
--   A1/A2/A3  LEGACY_DIM_ENTITY, DERIVED_RULE y CNV_PORTAL establecieron un
--             CUIT autoritativo, con la assertion sin left_ref.
--   A4        una assertion que declara CIK:SEC:... se reutilizo para
--             establecer un CUIT autoritativo  <-- "transformar CIK en CUIT".
--   A5        source_id correcto pero left_ref NULL.
--   A6        left_ref apuntando a otro valor.
--   A14       la assertion de la entidad A anclo a la entidad B.
--
-- El trigger existente sobre `assertion` SI funciona cuando la assertion
-- declara honestamente que establece (A9 y A10 fueron rechazados). Protege
-- contra el error, no contra la omision.
--
-- SIN CAMBIO DE SCHEMA
-- Todo lo necesario ya existe: el tipo en `identifier.id_type`, el vinculo en
-- `identifier.assertion_id`, la declaracion en `assertion.left_ref` con formato
-- canonico `TIPO:NAMESPACE:VALOR`, y la politica en `source.authoritative_for`.
-- Lo que faltaba era EVALUARLO EN EL MOMENTO CORRECTO.
--
-- Se implementa como TRIGGER, no como CHECK: la condicion depende de otras dos
-- tablas y un CHECK no puede consultarlas.
--
-- NO se otorgan privilegios nuevos. NO se usa el owner como parte de la
-- garantia. NO se reescribe ninguna fila.
-- =====================================================================

CREATE OR REPLACE FUNCTION identity_v1.fn_identifier_coherente_con_assertion()
RETURNS TRIGGER AS $$
DECLARE
    a_subject   TEXT;
    a_left      TEXT;
    a_entity    TEXT;
    a_method    TEXT;
    a_source    TEXT;
    s_nivel     TEXT;
    s_para      TEXT[];
    esperado    TEXT;
BEGIN
    -- Retirar un identificador SIEMPRE se permite. Sin esto, las 6 filas
    -- historicas de F-046 quedarian imposibles de retirar, y el mecanismo de
    -- supersede de F-041 se romperia.
    IF TG_OP = 'UPDATE' AND NEW.valid_to IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Solo se verifica lo que ESTABLECE identidad. Un CANDIDATE propone: no
    -- resuelve, no ancla, no contamina. Los 53 CUIT candidatos siguen entrando.
    IF NOT NEW.is_authoritative OR NEW.valid_to IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT subject_type, left_ref, entity_key, method, source_id
      INTO a_subject, a_left, a_entity, a_method, a_source
      FROM identity_v1.assertion WHERE assertion_id = NEW.assertion_id;

    -- (1) la assertion tiene que ser DE identificador
    IF a_subject IS DISTINCT FROM 'ENTITY_IDENTIFIER' THEN
        RAISE EXCEPTION
          'F-045: la assertion % es subject_type=% : no puede sostener el '
          'identificador autoritativo %:%:% .',
          NEW.assertion_id, COALESCE(a_subject, 'inexistente'),
          NEW.id_type, NEW.id_namespace, NEW.id_value;
    END IF;

    -- (2) left_ref NO puede faltar cuando se establece identidad.
    --     Este es el bypass A1/A2/A3/A5: sin left_ref, el trigger de
    --     `assertion` retornaba sin verificar nada.
    IF a_left IS NULL THEN
        RAISE EXCEPTION
          'F-045: la assertion % no declara que identificador establece '
          '(left_ref NULL) y se la usa para el autoritativo %:%:% . '
          'Una assertion que establece identidad declara cual.',
          NEW.assertion_id, NEW.id_type, NEW.id_namespace, NEW.id_value;
    END IF;

    -- (3) y tiene que declarar ESTE identificador, no otro.
    --     Igualdad exacta contra el formato canonico que ya usa
    --     engine/identity_v1.py:ref(). No es heuristica de texto libre.
    esperado := NEW.id_type || ':' || NEW.id_namespace || ':' || NEW.id_value;
    IF a_left <> esperado THEN
        RAISE EXCEPTION
          'F-045: tipo declarado distinto del real. La assertion % declara %, '
          'pero se la usa para establecer % . Una assertion sobre un CIK no '
          'establece un CUIT.',
          NEW.assertion_id, a_left, esperado;
    END IF;

    -- (4) y tiene que ser de LA MISMA entidad (bypass A14)
    IF a_entity IS DISTINCT FROM NEW.entity_key THEN
        RAISE EXCEPTION
          'F-045: la assertion % afirma sobre la entidad % y se la usa para '
          'anclar la entidad % . La provenance no se presta.',
          NEW.assertion_id, COALESCE(a_entity, 'ninguna'), NEW.entity_key;
    END IF;

    -- (5) la fuente tiene que ser autoritativa PARA ESTE TIPO.
    --     Se reverifica en el punto de uso: `source.authoritative_for` es
    --     mutable (F-044) y el chequeo de `assertion` pudo correr contra otra
    --     politica.
    IF a_method IS DISTINCT FROM 'HUMAN_DECISION' THEN
        SELECT authority_level, COALESCE(authoritative_for, '{}')
          INTO s_nivel, s_para
          FROM identity_v1.source WHERE source_id = a_source;

        IF s_nivel IS DISTINCT FROM 'AUTHORITATIVE' THEN
            RAISE EXCEPTION
              'F-045: la fuente % es % : no puede establecer el identificador '
              '%:%:% . Una fuente que no es autoritativa propone, no establece.',
              a_source, COALESCE(s_nivel, 'desconocida'),
              NEW.id_type, NEW.id_namespace, NEW.id_value;
        END IF;

        IF NOT (NEW.id_type = ANY (s_para)) THEN
            RAISE EXCEPTION
              'F-045: la fuente % es autoritativa para % pero NO para % : no '
              'puede establecer %:%:% .',
              a_source, s_para, NEW.id_type,
              NEW.id_type, NEW.id_namespace, NEW.id_value;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_identifier_coherente_con_assertion ON identity_v1.identifier;
CREATE TRIGGER tg_identifier_coherente_con_assertion
    BEFORE INSERT OR UPDATE ON identity_v1.identifier
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_identifier_coherente_con_assertion();

COMMENT ON FUNCTION identity_v1.fn_identifier_coherente_con_assertion() IS
  'F-045: la autoridad por tipo se verifica DONDE EL TIPO EXISTE. El trigger '
  'gemelo sobre `assertion` (tg_fuente_autoritativa_para_el_tipo) sigue vigente '
  'como rechazo temprano y para bridges; este cubre el punto de uso, que es el '
  'que se podia eludir dejando left_ref en NULL. Ver F045_CONTRACT.md.';

COMMENT ON COLUMN identity_v1.assertion.left_ref IS
  'Referencia canonica TIPO:NAMESPACE:VALOR del identificador que la assertion '
  'establece (o el extremo izquierdo de un bridge). Nullable por compatibilidad '
  'con assertions que no establecen identidad, PERO obligatoria de hecho para '
  'toda assertion que sostenga un identificador autoritativo: lo exige '
  'tg_identifier_coherente_con_assertion (F-045).';
