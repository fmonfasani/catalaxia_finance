# Etapa 1 — SEC EDGAR (US + ADR)

> Fuente base y "patrón oro" del proyecto. EDGAR manda; el resto de las fuentes se
> validan contra esto. Ver contexto en [00_VISION_GENERAL.md](00_VISION_GENERAL.md).

## Qué hicimos

Pipeline completo que baja los **XBRL companyfacts** de SEC EDGAR (taxonomías
`us-gaap` e `ifrs-full`), los unifica en conceptos canónicos y calcula ratios.

Flujo ([scripts/tickets/sec_edgar/scripts/](../../scripts/tickets/sec_edgar/scripts/)):

| Paso | Script | Qué hace |
|---|---|---|
| 1 | `01_mapear_cik.py` | ticker → CIK de SEC (para US y ADR) |
| 2 | `02_descargar_datos.py` | baja `companyfacts` por CIK → tabla `facts` (~4,6M hechos) |
| 3 | `03_calcular_ratios.py` / `calcular_ratios_base.py` | motor de ratios (TTM + CAGR) |
| 4 | `04_generar_reporte.py` | reportes |
| 5 | `05_comparar_investing.py` | validación contra Investing.com |
| — | `precios_y_valuacion.py` | precio + PER/P-B/EV-EBITDA con FX (yfinance) |
| — | `flags_calidad.py` | flags de calidad del dato |

### Lógica clave del motor (`calcular_ratios_base.py`)
- **Conceptos canónicos con prioridad de tags**: cuando varios tags XBRL mapean al
  mismo concepto (ej. `NetIncomeLoss` vs `ProfitLoss`), se elige por orden de preferencia.
  Unifica GAAP e IFRS sin ramas separadas.
- **TTM rodante** (`ttm_flujo`): (A) 4 trimestres consecutivos; (B) Anual + parcial nuevo
  − mismo parcial anterior (acepta Q1); (C) último anual. Devuelve la estrategia usada.
- **CAGR** a 5 años sobre la serie anual, con guardas contra valores basura (outliers,
  signos, arranques cerca de cero).
- Ratios con **precio** (PER, P/B, EV/EBITDA, yields) quedan en la capa de precios+FX
  (no en el motor base, que es EDGAR-only sin precio).

## Por qué

- EDGAR es la fuente **primaria, estructurada y auditada** (XBRL obligatorio para
  emisores SEC). Es el patrón contra el que se mide todo.
- Cubre **US (S&P 500)** y **ADR argentinos** que presentan 20-F.
- Al operar por conceptos canónicos, la misma infraestructura sirve para las otras fuentes.

## Datos que produce
- `empresas` (grupo `edgar`), `facts` (taxonomía `us-gaap`/`ifrs-full`), `ratios`, `precios`.

## Qué falta / limitaciones
- **Cobertura de precios**: la capa FX+precios depende de yfinance; revisar completitud.
- **Casos IFRS borde**: algunos emisores IFRS usan tags menos comunes no mapeados aún.
- **Cruce con las otras fuentes**: la conciliación EDGAR-ADR ↔ CNV está pendiente
  (ver [ETAPA_2_ADR.md](ETAPA_2_ADR.md)).
- El cache crudo de companyfacts (`datos/financials_sec/`) está **gitignoreado** (pesa);
  se re-baja corriendo el paso 2.

## Archivos clave
- Motor: [`calcular_ratios_base.py`](../../scripts/tickets/sec_edgar/scripts/calcular_ratios_base.py)
- Descarga: [`02_descargar_datos.py`](../../scripts/tickets/sec_edgar/scripts/02_descargar_datos.py)
- Guía para devs sin background financiero: [../calculos-financieros/](../calculos-financieros/)
