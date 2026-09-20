-- =====================================================================
-- CICLO 5 — AUDITORIA INDEPENDIENTE DE IDENTITY V1
-- =====================================================================
-- Escrito por el AUDITOR, no por el implementador.
--
-- Disciplina de este script:
--   * NO importa engine/identity_v1.py. Ataca la base directamente.
--   * NO usa tests/test_identity_v1.py. Los controles se reimplementan.
--   * Cada ataque corre en un savepoint de plpgsql que se revierte SIEMPRE,
--     haya sido aceptado o rechazado. El estado del piloto no se modifica.
--
-- Lectura del resultado:
--   [OK]     el ataque fue RECHAZADO por la base -> el control existe
--   [HUECO]  el ataque fue ACEPTADO             -> el control NO existe
--
-- Uso:
--   docker cp docs/review/identity_v1_audit.sql catalaxia-engine-dev:/tmp/
--   docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -f /tmp/identity_v1_audit.sql
-- =====================================================================

\set QUIET on
\pset pager off
SET client_min_messages TO WARNING;

BEGIN;   -- transaccion externa: se revierte al final, pase lo que pase

-- ---------------------------------------------------------------------
-- Arnes: ejecuta SQL esperando rechazo. Reporta y revierte siempre.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION pg_temp.atacar(nro text, titulo text, cuerpo text,
                                          esperado text DEFAULT 'RECHAZO')
RETURNS void AS $fn$
BEGIN
    BEGIN
        EXECUTE cuerpo;
        RAISE EXCEPTION 'SENTINELA_ACEPTADO';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'SENTINELA_ACEPTADO' THEN
            IF esperado = 'RECHAZO' THEN
                RAISE WARNING '[HUECO] %  %  -> ACEPTADO (no hay control)', nro, titulo;
            ELSE
                RAISE WARNING '[OK]    %  %  -> aceptado, como debe ser', nro, titulo;
            END IF;
        ELSE
            IF esperado = 'RECHAZO' THEN
                RAISE WARNING '[OK]    %  %  -> RECHAZADO: %', nro, titulo,
                              left(replace(SQLERRM, chr(10), ' '), 110);
            ELSE
                RAISE WARNING '[HUECO] %  %  -> RECHAZADO cuando debia aceptarse: %',
                              nro, titulo, left(SQLERRM, 90);
            END IF;
        END IF;
    END;
END;
$fn$ LANGUAGE plpgsql;

-- claves reales del piloto, leidas de la base (no hardcodeadas del implementador)
CREATE TEMP TABLE k AS
SELECT max(entity_key) FILTER (WHERE cik='0000904851') AS ypf,
       max(entity_key) FILTER (WHERE cik='0001717161') AS cepu,
       max(entity_key) FILTER (WHERE cik='0001114700') AS ggal,
       max(entity_key) FILTER (WHERE cik='0000931427') AS tgs
  FROM identity_v1.v_entity_resolution;

CREATE OR REPLACE FUNCTION pg_temp.ek(t text) RETURNS text AS $$
  SELECT CASE t WHEN 'ypf' THEN ypf WHEN 'cepu' THEN cepu
                WHEN 'ggal' THEN ggal ELSE tgs END FROM k;
$$ LANGUAGE sql;

-- assertion valida reutilizable para colgar identificadores de prueba
CREATE OR REPLACE FUNCTION pg_temp.assert_ok(ek text, lref text) RETURNS bigint AS $$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, left_ref, relationship, method, confidence, status,
     source_id, source_record, evidence, resolved_by)
  VALUES ('ENTITY_IDENTIFIER', ek, lref, 'BELONGS_TO', 'REGULATORY_DOCUMENT',
          'AUTHORITATIVE', 'VERIFIED', 'SEC_20F', 'auditoria/ciclo5',
          'cita fabricada por el auditor para probar el control', 'auditor:ciclo5')
  RETURNING assertion_id;
$$ LANGUAGE sql;

\echo ''
\echo '################ ATAQUES 1-3 · ATRIBUCION CRUZADA DE CUIT ################'

SELECT pg_temp.atacar('01', 'YPF + CUIT de CEPU (33650305499)   ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','33650305499', true, pg_temp.assert_ok(%L,'CUIT:AFIP:33650305499'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('02', 'CEPU + CUIT de YPF (30546689979)   ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','30546689979', true, pg_temp.assert_ok(%L,'CUIT:AFIP:30546689979'))
$q$, pg_temp.ek('cepu'), pg_temp.ek('cepu')));

