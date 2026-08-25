CREATE SCHEMA IF NOT EXISTS engine;

CREATE TABLE IF NOT EXISTS engine.runs (
    run_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('FAST', 'FULL', 'AUDIT')),
    status TEXT NOT NULL DEFAULT 'RUNNING',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    git_commit TEXT,
    pipeline_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS engine.stage_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES engine.runs(run_id),
    stage_id TEXT NOT NULL,
    state TEXT NOT NULL,
    prev_state TEXT,
    gate_status TEXT CHECK (gate_status IN ('PASS', 'WARNING', 'BLOCK')),
    gate_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    report JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_stage_runs_run_stage ON engine.stage_runs (run_id, stage_id);
CREATE INDEX IF NOT EXISTS ix_stage_runs_stage_state ON engine.stage_runs (stage_id, state);

CREATE TABLE IF NOT EXISTS engine.checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    stage_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES engine.runs(run_id),
    input_hash TEXT NOT NULL,
    code_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    artifact_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_checkpoints_reuse
    ON engine.checkpoints (stage_id, input_hash, code_version, contract_version);
