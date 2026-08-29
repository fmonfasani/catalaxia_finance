-- Aditiva. El check C-S03-006 (integridad referencial context_id/unit_ref) hace
-- un NOT EXISTS correlacionado de parsed.facts contra parsed.contexts/parsed.units
-- por (run_id, accession_number, context_id|unit_ref). Sin estos indices el plan
-- es nested-loop + seq scan: sobre ~67k facts (golden case YPF) supera el
-- statement_timeout de 120s ya configurado (incidente previo de S01, no se toca
-- el timeout). No cambia semantica de ninguna tabla ni columna.

CREATE INDEX IF NOT EXISTS ix_ctx_run_acc_id ON parsed.contexts (run_id, accession_number, context_id);
CREATE INDEX IF NOT EXISTS ix_units_run_acc_ref ON parsed.units (run_id, accession_number, unit_ref);
