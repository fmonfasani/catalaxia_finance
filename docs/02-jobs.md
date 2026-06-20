# 02 — Jobs: descarga y cálculo

> Fuente original: `Jobs_y_Base_de_Datos.docx` secciones 3, 4, 5, 6

Los tres jobs son **completamente independientes**. Ninguno espera a otro
para arrancar. El orden lógico óptimo es secuencial solo por eficiencia, no
por dependencia técnica obligatoria.

## Job 1A — Descarga de precios (Backend: Valentino)

**Descarga Yahoo Finance → escribe en `precios_raw`**

Base: `04_descargar_precios.py` (convertido en módulo importable, no script
standalone — FastAPI y APScheduler llaman a la misma función).

| Parámetro | Valor |
|---|---|
| Frecuencia | Cron diario — 22:00 UTC (fuera de horario de mercado USA) |
| También corre | Trigger manual desde `POST /api/jobs/ratios/precios` |
| Duración estimada | 100 tickers × 0.2s delay ≈ 25 segundos |
| Escritura | UPSERT — `INSERT ... ON CONFLICT (ticker_sec) DO UPDATE` |

### Pasos

1. **Crear registro en `jobs`** — `tipo='precios'`, `status='pending'`, `total=100`. Guardar el `job_id`.
2. **Leer tickers de la BD** — `SELECT ticker_sec, cik FROM cedears WHERE activo = true`. Nunca leer desde archivo JSON; la BD es la fuente de verdad.
3. **Loop de descarga** — `yfinance.Ticker(ticker).fast_info` por cada ticker.
   - Validar que `last_price`, `year_high`, `year_low` no sean `None` **individualmente**.
   - Si alguno es `None` → registrar en `job_errores`, continuar con el siguiente.
   - Delay de 0.2s entre requests.
   - Retry con backoff exponencial: 1s → 3s → 9s.
   - Actualizar `jobs.processed` cada 10 tickers.
4. **UPSERT en `precios_raw`** — incluir `fetched_at` con timestamp actual. Si falla, registrar en `job_errores`.
5. **Cerrar el job** — `status='done'` aunque haya habido errores parciales. Solo `status='error'` si el job no pudo arrancar.

### Rate limiting de Yahoo Finance (3 capas)

Yahoo Finance no tiene rate limit documentado, pero corta conexiones si se
hacen muchas requests seguidas:

1. Delay fijo de 0.2s entre cada ticker.
2. Retry con backoff exponencial (1s, 3s, 9s).
3. Si después de 3 intentos sigue fallando: registrar el error y **no frenar
   el job completo** — pasar al siguiente ticker.

---

## Job 1B — Descarga de financials SEC EDGAR (Backend: Mateo)

**Descarga SEC EDGAR XBRL → escribe en `financials_raw`**

Base: `03_descargar_financials_sec.py`. La función `extraer_metricas()` **no
se reescribe** — ya implementa correctamente el dedup por `(start, end)`
conservando el `filed` más reciente.

| Parámetro | Valor |
|---|---|
| Fuente | `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` |
| Auth | Ninguna — solo header `User-Agent` obligatorio |
| Frecuencia | Cron semanal — lunes 06:05 UTC (5 min después de Job 1A) |
| Duración estimada | 100 empresas × 0.15s ≈ 20 segundos de descarga |
| Escritura | `INSERT ... ON CONFLICT DO NOTHING` (no UPSERT — ver razón abajo) |

### Por qué INSERT y no UPSERT

Los datos de SEC EDGAR son **inmutables por diseño**. Una vez que una empresa
presenta un 10-K para 2023, ese valor no cambia. Lo que puede cambiar es que
la empresa presente una enmienda (`10-K/A`) con un restatement, que aparece
como un **nuevo registro** con el mismo período pero diferente `filed`.

Índice único:

```sql
UNIQUE (cik, metrica, periodo_end, filed, form)
```

Si la empresa no presentó nada nuevo esa semana, el INSERT falla
silenciosamente (sin duplicados). Si presentó una enmienda, el nuevo registro
con `filed` distinto se inserta correctamente.

### Pasos

1. **Crear registro en `jobs`** — `tipo='financials'`.
2. **Leer CIKs de la BD** — `SELECT DISTINCT cik, ticker_sec FROM cedears WHERE activo = true`. Deduplicar por CIK (varios `byma_ticker` pueden compartir CIK).
3. **Loop de descarga por empresa**:
   - Delay 0.15s entre requests (rate limit SEC: 10 req/s).
   - HTTP 429 → esperar 30s y reintentar.
   - HTTP 404 → la empresa no tiene datos en SEC (posible empresa extranjera IFRS).
   - Actualizar `jobs.processed` cada 10 empresas.
4. **Extraer métricas del JSON** — llamar a `extraer_metricas()` del script original, sin reescribirla.
5. **INSERT en `financials_raw`** — una fila por datapoint, nunca agrupar métricas en una sola fila.
6. **Cerrar el job**.

### Empresas extranjeras (caso INFY)

Algunas empresas (ej. Infosys) reportan con `20-F` pero usan esquema **IFRS**
en vez de `us-gaap`:

