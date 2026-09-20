# Diseño de implementación — Fundación de datos v1 (2026-07-14)

Implementa el [CONTRATO_datos.md](CONTRATO_datos.md) usando el esquema de
[CONCEPTOS_canonicos.md](CONCEPTOS_canonicos.md). Backend: **PostgreSQL**.

## Arquitectura (medallion)
```
                DESCARGA (idempotente, logueada, hasheada)
  SEC EDGAR ───┐   CNV ───┐   Yahoo (precios + AL30/AL30C) ───┐
               ▼          ▼                                    ▼
  [BRONZE / raw]  raw_sec_facts · raw_cnv_estados · raw_prices   (INMUTABLE)
               │
               ▼  parse + identidad + unidad/moneda + de-acumular + RECPAM
  [SILVER/parsed] dim_entity · dim_instrument · concepto_crosswalk · fact_financials
               │                                   └─► fact_financials_cuarentena (falla contrato)
               ▼  ratios + ensamblado
  [GOLD/derived]  fact_ratios · prices_daily · screener
               │
               ▼  control continuo
  RECONCILIACIÓN vs investing (ratios_externos / eerr_externos)
```

## Capa BRONZE (raw, inmutable)
| Tabla | Contenido | Claves de trazabilidad |
|---|---|---|
| `raw_sec_facts` | XBRL tal cual (todos los tags) | cik, tag, unit, period_start/end, val, fy, fp, form, **accession**, filed, downloaded_at, **sha256** |
| `raw_cnv_estados` | AIF CNV tal cual | cuit, concepto_origen, period_end, tipo, valor, **unidad**, **moneda**, fecha_reexpresion, form, **docid**, downloaded_at, **sha256** |
| `raw_prices` | Cierres yf + bonos CCL | ticker, fecha, close, currency, source, downloaded_at |
| `ingest_log` | Toda descarga | source, ref, http_status, sha256, bytes, path, fetched_at, error |

**Regla:** nada se pisa. Correcciones = nueva fila (versionado por `downloaded_at`/`accession`).

## Capa SILVER (parsed, con contratos)
### `dim_entity` — identidad canónica (resuelve el lío ticker/razón social)
`entity_id PK` · `cuit` · `cik` · `ticker_canonico` · `nombre` · `grupo` (byma_only/adr/sp500) ·
`moneda_funcional` · `fy_end_month` · `es_financiera`. **Una fila por empresa real.**

### `dim_instrument` — cada cotización
`instrument_id PK` · `entity_id FK` · `ticker` · `mercado` (BYMA/NYSE/NASDAQ) · `tipo`
(ordinaria/adr/cedear) · `moneda` · `ratio` (de `adr_ratios`/`cedear_ratios`).

### `concepto_crosswalk` — mapeo a canónico
`fuente` (sec/cnv) · `origen` (tag XBRL o concepto CNV) · `concepto_canonico` · `signo` · `nota`.
Semilla desde [CONCEPTOS_canonicos.md](CONCEPTOS_canonicos.md). Extensible sin tocar el esquema.

### `fact_financials` — fundamentals normalizados (el corazón)
`entity_id` · `concepto_canonico` · `period_end` · `period_type` (Q/A) · `fiscal_q` ·
`valor` · `moneda` · `unidad_factor` · **`incluye_recpam` (bool)** · `fecha_reexpresion` ·
`fuente` (sec/cnv) · `source_ref` (accession/docid) · `loaded_at`.
**Contrato (UNIQUE):** (entity_id, concepto_canonico, period_end, period_type, incluye_recpam, fuente).
- CNV se **des-acumula** YTD→standalone con `fy_end_month`.
- Conceptos afectados por RECPAM → 2 filas (`incluye_recpam` true/false).

### `fact_financials_cuarentena` — lo que NO pasa validación
Misma forma + `motivo_rechazo`. No entra al gold hasta resolverse.

