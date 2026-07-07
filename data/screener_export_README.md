# screener_export.csv — Guía de uso y limitaciones honestas (v2)

> Screener de **13 ratios** para ~72 empresas argentinas (56 BYMA-only + 17 ADR).
> **Fundamentales desde CNV** (estados contables oficiales, re-extracción v2 normalizada
> por UnidadMedida), **precios desde yfinance**. Generado por el ETL de
> `scripts/tickets/screener/` (ver
> [docs/screener/PLAN_ETL_SCREENER_CNV.md](../docs/screener/PLAN_ETL_SCREENER_CNV.md)).
>
> **Leé esto antes de usar los datos.** Este archivo documenta cobertura real, fuentes
> y limitaciones de cada ratio.

Fecha de generación: 2026-07.
Cada fila tiene `period_ref` (fecha del último estado contable disponible) y
`dato_desactualizado` (flag = 1 si `period_ref` es anterior a 2024).

---

## Cobertura medida (no estimada)

| Ratio | Cobertura | vs v1 | Nota |
|---|---|---|---|
| ROE | 65/72 (90%) | = | |
| ROA | 65/72 (90%) | = | |
| Margen Neto | 64/72 (89%) | = | |
| Deuda/EBITDA | 48/72 (67%) | = | |
| EPS | 66/72 (92%) | = | |
| FCF/CE | 69/72 (96%) | = | |
| **Payout** | **34/72 (47%)** | **15→34** ✅ | 33 facts + 1 CNV |
| **CAGR EPS 5y** | **46/72 (64%)** | = * | ahora **real** (IPC) |
| **PER** | **33/72 (46%)** | **24→33** ✅ | per-share (Precio/EPS) |
| **P/B** | **45/72 (62%)** | **40→45** ✅ | per-share (Precio/BVPS) |
| **P/S** | **45/72 (62%)** | **36→45** ✅ | per-share (Precio/SPS) |
| Precio | 69/72 (96%) | = | 3 tickers sin cotización Yahoo |
| **Staleness** | **1/72** | **16→1** ✅ | solo PATA_2 (2023, legítimo) |

**Resumen:** de los 13 ratios, ~12 confiables. CAGR es real (deflactado), payout cubre 34/72.

---

## Novedades de la v2

### CAGR real (deflactado IPC INDEC)
La serie histórica de EPS se **deflacta** por el coeficiente IPC (base dic-2016=100,
proveído en `data/ipc_nacional.csv`) antes de computar el CAGR. El resultado es **crecimiento
real**, no nominal. Los valores **negativos** (ej. TXAR -45%, BPAT -35%) son **correctos**:
en la mayoría de las empresas argentinas las ganancias nominales no le ganaron a la
inflación → caída real. Excepción: BHIP +0.9% real (banco que preservó valor).

El flag `vintage_mixto` indica que las fechas de la serie no alinean exactamente con el
período base de 5 años (esperado en empresas con cambios de fecha de cierre).

### Payout desde CNV (ventana de 12 meses)
Además del payout desde facts (yfinance, 33 entidades), se suma el payout calculado desde
los formularios 339 de dividendos de CNV. El monto del dividendo es **total** (no por
acción) y el formulario 339 **no tiene** campo de UnidadMedida (a diferencia de los EEFF),
por lo que el valor es directo.

**Alineación fiscal:** A diferencia de la v1 que agrupaba dividendos por año calendario
de pago (causando desajustes con el ejercicio fiscal), la v2 suma solo los dividendos
pagados en los **12 meses anteriores al cierre fiscal** (`ultimo`). Esto evita mezclar
dividendos de ejercicios distintos y asegura que `payout = dividendos_del_ejercicio / NI_del_mismo_ejercicio`.
Si el total supera 2× el NetIncome (ej. TXAR 516% → filtrado), se descarta como payout
no operativo.

