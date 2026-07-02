# Screener financiero — Visión general del proyecto

> **Para el agente/dev que lee esto por primera vez.** Este documento es el mapa.
> Explica QUÉ es el proyecto, CÓMO están organizados los datos, y te deriva a los
> documentos por etapa (EDGAR, ADR, BYMA-only, pipeline CNV). Si vas a tocar código,
> leé primero esto y después la etapa que corresponda.

Fecha de última actualización: 2026-07 (post pipeline CNV completo del subset).

---

## 1. Objetivo

Construir una **base de datos y un screener de ratios financieros** para tres universos
de empresas:

1. **US (S&P 500)** — vía SEC EDGAR.
2. **ADR argentinos** — vía SEC EDGAR (formulario 20-F) y, en paralelo, CNV.
3. **Argentinas que cotizan solo en BYMA (only-BYMA)** — vía yfinance y CNV.

El producto final es un **snapshot estático de ratios comparables** entre las tres,
más series históricas para calcular crecimiento (CAGR) y calidad.

### Los 13 ratios objetivo
Definidos y validados en [`comparar_13_ratios.py`](../../scripts/tickets/cnv/scripts/comparar_13_ratios.py):

1. Precio (u$s) · 2. PER · 3. Máx 52 sem · 4. Dif Máx · 5. Mín 52 sem · 6. Dif Mín ·
7. Deuda/EBITDA · 8. EPS anual · 9. Crecimiento EPS 5y · 10. Margen Neto · 11. ROE ·
12. FCF/CE · 13. Payout

Más el set ampliado de ratios fundamentales (márgenes, ROA, ROCE, liquidez, rotación,
etc.) que calcula [`calcular_ratios_base.py`](../../scripts/tickets/sec_edgar/scripts/calcular_ratios_base.py).

---

## 2. Arquitectura de datos

Todo vive en **`data/screener.db`** (SQLite, ~728 MB — **NO se versiona**, ver §6).

### Principio central: conceptos canónicos
Cada fuente (EDGAR, yfinance, CNV) usa tags distintos, pero se mapean a un set de
**conceptos canónicos** (`NetIncome`, `Revenue`, `Equity`, `Assets`, `EBITDA`...). El
motor de ratios opera sobre los conceptos, **no** sobre los tags crudos → un solo motor
calcula US + ADR + BYMA sin cambiar.

### Tablas principales

| Tabla | Qué | Fuente | Clave |
|---|---|---|---|
| `empresas` | catálogo (cik, ticker, nombre, moneda, sector, grupo) | todas | `cik` |
| `facts` | ~4,6M hechos financieros (tag + concepto canónico) | EDGAR + yfinance | `cik` |
| `ratios` | ratios fundamentales calculados | EDGAR/yfinance | `cik` |
| `precios` | precio + valuación (PER, P/B, EV/EBITDA) con FX | yfinance | `cik` |
| `cnv_estados` | estados contables CNV (conceptos + ratios pre-calc CNV) | CNV aif2 | ver ⚠️ |
| `cnv_dividendos` | dividendos/hechos relevantes/actas | CNV aif2 | `guid` |
| `cnv_estados_suspect` | filings que violan identidad contable (excluir del screener) | derivada | `cik,period_end` |

### Convención de `cik` por grupo (IMPORTANTE)
- **EDGAR (US + ADR)**: `cik` = CIK numérico de SEC.
- **BYMA-only (yfinance)**: `cik` = `BYMA-{ticker}` (ej. `BYMA-ALUA`).
- **CNV — extracción vieja** (`extract_aif2_masivo.py`): `cik` = `BYMA-{ticker}`.
- **CNV — extracción nueva** (jobs, el subset): `cik` = **CUIT** y `ticker` = **nombre de empresa**.

