# CONTRATO_TECNICO_EXTRACCION.md

> Ejecución de [PROMPT_CONTRATO_EXTRACCION.md](PROMPT_CONTRATO_EXTRACCION.md).
> Fecha: 2026-08-22 · Estado: **APLICADO — GO total** (P0 cerradas; ver §4 y §7).
> Analizado: EXTRACTION_SPECIFICATION · PROVENANCE_SPECIFICATION · DATA_CONTRACT_EXTRACTION ·
> EXTRACTION_CHECKLIST · DO_NOT_REPEAT · EXTRACTION_KNOWLEDGE_BASE ·
> PIPELINE_VALIDATION_SPECIFICATION (ubicado en `data/`, no en raíz) · scripts s0–s9 y b0–b9.

---

## 0. Veredicto (resumen)

**GO TOTAL desde 2026-08-22.** Las decisiones D1–D6 quedaron RESUELTAS (§6, registro en
FASE2_PLAN_CONSOLIDACION.md §7) y las condiciones P0 del §4 fueron ejecutadas la misma
fecha: precios refrescados al 2026-08-21 (G1), invalidación de cache por fecha con
`--force-refresh` y fin del fallback silencioso (G2), run_manifest + huella de descargas
EDGAR (G4). La próxima corrida completa puede producir foto certificada; queda deuda P1
no bloqueante (§4, destacando G9 namespace de precios y capa única de fetching).

---

## 1. Contrato final — 17 determinaciones

### 1.1 Universo objetivo

| Universo | Alcance | Estado |
|---|---|---|
| **Primario**: 73 entidades argentinas (56 BYMA-only + 17 ADR) | Producto de 13 ratios | Certificado audit v3 (`entidades_audit_v3.parquet`) |
| Secundario: S&P 500 (dataset M1 heredado, 571 tickers en screener v5) | Fuera de este contrato salvo D5 | Separado |
| Excluidos | CEDEARs sin ADR (sin fundamental propio), ETFs, bonos | — |

### 1.2 Empresas objetivo

Las 73 entity_keys del catálogo audit v3 (fuente única de verdad; no se duplica la lista
acá). Todo job nuevo debe leer el catálogo, nunca una lista hardcodeada.

### 1.3 Identificadores canónicos

- `entity_key`: CUIT (11 dígitos) para BYMA-only · CIK (10 dígitos) para ADR/US.
- Prefijos `BYMA-*`: clasificación interna SIN identidad legal (prohibido usarlos como clave).
- Tickers `.BA` (locale AR) y US, mapeados vía `catalogo_tickers.csv`.
- Prohibido resolver identidad por nombre.

### 1.4 Fuentes por tipo de dato

| Tipo | Fuente primaria (certifica) | Fuente secundaria (jamás parchea) |
|---|---|---|
| Precios BYMA | yfinance `.BA` (ARS) | IAMC (cierre oficial, benchmark) |
| MEP (CCL proxy pareo) | yfinance `GCAL` vs `YPF` (.BA) | — |
| Precios ADR/US | yfinance US (USD nativo) | — |
| Fundamentales BYMA | CNV form 339 (`eeff_html/{guid}.html`) | SEC EDGAR cuando exista |
| Fundamentales ADR/US | SEC EDGAR `companyfacts` XBRL | CNV |
| IPC (deflactación) | INDEC serie mensual | — |
| Dividendos | CNV 339 (BYMA) | yfinance `dividends` (ADR/US) |
| Benchmark externo | investing.com manual / auto-reporte CNV | Solo contraste, nunca carga |

### 1.5 Datos necesarios e historial requerido

- Precios y rangos 52s: ≥ 1 año diario.
- Métricas TTM: últimos 4 trimestres consecutivos del calendario fiscal propio.
- EPS anual / CAGR 5 años: ≥ 6 cierres fiscales anuales, extremos > 0.
- ROE 5 años: entre 3 y 5 cierres anuales, equity > 0.
- Balance: último FY snapshot. Dividendos: ventana 12 meses.
- **Historial mínimo global: 5–6 años** (CNV cubre ~15 años en ~124 empresas;
  raw cache EDGAR arrancó con 6 años, ampliable).

### 1.6 Fecha de corte

- Fundamentales: último FY completo reportado a CNV (por empresa).
- Precios: `as_of` de la corrida. ✅ Refresco ejecutado 2026-08-22: serie diaria
  (+18.085 ruedas vía `s3b_precios_historicos.py`) y foto reconstruida
  (`s3c_refrescar_precios.py`): 608 tickers al cierre **2026-08-21**. Excepciones conocidas:
  RAGH (2026-08-14, parcial), DGCE/BOLT_2/PATA_2 (sin datos en yfinance),
  ~57 filas legacy del S&P M1 sin serie.
