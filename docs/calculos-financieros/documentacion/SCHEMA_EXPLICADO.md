# Schema PostgreSQL — 5 Tablas

## Diagrama de Relaciones

```
cedears (MAESTRO)
    ↓ FK
    ├─→ precios_raw (Job 1A escribe, Job 2 lee)
    ├─→ financials_raw (Job 1B escribe, Job 2 lee)
    ├─→ ratios (Job 2 escribe, Frontend lee)
    └─→ jobs (auditoría)
            ↓
        job_errores (FK)
```

---

## 1. `cedears` — Maestro de Tickers

**Propósito:** Punto central de verdad para tickers, CIK, exchange.

| Columna | Tipo | Constraint | Descripción |
|---------|------|-----------|-------------|
| `ticker` | VARCHAR(10) | PK | Ticker BYMA (AAPL, MSFT, etc.) |
| `ticker_sec` | VARCHAR(10) | NOT NULL | Ticker SEC/yfinance |
| `cik` | VARCHAR(10) | NOT NULL | CIK de SEC (0000320193) |
| `nombre` | VARCHAR(150) | NOT NULL | Nombre oficial empresa |
| `exchange` | VARCHAR(10) | NOT NULL | NMS, NYQ, etc. |
| `pais` | VARCHAR(50) | NULL | País origen (USA, etc.) |
| `activo` | BOOLEAN | DEFAULT true | FALSE si CEDEAR suspendido |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Fecha de alta |

**Índices:**
```sql
CREATE INDEX idx_cedears_cik ON cedears (cik);
CREATE INDEX idx_cedears_activo ON cedears (activo) WHERE activo = true;
```

**Notas:**
- 422 tickers BYMA → 295 tickers SEC únicos (varios BYMA apuntan al mismo SEC)
- Los jobs filtran por `WHERE activo = true`

---

## 2. `precios_raw` — Datos Crudos de yfinance

**Propósito:** Guardar exactamente lo que devuelve yfinance, sin transformar.

| Columna | Tipo | Constraint | Descripción |
|---------|------|-----------|-------------|
| `ticker_sec` | VARCHAR(10) | PK, FK cedears | Ticker de descarga |
| `last_price` | FLOAT | NULL | Precio actual USD |
| `year_high` | FLOAT | NULL | Máximo 52w |
| `year_low` | FLOAT | NULL | Mínimo 52w |
| `market_cap` | FLOAT | NULL | Cap. de mercado |
| `shares` | FLOAT | NULL | Acciones en circulación |
| `currency` | VARCHAR(5) | NULL | Moneda |
| `exchange_yf` | VARCHAR(20) | NULL | Exchange reportado |
| `previous_close` | FLOAT | NULL | Cierre anterior |
| `fetched_at` | TIMESTAMP | NOT NULL | Timestamp exacto |

**Índices:**
```sql
CREATE INDEX idx_precios_raw_fetched ON precios_raw (fetched_at);
```

**Notas:**
- UPSERT (INSERT ... ON CONFLICT UPDATE): reescribe cada vez
- Job 1A corre diario, actualiza esto
- Job 2 lee: `SELECT * FROM precios_raw WHERE ticker_sec = ?`

---

## 3. `financials_raw` — Datos Crudos de SEC EDGAR

**Propósito:** 1 fila = 1 datapoint (métrica × período × empresa).

| Columna | Tipo | Constraint | Descripción |
|---------|------|-----------|-------------|
| `id` | BIGSERIAL | PK | Auto-increment |
| `cik` | VARCHAR(10) | FK cedears, NOT NULL | Empresa |
| `ticker_sec` | VARCHAR(10) | NOT NULL | Ticker (denormalizado) |
| `metrica` | VARCHAR(100) | NOT NULL | Campo XBRL (Revenues, NetIncome, etc.) |
| `unidad` | VARCHAR(20) | NOT NULL | USD, USD/shares, shares, pure |
| `periodo_start` | DATE | NULL | Inicio período (NULL para balance sheets) |
| `periodo_end` | DATE | NOT NULL | Fin período |
| `val` | FLOAT | NOT NULL | Valor numérico |
| `fy` | INTEGER | NULL | Año fiscal |
| `fp` | VARCHAR(5) | NULL | Q1, Q2, Q3, FY |
| `form` | VARCHAR(10) | NOT NULL | 10-K, 10-Q, 20-F, etc. |
| `filed` | DATE | NULL | Fecha presentación (para dedup) |
| `frame` | VARCHAR(20) | NULL | Frame SEC (CY2024Q1I) |
| `fetched_at` | TIMESTAMP | NOT NULL | Timestamp descarga |

**Índices:**
```sql
CREATE INDEX idx_financials_raw_cik_metrica_periodo 
    ON financials_raw (cik, metrica, periodo_end);
```

**Constraint UNIQUE:**
```sql
UNIQUE (cik, metrica, periodo_end, filed, form)
```

**Notas:**
- INSERT solo (nunca UPSERT): `ON CONFLICT DO NOTHING`
- Permite enmiendas (10-K/A): mismo período pero diferente `filed`
- Dedup automático si se ejecuta 2× el mismo Job 1B
- ~100k-200k filas (100 empresas × 30 métricas × 30-60 períodos c/u)

