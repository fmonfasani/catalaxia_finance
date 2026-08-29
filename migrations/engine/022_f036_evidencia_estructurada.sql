-- =====================================================================
-- 022_f036_evidencia_estructurada.sql  ·  cierra F-036
-- =====================================================================
-- F-036 reproducido con el ROL DE LA APLICACION (no con el admin):
--
--   INSERT ... source_id='GLEIF', evidence='GLEIF publica registeredAs
--              30-70496280-7 bajo RA000009'
--   -> ACEPTADO. GGAL adquirio un CUIT que GLEIF NO publica
--      (el registro real dice registeredAt=RA999999, registeredAs=null).
--
-- POR QUE NO SE RESUELVE CON UN CHECK SOBRE LA CITA
-- La base no observa GLEIF. Parsear `evidence` —texto libre— para adivinar si
-- la cita es cierta seria el "CHECK artificial" que el contrato prohibe: fragil,
-- ilegible, y falsamente tranquilizador.
--
-- LO QUE SI PUEDE EXIGIR LA BASE
-- No que la cita sea CIERTA, sino que quien afirma **declare la prueba de forma
-- estructurada**. Un CUIT por via GLEIF solo es legitimo si la autoridad de
-- registro es una que asigna CUIT (G4: RA000009 = AFIP, RA000010 = IGJ/RNS) y
-- si el registro publica el numero. Eso son dos campos, no una narracion.
--
-- El atacante ya no puede colar una frase: tiene que declarar
-- `{"registeredAt": "RA000009", "registeredAs": "..."}`, que es un dato
-- estructurado, falsificable pero **contrastable contra GLEIF por cualquier
-- auditor en un solo request**. Se pasa de una afirmacion inverificable a una
-- verificable. Eso es lo que la base puede garantizar, y es lo que garantiza.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Los hechos estructurados que la fuente declara.
--    `evidence` sigue siendo la cita legible; `source_facts` es la prueba.
-- ---------------------------------------------------------------------
ALTER TABLE identity_v1.assertion
  ADD COLUMN IF NOT EXISTS source_facts JSONB;

COMMENT ON COLUMN identity_v1.assertion.source_facts IS
  'Hechos ESTRUCTURADOS que la fuente declara, no la cita legible. '
  'Para GLEIF->CUIT: {"registeredAt": "RA000009", "registeredAs": "30-54668997-9"}. '
  'Permite contrastar la afirmacion contra la fuente sin leer prosa.';

-- ---------------------------------------------------------------------
-- 2. Un CUIT afirmado por GLEIF debe declarar la autoridad que lo respalda.
--    No valida que GLEIF lo diga: valida que quien afirma lo declare, y que
--    la autoridad declarada sea una que efectivamente asigna CUIT.
-- ---------------------------------------------------------------------
--    NOT VALID: hay 3 assertions historicas (4, 8, 16) que declaran la
--    autoridad correcta pero en `evidence` (texto libre), porque `source_facts`
--    no existia cuando se escribieron. Son inmutables por `tg_assertion_inmutable`
--    y no se reescribe el pasado para que encaje en un contrato nuevo.
--    NOT VALID hace exactamente lo que corresponde: no toca lo existente y
--    valida TODO INSERT y UPDATE futuro.
ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_gleif_cuit_declara_autoridad CHECK (
    NOT (source_id = 'GLEIF'
         AND left_ref LIKE 'CUIT:%'
         AND status = 'VERIFIED')
    OR (source_facts ->> 'registeredAt' IN ('RA000009', 'RA000010')
        AND COALESCE(source_facts ->> 'registeredAs', '') <> '')
  ) NOT VALID;

-- ---------------------------------------------------------------------
-- 3. La aplicacion no promueve is_authoritative por UPDATE.
--    Postgres permite GRANT por columna: se le deja lo que legitimamente
--    modifica (retirar un identificador, marcarlo en disputa) y nada mas.
--
--    ANTES:   catalaxia_engine  UPDATE sobre TODAS las columnas
--    DESPUES: catalaxia_engine  UPDATE solo sobre (valid_to, status)
-- ---------------------------------------------------------------------
REVOKE UPDATE ON identity_v1.identifier FROM catalaxia_engine;
GRANT  UPDATE (valid_to, status) ON identity_v1.identifier TO catalaxia_engine;

--    idem en assertion: cerrar y encadenar, nada mas.
--    ANTES:   UPDATE sobre todas las columnas
--    DESPUES: UPDATE solo sobre (valid_to, superseded_by)
REVOKE UPDATE ON identity_v1.assertion FROM catalaxia_engine;
GRANT  UPDATE (valid_to, superseded_by) ON identity_v1.assertion TO catalaxia_engine;

--    entity: la aplicacion cambia estado y nombre; no reasigna merged_into_key
--    a mano (eso lo hace una migracion administrativa).
--    ANTES:   UPDATE sobre todas las columnas
--    DESPUES: UPDATE solo sobre (preferred_name, country, updated_at)
REVOKE UPDATE ON identity_v1.entity FROM catalaxia_engine;
GRANT  UPDATE (preferred_name, country, updated_at) ON identity_v1.entity TO catalaxia_engine;
-- F-049: el auto-registro se retiro. `engine.schema_migrations` lo escribe
-- UNICAMENTE el runner (engine/db.py). Ver docs/architecture/MIGRATIONS_CONTRACT.md.