SELECT pg_temp.atacar('03', 'GGAL + CUIT de TGSU2 (30657862068) ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','30657862068', true, pg_temp.assert_ok(%L,'CUIT:AFIP:30657862068'))
$q$, pg_temp.ek('ggal'), pg_temp.ek('ggal')));

\echo ''
\echo '################ ATAQUES 4-5 · TICKER COMO IDENTIDAD ################'

SELECT pg_temp.atacar('04', 'TICKER/US "YPF" como autoritativo  ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'TICKER','US','YPF', true, pg_temp.assert_ok(%L,'TICKER:US:YPF'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('04b','YF_SYMBOL "YPF" como autoritativo  ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'YF_SYMBOL','YAHOO','YPF', true, pg_temp.assert_ok(%L,'YF_SYMBOL:YAHOO:YPF'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

-- TICKER/US y TICKER/BYMA deben poder coexistir apuntando a entidades distintas
SELECT pg_temp.atacar('05', 'TICKER/US:GGAL y TICKER/BYMA:GGAL a entidades distintas', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'TICKER','US','GGAL', false, pg_temp.assert_ok(%L,'TICKER:US:GGAL')),
         (%L,'TICKER','BYMA','GGAL', false, pg_temp.assert_ok(%L,'TICKER:BYMA:GGAL'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf'), pg_temp.ek('cepu'), pg_temp.ek('cepu')),
 'ACEPTACION');

\echo ''
\echo '################ ATAQUES 6-8 · UNICIDAD Y PROCEDENCIA ################'

SELECT pg_temp.atacar('06', 'segundo identificador autoritativo con el MISMO CUIT', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','30546689979', true, pg_temp.assert_ok(%L,'CUIT:AFIP:30546689979'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('07', 'identificador SIN assertion (sin procedencia)', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative)
  VALUES (%L,'CUIT','AFIP','30111222223', true)
$q$, pg_temp.ek('ypf')));

SELECT pg_temp.atacar('07b','identificador autoritativo colgado de assertion CANDIDATE', format($q$
  WITH a AS (
    INSERT INTO identity_v1.assertion
      (subject_type, entity_key, left_ref, relationship, method, confidence, status)
    VALUES ('ENTITY_IDENTIFIER', %L, 'CUIT:AFIP:30111222223','BELONGS_TO',
            'CROSS_REFERENCE','WEAK','CANDIDATE')
    RETURNING assertion_id)
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  SELECT %L,'CUIT','AFIP','30111222223', true, assertion_id FROM a
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('08', 'assertion VERIFIED sin evidence          ', format($q$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, method, confidence, status, source_id, resolved_by)
  VALUES ('ENTITY_IDENTIFIER', %L, 'REGISTRY','AUTHORITATIVE','VERIFIED','SEC_20F','x')
$q$, pg_temp.ek('ypf')));

SELECT pg_temp.atacar('08b','assertion VERIFIED sin source_id ni resolved_by', format($q$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, method, confidence, status, evidence)
  VALUES ('ENTITY_IDENTIFIER', %L, 'REGISTRY','AUTHORITATIVE','VERIFIED','cita suelta')
$q$, pg_temp.ek('ypf')));

SELECT pg_temp.atacar('08c','regla derivada declarada AUTHORITATIVE  ', format($q$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, method, confidence, status, source_id, source_record,
     evidence, resolved_by)
  VALUES ('ENTITY_IDENTIFIER', %L, 'DERIVED_RULE','AUTHORITATIVE','VERIFIED',
          'DERIVED_RULE','regla','sufijo .BA','proc')
$q$, pg_temp.ek('ypf')));

\echo ''
\echo '################ ATAQUE 9 · REVIEW_REQUIRED -> VERIFIED SIN REVISOR ################'

SELECT pg_temp.atacar('09a','cerrar review sin reviewer/decision      ', $q$
  UPDATE identity_v1.review SET status='RESOLVED', resolved_at=now()
   WHERE status='OPEN' AND reason LIKE 'GLEIF no permite%'
$q$);

-- 9b: la review de GGAL esta ABIERTA. ¿Puedo escribir igual el CUIT autoritativo,
--     salteando el flujo de revision?
SELECT pg_temp.atacar('09b','escribir CUIT autoritativo de GGAL con la review ABIERTA', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','30704962807', true, pg_temp.assert_ok(%L,'CUIT:AFIP:30704962807'))
$q$, pg_temp.ek('ggal'), pg_temp.ek('ggal')));

