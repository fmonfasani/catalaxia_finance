# screener_export.csv — Guía de uso y limitaciones honestas

> Screener de **13 ratios** para ~72 empresas argentinas (56 BYMA-only + 17 ADR).
> **Fundamentales desde CNV** (estados contables oficiales, NIC 29), **precios desde
> yfinance**. Generado por el ETL de `scripts/tickets/screener/` (ver
> [docs/screener/PLAN_ETL_SCREENER_CNV.md](../docs/screener/PLAN_ETL_SCREENER_CNV.md)).
>
> **Leé esto antes de usar los datos.** No todos los ratios son igual de confiables, y
> este archivo te dice exactamente cuáles y por qué.

Fecha de generación: 2026-07.
Cada fila tiene `period_ref` (fecha del último estado contable disponible) y
`dato_desactualizado` (flag = 1 si `period_ref` es anterior a 2024).

---

## Fuente por ratio

| # | Ratio | Fuente | Nota |
|---|---|---|---|
| 1 | Precio (u$s) | yfinance | precio local × FX |
| 2 | PER | híbrido | market_cap / NetIncome (misma moneda) |
| 3 | Máx 52 sem | yfinance | |
| 4 | Dif Máx | yfinance | precio/máx − 1 |
| 5 | Mín 52 sem | yfinance | |
| 6 | Dif Mín | yfinance | precio/mín − 1 |
| 7 | Deuda/EBITDA | **CNV** | (DebtCurrent+DebtNonCurrent)/EBITDA |
| 8 | EPS anual | **CNV** | EPS_basico último período |
| 9 | Crec. EPS 5y | **CNV** | ⚠️ ver limitación 1 |
| 10 | Margen Neto | **CNV** | NetIncome/Revenue |
| 11 | ROE | **CNV** | NetIncome/Equity |
| 12 | FCF/CE | **CNV** | (CF_Op+CF_Inv)/(Equity+DeudaLP) |
| 13 | Payout | **CNV / yfinance** | ⚠️ ver limitación 4 |

## Cobertura medida (no estimada)

| Ratio | Cobertura | Ratio | Cobertura |
|---|---|---|---|
| ROE | 65/72 (90%) | FCF/CE | 69/72 (96%) |
| ROA | 65/72 (90%) | CAGR EPS 5y | 46/72 (64%) ⚠️ |
| Margen Neto | 64/72 (89%) | PER | 24/72 (33%) |
| Deuda/EBITDA | 47/72 (65%) | P/B | 40/72 (56%) |
| EPS | 67/72 (93%) | P/S | 36/72 (50%) |
| Precio | 69/72 (96%) | Payout | 15/72 (21%) ⚠️ |

**Resumen honesto:** de los 13, ~11 confiables, 1 aproximado (CAGR), 1 parcial (payout).

---

## Limitaciones (leer sí o sí)

### 1. CAGR EPS 5y — flag `vintage_mixto` — APROXIMADO
Argentina reexpresa los estados por inflación (NIC 29): el mismo período tiene valores
nominales distintos según de qué balance se lo extrajo. La serie histórica **mezcla
vintages de reexpresión**, así que el "crecimiento" puede incluir efecto inflacionario,
no solo crecimiento real. **Usalo como orden de magnitud, no como dato exacto.** Para
tenerlo fino haría falta control de vintage (pendiente).

### 2. Valuación (PER / P/B / P/S) — flag `no_significativo`
En empresas con **ganancias / patrimonio / ventas ≈ 0**, estos ratios explotan a valores
absurdos (PER de millones). Están **marcados con flag** — **filtralos antes de usar o
promediar.** No son "extremos reales", son división por casi-cero.

### 3. Bancos y entidades financieras — flag `banco_fallback` (28/72)
Los bancos usan una plantilla contable distinta (sin los códigos estándar), así que
**nuestro cálculo de ROE/ROA/Margen no aplica**. Para esas entidades se usa el **ratio
oficial pre-calculado de la CNV** (`CNV_roe`, etc.), marcado con el flag. El PER de bancos
**no es confiable** (NetIncome mal mapeado) — no lo uses.

### 4. Payout — 15/72 (parcial)
Solo hay dato de dividendos donde yfinance lo reporta. Las otras ~57 tienen payout NULL:
puede ser que **no pagaron** o que **falta el dato** — no asumir 0. Upgrade pendiente:
parsear los montos de los formularios de dividendos de CNV (`cnv_dividendos`).

### 5. Datos desactualizados — flag `dato_desactualizado` ⚠️
El parser de estados CNV tiene un bug que afecta filings recientes (~2024+): ciertos
conceptos se parsean a escala incorrecta. Aproximadamente la mitad de las empresas
tiene **algún** período roto, pero solo 16/72 se quedaron **sin ningún período 2024
bueno** (el resto encontró un período válido más reciente vía la guardia automática).

**Consecuencia:** 16/72 filas tienen `period_ref` anterior a 2024 (∼2+ años de
antigüedad). En particular:
  - TXAR, BPAT → 2020 (5+ años)
  - METR → 2021 (5 años)
  - BYMA, GBAN, HARG → 2022 (4 años)
  - OEST, AUSO, CTIO, etc. → 2023 (3 años)

**Importante:** para estas filas, PER / P/B / P/S están anulados explícitamente
(NULL) porque cruzan precio actual (2026) con fundamentales viejos — el ratio no
tiene sentido. Los fundamentales puros (ROE, Margen, etc.) sí son consistentes
internamente (todo del mismo `period_ref`).

Filtrá `dato_desactualizado=0` si necesitás empresas con estados recientes (< 2 años).
Un fix de raíz (corregir el parser de CNV para las plantillas nuevas) está pendiente
como mejora prioritaria.

### 6. Precios en ARS — flag `fx_ars`
Los precios/valuación en pesos convertidos a USD son **poco confiables** por la inflación
y la brecha cambiaria. Están flageados. Tratá la valuación de esas como referencia gruesa.

---

## Cómo leer los flags

Antes de rankear o promediar cualquier ratio, **excluí las filas con el flag correspondiente**:
- Ranking por PER/P-B/P-S → excluir `no_significativo`.
- Análisis de bancos → tratar `banco_fallback` aparte (ratios oficiales CNV).
- Series de crecimiento → recordar que CAGR es `vintage_mixto`.
- Datos actuales → excluir `dato_desactualizado=1`.

## Qué NO hacer
- No promediar PER/P-B/P-S sin filtrar `no_significativo` (te contaminan los millones).
- No asumir payout=0 donde está NULL.
- No comparar la valuación en ARS (`fx_ars`) 1:1 contra los ADR en USD.

## Cómo se reconstruye
ETL en `scripts/tickets/screener/` (s0 normalizar → s2 ratios CNV → s3 precios →
s4 ensamblar → s5 export). Requiere `data/screener.db` (no está en git, 728MB).
Detalle: [docs/screener/PLAN_ETL_SCREENER_CNV.md](../docs/screener/PLAN_ETL_SCREENER_CNV.md).
