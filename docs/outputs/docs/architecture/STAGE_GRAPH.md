# STAGE_GRAPH.md — Catalaxia Financial Data Engine

PHASE 0 deliverable · 2026-08-23 · Status: PROPOSED

## 1. Definición de etapas

| ID | Etapa | INPUT | OUTPUT | Gate de salida (ejemplos) |
|---|---|---|---|---|
| S00 | Bootstrap/Config | repo + docs normativos | engine/config, registries, state machine, logs dir | config carga sin defaults silenciosos a prod |
| S01 | Identity | catálogos EDGAR/CNV | entity_registry (entity_key canónico + clasificación separada) | ticker duplicado/reciclado → BLOCK hasta revisión manual |
| S02 | Fetch SEC | entity_registry | RAW inmutable + `_manifest.csv` + download_log | conciliación expected→downloaded=100% explicada; http_status≠200 listado |
| S03 | Parse XBRL | RAW | PARSED (facts finos con dimensiones) | cobertura facts vs manifest; layouts no soportados = 0; parser_version registrada |
| S04 | Normalize | PARSED + reglas | NORMALIZED (concepto canónico, unit_original+scale_factor, perímetro, moneda) | todo fact rejected tiene reject_reason; unidad SIEMPRE columna |
| S05 | Facts | NORMALIZED | ECONOMIC FACTS series FY (+TTM cuando aplique) | dedup por `end`; sin mezcla ARS/USD entre vintages; tres planos temporales validados |
| S06 | Statements | FACTS | IS/BS/CF estructurados por FY | identidad contable Activo=Pasivo+PN por filing (tolerancia declarada) |
| S07 | Market | identity + yfinance/FX | precios/mcap/staleness con guards | guard sanidad s9; NULL ante duda; staleness_dias visible |
| S08 | Metrics | STATEMENTS(+FACTS) | 13 métricas + lineage L0-L5 + flags/null_reason | formula_version obligatoria; todo NULL con null_reason |
| S09 | Valuation | METRICS+MARKET | PER/PB/EV_EBITDA… apareados | apareo mcap↔métrica verificado; dif_check |
| S10 | Quality | todo lo anterior | validacion_matriz + certificación (estilo b7) | FAIL → NOT_CERTIFIED con motivo citando check |
| S11 | Snapshot | estado certificado | snapshot_id + hashes fuentes+DB+código | recompute_command ejecutable |
| S12 | Publish | snapshot certificado | DB/API/export | SOLO CERTIFIED o flaggeado; provenance de publicación |

Fuera de alcance v1 (documentado con null_reason): años pre-XBRL FY2010–FY2016 vía XBRL (requieren parser HTML/PDF distinto); CNV multi-fuente (post-YFP golden test).

## 2. Máquina de estados por etapa

```
PLANNED → READY → RUNNING → VALIDATING → FAILED → FIXING → RERUNNING → PASSED → CHECKPOINTED → CERTIFIED
```
- Solo `CHECKPOINTED` permite que etapas downstream corran.
- `FAILED` exige diagnóstico taxonomía A–E antes de `FIXING`.
- Re-corrida con input+code+contract sin cambios ⇒ NO reprocesa (checkpoint hit).

## 3. Contrato de reporte estándar (toda etapa)

```json
{
  "stage": "S03_parse", "run_id": "...", "mode": "FAST|FULL|AUDIT",
  "started_at": "...", "finished_at": "...",
  "input": {"checkpoint_id": "...", "rows": N},
  "coverage": {"expected": N, "parsed": N, "rejected": N, "by_reason": {}},
  "integrity": {"hash_in": "...", "hash_out": "..."},
  "gate": {"status": "PASS|WARNING|BLOCK", "reasons": [], "checks": [{"id":"...","result":"...","detail":"..."}]},
  "nulls": {"count": N, "by_null_reason": {}},
  "code": {"git_commit": "...", "parser_version": "...", "script": "..."}
}
```
La conciliación `rows_expected→downloaded→parsed→rejected→normalized→derived→published` es obligatoria en cada corrida (EXT-NEW-008); brecha sin explicación = gate BLOCK.

## 4. Checkpoints

- Estado de checkpoints en PG (tablas `engine.checkpoints`/`runs`); artefactos binarios grandes opcionales en `data/engine/checkpoints/{stage}/{run_id}/`.
- Clave de reutilización: hash(input) + code_version + contract_version.
- Modo AUDIT: corre validaciones sobre checkpoints existentes sin escribir capas nuevas.

## 5. Reglas transversales del stage graph

1. Ninguna etapa salta su gate; WARNING requiere registro en run report; BLOCK detiene el pipeline.
2. RAW jamás se modifica; correcciones = correction_log declarativo (raw_value+rule+reason+corrected_value+at+by).
3. Toda pieza nueva declara clase A/B/C/D al nacer.
4. Señales de alarma DO_NOT_REPEAT (conteo cambia, ratio >10% entre corridas, magnitud ×10/×1000, doc viejo sin deprecar, "terminó OK" con cobertura cayendo) ⇒ STOP + auditoría.