### Valuación por acción (shares_CNV consistente)
En v1 y v2 inicial, PER = market_cap_yahoo / NetIncome_TTM, P/B = market_cap / Equity,
P/S = market_cap / Revenue. Esto suponía que el market cap de Yahoo usaba las mismas
acciones que CNV. En realidad, Yahoo puede usar solo una clase de acciones (ej. CVH:
552M acciones CNV vs 181M Yahoo, ratio 3.06×), o el TTM de NetIncome suma valores
acumulados duplicando períodos (ej. MOLA: PER 3.10 vs Precio/EPS 6.12). La v2 final
usa **Precio / EPS directo** (no necesita acciones), y para P/B/P/S deriva
`shares = abs(NetIncome / EPS_basico)` del mismo período, consistente con CNV.

Para ADR, el precio en USD se convierte a ARS (`precio_ars = precio_usd / fx_usd_per_ars`)
antes de computar los ratios, asegurando moneda homogénea con los fundamentales CNV.

### Normalización de UnidadMedida
Los estados contables CNV v2 se normalizan por su `UnidadMedida` (MILES → ×1000,
MILLONES → ×1.000.000, otro → ×1). Esto corrigió el bug del v1 que dejaba escalas
inconsistentes entre períodos pre-2021 y post-2021.

### Fallback CNV_* eliminado
En v1 se usaban los ratios oficiales CNV (`CNV_roe`, `CNV_margen_neto`, etc.) como
fallback cuando el valor calculado difería del oficial. Con la v2 normalizada, los valores
calculados son más confiables que los v1 stale que aún persisten en esas columnas.
Ya no se aplica.

---

## Fuente por ratio

| # | Ratio | Fuente | Nota |
|---|---|---|---|
| 1 | Precio (u$s) | yfinance | precio local × FX |
| 2 | PER | híbrido | Precio / EPS (per-share, evita market_cap Yahoo con shares inconsistentes) |
| 3 | Máx 52 sem | yfinance | |
| 4 | Dif Máx | yfinance | precio/máx − 1 |
| 5 | Mín 52 sem | yfinance | |
| 6 | Dif Mín | yfinance | precio/mín − 1 |
| 7 | Deuda/EBITDA | **CNV** | (DebtCurrent+DebtNonCurrent)/EBITDA |
| 8 | EPS anual | **CNV** | EPS_basico último período |
| 9 | Crec. EPS 5y | **CNV** | CAGR real (deflactado IPC INDEC) |
| 10 | Margen Neto | **CNV** | NetIncome/Revenue |
| 11 | ROE | **CNV** | NetIncome/Equity |
| 12 | FCF/CE | **CNV** | (CF_Op+CF_Inv)/(Equity+DeudaLP) |
| 13 | Payout | **CNV / yfinance** | facts(yfinance) + cnv_dividendos |

---

## Limitaciones (leer sí o sí)

### 1. CAGR real — flageado `vintage_mixto` — APROXIMADO
El CAGR se deflacta por IPC INDEC (base dic-2016) a pesos constantes. Sin embargo,
la serie histórica de EPS extraída de CNV puede tener vintages mixtos de reexpresión
NIC 29 (el mismo período tiene valores nominales distintos según de qué balance se lo
extrajo). **Usalo como orden de magnitud, no como dato exacto.** Los valores negativos
son caída real (Argentina no crece en términos reales la mayoría de los años).

### 2. Valuación por acción (PER / P/B / P/S) — per-share
PER = Precio / EPS,  P/B = Precio / BVPS,  P/S = Precio / SPS.
**No usa market_cap de Yahoo.** El market cap de Yahoo usa acciones en circulación que
pueden diferir de las implícitas en los balances CNV (diferencia de hasta 3× en CVH
por clases de acciones múltiples). En su lugar, shares_CNV = NetIncome / EPS_basico,
consistente con todos los conceptos CNV. BVPS = Equity / shares_CNV, SPS = Revenue / shares_CNV.

En empresas con **ganancias / patrimonio / ventas ≈ 0 o negativos**, estos ratios
explotan a valores absurdos (PER de millones, P/B de miles). Están **marcados con flag**.
**Filtralos antes de usar o promediar.** No son "extremos reales", son división por
casi-cero.

