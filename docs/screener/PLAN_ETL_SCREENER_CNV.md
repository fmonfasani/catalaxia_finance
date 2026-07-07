# Plan ETL — Screener de 13 ratios (fundamentales CNV + precios yfinance)

> Objetivo: producir los **13 ratios × empresa argentina**, con los **7 fundamentales
> desde CNV** (`cnv_estados`) y los **6 de precio desde yfinance**. Robusto, idempotente,
> replicable y sistemático. Ver contexto en [00_VISION_GENERAL.md](00_VISION_GENERAL.md)
> y el estado de extracción en [ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md).

Alcance inicial: las 56 BYMA-only + los ADR (subset ya extraído). Escalable a la mina 556.

---

## Principios de diseño (por qué es robusto y replicable)

1. **Idempotente**: cada paso reconstruye su tabla de salida (`DROP`/`REPLACE`). Se puede
   re-correr N veces con el mismo resultado.
2. **Provenance**: cada ratio guarda `fuente` (cnv/yfinance/edgar), `period_end` y `fecha`.
   Nunca hay un número sin saber de dónde salió.
3. **Gates de validación entre fases**: si un chequeo falla (cobertura, identidad), se
   frena — no se avanza con data sucia.
4. **Config-driven**: universo (subset / 556), período, y **prioridad de fuente** por ratio
   se definen en un solo lugar.
5. **Determinístico**: de `cnv_estados` + yfinance → `screener` da siempre lo mismo.
6. **Fallbacks explícitos y flageados**: los bancos no parsean desde CNV (plantilla
   financiera) → caen a yfinance/EDGAR, marcados en la columna `fuente`.

---

## Mapeo de los 13 ratios → fuente y fórmula

| # | Ratio | Fuente | Fórmula |
|---|---|---|---|
| 1 | Precio u$s | yfinance | `precio_local × fx_a_usd` |
| 2 | PER | **híbrido** | `market_cap_usd / (NetIncome_CNV × fx)` |
| 3 | Máx 52 sem | yfinance | `year_high` |
| 4 | Dif Máx | yfinance | `precio/year_high − 1` |
| 5 | Mín 52 sem | yfinance | `precio/year_low − 1` |
| 6 | Dif Mín | yfinance | `precio/year_low − 1` |
| 7 | Deuda/EBITDA | **CNV** | `(DebtCurrent+DebtNonCurrent) / EBITDA` |
| 8 | EPS anual | **CNV** | `EPS_basico` (último anual) |
| 9 | Crec. EPS 5y | **CNV** | `CAGR(EPS_basico, 5y)` — usa la serie de ~15 años |
| 10 | Margen Neto | **CNV** | `NetIncome / Revenue` (validar vs `CNV_margen_neto`) |
| 11 | ROE | **CNV** | `NetIncome / Equity` (validar vs `CNV_roe`) |
| 12 | FCF/CE | **CNV** | `(CF_Operativo + CF_Inversion) / (Equity + DebtNonCurrent)` |
| 13 | Payout | **CNV** | `Dividendos / NetIncome` (dividendos de `cnv_dividendos`) |

---

## Las fases (ETL)

Scripts nuevos en **`scripts/tickets/screener/`**. Cada uno lee/escribe `data/screener.db`.

### FASE 0 — Normalización de clave (destrabar) · `s0_normalizar_cnv.py`
El bloqueante: las filas nuevas de `cnv_estados` tienen `cik`=CUIT y `ticker`=nombre.
- **In**: `cnv_estados`, `empresas_subset.csv`, `empresas`.
- **Proceso**: construir tabla `mapa_entidades (cuit, ticker, cik_canonico, grupo, nombre)`;
  reescribir `cnv_estados` a **clave por CUIT** consistente; deduplicar viejo (`BYMA-*`) vs
  nuevo (CUIT) **prefiriendo el nuevo** (historial completo + identidad validada).
- **Out**: `cnv_estados` normalizado + `mapa_entidades`.
- **Gate**: 0 CUIT sin mapear en el subset; 0 duplicados por (empresa, period_end, concepto).

