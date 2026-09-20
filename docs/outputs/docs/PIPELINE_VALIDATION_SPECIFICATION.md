# PIPELINE_VALIDATION_SPECIFICATION.md

**Especificación de validación del pipeline — Catalaxia Financial Data Engine**
v1.0 · 2026-08-23 · Cierre del gap R-02. Complementa `STAGE_GRAPH.md`, `EXTRACTION_CHECKLIST.md` y `DO_NOT_REPEAT.md`.
Alcance: qué significa que una etapa PASE, qué checks se exigen, cómo se concilia y cómo se certifica.

---

## 1. Niveles de gate

| Nivel | Semántica | Consecuencia |
|---|---|---|
| **PASS** | Todos los checks obligatorios ejecutados y aprobados | La etapa avanza a CHECKPOINTED |
| **WARNING** | Check no bloqueante falló o desvío explicado y aceptado por regla declarada | Avanza SOLO con el warning registrado en `gate_reasons` y visible en publicación |
| **BLOCK** | Check bloqueante falló, brecha de conciliación sin explicar, o señal de alarma DO_NOT_REPEAT activa | La etapa queda FAILED; downstream prohibido; diagnóstico taxonomía A–E antes de FIXING |

Regla dura: "terminó sin excepción" nunca es PASS (norma EXTRACTION_CHECKLIST FASE 5).

## 2. Catálogo mínimo de checks por etapa

Formato: `C-{stage}-{nnn}`. Los BLOCK son mínimos exigibles; cada fase puede agregar checks, jamás quitarlos sin ADR.

| Etapa | Checks BLOCK | Checks WARNING |
|---|---|---|
| S00 bootstrap | C-S00-001 migraciones aplicadas en orden sin drift · C-S00-002 target DB ≠ producción (EXT-010) | — |
| S01 identity | C-S01-001 entity_key canónico único · C-S01-002 ticker duplicado/reciclado → revisión manual (GOLD/CHA) · C-S01-003 identidad≠clasificación columnas separadas | alias ambiguo documentado |
| S02 fetch | C-S02-001 http_status=200 para todo expected (faltantes listados con motivo) · C-S02-002 RAW persistido ANTES de parsear con sha256 · C-S02-003 download_log append-only · C-S02-004 UA real + secuencial | respuesta anormalmente pequeña vs histórico |
| S03 parse | C-S03-001 cobertura facts vs manifest (expected→parsed→rejected con motivo) · C-S03-002 layouts no soportados = 0 · C-S03-003 parser_version registrada · C-S03-004 dimensiones preservadas (conteo contextual vs filas) | tags custom nuevos vs corrida anterior |
| S04 normalize | C-S04-001 unidad SIEMPRE columna (unit_original+scale_factor) · C-S04-002 moneda por-fact · C-S04-003 perímetro explícito NOT NULL · C-S04-004 todo rejected con reject_reason | cambio de factor vs histórico |
| S05 facts | C-S05-001 dedup por `end` (jamás fy) · C-S05-002 sin mezcla moneda/vintage en una serie · C-S05-003 tres planos temporales separados y poblados · C-S05-004 flujo vs foto coherente (start/end) | huecos intermedios tolerados con marca |
| S06 statements | C-S06-001 identidad contable Activo=Pasivo+PN por filing (tolerancia declarada; violación → suspect, excluido flaggeado) | partidas no mapeadas a estructura |
| S07 market | C-S07-001 guards sanidad precio (s9-style) · C-S07-002 staleness_dias calculado · C-S07-003 NULL ante duda, jamás estimar | staleness > umbral declarado |
| S08 metrics | C-S08-001 formula_version obligatoria · C-S08-002 inputs[] citables por métrica (lineage L0-L5) · C-S08-003 todo NULL con null_reason · C-S08-004 flags cargados (ni_fy, NOMINAL_sin_deflactar…) | fallback usado (flag visible) |
| S09 valuation | C-S09-001 apareo mcap↔métrica verificado (dif_check) · C-S09-002 FX con método/tasa/fecha si hubo conversión | dif_check > umbral |
| S10 quality | C-S10-001 matriz empresa×métrica completa · C-S10-002 FAIL ⇒ NOT_CERTIFIED con motivo citando check · C-S10-003 sin NULL sin motivo en lo publicado | INFO acumulado |
| S11 snapshot | C-S11-001 hashes fuentes+código+estado · C-S11-002 recompute_command ejecutable | — |
| S12 publish | C-S12-001 solo CERTIFIED o flaggeado · C-S12-002 provenance de publicación (snapshot_id, pipeline_version, git_commit) | — |

## 3. Conciliación obligatoria (EXT-NEW-008)

Toda corrida cierra con el bloque (del log y del reporte JSON):

```
rows_expected    = N   ← definido en PRE-FLIGHT, jamás post-hoc
rows_downloaded  = N   ← brecha => motivo por fila/clase
rows_parsed      = N
rows_rejected    = N   ← desglose por reject_reason
rows_normalized  = N
rows_derived     = N
rows_published   = N
```

Brecha sin explicación ⇒ gate BLOCK. El conteo NUNCA es validación suficiente (EXT-NEW-004): se verifican además columnas, valores (muestra+sumas de control), NULLs, claves únicas, hashes y cobertura por universo.

## 4. Contrato de reporte de corrida

Espeja `STAGE_GRAPH.md` §3. Campos obligatorios: `stage, run_id, mode, started_at, finished_at, input{checkpoint_id,rows}, coverage{expected,parsed,rejected,by_reason}, integrity{hash_in,hash_out}, gate{status,reasons[],checks[]}, nulls{count,by_null_reason}, code{git_commit,parser_version,script}`.
El reporte se persiste en `engine.stage_runs.report` (JSONB) y su resumen en el log de corrida (`data/logs/`).

## 5. Certificación

- Estado por (entity, metric): **CERTIFIED** / **NOT_CERTIFIED** con `motivos[]` citando el check fallado (patrón b7). Un único sello: el de esta especificación (resuelve contradicción #5 / doble sello M2-vs-b7).
- Certificado = consistencia interna + provenance demostrable. NO implica veracidad externa; el contraste externo vive como fuente secundaria conservando ambos valores (EXT-NEW-006).

## 6. Señales de alarma ⇒ BLOCK automático

Las 5 señales de `DO_NOT_REPEAT.md` (conteo cambia sin explicación; ratio ±>10% entre corridas; magnitud ×10/×1000; doc viejo sin deprecar; "terminó OK" con cobertura cayendo) se implementan como comparación contra la corrida anterior del mismo stage y fuerzan BLOCK.

## 7. Regresión

Antes de CERTIFIED, toda etapa compara contra su checkpoint anterior: cobertura por universo, sumas de control por concepto, distribución de unidades/monedas. Diferencia sin explicación = FIXING. La suite de regresión es parte del gate, no un extra.
