# PROVENANCE_SPECIFICATION.md

**Huella de datos — Catalaxia Finance**
v1.0 · 2026-08-22 · Complementa `EXTRACTION_SPECIFICATION.md` §16 y `DATA_CONTRACT_EXTRACTION.md`.
Pregunta que este diseño responde, dentro de 5 años: **"Mostrame exactamente de dónde salió este número."**

`source = CNV` NO es provenance. La huella identifica el hecho concreto.

## Cadena vertical exigible

```
MÉTRICA PUBLICADA
      ↓  formula_version + flags
FÓRMULA + VERSIÓN
      ↓  inputs citados (tabla_norm, concepto, period_end, perimetro)
INPUTS
      ↓  unit_normalized, scale_factor, moneda
DATOS NORMALIZADOS
      ↓  extraction_rule, parser_version
DATOS PARSEADOS
      ↓  raw_value, unidad_original, decimales, accn/guid
VALOR RAW
      ↓  form_type, filing_date, period_start/end
DOCUMENTO
      ↓  endpoint + request_parameters + downloaded_at
FUENTE
      ↓
ARCHIVO/RESPUESTA (raw_ref)
      ↓
HASH (raw_file_hash / snapshot_hash)
```

---

## 1. Provenance del DOCUMENTO

| Campo | Nivel | Notas |
|---|---|---|
| source_system (cnv/sec/yfinance/manual) | OBLIGATORIO | |
| source_url / endpoint + request_parameters | RECOMENDADO | reproducir la consulta |
| document_guid (CNV) / accession_number (EDGAR) | OBLIGATORIO | identifica el hecho concreto |
| form_type (10-K/20-F/6-K/339…) | OBLIGATORIO | catálogo es_eeff |
| filing_date / published_at | OBLIGATORIO | plano temporal de la fuente |
| downloaded_at + http_status | OBLIGATORIO download, RECOMENDADO http | hoy no existe → gap 8 |
| raw_ref (path del crudo) | OBLIGATORIO | eeff_html/{guid}.html, data/raw/*.json |
| raw_file_hash | RECOMENDADO | integridad del archivo |

## 2. Provenance del HECHO (dato crudo)

| Campo | Nivel | Notas |
|---|---|---|
| entity_key canónico (CUIT/CIK) | OBLIGATORIO | jamás razón social/ticker |
| concept canónico + source_tag + taxonomy/namespace | OBLIGATORIO | NetIncome ← us-gaap:NetIncomeLoss |
| period_start / period_end / fy / fp | OBLIGATORIOS | dedup por `end`; fy ≠ período |
| start/end presentes (flujo vs foto) | OBLIGATORIO | define tratamiento TTM |
| raw_value | OBLIGATORIO | tal como vino |
| unit_original + currency_original | OBLIGATORIOS | nunca supuesto |
| perimetro_original (I/C) | OBLIGATORIO | desde migración 002 |
| decimals (XBRL) | RECOMENDADO | presente en raw, NO propagado → gap 1-2 |
| es_restatement | RECOMENDADO | re-emisiones de filings → gap 3 |
| frame / filed / accn XBRL | OPCIONAL→RECOMENDADO | |
| hash_valor | OPCIONAL | auditoría profunda |

## 3. Provenance de la TRANSFORMACIÓN

| Campo | Nivel | Notas |
|---|---|---|
| extraction_rule / transformation_rule declarada | OBLIGATORIO | factor_unidad, perimetro_preferido, fiscal_calendar… |
| parser + parser_version | OBLIGATORIO | template CNV cambió 2024+; versión obligatoria |
| script + git_commit + job_id | RECOMENDADO | gaps 4-6 hoy ausentes |
| unit_normalized + scale_factor aplicado | OBLIGATORIO | conservar ambos, no solo el resultado |
| currency_normalized + conversion_method/rate/date | OBLIGATORIO si hubo conversión | MEP pareado con dif_check |
| deflator + deflator_vintage (IPC) | OBLIGATORIO si hubo deflactación | gap 11: vintage no persistido por fila |
| normalized_record_hash | RECOMENDADO | |
| transformed_at | OBLIGATORIO | plano pipeline |

## 4. Provenance del CÁLCULO

| Campo | Nivel |
|---|---|
| formula_id + formula_version (per_ttm@v3…) | OBLIGATORIO — todo cambio de fórmula = nueva versión (lección TXAR payout) |
| inputs[] citando (tabla_norm, entity_key, concepto, period_end, perimetro) por partida usada | OBLIGATORIO — patrón traza L0-L5 |
| flags que afectaron el cálculo (EPS_FALLBACK_OpInc, ni_fy, NOMINAL_sin_deflactar, roe_ns…) | OBLIGATORIO |
| null_reason / discard_reason para NULLs derivados | OBLIGATORIO — NULL sin motivo = defecto |
| computed_at + pipeline_version | OBLIGATORIO |

## 5. Provenance de la PUBLICACIÓN

snapshot_id · db_target (sqlite local / postgres prod) · api_version · export_hash (screener_export.csv) · published_at · certificación asociada (b7 status/motivos). `[RECOMENDACIÓN — hoy inexistente]` Sin esto no se puede responder "¿qué estaba publicado el día X y quién lo produjo?".

## 6. Provenance del SNAPSHOT

snapshot_id · timestamp · fuentes cubiertas · files+hashes · estado DB (hash de tablas) · pipeline_version · git_commit. Implementado en flujo byma (`snapshot_byma.py`); pendiente formalizar hash de DB y extender a producción.

## 7. Provenance del CÓDIGO

git_commit · script path · parser_version · requirements/env hash. Regla: **toda tabla DERIVED debe poder responder "qué commit te produjo"**. Hoy: gap 4-6 (parser_version/git_commit/job_id ausentes en tablas y exports).

## 8. MRR — Minimum Reproducibility Record v2

Base: KB §24. Verificación contra el estándar pedido → faltaban y se agregan:

```yaml
mrr:
  metric_id: PER_TTM
  entity_key: "30691421816"
  asof_date: 2026-08-22
  formula_version: per_ttm@v3
  inputs:
    - source: cnv_aif2            # NUEVO vs v1
      entity: "30691421816"
      concept: NetIncome          # + source_tag/taxonomy en nivel hecho
      period_start: 2025-01-01    # NUEVO
      period_end: 2025-12-31
      perimetro: I
      raw_value: 12345            # NUEVO (valor pre-factor)
      normalized_value: 12345000
      unit: MILES                 # + unit_original/scale_factor
      currency: ARS
      document: {guid: 04cfdb86-, form_type: EEFF, filed_at: ...}   # NUEVO
      raw_ref: eeff/eeff_html/04cfdb86.html                          # NUEVO
      hash: <sha256>                                                 # NUEVO
  transformations:
    - rule: factor_unidad         # NUEVO como lista versionada
      version: v2
      parameters: {MILES: 1000}
    - rule: ttm_strategy_C
      version: v1
      parameters: {period_ref: 2025-Q4}
  flags: [EPS_FALLBACK_OpInc]
  null_reasons: []                # NUEVO
  snapshot_id: byma_snapshot_2026-08-22
  pipeline_version: audit-v3      # NUEVO
  git_commit: "<sha>"             # existía
  computed_at: 2026-08-22T03:41Z
  recompute_command: python scripts/byma/b5_metricas.py --entity 30691421816
```

Regla MRR: generado por código (nunca a mano); si un input no completa campos OBLIGATORIOS → la métrica se publica flaggeada o no se publica.

## 9. Los 11 gaps vigentes mapeados a su fix

| # | Gap actual | Tipo provenance | Fix propuesto (fase 2) | Prioridad |
|---|---|---|---|---|
| 1-2 | accn + decimals no propagados raw→facts | Hecho | columnas accn/decimals en facts al re-parsear desde cache | P1 |
| 3 | es_restatement inexistente | Hecho | detectar por (concept,end) duplicado con val distinto entre filings | P2 |
| 4 | sin hash por valor | Hecho | hash_valor opcional solo en exports de auditoría | P3 |
| 5-6 | parser_version/git_commit/job_id ausentes | Transformación/Código | columnas estándar en tablas DERIVED + encabezado en exports | P1 |
| 7 | fecha_facts pisada (sin histórico descargas) | Documento | tabla download_log (cik, form, filed_at, downloaded_at, http) | P1 |
| 8 | http_status no persistido | Documento | idem download_log — distingue "no existe" de "rate-limited" | P1 |
| 9 | motivo_descarte incompleto para NULLs | Cálculo | null_reason obligatoria junto a cada métrica NULL | P2 |
| 10 | raw_ref no indexado fila→archivo CNV | Documento | columna raw_ref en cnv_estados_norm (guid ya existe) | P2 |
| 11 | vintage deflactor no persistido por CAGR | Transformación | deflator_vintage junto a cada CAGR dolarizado | P2 |

## 10. Prueba de fuego: la pregunta dentro de 5 años

*"¿Por qué el PER_TTM de HAVA del 2026-08-22 dio X?"* — Respuesta exigible con este diseño:
traza L0-L5 → inputs: NI_ttm (partidas_norm, concepto 3049999, perímetro I, TTM period_ref Q4-2025, factor ×1000 por MILES, guid 04cfdb86, HTML en eeff_html/, snapshot byma_2026-08-22) + mcap_ars (mercado_byma, yfinance .BA, staleness 47d) → formula per_ttm@v3 = mcap/NI_ttm → git_commit + b7 CERTIFIED/NOT_CERTIFIED con motivo. `[INFERENCIA]` Hoy esto ya es ~80% reconstruible para BYMA v3; para US/ADR falta propagación accn/decimales y lineage generalizado.

## 11. Criterios A–N del éxito

Cubiertos íntegramente en `EXTRACTION_SPECIFICATION.md` §25 (tabla con estado 🟢/🟡/❌ y gaps). Resumen: los tres NO-parciales que bloquean el pleno cumplimiento son **A/M/N** → gaps 1-8 de la tabla §9.

---
*Cierre: "Un número sin origen demostrable no es un dato confiable." La huella empieza en el crudo (EXT-NEW-001), viaja por las 7 capas de esta especificación y termina siendo demostrable en el MRR.*
