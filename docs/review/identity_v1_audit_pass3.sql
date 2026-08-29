-- =====================================================================
-- CICLO 6 — PASADA 3: verificacion post-hardening (009 + 010)
-- =====================================================================
-- DEFECTO DEL ARNES ANTERIOR, corregido aca:
--   Las pasadas 1 y 2 reportaban [HUECO] cuando el ataque no lanzaba
--   excepcion. Pero un UPDATE/DELETE que no matchea NINGUNA fila tampoco
--   lanza excepcion: pasaba por "aceptado" sin haber atacado nada.
--
--   Consecuencia concreta: en el ciclo 5 el ataque 12e ("borrar un conflict
--   abierto") se reporto como HUECO con la tabla conflict VACIA. Ese hallazgo
--   era falso y se corrige en este documento.
--
-- Este arnes exige BLANCO REAL: cada ataque declara cuantas filas debe tocar,
-- y si toca cero se reporta [NULO] en vez de [HUECO].
--
-- Ademas monta sus PROPIOS objetivos (dos entidades con CUIT autoritativo
-- vigente), en vez de depender del estado del piloto —que tras la migracion
-- 009 tiene los CUIT retirados y por lo tanto ya no sirve de blanco.
--
-- Todo se revierte.
-- =====================================================================
\set QUIET on
\pset pager off
SET client_min_messages TO WARNING;
BEGIN;

CREATE OR REPLACE FUNCTION pg_temp.atacar(nro text, titulo text, cuerpo text,
                                          esperado text DEFAULT 'RECHAZO')
RETURNS void AS $fn$
DECLARE tocadas bigint;
BEGIN
    BEGIN
        EXECUTE cuerpo;
        GET DIAGNOSTICS tocadas = ROW_COUNT;
        IF tocadas = 0 THEN
            RAISE WARNING '[NULO]  %  %  -> no toco ninguna fila: el ataque no probo nada',
                          nro, titulo;
        ELSIF esperado = 'RECHAZO' THEN
            RAISE WARNING '[HUECO] %  %  -> ACEPTADO (% filas)', nro, titulo, tocadas;
        ELSE
            RAISE WARNING '[OK]    %  %  -> aceptado, como debe ser', nro, titulo;
        END IF;
        RAISE EXCEPTION 'SENTINELA';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'SENTINELA' THEN
            NULL;                      -- ya se reporto arriba; el savepoint revierte
        ELSIF esperado = 'RECHAZO' THEN
            RAISE WARNING '[OK]    %  %  -> RECHAZADO: %', nro, titulo,
                          left(replace(SQLERRM, chr(10), ' '), 95);
        ELSE
            RAISE WARNING '[HUECO] %  %  -> RECHAZADO cuando debia aceptarse: %',
                          nro, titulo, left(SQLERRM, 80);
        END IF;
    END;
END;
$fn$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- Blancos propios del auditor: dos entidades con CUIT AUTORITATIVO VIGENTE.
-- Se usan CUIT reales y validos (YPF y CEPU), que es lo que exige la consigna.
-- ---------------------------------------------------------------------
INSERT INTO identity_v1.entity (entity_key, preferred_name, country) VALUES
  ('E000000000000000000000000A1','AUDITORIA · sustituta de YPF','AR'),
  ('E000000000000000000000000A2','AUDITORIA · sustituta de CEPU','AR');

CREATE OR REPLACE FUNCTION pg_temp.a_ok(ek text, lref text) RETURNS bigint AS $$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, left_ref, relationship, method, confidence, status,
     source_id, source_record, evidence, resolved_by)
  VALUES ('ENTITY_IDENTIFIER', ek, lref,'BELONGS_TO','REGULATORY_DOCUMENT',
          'AUTHORITATIVE','VERIFIED','SEC_20F','auditoria/ciclo6',
          'cita del auditor para montar el blanco','auditor:ciclo6')
  RETURNING assertion_id;
$$ LANGUAGE sql;

INSERT INTO identity_v1.identifier
  (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
VALUES
  ('E000000000000000000000000A1','CUIT','AFIP','30546689979',true,
   pg_temp.a_ok('E000000000000000000000000A1','CUIT:AFIP:30546689979')),
  ('E000000000000000000000000A2','CUIT','AFIP','33650305499',true,
   pg_temp.a_ok('E000000000000000000000000A2','CUIT:AFIP:33650305499'));

\echo ''
\echo '### A · EL ERROR HISTORICO, con blanco real (los 3 pares exigidos) ###'

SELECT pg_temp.atacar('A1','YPF + CUIT de CEPU (33650305499)  ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A1','CUIT','AFIP','33650305499',true,
          pg_temp.a_ok('E000000000000000000000000A1','x'))
$q$);

