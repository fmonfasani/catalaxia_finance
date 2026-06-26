# Pipeline del Screener — `scripts/tickets/`

Sistema completo para construir una **base de datos de ratios financieros** de
acciones que cotizan en EE.UU. (S&P 500 + ADRs), usando **SEC EDGAR** (financials
oficiales) + **yfinance** (precios). Unifica empresas que reportan en **US-GAAP**
e **IFRS** y marca dónde no confiar (flags de calidad).

> **Estado actual:** 8.021 empresas catalogadas, **553 con ratios calculados**
> (S&P 500 + ADRs ARG/BRA/LatAm), ~35 ratios c/u, base `data/screener.db` (~700 MB).
> Última corrida: junio 2026.

---

## 1. Las dos partes del pipeline

### A) Validación (scripts `01`–`05`) — el origen
Pipeline original que **validó la metodología** contra Investing.com sobre 99
tickers (`Tickets.xlsx`). De acá salieron los hallazgos clave (ver
`docs/screener/DIAGNOSTICO_INVESTING_vs_EDGAR.md`). Sigue sirviendo para
re-validar contra una muestra cargada a mano.

| Script | Hace |
|--------|------|
| `01_mapear_cik.py` | ticker → CIK (`company_tickers.json`), excluye tickers reciclados |
| `02_descargar_datos.py` | baja companyfacts (SEC) + precios (yfinance) a `datos/` |
| `03_calcular_ratios.py` | **el calculador validado**: TTM robusto, CAGR, EBITDA, ROE promedio, fix del `fy`, eps_annual, etc. |
| `04_generar_reporte.py` | Excel con tabs Ratios / Calidad / Sin CIK |
| `05_comparar_investing.py` | cruza contra Investing y mide divergencia |

### B) Base de datos (scripts nuevos) — el screener a escala
Pipeline que construye la base unificada para **todo el universo**. Lee/escribe
en `data/screener.db` (SQLite, Postgres-ready).

| Orden | Script | Bloque | Hace |
|-------|--------|--------|------|
| 1 | `construir_catalogo.py` | Bloque 0+1 | catálogo de las 8.021 (ticker, exchange, sector GICS/SIC, país, tamaño, grupo) + metadata de `submissions` |
| 2 | `construir_base.py` | Bloque 2 | descarga **todos los tags** de companyfacts → tabla `facts`. Unifica GAAP/IFRS por concepto canónico. Detecta esquema y moneda |
| 3 | `calcular_ratios_base.py` | — | calcula ~28 ratios fundamentales desde los conceptos canónicos → tabla `ratios` |
| 4 | `precios_y_valuacion.py` | — | precios (yfinance) + market cap + **FX** → ratios de valuación (PER, P/B, P/S, EV/EBITDA, yields) |
| 5 | `flags_calidad.py` | — | **flags de calidad**: marca dónde no confiar (`ni_fy`, `roe_ns`, `fx`, `mktcap_rev`) |

---

## 2. Cómo correrlo (por bloques)

```bash
# Bloque 0+1: catálogo + metadata de las 8.021 (~20 min, resume-safe)
python scripts/tickets/construir_catalogo.py            # o: catalogo / meta

# Bloque 2: facts. Por prioridad. Filtro de 6 años (fase 1).
python scripts/tickets/construir_base.py sp500          # S&P 500 (~15 min)
python scripts/tickets/construir_base.py latam          # ADRs ARG/BRA/LatAm
python scripts/tickets/construir_base.py adr            # solo ADR ARG+BRA

# Capas de cálculo (rápidas, sin red salvo precios)
python scripts/tickets/calcular_ratios_base.py          # ratios fundamentales
python scripts/tickets/precios_y_valuacion.py           # PER, P/B, EV/EBITDA + FX
python scripts/tickets/flags_calidad.py                 # flags de calidad
```

**Robustez:** cada paso es **resume-safe** (saltea lo hecho), **cachea el raw**
en `data/raw/` (fuente de verdad, no se re-baja), y usa **WAL + busy_timeout**.
Respeta el rate limit de SEC (10 req/s) — **no correr dos descargas SEC en
paralelo**.

---

## 3. La base de datos (`data/screener.db`)

```
empresas (8.021)   catálogo: cik, ticker_ppal, exchange, es_sp500, grupo,
                   sector_gics, sic, pais, category, fiscal_year_end,
                   esquema (gaap/ifrs), moneda, n_tags, n_datapoints
tickers (10.433)   cik, ticker, exchange   (multi-clase)
facts (4,6M)       cik, taxonomia, tag, concepto, unit, period_start/end,
                   val, fy, fp, form, filed   ← series temporales crudas
ratios (553)       ~35 ratios + flags + building blocks  (1 fila por empresa)
precios (553)      market cap, precio, 52w, currency
descargas_log      cik, capa, estado, error, ts   (robustez)
```

`grupo` ∈ {`sp500`, `adr_arg`, `adr_bra`, `latam`, `us_other`} — eje de
priorización y segmentación.

### Consultar (ejemplo de screening)
```sql
-- S&P 500 baratas + de calidad, solo las confiables
SELECT ticker, sector_gics, per, roe, deuda_ebitda, fcf_margin
FROM ratios
WHERE grupo='sp500' AND flags IS NULL
  AND per BETWEEN 0 AND 15 AND roe > 0.20 AND deuda_ebitda < 3
ORDER BY per;
```

---

## 4. El fix IFRS (lo que desbloquea los ADRs)

EDGAR habla dos idiomas: **us-gaap** e **ifrs-full**. El mismo concepto tiene
nombres distintos (`NetIncomeLoss` vs `ProfitLoss`, `Revenues` vs `Revenue`,
`StockholdersEquity` vs `Equity`…). `construir_base.py` tiene un **mapeo
canónico** con los tags de las dos taxonomías (los IFRS descubiertos
empíricamente sobre ADRs reales), así una empresa US y una argentina quedan
comparables. Sin esto, casi toda la plaza argentina y media brasilera quedaba en
blanco. Ver `docs/screener/ESPEC_TAGS_RATIOS.md`.

**Moneda:** las IFRS reportan en moneda local (ARS/BRL). Los ratios *puros*
(margen, ROE, payout) no la necesitan; los de *valuación* (PER, P/B) usan
**market cap (USD) + FX**. ARS se marca con flag por la inflación.

---

## 5. Decisiones clave (heredadas de la validación)

- **Nunca estimar:** si falta un componente, el ratio es NULL.
- **TTM rodante** (estrategia B generalizada al caso Q1), no "último año fiscal".
- **Dedup por `end` del período**, no por `fy` (un 10-K trae varios años con el
  mismo `fy`).
- **ROE con equity promedio**; **EBITDA** con D&A comprensivo + amort. de
  intangibles.
- **Validación medida:** PER mediana 1,3% vs Investing, ROE 0,4%, márgenes ~0%.

> Documentación completa: `docs/screener/` (GUIA_SEC_EDGAR_PARA_DEVS,
> DIAGNOSTICO_INVESTING_vs_EDGAR, ESPEC_TAGS_RATIOS) y
> `docs/calculos-financieros/`.

---

## 6. Estructura de datos (no versionada)

```
data/                      ← gitignoreado (pesa GBs)
├── raw/companyfacts/      cache crudo SEC (fuente de verdad)
├── raw/submissions/       metadata cruda
├── catalogo/              company_tickers.json
├── bulk/                  (para el companyfacts.zip masivo de SEC)
└── screener.db            la base
```

El **raw es la fuente de verdad**: la base se reconstruye (o se migra a Postgres)
re-parseando el raw, sin volver a SEC.
