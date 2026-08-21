-- ============================================================================
-- 002 — Alinear la base de PRODUCCION con sql/init/01_schema.sql
-- PostgreSQL 16
-- ============================================================================
-- POR QUE HACE FALTA ESTE ARCHIVO
--
--   sql/init/01_schema.sql es todo `CREATE TABLE IF NOT EXISTS`. Sobre una base
--   ya poblada eso NO agrega ni una columna: las tablas existen, y psql las
--   saltea con un NOTICE. Aplicarlo tal cual a produccion (hecho el 2026-08-21)
--   creo `cnv_doc_meta` y nada mas.
--
--   Medido contra produccion ese mismo dia, faltaban 15 columnas repartidas asi:
--
--       cnv_estados_v2      1   tipo_balance
--       cnv_estados_norm    3   tipo_balance, perimetro_mixto, identidad_desvio_pct
--       screener           11   la migracion IAMC -> MEP
--
--   Este archivo cierra las 4 primeras. Las 11 de `screener` NO estan aca y no
--   es un olvido: ver migrations/003_screener_iamc_mep.sql.
--
-- QUE SE PIERDE
--
--   Nada. Todo lo de abajo es aditivo salvo el cambio de PK, que AMPLIA la
--   clave de 4 a 5 columnas. Ampliar una PK solo admite mas filas: no puede
--   rechazar ni borrar ninguna de las que ya estan. Verificado antes de correr:
--   0 filas afectadas en cnv_estados_v2 (81.695) y cnv_estados_norm (84.316).
--
-- POR QUE LA PK IGUAL IMPORTA AHORA
--
--   La PK vieja (cuit, concepto, period_end, fecha_reexpresion) hace colisionar
--   el balance individual con el consolidado. En SQLite eso ya costo el 25% de
--   las filas (81.695 reales contra 102.323 de la version corregida; ver
--   scripts/tickets/screener/aplicar_pk_cnv_v2.py). Cuando esa base corregida
--   se migre a PostgreSQL, con la PK vieja las ~20.628 filas recuperadas se
--   volverian a perder en silencio. Se amplia antes para que no pase.
--
-- MARCHA ATRAS
--   BEGIN;
--     ALTER TABLE cnv_estados_v2   DROP CONSTRAINT cnv_estados_v2_pkey;
--     ALTER TABLE cnv_estados_v2   ADD PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion);
--     ALTER TABLE cnv_estados_norm DROP CONSTRAINT cnv_estados_norm_pkey;
--     ALTER TABLE cnv_estados_norm ADD PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion);
--   COMMIT;
--   (las columnas nuevas pueden quedar: nadie las lee todavia)
--
-- QUE NO TOCA
--   `screener`, `screener_v2` y la API. Ningun endpoint de api/main.py consulta
--   cnv_estados_v2 ni cnv_estados_norm.
-- ============================================================================

BEGIN;

-- ── cnv_estados_v2 ──────────────────────────────────────────────────────────
ALTER TABLE cnv_estados_v2
    ADD COLUMN IF NOT EXISTS tipo_balance TEXT DEFAULT '';

-- Las filas que ya estaban entraron con la PK vieja, o sea sin perimetro
-- declarado. '' es el mismo default que declara el schema del repo.
UPDATE cnv_estados_v2 SET tipo_balance = '' WHERE tipo_balance IS NULL;
ALTER TABLE cnv_estados_v2 ALTER COLUMN tipo_balance SET NOT NULL;

ALTER TABLE cnv_estados_v2 DROP CONSTRAINT IF EXISTS cnv_estados_v2_pkey;
ALTER TABLE cnv_estados_v2
    ADD CONSTRAINT cnv_estados_v2_pkey
    PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance);

-- ── cnv_estados_norm ────────────────────────────────────────────────────────
ALTER TABLE cnv_estados_norm
    ADD COLUMN IF NOT EXISTS tipo_balance         TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS perimetro_mixto      INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS identidad_desvio_pct DOUBLE PRECISION;

UPDATE cnv_estados_norm SET tipo_balance = '' WHERE tipo_balance IS NULL;
ALTER TABLE cnv_estados_norm ALTER COLUMN tipo_balance SET NOT NULL;

ALTER TABLE cnv_estados_norm DROP CONSTRAINT IF EXISTS cnv_estados_norm_pkey;
ALTER TABLE cnv_estados_norm
    ADD CONSTRAINT cnv_estados_norm_pkey
    PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance);

COMMIT;
