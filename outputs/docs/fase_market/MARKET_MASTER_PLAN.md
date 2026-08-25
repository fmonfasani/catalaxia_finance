# MARKET MASTER PLAN — Capa Market Data Catalaxia

**Estado:** EN EJECUCIÓN · **Fuente externa:** Yahoo Finance (yfinance 1.3.0)
**Identidad canónica:** `dim_entity` + `dim_instrument` (screener.db) → publicada a PostgreSQL
**Persistencia:** PostgreSQL 16.14 (día 1, decisión 2026-08-24)

```
IDENTITY → DISCOVERY/MAPPING → FETCH → RAW/SNAPSHOT → PARSE → NORMALIZE
        → VALIDATION → PERSISTENCE → METRICS
```

## Principios no negociables

1. El ticker Yahoo NO es identidad. Identidad = entity_id/instrument_id.
2. RAW inmutable y versionado. Nunca sobrescribir.
3. Close ≠ Adj Close: ambas series persisten; nunca se sustituyen.
4. Snapshot ≠ histórico. info/fast_info jamás se convierten en hechos históricos.
5. Sin fallback silencioso de símbolos: UNMAPPED/NOT_FOUND/AMBIGUOUS/CONFLICT se registran.
6. ADR USD y local ARS son instrumentos independientes; ratio ADR/local es capa posterior.
7. Cada dato debe poder responder: qué es, de qué instrumento/mercado/fecha, Close o Adj, ticker Yahoo, cuándo/con qué versión/parámetros se descargó, de qué RAW (SHA256), si cambió desde la corrida previa y si pasó quality.

## Fases → módulos

| Fase | Alcance | Módulo / artefacto | Estado |
|---|---|---|---|
| M0 | Contrato/discovery yfinance | `scripts/market/m0_discovery_yahoo.py` + este reporte par | ✅ DONE |
| M25a | Docs skeleton | MARKET_DISCOVERY_REPORT.md ✅ / MARKET_MASTER_PLAN.md (este) / FETCH_DESIGN+DATA_MODEL+VALIDATION_SPEC (M19-M21) | 🔄 |
| M19 | DDL PostgreSQL `market_*` (10 tablas) | `scripts/market/market_schema.sql` + loader | ⏳ |
| M1-M2 | Identity→Yahoo mapping + discovery por instrumento | `m1_symbol_mapping.py` (lee dim_instrument; cero mappings manuales) | ⏳ |
| M3-M5 | Fetch max-history → RAW → modelo OHLCV | `m2_fetch_engine.py` | ⏳ |
| M6 | Corporate actions separadas | ídem | ⏳ |
| M7-M9 | Close/AdjClose + snapshots + 52w derivadas | ídem | ⏳ |
| M10-M12 | Incremental + force-refresh + change detection + fingerprints | `m3_update.py` | ⏳ |
| M13-M15 | Quality checks, coverage, certificación daily close | `m4_quality.py` | ⏳ |
| M16-M18 | Separación ADR/local + catálogo campos + options doc | docs | ⏳ |
| M20-M21 | fetch_log + validación cruzada snapshot vs history | motor | ⏳ |
| M22 | **GOLDEN CASE YPF** → audit xlsx 12 hojas | `m5_golden_case_ypf.py` | ⏳ GATE |
| M23 | Escalamiento por lotes (rate limit, retry, checkpoint) | `m6_scale.py` — solo tras PASS | 🔒 |
| M24 | Gates C-MKT-001..015 embebidos por etapa | validation spec | ⏳ |
| M26-M27 | Reporte 20 preguntas + matriz ratios (sin calcularlos) | docs | ⏳ |

## Criterio GO (M22)

`MARKET_GOLDEN_CASE_PASS` exige los 20 puntos del contrato (identity, mapping,
backfill máx, RAW preservado, OHLC completo, Close/Adj separados, corporate
actions, provenance, SHA256, coverage, quality PASS, staleness, incremental +
idempotencia probados, change detection probado, separación ADR/local,
snapshot≠histórico, outputs bajo outputs/, reproducibilidad, cero conflictos de
identidad). Falla cualquiera → `BLOCKED_MARKET_SCALE` con causa/impacto/mitigación.

## Entregables bajo outputs/docs/fase_market/

Ver contrato M25: 9 documentos maestro + paquete Golden Case (md/xlsx/csv ×4).
Toda ejecución deja evidencia (JSON/logs) junto al resultado.
