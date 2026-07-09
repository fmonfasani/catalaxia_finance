# Estado del pipeline ETL — de punta a punta

> Repaso completo del proceso: las 3 fuentes, sus pipelines, el ETL del screener, el estado
> real (cobertura, flags), lo resuelto y lo pendiente. Números medidos de la DB (2026-07).

Objetivo: **screener de 13 ratios** para argentinas (56 BYMA-only + 16 ADR), fundamentales
de CNV/EDGAR, precios de yfinance. Ver [00_VISION_GENERAL.md](00_VISION_GENERAL.md).

---

## 1. Las 3 fuentes y sus pipelines

### A. CNV → para las BYMA-only (`scripts/tickets/cnv/`)
| Etapa | Script | Estado |
|---|---|---|
| Discovery | jobs/job1..job4 + build_subset | ✅ universo 555, subset 72 |
| Extracción EEFF | jobs/job5 → **job5_v2** | ✅ v2: unidad MILES/Millones fija + guarda HTML crudo + claves canónicas |
| Dividendos | jobs/job6 → **job6_v2** | 🟡 form 339 parseado (parcial) |
| Validación | jobs/job7 | ✅ identidad contable → `cnv_estados_suspect` |
| Deflación CAGR | data/ipc_nacional.csv (IPC INDEC) | ✅ |

### B. EDGAR → para US + ADR (`scripts/tickets/sec_edgar/`)
| Etapa | Script | Estado |
|---|---|---|
| CIK + facts | 01_mapear_cik, 02_descargar | ✅ 553 empresas con facts |
| Ratios | calcular_ratios_base, precios_y_valuacion | ✅ ratios EDGAR (incl. ADR argentinos) |
| **Ratios ADR oficiales** | **sec_adr_ratios.py** | ✅ **13/13** ratios ADR del 20-F/F-6 (con URL auditable) |

### C. yfinance → precios + fundamentales BYMA (`cargar_byma_yfinance.py`)
- ✅ 56 BYMA-only (~160 tags), precios de todos.

---

## 2. El ETL del screener (`scripts/tickets/screener/`)
Orden: **s0 → s2 → s3 → s4 → s6 → s5** (orquestado por `run_screener.py`).

| Fase | Qué hace | Estado |
|---|---|---|
| s0 | normalizar clave CNV (cuit↔ticker) | ✅ |
| s2 | ratios CNV: CAGR deflactado IPC + payout 12m | ✅ (gap ROE lo tapa s6) |
| s3 | precios yfinance + FX | ✅ (ADR con precio USD — ver pendiente) |
| s4 | ensamblar los 13 ratios + flags no_significativo | ✅ |
| **s6** | **ajustes reproducibles**: tickers ADR reales, flag bancos + N/A, relleno ROE, sector | ✅ (consolidado, no se pierde en re-run) |
| s5 | validación + export `screener_export.csv` | ✅ |

---

## 3. Estado actual (números medidos)

**72 empresas** = 56 byma_only + 16 adr.

**Cobertura por ratio:**
| Ratio | Cob. | Ratio | Cob. |
|---|---|---|---|
| ROE / ROA | **100%** | FCF/CE | 86% |
| EPS | 92% | Margen | 81% |
| Precio | 96% | D/EBITDA | 67% |
| CAGR real | 64% | P/B | 62% |
| P/S | 57% | **PER** | **46%** ⚠️ |
| Payout | 47% ⚠️ | | |

**Flags:** `es_financiera`=8 (bancos) · `no_significativo`=14 · `dato_desactualizado`=6 · `cnv_fallback`=0.

**Sectores:** Otros 24 · Energía 12 · Consumo 10 · Financiero 8 · RealEstate/Agro 7 · Materiales 6 · Infra 3 · Telecom 2.

**Payout:** 33 yfinance · 1 CNV · 38 NULL (de los 38: **26 "no paga" confirmado** + 12 "falta dato").

---

## 4. Lo RESUELTO (el arco del trabajo)
1. **v1** → screener con staleness, CAGR nominal, payout parcial, PER roto.
2. **v2 (datos confiables)**: unidad MILES/Millones (mató staleness 16→1) · CAGR real (IPC) ·
   payout desde CNV (alineado por año) · PER per-share · clave canónica.
3. **Limpieza**: `CNV_*` descartado (parser de ratios mal-asociado) · **16 ADR flagship con
   ticker real** (eran `_ADR_`) · bancos flageados + ratios industriales N/A · sector ·
   **ratios ADR oficiales de EDGAR (13/13)** · todo consolidado en s6.

---

## 5. Lo ABIERTO (flags de estado — pendientes)

### 🔴 El grande: valuación de los ADR (PER/P-B/P-S)
El screener todavía calcula el PER de los ADR con **precio USD del ADR sin el ratio** →
inflado (YPF 44, Pampa 335). **Ya está la solución, falta cablearla:**
- **Usar los ratios EDGAR** de los ADR (oficiales, 20-F: Galicia PER 8.8, Pampa 6.9…), o
- convertir con el **precio `.BA`** (por acción, ARS) + el **ratio ADR oficial** (ya lo tenemos).
- El PER neto en Argentina está distorsionado por FX/RECPAM → **EV/EBITDA** es mejor termómetro.

### 🟡 Otros
- **Payout**: implementar `payout_status` (calculado / no_paga / falta_dato) → 83% con respuesta.
- **Bancos**: ratios propios (eficiencia, NIM, capital) pendientes (necesita parser bank-aware).
- **Shares/CAGR**: consistencia EPS/NI (40/72).
- **Mina 556** + **unificación EDGAR** (roadmap).

---

## 6. Datos / artefactos clave
- `data/screener.db` (754MB, **NO en git** — copiar a mano).
- `data/screener_export.csv` + `_README.md` (el entregable).
- `data/ipc_nacional.csv` (deflactor CAGR).
- `scripts/tickets/cnv/datos/`: adr_ratios.csv, adr_tickers.csv, empresas_subset.csv.
- Docs: [RETOMAR_AQUI.md](RETOMAR_AQUI.md) · [PROBLEMAS_ACTUALES.md](PROBLEMAS_ACTUALES.md) ·
  [PLAN_V2_DATOS_CONFIABLES.md](PLAN_V2_DATOS_CONFIABLES.md).

## 7. Próximo paso recomendado
**Cablear los ADR con dato oficial** (ratios EDGAR + ratio ADR) → resuelve el PER flagship
de una, en serio. Después: payout_status, y luego expansión 556.
