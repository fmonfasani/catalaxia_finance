# 📚 _research — Referencia de Scripts y Arquitectura

Esta carpeta contiene **documentación completa** del pipeline de datos que genera el dashboard de ratios financieros. Aquí encontrará:

- **Scripts originales** (scripts/) — Los 3 procesos base que descargan y calculan datos
- **Schema SQL** (schema/) — Estructura de 5 tablas PostgreSQL
- **Documentación** (docs/) — Qué hace cada script, entrada/salida, ejemplos
- **Ejemplos** (ejemplos/) — Datos de muestra para entender el flujo

## 🎯 Objetivo Final

Generar un **dashboard** que muestre una tabla como `seguimiento.csv` pero de forma visual e interactiva. Esa tabla contiene:
- Precio actual, máximo/mínimo de 52 semanas
- Ratios: PER, EPS, Margen Neto, ROE, FCF/CE, Payout, Deuda/EBITDA
- Crecimiento EPS 5 años, Crecimiento ROE 5 años
- Columnas de debug (_revenue_ttm, _netincome_ttm, _ebitda_ttm, etc.)

## 🔄 Flujo de Datos (Paso a Paso)

```
cedears_con_cik.json  (mapeo de tickers: BYMA ↔ SEC ↔ CIK)
    ↓
    ├─────→  PASO 3: 03_descargar_financials_sec.py
    │        Input:  cedears_con_cik.json (295 CIKs únicos)
    │        Output: financials_sec/*.json + financials_index.json
    │        • Descarga desde SEC EDGAR XBRL
    │        • 1 JSON por empresa con historial financiero completo
    │        • Rate limit: 0.15s entre requests (10 req/s SEC)
    │
    ├─────→  PASO 4: 04_descargar_precios.py
    │        Input:  cedears_con_cik.json (295 tickers)
    │        Output: precios.json
    │        • Descarga desde yfinance
    │        • Precio actual, 52w hi/lo, market cap, shares
    │        • Rate limit: 0.2s entre requests
    │
    └─────→  PASO 5: 05_calcular_ratios.py
             Input:  financials_sec/ + precios.json + cedears_con_cik.json
             Output: seguimiento.csv + seguimiento.json
             • Calcula TTM, CAGR, ratios
             • 1 fila por BYMA ticker
             • ~60 columnas (ratios + debug)
```

## 📊 Tablas de Base de Datos (PostgreSQL)

Después de estos 3 pasos, los datos van a 5 tablas en Postgres:

| Tabla | Input | Descripción |
|-------|-------|-------------|
| `cedears` | Paso 0 | Maestro: ticker, nombre, CIK, exchange, país, activo |
| `precios_raw` | Paso 4 | Crudos de yfinance: precio, 52w hi/lo, market cap, shares |
| `financials_raw` | Paso 3 | Crudos de SEC EDGAR: 1 fila por datapoint (métrica+período) |
| `ratios` | Paso 5 | Calculados: PER, EPS, margen, ROE, FCF/CE, etc. |
| `jobs` / `job_errores` | Orchestración | Auditoría de cada run (OK/errores/progreso) |

Ver `docs/SCHEMA_EXPLICADO.md` para detalles de cada tabla.

## 📄 Estructura de esta Carpeta

```
_research/
├── README.md                    ← Estás aquí
├── FLUJO_GENERAL.md             ← Diagrama y visión general
│
├── scripts/
│   ├── 03_descargar_financials_sec.py   (SEC EDGAR XBRL)
│   ├── 04_descargar_precios.py           (yfinance)
│   └── 05_calcular_ratios.py             (Cálculos)
│
├── schema/
│   └── 001_initial_schema.sql            (5 tablas Postgres)
│
├── docs/
│   ├── SCRIPT_03_FINANCIALS_SEC.md       (Qué hace, entrada, salida)
│   ├── SCRIPT_04_PRECIOS.md              (Qué hace, entrada, salida)
│   ├── SCRIPT_05_RATIOS.md               (Qué hace, entrada, salida)
│   ├── SCHEMA_EXPLICADO.md               (Estructura de tablas)
│   └── FORMULAS_RATIOS.md                (Cómo se calcula cada ratio)
│
└── ejemplos/
    ├── EJEMPLO_03_OUTPUT.md              (Salida JSON de script 3)
    ├── EJEMPLO_04_OUTPUT.md              (Salida JSON de script 4)
    ├── EJEMPLO_05_OUTPUT.md              (Salida CSV de script 5)
    └── MAPEO_COLUMNAS.md                 (Qué columna viene de dónde)
```

## 🚀 Para Colaboradores

**Si necesitas entender el pipeline:**
1. Lee este README
2. Lee `FLUJO_GENERAL.md` para ver el diagrama
3. Lee `docs/SCRIPT_XX.md` según el script que te interesa

**Si necesitas saber cómo se calcula un ratio:**
1. Mira `docs/FORMULAS_RATIOS.md`
2. Busca la función correspondiente en `scripts/05_calcular_ratios.py`

**Si necesitas ver un ejemplo de salida:**
1. Mira `ejemplos/EJEMPLO_XX_OUTPUT.md`
2. Ejecuta el script localmente si quieres generar tus propios datos

## 🛠️ Cómo Usar

Los scripts pueden correr **standalone** (modo investigación) o pueden ser adaptados a **módulos Python** que vivan en `backend/fetchers/` y `backend/calculators/` (modo producción, integrado con FastAPI/APScheduler).

Hoy, en este repo, existen como módulos adaptados en:
- `backend/fetchers/precios.py` — función `descargar_ticker()`
- `backend/fetchers/sec_edgar.py` — funciones `descargar_empresa()`, `extraer_metricas()`
- `backend/calculators/ratios.py` — función `calcular_ratios_ticker()` (por implementar)

Los scripts originales en `_research/scripts/` son la **referencia completa** y funcionan como scripts standalone.

## 📝 Notas Importantes

### TTM (Trailing Twelve Months)
- Para **flujos** (Revenue, NetIncome, CFO, CapEx, Dividendos, D&A): suma de últimos 4 trimestres o Annual + YTD actual − YTD año anterior.
- Para **stocks** (Equity, Debt, Cash, Shares): último período disponible.
- Ver `scripts/05_calcular_ratios.py` función `ttm_flujo()` para la lógica exacta.

### CAGR (Compound Annual Growth Rate)
- (valor_fin / valor_ini)^(1/years) − 1
- Requiere serie anual (10-K) con >5 años de historia.
- Si no hay datos suficientes, el ratio es `None` (nunca se estima).

### Deuda/EBITDA (Dos Variantes)
- **deuda_lp_sobre_ebitda**: LongTermDebt / EBITDA
- **deuda_total_sobre_ebitda**: (LT + ST + Current) / EBITDA

### EBITDA (No existe en XBRL)
- Se calcula como: OperatingIncome + D&A
- Si falta algún componente, el valor es `None`.

---

**Última actualización:** Junio 2026  
**Equipo:** Valentino (Backend A), Mateo (Backend B), Joaquin (Frontend A), Aldana (Frontend B), Federico (Arquitecto)
