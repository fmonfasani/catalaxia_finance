-- =====================================================================
-- 027_f039_autorreferencia.sql  ·  F-039, correccion de 026
-- =====================================================================
-- Contrato: docs/architecture/F039_CONTRATO.md
--
-- LA 026 SE QUEDO CORTA, Y POR LA MISMA RAZON QUE EL BUG QUE CORREGIA.
--
-- 026 definio `relacion_es_inversa = (relacion = 'CONTROLANTE')`, con el
-- argumento de que en esas filas `cuit_relacionado` es el CUIT del propio
-- perfil. El argumento era correcto; el predicado, no.
--
-- Los datos reales de YPF (9.838 filas, verificadas tras cargar):
--
--     relacion      es_inversa   filas   cuit_relacionado = cuit del perfil
--     (NULL)             -        8670                    0
--     VINCULADA          f         676                    0
--     CONTROLADA         f         488                   32   <-- NO marcadas
--     CONTROLANTE        t           4                    4
--
-- Hay 32 filas CONTROLADA que TAMBIEN auto-referencian: son las
-- "CONCILIACIONES DEL PATRIMONIO" de YPF, donde la empresa relacionada es
-- YPF misma. Un consumidor que las lea como estados de una subsidiaria
-- contabiliza a YPF dentro de YPF -- exactamente el fallo que 026 decia
-- prevenir, y que dejaba pasar en 32 de 36 casos.
--
-- El defecto de 026 es el mismo patron que F-039, F-026 y el primer CHECK de
-- F-038: escribir la garantia contra el caso que acababa de descubrir, en vez
-- de contra el invariante. El invariante no es "el valor es CONTROLANTE": es
-- "la empresa relacionada es la del propio perfil".
--
-- No se borra 026: registra que paso. Se la corrige.
-- =====================================================================

ALTER TABLE fetch_raw.cnv_presentation DROP COLUMN IF EXISTS relacion_es_inversa;

ALTER TABLE fetch_raw.cnv_presentation
  ADD COLUMN IF NOT EXISTS es_autorreferencia BOOLEAN
  GENERATED ALWAYS AS (
      cuit_relacionado IS NOT NULL AND cuit_relacionado = cuit
  ) STORED;

COMMENT ON COLUMN fetch_raw.cnv_presentation.es_autorreferencia IS
  'TRUE cuando la empresa "relacionada" de la fila es la del propio perfil '
  '(cuit_relacionado = cuit). Ocurre en las filas CONTROLANTE (la fila nombra '
  'al controlante del perfil) y en conciliaciones patrimoniales declaradas '
  'CONTROLADA. Ningun consumidor debe leerlas como estados de una subsidiaria: '
  'contabilizaria la empresa dentro de si misma. Ver F039_CONTRATO.md.';
