-- =====================================================================
-- 013_f009_cierre_corridas_huerfanas.sql  ·  cierra F-009
-- =====================================================================
-- AUDITORIA PREVIA (evidencia, no suposicion):
--
--   pg_stat_activity: 0 sesiones sobre la base. NINGUNA corrida sigue viva.
--   engine.runs: 28 corridas · OK 8 · ABORTED 7 · BLOCKED 6 · RUNNING 7
--   Los tres primeros son estados terminales. Solo RUNNING no lo es.
--
-- Las 7 en RUNNING NO son un grupo homogeneo. Se auditaron una por una y hay
-- DOS causas distintas. Marcarlas todas igual habria borrado esa diferencia.
--
-- ---------------------------------------------------------------------
-- GRUPO A — 5 corridas que murieron al principio
-- ---------------------------------------------------------------------
--   e004ed88a54644009efa9c8b790a92bb  S03_parse  2026-08-24 21:37  (27.4 h)
--   e65a3c6a72e64813a83a28b81a0df53a  S03_parse  2026-08-25 04:13  (20.8 h)
--   eccd5fb3e31c4757a59b5194ba5057b3  S03_parse  2026-08-25 04:17  (20.7 h)
--   b4a2b22073744b3789231b1dbf744f3e  S03_parse  2026-08-25 04:26  (20.6 h)
--   973b7e9eb7db4a7eba4200200c521fa9  S03_parse  2026-08-25 04:36  (20.4 h)
--
--   Evidencia de abandono, la misma en las 5:
--     * traza completa = 'READY | RUNNING'. No llegaron a VALIDATING.
--     * la ultima transicion es de MILISEGUNDOS despues del arranque.
--     * 0 filas en engine.checkpoints.
--     * report IS NULL, finished_at IS NULL en todas sus stage_runs.
--     * 20-27 horas sin actividad y sin proceso vivo.
--   Diagnostico: abortaron en el arranque. Nunca produjeron nada.
--
-- ---------------------------------------------------------------------
-- GRUPO B — 2 corridas que hicieron el trabajo y murieron al persistir
-- ---------------------------------------------------------------------
--   f8b8c389a60441c09fb47e5d0195f73f  S03_parse     2026-08-25 13:41 -> 13:54
--   39d072dbe6af444da231c63fbc29685e  C3_CNV_fetch  2026-08-25 13:46 -> 13:48
--
--   Evidencia, distinta de la del grupo A:
--     * traza COMPLETA: READY|RUNNING|VALIDATING|PASSED|CHECKPOINTED
--     * gate_status = 'PASS' en la fila CHECKPOINTED
--     * PERO report IS NULL y finished_at IS NULL en TODAS sus filas
--
--   Contraste con una corrida que si cerro (971ce5d9...):
--     su fila CHECKPOINTED tiene report poblado y finished_at poblado.
--
--   CAUSA RAIZ: en s03_parse_ypf.py las transiciones PASSED y CHECKPOINTED se
--   registran (linea ~620) ANTES del bloque `with engine.begin()` que persiste
--   el report y el checkpoint (~646) y ANTES de finish_run (~665). El proceso
--   murio en ese tramo: entre construir el StageReport y persistirlo.
--   El estado de ETAPA quedo adelantado respecto del estado de CORRIDA.
--
--   Ademas sus checkpoints fueron REASIGNADOS a corridas posteriores por el
--   `ON CONFLICT ... DO UPDATE SET run_id = EXCLUDED.run_id`:
--     checkpoint 971ce5d999a2499b-s03  -> run 971ce5d9... (OK, 13:56)
--     checkpoint 8db8692ebce9439c...   -> run eb05375b... (OK, 13:52)
--   O sea: aunque hubieran cerrado, no son las duenas de ningun artefacto.
--
--   Se marcan ABORTED y no OK: llegar a CHECKPOINTED sin persistir el report
--   NO es completar el contrato de la etapa. Declararlas OK seria afirmar un
--   cierre que no ocurrio.
--
-- ---------------------------------------------------------------------
-- Ninguna corrida con evidencia de estar VIVA fue tocada. No la habia.
-- =====================================================================

-- GRUPO A — abandono en el arranque
UPDATE engine.runs
   SET status = 'ABORTED', finished_at = COALESCE(finished_at, now())
 WHERE status = 'RUNNING'
   AND run_id IN ('e004ed88a54644009efa9c8b790a92bb',
                  'e65a3c6a72e64813a83a28b81a0df53a',
                  'eccd5fb3e31c4757a59b5194ba5057b3',
                  'b4a2b22073744b3789231b1dbf744f3e',
                  '973b7e9eb7db4a7eba4200200c521fa9');

-- GRUPO B — murieron entre validar y persistir
UPDATE engine.runs
   SET status = 'ABORTED', finished_at = COALESCE(finished_at, now())
 WHERE status = 'RUNNING'
   AND run_id IN ('f8b8c389a60441c09fb47e5d0195f73f',
                  '39d072dbe6af444da231c63fbc29685e');

-- Guarda: si quedara alguna RUNNING no auditada, la migracion falla en vez de
-- dejar el problema silencioso.
DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM engine.runs WHERE status = 'RUNNING';
    IF n > 0 THEN
        RAISE EXCEPTION
          'F-009: quedan % corridas en RUNNING sin auditar. '
          'Auditar una por una antes de cerrar; no cerrarlas en bloque.', n;
    END IF;
END $$;

INSERT INTO engine.schema_migrations (filename)
VALUES ('013_f009_cierre_corridas_huerfanas.sql') ON CONFLICT DO NOTHING;