## Capa GOLD (derived)
| Tabla | Qué |
|---|---|
| `fact_ratios` | Ratios canónicos por entity/period/`incluye_recpam` (TTM para flujos, snapshot balance) |
| `prices_daily` | ticker, fecha, `precio_ars`, `precio_usd`, `ccl`, `market_cap`, `max_52s`, `min_52s` |
| `screener` | Producto: las columnas de [CONCEPTOS_canonicos.md §G](CONCEPTOS_canonicos.md) |

### Precios / CCL (regla del contrato §4)
- only-byma: `precio_ars` (yf BYMA) · `precio_usd = precio_ars / ccl_mercado` · `ccl_mercado = AL30/AL30C`.
- ADR: `precio_adr_usd` (yf US) · `precio_ars` (yf BYMA) · `ccl_implicito = precio_ars·ratio/precio_adr_usd`.
- US: `precio_usd` (yf).

## Pipeline (stages, idempotentes)
| Stage | Qué hace | Falla → |
|---|---|---|
| **S0 descarga** | SEC companyfacts (por CIK) · CNV (por cuit/docid) · yf (precios + AL30/AL30C) | log + retry |
| **S1 raw** | Persistir crudo a `raw_*` con hash | — |
| **S2 normaliza** | crosswalk → concepto_canonico · identidad (`dim_entity`) · unidad/moneda per-fact · des-acumular CNV · variantes RECPAM | cuarentena |
| **S3 valida** | Contratos: unidad presente, Revenue≥0, Assets≈Pas+PN, escala consistente, período dentro del trimestre, sin duplicados | cuarentena + alerta |
| **S4 deriva** | Ratios + ensamblar `screener` | — |
| **S5 reconcilia** | vs investing (`ratios_externos`/`eerr_externos`) — control continuo | reporte |

## Job de actualización (cron; deploy VPS luego)
- **Diario (post-cierre):** precios de ~575 tickers (yf) + AL30/AL30C → `prices_daily`.
- **Disparado por filing:** consultar EDGAR (`submissions` API: última presentación por CIK) y CNV
  (docids nuevos); si hay algo nuevo → S0–S4 **solo** para esas entidades.
- **Tabla `freshness`:** por ticker → último período Q/A presente, última verificación, estado
  (`al_dia`/`desactualizado`/`sin_datos`). Permite "comparar todos y actualizar lo que falta".

## Plan por fases (build order)
| Fase | Entregable | Estado |
|---|---|---|
| **0 — Infra** | Dev en **SQLite** (`data/screener.db`); PG vía Docker en la VPS (db.py abstrae ambos) | ✅ decidido |
| **1 — Identidad** | `dim_entity` (572) / `dim_instrument` (584) — resuelve ticker/razón social | ✅ **hecho** (`scripts/pipeline/f1_identidad.py`) |
| **2 — Raw ingest** | Re-extracción CONSOLIDADO de byma_only desde eeff_html (`f2_reextract_batch.py` → `cnv_reextract`, 55/56, 45k filas). Arregla individual→consolidado + unidad + formato nº. **Hecho**; recuperar EDN/BPAT/DGCE + 5 cik ADR pendiente | 🟢 byma ok |
| **3 — Normalización** | `fact_financials` + cuarentena + RECPAM. **CNV hecho** (`f3_normalizar_cnv.py`, 75.733 filas, recon: Rev 10/19, NI 15/19 en trim reciente). SEC (F3b) pendiente | 🟡 CNV ok |
| **4 — Derivados** | `fact_ratios` (844 filas, confianza + RECPAM; PER=precio/EPS). **Ratios hecho** (`f4_ratios.py`; recon ROE 6/18, PER 4/11, los limpios+financieras OK). `screener` §G pendiente | 🟡 ratios ok |
| **5 — Precios/CCL** | `prices_daily` + AL30/AL30C | ⬜ |
| **6 — Jobs/cron** | `freshness` + updates por filing + reconciliación continua | ⬜ |

## Principios no negociables (del contrato)
1. Nada entra al gold sin pasar S3 (validación).
2. Todo dato derivado rastreable a su raw (accession/docid + hash).
3. Un comando reconstruye todo desde raw.
4. La moneda/unidad se lee **por-fact**, nunca se asume por fuente.
