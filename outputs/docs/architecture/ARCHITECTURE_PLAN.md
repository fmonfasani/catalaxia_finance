# ARCHITECTURE_PLAN.md — Catalaxia Financial Data Engine

PHASE 0 deliverable · 2026-08-23 · Status: PROPOSED (bloqueado por DECISION_QUEUE)
Base normativa: EXTRACTION_SPECIFICATION · PROVENANCE_SPECIFICATION · DATA_CONTRACT_EXTRACTION · EXTRACTION_CHECKLIST · DO_NOT_REPEAT (+EXT-NEW-001..012) · EXTRACTION_KNOWLEDGE_BASE.
Nota: `PIPELINE_VALIDATION_SPECIFICATION.md` referido por el programa NO existe en el repo → se autorá en PHASE 1 (ver RISK R-02).

## 1. Evidencia de la auditoría de repositorio (PHASE 0)

Generaciones de código vivas inventariadas (~90 .py activos):

| Generación | Ubicación | Rol histórico | Veredicto heredado (FASE2 §4) |
|---|---|---|---|
| Screener v1 | `scripts/screener/01..08` | primera generación EDGAR+ratios | ARCHIVAR (referencia) |
| Pipeline f1–f6 | `scripts/pipeline/` | pipeline v1 + fixes manuales incrustados | PORT controles únicos; resto DEPRECAR |
| jobs CNV job1–8 | `scripts/tickets/cnv/` | única extracción CNV válida | KEEP (fuente primaria CNV) |
| M1 s0–s9 | `scripts/tickets/screener/` | extracción+ensamblado canónico vigente | KEEP como referencia M1 |
| Audit b0–b9 | `scripts/byma/` | certificación oficial (487 CERTIFIED/72 NOT) | KEEP patrón de gates/certificación |
| EDGAR tickets | `scripts/tickets/sec_edgar/` (construir_base, calcular_ratios_base, precios_y_valuacion, _caducidad, run_all/run_update) | extractor EDGAR vigente (~4,6M filas `facts`) | KEEP; su lógica se porta al engine |
| TXAR demo | `scripts/demo_txar/` | demostración medallion bronce→silver→certificar | patrón de referencia para engine |
| Piloto YPF | `scratchpad/ypf_edgar_audit/` | parser XBRL universal + auditoría 16 filings | PORT directo → `engine/parsers/xbrl/` |

Hallazgos clave que condicionan la arquitectura `[DOCUMENTADO]`:
1. Extractor EDGAR vigente solo resuelve 4/32 métricas buscadas sobre YPF (busca nombres us-gaap dentro de namespace ifrs-full); el dato SÍ existe con tags IFRS correctos (`ifrs-full:Revenue`, `ProfitLossAttributableToOwnersOfParent`, `Borrowings`, …).
2. El 77% de las observaciones XBRL de YPF son dimensionales; extraer solo consolidado pierde información → PARSED debe preservar dimensiones completas.
3. Layouts XBRL heterogéneos (instancia XML / `-xbrl.zip` / iXBRL `_htm.xml` / linkbases embebidos en xsd) → parser ya resuelto en piloto YPF.
4. Cambio de moneda de presentación ARS→USD entre 20-F FY2021/FY2022 → guard de unidad/moneda obligatorio por período.
5. `backend/requirements.txt` fija `yfinance==0.2.50`, versión rota según EXT-053 → riesgo activo (R-01).
6. Deuda FASE2 pendiente: oleadas O2–O5 (ports, unificación de certificación, bajas, correction_log).

## 2. Arquitectura objetivo

Pipeline por capacidades (una capacidad = una etapa del stage graph = un agente responsable):

```
S00 BOOTSTRAP (config+registros+state machine)
S01 IDENTITY      → entity_registry canónico (CIK/CUIT ↔ ticker ↔ clasificación)
S02 FETCH SEC     → RAW inmutable + download_log (append-only)
S03 PARSE XBRL    → PARSED: todos los facts, dimensiones incluidas
S04 NORMALIZE     → NORMALIZED: conceptos canónicos + factor_unidad + perímetro + moneda
S05 FACTS         → ECONOMIC FACTS: serie anual/TTM por concepto canónico, sin mezcla de vintages
S06 STATEMENTS    → FINANCIAL STATEMENTS estructurados (IS/BS/CF por FY)
S07 MARKET        → precios/mcap/FX con guards y staleness
S08 METRICS       → 13 métricas + fórmulas versionadas + lineage L0-L5
S09 VALUATION     → PER/PB/EV_EBITDA/etc. apareados con mercado
S10 QUALITY       → validación matricial empresa×métrica + certificación estilo b7
S11 SNAPSHOT      → snapshot certificado SHA256 (fuentes+DB+código)
S12 PUBLISH       → DB/API/screener export SOLO estados certificados o flaggeados
```

