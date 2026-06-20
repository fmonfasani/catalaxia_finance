# 03 — Base de datos

> PostgreSQL 16. Cinco tablas, cada una con responsabilidad única.
> El SQL ejecutable vive en [`../migrations/001_initial_schema.sql`](../migrations/001_initial_schema.sql).

## 3.1 `cedears` — Maestro de tickers

Tabla raíz. Todos los jobs y consultas parten de acá.

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `ticker` | `VARCHAR(10)` | PK, NOT NULL | Ticker BYMA. Ej: `BIIB`, `AMAT` |
| `ticker_sec` | `VARCHAR(10)` | NOT NULL | Ticker en Yahoo Finance / SEC |
| `cik` | `VARCHAR(10)` | NOT NULL | CIK de la empresa en SEC EDGAR |
| `nombre` | `VARCHAR(150)` | NOT NULL | Nombre completo de la empresa |
| `exchange` | `VARCHAR(10)` | NOT NULL | NASDAQ / NYSE / AMEX |
| `pais` | `VARCHAR(50)` | NULL | País de origen |
| `activo` | `BOOLEAN` | DEFAULT true | False si el CEDEAR fue suspendido |
| `created_at` | `TIMESTAMP` | DEFAULT NOW() | Fecha de alta |

## 3.2 `precios_raw` — Datos crudos de Yahoo Finance

Escrita **exclusivamente** por Job 1A. Guarda exactamente lo que devuelve
`yfinance` sin modificar ningún valor.

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `ticker_sec` | `VARCHAR(10)` | PK, FK `cedears` | Ticker de Yahoo Finance |
| `last_price` | `FLOAT` | NULL | Precio actual USD |
| `year_high` | `FLOAT` | NULL | Máximo últimos 365 días |
| `year_low` | `FLOAT` | NULL | Mínimo últimos 365 días |
| `market_cap` | `FLOAT` | NULL | Capitalización de mercado |
| `shares` | `FLOAT` | NULL | Acciones en circulación |
| `currency` | `VARCHAR(5)` | NULL | Moneda del precio |
| `exchange_yf` | `VARCHAR(20)` | NULL | Exchange reportado por Yahoo |
| `previous_close` | `FLOAT` | NULL | Cierre del día anterior |
| `fetched_at` | `TIMESTAMP` | NOT NULL | Timestamp exacto de la descarga |

## 3.3 `financials_raw` — Datos crudos de SEC EDGAR

Escrita **exclusivamente** por Job 1B. Una fila por **datapoint** de cada
métrica de cada empresa. La tabla más grande del sistema — para 100 empresas
con 10 años de historia, decenas de miles de filas.

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | `BIGSERIAL` | PK | ID autoincremental |
| `cik` | `VARCHAR(10)` | FK `cedears`, NOT NULL | CIK de la empresa |
| `ticker_sec` | `VARCHAR(10)` | NOT NULL | Ticker de la empresa |
| `metrica` | `VARCHAR(100)` | NOT NULL | Campo XBRL. Ej: `NetIncomeLoss` |
| `unidad` | `VARCHAR(20)` | NOT NULL | `USD` / `USD/shares` / `shares` / `pure` |
| `periodo_start` | `DATE` | NULL | Inicio del período (NULL en balance sheets) |
| `periodo_end` | `DATE` | NOT NULL | Fin del período reportado |
| `val` | `FLOAT` | NOT NULL | Valor numérico |
| `fy` | `INTEGER` | NULL | Año fiscal |
| `fp` | `VARCHAR(5)` | NULL | `Q1` / `Q2` / `Q3` / `FY` |
| `form` | `VARCHAR(10)` | NOT NULL | `10-K` / `10-Q` / `20-F` / etc. |
| `filed` | `DATE` | NULL | Fecha de presentación del reporte |
| `frame` | `VARCHAR(20)` | NULL | Marco fiscal SEC. Ej: `CY2024Q3I` |
| `fetched_at` | `TIMESTAMP` | NOT NULL | Fecha de descarga de Job 1B |

**Índice único** (evita duplicados entre runs semanales, permite enmiendas):

