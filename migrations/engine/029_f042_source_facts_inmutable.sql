-- =====================================================================
-- 029_f042_source_facts_inmutable.sql  ·  F-042 (hallado resolviendo F-041)
-- =====================================================================
-- Contrato: docs/architecture/F041_CONTRACT.md  §3, §8
--
-- EL HUECO
-- `fn_assertion_inmutable` enumera 16 columnas y `source_facts` NO esta entre
-- ellas. La columna se agrego en F-036 (migracion 022), despues de escribirse
-- el trigger (migracion 009), y nadie extendio la lista.
--
-- Verificado empiricamente: el owner puede MUTAR y hasta BORRAR el
-- `source_facts` de una assertion VERIFIED historica sin que nada lo impida.
--
--   UPDATE identity_v1.assertion SET source_facts = '{"inventado":"x"}'
--    WHERE assertion_id = 5;                                  -- ACEPTADO
--   UPDATE identity_v1.assertion SET source_facts = NULL ...;  -- ACEPTADO
--
-- POR QUE IMPORTA AHORA
-- Ese es el camino barato para "cerrar" F-041: un UPDATE sobre las 7 y listo.
-- Es exactamente lo que el contrato prohibe -- reescribir el pasado para
-- satisfacer un contrato nuevo. Mientras el hueco exista, la disciplina de
-- re-afirmacion es decorativa: cualquiera puede saltearsela y ningun control
-- lo detectaria, porque la fila resultante es indistinguible de una legitima.
--
-- ALCANCE REAL
-- El rol de aplicacion `catalaxia_engine` NO llega al hueco: su GRANT sobre
-- `assertion` es solo (valid_to, superseded_by). El agujero esta en el TRIGGER,
-- que es la capa que deberia ser la ultima linea -- y por la que corren las
-- migraciones.
--
-- QUE HACE ESTA MIGRACION
-- Agrega `source_facts` a los hechos inmutables. No toca ninguna fila.
-- La re-afirmacion de F-041 sigue siendo posible porque INSERTA assertions
-- nuevas y solo actualiza `valid_to`/`superseded_by` en las viejas, que el
-- trigger permite explicitamente.
-- =====================================================================

CREATE OR REPLACE FUNCTION identity_v1.fn_assertion_inmutable()
RETURNS TRIGGER AS $$
BEGIN
    -- los hechos: jamas mutan, este la assertion vigente o cerrada.
    -- `source_facts` ES un hecho afirmado: es la evidencia estructurada que
    -- sostiene la assertion. F-042.
    IF ROW(NEW.assertion_id, NEW.subject_type, NEW.entity_key, NEW.left_ref,
           NEW.right_ref, NEW.relationship, NEW.method, NEW.confidence,
           NEW.status, NEW.source_id, NEW.source_record, NEW.evidence,
           NEW.resolved_by, NEW.resolution_reason, NEW.valid_from, NEW.created_at,
           NEW.source_facts)
       IS DISTINCT FROM
       ROW(OLD.assertion_id, OLD.subject_type, OLD.entity_key, OLD.left_ref,
           OLD.right_ref, OLD.relationship, OLD.method, OLD.confidence,
           OLD.status, OLD.source_id, OLD.source_record, OLD.evidence,
           OLD.resolved_by, OLD.resolution_reason, OLD.valid_from, OLD.created_at,
           OLD.source_facts)
    THEN
        RAISE EXCEPTION
          'Assertion %: los hechos afirmados son inmutables (status=% valid_to=%). '
          'Para corregir, cree una assertion nueva y supersedala; no la edite.',
          OLD.assertion_id, OLD.status, OLD.valid_to;
    END IF;

    -- cerrar: una sola vez, y nunca reabrir
    IF OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to THEN
        RAISE EXCEPTION
          'Assertion % ya fue cerrada el %: no puede reabrirse ni re-fecharse.',
          OLD.assertion_id, OLD.valid_to;
    END IF;

    -- encadenar: una sola vez
    IF OLD.superseded_by IS NOT NULL AND NEW.superseded_by IS DISTINCT FROM OLD.superseded_by THEN
        RAISE EXCEPTION
          'Assertion % ya fue supersedida por %: la cadena no se reescribe.',
          OLD.assertion_id, OLD.superseded_by;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON COLUMN identity_v1.assertion.source_facts IS
  'Evidencia estructurada: cada clave sale LITERALMENTE del artefacto primario. '
  'Es un hecho afirmado, no un anexo: inmutable como el resto (F-042). Para '
  'agregarla a una assertion historica hay que re-afirmar, no editar. '
  'Ver F041_CONTRACT.md.';
