-- =====================================================================
-- 015_s04_unidad_resuelta.sql
-- =====================================================================
-- Hallazgo de la primera ejecucion real de S04 (gate BLOCK en C-S04-005):
-- 436 hechos con unidad DIVIDED (Unit_USD_per_Share, Unit_ARS_per_Share,
-- Unit_USD_bbl) quedaban fuera porque no tienen unidad resoluble.
--
-- Causa: S03 no extrae numerator/denominator de las unidades divididas.
-- `parsed.facts.numerator` esta NULL en los 436, y `parsed.units` tampoco los
-- tiene: `measures = []`, numerator y denominator NULL. -> F-026, contra S03.
--
-- El unico dato disponible es el NOMBRE del unit_ref ('Unit_USD_per_Share').
-- Derivar la moneda de ahi seria inferir identidad por nombre, que es
-- exactamente lo que este proyecto prohibe.
--
-- Decision: NO se descartan y NO se les inventa la unidad. Se emiten con
-- `unidad_resuelta = false`. El valor esta, la unidad queda declarada como no
-- resuelta, y el conflicto dice por que. Quien calcule ratios filtra por
-- `unidad_resuelta`; quien audite ve los 436 y su motivo.
-- =====================================================================

ALTER TABLE derived.fact
  ADD COLUMN IF NOT EXISTS unidad_resuelta BOOLEAN NOT NULL DEFAULT true;

COMMENT ON COLUMN derived.fact.unidad_resuelta IS
  'false = el hecho tiene unidad declarada pero no descomponible (F-026). '
  'No usar para calculo sin resolver la unidad primero.';

-- el CHECK pasa a exigir medida solo cuando la unidad SI se resolvio
ALTER TABLE derived.fact DROP CONSTRAINT IF EXISTS ck_numerico_con_unidad;
ALTER TABLE derived.fact ADD CONSTRAINT ck_numerico_con_unidad CHECK (
    NOT (is_numeric AND NOT is_nil AND unidad_resuelta) OR unit_measure IS NOT NULL);

-- si la unidad no se resolvio, tiene que haber quedado dicho de donde venia
ALTER TABLE derived.fact DROP CONSTRAINT IF EXISTS ck_unidad_no_resuelta_declarada;
ALTER TABLE derived.fact ADD CONSTRAINT ck_unidad_no_resuelta_declarada CHECK (
    unidad_resuelta OR unit_ref IS NOT NULL);

CREATE INDEX IF NOT EXISTS ix_dfact_unidad_resuelta
    ON derived.fact (unidad_resuelta) WHERE NOT unidad_resuelta;
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
