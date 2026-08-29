-- =====================================================================
-- 009_identity_v1_hardening.sql
-- =====================================================================
-- Cierra los blockers del CICLO 5:
--
--   F-015  una assertion VIGENTE podia reescribirse sin dejar historia
--   F-016  el piloto atribuia a una persona una decision que nunca tomo
--   F-017  procedencia historica y gobernanza eran borrables sin rastro
--   F-018  sin validacion de formato ni checksum en la base
--
-- Y de paso, por ser una linea cada uno en la misma migracion:
--   F-021  instrument.assertion_id nullable
--   F-022  superseded_by auto-referenciable, valid_to retro-fechable
--
-- ORDEN CRITICO: los pasos de DATOS van ANTES de instalar las guardas.
-- Una vez instaladas, la procedencia fabricada ya no se puede corregir —
-- que es exactamente el punto.
--
-- NO toca SEC, CNV ni Market.
-- =====================================================================

-- =====================================================================
-- PARTE A — CORRECCION DE DATOS (antes de las guardas)
-- =====================================================================

-- ---------------------------------------------------------------------
-- A.0 Retirar la guarda vieja para poder purgar la procedencia fabricada.
--     Es la unica ventana en la que esto es posible, y se cierra en B.5 con
--     una guarda estrictamente mas fuerte.
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS tg_no_borrar_vigente ON identity_v1.assertion;

-- ---------------------------------------------------------------------
-- A.1 (F-016) Retirar los identificadores CUIT que colgaban de un puente
--     CIK<->LEI fabricado.
--
--     Los 4 bridges del piloto decian method=HUMAN_DECISION,
--     resolved_by='fmonfasani', todos en el mismo microsegundo. Los escribio
--     un script en bucle. Ninguna persona los ratifico.
--
--     Sin puente demostrado, la cadena CIK -> LEI -> CUIT tiene un eslabon no
--     probado (G5). Los CUIT que dependian de el se retiran: no se borran, se
--     cierran con valid_to, y quedan legibles como lo que fueron.
-- ---------------------------------------------------------------------
UPDATE identity_v1.identifier i
   SET valid_to = now(), status = 'DISPUTED'
 WHERE i.id_type = 'CUIT'
   AND i.valid_to IS NULL
   AND EXISTS (
        SELECT 1 FROM identity_v1.assertion a
         WHERE a.subject_type = 'IDENTIFIER_BRIDGE'
           AND a.method = 'HUMAN_DECISION'
           AND a.resolved_by = 'fmonfasani'
           AND a.left_ref = 'CIK:SEC:' || (
               SELECT id_value FROM identity_v1.identifier c
                WHERE c.entity_key = i.entity_key AND c.id_type = 'CIK'
                  AND c.is_authoritative AND c.valid_to IS NULL));

-- ---------------------------------------------------------------------
-- A.2 (F-016) Purgar los bridges fabricados.
--
--     Se ELIMINAN, no se supersedan. Una assertion superseded sigue diciendo
--     "fmonfasani lo verifico el 2026-08-25" en el registro historico, y eso
--     nunca ocurrio: seria conservar una firma falsa en nombre de la
--     trazabilidad. La procedencia fabricada no es historia, es contaminacion.
--     Queda constancia del acto en esta migracion y en el DECISION_RECORD.
-- ---------------------------------------------------------------------
DELETE FROM identity_v1.assertion
 WHERE subject_type = 'IDENTIFIER_BRIDGE'
   AND method = 'HUMAN_DECISION'
   AND resolved_by = 'fmonfasani'
   AND source_record = 'docs/architecture/IDENTITY_DECISION_RECORD.md#G5';

-- ---------------------------------------------------------------------
-- A.3 (F-016) Abrir la review que corresponde: el puente necesita una
--     persona real. Esto es lo que el sistema deberia haber dicho desde el
--     principio, en vez de firmarlo solo.
-- ---------------------------------------------------------------------
INSERT INTO identity_v1.review (entity_key, candidate_identifiers, reason, evidence)
SELECT v.entity_key,
       jsonb_build_object('cik', v.cik, 'lei', v.lei, 'cuit_propuesto_via_gleif', v.cuit),
       'puente CIK<->LEI sin ratificar: ninguna fuente primaria lo publica (G5) '
       'y el piloto lo habia firmado automaticamente (F-016)',
       'ratificar con scripts/engine/identity_v1_ratificar.py'
  FROM identity_v1.v_entity_resolution v
 WHERE v.cik IS NOT NULL AND v.lei IS NOT NULL;

