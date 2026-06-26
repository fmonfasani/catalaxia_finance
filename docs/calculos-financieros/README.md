# Cálculos Financieros — Documentación y Código de Referencia

> 📌 **Estado (jun 2026):** esta carpeta es la **investigación previa** que validó
> la metodología. El sistema que **corre hoy** vive en `scripts/tickets/`
> (ver su `README.md`) y puebla `data/screener.db` con 553 empresas (S&P 500 +
> ADRs), GAAP+IFRS unificados. Estos docs siguen siendo la referencia de
> **fórmulas** y el porqué de cada decisión.


Esta carpeta concentra **todo lo relacionado con el cálculo de estados financieros y
ratios** del proyecto: fórmulas, mapeos de datos, diagnósticos de divergencias, y el
código que efectivamente calcula los ratios.

Se armó para tener en un solo lugar el conocimiento de "cómo se calcula cada número".

---

## 📁 `documentacion/` — explicaciones y fórmulas

> Estos archivos fueron **movidos** aquí desde sus ubicaciones originales (cortar y pegar)
> para consolidar la documentación de cálculos.

| Archivo | De qué trata | Origen |
|---------|--------------|--------|
| `FORMULAS_RATIOS.md` | **Fórmulas detalladas de cada ratio** (PER, ROE, EBITDA, margen, payout, FCF, CAGR…) | `_research/docs/` |
| `MAPEO_COLUMNAS.md` | De dónde sale cada columna del CSV final (fuente → dato) | `_research/docs/` |
| `SCHEMA_EXPLICADO.md` | Estructura de las tablas donde viven los datos financieros | `_research/docs/` |
| `SCRIPT_03_FINANCIALS_SEC.md` | Cómo se descargan los financials de SEC EDGAR | `_research/docs/` |
| `SCRIPT_04_PRECIOS.md` | Cómo se descargan los precios (para el PER) | `_research/docs/` |
| `SCRIPT_05_RATIOS.md` | Cómo el script calcula los ~60 ratios por empresa | `_research/docs/` |
| `GUIA_RATIOS_EDGAR_vs_INVESTING.md` | Qué usar de EDGAR y qué ajustar para acercarse a Investing.com | `docs/screener/` |
| `EJEMPLO_CALCULO_LOCAL.md` | Ejemplo: calcular localmente vs descargar pre-calculado | `docs/screener/` |
| `DIAGNOSTICO_INVESTING_vs_EDGAR.md` | Ingeniería inversa de las divergencias columna por columna | `docs/screener/` |
| `RESUMEN_FINAL_HALLAZGOS.md` | Convergencia SEC EDGAR vs Investing.com (qué ratios coinciden) | `docs/screener/` |

---

## 📁 `codigo-referencia/` — el código que calcula

> Estos archivos son **copias** (el original sigue funcionando en su ubicación; acá están
> solo como referencia para estudiar los cálculos).

| Archivo | Qué calcula / hace | Original (NO tocar) |
|---------|--------------------|--------------------|
| `ratios.py` | Calculador de ratios del backend (Job 2) | `backend/calculators/ratios.py` |
| `sec_edgar.py` | Fetcher de financials desde SEC EDGAR | `backend/fetchers/sec_edgar.py` |
| `03_calcular_ratios.py` | Cálculo de ratios del pipeline actual (Tickets.xlsx) | `scripts/tickets/03_calcular_ratios.py` |
| `02_descargar_datos.py` | Descarga de datos financieros (pipeline actual) | `scripts/tickets/02_descargar_datos.py` |
| `07_calcular_ratios.py` | Cálculo de 13 ratios (screener, versión previa) | `scripts/screener/07_calcular_ratios.py` |
| `05_calcular_ratios.py` | Cálculo de ratios (investigación, schema v2) | `_research/scripts/05_calcular_ratios.py` |
| `03_descargar_financials_sec.py` | Descarga de financials SEC (investigación) | `_research/scripts/03_descargar_financials_sec.py` |

> ⚠️ **Importante:** si vas a modificar la lógica de cálculo, hacelo en el **original**, no
> en estas copias. Estas son fotos de referencia para entender cómo se calcula.

---

## ¿Por dónde empezar?

1. **`documentacion/FORMULAS_RATIOS.md`** — entender qué es cada ratio y su fórmula.
2. **`documentacion/MAPEO_COLUMNAS.md`** — de dónde sale cada dato.
3. **`codigo-referencia/ratios.py`** — ver la fórmula implementada en código.
4. **`documentacion/DIAGNOSTICO_INVESTING_vs_EDGAR.md`** — por qué a veces difieren de Investing.

> Para entender cómo se **obtienen** los datos de SEC EDGAR (la API), ver también
> `../screener/GUIA_SEC_EDGAR_PARA_DEVS.md`.
