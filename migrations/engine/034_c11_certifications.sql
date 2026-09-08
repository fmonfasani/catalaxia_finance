-- =====================================================================
-- 034_c11_certifications.sql  ·  CAPA 11 — CERTIFICACIÓN INDEPENDIENTE
-- =====================================================================
-- Contrato: docs/review/bymastocks_reingenieria/fase_definir/04_R4_CAPA11.md
--
-- C11 es READ-ONLY sobre las tablas de cálculo: lee `engine.runs`,
-- `engine.stage_runs` (evidencia de C10) y `engine.checkpoints` cuando
-- corresponde, y produce UN veredicto determinista por corrida. No calcula
-- datos, no modifica tablas de cálculo, no publica.
--
-- Esta tabla es la salida PRIMARIA de C11. El JSON de evidencia que emite
-- `c11_certificar.py` es solo artefacto de evidenciación, nunca fuente
-- primaria. Inmutabilidad: un `certification_id` por `run_id`; la
-- re-ejecución es idempotente (ON CONFLICT DO NOTHING) y no reescribe el
-- acta (invaríante INV6 del contrato).
--
-- Numeración: el contrato original proponía `002_c11_certifications.sql`,
-- PERO `002_s01_identity.sql` ya existía y está aplicada (F-049: el runner
-- es el único dueño del registro; el orden de aplicación es por nombre).
-- Se adopta `034_c11_certifications.sql`, consecutivo real posterior a
-- `033_ratio_inputs_solo_si_calculado.sql`. Ver R4_CAPA11_EVIDENCIA.md.
--
-- Esta migración NO se auto-registra en `engine.schema_migrations`: lo hace
-- únicamente el runner (`engine/db.py::_apply_migrations`, F-049).
-- =====================================================================

CREATE TABLE IF NOT EXISTS engine.certifications (
    certification_id    TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES engine.runs(run_id),
    objeto              TEXT NOT NULL,          -- clase de objeto certificado (R4: 'RUN')
    veredicto           TEXT NOT NULL
        CHECK (veredicto IN ('CERTIFICADA','CERTIFICADA_CON_OBSERVACIONES','NEGADA')),
    cert_rule           TEXT NOT NULL,          -- regla/versión de certificación (p.ej. c11-rule-v1)
    cert_hash           TEXT NOT NULL
        CHECK (cert_hash ~ '^[0-9a-f]{64}$'),   -- sha256 determinista sobre la evidencia
    pipeline_version    TEXT NOT NULL,
    stages_total        INT NOT NULL CHECK (stages_total >= 0),
    stages_pass         INT NOT NULL CHECK (stages_pass >= 0),
    stages_warn         INT NOT NULL CHECK (stages_warn >= 0),
    stages_block        INT NOT NULL CHECK (stages_block >= 0),
    stages_insuf        INT NOT NULL CHECK (stages_insuf >= 0),
    CHECK (stages_pass + stages_warn + stages_block + stages_insuf = stages_total),
    evidence            JSONB NOT NULL DEFAULT '{}'::jsonb,  -- referencia al stage/evidencia C10 validada
    motivo              TEXT,                               -- motivo/resultado cuando no limpia
    generado_por        TEXT NOT NULL,
    generado_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- un solo acta por corrida (INV6) — soporta la idempotencia de C11
CREATE UNIQUE INDEX IF NOT EXISTS ux_cert_run ON engine.certifications (run_id);
CREATE INDEX IF NOT EXISTS ix_cert_veredicto ON engine.certifications (veredicto);

-- Permisos: el rol de aplicación puede CONSIDERAR y EMITIR actas, pero no
-- reescribirlas ni borrarlas (INV6). El owner (catalaxia/admin) sí.
GRANT SELECT, INSERT ON engine.certifications TO catalaxia_engine;
REVOKE UPDATE, DELETE ON engine.certifications FROM catalaxia_engine;