---

## 4. `ratios` — Ratios Calculados (Única tabla que lee Frontend)

**Propósito:** 1 fila = 1 ticker BYMA, con 60 columnas de ratios finales.

| Columna | Tipo | Constraint | Descripción |
|---------|------|-----------|-------------|
| `ticker` | VARCHAR(10) | PK, FK cedears | Ticker BYMA |
| `precio_usd` | FLOAT | NULL | De precios_raw |
| `year_high` | FLOAT | NULL | De precios_raw |
| `year_low` | FLOAT | NULL | De precios_raw |
| `dif_max` | FLOAT | NULL | (precio/year_high) - 1 |
| `dif_min` | FLOAT | NULL | (precio/year_low) - 1 |
| `per` | FLOAT | NULL | Precio / EPS_TTM |
| `eps_anual` | FLOAT | NULL | NetIncome_TTM / Shares |
| `crec_eps_5y` | FLOAT | NULL | CAGR EPS |
| `margen_neto` | FLOAT | NULL | NetIncome_TTM / Revenue_TTM |
| `roe_5y` | FLOAT | NULL | CAGR ROE |
| `fcf_on_ce` | FLOAT | NULL | FCF_TTM / Capital_Empleado |
| `payout` | FLOAT | NULL | Dividendos / NetIncome_TTM |
| `deuda_ebitda` | FLOAT | NULL | Deuda / EBITDA |
| `calculated_at` | TIMESTAMP | NULL | Cuándo corrió Job 2 |
| `prices_updated_at` | TIMESTAMP | NULL | Timestamp de precios_raw usado |
| `financials_updated_at` | TIMESTAMP | NULL | Timestamp más reciente de financials_raw |

**Índices:**
```sql
CREATE INDEX idx_ratios_calculated ON ratios (calculated_at DESC);
```

**Constraint:**
```sql
INSERT INTO ratios (...) VALUES (...)
ON CONFLICT (ticker) DO UPDATE SET ...;
```

**Notas:**
- UPSERT: Job 2 recalcula y reescribe
- Frontend usa: `SELECT * FROM ratios ORDER BY per, deuda_ebitda, etc.`
- Timestamps permiten al frontend mostrar "Precios: hace 1 día"
- Las 60 columnas incluyen ~30 debug (_revenue_ttm, _ebitda_ttm, etc.)

---

## 5. `jobs` + `job_errores` — Auditoría

### Tabla `jobs`

| Columna | Tipo | Constraint | Descripción |
|---------|------|-----------|-------------|
| `id` | UUID | PK | gen_random_uuid() |
| `tipo` | VARCHAR(30) | NOT NULL, CHECK | precios / financials / calculo |
| `status` | VARCHAR(15) | NOT NULL, CHECK | pending / running / done / error |
| `processed` | INTEGER | NOT NULL DEFAULT 0 | Cuántos hizo |
| `total` | INTEGER | NOT NULL DEFAULT 0 | De cuántos |
| `errores_count` | INTEGER | NOT NULL DEFAULT 0 | Cuántos erraron |
| `duracion_seg` | FLOAT | NULL | Segundos tomó |
| `started_at` | TIMESTAMP | NOT NULL DEFAULT NOW() | Cuándo arrancó |
| `finished_at` | TIMESTAMP | NULL | Cuándo terminó |

### Tabla `job_errores`

| Columna | Tipo | Constraint | Descripción |
|---------|------|-----------|-------------|
| `id` | UUID | PK | gen_random_uuid() |
| `job_id` | UUID | FK jobs, NOT NULL | Qué job errró |
| `ticker` | VARCHAR(10) | NOT NULL | Ticker que falló |
| `mensaje` | TEXT | NOT NULL | Mensaje de error |
| `intento` | INTEGER | NOT NULL DEFAULT 1 | Intento 1/2/3 |
| `ts` | TIMESTAMP | NOT NULL DEFAULT NOW() | Cuándo pasó |

**Índices:**
```sql
CREATE INDEX idx_job_errores_job_id ON job_errores (job_id);
```

**Notas:**
- Job 1A crea: `tipo='precios'`
- Job 1B crea: `tipo='financials'`
- Job 2 crea: `tipo='calculo'`
- Frontend muestra: jobs recientes, errores pendientes, progreso

---

## Flujo de Datos Resumido

```
Job 1A (Paso 4)
  ↓
cedears + precios.json → UPSERT precios_raw

Job 1B (Paso 3)
  ↓
cedears + financials_sec/ → INSERT financials_raw (ON CONFLICT DO NOTHING)

Job 2 (Paso 5)
  ↓
Leer: precios_raw + financials_raw + cedears
Calcular: TTM, ratios, CAGR
Escribir: UPSERT ratios

Frontend
  ↓
SELECT * FROM ratios
      + jobs/job_errores para UI de progreso
```

---

**Diagrama SQL:**

Ver `001_initial_schema.sql` en la carpeta `schema/` para el código DDL completo.
