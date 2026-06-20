# 🚀 COMIENZA AQUÍ

Bienvenido a la carpeta `_research`. Aquí está **toda la documentación y los scripts originales** que generan el dashboard de ratios financieros.

## 📖 Para Empezar (5 minutos)

**Si es tu primera vez aquí:**

1. Lee [`README.md`](README.md) — visión general de qué hay en esta carpeta
2. Lee [`FLUJO_GENERAL.md`](FLUJO_GENERAL.md) — diagrama de los 3 pasos y cómo se conectan

**Resultado:** Entenderás que hay 3 scripts independientes que descargan/calculan datos, y que generan un archivo `seguimiento.csv` como output final.

## 🎯 Para Entender un Script Específico

**Si necesitas entender QUÉ HACE cada paso:**

- **Paso 3 (SEC EDGAR):** Lee [`docs/SCRIPT_03_FINANCIALS_SEC.md`](docs/SCRIPT_03_FINANCIALS_SEC.md)
  - Qué descarga, de dónde, en qué formato, columnas, ejemplos

- **Paso 4 (yfinance):** Lee [`docs/SCRIPT_04_PRECIOS.md`](docs/SCRIPT_04_PRECIOS.md)
  - Qué descarga, de dónde, en qué formato, ejemplos

- **Paso 5 (Cálculos):** Lee [`docs/SCRIPT_05_RATIOS.md`](docs/SCRIPT_05_RATIOS.md)
  - Qué calcula, cómo, ejemplos de salida

## 💻 Para Ver el Código

Los scripts originales están aquí:

```
scripts/
├── 03_descargar_financials_sec.py    (SEC EDGAR)
├── 04_descargar_precios.py            (yfinance)
└── 05_calcular_ratios.py              (Cálculos)
```

**Nota:** El código está adaptado en `backend/fetchers/` y `backend/calculators/` como módulos Python. Los scripts aquí en `_research/` son la **versión completa standalone** que funcionan como scripts por línea de comando.

## 📊 Para Entender el Schema de Base de Datos

Lee [`docs/SCHEMA_EXPLICADO.md`](docs/SCHEMA_EXPLICADO.md)

- Qué tabla es cuál
- Qué escribir en cada una
- Relaciones entre tablas
- Índices y constraints

## 📐 Para Entender las Fórmulas de los Ratios

Lee [`docs/FORMULAS_RATIOS.md`](docs/FORMULAS_RATIOS.md)

- Cómo se calcula PER, EPS, Margen Neto, ROE, FCF/CE, etc.
- Qué es TTM (Trailing Twelve Months)
- Qué es CAGR
- Por qué algunas métricas son `None` (nunca se estiman)

## 🔍 Para Ver Ejemplos de Entrada/Salida

Mira los archivos en `ejemplos/`:

- `EJEMPLO_03_OUTPUT.md` — Qué devuelve el Paso 3 (JSON)
- `EJEMPLO_04_OUTPUT.md` — Qué devuelve el Paso 4 (JSON)
- `EJEMPLO_05_OUTPUT.md` — Qué devuelve el Paso 5 (CSV)
- `MAPEO_COLUMNAS.md` — De dónde viene cada columna del CSV final

## 🛠️ Para Developers (Valentino, Mateo, Joaquin, Aldana)

**Si necesitas MODIFICAR el código:**

1. **Backend A (Valentino):** Enfoque en `scripts/04_descargar_precios.py`
   - Implementar fallbacks si yfinance falla
   - Agregar retry logic
   - Integrar con Job 1A en FastAPI

2. **Backend B (Mateo):** Enfoque en `scripts/03_descargar_financials_sec.py` + `scripts/05_calcular_ratios.py`
   - Completar la lógica de TTM en `scripts/05_calcular_ratios.py` función `ttm_flujo()`
   - Implementar CAGR en función `cagr()`
   - Integrar con Job 1B y Job 2 en FastAPI

3. **Frontend A/B (Joaquin, Aldana):** Enfoque en el CSV final
   - `seguimiento.csv` es lo que necesitan para el dashboard
   - Las 60 columnas se describen en `MAPEO_COLUMNAS.md`
   - Las métricas se explican en `FORMULAS_RATIOS.md`

## 🏃 Orden de Lectura Recomendado

**5 min:** README.md → FLUJO_GENERAL.md  
**15 min:** SCRIPT_03, SCRIPT_04, SCRIPT_05 (docs/)  
**10 min:** FORMULAS_RATIOS.md + SCHEMA_EXPLICADO.md  
**5 min:** MAPEO_COLUMNAS.md + ejemplos/  

**Total: 35 minutos para entender TODO el pipeline**

---

**¿Preguntas?** Chequea los archivos en `docs/` — toda la info está ahí.  
**¿Necesitas modificar código?** Los scripts en `scripts/` tienen todo comentado.
