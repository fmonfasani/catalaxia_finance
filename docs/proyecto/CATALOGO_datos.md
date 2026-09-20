# Catálogo de datos — `data/screener.db` (2026-07-14)

> **REGLA:** antes de pedir un dato, re-derivar algo, o asumir que "no existe", **se consulta
> este catálogo primero.** Si un dato ya está acá, se usa. Se actualiza cuando cambia el esquema.
> (Este doc nace porque se pidió un dato — `ratio_adr` — que ya estaba en `adr_ratios`.)

## Índice rápido — "¿dónde está X?"
| Necesito… | Tabla |
|---|---|
| Ratio de ADR (acciones por ADR) | **`adr_ratios`** (13, con source_url del 20-F) |
| Ratio de CEDEAR (US) | **`cedear_ratios`** (356, de Comafi) |
| Precios ARS/USD/CCL por acción | **`screener`** (`precio_ars`,`precio_usd`,`ccl`,`adr_ratio`,`cedear_ratio`) |
| Fundamentals crudos SEC | **`facts`** (4,6M; `unit` = moneda por-fact) |
| Fundamentals crudos CNV | `cnv_estados` (V1) → `cnv_estados_norm` → `cnv_estados_v2` |
| Moneda/escala de un dato CNV | `cnv_estados_v2` (`moneda`,`unidad_medida`,`unidad_factor`) |
| Identidad (cuit↔ticker↔cik) | `mapa_entidades`, `empresas`, `tickers` |
| Calendario fiscal (fin de ejercicio) | `fiscal_calendar` (`fy_end_month`) |
| Ratios calculados | `ratios` (EDGAR), `ratios_cnv`, `ratios_ttm`, `per_ttm` |
| Datos externos investing (nuestros) | `ratios_externos`, `eerr_externos` |
| Dividendos | `adr_dividendos`, `cnv_dividendos` |

## Tablas por dominio

### Identidad / universo
| Tabla | Filas | Qué | Gotchas |
|---|--:|---|---|
| `mapa_entidades` | 75 | cuit↔ticker↔nombre↔grupo↔cik_byma | El universo AR "oficial" (75) |
| `empresas` | 8.077 | Master SEC: cik, nombre, ticker_ppal, grupo, moneda, sector_gics, sic, pais, esquema, n_tags | ⚠️ `moneda` y `pais` **sucios** (pais="C1", vacíos); no confiar |
| `tickers` | 10.433 | cik↔ticker↔exchange | Mapa SEC completo |
| `instrumentos` | 733 | Por instrumento: ticker, mercado, moneda, ratio, precio | Tiene precio y ratio por instrumento |
| `screener` | 572 | **PRODUCTO**: ratios + precios ensamblados | Ya trae `precio_ars/precio_usd/ccl/adr_ratio/cedear_ratio/es_financiera/sector`. ⚠️ `MarketCapUSD` en realidad es **ARS** |

### Fundamentals crudos
| Tabla | Filas | Qué | Gotchas |
|---|--:|---|---|
| `facts` | 4.605.617 | SEC EDGAR XBRL **+ CNV mapeado** | cik numérico = SEC; cik `BYMA-XXX` = CNV. `unit` = moneda por-fact (**11/13 ADR arg en ARS**) |
| `cnv_estados` | 163.070 | CNV V1 (raw) | Keyed por ticker+cik |
| `cnv_estados_norm` | 84.316 | CNV normalizado (paso intermedio) | |
| `cnv_estados_v2` | 81.695 | CNV V2 (el que usa el pipeline) | ⚠️ byma_only por **ticker**, ADR por **razón social** (rompe joins). Tiene `moneda/unidad_medida/unidad_factor`. Se cayeron EDN/BPAT/DGCE en V1→V2 |
| `cnv_estados_suspect` | 10 | Filas marcadas dudosas (Assets≠Pas+PN) | Semilla de validación |

### Ratios de conversión (precios)
| Tabla | Filas | Qué |
|---|--:|---|
| `adr_ratios` | 13 | **Acciones locales por ADR** (YPF 1, GGAL 10, PAM 25, TEO 5, BBAR 3, CEPU 10…) + source_url del 20-F |
| `cedear_ratios` | 356 | Ratio CEDEAR de acciones US (de Comafi) + ISIN |

### Ratios / derivados
| Tabla | Filas | Qué | Gotchas |
|---|--:|---|---|
| `ratios` | 609 | Ratios completos vía EDGAR (márgenes, ROE, PER, CAGR…) | Fuente SEC |
| `ratios_cnv` | 72 | Ratios desde CNV | |
| `ratios_ttm` | 56 | Ratios TTM recalculados (des-acumulados) | Construido en la depuración; caps de sanidad |
| `per_ttm` | 56 | PER TTM método IAMC | |

### Precios
| Tabla | Filas | Qué |
|---|--:|---|
| `precios` | 679 | cik, ticker, precio, market_cap, currency |
| `iamc_precios` | 71 | Cierre ARS + mcap de IAMC |

### Metadata / calendario / logs (medallion)
| Tabla | Filas | Qué |
|---|--:|---|
| `cnv_filings` | 18.910 | Presentaciones CNV (norma, periodicidad, fecha_cierre) |
| `cnv_documents` | 267.841 | Docs CNV (docid, url) |
| `fiscal_calendar` | 517 | Fin de ejercicio por cuit (`fy_end_month`) |
| `ingest_log` | 50 | Log de descargas CNV (url, http_status, sha256, bytes) |
| `descargas_log` | **0** | ⚠️ Esqueleto vacío del log de descargas (capa, estado, error, ts) — **a usar en el pipeline nuevo** |

### Externos (investing) — nuestros
| Tabla | Filas | Qué |
|---|--:|---|
| `ratios_externos` | 17 | Ratios headline investing (byma_only) |
| `eerr_externos` | 860 | EERR trimestral investing (20 empresas) |

### Diagnósticos (one-off)
| Tabla | Filas | Qué |
|---|--:|---|
| `diag_nic29` | 25 | Diagnóstico NIC-29 |
| `diag_per_operativo` | 10 | Diagnóstico PER operativo |

## Hallazgos de calidad ya conocidos (no re-descubrir)
1. **`facts` mezcla SEC + CNV** (cik numérico vs `BYMA-XXX`).
2. **Moneda por-fact:** 11/13 ADR argentinos reportan a SEC en **ARS** (solo YPF/Vista USD). Leer `unit`.
3. **`cnv_estados_v2` keying inconsistente:** byma_only por ticker, ADR por razón social.
4. **EDN/BPAT/DGCE** existen en V1 pero se cayeron de V2.
5. **`empresas.moneda`/`pais` no confiables.**
6. **`screener.MarketCapUSD` es ARS**, no USD.
7. **`cnv_estados_v2` corrupto en varios** (GCLA escalas 10³–10¹⁵, fecha 2024-11-08; A3/FIPL/BOLT_2/PATA_2).
8. Solo **3/20** byma_only muestreadas reconcilian limpio (DGCU2, METR, AGRO).