-- ---------------------------------------------------------------------
-- A.4 (F-021) Procedencia para los instrumentos que hoy no la tienen.
--     El catalogo de Market es la fuente; no establece identidad, la propone.
-- ---------------------------------------------------------------------
INSERT INTO identity_v1.source (source_id, descripcion, authority_level, authoritative_for, notas)
VALUES ('MARKET_CATALOG', 'market_instruments / market_symbol_mappings (5432)',
        'CORROBORATING', NULL,
        'Propone la relacion entidad<->instrumento. No establece identidad juridica. '
        'Ver F-014: ticker_canonico repite el ticker local en la fila del ADR.')
ON CONFLICT (source_id) DO NOTHING;

WITH nuevas AS (
    INSERT INTO identity_v1.assertion
        (subject_type, entity_key, left_ref, relationship, method, confidence, status,
         source_id, source_record, evidence, resolved_by)
    SELECT 'ENTITY_INSTRUMENT', i.entity_key, 'INSTRUMENT:' || i.instrument_key,
           'BELONGS_TO', 'LEGACY_IMPORT', 'WEAK', 'CANDIDATE',
           'MARKET_CATALOG', 'market_instruments.instrument_id=' || split_part(i.instrument_key, ':', 2),
           'market_instruments asocia el instrumento ' || i.instrument_key ||
           ' (' || i.exchange || ' ' || i.currency || ') a esta entidad',
           'proc:migracion_009'
      FROM identity_v1.instrument i
     WHERE i.assertion_id IS NULL
    RETURNING assertion_id, left_ref)
UPDATE identity_v1.instrument i
   SET assertion_id = n.assertion_id
  FROM nuevas n
 WHERE 'INSTRUMENT:' || i.instrument_key = n.left_ref;

-- =====================================================================
-- PARTE B — GUARDAS (a partir de aca, la correccion de datos ya no es posible)
-- =====================================================================

-- ---------------------------------------------------------------------
-- B.1 (F-018) Formato y digito verificador EN LA BASE.
--
--     Hasta ahora norm_cik/norm_cuit/cuit_valido vivian solo en Python. Una
--     escritura desde psql, otro proceso o un backfill inyectaba basura.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.cuit_valido(v text)
RETURNS boolean AS $$
DECLARE
    pesos int[] := ARRAY[5,4,3,2,7,6,5,4,3,2];
    s int := 0;
    r int;
    dv int;
BEGIN
    IF v IS NULL OR v !~ '^[0-9]{11}$' THEN
        RETURN false;
    END IF;
    FOR i IN 1..10 LOOP
        s := s + substr(v, i, 1)::int * pesos[i];
    END LOOP;
    r := 11 - (s % 11);
    dv := CASE WHEN r = 11 THEN 0 WHEN r = 10 THEN 9 ELSE r END;
    RETURN dv = substr(v, 11, 1)::int;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

ALTER TABLE identity_v1.identifier
  ADD CONSTRAINT ck_formato_identificador CHECK (
    CASE id_type
      WHEN 'CIK'  THEN id_value ~ '^[0-9]{10}$'
      WHEN 'CUIT' THEN identity_v1.cuit_valido(id_value)
      WHEN 'LEI'  THEN id_value ~ '^[0-9A-Z]{18}[0-9]{2}$'
      ELSE id_value <> '' AND id_value = btrim(id_value)
    END);

-- ---------------------------------------------------------------------
-- B.2 (F-016) Un proceso automatico no puede firmar como humano.
--     Convencion obligatoria: los procesos se identifican con el prefijo 'proc:'.
-- ---------------------------------------------------------------------
ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_humano_no_es_proceso CHECK (
    method <> 'HUMAN_DECISION' OR resolved_by NOT LIKE 'proc:%');