1. Detectar si `facts['facts']['us-gaap']` está vacío o ausente.
2. Si es así, intentar `facts['facts']['ifrs-full']` con los mismos nombres de métricas.
3. Registrar en el campo `form` de `financials_raw` que es `20-F` para que Job 2 lo sepa.
4. Si no hay datos en ninguno de los dos esquemas → `job_errores` con mensaje `'sin_datos_xbrl'`.

---

## Job 2 — Cálculo de ratios (Backend: Mateo, con apoyo de Valentino)

**Lee `precios_raw` + `financials_raw` → calcula → escribe en `ratios`**

Este es el script nuevo: `05_calcular_ratios.py` ya existe como base de
investigación — el trabajo de producción es envolverlo en un job con
progreso reportable.

| Parámetro | Valor |
|---|---|
| Descarga | Cero requests a internet. Solo lee de la BD. |
| Frecuencia | Después de Job 1B — lunes 07:00 UTC |
| También corre | Manual, en cualquier momento, sin descargar nada |
| Duración estimada | 100 tickers × cálculo en memoria < 60 segundos |
| Escritura | UPSERT — una fila por ticker |

### Lógica de TTM (el cálculo más importante)

Las empresas USA reportan en el `10-Q` valores **YTD acumulados** desde el
inicio del año fiscal, no valores del trimestre solo. El Q3 de income
statement = Q1+Q2+Q3, no solo Q3.

**Distinguir un trimestre de un YTD por duración del período:**

| Duración (días) | Tipo de período |
|---|---|
| ~90 | Trimestre individual |
| ~180 | Semianual (Q1+Q2) |
| ~270 | Nueve meses (Q1+Q2+Q3) |
| ~365 | Año completo (10-K) |

**Fórmula TTM:**

```
TTM = último 10-K + trimestres posteriores al 10-K − trimestres equivalentes del año anterior
```

### Fallback entre métricas equivalentes

SEC EDGAR usa nombres distintos para el mismo concepto según la empresa. El
job intenta cada candidato en orden hasta encontrar uno con datos:

| Concepto | Candidatos en orden |
|---|---|
| Revenue | `Revenues` → `RevenueFromContractWithCustomer...` → `SalesRevenueNet` |
| D&A | `DepreciationDepletionAndAmortization` → `DepreciationAndAmortization` → `Depreciation` |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` → `PaymentsToAcquireProductiveAssets` |
| Deuda total | `DebtLongtermAndShorttermCombinedAmount` → `LongTermDebt` + `ShortTermBorrowings` |
| Dividendos | `PaymentsOfDividendsCommonStock` → `PaymentsOfDividends` |

### Pasos

1. Crear registro en `jobs` con `tipo='calculo'`.
2. Leer tickers activos.
3. Para cada ticker: leer `precios_raw`. Si no hay precio → `job_errores('sin_precios')`, continuar.
4. Para cada ticker: leer `financials_raw` ordenado por `periodo_end`. Agrupar por métrica en memoria.
5. Calcular cada ratio:
   - TTM para métricas de flujo (income statement, cash flow).
   - Último valor disponible para métricas de stock (balance sheet).
   - Fallback entre candidatos.
   - Si algún componente es `None` → el ratio queda `NULL` (**nunca estimar**).
   - CAGR 5 años: `(valor_fin / valor_ini)^(1/5) - 1`.
6. UPSERT en `ratios` con `calculated_at`, `prices_updated_at`, `financials_updated_at`.
7. Cerrar el job.

---

## Independencia entre jobs — schedule semanal

| Momento | Job | Duración | Por qué |
|---|---|---|---|
| Lunes 06:00 UTC | Job 1A — Precios | ~25s | Mercados USA cerrados, precios del viernes |
| Lunes 06:05 UTC | Job 1B — Financials | ~20s | Inmediatamente después de precios |
| Lunes 07:00 UTC | Job 2 — Cálculo | ~60s | Espera 55 min por si Job 1B tarda más |
| Martes a domingo | Job 1A solo | ~25s | Precios se actualizan a diario |
| Cualquier momento | Job 2 solo | ~60s | Si cambia una fórmula o se agrega un ratio |

## Casos de uso reales de la independencia

**Cambio de fórmula** — se corrige la fórmula de FCFonCE en el código de Job
2, se corre manualmente, en 60 segundos la tabla `ratios` tiene los valores
corregidos. Cero requests a internet.

**Ratio nuevo (ej. EV/EBITDA)** — se agrega la columna, se agrega el cálculo
en Job 2, se verifica que los campos necesarios ya estén en `precios_raw` /
`financials_raw`, se corre Job 2. La columna se llena para los 100 tickers sin
descargar nada.

**Yahoo Finance falla parcialmente** — Job 1A falla para 5 tickers, quedan en
`job_errores`, los otros 95 se actualizan. Job 2 usa el precio anterior de los
5 fallidos. El frontend muestra esos 5 con badge "Precio: hace 2 días".

**Análisis histórico** — como `financials_raw` guarda todo el historial, se
puede calcular el PER de cualquier ticker en cualquier fecha pasada con un Job
3 futuro, sin descargar nada nuevo.
