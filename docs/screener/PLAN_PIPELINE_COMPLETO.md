# Plan — Pipeline completo, replicable y actualizable

> Objetivo: **base lista con 572 empresas** (500 S&P + 16 ADR + 56 BYMA-only), todos los
> ratios, pipeline **replicable desde cero** y **actualizable con jobs periódicos**.
> Estado medido: los ratios de las 572 YA existen; falta unificar + automatizar. Ver
> [ESTADO_PIPELINE.md](ESTADO_PIPELINE.md).

---

## 1. Universos, fuentes y cadencia

| Universo | # | Fundamentales | Precios | Actualización |
|---|---|---|---|---|
| S&P 500 | 500 | SEC EDGAR (10-K/10-Q, XBRL) | yfinance | trimestral (filings) |
| ADR argentinos | 16 | SEC EDGAR (20-F) + adr_ratios (F-6) | yfinance | anual (20-F) |
| BYMA-only | 56 | CNV (NIC 29) + yfinance | yfinance | trimestral (filings) |
| — común — | | IPC INDEC (deflactor CAGR) | | mensual |

---

## 2. Arquitectura (capas E-T-L)

```
EXTRACT            TRANSFORM                     ASSEMBLE
EDGAR  ─┐          calcular_ratios_base ─┐
CNV    ─┼─ facts ─ ratios_cnv (IPC)     ─┼─ screener (572) ─ export CSV
yfin   ─┘          precios_y_valuacion  ─┘   + provenance (fuente_fund)
```
Clave: **conceptos canónicos** → un solo motor de ratios para todas las fuentes.

---

## 3. Estado actual vs objetivo (el gap real)

| Componente | Estado |
|---|---|
| EDGAR facts + ratios (499 S&P + 16 ADR) | ✅ **ya calculado** (`ratios`: 553 filas) |
| CNV + yfinance (56 BYMA) | ✅ en `screener` |
| precios (625) | ✅ |
| **Screener UNIFICADO** | 🔴 solo tiene las 72 AR — **falta ensamblar las 499 S&P** |
| Jobs periódicos / scheduling | 🔴 no existen |

**Conclusión: ~80% hecho.** El trabajo real es (a) unificar y (b) automatizar.

---

## 4. Los pipelines por fuente (ya existen — replicables)

### 4.1 EDGAR (US + ADR) — `sec_edgar/scripts/`
`01_mapear_cik → 02_descargar_datos → calcular_ratios_base → precios_y_valuacion → flags_calidad`
+ `sec_adr_ratios` (ratios ADR oficiales del F-6). **Estado: ✅**

### 4.2 CNV (BYMA-only) — `cnv/jobs/` + `screener/`
`job1..job4 (discovery) → job5_v2 (extract, unidad+HTML) → job6_v2 (div) → job7 (validar)`
→ `s0 (clave) → s2 (ratios+IPC)`. **Estado: ✅ subset 72.**

### 4.3 yfinance — `cargar_byma_yfinance.py` + `precios_y_valuacion.py`
Precios de todos + fundamentales BYMA. **Estado: ✅**

### 4.4 Auxiliares
IPC INDEC (`data/ipc_nacional.csv`, mensual) · adr_ratios (`sec_adr_ratios.py`, F-6).

---

## 5. Lo que FALTA construir

### 5.1 `s7_unificar.py` — ensamblado de las 3 universos (el gap principal)
Inserta en `screener` las **499 S&P + 16 ADR** desde la tabla `ratios` (EDGAR), junto a
las 56 BYMA (ya de CNV). Reusa el mapeo de columnas ya probado en el cableo ADR:
`ratios.roe→ROE, .per→PER, .p_book→PriceBook, .eps_anual→EPS, ...`, con `fuente_fund`,
`grupo` y `sector` (de `sector_gics`). Idempotente.
→ Resultado: `screener` con **572 empresas**.

### 5.2 Completar ratios (calidad)
- **`payout_status`** (calculado / no_paga / falta_dato).
- **EV/EBITDA + margen operativo** (mejor termómetro que PER neto, sobre todo AR).

### 5.3 Jobs de actualización periódica (ver §6)

---

## 6. Actualización periódica (jobs programados)

| Job | Frecuencia | Qué hace | Incremental |
|---|---|---|---|
| `upd_precios` | **diario** | yfinance: precio, máx/mín 52s, market cap | siempre (barato) |
| `upd_ipc` | **mensual** | bajar IPC INDEC nuevo (datos.gob.ar) | append |
| `upd_edgar` | **trimestral** | re-fetch companyfacts de los que tienen filing nuevo | sí (por `lastFiled`) |
| `upd_cnv` | **trimestral** | job5_v2 de GUIDs nuevos (resume-safe) | sí (done log) |
| `upd_ratios` | tras edgar/cnv | recalcular ratios + IPC | recompute |
| `upd_adr_ratios` | **anual** | sec_adr_ratios (nuevo 20-F) | recompute |
| `rebuild_screener` | tras cualquier upd | s0→s2→s3→s4→s6→s7→s5 | reconstruye |

**Scheduling** (están en Windows): **Task Scheduler** llamando a `run_update.py --daily` /
`--quarterly`. (Alternativa: una VM/servidor con cron.) La DB queda local (754MB, no va a git).

**Incremental de EDGAR**: SEC expone `lastFiled` por CIK → solo re-bajar los que cambiaron.
**Incremental de CNV**: los jobs ya son resume-safe (done log + HTML guardado).

---

## 7. Reproducibilidad (desde cero)

`run_all.py` — orquesta TODO end-to-end:
```
1. EXTRACT:  edgar (cik+facts) · cnv (jobs) · yfinance (precios+byma) · ipc · adr_ratios
2. TRANSFORM: calcular_ratios_base · ratios_cnv (IPC) · precios_y_valuacion
3. ASSEMBLE:  s0→s2→s3→s4→s6→s7→s5
4. EXPORT:    screener_export.csv
```
Cada stage idempotente. Corriendo `run_all.py` en una máquina limpia (con `requirements.txt`)
reconstruye la base entera. (La descarga cruda de EDGAR/CNV es la parte lenta; con cache/incremental
las corridas siguientes son rápidas.)

---

## 8. Plan de ejecución (fases, en orden)

| Fase | Qué | Esfuerzo |
|---|---|---|
| **1** | **`s7_unificar.py`** → screener con 572 (el gap principal; los ratios ya están) | bajo — reusa mapeo ADR |
| **2** | `payout_status` + EV/EBITDA (completar ratios) | medio |
| **3** | `run_update.py` (jobs diario/trimestral/anual) + `run_all.py` (from-scratch) | medio |
| **4** | Scheduling (Task Scheduler) + validación + export productivo | bajo |
| **5** | (opcional) sumar ADR-BR/LATAM (38 más ya en `ratios`), ratios de bancos, mina 556 | — |

---

## 9. Entregable final
- **`data/screener.db`** — 572 empresas, todos los ratios, con `fuente_fund` y `sector`.
- **`data/screener_export.csv`** — el screener comparable (versionable).
- **Jobs programados** — actualización diaria (precios) / trimestral (fundamentales).
- **`run_all.py`** — reconstrucción completa desde cero.

## Nota
Empezar por la **Fase 1 (s7_unificar)** rinde muchísimo: en una corrida tenés las 572 en el
screener, porque el 80% (los ratios) ya está calculado. El resto (jobs) es automatización
sobre lo que ya funciona.