-- ---------------------------------------------------------------------
-- B.3 (F-022) Cadena de sucesion sana y linea de tiempo coherente.
-- ---------------------------------------------------------------------
ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_supersede_no_circular CHECK (superseded_by IS DISTINCT FROM assertion_id);

ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_vigencia_coherente CHECK (valid_to IS NULL OR valid_to >= valid_from);

-- ---------------------------------------------------------------------
-- B.4 (F-015) INMUTABILIDAD TOTAL de los hechos afirmados.
--
--     Antes la guarda era `IF OLD.valid_to IS NOT NULL OR OLD.status='REJECTED'`,
--     de modo que las filas VIGENTES —las que sostienen la identidad en
--     produccion— quedaban fuera. Se podia reescribir la evidencia, reapuntar
--     la assertion a otra entidad y promover REVIEW_REQUIRED -> VERIFIED.
--
--     Ahora: en CUALQUIER assertion, los hechos afirmados son inmutables. Lo
--     unico que puede cambiar es cerrarla (valid_to) y encadenarla
--     (superseded_by), y cada uno una sola vez. Corregir es supersedir.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.fn_assertion_inmutable()
RETURNS TRIGGER AS $$
BEGIN
    -- los hechos: jamas mutan, este la assertion vigente o cerrada
    IF ROW(NEW.assertion_id, NEW.subject_type, NEW.entity_key, NEW.left_ref,
           NEW.right_ref, NEW.relationship, NEW.method, NEW.confidence,
           NEW.status, NEW.source_id, NEW.source_record, NEW.evidence,
           NEW.resolved_by, NEW.resolution_reason, NEW.valid_from, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.assertion_id, OLD.subject_type, OLD.entity_key, OLD.left_ref,
           OLD.right_ref, OLD.relationship, OLD.method, OLD.confidence,
           OLD.status, OLD.source_id, OLD.source_record, OLD.evidence,
           OLD.resolved_by, OLD.resolution_reason, OLD.valid_from, OLD.created_at)
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

-- ---------------------------------------------------------------------
-- B.5 (F-017) La procedencia y la gobernanza NO se borran.
--
--     Antes solo se bloqueaba el DELETE de assertions vigentes VERIFIED o
--     CANDIDATE. Quedaban borrables: la historia cerrada, las assertions en
--     revision, y las tablas review y conflict enteras. Un sistema cuyo valor
--     es la auditabilidad permitia borrar la auditoria.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.fn_prohibir_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
      'DELETE prohibido en %.%: la procedencia no se borra. '
      'Cierre el registro (valid_to / estado terminal) en lugar de eliminarlo.',
      TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS identity_v1.fn_no_borrar_vigente();

CREATE TRIGGER tg_no_borrar_assertion BEFORE DELETE ON identity_v1.assertion
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_borrar_review    BEFORE DELETE ON identity_v1.review
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_borrar_conflict  BEFORE DELETE ON identity_v1.conflict
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_borrar_identifier BEFORE DELETE ON identity_v1.identifier
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_prohibir_delete();

-- ---------------------------------------------------------------------
-- B.6 (F-017) TRUNCATE evade los triggers de fila. Se bloquea tambien,
--     porque si no la proteccion anterior es decorativa: cualquier dueno de
--     la tabla vacia el historial con una sentencia.
--
--     Consecuencia buscada: el piloto ya no puede tener --reset. Debe ser
--     idempotente. Para reiniciar de cero en dev queda un unico camino, y es
--     deliberadamente ruidoso: DROP SCHEMA identity_v1 CASCADE + re-migrar.
-- ---------------------------------------------------------------------
CREATE TRIGGER tg_no_truncar_assertion BEFORE TRUNCATE ON identity_v1.assertion
    EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_truncar_review    BEFORE TRUNCATE ON identity_v1.review
    EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_truncar_conflict  BEFORE TRUNCATE ON identity_v1.conflict
    EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_truncar_identifier BEFORE TRUNCATE ON identity_v1.identifier
    EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
CREATE TRIGGER tg_no_truncar_entity    BEFORE TRUNCATE ON identity_v1.entity
    EXECUTE FUNCTION identity_v1.fn_prohibir_delete();
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
