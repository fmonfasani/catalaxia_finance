# CatalaXia — Módulo de Análisis Financiero CEDEARs

Módulo base limpio con las **funciones puras de descarga y cálculo** para el análisis financiero de CEDEARs (Constructores).

Este repositorio contiene SOLO:
- **Fetchers** — descarga de Yahoo Finance y SEC EDGAR XBRL (sin persistencia, sin orquestación)
- **Calculators** — cálculo de ratios financieros (funciones puras, sin acceso a BD)
- **Schema SQL** — estructura de 5 tablas PostgreSQL (cedears, precios_raw, financials_raw, ratios, jobs)
- **Documentación** — arquitectura, diseño de jobs, decisiones técnicas

## Estructura

```
catalaxia-cedears-prod/
├── backend/
│   ├── fetchers/           (descarga pura — yfinance, SEC EDGAR)
│   │   ├── precios.py      (descargar_ticker) — Job 1A base
│   │   └── sec_edgar.py    (descargar_empresa, extraer_metricas) — Job 1B base
│   ├── calculators/        (cálculos puros — sin BD, sin internet)
│   │   └── ratios.py       (calcular_ratios_ticker) — Job 2 base
│   ├── requirements.txt    (yfinance, requests, sqlalchemy)
│   └── pyproject.toml      (Ruff, Mypy, Pytest config)
├── migrations/
│   └── 001_initial_schema.sql  (5 tablas, índices, constraints)
├── data/                   (vacía — para CSV/JSON de research si se usan)
├── docs/
│   ├── 01-arquitectura.md  (3 capas: descarga → raw → cálculo → ratios)
│   ├── 02-jobs.md          (Job 1A/1B/2 contratos completos)
│   ├── 03-base-de-datos.md (schema detallado, 5 tablas)
│   └── 06-decisiones-tecnicas.md (TTM, EBITDA, fallbacks)
└── README.md               (este archivo)
```

## Origen de los archivos

Todos los scripts vienen del repo [catalaxia-cedears](D:\Software Development\Documentos de portfolio\Catalaxia\catalaxia-cedears) (repo completo con FastAPI, frontend, etc.):

- `fetchers/precios.py` ← adaptado de `04_descargar_precios.py` (script de research)
- `fetchers/sec_edgar.py` ← textual de `03_descargar_financials_sec.py`
- `calculators/ratios.py` ← esqueleto base de `05_calcular_ratios.py`
- `migrations/001_initial_schema.sql` ← schema oficial PostgreSQL
- `docs/*.md` ← documentación técnica del equipo (Valentino, Mateo, Aldana, Joaquin)

## implementar 

Este módulo es la **base limpia para las próximas fases**:

1. **Wrapping en jobs** (Jobs 1A, 1B, 2 con FastAPI + APScheduler)
   - Orquestación, retry, progreso en BD
   - Logs a `jobs` y `job_errores`

2. **Conexión a PostgreSQL**
   - Pool async (asyncpg)
   - Migraciones automáticas

3. **Endpoints FastAPI**
   - `POST /api/jobs/precios` — trigger Job 1A
   - `POST /api/jobs/financials` — trigger Job 1B
   - `POST /api/jobs/calculo` — trigger Job 2
   - `GET /api/jobs/{job_id}/status` — progreso en tiempo real

4. **Completar el calculador de ratios**
   - Implementar `calcular_ttm_flujo()` — TTM con estrategias A/B/C
   - Implementar `calcular_cagr()` — crecimiento 5 años
   - Implementar `calcular_ratios_ticker()` — punto de entrada Job 2

5. **Tests unitarios**
   - Para fetchers (mock requests)
   - Para calculators (fixtures con datos SEC/Yahoo reales)

## Cómo usar este módulo

### Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

### Importar funciones base

```python
from backend.fetchers.precios import descargar_ticker
from backend.fetchers.sec_edgar import descargar_empresa, extraer_metricas
from backend.calculators.ratios import calcular_ratios_ticker

# Descarga pura (sin BD)
precios = descargar_ticker("AAPL")
empresa = descargar_empresa(cik="0000789019")  # Apple
metricas = extraer_metricas(empresa_json)

# Cálculos puros (requiere datos ya descargados)
ratios = calcular_ratios_ticker(precios_row, financials_rows)
```

### Crear la BD

```bash
psql -U postgres -h localhost < migrations/001_initial_schema.sql
```

## Documentación técnica

Leer en orden:

1. **[01-arquitectura.md](docs/01-arquitectura.md)** — visión general de 3 capas
2. **[02-jobs.md](docs/02-jobs.md)** — contratos completos Job 1A/1B/2
3. **[03-base-de-datos.md](docs/03-base-de-datos.md)** — schema 5 tablas
4. **[06-decisiones-tecnicas.md](docs/06-decisiones-tecnicas.md)** — TTM, EBITDA, fallbacks

## Stack

- **Python 3.11** — tipo hints, f-strings
- **yfinance 0.2.50** — Yahoo Finance
- **requests 2.32.3** — SEC EDGAR HTTP
- **SQLAlchemy 2.0.36** — types y async
- **Pydantic 2.9.2** — validación (para Jobs futuros)

## Próximos pasos

1. Integrar `descargar_ticker()` y `descargar_empresa()` en Jobs con FastAPI
2. Implementar `calcular_ratios_ticker()` completamente (TTM, CAGR)
3. Conectar a PostgreSQL con asyncpg
4. Tests con datos reales de SEC/Yahoo
5. Deploy en Coolify como servicio de cron

## Licencia

Privado — Equipo webshooks (Mateo, Aldana, Joaquin)

---

**Última actualización:** Junio 2026  
**Mantenedor:** Federico Monfasani (@fmonfasani)