-- 9c: promover a VERIFIED una assertion que hoy esta en REVIEW_REQUIRED
SELECT pg_temp.atacar('09c','promover assertion REVIEW_REQUIRED -> VERIFIED por UPDATE', $q$
  UPDATE identity_v1.assertion
     SET status='VERIFIED', confidence='AUTHORITATIVE', method='REGISTRY'
   WHERE status='REVIEW_REQUIRED' AND valid_to IS NULL
$q$);

\echo ''
\echo '################ ATAQUES 10-11 · IDENTIFICADORES CONTRADICTORIOS ################'

SELECT pg_temp.atacar('10', 'segundo CIK autoritativo para YPF        ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CIK','SEC','0000320193', true, pg_temp.assert_ok(%L,'CIK:SEC:0000320193'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('11', 'segundo CUIT autoritativo para YPF       ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','30707429468', true, pg_temp.assert_ok(%L,'CUIT:AFIP:30707429468'))
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('11b','CUIT con digito verificador INVALIDO     ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','99999999999', true, pg_temp.assert_ok(%L,'CUIT:AFIP:99999999999'))
$q$, pg_temp.ek('ggal'), pg_temp.ek('ggal')));

SELECT pg_temp.atacar('11c','CUIT con formato basura ("no-soy-un-cuit")', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CUIT','AFIP','no-soy-un-cuit', true, pg_temp.assert_ok(%L,'CUIT:AFIP:x'))
$q$, pg_temp.ek('ggal'), pg_temp.ek('ggal')));

SELECT pg_temp.atacar('11d','CIK con formato invalido ("YPF")         ', format($q$
  INSERT INTO identity_v1.identifier
    (entity_key, id_type, id_namespace, id_value, is_authoritative, assertion_id)
  VALUES (%L,'CIK','SEC','YPF', true, pg_temp.assert_ok(%L,'CIK:SEC:YPF'))
$q$, pg_temp.ek('ggal'), pg_temp.ek('ggal')));

\echo ''
\echo '################ ATAQUES 12-13 · HISTORIA Y PROCEDENCIA ################'

SELECT pg_temp.atacar('12a','borrar assertion VIGENTE de YPF          ', $q$
  DELETE FROM identity_v1.assertion
   WHERE assertion_id = (SELECT min(assertion_id) FROM identity_v1.assertion
                          WHERE status='VERIFIED' AND valid_to IS NULL)
$q$);