SELECT pg_temp.atacar('A2','CEPU + CUIT de YPF (30546689979)  ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A2','CUIT','AFIP','30546689979',true,
          pg_temp.a_ok('E000000000000000000000000A2','x'))
$q$);

SELECT pg_temp.atacar('A3','segundo CUIT autoritativo para la misma entidad', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A1','CUIT','AFIP','30657862068',true,
          pg_temp.a_ok('E000000000000000000000000A1','x'))
$q$);

SELECT pg_temp.atacar('A4','reapuntar un identifier vigente a otra entidad', $q$
  UPDATE identity_v1.identifier SET entity_key='E000000000000000000000000A2'
   WHERE id_type='CUIT' AND id_value='30546689979' AND valid_to IS NULL
$q$);

\echo ''
\echo '### B · F-018 · FORMATO Y CHECKSUM EN LA BASE ###'

SELECT pg_temp.atacar('B1','CUIT con checksum invalido (99999999999)', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A2','CUIT','AFIP','99999999999',true,
          pg_temp.a_ok('E000000000000000000000000A2','x'))
$q$);

SELECT pg_temp.atacar('B2','CUIT con guiones (30-54668997-9)  ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A2','CUIT','AFIP','30-54668997-9',true,
          pg_temp.a_ok('E000000000000000000000000A2','x'))
$q$);

SELECT pg_temp.atacar('B3','CIK = "YPF"                       ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A2','CIK','SEC','YPF',true,
          pg_temp.a_ok('E000000000000000000000000A2','x'))
$q$);

SELECT pg_temp.atacar('B4','CIK = "42" (sin zero-padding)     ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A2','CIK','SEC','42',true,
          pg_temp.a_ok('E000000000000000000000000A2','x'))
$q$);

SELECT pg_temp.atacar('B5','LEI = "no-es-un-lei"              ', $q$
  INSERT INTO identity_v1.identifier
    (entity_key,id_type,id_namespace,id_value,is_authoritative,assertion_id)
  VALUES ('E000000000000000000000000A2','LEI','GLEIF','no-es-un-lei',true,
          pg_temp.a_ok('E000000000000000000000000A2','x'))
$q$);

\echo ''
\echo '### C · F-016 · UN PROCESO NO FIRMA COMO HUMANO ###'

SELECT pg_temp.atacar('C1','proc: firmando HUMAN_DECISION     ', $q$
  INSERT INTO identity_v1.assertion
    (subject_type,left_ref,right_ref,relationship,method,confidence,status,
     source_id,source_record,evidence,resolved_by,resolution_reason)
  VALUES ('IDENTIFIER_BRIDGE','CIK:SEC:0000904851','LEI:GLEIF:5493003N7447U18U5U53',
          'SAME_ENTITY','HUMAN_DECISION','STRONG','VERIFIED','HUMAN','x',
          'cita','proc:un_script','porque si')
$q$);

SELECT pg_temp.atacar('C2','persona firmando HUMAN_DECISION   ', $q$
  INSERT INTO identity_v1.assertion
    (subject_type,left_ref,right_ref,relationship,method,confidence,status,
     source_id,source_record,evidence,resolved_by,resolution_reason)
  VALUES ('IDENTIFIER_BRIDGE','CIK:SEC:0000904851','LEI:GLEIF:5493003N7447U18U5U53',
          'SAME_ENTITY','HUMAN_DECISION','STRONG','VERIFIED','HUMAN','ratificacion',
          'evidencia de ambos lados','una.persona','ratificado')
$q$, 'ACEPTACION');

SELECT pg_temp.atacar('C3','¿quedan bridges firmados por una persona sin ratificar?', $q$
  INSERT INTO identity_v1.entity (entity_key, preferred_name)
  SELECT 'E0000000000000000000000FAK', 'no deberia entrar'
   WHERE EXISTS (SELECT 1 FROM identity_v1.assertion
                  WHERE method='HUMAN_DECISION' AND resolved_by='fmonfasani')
$q$);

\echo ''
\echo '### D · F-015 · INMUTABILIDAD DE LO VIGENTE ###'

SELECT pg_temp.atacar('D1','reescribir evidence de una assertion VIGENTE', $q$
  UPDATE identity_v1.assertion SET evidence='reescrita por el atacante'
   WHERE status='VERIFIED' AND valid_to IS NULL
$q$);

SELECT pg_temp.atacar('D2','reapuntar assertion vigente a otra entidad', $q$
  UPDATE identity_v1.assertion SET entity_key='E000000000000000000000000A2'
   WHERE entity_key='E000000000000000000000000A1'
$q$);

SELECT pg_temp.atacar('D3','promover REVIEW_REQUIRED -> VERIFIED  ', $q$
  UPDATE identity_v1.assertion SET status='VERIFIED'
   WHERE status='REVIEW_REQUIRED' AND valid_to IS NULL
$q$);