- IPC: última publicación INDEC disponible al `as_of`.
- Toda foto declara `cutoff_date` explícito + staleness por métrica (días).

### 1.7 Periodicidad

Precios diario · fundamentales trimestral (`--quarterly`) + anual derivado · IPC mensual · dividendos por evento.

### 1.8 Moneda

Por-fact (`currency` ARS/USD según reporte origen). Producto final: **precios en USD**
(AR convertido a MEP pareado; ADR/US nativo). Fundamentales BYMA en ARS corrientes con
flags NIC-29; ADR/US en USD nominal.

### 1.9 Unidad

`factor_unidad` por statement + flags NIC-29 (`is_nic29_adjusted`). Escalas validadas por
b6 (`ESCALA_ALTA_xN` bloquea). Prohibido asumir unidad implícita.

### 1.10 Calendario fiscal

Calendario propio por empresa (`fy_end_month`; 8 empresas no-calendario documentadas en KB).
TTM = ventana de 4 trimestres propios. Comparables siempre contra mismo `fy_end`.

### 1.11 Política de datos faltantes

NULL + motivo codificado (`sin_datos_cnv` / `sin_edgar` / `cf_no_disponible` /
`eps_no_positivo` / …). Prohibido inventar o interpolar fundamentales. Fallbacks permitidos
solo si están declarados en la matriz (§2) y quedan flaggeados (ej. OpInc→EPS `_fallback`).

### 1.12 Política de restatements

Conservar TODAS las vintages (`efectos_reexpresion.parquet`, 12 casos medidos). Para cálculo
se usa la reexpresión MÁS RECIENTE de cada período. Gap: `es_restatement` aún no propagado (§4 P1).

### 1.13 Política de fuentes contradictorias

La primaria certifica; la secundaria jamás parchea valores. Discrepancia sobre tolerancia →
arbitraje 3-vías (CNV vs SEC vs manual), conservando ambos valores. Tolerancias vigentes:
PER_2PATH < 10% (unificación pendiente, D3) · ESCALA_ALTA_xN bloquea.

### 1.14 Provenance requerida

Nivel OBLIGATORIO de [PROVENANCE_SPECIFICATION.md](PROVENANCE_SPECIFICATION.md) §3:
source_system · doc_id/guid/accession · fecha extracción · factor_unidad · flags NIC-29 ·
run_id · versión de código. **Sin provenance completa el dato no es certificable** (queda WARNING como mínimo).

### 1.15 RAW requerido

- `eeff_html/{guid}.html` intacto (CNV) · respuestas crudas API bajo `data/raw/`
  (companyfacts JSON, JSON de yahoo) · prohibido editar RAW post-carga.
- **Propuesto (hoy inexistente)**: `download_log.jsonl` append-only por request
  (timestamp, URL, status, bytes, sha256).

### 1.16 Checkpoints necesarios

| Momento | Artefacto | Estado |
|---|---|---|
| Pre-run | `snapshot_byma.json` SHA256 | ✅ existe |
| Por corrida | run_id + log resume-safe por job | ✅ existe |
| Por corrida | `run_manifest` (versión código/git SHA + hash de inputs) | ❌ propuesto |
| Intermedio | tablas idempotentes normalizadas/fundamentales/métricas (rerun seguro) | ✅ parcial |
| Post-run | foto certificado + checksums parquet | ✅ existe |

---

## 2. Matriz de inputs — 13 ratios

**Tabla A — inputs y fuentes**

