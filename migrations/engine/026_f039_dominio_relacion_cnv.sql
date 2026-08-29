-- =====================================================================
-- 026_f039_dominio_relacion_cnv.sql  ·  F-039
-- =====================================================================
-- Contrato: docs/architecture/F039_CONTRATO.md
--
-- `cnv_presentation_relacion_check` admitia solo CONTROLADA|VINCULADA. Ese
-- dominio se escribio mirando una sola empresa (CEPU). YPF declara ademas
-- CONTROLANTE (2 filas sobre 601 relaciones), y el fetch entero muere ahi.
--
-- El parser NO tiene el defecto: engine/cnv/discovery.py ya preveia un tercer
-- valor (CLASE_EEFF_RELAC_OTRA). Era el CHECK el que no lo sabia.
--
-- No se reescribe ninguna fila existente. Las 9.305 de CEPU no tienen
-- CONTROLANTE.
-- =====================================================================

-- --------------------------------------------------------------------
-- 1. El dominio se amplia a lo OBSERVADO en el RAW, no a "cualquier cosa".
--    NULL sigue siendo valido: relacion_origen='AUSENTE' es un estado real
--    (8.915 filas), no una omision.
-- --------------------------------------------------------------------
ALTER TABLE fetch_raw.cnv_presentation
  DROP CONSTRAINT IF EXISTS cnv_presentation_relacion_check;
ALTER TABLE fetch_raw.cnv_presentation
  ADD CONSTRAINT cnv_presentation_relacion_check
  CHECK (relacion IS NULL
         OR relacion IN ('CONTROLADA', 'VINCULADA', 'CONTROLANTE'));

-- --------------------------------------------------------------------
-- 2. Lo que de verdad importa: en CONTROLANTE la arista va al reves.
--
--    En CONTROLADA/VINCULADA, `cuit_relacionado` es LA OTRA empresa.
--    En CONTROLANTE, es LA EMPRESA DEL PERFIL: la fila la presenta la
--    controlada y nombra a su controlante.
--
--    Sin esta columna, un consumidor que lea `relacion IS NOT NULL` como
--    "subsidiaria nuestra" toma a YPF como subsidiaria de YPF.
-- --------------------------------------------------------------------
ALTER TABLE fetch_raw.cnv_presentation
  ADD COLUMN IF NOT EXISTS relacion_es_inversa BOOLEAN
  GENERATED ALWAYS AS (relacion = 'CONTROLANTE') STORED;

COMMENT ON COLUMN fetch_raw.cnv_presentation.relacion_es_inversa IS
  'TRUE cuando la fila declara al controlante del perfil, no a una empresa '
  'controlada por el. En esas filas `cuit_relacionado` es el CUIT del PROPIO '
  'perfil. Ningun consumidor debe leerlas como subsidiaria. Ver F039_CONTRATO.md.';

COMMENT ON COLUMN fetch_raw.cnv_presentation.relacion IS
  'Lo que la CNV declara literalmente en el campo RELAC.: del titulo. '
  'Dominio observado: CONTROLADA | VINCULADA | CONTROLANTE. NULL = la CNV no '
  'la declara (relacion_origen=AUSENTE); nunca se asume. Ver F039_CONTRATO.md.';
