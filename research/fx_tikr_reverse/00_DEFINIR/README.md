# FX RESEARCH — TIKR REVERSE ENGINEERING · FASE DEFINIR

Estado: DEFINIR (ciclo DEFINIR → IMPLEMENTAR → VERIFICAR → CERTIFICAR).
Fecha: 2026-09-15. No se modificó producción. Directorio aislado: `research/fx_tikr_reverse/`.

## 1. HOY vs OBJETIVO (separación obligatoria)

### HOY (VERIFICADO POR CÓDIGO / EJECUCIÓN sobre este repo)

- H1 — Existe homologación METR anual FY2021–FY2025 (`data/TIKR_METR_HOMOLOGATION.md` §4)
  que reporta FX implícito TIKR ≈ mayorista con desvío 0,0–0,3 %.
  Clasificación técnica: VERIFICADO POR EJECUCIÓN (recomputado 2026-09-15 desde
  `data/TIKR_METR_BENCHMARK_ARS_USD.xlsx`: Revenue 102,69 / 176,75 / 808,46 /
  1030,50 / 1451,00; coincide con tabla §4 salvo Total Equity con +0,2 % por
  redondeo). Alcance: **5 puntos anuales, 1 emisora (METR), frecuencia anual**.
- H2 — El mismo benchmark contiene anomalías internas que impiden usarlo como oracle:
  EBITDA ARS/USD no reconcilia (−97,6 % a −22,2 %), acciones convertidas por FX
  (569M / FX), múltiplos 2024 no reconstruibles. VERIFICADO POR EJECUCIÓN (mismo archivo).
- H3 — Infraestructura FX existente en Catalaxia usa MEP (dolarito) y CCL por ADR
  (`scripts/dolares/_dolar.py`, `fetch_dolarito_historico.py`), con fuentes
  secundarias (dolarapi, criptoya, yfinance). Ninguna es fuente primaria BCRA.
  VERIFICADO POR CÓDIGO.
- H4 — Arquitectura documentada del repo es de 3 capas (descarga → raw → cálculo),
  NO las 12 capas del enunciado. Las 12 capas son OBJETIVO metodológico de esta
  investigación, no estado actual. VERIFICADO POR CÓDIGO (`docs/01-arquitectura.md`).
- H5 — No existe en el repo serie quarterly TIKR ARS↔USD con provenance, ni matriz
  de fechas objetivo, ni criterios pre-registrados, ni reconstrucción instrumental
  con settlement declarado. VERIFICADO POR CÓDIGO (búsqueda de `TIKR*`, `dolar/`).

### OBJETIVO (no afirmado hasta VERIFICAR + CERTIFICAR)

- Determinar `TIKR_FX_METHOD ∈ {A3500, OFICIAL, MEP, CCL, MEP_RECONSTRUCTED,
  CCL_RECONSTRUCTED, HYBRID, UNKNOWN}` + `TIKR_FX_CONFIDENCE` + `TIKR_FX_EVIDENCE`,
  sobre período quarterly prioritario 2023-Q3 → 2026-Q2, extendible hacia atrás
  sólo con evidencia reproducible.
- Regla: si la evidencia no alcanza, la salida es `UNKNOWN`. No se adapta la
  metodología tras ver resultados.

## 2. Mapeo a arquitectura Catalaxia (12 capas, 4 planos)

Las 12 capas se instancian SÓLO dentro de `research/fx_tikr_reverse/`:

