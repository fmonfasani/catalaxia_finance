# 20 — F8: Integración E2E Validación (C10) → Certificación (C11) → Publicación (C12)

Cadena completa ejecutada en DEV (`catalaxia_engine@127.0.0.1:5433/catalaxia`, staging Postgres) sobre un run SEC E2E **fresco** de YPF. Evidencia marcada `[EJECUCIÓN]` (comandos reales), `[CÓDIGO]` (scripts), `[TEST]` (pytest). Solo lectura/DDEV: C12 publica únicamente al schema `staging` (sin cutover productivo) `[CÓDIGO]`.

## 1. Run de la cadena

`161f128ca0d347ad94bbb27cefbdc024` — YPF (CIK 0000904851) E2E `e2e-sec-edgar-v1`, S00→S04 todos `CHECKPOINTED/PASS` (25 eventos de vida, historial completo). Es el último writer de `derived.fact` (47.930 filas) `[EJECUCIÓN]`.

## 2. C10 — VALIDACIÓN (solo lectura)

```
python scripts/engine/c10_evaluate.py --sec-runs 161f128c… --ciks 0000904851 --tickers YPFD --scope all
```

- Veredicto: **WARN** (2/2 ejecuciones idéntico → determinista) `[EJECUCIÓN]`.
- 8 invariantes PASS: `SEC_GATES` (5 etapas PASS), `IDENTITY`, `PROVENANCE` (source_fact_ids y input_checkpoint_id en 100% de facts), `NO_DANGLING` (0), `NO_ORPHAN_ENTITY`, `BRIDGE` (YPFD con precios), `SEPARATION`, `NO_CROSS_OVERWRITE`.
- 1 WARN: `CNV_SCOPE` (motor CNV sin artefactos PG DEV; alcance documentado, no BLOCK). Contrato C10: WARN → pasa a C11 con alcance.

## 3. C11 — CERTIFICACIÓN

```
python scripts/engine/c11_certificar.py --run-id 161f128ca0d347ad94bbb27cefbdc024
```

- Acta: `c11-161f128ca0d347ad94bbb27cefbdc024`, veredicto **CERTIFICADA**, `cert_hash=b0b95154aee77f4cfc45de351f7a2ebdf04fc830e05e957ca00c192570cc2d34`, stages 5/5 PASS, `pipeline_version=e2e-sec-edgar-v1` `[EJECUCIÓN]`.
- Determinismo/idempotencia: re-ejecución devuelve el **mismo `cert_hash`** y **sin duplicar** la acta (`count(certifications run_id)=1`) `[EJECUCIÓN]`+`[TEST]` (test C).

## 4. C12 — PUBLICACIÓN (staging)

```
python scripts/engine/publisher.py --source derived.fact --target f8_ypf_fact \
  --run-id 161f128c… --pk fact_key \
  --filter "WHERE run_id = '161f128c…'" --min-rows 47930 [--dry-run]
```

- `--dry-run` → `DRY_RUN_OK`, 47.930 filas, `input_hash=fcaf382f…5ea`, `c10_pass=true`, cert enlazado (`certification_id=c11-161f128c…`, `cert_hash=b0b95154…`) `[EJECUCIÓN]`.
- Publicación real → **PUBLISHED** (swap atómico RENAME transaccional), `provenance_id=268`, 47.930 filas, mismo `input_hash` que dry-run. Segunda publicación (idempotencia) → `provenance_id=269`, mismo `input_hash` y `content_hash` (reproducible, sin duplicados vía swap) `[EJECUCIÓN]`.
- Provenance completa: fila en `staging._publications` con run_id, c10_ref (gate por etapa), `certification_id`, `cert_hash`, `content_hash`, `snapshot_hash/snapshot_rows` del target previo, `pk_columns=fact_key` `[EJECUCIÓN]`.
- Checks previos al gate (orden verificado): build > schema > volumen > PK (0 duplicados) > digest > gate C10/C11 > swap `[CÓDIGO]`.

## 5. Casos negativos (gate nunca se saltea)

| Caso | Input | Resultado | Evidencia |
|---|---|---|---|
| C10 no PASS | run `e1f6e26e…` (FAILED) con 47.930 filas presentes en staging | `BLOCK:C10_NO_PASS` | `[EJECUCIÓN]` |
| Volumen vacío | run CERTIFICADA `9331e02…` sin facts (tipo) | `BLOCK:staging vacio` (antes del gate) | `[EJECUCIÓN]` |
| Target inválido | `f8_negA` (mayúscula) | `target invalido (solo staging, [a-z0-9_])` | `[EJECUCIÓN]` |
| Sin C11 | `fetch_certification`→None | `BLOCK:C11_MISSING`, sin target residual | `[TEST]` (test G) |
| C11 NEGADA | veredicto NEGADA | `BLOCK:C11_NOT_CERTIFIED` | `[TEST]` (test D puro) |
| NEGADA con observaciones | `CERTIFICADA_CON_OBSERVACIONES` | `BLOCK:C11_NOT_CERTIFIED` | `[TEST]` (test D puro) |

## 6. Auditoría de estado y no-touch

- El run de la cadena **no** dejó etapas RUNNING huérfanas (0) y el conteo global de huérfanos no varía al repetir C10/C11/publish-dry-run `[TEST]` (test J).
- La cadena **no modifica datos**: conteos de `engine.checkpoints`, `parsed.facts`, `derived.fact` idénticos pre/post `[TEST]` (test K); C10/C11 solo leen (scripts sin writes), C12 solo crea tablas/registros en `staging` `[CÓDIGO]`.
- **Hallazgo pre-existente (no F8):** 15 etapas RUNNING huérfanas en runs de `C3_CNV_FETCH` y `S02_fetch` con timestamps 2026-09-06/07 (otros workstreams, anteriores al run F8). Documentado como residuo a reconciliar en F9; la cadena F8 no los introdujo ni los tocó `[EJECUCIÓN]`.

## 7. Tests y regresión

- Nuevo `tests/test_f8_e2e.py`: 13/13 PASS (cadena, determinismo, idempotencia, negativos, no-touch, provenance) `[TEST]`.
- Regresión relacionada 114/114 PASS: f2 (publisher), f6 (validation), f7 (certification), c11-contract, e2e_orchestrator(+integration), f050 `[TEST]`.

## 8. Cierre

Veredicto general: **PASS** — la cadena C10→C11→C12 opera de extremo a extremo sobre un run real: validación (WARN de alcance documentado) → certificación CERTIFICADA determinista → publicación atómica en staging con provenance y sin efectos colaterales; los bloqueos responden como contrata (C10_NO_PASS/C11_MISSING/C11_NOT_CERTIFIED/volumen). Gaps conocidos permanecen (S03-replace, M5, hist-writer, TLS/auth, cron-VPS, runtime legacy) como en F7; la publicación productiva queda fuera del alcance (C12 es solo staging por diseño).