Ciclo por etapa: `PLAN → DESIGN → IMPLEMENT → RUN → MEASURE → VALIDATE → DEBUG → FIX → RERUN → REGRESSION → GATE → CHECKPOINT → DOCUMENT → NEXT`.
Modos: FAST (subset YPF), FULL (universo completo), AUDIT (verificación sin escrituras nuevas).

## 3. Modelo de datos por capa

Decisión D-002 (gate 2026-08-23): **PostgreSQL desde día 1** para todas las capas PARSED→PUBLISHED; RAW permanece como archivo inmutable en disco con índice/manifest en DB.

| Capa | Artefacto | Contenido mínimo (provenance obligatoria) |
|---|---|---|
| RAW | archivos inmutables `data/raw/edgar/{cik}/{accession}/…` + `_manifest.csv` + tabla `download_log` (URL/status/bytes/sha256/downloaded_at) | tal cual fuente |
| PARSED | tabla de hechos fina: (entity_key, accession, tag crudo, taxonomy, start/end, value, unit, decimals, dimensions JSONB, form, filed) | nace la huella (EXT-NEW-001) |
| NORMALIZED | (entity_key, concept_canonico, period_start/end, value_norm, unit_original, scale_factor, moneda, perimetro, accn, parser_version) | reglas §6/§7 SPEC |
| ECONOMIC FACTS | series FY/TTM por concepto con period_ref y tres planos temporales separados | EXT-NEW-003 |
| DERIVED/METRICS | valor + formula_version + inputs[] citables + flags + null_reason | patrón traza L0-L5 / MRR |
| CERTIFIED | status por (entity, metric) + motivos citando check fallado | estilo b7 |
| PUBLISHED | snapshot_id + pipeline_version + git_commit | SPEC §20 |

Regla dura: ninguna capa lee "dos capas abajo"; el lineage es estrictamente vertical (PROVENANCE_SPEC cadena vertical).

## 4. Reutilización (no reescritura)

| Componente nuevo | Se alimenta de | Modo |
|---|---|---|
| engine/parsers/xbrl | piloto YPF `02_parsear.py` (soporta los 4 layouts) | PORT |
| engine/fetchers/edgar | `tickets/sec_edgar/construir_base.py::_caducidad` + UA/delay de SPEC §13 | PORT de reglas, reimplementación del orquestador |
| identity | f1_identidad + EXT-NEW-002/012 (ticker≠identidad, revisión manual GOLD/CHA) | PORT |
| normalization | `factor_unidad()`, `perimetro_preferido()`, calendarios s2a | PORT de funciones |
| metrics/ratios | calcular_ratios_base PRIORIDAD + fallbacks declarados | PORT + versionado formula_version |
| quality/certification | b6/b7 + validar_suite cruces (resuelve doble sello, R-10) | PORT |
| market | s3*/s9 guards + precios_y_valuacion apareo | PORT |
| publish | deploy/sincronizar_a_produccion.py + contrato DATA_CONTRACT §9 | KEEP + provenance de publicación |

Legacy NO se borra ni se modifica durante el programa; queda como fallback consultable (regla maestra §1.4 del programa).

## 5. Cumplimiento normativo (matriz resumen)

| Norma | Cómo la absorbe la arquitectura |
|---|---|
| DO_NOT_REPEAT 1–20 + EXT-NEW-001..012 | guards por etapa + contratos de tabla + conciliación expected→published obligatoria |
| PROVENANCE_SPEC 7 tipos de huella | columnas mínimas por capa (§3) + MRR generado por código |
| DATA_CONTRACT | cada tabla nueva nace con entrada de contrato; PK con dimensiones de unicidad declaradas |
| CHECKLIST FASE 0–5 | pre-flight y firma de corrida automatizados en el reporte estándar de etapa |
| Reproducibilidad clase A/B/C/D | toda pieza nueva declara clase; engine v1 apunta a clase A desde PARSED hacia abajo |