> ⚠️ **DEUDA TÉCNICA ABIERTA:** las filas nuevas de CNV (job5) quedaron con `cik`=CUIT
> y `ticker`=nombre, distinto del resto de la base. **Antes de calcular ratios CNV hay
> que normalizar la clave** (mapear CUIT→ticker→cik canónico y deduplicar viejo/nuevo).
> Detalle en [ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md#deuda-técnica-clave).

---

## 3. Las etapas (documentos por fuente)

| Etapa | Documento | Estado |
|---|---|---|
| 1 · SEC EDGAR (US + ADR) | [ETAPA_1_EDGAR.md](ETAPA_1_EDGAR.md) | ✅ operativo |
| 2 · ADR argentinos | [ETAPA_2_ADR.md](ETAPA_2_ADR.md) | 🟡 EDGAR ok, cruce CNV pendiente |
| 3 · BYMA-only | [ETAPA_3_BYMA_ONLY.md](ETAPA_3_BYMA_ONLY.md) | 🟡 yfinance ok, CNV cargado sin normalizar |
| 4 · Pipeline CNV (jobs) | [ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md) | 🟡 extracción 100% del subset, ratios pendientes |

Documentos de apoyo ya existentes:
- [BITACORA_Y_DECISIONES.md](BITACORA_Y_DECISIONES.md) — decisiones históricas.
- [PIPELINE_CNV.md](PIPELINE_CNV.md) — diseño del pipeline CNV.
- [LISTA_56_CNV.md](LISTA_56_CNV.md) — las 56 BYMA-only.
- [jobs/README.md](../../scripts/tickets/cnv/jobs/README.md) — manual de ejecución de los jobs.
- [../calculos-financieros/](../calculos-financieros/) — guías de cálculo y de SEC EDGAR.

---

## 4. Estado global (qué está listo, qué falta)

### ✅ Listo
- Base EDGAR (US + ADR) con facts, ratios, precios.
- 56 BYMA-only cargadas desde yfinance (~160 tags c/u).
- Pipeline CNV completo: universo 555 descubierto, subset (70 empresas) extraído al
  100% (31.626 EEFF + 3.225 dividendos), 124 empresas con 28-33 períodos (~15 años).
- Validación de identidad contable (job7): 21 filings suspect detectados, 11 basura
  purgados, 10 preservados (bancos con PCGA distinto).

### 🟡 Falta (orden recomendado)
1. **Normalizar la clave de `cnv_estados`** (deuda técnica, §2). Bloquea lo demás.
2. **Capa de ratios CNV** (`calcular_ratios_cnv.py`): último período limpio por empresa.
3. **Ensamblar el screener**: merge EDGAR + yfinance + CNV, rellenar huecos (bancos →
   yfinance) y exportar el snapshot final (CSV comparable + los 13 ratios).
4. **Parser bank-aware** para las entidades financieras (plantilla CNV distinta).
5. **Extracción full-556** (hoy solo el subset) — el pipeline ya está listo para escalar.
6. **Parseo de texto de dividendos** (hechos relevantes / actas son texto libre).

---

## 5. Cómo está organizado el repo

```
scripts/tickets/
  sec_edgar/scripts/   # pipeline EDGAR (01_mapear_cik ... calcular_ratios_base, precios, flags)
  cnv/
    jobs/              # pipeline CNV ETL segmentado (job1..job7 + build_subset + README) ← lo nuevo
    scripts/           # scripts CNV varios (extracción, parsers, cruces, ratios)
    datos/             # CSVs (universo, whitelists, catálogos) — grandes van gitignore
docs/
  screener/            # este set de documentos
  calculos-financieros/# guías de cálculo y SEC EDGAR
data/
  screener.db          # la base (gitignore, 728MB)
  raw/                 # cache crudo (gitignore)
```

---

## 6. Qué se sube a GitHub y qué no

**Principio: solo procesado, nunca crudo.**

- ✅ **Suben**: scripts, documentación, CSVs chicos curados (universo, subset, catálogos,
  tabla maestra).
- ❌ **NO suben** (gitignore): HTML crudos (`html_descargados/`, `div_html/`, `ledesma.html`),
  la DB (728MB), cache `data/raw/`, logs (`data/*.txt`), y los CSVs grandes reproducibles
  (`guid_formtype.csv` 47M, `whitelist_*.csv`, `links*.csv`).

**La DB no va a GitHub** (728MB > límite). Se reconstruye corriendo los pipelines
(EDGAR → yfinance → jobs CNV). Cuando el screener final esté armado, se exporta un
**CSV compacto** con el snapshot de ratios como artefacto procesado versionable.
