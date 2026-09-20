-- =====================================================================
-- CICLO 5 — PASADA 2: desambiguar resultados dudosos de la pasada 1
-- =====================================================================
-- Motivo: tres resultados de la pasada 1 no son concluyentes.
--
--   12b / 13c  usaban un CTE que cerraba la assertion y la borraba/modificaba
--              en la MISMA sentencia. En Postgres las dos ramas del CTE ven el
--              mismo snapshot, asi que la segunda pudo no haber tocado ninguna
--              fila y "pasar" de forma vacua. Se rehace en sentencias separadas.
--
--   11d        fue RECHAZADO por 'ux_entity_un_autoritativo_por_tipo' (GGAL ya
--              tenia CIK), no por un control de formato. No prueba nada sobre
--              validacion de CIK. Se rehace sobre una entidad SIN CIK.
--
-- Todo se revierte.
-- =====================================================================
\set QUIET on
\pset pager off
SET client_min_messages TO WARNING;
BEGIN;

CREATE OR REPLACE FUNCTION pg_temp.atacar(nro text, titulo text, cuerpo text)
RETURNS void AS $fn$
BEGIN
    BEGIN
        EXECUTE cuerpo;
        RAISE EXCEPTION 'SENTINELA_ACEPTADO';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'SENTINELA_ACEPTADO' THEN
            RAISE WARNING '[HUECO] %  %  -> ACEPTADO', nro, titulo;
        ELSE
            RAISE WARNING '[OK]    %  %  -> RECHAZADO: %', nro, titulo,
                          left(replace(SQLERRM, chr(10), ' '), 100);
        END IF;
    END;
END;
$fn$ LANGUAGE plpgsql;

-- entidad limpia del auditor: sin CIK, sin CUIT, sin LEI
INSERT INTO identity_v1.entity (entity_key, preferred_name, country)
VALUES ('E000000000000000000000000AA','SOCIEDAD DE PRUEBA DEL AUDITOR','AR');

CREATE OR REPLACE FUNCTION pg_temp.a_ok(lref text) RETURNS bigint AS $$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, left_ref, relationship, method, confidence, status,
     source_id, source_record, evidence, resolved_by)
  VALUES ('ENTITY_IDENTIFIER','E000000000000000000000000AA', lref,'BELONGS_TO',
          'REGULATORY_DOCUMENT','AUTHORITATIVE','VERIFIED','SEC_20F','auditoria/ciclo5-p2',
          'cita del auditor','auditor:ciclo5')
  RETURNING assertion_id;
$$ LANGUAGE sql;

\echo ''
\echo '### VALIDACION DE FORMATO EN LA BASE (entidad sin identificadores previos) ###'

SELECT pg_temp.atacar('P2-01','CIK = "YPF" (texto, no digitos)      ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000AA','CIK','SEC','YPF',true,pg_temp.a_ok('CIK:SEC:YPF'))
$q$);

SELECT pg_temp.atacar('P2-02','CIK = "42" (sin zero-padding)        ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000AA','CIK','SEC','42',true,pg_temp.a_ok('CIK:SEC:42'))
$q$);

SELECT pg_temp.atacar('P2-03','CUIT = "no-soy-un-cuit"              ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000AA','CUIT','AFIP','no-soy-un-cuit',true,pg_temp.a_ok('c1'))
$q$);

SELECT pg_temp.atacar('P2-04','CUIT = "99999999999" (checksum malo) ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000AA','CUIT','AFIP','99999999999',true,pg_temp.a_ok('c2'))
$q$);

SELECT pg_temp.atacar('P2-05','LEI = "no-es-un-lei"                 ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000AA','LEI','GLEIF','no-es-un-lei',true,pg_temp.a_ok('l1'))
$q$);

SELECT pg_temp.atacar('P2-06','CUIT con guiones "30-54668997-9"     ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000AA','CUIT','AFIP','30-54668997-9',true,pg_temp.a_ok('c3'))
$q$);

\echo ''
\echo '### INMUTABILIDAD HISTORICA: sentencias SEPARADAS, no CTE ###'

-- se crea una assertion propia y se la cierra en una sentencia aparte
DO $$
DECLARE vieja bigint; nueva bigint;
BEGIN
    vieja := pg_temp.a_ok('CIK:SEC:0000000001');
    nueva := pg_temp.a_ok('CIK:SEC:0000000002');
    UPDATE identity_v1.assertion SET valid_to = now(), superseded_by = nueva
     WHERE assertion_id = vieja;
    PERFORM set_config('audit.vieja', vieja::text, false);
    RAISE WARNING '   (preparado: assertion % cerrada, superseded_by=%)', vieja, nueva;
END $$;

SELECT pg_temp.atacar('P2-07','MODIFICAR assertion historica (separada)', format($q$
  UPDATE identity_v1.assertion SET evidence='reescrita por el atacante'
   WHERE assertion_id = %s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('P2-08','BORRAR assertion historica (separada)   ', format($q$
  DELETE FROM identity_v1.assertion WHERE assertion_id = %s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('P2-09','cambiar status de historica a REJECTED  ', format($q$
  UPDATE identity_v1.assertion SET status='REJECTED' WHERE assertion_id = %s
$q$, current_setting('audit.vieja')));

\echo ''
\echo '### CADENA DE SUCESION ###'

SELECT pg_temp.atacar('P2-10','superseded_by apuntando a si misma      ', format($q$
  UPDATE identity_v1.assertion SET superseded_by = assertion_id WHERE assertion_id = %s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('P2-11','cerrar una assertion con valid_to en el pasado remoto', $q$
  UPDATE identity_v1.assertion SET valid_to = '1900-01-01'
   WHERE assertion_id = (SELECT min(assertion_id) FROM identity_v1.assertion
                          WHERE status='VERIFIED' AND valid_to IS NULL)
$q$);

ROLLBACK;

\echo ''
\echo '### ESTADO POSTERIOR (debe ser identico al inicial) ###'
SELECT (SELECT count(*) FROM identity_v1.entity) AS entidades,
       (SELECT count(*) FROM identity_v1.assertion) AS assertions,
       (SELECT count(*) FROM identity_v1.identifier) AS identifiers;