### 3. Margen Neto y ROE — flag `no_significativo` (nuevo en v2)
El flag `no_significativo` ahora también cubre:
- **MargenNeto**: si Revenue ≤ 0 o |Margen| > 300% (división por Revenue casi-cero o
  ingresos no operativos que dominan). Ej: GCLA (holding, Revenue casi cero) → 584%.
- **ROE**: si Equity ≤ 0 (patrimonio neto negativo o cero). Ej: ROSE → 858%.

El valor crudo se conserva en la celda; el flag indica que no es confiable.

### 4. Payout — 34/72 (47%)
- **33** desde facts (yfinance): Cash Dividends Paid anual / NetIncome.
- **1** desde CNV (`cnv_dividendos`): formularios 339 de dividendos (monto total).
- El payout CNV se calcula con ventana de 12 meses desde el cierre fiscal (`ultimo`),
  sumando solo los dividendos pagados durante el ejercicio. Si el total supera 2× el
  NetIncome (ej. TXAR 516% → filtrado), se descarta por no ser un payout operativo.
- Las 38 restantes tienen payout=NULL: puede ser que **no pagaron dividendos** o que
  **falta el dato**. No asumir 0.

### 5. Datos desactualizados — de 16 a 1 en v2
La re-extracción v2 (normalización de UnidadMedida) corrigió la mayoría de los casos
donde el parser v1 fallaba en períodos recientes (~2024+). Antes 16/72 tenían
`period_ref` anterior a 2024; ahora solo **1/72** (PATA_2, secundaria con cierre
genuino en 2023). El resto tiene datos al 2024-2026.

### 6. Precios en ARS — flag `fx_ars`
BYMA cotiza en ARS. Los precios se convierten a USD usando el tipo de cambio de
yfinance, que puede diferir del CCL o MEP. Tratá la valuación en USD como referencia
gruesa.

### 7. Bancos y financieras
Los bancos usan plantilla contable distinta (sin códigos estándar de CNV). Con la
normalización v2, los ratios calculados (ROE, ROA, Margen) son más confiables que los
v1 stale, aunque el mapeo de conceptos puede no ser perfecto. PER de bancos **no es
confiable** (NetIncome mal mapeado) — no lo uses.

### 8. Sin precio (3 entidades)
BOLT_2, PATA_2 y _ADR_8309 no tienen cotización en Yahoo Finance. Sus tickers BYMA
no existen o cambiaron. P/B, P/S, PER son NULL para estas.

---

## Cómo leer los flags

Antes de rankear o promediar cualquier ratio, **excluí las filas con el flag correspondiente**:
- Ranking por PER/P/B/P/S → excluir `no_significativo`.
- Análisis de Margen o ROE → excluir `no_significativo` (nuevo).
- Series de crecimiento → CAGR es real, pero con posible `vintage_mixto`.
- Datos actuales → excluir `dato_desactualizado=1`.
- Precios ARS → tratar valuación como referencia.

## Qué NO hacer
- No promediar PER/P/B/P/S sin filtrar `no_significativo` (contaminan).
- No asumir CAGR negativo = empresa en crisis (es real, Argentina no crece).
- No asumir payout=0 donde está NULL.
- No comparar valuación ARS 1:1 contra ADR en USD (brecha cambiaria).

## Cómo se reconstruye
ETL en `scripts/tickets/screener/` (s0 normalizar → s2 ratios CNV → s3 precios →
s4 ensamblar → s5 export). Requiere `data/screener.db` (no está en git, ~1GB).
Detalle: [docs/screener/PLAN_ETL_SCREENER_CNV.md](../docs/screener/PLAN_ETL_SCREENER_CNV.md).

El archivo IPC (`data/ipc_nacional.csv`) es provisto externamente (no se descarga).
Contiene el índice de precios INDEC base dic-2016=100 y el coeficiente de deflación
al último mes. Sin este archivo, el CAGR cae a nominal con flag `vintage_mixto`.