SELECT pg_temp.atacar('D4','cambiar source_id de una assertion vigente', $q$
  UPDATE identity_v1.assertion SET source_id='LEGACY_DIM_ENTITY'
   WHERE status='VERIFIED' AND valid_to IS NULL
$q$);

-- inmutabilidad de la historia, en sentencias SEPARADAS (no CTE)
DO $$
DECLARE vieja bigint; nueva bigint;
BEGIN
    vieja := pg_temp.a_ok('E000000000000000000000000A1','CIK:SEC:0000000001');
    nueva := pg_temp.a_ok('E000000000000000000000000A1','CIK:SEC:0000000002');
    UPDATE identity_v1.assertion SET valid_to=now(), superseded_by=nueva
     WHERE assertion_id=vieja;
    PERFORM set_config('audit.vieja', vieja::text, false);
END $$;

SELECT pg_temp.atacar('D5','modificar assertion HISTORICA     ', format($q$
  UPDATE identity_v1.assertion SET evidence='reescrita' WHERE assertion_id=%s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('D6','reabrir una assertion cerrada     ', format($q$
  UPDATE identity_v1.assertion SET valid_to=NULL WHERE assertion_id=%s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('D7','re-fechar el cierre               ', format($q$
  UPDATE identity_v1.assertion SET valid_to='1900-01-01' WHERE assertion_id=%s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('D8','superseded_by auto-referencia     ', format($q$
  UPDATE identity_v1.assertion SET superseded_by=assertion_id WHERE assertion_id=%s
$q$, current_setting('audit.vieja')));

\echo ''
\echo '### E · F-017 · NADA SE BORRA (con blanco real en cada tabla) ###'

SELECT pg_temp.atacar('E1','borrar assertion VIGENTE          ', $q$
  DELETE FROM identity_v1.assertion WHERE status='VERIFIED' AND valid_to IS NULL
$q$);

SELECT pg_temp.atacar('E2','borrar assertion HISTORICA        ', format($q$
  DELETE FROM identity_v1.assertion WHERE assertion_id=%s
$q$, current_setting('audit.vieja')));

SELECT pg_temp.atacar('E3','borrar assertion REVIEW_REQUIRED  ', $q$
  DELETE FROM identity_v1.assertion WHERE status='REVIEW_REQUIRED'
$q$);

SELECT pg_temp.atacar('E4','borrar una review ABIERTA         ', $q$
  DELETE FROM identity_v1.review WHERE status='OPEN'
$q$);

SELECT pg_temp.atacar('E5','borrar un identifier vigente      ', $q$
  DELETE FROM identity_v1.identifier WHERE is_authoritative AND valid_to IS NULL
$q$);

-- blanco real para conflict: se crea uno primero. En el ciclo 5 este ataque
-- corrio contra una tabla VACIA y por eso dio un HUECO falso.
INSERT INTO identity_v1.conflict (id_type,id_namespace,id_value,candidate_entity_keys,reason)
VALUES ('CUIT','AFIP','30546689979',
        '["E000000000000000000000000A1","E000000000000000000000000A2"]'::jsonb,
        'conflicto sembrado por el auditor para tener blanco real');

SELECT pg_temp.atacar('E6','borrar un conflict abierto        ', $q$
  DELETE FROM identity_v1.conflict WHERE state='OPEN'
$q$);

SELECT pg_temp.atacar('E7','TRUNCATE de la procedencia        ', $q$
  TRUNCATE identity_v1.assertion CASCADE
$q$);

\echo ''
\echo '### F · F-021 · PROCEDENCIA DEL INSTRUMENTO ###'

SELECT pg_temp.atacar('F1','instrumento sin assertion         ', $q$
  INSERT INTO identity_v1.instrument
    (instrument_key,entity_key,instrument_type,exchange,currency)
  VALUES ('AUDIT:X','E000000000000000000000000A1','EQUITY','BUE','ARS')
$q$);

SELECT pg_temp.atacar('F2','ADR sin ratio (con procedencia ok)', $q$
  INSERT INTO identity_v1.instrument
    (instrument_key,entity_key,instrument_type,exchange,currency,assertion_id)
  VALUES ('AUDIT:ADR','E000000000000000000000000A1','ADR','NYSE','USD',
          pg_temp.a_ok('E000000000000000000000000A1','INSTRUMENT:AUDIT:ADR'))
$q$);

ROLLBACK;

\echo ''
\echo '### ESTADO POSTERIOR (debe ser identico al inicial) ###'
SELECT (SELECT count(*) FROM identity_v1.entity) AS entidades,
       (SELECT count(*) FROM identity_v1.assertion) AS assertions,
       (SELECT count(*) FROM identity_v1.identifier) AS identifiers,
       (SELECT count(*) FROM identity_v1.review) AS reviews,
       (SELECT count(*) FROM identity_v1.conflict) AS conflicts;
