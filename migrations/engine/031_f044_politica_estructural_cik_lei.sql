-- =====================================================================
-- 031_f044_politica_estructural_cik_lei.sql  ·  F-044
-- =====================================================================
-- Contrato: docs/architecture/F044_CONTRACT.md
--
-- EL PROBLEMA
-- `identity_v1.source` es una tabla de DATOS, mutable por el owner con un
-- UPDATE ordinario, y todas las garantias de autoridad la consultan. Con la
-- politica adulterada, y escribiendo con el rol OPERATIVO `catalaxia_engine`:
--
--   LEGACY_DIM_ENTITY -> CIK    ENTRA
--   LEGACY_DIM_ENTITY -> LEI    ENTRA
--   LEGACY_DIM_ENTITY -> CUIT   bloqueado por ck_cuit_exige_evidencia_estructurada
--   CNV_PORTAL        -> CIK    ENTRA
--   DERIVED_RULE      -> LEI    ENTRA
--
-- LA ASIMETRIA ES EL HALLAZGO
-- El CUIT sobrevive porque `ck_cuit_exige_evidencia_estructurada` (F-037)
-- enumera las fuentes LITERALMENTE (CASE source_id ... ELSE false) y NO
-- consulta `source`. CIK y LEI no tienen nada equivalente.
--
-- Ni el trigger de F-045 ayuda: tambien consulta `source`, asi que una politica
-- adulterada convence a los dos triggers. F-045 agrego una segunda barrera, no
-- una independiente.
--
-- LA CORRECCION
-- Replicar para CIK y LEI el patron que ya demostro funcionar para CUIT. No es
-- una idea nueva: es la razon por la que el CUIT resistio el ataque.
--
-- La politica sigue viviendo en `source` como documentacion operativa y primera
-- barrera. Lo que se agrega es una segunda barrera que NO la consulta -- de modo
-- que adulterar la tabla deja de servir de nada.
--
-- LIMITE HONESTO
-- El owner puede hacer DROP CONSTRAINT. Ninguna garantia en PostgreSQL sobrevive
-- a su propio owner, y esta migracion no pretende lo contrario. Lo que cambia es
-- la NATURALEZA del acto: adulterar `source` es un UPDATE de datos, invisible en
-- un diff de schema y plausible como operacion de mantenimiento; quitar un CHECK
-- es DDL, visible y sin ambiguedad.
--
-- EL DETALLE QUE CASI ROMPE LOS BRIDGES
-- Los 3 bridges VERIFIED tienen left_ref='CIK:SEC:...' y source_id='HUMAN'. Un
-- CHECK sobre (left_ref LIKE 'CIK:%' AND status='VERIFIED') los alcanzaria y los
-- romperia. Por eso el predicado exige ademas subject_type='ENTITY_IDENTIFIER'.
--
-- Verificado antes de escribir: 523 assertions ENTITY_IDENTIFIER VERIFIED con
-- left_ref, de las cuales 0 incumplen. Por eso el constraint va VALIDADO, no
-- NOT VALID: no hay historia que perdonar.
-- =====================================================================

ALTER TABLE identity_v1.assertion
  DROP CONSTRAINT IF EXISTS ck_politica_estructural_cik_lei;

ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_politica_estructural_cik_lei CHECK (
    -- solo alcanza a lo que ESTABLECE identidad de entidad.
    -- `subject_type` no es decorativo aca: sin el, los bridges VERIFIED
    -- (left_ref='CIK:...', source_id='HUMAN') quedarian atrapados.
    NOT (subject_type = 'ENTITY_IDENTIFIER' AND status = 'VERIFIED')
    OR left_ref IS NULL          -- lo gobierna F-045 en el punto de uso
    OR CASE split_part(left_ref, ':', 1)
         -- Fuentes enumeradas LITERALMENTE. No se consulta `source`:
         -- ese es todo el punto.
         WHEN 'CIK'  THEN source_id IN ('SEC_REGISTRY', 'SEC_20F', 'HUMAN')
         WHEN 'LEI'  THEN source_id IN ('GLEIF', 'HUMAN')
         ELSE TRUE                -- CUIT ya lo cubre F-037; el resto no aplica
       END
  );

COMMENT ON CONSTRAINT ck_politica_estructural_cik_lei ON identity_v1.assertion IS
  'F-044: que fuente puede ESTABLECER un CIK o un LEI, enumerado en el schema y '
  'NO leido de identity_v1.source. Cierra el camino demostrado: con la politica '
  'adulterada por el owner, `catalaxia_engine` podia establecer CIK y LEI desde '
  'fuentes CORROBORATING o DISCOVERY_ONLY. Es el mismo patron que ya protegia al '
  'CUIT (ck_cuit_exige_evidencia_estructurada, F-037). Ver F044_CONTRACT.md.';
