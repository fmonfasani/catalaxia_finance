# MARKET_DISCOVERY_REPORT — Contrato Yahoo Finance

**Fase:** M0 · **Fecha corrida:** 2026-08-24 (UTC)
**Evidencia cruda:** `outputs/docs/fase_market/M0_discovery_evidence.json`
**Entorno:** yfinance **1.3.0** · Python 3.11.9 · Windows

---

## 1. Resultados por instrumento (period=max, interval=1d, auto_adjust=False, actions=True)

| | YPF (ADR NYSE) | YPFD.BA (local BYMA) |
|---|---|---|
| Ruedas | **8.344** ✅ reproduce piloto | 6.633 |
| Primera rueda | 1993-06-29 | 2000-01-03 |
| Última rueda | 2026-08-21 | 2026-08-21 |
| Timezone índice | America/New_York | America/Argentina/Buenos_Aires |
| Currency | USD | ARS |
| Exchange | NYQ → full: **NYSE** | BUE → full: **Buenos Aires** |
| Dividendos | 58 eventos | 16 eventos |
| Splits | 0 eventos | **1 evento** |
| info claves | 170 | 159 |

El número del piloto (8.344) se reproduce → Yahoo mantiene disponibilidad histórica al mismo cutoff.

## 2. Comportamiento `auto_adjust`

- `auto_adjust=False`: devuelve `Open High Low Close Adj Close Volume Dividends "Stock Splits"` → **modo contractual del pipeline**.
- `auto_adjust=True`: **elimina la columna Adj Close** y ajusta OHLC retroactivamente; además las ventanas cortas sin acción corporativa reciente muestran diff=0 (falso neutro). No usar nunca en fetch histórico.

## 3. Close vs Adj Close (definición contractual)

| Campo | Definición | Uso |
|---|---|---|
| `Close` | Precio de cierre nominal reportado por Yahoo para esa rueda. | Precios nominales, foto de ratios, 52w nominal. |
| `Adj Close` | Cierre retroajustado por Yahoo según SU metodología de corporate actions. | Retornos totales / análisis de performance. Nunca reemplaza a Close. |

Prohibido mezclar series o derivar máximos/mínimos nominales desde Adj Close.

## 4. Clasificación de campos (contrato M0)

| Campo | Objeto(s) | Clase |
|---|---|---|
| Open/High/Low/Close/Adj Close/Volume/Dividends/Stock Splits | history | **HISTORICAL** |
| currency, exchange, quoteType, instrumentType | info/meta/fast_info | **STATIC*** (con alerta de drift) |
| regularMarketPrice, regularMarketPreviousClose, fiftyTwoWeek*, day OHLC, volume | info/fast_info | **SNAPSHOT** |
| fiftyDayAverage, twoHundredDayAverage, tenDayAverage, threeMonthAverage | fast_info/info | **DERIVED** (ventana móvil de Yahoo) |
| market_cap, shares | fast_info/info | **UNSTABLE/UNKNOWN** (validar contra CNV antes de usar) |
| firstTradeDate | history_metadata ✅ / info ❌ (None) | **UNSTABLE** (objeto-dependiente) |
| fullExchangeName | history_metadata ✅ / fast_info ❌ | **UNSTABLE** (objeto-dependiente) |
| gmtOffSetMilliseconds, timeZoneShortName/FullName | history_metadata/info | **UNSTABLE** (observados None) |
| firstTradeDate (epoch 741360600) | history_metadata | HISTORICAL-boundary útil para validar cobertura |

Regla dura: **nada de `info`/`fast_info` se trata como hecho histórico.**

## 5. Intervalos sondeados (YPF)

`1wk`(1730) · `1mo`(399) · `1h`(~730d, 5072) · `15m`(60d ventana, 1560) · `1m`(7d/request, 2308) — todos OK.
Core del pipeline: **solo 1d**; los demás quedan documentados como disponibles.

## 6. Pre/post market

- NYSE (YPF): prepost=True agrega +43 barras en 2d/15m → existe.
- BYMA (YPFD.BA): 0 filas extra → **no aplica**. El flag debe registrarse por instrumento, no globalmente.

## 7. Endpoints internos (observación de librería)

yfinance 1.3.0 resuelve vía chart API pública de Yahoo (`query1/query2.finance.yahoo.com/v8/finance/chart`) y quoteSummary para `info`. El pipeline NO hardcodea endpoints: registra `source_version=yfinance@1.3.0` + parámetros de request como contrato reproducible.

## 8. Implicancias para diseño (insumos M3-M12)

1. Índice temporal viene tz-aware por mercado → normalizar a **fecha de mercado (DATE)** preservando tz origen en metadata; nunca convertir a UTC para "fecha".
2. `Stock Splits=0` constante se registra como resultado observado, no como certeza absoluta.
3. Snapshot vs histórico: capas separadas desde el modelo (M8).
4. 52w de fast_info = SNAPSHOT móvil ≠ rolling propio → calcular ROLLING_52_WEEK desde nuestra serie como DERIVED_FROM_HISTORY (M9).
5. ADR vs local: dos instrumentos, dos series, cero conversión automática (M16). El split presente en local y ausente en ADR confirma que ni siquiera los corporate actions son transferibles entre series.

## 9. Brechas abiertas detectadas

- Diff real de Close con/sin auto_adjust requiere ventana con dividendos → validar en fase motor (no bloqueante: contrato ya fija auto_adjust=False).
- Campos `shares`/`marketCap` de fast_info sin segunda fuente aún → UNKNOWN hasta M21/M27.
