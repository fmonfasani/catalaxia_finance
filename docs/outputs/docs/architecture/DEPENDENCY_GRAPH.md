# DEPENDENCY_GRAPH.md — Catalaxia Financial Data Engine

PHASE 0 deliverable · 2026-08-23 · Status: PROPOSED

## 1. Dependencias de datos (fuentes)

| Fuente | Rol | Endpoint/Mecanismo | Rate limit / cortesía | Clase reproducibilidad |
|---|---|---|---|---|
| SEC EDGAR submissions | S02 | `data.sec.gov/submissions/CIK{zfill10}.json` | secuencial, UA real "Nombre email", sleep ~0.15–0.30s, NUNCA paralelo | B |
| SEC EDGAR filings XBRL | S02/S03 | índice + `-xbrl.zip` / `_htm.xml` / xsd embebido (4 layouts) | idem | B (A una vez en RAW) |
| SEC companyfacts | contraste S05 | `data.sec.gov/api/xbrl/companyfacts/` | idem; diverge de filings (lag conocido) | B |
| CNV aif2 | futuro multi-fuente (fuera de v1 YPF) | publicview aif2 (NO aif: geo-bloqueo), sleep 0.3–1s, una instancia | C parcial | — |
| yfinance | S07 precios/FX | versión FIJADA ≠ 0.2.50 (rota, EXT-053) + guard sanidad s9 | tolerante, retry 429 | B |
| INDEC IPC | transformación declarada (deflator_vintage por fila) | descarga manual/monitor | C | — |
| Benchmarks (TIKR/StockAnalysis) | PHASE 11 contraste | drop manual en `data/raw/benchmarks/{source}/{fecha}/` (ver D-006) | scraping bloqueado precedentemente (Cloudflare) | C |

Regla EXT-NEW-006: fuente secundaria JAMÁS parchea primario; contraste conserva ambos valores + diferencia.

## 2. Grafo de dependencias entre etapas

```
S00 ─→ S01(IDENTITY) ─→ S02(FETCH) ─→ S03(PARSE) ─→ S04(NORMALIZE) ─→ S05(FACTS) ─┬→ S06(STATEMENTS) ─┐
                                                                                   │                    ├→ S08(METRICS) ─→ S09(VALUATION) ─→ S10(QUALITY) ─→ S11(SNAPSHOT) ─→ S12(PUBLISH)
                                                                                   └─→ S07(MARKET) ─────┘
```
- S07 depende de S01 (identity) pero NO de S05: puede correr en paralelo al branch fundamental.
- S08 consume S06+S07; S09 consume S08+S07 (apareo obligatorio EXT-005).
- S10/S11/S12 estrictamente secuenciales sobre lo anterior.

## 3. Dependencias de código (mapa de ports)

| Módulo engine nuevo | Depende de (legacy/piloto) | Qué porta |
|---|---|---|
| engine/config.py | — | SCREENER_DB-style env var; jamás hardcode (lección O1) |
| engine/registry.py | f1_identidad.py, DATA_CONTRACT §1 | entity_registry: identidad≠clasificación |
| engine/fetchers/edgar.py | construir_base.py::_caducidad, run_update.py lastFiled | invalidación por fecha explícita; download_log append-only |
| engine/fetchers/yfinance.py | s9_guards_yfinance.py | guards + staleness_dias |
| engine/parsers/xbrl/* | scratchpad/ypf_edgar_audit/02_parsear.py | los 4 layouts, contextos, dimensiones, unidades, linkbases |
| engine/normalize/{units,perimeter,currency,calendar}.py | factor_unidad(), perimetro_preferido(), s1_bimoneda, s2a_calendario | reglas SPEC §6–§10 |
| engine/facts/series.py | dedup por `end` (construir_base CANONICO/PRIORIDAD) | series FY/TTM period_ref |
| engine/metrics/formulas/*.py | calcular_ratios_base.py + fallbacks declarados | fórmulas versionadas formula_id@version |
| engine/market/valuacion.py | precios_y_valuacion.py apareo | mcap+FX pareados |
| engine/quality/{checks,certify}.py | b2 ESCALA_JUMP, job7 identidad contable, b6/b7 | matriz OK/WARN/INFO/FAIL → CERTIFIED |
| engine/snapshot.py | scripts/byma/snapshot_byma.py | SHA256 fuentes+estado+código |
| engine/publish/* | deploy/sincronizar_a_produccion.py | publicación solo certificado + provenance |

## 4. Dependencias documentales (entrada obligatoria por fase)

| Fase | Docs que debe leer antes de codificar |
|---|---|
| Todas | DO_NOT_REPEAT.md, EXTRACTION_CHECKLIST.md |
| 1 (documentación) | KB completa + PIPELINE_VALIDATION_SPECIFICATION.md (a autorar) |
| 2 (esqueleto) | STAGE_GRAPH, ARCHITECTURE_PLAN |
| 3–5 | EXTRACTION_SPECIFICATION §4–§12, PROVENANCE_SPEC §1–§3, DATA_CONTRACT §2 |
| 6–8 | DATA_CONTRACT §3–§4, FORMULAS_RATIOS (docs/calculos-financieros), ESPEC_TAGS_RATIOS |
| 9–10 | PROVENANCE_SPEC §4–§7, método audit v3 (SPEC §22) |
| 11–13 | estándar admisión fuentes §2.2 (12 requisitos) |
