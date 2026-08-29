-- =====================================================================
-- 028_f040_cierre_huerfanas_c3.sql  ·  F-040
-- =====================================================================
-- Contrato: docs/architecture/F040_HALLAZGO.md
--
-- QUE CORRIGE
-- Tres corridas de `cnv-fetch-v1` quedaron en RUNNING el 2026-08-28 porque
-- `c3_cnv_fetch.py` abria la corrida con start_run() y la cerraba con
-- finish_run() 350 lineas mas abajo. Las tres murieron en el medio:
--
--   b01395aa33ca43c292e99fdfdf87bc2b  15:00:29  CheckViolation de F-039
--   021cb5dc41e3446d8788f3e79fc1200b  15:01:23  CheckViolation de F-039
--   50251c198a9947ac99d1e89367a1b564  15:04:49  matada por `timeout 560`
--
-- El codigo ya esta migrado a run_scope(), asi que no se generan mas. Estas
-- tres son anteriores al fix y hay que cerrarlas: mientras digan RUNNING, la
-- base afirma que hay tres fetch de CNV en curso, y no hay ninguno.
--
-- QUE **NO** HACE
--   * NO las borra. Registran que hubo tres intentos fallidos, y son la
--     evidencia de F-039. Se aplica el criterio del proyecto: "se borra lo que
--     se reconstruye desde el RAW; no se borra lo que registra que paso".
--   * NO las marca OK. Fallaron.
--   * NO toca sus stage_runs, artefactos ni presentaciones.
--
-- Se marcan ABORTED, que es literalmente lo que les paso, con `finished_at`
-- fijado al ultimo momento en que se sabe que existieron -- no a `now()`, que
-- fingiria que terminaron hoy a esta hora.
-- =====================================================================

UPDATE engine.runs r
   SET status = 'ABORTED',
       finished_at = COALESCE(
           (SELECT max(COALESCE(s.finished_at, s.started_at))
              FROM engine.stage_runs s WHERE s.run_id = r.run_id),
           r.started_at)
 WHERE r.status = 'RUNNING'
   AND r.pipeline_version LIKE 'cnv-fetch%'
   AND r.run_id IN ('b01395aa33ca43c292e99fdfdf87bc2b',
                    '021cb5dc41e3446d8788f3e79fc1200b',
                    '50251c198a9947ac99d1e89367a1b564');