| # | Ratio | Inputs | Fuente primaria | Secundaria | Período | Unidad / Moneda |
|---|---|---|---|---|---|---|
| 1 | Precio USD | last_price `.BA`; MEP GCAL/YPF; o precio ADR | yfinance | IAMC | cierre del día | USD (ARS→MEP) / nativo |
| 2 | PER | mcap_ars + NI_ttm (BYMA) · price + EPS_ttm (US/ADR) | CNV · SEC | investing manual | TTM | x · — |
| 3 | Máx 52s | year_high | yfinance | sin benchmark ext. | 252 días | USD |
| 4 | Dif vs máx 52s | precio + high | derivado de 1+3 | — | — | % |
| 5 | Mín 52s | year_low | yfinance | sin benchmark ext. | 252 días | USD |
| 6 | Dif vs mín 52s | precio + low | derivado de 1+5 | — | — | % |
| 7 | Deuda/EBITDA | deuda_total snapshot; EBITDA_ttm = OpInc_ttm + D&A_ttm | CNV · SEC | investing manual | TTM + snap | x |
| 8 | EPS anual | NI_fy; shares_dil promedio FY | CNV (BYMA) · SEC (ADR) | EDGAR EPS reportado | último FY | ARS/USD por acción |
| 9 | Crec. EPS 5 años | serie ≥6 EPS anuales + IPC INDEC | CNV/SEC + INDEC | S&P nominal USD | 5 años (CAGR real) | % |
| 10 | Margen Neto | NI_ttm; Rev_ttm (mismo perímetro) | CNV · SEC | investing manual | TTM | % |
| 11 | ROE 5 años | NI_fy; equity_fy (3–5 cierres) | CNV · SEC | cnv_roe self-report + investing | 3–5 FY | % |
| 12 | FCF/CE | CFO_ttm + CFI_ttm; equity + deuda_LP (v1) o caja neta (v2) | CNV · SEC | investing manual | TTM + snap | x |
| 13 | Payout | dividendos 12m; NI_ttm | CNV 339 (BYMA) · yfinance div (ADR) | yfinance trailingDiv | 12 meses | % |

**Tabla B — fórmula, validación y benchmark**

| # | Fórmula | Validación (gate) | Benchmark externo |
|---|---|---|---|
| 1 | AR: `precio_ars/mep` · ADR: directo | dif_check pareo < 0,5%; rango > 0 | IAMC cierre oficial |
| 2 | `mcap/NI_ttm` · `price/EPS_ttm` | PER_2PATH dos niveles (D3): ≤8% PASS · 8–10% WARNING · >10% arbitraje; NULL si EPS ≤ 0 | investing + AUDITORIA_investing_vs_certificado |
| 3 | `max(high)` | s9b: H ≥ L ≥ 0 | [no determinado — ver §3] |
| 4 | `(p − high)/high` | ∈ [−100%, 0] | ídem |
| 5 | `min(low)` | low ≤ p | ídem |
| 6 | `(p − low)/low` | ≥ 0 | ídem |
| 7 | `deuda_total/EBITDA_ttm`, EBITDA = OpInc+D&A receta única **D2** (fallback AmortIntangibles flag) | ESCALA_ALTA_xN; flag NIC-29 | investing manual |
| 8 | `NI_fy/shares_dil_prom` (fallback OpInc flag) | `_ADR_0580` abierto; flag fallback | EarningsPerShareDiluted EDGAR vs calculado |
| 9 | `CAGR(EPS_deflactada)` extremos > 0; ≥ 6 puntos; flag NOMINAL_sin_deflactar | cobertura ≥ 6 | S&P nominal USD (dif. metodológica declarada, §3) |
| 10 | `NI_ttm/Rev_ttm` | IDENTIDAD_balance; MARGEN_ALTA_CNV (>100% → revisar) | investing manual |
| 11 | `mean(NI_fy/equity_fy)` con equity > 0 | gate_autoreporte (umbral 8000009); \|ROE\| ≤ 5x | cnv_roe self-report + investing |
| 12 | v1 `(CFO+CFI)/(Equity+Deuda_LP)` (default) · v2 caja neta, validar vs benchmark | INVJ/DOME/VALO sin cashflow → NULL flag | investing manual |
| 13 | `div_12m/NI_ttm` | > 2× → descartar (reservas); bancarios D4 | yfinance trailingDiv vs CNV |

---

## 3. Diferencias metodológicas entre fuentes (explícitas)

No asumir equivalencia TIKR = SEC = CNV = yfinance:

1. **CNV/TIKR**: CNV publica GAAP local crudo por formulario; TIKR estandariza y a veces
   normaliza non-GAAP. Unidades y clasificaciones difieren.
2. **SEC companyfacts**: valores reportados GAAP puros, sin ajustes editoriales.
3. **TTM**: yfinance usa TTM rodante sobre trimestres calendario; Catalaxia usa ventana
   de 4 trimestres del calendario fiscal propio (estrategia C). Pueden diferir legítimamente.
4. **NIC-29**: BYMA reporta en moneda de inflación (reexpresión) mientras los ADR/US van en
   nominal → series mixtas; comparables solo dentro del mismo régimen.
