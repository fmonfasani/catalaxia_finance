# MARKET GOLDEN CASE

**checkpoint_id:** `MKT-GOLDEN-20260825-89c2f00f26c0`
**veredicto:** PASS_WITH_WARNINGS
**generado (UTC):** 2026-08-25T04:29:30.565145+00:00
**instrumentos:** YPFD.BA (83, LOCAL), YPF (84, ADR)

## 1. Estado por instrumento

| instrument_id | ticker | tipo | moneda | mercado | ruedas | primera | ultima | ultimo close | dividendos | splits |
|---|---|---|---|---|---|---|---|---|---|---|
| 83 | YPFD.BA | LOCAL | ARS | BUE | 6634 | 2000-01-03 | 2026-08-24 | 8175.0 | 16 | 1 |
| 84 | YPF | ADR | USD | NYSE | 8345 | 1993-06-29 | 2026-08-24 | 51.279999 | 58 | 0 |

## 2. Separacion ADR / local

Cada instrumento es una serie independiente, con su moneda, su mercado y sus propias acciones corporativas. No se convierte ni se deriva un ratio entre ellos en esta capa.

| instrument_id | ticker | moneda | mercado | tz | dividendos | splits |
|---|---|---|---|---|---|---|
| 83 | YPFD.BA | ARS | BUE | America/Argentina/Buenos_Aires | 16 | 1 |
| 84 | YPF | USD | NYSE | America/New_York | 58 | 0 |

## 3. Los 20 puntos del contrato

| # | punto | estado | evidencia |
|---|---|---|---|
| 1 | identidad canonica | PASS | entity_id/instrument_id verificados en cada corrida |
| 2 | mapping explicito | PASS | mappings MAPPED, sin simbolos compartidos |
| 3 | backfill maximo | PASS | period=max: YPFD.BA 2000-01-03→2026-08-24; YPF 1993-06-29→2026-08-24 |
| 4 | RAW preservado | PASS | 26/26 archivos RAW verificados |
| 5 | OHLC completo | PASS* | 14979 ruedas con OHLC+volumen |
| 6 | Close y Adj Close separados | PASS | columnas close y adj_close persisten por separado |
| 7 | corporate actions | PASS | 75 acciones corporativas en tabla propia |
| 8 | provenance | PASS | cada fila referencia corrida y RAW existentes |
| 9 | sha256 | PASS | sha256 por archivo, recalculado al generar este caso |
| 10 | cobertura | PASS | cobertura anual y gaps auditados |
| 11 | quality PASS | PASS* | bateria completa ejecutada |
| 12 | staleness | PASS | ultimo cierre certificado con estado de sesion |
| 13 | incremental + idempotencia | PASS* | 7 corrida(s) SIN_CAMBIOS con 0 escrituras |
| 14 | change detection | PASS* | motivos observados: {'YAHOO_UPDATE': 14979, 'VOLUME_RESTATEMENT': 1} |
| 15 | intraday distinguido | PASS | sesion CURRENT clasificada como INTRADAY_UPDATE, no corrupcion |
| 16 | separacion ADR/local | PASS | 2 instrumentos independientes, sin conversion |
| 17 | snapshot != historico | PASS | 10 snapshot(s) en tabla separada |
| 18 | outputs bajo outputs/ | PASS | paquete completo bajo outputs/docs/fase_market/ |
| 19 | reproducibilidad | PASS | 0 fila(s) con hash no reconstruible |
| 20 | cero conflictos de identidad | PASS | sin colisiones de identidad |

## 4. Fingerprints

| instrument_id | ruedas | hash reconstruido | batch_hash |
|---|---|---|---|
| 83 | 6634 | 6634/6634 | 192aa57329485470b2e91ba7… |
| 84 | 8345 | 8345/8345 | 4be3bce56c3bd82981477b2c… |

## 5. Idempotencia observada

| instrument_id | run_id | estado | ruedas recibidas | filas escritas |
|---|---|---|---|---|
| 83 | golden-v5-retest-83-20260824T222714192051Z | SIN_CAMBIOS | 6634 | 0 (ninguna fila escrita) |
| 83 | golden-v5-retest5-83-20260825T042727797783Z | SIN_CAMBIOS | 6634 | 0 (ninguna fila escrita) |
| 84 | golden-v5-retest-84-20260824T222724322764Z | SIN_CAMBIOS | 8345 | 0 (ninguna fila escrita) |
| 84 | golden-v5-retest5-84-20260825T042739898974Z | SUCCESS | 8345 | ver cambios |

## 6. Gates C-MKT

| severidad | n |
|---|---|
| VALID | 29 |
| WARNING | 6 |

Observaciones abiertas:

| gate | instrumento | severidad | detalle |
|---|---|---|---|
| C-MKT-004 | 83 | WARNING | filas=6634; incoherencias=4; reproducidas byte a byte en el RAW (defecto de la fuente)=4; introducidas por el pipeline=0 []; ej=[('2007-10-12', 'LOW_GT_OPEN'), ('2007-10-25', 'LOW_GT_OPEN'), ('2011-05 |
| C-MKT-013 | 84 | WARNING | ultima corrida=golden-v5-retest5-84-20260825T042739898974Z estado=SUCCESS; cambios registrados=[('CHANGED', 'VOLUME_RESTATEMENT', 1)]; no benignos=[('CHANGED', 'VOLUME_RESTATEMENT', 1)] |

## 7. Que NO cubre este checkpoint

* No hay ratios ni metricas derivadas: esta capa entrega precios, acciones corporativas y snapshots, nada mas.
* Los snapshots (`market_snapshots`) son foto del momento y jamas se convierten en hechos historicos.
* `Adj Close` es la metodologia de ajuste de la fuente; para retornos totales se usa esa serie, para precios nominales se usa `close`. Nunca se sustituyen entre si.
