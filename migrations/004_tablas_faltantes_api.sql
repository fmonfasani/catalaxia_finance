-- ============================================================================
-- 004 — Las tablas que la API consulta y nunca se migraron
-- PostgreSQL 16                                    aplicada el 2026-08-22
-- ============================================================================
-- POR QUE HACE FALTA
--
--   Cuatro de los once endpoints devolvian HTTP 500. Medido el 2026-08-22
--   contra produccion, antes de este archivo:
--
--       /v1/ratios          500   relation "silver_norm" does not exist
--       /v1/validaciones    500   relation "validaciones" does not exist
--       /v1/certificacion   500   relation "certificacion_nueva" does not exist
--       /v1/mep             500   relation "mep_actual" does not exist
--
--   Las tres primeras existen en SQLite desde hace tiempo; simplemente nunca
--   entraron a PostgreSQL. La cuarta no existia en ningun lado: `mep_actual`
--   es una vista que el endpoint da por sentada y que nadie creo.
--
-- LA VISTA `mep_actual`
--
--   /v1/mep hace `SELECT * FROM mep_actual LIMIT 1`. Se arma con la ultima
--   rueda MEP de `dolarito_cotizaciones` -- la MISMA fuente que usa s9 para
--   llenar `screener.valor_mep_dolarito`. Si se armara con otra fuente, el MEP
--   que sirve la API y el que se uso para calcular los precios en dolares
--   podrian no coincidir, y nadie lo notaria.
--
-- ORDEN
--   dolarito_cotizaciones se crea ANTES que la vista: la vista la consulta.
--
-- MARCHA ATRAS
--   DROP VIEW IF EXISTS mep_actual;
--   DROP TABLE IF EXISTS dolarito_cotizaciones, certificacion_nueva,
--                        validaciones, silver_norm;
--   (vuelven los cuatro 500, que es el estado anterior)
--
-- LOS DATOS NO VIENEN DE ACA
--   Este archivo crea la estructura. Las filas las carga
--   scripts/deploy/sincronizar_a_produccion.py, que exporta de SQLite y hace
--   COPY + upsert. Ver ese script para por que NO se usa
--   migrate_sqlite_to_pg.py.
-- ============================================================================

BEGIN;

-- ── silver_norm ─────────────────────────────────────── /v1/ratios (legacy)
CREATE TABLE IF NOT EXISTS silver_norm (
    ticker              text,
    concepto            text,
    valor               double precision,
    moneda              text,
    escala              double precision,
    period_end          text,
    nivel_certificacion text
);

-- ── validaciones ───────────────────────────────────────── /v1/validaciones
CREATE TABLE IF NOT EXISTS validaciones (
    cuit       text,
    ticker     text,
    regla      text,
    period_end text,
    resultado  text,
    detalle    text
);

-- ── certificacion_nueva ───────────────────────────────── /v1/certificacion
CREATE TABLE IF NOT EXISTS certificacion_nueva (
    cuit       text,
    ticker     text,
    period_end text,
    nivel      text,
    motivo     text
);

-- ── dolarito_cotizaciones ──────────────── fuente del MEP, la misma que s9
CREATE TABLE IF NOT EXISTS dolarito_cotizaciones (
    fecha      text,
    tipo       text,
    compra     double precision,
    venta      double precision,
    ts_ms      bigint,
    ts_ingesta text
);

-- ── mep_actual ───────────────────────────────────────────────── /v1/mep
-- Vista, no tabla: se mueve sola cuando entra una rueda nueva.
DROP VIEW IF EXISTS mep_actual;
CREATE VIEW mep_actual AS
    SELECT fecha, tipo, compra, venta
    FROM dolarito_cotizaciones
    WHERE upper(tipo) = 'MEP'
    ORDER BY fecha DESC
    LIMIT 1;

COMMIT;

-- ============================================================================
-- OJO: la estructura sola no alcanza. `silver_norm`, `validaciones` y
-- `certificacion_nueva` con 0 filas devuelven 200 con lista vacia, y
-- `mep_actual` sin dolarito devuelve null. Correr el sincronizador despues.
-- ============================================================================
