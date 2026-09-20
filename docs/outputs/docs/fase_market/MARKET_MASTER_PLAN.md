# MARKET MASTER PLAN — Capa Market Data Catalaxia

**Estado:** M22 (Golden Case YPF) ejecutado y confirmado **PASS_WITH_WARNINGS** contra el
código vigente (reconfirmación 2026-08-25, tercera corrida real independiente — ver
"Decisión GO (M22)" al final). M23 queda desbloqueado documentalmente; su implementación
(`m6_scale.py`) no existe todavía. · **Fuente externa:** Yahoo Finance (yfinance 1.3.0)
**Identidad canónica:** `dim_entity` + `dim_instrument` (screener.db) → publicada a PostgreSQL
**Persistencia:** PostgreSQL 16.14 (día 1, decisión 2026-08-24)

> Esta tabla estuvo desactualizada entre 2026-08-23 22:23 (redacción original, todo ⏳)
> y 2026-08-25 (esta reconciliación): el código y las corridas reales ya habían superado
> lo que la tabla reflejaba. Reconciliado contra evidencia de filesystem/DB/tests, no
> contra el texto previo del plan — ver `.claude/state/MARKET_STATE.md`.

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
| M25a | Docs skeleton | MARKET_DISCOVERY_REPORT.md ✅ / MARKET_MASTER_PLAN.md (este) | 🔄 (FETCH_DESIGN/DATA_MODEL/VALIDATION_SPEC como documentos M19-M21 separados no existen; su contenido vive en `market_schema.sql` + docstrings de `m4_quality.py`) |
| M19 | DDL PostgreSQL `market_*` (10 tablas) | `scripts/market/market_schema.sql` + `m19_apply_schema.py` | ✅ DONE |
| M1-M2 | Identity→Yahoo mapping + discovery por instrumento | `m1_symbol_mapping.py` (lee dim_instrument; cero mappings manuales) | ✅ DONE (C-MKT-001/007 VALID: 584 MAPPED, 0 conflictos) |
| M3-M5 | Fetch max-history → RAW → modelo OHLCV | `m2_fetch_engine.py` | ✅ DONE (period=max; RAW verificado 26/26 archivos, 0 alterados) |
| M6 | Corporate actions separadas | `m2_fetch_engine.py` + `market_core.py` | ✅ DONE (C-MKT-016 VALID: dividendos/splits de la serie coinciden con `market_corporate_actions`) |
| M7-M9 | Close/AdjClose + snapshots + 52w derivadas | ídem | 🔄 PARCIAL — Close/Adj Close separados y snapshots ✅ (C-MKT-010/014 VALID); **52w derivadas: no implementado** (sin código bajo `scripts/market/` que lo calcule) |
| M10-M12 | Incremental + force-refresh + change detection + fingerprints | `m2_fetch_engine.py` + `market_core.py` (no existe `m3_update.py` como módulo separado — la lógica vive en estos dos archivos) | ✅ DONE — probado en vivo, no solo por unit test: la corrida real de reconfirmación (2026-08-25) detectó y clasificó correctamente 1 `VOLUME_RESTATEMENT` real en instrumento 84 |
| M13-M15 | Quality checks, coverage, certificación daily close | `m4_quality.py` | ✅ DONE (17 gates C-MKT-001..017 activos) |
| M16-M18 | Separación ADR/local + catálogo campos + options doc | — | 🔄 PARCIAL — separación ADR(84)/local(83) probada y activa (C-MKT-006); **catálogo de campos y doc de opciones: no localizados**, no existen como entregable |
| M20-M21 | fetch_log + validación cruzada snapshot vs history | `market_fetch_log` / `market_snapshots` (C-MKT-014, C-MKT-017) | ✅ DONE |
| M22 | **GOLDEN CASE YPF** (instrumentos 83/84) | `m5_golden_case.py` (el plan original decía `m5_golden_case_ypf.py`; el archivo real es genérico por instrumento, no atado a YPF por nombre) | ✅ **PASS_WITH_WARNINGS** — ejecutado 3 veces reales (2026-08-24 ×2, 2026-08-25 ×1) + 18/18 tests unitarios. Ver "Decisión GO (M22)" |
| M23 | Escalamiento por lotes (rate limit, retry, checkpoint) | `m6_scale.py` — **no escrito** | 🔓 DESBLOQUEADO documentalmente (M22 GO registrado 2026-08-25); implementación pendiente, sigue sin empezar |
| M24 | Gates C-MKT-001..015 embebidos por etapa | `m4_quality.py` | ✅ DONE — en la práctica son 17 gates (C-MKT-001..017), más de los 15 previstos originalmente |
| M26-M27 | Reporte 20 preguntas + matriz ratios (sin calcularlos) | docs | ⏳ no iniciado |

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

## Decisión GO (M22) — 2026-08-25

**Veredicto: PASS_WITH_WARNINGS.** Los 20 puntos del criterio GO tienen evidencia; ninguno
falló. Dos advertencias legítimas quedan registradas (no corregidas en silencio, no
convertidas en PASS limpio):

