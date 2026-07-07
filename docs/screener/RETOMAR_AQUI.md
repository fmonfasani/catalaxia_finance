# RETOMAR ACÁ — punto de entrada para continuar el proyecto

> **Si sos un agente/dev retomando esto en otra máquina o IDE: leé este archivo primero.**
> Te pone al día con el estado, lo que se logró, las limitaciones y el próximo paso.

Última actualización: 2026-07 (post screener **v2**).

---

## 0. Cómo levantar el proyecto en otra compu

1. `git clone https://github.com/fmonfasani/catalaxia_finance.git`
2. ⚠️ **`data/screener.db` (~754MB) NO está en git** (supera el límite de GitHub). Es donde
   vive TODA la data (cnv_estados_v2, screener, etc.). **Copiala a mano** (USB/drive/nube)
   y ponela en `data/`. Sin la DB, arrancás de cero.
3. Leé, en orden: este archivo → [00_VISION_GENERAL.md](00_VISION_GENERAL.md) → la etapa
   que vayas a tocar.
4. La memoria local del agente (`.claude/`) **no viaja** — todo el contexto está en estos docs.

---

## 1. Qué es el proyecto

Screener de **13 ratios financieros** comparables para: **US (S&P 500)** y **ADR** (vía SEC
EDGAR) y **argentinas BYMA-only** (vía yfinance + CNV). Precios de yfinance. Los 13 ratios y
su origen: [00_VISION_GENERAL.md](00_VISION_GENERAL.md) §1.

---

## 2. Estado actual (honesto)

### ✅ Screener v2 argentino — LISTO y validado (72 empresas: 56 BYMA-only + ADR)
Salida: **`data/screener_export.csv`** (72 filas × 26 columnas). Fundamentales desde CNV,
precios desde yfinance. Cobertura medida:

| Ratio | Cob. | Ratio | Cob. |
|---|---|---|---|
| ROE / ROA | 90% | FCF/CE | 96% |
| Margen | 89% | EPS | 92% |
| P/B | 82% | P/S | 79% |
| PER | 53% | Payout | 47% (34/72) |
| CAGR real | 64% | Precio | 96% |

**Los tres logros del v2** (vs v1):
- **CAGR REAL** deflactado por IPC INDEC (`data/ipc_nacional.csv`, base dic-2016). Los CAGR
  **negativos son correctos**: las ganancias nominales no le ganaron a la inflación → caída
  real (TXAR −45% real vs +10% nominal; BHIP +0.9% real es la que preservó valor).
- **Staleness muerta** (16→1): el bug era la **unidad del template CNV** (MILES vs Millones
  de $), no un layout. `factor_unidad()` lo normaliza. Último período usable en todas.
- **Payout desde CNV** (cash-basis, ventana 12m alineada al cierre fiscal).

### 🟡 US / ADR (EDGAR) — existe, sin unificar
Base EDGAR (`facts`, `ratios`, `precios`) construida en etapas previas. **No está unificada**
con el screener argentino en una sola salida.

---

## 3. Limitaciones conocidas (documentadas en el README del CSV)
- **Payout (34/72)** es lo más débil: cash-basis aproximado, **filtra** dividendos de
  reservas (>200% → se descartan, ej. TXAR pagó 5× ganancias). Puede tener desfasaje de
  timing cross-año. No asumir 0 donde está NULL.
- **CAGR (64%)**: real pero limitado a empresas con ≥5 años de serie.
- **`no_significativo`** (flag): valuación/Margen/ROE nulos cuando el denominador ≈ 0
  (GCLA holding Revenue≈0 → Margen 584% flageado; ROSE equity<0 → ROE flageado).
- **1 empresa stale** (PATA_2, 2023) + placeholders `_ADR_xxxx` sin CNV (solo precio).

---

## 4. Cómo está armado el ETL (para reproducir / extender)
```
Extracción CNV:  jobs/job5_v2_extract_eeff.py  (fix unidad + GUARDA HTML crudo + claves canónicas)
                 jobs/job6_v2_reparse_div.py   (dividendos form 339, re-parse local)
Screener:        screener/s0_normalizar_cnv → s2_ratios_cnv (CAGR IPC + payout 12m)
                 → s3_precios → s4_ensamblar (flags) → s5_exportar
Deflación CAGR:  data/ipc_nacional.csv  (IPC INDEC, 114 meses)
```
**Lección clave:** el HTML crudo se guarda (`eeff/eeff_html/`) → cualquier re-parse futuro es
LOCAL (segundos), sin re-bajar. Y solo ~2.500 de los 31.626 GUIDs son planilla de códigos
(8%); el resto son anexos → filtrar con la mini-whitelist de `accn` de `cnv_estados`.

---

## 5. Próximos pasos (en orden)
1. **Shipear el v2** (si no se hizo): commit de screener_export.csv + README + s2/s4 +
   job5_v2/job6_v2 + ipc_nacional.csv.
2. **Escalar a las 556**: mismo pipeline, correr job5_v2 sobre toda la whitelist filtrada a
   los GUIDs de códigos (atajo mini-whitelist → ~horas, no días).
3. **Unificar** el screener argentino con la base US/ADR (EDGAR) en una sola salida.
4. (Opcional) Parser bank-aware si algún banco sigue sin parsear bien.

---

## 6. Mapa de documentos
- [00_VISION_GENERAL.md](00_VISION_GENERAL.md) — arquitectura, 13 ratios, tablas.
- [PLAN_ETL_SCREENER_CNV.md](PLAN_ETL_SCREENER_CNV.md) — el ETL del screener.
- [PLAN_V2_DATOS_CONFIABLES.md](PLAN_V2_DATOS_CONFIABLES.md) — la re-extracción robusta v2.
- [ETAPA_1_EDGAR.md](ETAPA_1_EDGAR.md) · [ETAPA_2_ADR.md](ETAPA_2_ADR.md) · [ETAPA_3_BYMA_ONLY.md](ETAPA_3_BYMA_ONLY.md) · [ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md)
- `data/screener_export_README.md` — guía y limitaciones del CSV final.
