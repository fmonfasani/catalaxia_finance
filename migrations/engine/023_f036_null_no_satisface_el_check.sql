-- 023_f036_null_no_satisface_el_check.sql
--
-- El CHECK de la migracion 022 tenia un hueco de logica trivaluada:
--     source_facts ->> 'registeredAt' IN ('RA000009','RA000010')
-- Con registeredAt ausente, `->>` devuelve NULL, `NULL IN (...)` evalua a NULL,
-- y un CHECK considera NULL como SATISFECHO. Es decir: omitir el campo pasaba,
-- declararlo mal no. Exactamente al reves de lo que hace falta.
--
-- Lo encontro el test parametrizado con {"registeredAt": null, ...}.
ALTER TABLE identity_v1.assertion DROP CONSTRAINT ck_gleif_cuit_declara_autoridad;
ALTER TABLE identity_v1.assertion
  ADD CONSTRAINT ck_gleif_cuit_declara_autoridad CHECK (
    NOT (source_id = 'GLEIF' AND left_ref LIKE 'CUIT:%' AND status = 'VERIFIED')
    OR (COALESCE(source_facts ->> 'registeredAt', '') IN ('RA000009', 'RA000010')
        AND COALESCE(source_facts ->> 'registeredAs', '') <> '')
  ) NOT VALID;
INSERT INTO engine.schema_migrations (filename)
VALUES ('023_f036_null_no_satisface_el_check.sql') ON CONFLICT DO NOTHING;