| # | Punto | Evidencia |
|---|---|---|
| 1 | identity | C-MKT-001 VALID — 0 precios sin identidad |
| 2 | mapping | C-MKT-007 VALID — 584 MAPPED, 0 símbolos compartidos |
| 3 | backfill máximo | `period=max` en los params de fetch; 83 desde 2000, 84 desde 1993 |
| 4 | RAW preservado | C-MKT-015 VALID — 26/26 archivos verificados, 0 ausentes/alterados |
| 5 | OHLC completo | C-MKT-009 VALID — 0 nulos en OHLC/volumen |
| 6 | Close/Adj separados | C-MKT-010 VALID — ruido de Adj Close nunca persiste (tolerancia 1e-5) |
| 7 | corporate actions | C-MKT-016 VALID — dividendos/splits de la serie == tabla dedicada |
| 8 | provenance | C-MKT-002/017 VALID — toda fila tiene corrida de origen con fuente/versión/params |
| 9 | SHA256 | C-MKT-012/015 VALID — hash reconstruible al 100%, RAW con sha verificado |
| 10 | coverage | C-MKT-003 VALID — 0 gaps > umbral |
| 11 | quality PASS | **PASS_WITH_WARNINGS** (ver advertencias abajo) — no es un PASS limpio |
| 12 | staleness | C-MKT-011 VALID — último cierre 2026-08-24, staleness=1 día, coherente con el cutoff |
| 13 | incremental probado | corrida real 2026-08-25 escribió 1 fila nueva (84) sobre una base ya persistida |
| 14 | idempotencia probada | instrumento 83: SIN_CAMBIOS en 3 corridas reales consecutivas + test 02 |
| 15 | change detection probado | la misma corrida real detectó y clasificó `VOLUME_RESTATEMENT` correctamente (no fue solo el unit test) |
| 16 | separación ADR/local | 83 (LOCAL, ARS, BUE) y 84 (ADR, USD, NYSE) como instrumentos independientes, C-MKT-006 |
| 17 | snapshot ≠ histórico | C-MKT-014 VALID — snapshots en tabla separada, la serie histórica no tiene campos de snapshot |
| 18 | outputs bajo outputs/ | todo el paquete Golden Case vive en `outputs/docs/fase_market/golden/` |
| 19 | reproducibilidad | reconfirmado por una tercera corrida real independiente, con resultado explicado, no solo repetido a ciegas |
| 20 | cero conflictos de identidad | C-MKT-001/007 VALID |

**Advertencias activas (no bloqueantes, ambas explicadas — no son bugs del pipeline):**

1. **C-MKT-004** (instrumento 83, YPFD.BA): 4 ruedas con OHLC internamente incoherente
   (2007-10-12, 2007-10-25, 2011-05-03, 2012-11-02 — `LOW_GT_OPEN`/`HIGH_LT_CLOSE`).
   Verificado byte a byte contra el RAW archivado de cada corrida: el valor incoherente
   ya viene así en el payload crudo de Yahoo (`introducidas por el pipeline=0` en las
   tres corridas reales). No coincide con ninguna fecha de dividendo/split (tabla
   `market_corporate_actions`, instrumento 83). Conclusión: defecto de la fuente
   (Yahoo, sesiones históricas de un ticker BYMA poco líquido de esa época — consistente
   con hallazgos previos del proyecto sobre calidad de datos yfinance en BYMA). Tratamiento
   correcto: **mantener como WARNING**, no reescribir el valor.
2. **C-MKT-013** (instrumento 84, YPF/NYSE) — **nueva en esta reconfirmación**: la rueda
   del 2026-08-24 cambió de volumen entre la corrida del 24 (sesión todavía `CURRENT`,
   volumen intradía) y la del 25 (sesión ya `FINALIZED`, volumen de cierre oficial). OHLC
   no cambió. El pipeline clasifica esto como `VOLUME_RESTATEMENT` (no está en
   `BENIGN_REASONS` por diseño: cualquier cambio en una rueda que dejó de ser `CURRENT`
   se marca para revisión humana en vez de aceptarse en silencio). Es el comportamiento
   esperado del asentamiento de volumen post-cierre, no un bug de determinismo del
   pipeline — pero como el código no distingue "primera vez que una rueda deja de ser
   CURRENT" de una restatement genuina años después, seguirá apareciendo cada vez que el
   golden case se re-ejecute al día siguiente de haber capturado una sesión en curso. No
   se corrigió (no era un error de código); queda documentado para que una futura sesión
   decida si vale la pena una razón de cambio más fina.

**No confundir con un GO limpio ni con un BLOCKED**: no hay ningún gate `INVALID`, ningún
test roto, ningún dato inventado ni corregido en silencio. `M23` queda desbloqueado
documentalmente (los 20 puntos tienen evidencia), pero `m6_scale.py` sigue sin escribirse.