```sql
UNIQUE (cik, metrica, periodo_end, filed, form)
```

**Índice de performance** para las consultas de Job 2:

```sql
(cik, metrica, periodo_end)
```

## 3.4 `ratios` — Ratios calculados para el frontend

Escrita **exclusivamente** por Job 2. Solo números finales. **La única
tabla que lee el frontend.**

| Columna | Tipo | Fuente del cálculo | Descripción |
|---|---|---|---|
| `ticker` | `VARCHAR(10)` | PK, FK `cedears` | Ticker BYMA |
| `precio_usd` | `FLOAT` | `precios_raw.last_price` | Precio actual |
| `year_high` | `FLOAT` | `precios_raw.year_high` | Máximo 52 semanas |
| `year_low` | `FLOAT` | `precios_raw.year_low` | Mínimo 52 semanas |
| `dif_max` | `FLOAT` | `(precio/year_high)-1` | Dif. % vs máximo |
| `dif_min` | `FLOAT` | `(precio/year_low)-1` | Dif. % vs mínimo |
| `per` | `FLOAT` | `precio / eps_ttm` | PER TTM |
| `eps_anual` | `FLOAT` | `NetIncomeLoss_TTM / shares` | EPS TTM diluted |
| `crec_eps_5y` | `FLOAT` | CAGR EPS 5 años | Crecimiento anualizado |
| `margen_neto` | `FLOAT` | `NetIncome / Revenue` TTM | Margen neto |
| `roe_5y` | `FLOAT` | CAGR ROE 5 años | Retorno sobre equity |
| `fcf_on_ce` | `FLOAT` | `(CFO-CapEx)/(Activo-PasivoCte)` | FCF sobre Capital Empleado |
| `payout` | `FLOAT` | `Dividendos/NetIncome` TTM | Payout Ratio |
| `deuda_ebitda` | `FLOAT` | `TotalDebt / EBITDA` TTM | Apalancamiento |
| `calculated_at` | `TIMESTAMP` | Job 2 | Último cálculo |
| `prices_updated_at` | `TIMESTAMP` | Job 1A | Fecha del precio usado |
| `financials_updated_at` | `TIMESTAMP` | Job 1B | Fecha de los financials usados |

Los timestamps `prices_updated_at` / `financials_updated_at` permiten al
frontend mostrar los badges de estado sin consultas adicionales.

## 3.5 `jobs` + `job_errores` — Control y auditoría

Escritas por todos los jobs. Permiten al frontend mostrar progreso en tiempo
real y al equipo auditar cada ejecución.

**`jobs`**

| Columna | Tipo | Valores posibles |
|---|---|---|
| `id` | `UUID` | PK generado |
| `tipo` | `VARCHAR(30)` | `precios` / `financials` / `calculo` |
| `status` | `VARCHAR(15)` | `pending` / `running` / `done` / `error` |
| `processed` | `INTEGER` | 0 a `total` |
| `total` | `INTEGER` | ej. 100 |
| `errores_count` | `INTEGER` | ≥ 0 |
| `duracion_seg` | `FLOAT` | NULL hasta finalizar |
| `started_at` | `TIMESTAMP` | NOT NULL |
| `finished_at` | `TIMESTAMP` | NULL hasta finalizar |

**`job_errores`**

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `UUID` | PK |
| `job_id` | `UUID` | FK `jobs` |
| `ticker` | `VARCHAR(10)` | Ticker que falló |
| `mensaje` | `TEXT` | Mensaje de error completo |
| `intento` | `INTEGER` | 1 / 2 / 3 |
| `ts` | `TIMESTAMP` | NOT NULL |

## El schema es el contrato

Antes de escribir una línea de código, **los 4 colaboradores acuerdan este
schema**. Una vez fijo:

- Backend A desarrolla Job 1A de forma completamente independiente.
- Backend B desarrolla Job 1B y Job 2 de forma independiente.
- Frontend A y B desarrollan contra datos mockeados hasta que los jobs estén listos.

El archivo `../migrations/001_initial_schema.sql` es la fuente de verdad
ejecutable. Si alguien necesita crear la base desde cero, ese archivo lo hace
todo.
