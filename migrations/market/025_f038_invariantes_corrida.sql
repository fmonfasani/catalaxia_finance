-- =====================================================================
-- 025_f038_invariantes_corrida.sql  ·  F-038
-- =====================================================================
-- Contrato: docs/architecture/F038_CONTRATO.md
--
-- CORRECCION DEL DIAGNOSTICO INICIAL
-- F-038 se abrio como "M23 no dejo traza". Es FALSO. M23 registro sus 591
-- filas en `market_raw_runs` de catalaxia-engine-dev (5433) bajo
-- stage_run_id='smoke-real-2026-08-28'. Lo que fallo fue la auditoria: se
-- consulto catalaxia-db (5432), donde Market NO escribe por diseno (F-001).
--
-- No hay defecto de persistencia que corregir. Lo que sigue son las
-- invariantes que el mecanismo ya cumple de hecho pero no declaraba.
--
-- No se modifica ningun dato obtenido por M23.
-- =====================================================================

-- INVARIANTE: el estado y el artefacto no pueden contradecirse.
--   * un SUCCESS trae su sha256 y su row_count;
--   * un FAILED no finge tener artefacto (no declara sha256).
-- `row_count` NO se exige NULL en FAILED: el escritor real
-- (m2_fetch_engine.py:199) inserta 0, que es el dato correcto -- se pidio y
-- no vino nada. Exigir NULL habria roto la proxima corrida.
-- Verificado contra las 591 filas reales: 577 SUCCESS todas con sha256,
-- 14 FAILED ninguna con sha256.
ALTER TABLE market_raw_runs DROP CONSTRAINT IF EXISTS ck_estado_coherente_con_artefacto;
ALTER TABLE market_raw_runs
  ADD CONSTRAINT ck_estado_coherente_con_artefacto CHECK (
        (status = 'SUCCESS' AND sha256 IS NOT NULL AND row_count IS NOT NULL)
     OR (status = 'FAILED'  AND sha256 IS NULL)
     OR (status IN ('EMPTY', 'PARTIAL'))
  ) NOT VALID;

COMMENT ON COLUMN market_raw_runs.stage_run_id IS
  'Identificador del LOTE. Agrupa los instrumentos de una misma corrida '
  '(p.ej. smoke-real-2026-08-28). Permite reconstruir la corrida desde la base '
  'sin leer el reporte JSON. Ver F038_CONTRATO.md.';