-- 12b: crear una assertion HISTORICA (cerrada) y despues intentar borrarla
SELECT pg_temp.atacar('12b','borrar assertion HISTORICA (ya superseded)', format($q$
  WITH nueva AS (SELECT pg_temp.assert_ok(%L,'CIK:SEC:0000904851') AS id),
       cerrada AS (
         UPDATE identity_v1.assertion a SET valid_to=now(), superseded_by=(SELECT id FROM nueva)
          WHERE a.assertion_id = (SELECT min(assertion_id) FROM identity_v1.assertion
                                   WHERE entity_key=%L AND left_ref LIKE 'CIK%%')
          RETURNING a.assertion_id)
  DELETE FROM identity_v1.assertion WHERE assertion_id IN (SELECT assertion_id FROM cerrada)
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('12c','borrar assertion REVIEW_REQUIRED vigente ', $q$
  DELETE FROM identity_v1.assertion WHERE status='REVIEW_REQUIRED' AND valid_to IS NULL
$q$);

SELECT pg_temp.atacar('12d','borrar la review ABIERTA de GGAL         ', $q$
  DELETE FROM identity_v1.review WHERE status='OPEN'
$q$);

SELECT pg_temp.atacar('12e','borrar un conflict abierto               ', $q$
  DELETE FROM identity_v1.conflict WHERE state='OPEN'
$q$);

SELECT pg_temp.atacar('13a','MODIFICAR la evidencia de una assertion VIGENTE', $q$
  UPDATE identity_v1.assertion SET evidence='evidencia reescrita por el atacante'
   WHERE status='VERIFIED' AND valid_to IS NULL
     AND assertion_id=(SELECT min(assertion_id) FROM identity_v1.assertion
                        WHERE status='VERIFIED' AND valid_to IS NULL)
$q$);

SELECT pg_temp.atacar('13b','REAPUNTAR una assertion vigente a otra entidad ', format($q$
  UPDATE identity_v1.assertion SET entity_key=%L
   WHERE assertion_id=(SELECT min(assertion_id) FROM identity_v1.assertion
                        WHERE entity_key=%L AND status='VERIFIED' AND valid_to IS NULL)
$q$, pg_temp.ek('cepu'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('13c','MODIFICAR una assertion HISTORICA        ', format($q$
  WITH nueva AS (SELECT pg_temp.assert_ok(%L,'CIK:SEC:0000904851') AS id),
       cerrada AS (
         UPDATE identity_v1.assertion a SET valid_to=now(), superseded_by=(SELECT id FROM nueva)
          WHERE a.assertion_id=(SELECT min(assertion_id) FROM identity_v1.assertion
                                 WHERE entity_key=%L AND left_ref LIKE 'CIK%%')
          RETURNING a.assertion_id)
  UPDATE identity_v1.assertion SET evidence='reescrita'
   WHERE assertion_id IN (SELECT assertion_id FROM cerrada)
$q$, pg_temp.ek('ypf'), pg_temp.ek('ypf')));

SELECT pg_temp.atacar('13d','REAPUNTAR un identifier vigente a otra entidad', format($q$
  UPDATE identity_v1.identifier SET entity_key=%L
   WHERE id_type='CUIT' AND id_value='30546689979' AND is_authoritative
$q$, pg_temp.ek('cepu')));

\echo ''
\echo '################ EXTRA · SUPERFICIES NO DECLARADAS ################'

SELECT pg_temp.atacar('E1', 'instrumento SIN assertion (procedencia)  ', format($q$
  INSERT INTO identity_v1.instrument
    (instrument_key, entity_key, instrument_type, exchange, currency)
  VALUES ('AUDIT:X', %L, 'EQUITY','BUE','ARS')
$q$, pg_temp.ek('ypf')));

SELECT pg_temp.atacar('E2', 'ADR sin ratio_underlying                 ', format($q$
  INSERT INTO identity_v1.instrument
    (instrument_key, entity_key, instrument_type, exchange, currency)
  VALUES ('AUDIT:ADR', %L, 'ADR','NYSE','USD')
$q$, pg_temp.ek('ypf')));

SELECT pg_temp.atacar('E3', 'entity_key con formato arbitrario ("YPF")', $q$
  INSERT INTO identity_v1.entity (entity_key, preferred_name) VALUES ('YPF','falsa')
$q$);

SELECT pg_temp.atacar('E4', 'fuente inventada (FK a source)           ', format($q$
  INSERT INTO identity_v1.assertion
    (subject_type, entity_key, method, confidence, status, source_id, source_record,
     evidence, resolved_by)
  VALUES ('ENTITY_IDENTIFIER', %L,'REGISTRY','AUTHORITATIVE','VERIFIED',
          'FUENTE_INVENTADA','x','y','z')
$q$, pg_temp.ek('ypf')));

SELECT pg_temp.atacar('E5', 'bridge IDENTIFIER_BRIDGE con un solo extremo', $q$
  INSERT INTO identity_v1.assertion
    (subject_type, left_ref, method, confidence, status, source_id, source_record,
     evidence, resolved_by)
  VALUES ('IDENTIFIER_BRIDGE','CIK:SEC:0000904851','HUMAN_DECISION','STRONG','VERIFIED',
          'HUMAN','x','y','z')
$q$);

SELECT pg_temp.atacar('E6', 'HUMAN_DECISION sin resolution_reason     ', $q$
  INSERT INTO identity_v1.assertion
    (subject_type, left_ref, right_ref, method, confidence, status, source_id,
     source_record, evidence, resolved_by)
  VALUES ('IDENTIFIER_BRIDGE','CIK:SEC:1','LEI:GLEIF:2','HUMAN_DECISION','STRONG',
          'VERIFIED','HUMAN','x','y','z')
$q$);

SELECT pg_temp.atacar('E7', 'mismo simbolo YAHOO en dos instrumentos  ', $q$
  INSERT INTO identity_v1.instrument_symbol (instrument_key, id_namespace, symbol)
  VALUES ('MKT:83','YAHOO','YPF')
$q$);

ROLLBACK;   -- el piloto queda exactamente como estaba

\echo ''
\echo '################ VERIFICACION DE QUE NADA SE MODIFICO ################'
SELECT (SELECT count(*) FROM identity_v1.entity)     AS entidades,
       (SELECT count(*) FROM identity_v1.assertion)  AS assertions,
       (SELECT count(*) FROM identity_v1.identifier) AS identifiers,
       (SELECT count(*) FROM identity_v1.review WHERE status='OPEN') AS reviews_abiertas,
       (SELECT count(*) FROM identity_v1.conflict)   AS conflicts;