### FASE 1 — Validación de calidad · `s1_validar_identidad.py` (= `job7_validar.py`)
- **In**: `cnv_estados`.
- **Proceso**: identidad contable por filing → `cnv_estados_suspect` (ya existe). `--purge`
  selectivo de los rotos.
- **Out**: `cnv_estados_suspect` actualizado.
- **Gate**: % de filings suspect < umbral (hoy ~0,3%).

### FASE 2 — Ratios fundamentales desde CNV · `s2_ratios_cnv.py`
- **In**: `cnv_estados` (excluyendo suspect), `cnv_dividendos`, `mapa_entidades`.
- **Proceso**: por empresa, elegir **último período anual limpio** (ref. para ratios
  estáticos) + la **serie anual** para CAGR. Calcular los 7 fundamentales (tabla de arriba),
  usando los ratios pre-calc de CNV como **cross-check/fallback**. Payout: joinear dividendos.
- **Out**: tabla `ratios_cnv (cuit, ticker, period_ref, deuda_ebitda, eps_anual,
  cagr_eps_5y, margen_neto, roe, fcf_ce, payout, + cross-check CNV_*, fuente, fecha)`.
- **Gate**: `ROE_computado ≈ CNV_roe` (diferencia < X%) en la mayoría; reportar cobertura
  por ratio (cuántas empresas tienen cada uno no-nulo).

### FASE 3 — Precios desde yfinance · `s3_precios_yf.py`
- **In**: `mapa_entidades` (para el ticker `.BA`), `ratios_cnv` (NetIncome para PER).
- **Proceso**: bajar `precio`, `year_high`, `year_low`, `market_cap` de yfinance + FX a USD.
  Reusa la lógica robusta de [`precios_y_valuacion.py`](../../scripts/tickets/sec_edgar/scripts/precios_y_valuacion.py)
  (market cap USD, flag `fx_ars`).
- **Out**: tabla `precios` (por clave canónica).
- **Gate**: cobertura de precio; flag `fx_ars` en las ARS.

### FASE 4 — Ensamblado del screener · `s4_armar_screener.py`
- **In**: `ratios_cnv` (7-13) + `precios` (1-6).
- **Proceso**: derivar los 4 triviales (Precio u$s, dif máx/mín, PER híbrido), unir en los
  **13 ratios nombrados** por empresa. Para **bancos / empresas sin CNV** → fallback a la
  tabla `ratios` (yfinance/EDGAR), marcando `fuente`.
- **Out**: tabla `screener (ticker, cuit, grupo, [13 ratios], fuente_por_ratio, fecha)` +
  **export CSV** `data/screener_export.csv` (artefacto versionable).
- **Gate**: reporte de **cobertura real por ratio** (el número duro).

### FASE 5 — Validación final · `s5_validar_screener.py`
- **In**: `screener`.
- **Proceso**: cross-checks (ROE vs CNV, outliers, nulos), resumen por universo.
- **Out**: reporte + CSV compacto listo para git.
- **Gate**: sin outliers absurdos; cobertura documentada.

---

## Orquestación

`run_screener.py` corre FASE 0→5 en orden, frenando en el primer gate que falle. También
se puede correr paso a paso (cada `sN_*.py` es autónomo e idempotente).

```
python run_screener.py                 # todo, con gates
python scripts/tickets/screener/s2_ratios_cnv.py   # un paso suelto (re-corre limpio)
```

## Tablas resultantes en la DB

| Tabla | Fase | Contenido |
|---|---|---|
| `mapa_entidades` | 0 | cuit ↔ ticker ↔ cik ↔ grupo |
| `cnv_estados` (normalizado) | 0 | estados con clave consistente |
| `cnv_estados_suspect` | 1 | filings a excluir |
| `ratios_cnv` | 2 | los 7 fundamentales desde CNV |
| `precios` | 3 | precio/máx/mín/mcap/fx |
| `screener` | 4 | los 13 ratios × empresa (+ provenance) |

## Cómo escalar a la mina 556
El pipeline es el mismo. Solo cambia el input de extracción: correr `job5`/`job6`
**sin `--cuits`** (todo el universo), y las fases 0-5 no cambian — operan sobre lo que
haya en `cnv_estados`.