5. **Shares**: weighted diluted (SEC/CNV) vs outstanding puntual (yfinance market cap).
6. **52s**: no existe benchmark externo determinado para máx/mín 52 semanas AR (IAMC da
   cierre, no intradía histórico) → quedan certificados solo contra consistencia interna (s9b).

---

## 4. Gaps

**P0 — TODAS CERRADAS el 2026-08-22:**
- ✅ ~~G1~~ Precios refrescados: `s3b_precios_historicos.py` (+18.085 ruedas) +
  `s3c_refrescar_precios.py` → foto al cierre 2026-08-21 (608 tickers). Hallazgo durante
  G1: ADRs legacy stale por namespace dual → parche de apareo en s3c (ver G9).
- ✅ ~~G2~~ EXT-019 consolidado: `construir_base.py` invalida POR FECHA vía `_caducidad`
  y hace BLOCK si el módulo falta (fin del fallback silencioso a cache eterno); flag
  `--force-refresh` propagado a `run_all.py`. Semántica única de skip/refetch;
  `run_update.py` conserva su incremental por lastFiled.
- ✅ ~~G3~~ D2–D6 aprobadas (§6).
- ✅ ~~G4~~ `_run_manifest.py` → `data/logs/runs/<run_id>.manifest.json` (git sha, args,
  resultado por stage, hash del snapshot baseline pre-run) + huella EDGAR en tabla
  `ingesta_log`. Pendiente P2: wirear `ingesta_log` en jobs CNV y descargas yfinance.

**P1 (no bloquean extracción):**
- G5 `es_restatement` y `accn`/`decimals` sin propagar a tablas finales.
- G6 Filings corruptos `_ADR_0580` / `_ADR_2807` (re-descarga pendiente).
- G7 Motor único de validación: la especificación existe (`data/PIPELINE_VALIDATION_SPECIFICATION.md`)
  pero `validar_suite.py` vive solo dentro de auditoría v3; port está planificado en O3.
- G8 Benchmark externo para máx/mín 52s indefinido (aceptado como limitación declarada).
- **G9 (nuevo, 2026-08-22)** Namespace dual de precios: `precios_diarios` guarda ticker
  canónico del screener (`YPFD`) mientras filas legacy de `precios` guardan símbolo
  yfinance (`YPF`). Mitigado con apareo `cuit ↔ ADR_YF` en s3c; consolidar convención
  única al unificar entry-points de precios (O3).

---

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Doble entry-point de cache genera dataset divergente | Alto | G2 antes de escalar descargas |
| Certificar foto con precios viejos | Alto | G1 obligatorio pre-foto |
| Mezclar NIC-29 con nominal en comparables | Medio | flags + §3.4 |
| Fallback silencioso OpInc→EPS | Medio | flags obligatorios + matriz §2 |
| Payout bancario sin convención | Bajo-Medio | ✅ cerrada: D4 sin excepción (2026-08-22) |

---

## 6. Decisiones — RESUELTAS (2026-08-22)

| ID | Decisión | Resolución aprobada |
|---|---|---|
| D1 | Base canónica screener | A: `screener` M1 + certificación b7 |
| D2 | Receta única EBITDA | `OpInc_ttm + D&A_ttm`; fallback `AmortIntangibles` flaggeado |
| D3 | Tolerancia PER_2PATH | Dos niveles: ≤8% PASS · 8–10% WARNING · >10% arbitraje 3-vías |
| D4 | Payout bancos | Sin excepción (`div_12m/NI_ttm`; NULL+motivo si falta pata; >2× descarte) |
| D5 | S&P 500 | Separado de este contrato; reintegro post O4/O5 |
| D6 | Cutoff foto | Timestamp único por corrida + staleness por métrica |

Registro canónico: [FASE2_PLAN_CONSOLIDACION.md](FASE2_PLAN_CONSOLIDACION.md) §7.

---

## 7. GO / NO-GO para comenzar extracción

| Actividad | Veredicto |
|---|---|
| Extracción incremental (jobs resume-safe, guards activos) | ✅ **GO** |
| Nueva foto certificada al último dato | ✅ **GO** desde 2026-08-22 (G1/G2/G4 ejecutados; D2–D6 resueltas) |

Siguiente corrida sugerida: `python run_all.py` (extract incremental por fecha →
transform → assemble → export), que ahora deja manifiesto en `data/logs/runs/`.
Deuda P1 (G9 namespace de precios, capa única de fetching, es_restatement/accn,
filings _ADR_0580/2807) se aborda en O2–O3 según FASE2_PLAN; no bloquea certificar.
