# Arquitectura técnica y esquema de base de datos

> Cómo se conecta todo y cómo queda la BD en PostgreSQL. Dueño: **Federico** (DBA/Infra),
> consultado con Mateo (backend).

---

## 1. Diagrama de arquitectura

```
                    ┌───────────────────────────────┐
   Pipeline (ya     │  raw cache (SEC/CNV/IAMC/…)    │   (ya construido y validado)
   existente) ─────▶│  → screener_export.json/csv   │
                    └──────────────┬────────────────┘
                                   │ carga inicial + jobs
                                   ▼
   VPS  ┌─────────────────────────────────────────────────────────┐
        │  PostgreSQL 16   (empresas · instrumentos · dividendos)  │
        └───────────────┬─────────────────────────────────────────┘
                        │ SQLAlchemy 2.0 (async, asyncpg)
                        ▼
        ┌─────────────────────────────┐        ┌──────────────────┐
        │  FastAPI (Uvicorn)          │◀──────▶│ APScheduler jobs │
        │  /empresas /instrumentos …  │        │ precios, financ. │
        └───────────────┬─────────────┘        └──────────────────┘
                        │ HTTPS (nginx) · dominio · CORS
                        ▼
        ┌─────────────────────────────┐
        │  Next.js (screener + detalle)│  ← Joaquín / Aldana
        └─────────────────────────────┘
```

## 2. Principios

- **La BD es de solo lectura para la API.** La escribe el pipeline/jobs; la API sirve.
- **Modelo de 2 niveles:** `empresas` (fundamentales, 1 fila/empresa) + `instrumentos`
  (1 fila por instrumento negociable: ADR/CEDEAR/local, con ISIN, precio, moneda, ratio).
- **Provenance:** cada dato "sensible" (precio, ratio de conversión) guarda su `source_url`.
- **El pipeline no se toca.** Se lo trata como productor externo; la migración solo mueve su
  salida (`screener_export.json` + `instrumentos.csv` + tablas) a PostgreSQL.

## 3. Esquema PostgreSQL (borrador — a refinar en Semana 1)

```sql
-- 1 fila por empresa (el screener / fundamentales)
CREATE TABLE empresas (
    id            TEXT PRIMARY KEY,        -- cik / company_id
    ticker        TEXT NOT NULL,
    nombre        TEXT,
    grupo         TEXT NOT NULL,           -- 'sp500' | 'adr' | 'byma'
    sector        TEXT,
    pais          TEXT,
    moneda_rep    TEXT,                    -- moneda de reporte de los EECC
    -- fundamentales / ratios (~16)
    per           NUMERIC, pb NUMERIC, roe NUMERIC, roa NUMERIC,
    margen_neto   NUMERIC, margen_operativo NUMERIC,
    ev_ebitda     NUMERIC, deuda_ebitda NUMERIC, fcf_yield NUMERIC,
    cagr_ingresos NUMERIC, cagr_eps NUMERIC,
    -- precios
    precio_ars    NUMERIC, precio_usd NUMERIC, ccl NUMERIC,
    precio_fuente TEXT, precio_dif_iamc NUMERIC,
    mcap_usd      NUMERIC,
    -- calidad / trazabilidad
    flag_no_significativo BOOLEAN DEFAULT false,
    dato_desactualizado   BOOLEAN DEFAULT false,
    generated_at  TIMESTAMPTZ,
    UNIQUE (ticker, grupo)
);

-- 1 fila por instrumento negociable (modelo 2 niveles)
CREATE TABLE instrumentos (
    id           BIGSERIAL PRIMARY KEY,
    empresa_id   TEXT REFERENCES empresas(id),
    tipo         TEXT NOT NULL,            -- 'ordinaria_us'|'adr'|'cedear'|'ordinaria_ar'
    ticker       TEXT NOT NULL,
    mercado      TEXT,                     -- 'NYSE'|'NASDAQ'|'BYMA'
    moneda       TEXT,                     -- 'USD'|'ARS'
    isin         TEXT,
    ratio        NUMERIC,                  -- cedear_ratio (N:1) o adr_ratio (1 ADR = N acc)
    ratio_tipo   TEXT,                     -- 'cedear' | 'adr' | null
    precio       NUMERIC,
    precio_fecha DATE,
    fuente       TEXT,                     -- 'Comafi'|'SEC F-6'|'IAMC'|'yfinance'|'JPMorgan'
    source_url   TEXT
);
CREATE INDEX idx_instr_empresa ON instrumentos(empresa_id);
CREATE INDEX idx_instr_tipo    ON instrumentos(tipo, mercado);

-- dividendos del ADR (para el detalle)
CREATE TABLE adr_dividendos (
    id         BIGSERIAL PRIMARY KEY,
    empresa_id TEXT REFERENCES empresas(id),
    fecha      DATE, monto_adr NUMERIC, moneda TEXT, fuente TEXT
);

-- registro de jobs (para el panel de estado)
CREATE TABLE jobs (
    id          BIGSERIAL PRIMARY KEY,
    tipo        TEXT NOT NULL,             -- 'precios'|'financials'|'rebuild'
    estado      TEXT NOT NULL,             -- 'pending'|'running'|'done'|'error'
    started_at  TIMESTAMPTZ, finished_at TIMESTAMPTZ,
    detalle     JSONB
);
```

> El shape exacto se cierra en Semana 1 mapeando 1:1 contra `data/screener_export.json` y
> `data/instrumentos.csv` (los entregables reales del pipeline). Este borrador ya cubre el 90 %.

## 4. Migración (Semana 1, Federico)

1. Crear el esquema en PostgreSQL (VPS).
2. Script de carga: leer `screener_export.json` → `empresas`; `instrumentos.csv` → `instrumentos`;
   `adr_dividendos` → tabla. Idempotente (upsert por PK).
3. Verificar conteos: 572 en `empresas`, 733 en `instrumentos` (validación de carga).
4. Enganchar los **jobs** para que reescriban las tablas tras cada rebuild del pipeline.

## 5. Decisiones ya tomadas (no re-discutir)

- **PostgreSQL 16** (hoy SQLite validado) · **SQLAlchemy 2.0 async + asyncpg**.
- **FastAPI + Uvicorn** detrás de **nginx** (TLS) en la VPS.
- **Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui** en el front.
- La API es **read-only**; la escritura la hacen pipeline + jobs.