| Capa | Instancia en esta investigación | Artefacto |
|---|---|---|
| 1 FUENTES | BCRA (A3500, oficial), fuentes MEP/CCL directas, precios ARS+USD por instrumento | `00_DEFINIR/source_registry.yaml` + `01_raw/` |
| 2 IDENTIDAD | entity_key canónico (CUIT/CIK), instrument_key, listing; ticker jamás es identidad | `00_DEFINIR/identity_rules.md` §3 |
| 3 RAW | respuestas crudas inmutables + hash + http_status + downloaded_at | `01_raw/` (append-only) |
| 4 PARSED | extracción tipada por fuente, parser versionado | `scripts/parse_*` |
| 5 NORMALIZED | (fecha, tipo_fx) canónico, moneda, escala, settlement | `scripts/normalize_*` |
| 6 ECONOMIC FACTS | FX implícito TIKR = ARS ÷ USD por métrica Cf. §4 homologación | `scripts/extract_tikr_fx.py` |
| 7 FINANCIAL MODEL | alineación temporal period_end vs publication vs settlement | `scripts/align_*` |
| 8 RATIOS | desvíos relativos por candidato, no ratios contables | `scripts/compare_stats.py` |
| 9 PROVENANCE | MRR por cada celda comparada | `outputs/provenance/` |
| 10 VALIDACIÓN | tests + gates (no-imputación, cobertura, invariantes) | `tests/` |
| 11 CERTIFICACIÓN | veredicto + confianza + evidencia, criterios pre-registrados | `outputs/CERTIFICATION.md` |
| 12 PUBLICACIÓN | export versionado con hashes, jamás a producción | `outputs/` |

Planos: DATOS (capas 1,3,4,5,6), CONTROL (9,10,11), EJECUCIÓN (scripts + runbook),
INFRAESTRUCTURA (esta carpeta + `requirements-fx.txt` + git commit).

## 3. Reglas (vinculantes)

- RAW inmutable: `01_raw/` es append-only; corrección = nuevo archivo + regla registrada.
- Provenance obligatoria en todo derivado (fuente, endpoint/parámetros, downloaded_at,
  http_status, raw_ref, raw_hash, parser_version, git_commit).
- No inventar datos. No completar períodos faltantes. Celda ausente = `NULL + null_reason`.
- No usar TIKR como oracle: TIKR es objeto de estudio, no fuente de FX.
- No adaptar metodología post-resultados: `decision_criteria.md` queda congelado antes
  de `IMPLEMENTAR` comparaciones (hash + fecha).
- No modificar producción: prohibido escribir en `data/screener.db`, `engine/`,
  `backend/`, `scripts/` (fuera de esta carpeta), Postgres 5432/5433.
- Toda afirmación técnica clasificada: VERIFICADO POR CÓDIGO / TEST / EJECUCIÓN /
  FUENTE / NO DETERMINABLE.
- Todo hallazgo clasificado: BLOCKER / REQUIRED_FIX / OBSERVATION / IMPROVEMENT /
  OUT_OF_SCOPE / NO DETERMINABLE.

## 4. Trazabilidad REQ-FX-001..010

| REQ | Artefacto que lo cubre | Estado |
|---|---|---|
| 001 matriz fechas | `target_dates.csv` + `build_target_matrix.py` + test | DEFINIR listo, test pendiente |
| 002 A3500 primario | `source_registry.yaml` §A3500 + `fetch_bcra_a3500.py` (stub) | DEFINIR, fuente por verificar |
| 003 Oficial primario | `source_registry.yaml` §OFICIAL | DEFINIR, fuente por verificar |
| 004 directa vs instrumental | `source_registry.yaml` §MEP/CCL + `instrumental_spec.md` | DEFINIR |
| 005 reproducibilidad instrumental | `instrumental_spec.md` + schema `instrumental_quote` | DEFINIR |
| 006 no imputación | `stats_spec.md` §6 + test `test_no_imputation` | DEFINIR |
| 007 estadísticos | `stats_spec.md` + `stats.py` + test | DEFINIR listo, test pendiente |
| 008 comparación 6 candidatos | `decision_criteria.md` §3 + `compare_stats.py` (stub) | DEFINIR |
| 009 criterios previos | `decision_criteria.md` (congelar por hash) | DEFINIR — NO modificar tras ver datos |
| 010 reproducibilidad auditor | `REPRODUCIBILITY.md` + runbook + `requirements-fx.txt` | DEFINIR |

## 5. Salida inicial (sin evidencia nueva)

```
TIKR_FX_METHOD = UNKNOWN
TIKR_FX_CONFIDENCE = 0.00 (sin cobertura quarterly)
TIKR_FX_EVIDENCE = {H1 anual METR n=5 (insuficiente para quarterly),
  H2 anomalías benchmark, H5 ausencia de serie quarterly}
```

Cualquier otra clasificación hoy sería NO DETERMINABLE.
