# F-056 — LOS SCRIPTS DE INVENTARIO E2E DECLARABAN SUS PROPIAS LISTAS DE TAGS, SOLO-IFRS, EN VEZ DE USAR EL FALLBACK DE `ratio_defs.py`

**Detectado:** 2026-09-01, al validar la Fase D (multiempresa) del encargo de
auditoría de ratios sobre `ratios_inventario.py` y `e2e_producto.py`
**Severidad: alta** (cobertura, no cálculo) · **Estado: CORREGIDO**

---

## 1. El hallazgo

`ratio_defs.py` ya declaraba, para cada concepto financiero, la cadena de
tags candidatos por taxonomía (ej. `activo_corriente` → `CurrentAssets`
(ifrs-full) **o** `AssetsCurrent` (us-gaap)). Es la fuente de verdad prevista
para resolver ratios sea cual sea la taxonomía del emisor.

`ratios_inventario.py` y `e2e_producto.py` — los dos scripts que producen la
evidencia de cobertura del producto (`ratios_calculados.json`,
`e2e_producto.json`) — **no importaban `ratio_defs`**. Cada uno declaraba su
propio diccionario `FUNDAMENTALES` con listas de tags hardcodeadas que solo
cubrían el lado `ifrs-full` (`CurrentAssets`, `Equity`,
`ProfitLossAttributableToOwnersOfParent`/`ProfitLoss`, `Revenue`,
`CashAndCashEquivalents`…), sin las variantes `us-gaap`
(`AssetsCurrent`, `StockholdersEquity`, `NetIncomeLoss`,
`RevenueFromContractWithCustomerExcludingAssessedTax`,
`CashAndCashEquivalentsAtCarryingValue`…).

## 2. Efecto medido

AAPL, MSFT y NVDA tenían sus facts completos en `derived.fact` (ingeridos
correctamente, con provenance íntegra) y aun así:

```
e2e_producto.py, antes del fix:
  AAPL    EMPRESA OK  IDENTITY OK  SEC_XBRL OK  MARKET OK  METRICAS OK  RATIOS CORTE (0/9)
  MSFT    EMPRESA OK  IDENTITY OK  SEC_XBRL OK  MARKET OK  METRICAS OK  RATIOS CORTE (0/9)
  NVDA    EMPRESA OK  IDENTITY OK  SEC_XBRL OK  MARKET OK  METRICAS OK  RATIOS CORTE (0/9)
```

El corte no era de datos: era de que ningún tag de la lista local coincidía
con lo que un emisor US-GAAP realmente publica. `ratios_inventario.py` daba
el mismo patrón: **0 ratios calculados para las tres empresas US-GAAP** pese
a tener `Assets`, `AssetsCurrent`, `StockholdersEquity`, `NetIncomeLoss`, etc.
verificables en la base con una consulta directa.

## 3. Por qué no lo detectó ningún control

Los controles de `ratios_auditoria.py` (reproducibilidad, provenance,
monedas, períodos) auditan **lo que el implementador afirma haber
calculado**. Si el implementador afirma 0 ratios para AAPL, no hay nada que
reproducir ni que contradecir: el silencio pasaba todos los checks. Es la
misma familia que F-053/F-054/F-055: **el control verificaba la ejecución,
no la premisa** — en este caso, la premisa de que la lista de tags usada
fuera la declarada como fuente de verdad del sistema.

## 4. Corrección aplicada

`ratios_inventario.py` y `e2e_producto.py` ahora importan `CONCEPTOS` y
`RATIOS` de `ratio_defs.py` y construyen su diccionario de fundamentales
programáticamente a partir de esas estructuras, en vez de duplicar listas de
tags. Un solo lugar declara la cadena de fallback; los scripts de cálculo la
consumen.

## 5. Efecto tras la corrección

```
ratios_inventario.py:  188/308 CALCULADO  ->  274/308 CALCULADO
e2e_producto.py:       cadenas completas 1/8  ->  7/8
                        (la unica bloqueada, BMA, corta en IDENTITY —
                         causa distinta y ya documentada: falta el enlace
                         identity_v1.instrument, no un problema de tags)
P/E:                    solo YPFD calculable  ->  6/7 empresas con EPS>0
                        calculan P/E (AAPL 42.00, MSFT 28.06, NVDA 46.23,
                        CEPU 9.39, TGSU2 16.29, GGAL 51.93)
```

Reverificado con el auditor independiente (`ratios_auditoria.py`, que no
importa ninguno de estos módulos): **274/274 ratios reproducidos, 0
divergentes** (control A2).

## 6. Lo que esto no es

- No es un problema de ingesta: los facts de AAPL/MSFT/NVDA ya estaban
  completos y correctos antes de este fix.
- No afecta a `screener_demo.py`, que sí importaba `ratio_defs` desde su
  primera versión — el defecto estaba localizado en los dos scripts de
  inventario/E2E de este ciclo.
- No cambia ningún dato en la base: es una corrección de la capa de
  cálculo, de solo lectura.

## 7. Lección

La declaración correcta (`ratio_defs.py`) existía y estaba bien diseñada.
El defecto fue de **cableado**, no de diseño: dos consumidores la
ignoraron y reimplementaron una versión parcial. "El fallback está
declarado en algún lugar del código" no es lo mismo que "el fallback se usa
donde importa". Ver también F-057, encontrado al recorrer el auditor
independiente sobre este mismo universo ampliado.
