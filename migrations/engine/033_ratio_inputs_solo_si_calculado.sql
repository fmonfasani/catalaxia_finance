-- =====================================================================
-- 033_ratio_inputs_solo_si_calculado.sql  ·  corrige 032
-- =====================================================================
-- QUE PASO
-- La migracion 032 declaro `ck_ratio_inputs_no_vacio` sobre TODAS las filas.
-- El primer `--persist` del motor lo rompio en el acto: GGAL, BMA y CEPU
-- terminan en NOT_CALCULABLE -- GGAL y BMA porque no publican `Revenue` (son
-- bancos), CEPU porque no publica ningun tag de deuda financiera -- y una fila
-- NOT_CALCULABLE no tiene insumos que citar.
--
-- El choque es entre dos reglas del contrato, y las dos son correctas:
--   R7   "no se pudo" es informacion y se persiste; sin la fila, un hueco es
--        indistinguible de un emisor que nunca se proceso.
--   R10  ningun VALOR se persiste sin provenance completa.
--
-- La 032 aplicaba R10 a la fila entera en vez de al valor. Se corrige el
-- alcance: R10 exige insumos cuando hay valor. Cuando no lo hay, lo que la
-- fila debe llevar es el MOTIVO, y eso ya lo garantiza
-- `ck_ratio_valor_vs_status`, que sigue vigente sin cambios.
--
-- El motor, ademas, pasa a registrar los insumos que SI encontro antes de
-- cortar: una fila NOT_CALCULABLE con provenance parcial dice en que eslabon
-- se corto, no solo que se corto.
--
-- No se edita la 032: ya esta aplicada y el registro de migraciones es del
-- runner (F-049). Se corrige hacia adelante.
-- =====================================================================

ALTER TABLE derived.ratio DROP CONSTRAINT IF EXISTS ck_ratio_inputs_no_vacio;

ALTER TABLE derived.ratio ADD CONSTRAINT ck_ratio_inputs_si_calculado CHECK (
    status <> 'CALCULADO' OR jsonb_array_length(inputs) > 0);

COMMENT ON CONSTRAINT ck_ratio_inputs_si_calculado ON derived.ratio IS
  'R10: un VALOR no existe sin provenance. Una fila NOT_CALCULABLE puede tener '
  'inputs parciales o vacios; lo que no puede faltar es el motivo, que exige '
  'ck_ratio_valor_vs_status.';
