-- =====================================================================
-- 008_identity_v1.sql — Identity v1
-- =====================================================================
-- Capa de identidad independiente y auditable.
--
-- Decisiones que implementa (ver IDENTITY_DECISION_RECORD.md):
--   D-I-A  la assertion es objeto de primera clase, no un par de columnas
--   D-I-B  entity_key opaco, NO derivado de ningun identificador
--   D-I-D  TICKER y YF_SYMBOL nunca son autoritativos
--   D-I-03 A1: Identity centralizada en este PostgreSQL (5433)
--   G5     CIK->LEI no tiene fuente primaria => la resolucion humana es una
--          capacidad PERMANENTE, no un paso transitorio
--
-- Convive con el schema `identity` existente (seeding SEC). No lo toca.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS identity_v1;

-- ---------------------------------------------------------------------
-- Catalogo de fuentes: define la AUTORIDAD, que es propiedad de la fuente
-- y no del dato. Una fuente puede ser autoritativa para un id_type y no
-- serlo para otro (GLEIF: autoritativa para CUIT via AFIP, inutil para CIK).
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.source (
    source_id       TEXT PRIMARY KEY,
    descripcion     TEXT        NOT NULL,
    authority_level TEXT        NOT NULL
        CHECK (authority_level IN ('AUTHORITATIVE','CORROBORATING','DISCOVERY_ONLY','UNUSABLE')),
    -- para que id_type es autoritativa. NULL => para ninguno.
    authoritative_for TEXT[],
    url             TEXT,
    notas           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- ENTITY — el emisor economico. Clave OPACA.
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.entity (
    entity_key      TEXT PRIMARY KEY
        CHECK (entity_key ~ '^E[0-9A-HJKMNP-TV-Z]{26}$'),   -- ULID
    preferred_name  TEXT        NOT NULL,
    country         TEXT,
    entity_status   TEXT        NOT NULL DEFAULT 'ACTIVE'
        CHECK (entity_status IN ('ACTIVE','MERGED','DISSOLVED','PROVISIONAL')),
    merged_into_key TEXT REFERENCES identity_v1.entity(entity_key),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_merged_coherente CHECK (
        (entity_status = 'MERGED') = (merged_into_key IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- ASSERTION — el objeto central. Afirmar que un identificador pertenece a
-- una entidad (o que dos identificadores son la misma entidad) es un HECHO
-- CON AUTOR, no una propiedad intrinseca del dato.
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.assertion (
    assertion_id    BIGSERIAL PRIMARY KEY,
    subject_type    TEXT NOT NULL
        CHECK (subject_type IN ('ENTITY_IDENTIFIER','IDENTIFIER_BRIDGE',
                                'ENTITY_INSTRUMENT','ENTITY_MERGE')),
    entity_key      TEXT REFERENCES identity_v1.entity(entity_key),
    left_ref        TEXT,          -- p.ej. 'CIK:SEC:0000904851'
    right_ref       TEXT,          -- p.ej. 'CUIT:AFIP:30546689979'
    relationship    TEXT,          -- SAME_ENTITY | BELONGS_TO | ...

    method          TEXT NOT NULL
        CHECK (method IN ('REGISTRY','REGULATORY_DOCUMENT','CROSS_REFERENCE',
                          'HUMAN_DECISION','DERIVED_RULE','LEGACY_IMPORT')),
    confidence      TEXT NOT NULL
        CHECK (confidence IN ('AUTHORITATIVE','STRONG','WEAK','DISPUTED')),
    status          TEXT NOT NULL
        CHECK (status IN ('UNRESOLVED','CANDIDATE','REVIEW_REQUIRED','VERIFIED','REJECTED')),

    source_id       TEXT REFERENCES identity_v1.source(source_id),
    source_record   TEXT,          -- accession, URL, fila
    evidence        TEXT,          -- cita textual verificable por un tercero

    resolved_by     TEXT,          -- persona o proceso
    resolution_reason TEXT,

    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ,
    superseded_by   BIGINT REFERENCES identity_v1.assertion(assertion_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- INTEGRIDAD 1: no se publica VERIFIED sin evidencia y sin autor.
    CONSTRAINT ck_verified_exige_evidencia CHECK (
        status <> 'VERIFIED'
        OR (evidence IS NOT NULL AND source_id IS NOT NULL AND resolved_by IS NOT NULL)),

    -- INTEGRIDAD 2: una decision humana debe declarar quien y por que.
    CONSTRAINT ck_humano_exige_autor CHECK (
        method <> 'HUMAN_DECISION'
        OR (resolved_by IS NOT NULL AND resolution_reason IS NOT NULL)),

    -- INTEGRIDAD 3: AUTHORITATIVE exige metodo compatible. Una regla derivada
    -- o un import legacy NUNCA pueden ser autoritativos.
    CONSTRAINT ck_authoritative_metodo CHECK (
        confidence <> 'AUTHORITATIVE'
        OR method IN ('REGISTRY','REGULATORY_DOCUMENT')),

    -- INTEGRIDAD 4: un bridge necesita sus dos extremos.
    CONSTRAINT ck_bridge_dos_extremos CHECK (
        subject_type <> 'IDENTIFIER_BRIDGE'
        OR (left_ref IS NOT NULL AND right_ref IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- IDENTIFIER — como cada fuente nombra a la entidad.
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.identifier (
    identifier_id   BIGSERIAL PRIMARY KEY,
    entity_key      TEXT NOT NULL REFERENCES identity_v1.entity(entity_key),
    id_type         TEXT NOT NULL
        CHECK (id_type IN ('CIK','CUIT','LEI','TICKER','ISIN','YF_SYMBOL',
                           'CNV_ENTITY_ID','LEGACY_ENTITY_ID')),
    id_namespace    TEXT NOT NULL,      -- SEC | AFIP | GLEIF | US | BYMA | YAHOO | CNV | LEGACY
    id_value        TEXT NOT NULL,
    is_authoritative BOOLEAN NOT NULL DEFAULT false,
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','RETIRED','DISPUTED')),
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ,
    assertion_id    BIGINT NOT NULL REFERENCES identity_v1.assertion(assertion_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- INTEGRIDAD 5: el ticker NUNCA es identidad juridica. Constraint duro.
    CONSTRAINT ck_ticker_no_autoritativo CHECK (
        NOT (is_authoritative AND id_type IN ('TICKER','YF_SYMBOL','LEGACY_ENTITY_ID')))
);

-- INTEGRIDAD 6: un identificador AUTORITATIVO vigente no puede apuntar a dos
-- entidades. Esto es lo que hace IMPOSIBLE el error historico
-- (CUIT de CEPU atribuido a YPF).
CREATE UNIQUE INDEX ux_identifier_autoritativo_unico
    ON identity_v1.identifier (id_type, id_namespace, id_value)
    WHERE is_authoritative AND valid_to IS NULL;

-- INTEGRIDAD 7: una entidad no puede tener dos identificadores autoritativos
-- vigentes del mismo tipo (dos CUIT, dos CIK).
CREATE UNIQUE INDEX ux_entity_un_autoritativo_por_tipo
    ON identity_v1.identifier (entity_key, id_type, id_namespace)
    WHERE is_authoritative AND valid_to IS NULL;

CREATE INDEX ix_identifier_entity  ON identity_v1.identifier (entity_key);
CREATE INDEX ix_identifier_lookup  ON identity_v1.identifier (id_type, id_value);

-- ---------------------------------------------------------------------
-- INSTRUMENT — lo que se opera. La entidad emite; el instrumento cotiza.
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.instrument (
    instrument_key  TEXT PRIMARY KEY,
    entity_key      TEXT NOT NULL REFERENCES identity_v1.entity(entity_key),
    instrument_type TEXT NOT NULL
        CHECK (instrument_type IN ('EQUITY','ADR','CEDEAR','BOND')),
    exchange        TEXT NOT NULL,
    currency        TEXT NOT NULL,
    ratio_underlying NUMERIC,
    status          TEXT NOT NULL DEFAULT 'ACTIVE',
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ,
    assertion_id    BIGINT REFERENCES identity_v1.assertion(assertion_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- INTEGRIDAD 8: ADR/CEDEAR sin ratio produce errores de factor N silenciosos.
    CONSTRAINT ck_ratio_obligatorio CHECK (
        instrument_type NOT IN ('ADR','CEDEAR') OR ratio_underlying IS NOT NULL)
);

CREATE TABLE identity_v1.instrument_symbol (
    symbol_id       BIGSERIAL PRIMARY KEY,
    instrument_key  TEXT NOT NULL REFERENCES identity_v1.instrument(instrument_key),
    id_namespace    TEXT NOT NULL,     -- YAHOO | BYMA | US
    symbol          TEXT NOT NULL,
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ
);

-- INTEGRIDAD 9: un simbolo vigente pertenece a un solo instrumento.
CREATE UNIQUE INDEX ux_symbol_vigente
    ON identity_v1.instrument_symbol (id_namespace, symbol)
    WHERE valid_to IS NULL;

-- ---------------------------------------------------------------------
-- REVIEW — cola de resolucion humana. Capacidad PERMANENTE (ver G5).
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.review (
    review_id       BIGSERIAL PRIMARY KEY,
    entity_key      TEXT REFERENCES identity_v1.entity(entity_key),
    candidate_identifiers JSONB NOT NULL,
    reason          TEXT NOT NULL,
    evidence        TEXT,
    status          TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN','RESOLVED','REJECTED','ACCEPTED_AMBIGUOUS')),
    reviewer        TEXT,
    decision        TEXT,
    decision_reason TEXT,
    resolution_assertion_id BIGINT REFERENCES identity_v1.assertion(assertion_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,

    -- INTEGRIDAD 10: no se cierra una review sin reviewer, decision y motivo.
    CONSTRAINT ck_cierre_exige_reviewer CHECK (
        status = 'OPEN'
        OR (reviewer IS NOT NULL AND decision IS NOT NULL
            AND decision_reason IS NOT NULL AND resolved_at IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- CONFLICT — ambiguedad explicita. Nunca se resuelve en silencio.
-- ---------------------------------------------------------------------
CREATE TABLE identity_v1.conflict (
    conflict_id     BIGSERIAL PRIMARY KEY,
    id_type         TEXT NOT NULL,
    id_namespace    TEXT NOT NULL,
    id_value        TEXT,
    candidate_entity_keys JSONB NOT NULL,
    detected_by     TEXT,
    reason          TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (state IN ('OPEN','RESOLVED','ACCEPTED_AMBIGUOUS')),
    resolution_assertion_id BIGINT REFERENCES identity_v1.assertion(assertion_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,

    -- INTEGRIDAD 11: OPEN sin resolucion; resuelto CON resolucion.
    CONSTRAINT ck_conflict_resolucion CHECK (
        (state = 'OPEN'  AND resolution_assertion_id IS NULL)
     OR (state <> 'OPEN' AND resolution_assertion_id IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- INTEGRIDAD 12: las assertions historicas son INMUTABLES.
-- Una assertion cerrada (valid_to poblado) o REJECTED no puede editarse:
-- se supersede creando una nueva. Esto impide la modificacion silenciosa.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.fn_assertion_inmutable()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.valid_to IS NOT NULL OR OLD.status = 'REJECTED' THEN
        -- En una assertion historica el UNICO campo mutable es superseded_by
        -- (encadenar la sucesion). Cualquier otro cambio es reescritura del
        -- pasado y se rechaza. Se comparan las columnas explicitamente: usar
        -- ROW(NEW.*) IS DISTINCT FROM ROW(OLD.*) dejaria pasar un cambio
        -- combinado (superseded_by + otra columna en el mismo UPDATE).
        IF ROW(NEW.assertion_id, NEW.subject_type, NEW.entity_key, NEW.left_ref,
               NEW.right_ref, NEW.relationship, NEW.method, NEW.confidence,
               NEW.status, NEW.source_id, NEW.source_record, NEW.evidence,
               NEW.resolved_by, NEW.resolution_reason, NEW.valid_from,
               NEW.valid_to, NEW.created_at)
           IS DISTINCT FROM
           ROW(OLD.assertion_id, OLD.subject_type, OLD.entity_key, OLD.left_ref,
               OLD.right_ref, OLD.relationship, OLD.method, OLD.confidence,
               OLD.status, OLD.source_id, OLD.source_record, OLD.evidence,
               OLD.resolved_by, OLD.resolution_reason, OLD.valid_from,
               OLD.valid_to, OLD.created_at)
        THEN
            RAISE EXCEPTION
              'Assertion % es historica (valid_to=% status=%): es inmutable. '
              'Cree una nueva assertion con superseded_by en lugar de modificarla.',
              OLD.assertion_id, OLD.valid_to, OLD.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_assertion_inmutable
    BEFORE UPDATE ON identity_v1.assertion
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_assertion_inmutable();

-- INTEGRIDAD 13: no se borra provenance de una assertion vigente.
CREATE OR REPLACE FUNCTION identity_v1.fn_no_borrar_vigente()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.valid_to IS NULL AND OLD.status IN ('VERIFIED','CANDIDATE') THEN
        RAISE EXCEPTION
          'Assertion % esta vigente (status=%): no puede eliminarse. '
          'Cierrela con valid_to o superseda_la.', OLD.assertion_id, OLD.status;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_no_borrar_vigente
    BEFORE DELETE ON identity_v1.assertion
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_no_borrar_vigente();

-- ---------------------------------------------------------------------
-- INTEGRIDAD 14: un identificador AUTORITATIVO exige una assertion VERIFIED.
-- Encadenado con ck_verified_exige_evidencia esto produce la garantia dura:
-- no existe identificador autoritativo sin evidencia citable y sin autor.
-- Ademas, la confianza WEAK/DISPUTED nunca puede volverse autoritativa.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identity_v1.fn_identifier_autoritativo_exige_verified()
RETURNS TRIGGER AS $$
DECLARE
    a_status     TEXT;
    a_confidence TEXT;
BEGIN
    IF NOT NEW.is_authoritative THEN
        RETURN NEW;
    END IF;
    SELECT status, confidence INTO a_status, a_confidence
      FROM identity_v1.assertion WHERE assertion_id = NEW.assertion_id;
    IF a_status <> 'VERIFIED' OR a_confidence NOT IN ('AUTHORITATIVE','STRONG') THEN
        RAISE EXCEPTION
          'Identificador %:%:% no puede ser autoritativo: la assertion % es '
          'status=% confidence=%. Se exige VERIFIED con confidence '
          'AUTHORITATIVE o STRONG.',
          NEW.id_type, NEW.id_namespace, NEW.id_value,
          NEW.assertion_id, a_status, a_confidence;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_identifier_autoritativo
    BEFORE INSERT OR UPDATE ON identity_v1.identifier
    FOR EACH ROW EXECUTE FUNCTION identity_v1.fn_identifier_autoritativo_exige_verified();

-- ---------------------------------------------------------------------
-- Vista de resolucion: estado de identidad por entidad, derivado de los
-- hechos, no almacenado. Lo que no tiene respaldo aparece como faltante.
-- ---------------------------------------------------------------------
CREATE VIEW identity_v1.v_entity_resolution AS
SELECT e.entity_key,
       e.preferred_name,
       MAX(i.id_value) FILTER (WHERE i.id_type='CIK'  AND i.is_authoritative AND i.valid_to IS NULL) AS cik,
       MAX(i.id_value) FILTER (WHERE i.id_type='CUIT' AND i.is_authoritative AND i.valid_to IS NULL) AS cuit,
       MAX(i.id_value) FILTER (WHERE i.id_type='LEI'  AND i.is_authoritative AND i.valid_to IS NULL) AS lei,
       COUNT(*) FILTER (WHERE i.is_authoritative AND i.valid_to IS NULL) AS n_autoritativos,
       (SELECT COUNT(*) FROM identity_v1.review r
         WHERE r.entity_key = e.entity_key AND r.status='OPEN')          AS reviews_abiertas,
       (SELECT COUNT(*) FROM identity_v1.conflict c
         WHERE c.candidate_entity_keys ? e.entity_key AND c.state='OPEN') AS conflictos_abiertos
  FROM identity_v1.entity e
  LEFT JOIN identity_v1.identifier i ON i.entity_key = e.entity_key
 GROUP BY e.entity_key, e.preferred_name;

-- ---------------------------------------------------------------------
-- Catalogo inicial de fuentes, con la autoridad establecida en los
-- ciclos 3B..G5. NO se inventa autoridad: cada nivel esta respaldado.
-- ---------------------------------------------------------------------
INSERT INTO identity_v1.source (source_id, descripcion, authority_level, authoritative_for, url, notas) VALUES
 ('SEC_REGISTRY',   'SEC company_tickers / submissions', 'AUTHORITATIVE', ARRAY['CIK'],
  'https://data.sec.gov', 'Fuente de registro del CIK. NO publica LEI (G5: 0/6 en control).'),
 ('SEC_20F',        'Formulario 20-F ante la SEC', 'AUTHORITATIVE', ARRAY['CIK','CUIT'],
  'https://www.sec.gov/Archives/edgar', 'Autoritativa para CUIT SOLO si declara bloque de identificacion. Cobertura medida 1/4 (ciclo 3C).'),
 ('GLEIF',          'Global LEI Foundation', 'AUTHORITATIVE', ARRAY['LEI','CUIT'],
  'https://api.gleif.org/api/v1', 'Autoritativa para CUIT cuando registeredAt=RA000009(AFIP)/RA000010(RNS). NO establece CIK (G4/G5).'),
 ('AFIP',           'Constancia de inscripcion AFIP', 'AUTHORITATIVE', ARRAY['CUIT'],
  'https://seti.afip.gob.ar', 'Maxima autoridad para CUIT. NO automatizable: captcha (ciclo 3D).'),
 ('CNV_PORTAL',     'Portal CNV', 'DISCOVERY_ONLY', NULL,
  'https://www.cnv.gov.ar', 'NO declara el CUIT del emisor; solo del auditor (ciclo 3D).'),
 ('LEGACY_DIM_ENTITY','Catalogo legacy dim_entity (SQLite)', 'CORROBORATING', NULL,
  NULL, 'Sin autor ni evidencia. Ya fallo con el CIK de YPF (4 conflictos). Solo corrobora.'),
 ('HUMAN',          'Decision humana registrada', 'AUTHORITATIVE', NULL,
  NULL, 'Capacidad PERMANENTE de Identity v1: CIK->LEI no tiene fuente primaria (G5).'),
 ('DERIVED_RULE',   'Regla derivada documentada', 'DISCOVERY_ONLY', NULL,
  NULL, 'p.ej. sufijo .BA de Yahoo. Nunca autoritativa.');
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
