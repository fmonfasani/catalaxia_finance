-- C3 CNV FETCHER: idempotencia por hash canonico. Aditiva: solo agrega columnas
-- e indices sobre las tablas de 005_c3_cnv_fetch.sql; no toca SEC ni Market.
--
-- Decision (2026-08-25, sesion de ejecucion C2->C3): EMPRESA_PAGE y VISOR
-- embeben contenido aleatorio POR REQUEST, por diseno del propio servidor CNV
-- (query-strings de cache-busting en assets estaticos; token anti-forgery
-- ASP.NET en el visor). El sha256 de bytes crudos jamas puede coincidir entre
-- dos fetches de la misma URL, asi que no sirve para decidir si el contenido
-- SUSTANTIVO cambio. `canonical_sha256` (ver engine/cnv/rawstore.py) es un
-- segundo hash, calculado excluyendo unicamente esos 2 patrones confirmados,
-- usado SOLO para el gate de idempotencia -- el RAW en disco y su hash de
-- integridad (`sha256`) no se tocan.

ALTER TABLE fetch_raw.cnv_download_log ADD COLUMN IF NOT EXISTS canonical_sha256 TEXT;
ALTER TABLE fetch_raw.cnv_artifact ADD COLUMN IF NOT EXISTS canonical_sha256 TEXT;

CREATE INDEX IF NOT EXISTS ix_cnv_download_log_canonical
    ON fetch_raw.cnv_download_log (artifact_kind, artifact_key, downloaded_at);
