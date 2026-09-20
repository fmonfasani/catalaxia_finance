-- =====================================================================
-- 032_f061_derived_ratio.sql  ·  F-061 + RATIO_CONTRACT 1.0
-- =====================================================================
-- Contrato: outputs/docs/fase_ratios/RATIO_CONTRACT.md
-- Causa raiz: outputs/docs/fase_ratios/F061_ROOT_CAUSE.md
--
-- QUE RESUELVE
-- 1. La capa de ratios calculaba en memoria y escribia a JSON. Sin fila no hay
--    valid_to, ni provenance persistida, ni idempotencia verificable.
-- 2. Un ratio podia consumir hechos de OTRA entidad sin que nada lo notara
--    (F-061). La funcion de deteccion queda declarada aca, en la base, para que
--    cualquier consumidor -- no solo el motor -- pueda auditarlo.
--
-- POR QUE `period_window` Y NO `window`
-- `window` es palabra reservada en PostgreSQL: `CREATE TABLE t (window text)`
-- es un error de sintaxis. El campo del contrato se llama `window`; la columna
-- se llama `period_window`. Es la unica desviacion de nombre respecto del
-- contrato y es forzada por el motor, no por criterio.
--
-- FY Y TTM NO SE PISAN
-- Van en la clave unica. Dos ventanas del mismo ratio y periodo son DOS hechos
-- distintos, ninguno supersede al otro. Es la Regla 1 del contrato.
-- =====================================================================

CREATE TABLE IF NOT EXISTS derived.ratio (
  ratio_key           text PRIMARY KEY,

  -- ── identidad del valor ───────────────────────────────────────────
  entity_key          text        NOT NULL,
  cik                 text        NOT NULL,
  canonical_id        text        NOT NULL,
  period_end          date        NOT NULL,
  period_window       text        NOT NULL,   -- el `window` del contrato
  denominator_basis   text        NOT NULL,
  currency            text,                   -- NULL si la unidad es adimensional

  -- ── el valor ──────────────────────────────────────────────────────
  value               numeric,
  unit                text        NOT NULL,
  status              text        NOT NULL,
  motivo              text,
  publicable          boolean     NOT NULL DEFAULT false,

  -- ── como se obtuvo ────────────────────────────────────────────────
  formula_version     text        NOT NULL,
  formula             text        NOT NULL,
  inputs              jsonb       NOT NULL,

  -- ── provenance y ciclo de vida ────────────────────────────────────
  input_checkpoint_id text        NOT NULL,
  run_id              text        NOT NULL REFERENCES engine.runs(run_id),
  calculated_at       timestamptz NOT NULL DEFAULT now(),
  valid_from          timestamptz NOT NULL DEFAULT now(),
  valid_to            timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ck_ratio_window CHECK (
      period_window IN ('FY', 'TTM', 'Q', 'YTD', 'PIT', 'FORWARD')),
  CONSTRAINT ck_ratio_basis CHECK (
      denominator_basis IN ('CLOSING', 'AVERAGE', 'n/a')),
  CONSTRAINT ck_ratio_status CHECK (
      status IN ('CALCULADO', 'NOT_CALCULABLE', 'REVIEW_REQUIRED')),
  CONSTRAINT ck_ratio_unit CHECK (
      unit IN ('veces', 'fraccion', 'moneda', 'moneda_por_accion')),

  -- R7 · un valor existe si y solo si el status es CALCULADO. Nunca 0 por
  -- "no se pudo", nunca CALCULADO sin numero.
  CONSTRAINT ck_ratio_valor_vs_status CHECK (
      (status =  'CALCULADO' AND value IS NOT NULL) OR
      (status <> 'CALCULADO' AND value IS NULL AND motivo IS NOT NULL)),

  -- R10 · sin provenance no hay valor publicable.
  CONSTRAINT ck_ratio_inputs_no_vacio CHECK (jsonb_array_length(inputs) > 0),

  -- Nada publicable que no este calculado.
  CONSTRAINT ck_ratio_publicable CHECK (NOT publicable OR status = 'CALCULADO')
);

-- LA CLAVE DE IDENTIDAD DEL CONTRATO.
-- `valid_to` participa: cerrar una version y abrir otra no colisiona, pero dos
-- vigentes con la misma identidad si. El indice parcial es la forma correcta
-- porque NULL nunca es igual a NULL en un UNIQUE ordinario.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ratio_identidad_vigente
    ON derived.ratio (entity_key, canonical_id, period_end, period_window,
                      denominator_basis, coalesce(currency, '-'))
 WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS ix_ratio_entidad  ON derived.ratio (entity_key, canonical_id);
CREATE INDEX IF NOT EXISTS ix_ratio_run      ON derived.ratio (run_id);
CREATE INDEX IF NOT EXISTS ix_ratio_vigente  ON derived.ratio (canonical_id, period_end)
 WHERE valid_to IS NULL;


-- =====================================================================
-- F-061 · el invariante de pertenencia, como objeto de la base
-- =====================================================================
-- Todo fact_id de derived.fact.source_fact_ids debe resolver a una fila de
-- parsed.facts DEL MISMO emisor, del MISMO filing y del MISMO concepto.
--
-- No menciona ningun ticker, nombre ni empresa: la regla es de pertenencia via
-- provenance. Se declara como vista para que el motor, los tests y cualquier
-- auditoria externa usen literalmente la misma definicion.
CREATE OR REPLACE VIEW derived.v_fact_pertenencia AS
SELECT d.fact_key,
       d.cik,
       d.entity_key,
       d.accession_number,
       d.qname,
       s.fid                                   AS source_fact_id,
       p.fact_id IS NULL                       AS puntero_huerfano,
       p.cik              IS DISTINCT FROM d.cik              AS cik_ajeno,
       p.accession_number IS DISTINCT FROM d.accession_number AS filing_ajeno,
       p.qname            IS DISTINCT FROM d.qname            AS concepto_ajeno
  FROM derived.fact d
  CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
  LEFT JOIN parsed.facts p ON p.fact_id = s.fid
 WHERE d.valid_to IS NULL;

COMMENT ON VIEW derived.v_fact_pertenencia IS
  'F-061: una fila por puntero de provenance. Cualquier columna booleana en '
  'true es una violacion de pertenencia. Ver F061_ROOT_CAUSE.md.';

COMMENT ON TABLE derived.ratio IS
  'Ratios canonicos (S1). period_window es el `window` del contrato: `window` '
  'es palabra reservada en PostgreSQL. Ver RATIO_CONTRACT.md.';
