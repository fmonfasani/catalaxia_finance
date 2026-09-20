# EVIDENCIA R4 — CAPA 11: CERTIFICACIÓN INDEPENDIENTE

| Campo | Valor |
|---|---|
| Fecha de emision | 2026-09-06 |
| Contrato | `docs/review/bymastocks_reingenieria/fase_definir/04_R4_CAPA11.md` (APPROVED → IMPLEMENTAR) |
| Decisión owner | C11 independiente de VALIDACIÓN; salida primaria `engine.certifications` (PostgreSQL); JSON solo evidencia; NO migrar criterio de 40_certificar; activación INFORMATIVA |
| Implementación | `scripts/engine/c11_certificar.py` · `migrations/engine/034_c11_certifications.sql` |
| Documento de test | `tests/test_c11_contract.py` |
| Estado | **VERIFICADO — PENDIENTE CERTIFICACIÓN** (la certificación es etapa separada) |

---

## ALCANCE DE ESTA EVIDENCIA

Alineación final de `04_R4_CAPA11.md` contra la implementación, la migración 034,
`tests/test_c11_contract.py` y la evidencia de ejecución. Se dejó el expediente
listo para la decisión de certificación; **NO se emite R4 CERTIFIED** en este documento.

---

## 1. CONTRATO C11 vs IMPLEMENTACIÓN

| Contrato | Implementación | Estado |
|---|---|---|
| LEE `engine.runs` + `engine.stage_runs` + `engine.checkpoints` | `_stages_final` (fila final por stage con report), `_checkpoints_ctx` (input_hash/code_version/contract_version), `runs` (run_id/status/mode/pipeline_version/git_commit) | ✅ |
| NO calcula datos | No calcula: reconstruye del report JSONB de C10; no toca capas 1-9 | ✅ |
| Única escritura `engine.certifications` (INV1) | `grep engine.certifications`: único `INSERT` en `c11_certificar.py` | ✅ |
| NO reemplaza VALIDACIÓN | Reusa `StageReport.validate` de C10 (le consume la evidencia, no la recalcula) | ✅ |
| NO acoplado a legado como autoridad (INV2) | Sin imports de `40_certificar`/`validar_suite`/`f6_sec`; mundos separados | ✅ |
| Veredicto determinista (INV3) | puro sobre evidencia; `cert_hash` sin timestamps/azar | ✅ |
| BLOCK→NEGADA / WARNING→CON_OBSERVACIONES / PASS→limpia (INV4) | `evaluar_evidencia` (ver §3) | ✅ |
| Salida primaria tabular; JSON solo artefacto (INV5) | acta persistida en columnas; `--json-output` opcional no primario | ✅ |
| Idempotente, sin reescritura (INV6) | `ON CONFLICT (run_id) DO NOTHING` + `ux_cert_run` + `certification_id = c11-<run>` | ✅ |
| INFORMATIVA, no bloquea API (INV7) | API no lee `engine.certifications` (R5 fuera) | ✅ |
| Artefacto JSON de evidencia opcional | `--json-output boletin/` | ✅ |

---

## 2. CRITERIOS C10 → C11 (estados VERDICT/NEGADA/CON_OBSERVACIONES)

Fila final por etapa (`_stages_final`: `row_number() OVER (PARTITION BY stage_id
ORDER BY id DESC)` con `report IS NOT NULL`) → clasificada por `gate_status`:

- `report` ausente o no-objeto → `INSUF`
- `gate_status` ausente o inválido → `INSUF`
- report que NO pasa la validación C10 (`StageReport.validate`) → `INSUF`
- `gate_status` contradictorio al report → `INSUF` (integridad rota)
- etapa declarada en `stage_runs` sin report → `INSUF` (azúcar/insumo: cobertura de etapas declaradas)
- válido → `PASS` / `WARNING` / `BLOCK` por `gate_status`

Veredicto (orden de precedencia):

1. `run.status` no terminal → **NEGADA** (corrida en curso)
2. `run.status = ABORTED` → **NEGADA**
3. sin `stage_runs` → **NEGADA**
4. `INSUF` > 0 → **NEGADA** (evidencia C10 insuficiente)
5. `BLOCK` > 0 → **NEGADA** (gate BLOCK)
6. `WARNING` > 0 (sin BLOCK/INSUF) → **CERTIFICADA_CON_OBSERVACIONES**
7. corrida `BLOCKED` sin etapa BLOCK declarada → **NEGADA** (inconsistencia)
8. resto (todo PASS, run OK) → **CERTIFICADA**

Estados permitidos por el CHECK de la tabla:
`CERTIFICADA | CERTIFICADA_CON_OBSERVACIONES | NEGADA`. La casuística C10→C11
agrega `INSUF` como clasificación intermedia interna (no es un veredicto
persistente, es un estado de entrada que deriva en `NEGADA`).

---

## 3. CERT_HASH DETERMINISTA (INV3)

`cert_hash = sha256_hex(canonical_json(payload))` con
`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.

Payload: `cert_rule` + `run_id` + `pipeline_version` + `run_status` +
`etapas_declaradas` (DISTINCT stage_id de `stage_runs`, ordenado) + `stages`
(report final JSONB por etapa, estado y gate_status, ordenado por stage_id).

- NO incluye `generado_at` ni aleatoriedad.
- El hash se reproduce recomputando a partir de la evidencia almacenada (test lo demuestra).
- El CHECK de la tabla exige `^[0-9a-f]{64}$` (sha256 hexadecimal minúscula).

**Matiz contractual a aclarar en el contrato:** §4.5 dice "2 corridas = igual".
Como `cert_hash` ancla a `run_id` (su `certification_id` es `c11-<run_id>`), dos
**corridas distintas** con `stage_runs` idénticas NO dan hashes iguales (son
certificaciones distintas, como dos documentos con distinto Nº de serie). La
garantía real y verificada es la del INV3: **la misma evidencia, re-evaluada,
da siempre el mismo `cert_hash`** (reproducibilidad intra-run + reproducción
desde la evidencia almacenada). Se recomienda reformular "2 corridas = igual" en
el contrato para reflejar esto.

---

## 4. IDEMPOTENCIA (INV6)

- `certification_id = f"c11-{run_id}"` (1:1 con la corrida).
- `ux_cert_run` (UNIQUE sobre `run_id`) + `ON CONFLICT (run_id) DO NOTHING`.
- Re-ejecución sobre el mismo run: no inserta duplicado, no reescribe el acta;
  re-lee la fila existente y la normaliza a JSON-safe (dataclass→dict) para que
  el acta devuelta sea idéntica en forma a la insertada (INV3).
- Test: `test_cert_hash_determinista_y_reejecucion_idempotente` (1 fila por run).

---

## 5. PROVENANCE / FK

- `run_id TEXT NOT NULL REFERENCES engine.runs(run_id)` (FK real).
- `generado_por = scripts/engine/c11_certificar.py` (traza del emisor).
- `pipeline_version` y `generado_at` registrados.
- `evidence` JSONB refiere stage_id + resultado + `report_sha256` + contexto de
  checkpoint (checkpoint_id/input_hash/code_version/contract_version cuando existe).
- Tests: `test_run_id_trazable_a_runs`, `test_provenance_presente`.

---

## 6. SEPARACIÓN DE RAW / CÁLCULO / PUBLICACIÓN

- **RAW:** C11 no toca `data/raw` (test `test_no_toca_raw_ni_archivos_de_datos`).
- **Cálculo:** snapshot de `engine.runs`/`stage_runs`/`checkpoints` antes/después
  de certificar → sin cambios (test `test_no_modifica_tablas_de_calculo`).
- **Publicación:** `grep "certifications" api/main.py` → ausente; C11 no publica
  (test `test_no_publica`). La API no lee C11 todavía (R5, fuera de esta ejecución).

---

## 7. AUSENCIA DE DEPENDENCIA DE LEGACY

`40_certificar` (legado → `certificacion_nueva`, SQLite, TXAR) se mantiene
intacto como referencia histórica. C11 no lo importa ni delega el sello (INV2).
Test `test_no_depende_de_legado_ni_pilotos` (analiza el código del script,
excluyendo el docstring que documenta el propio invariante).

---

## 8. MIGRACIÓN 034

`migrations/engine/034_c11_certifications.sql`, registrada por el runner único
(F-049) en `engine.schema_migrations`. Aplicada en dev (5433).

Tabla `engine.certifications` (verificada en la base dev):

- PK `certification_id`; `run_id` FK → `engine.runs(run_id)`.
- CHECK veredicto: `CERTIFICADA | CERTIFICADA_CON_OBSERVACIONES | NEGADA`.
- CHECK `cert_hash ~ '^[0-9a-f]{64}$'`.
- CHECKs de conteos ≥ 0 y `stages_pass+warn+block+insuf = stages_total`.
- `evidence JSONB`, `motivo`, `generado_por`, `generado_at TIMESTAMPTZ`.
- `ux_cert_run` (UNIQUE run_id) → idempotencia.
- Grants: `catalaxia_engine` = `SELECT, INSERT` (sin UPDATE/DELETE → INV6 a nivel de rol).

**Observación (alineación doc):** el snippet SQL de `04_R4_CAPA11.md` §4.2
proponía los nombres `cert_id` y `acta jsonb`; la migración real usa
`certification_id` y `evidence jsonb` y añade `objeto`, `cert_rule`, `motivo`,
`stages_insuf`. Es una evolución coherente con la implementación, no una
violación de contrato, pero el snippet del contrato quedó desactualizado.

---

## 9. MANIFEST

`engine/manifest.yaml` incluye:
- `scripts/engine/c11_certificar.py` → `etapa: C11_CERTIFICACION`, `clase: B`,
  nota "R4 — capa 11 independiente; lee runs/stage_runs/checkpoints y escribe
  unicamente engine.certifications".
- `migrations/engine/034_c11_certifications.sql` → tabla `engine.certifications`.

---

## 10. TESTS Y EVIDENCIA EJECUTADA

```
python -m pytest tests/test_c11_contract.py -q
=> 18 passed
```

| # | Requisito | Test |
|---|---|---|
| 1 | esquema + migration registry | `test_migracion_034_registrada_por_el_runner`, `test_engine_certifications_existe` |
| 2 | certificación de evidencia C10 válida | `test_certifica_run_con_evidencia_c10_valida` |
| 3 | evidencia incompleta → NEGADA | `test_evidencia_incompleta_es_NEGADA`, `test_sin_stage_runs_es_NEGADA`, `test_corrida_en_curso_o_abortada_no_certifica` |
| 4 | BLOCK → NEGADA / WARNING → CON_OBSERVACIONES / inconsistencia | `test_gate_BLOCK_es_NEGADA`, `test_warning_es_CERTIFICADA_CON_OBSERVACIONES`, `test_corrida_BLOCKED_sin_etapa_BLOCK_inconsistente` |
| 5 | cert_hash determinista + idempotencia | `test_cert_hash_determinista_y_reejecucion_idempotente` |
| 6 | FK trazable | `test_run_id_trazable_a_runs` |
| 7 | provenance | `test_provenance_presente` |
| 8 | sin side-effects sobre tablas de cálculo | `test_no_modifica_tablas_de_calculo` |
| 9 | no publica (INV7/R5) | `test_no_publica` |
| 10 | sin dependencia de legado (INV2) | `test_no_depende_de_legado_ni_pilotos` |
| 11 | no toca RAW | `test_no_toca_raw_ni_archivos_de_datos` |
| 12 | grants SELECT+INSERT sin UPDATE/DELETE (INV6 a nivel de rol) | `test_grant_de_la_tabla_no_permiten_reescribir` |
| 13 | motivo queda registrado para prueba de no-limpiado | `test_motivo_queda_registrado_para_no_limpia` |

Regresión relacionada: `tests/test_c11_contract.py` + `tests/test_f050_lifecycle_s00_s02.py`
`=> 37 passed`.

Barrido global (para contexto): 781 passed, 43 failed, 19 skipped. **Los 43
fallos son pre-existentes y ajenos a C11** (base dev sin `market_raw_runs`, sin
datos de identity/ratios, defecto conocido F-029 en `hashout`) y NO afectan el
contrato C11; no se atacaron en este expediente por estar fuera del alcance R4.

---

## 11. GATES DE PASO (evidencia del cumplimiento, SIN cerrar certificación)

| Gate del contrato §6 | Evidencia |
|---|---|
| Migración 034 aplicada (dev) | registrada + tabla verificada en 5433 |
| `c11_certificar.py` produce acta con veredicto esperado sobre un run histórico | corrida real certificada (ej. `e4e7d0bb…` → CERTIFICADA; corridas de test → NEGADA/BLOCK/CON_OBSERVACIONES) |
| Determinismo demostrado (mismo `cert_hash` en 2 corridas) | reproducibilidad intra-run + recomputo desde evidencia almacenada (ver §3) |
| Run con BLOCK → NEGADA | `test_gate_BLOCK_es_NEGADA` + filas `NEGADA / gate BLOCK` |
| `test_c11_contract.py` verde y sin side-effects sobre tablas de cálculo | 18 passed; `test_no_modifica_tablas_de_calculo` |
| No se modificaron `validar_suite`/`f6_sec`/`40_certificar` | sin imports en C11; legado intacto |
| La API no se bloquea (activación informativa) | `api/main.py` no lee C11 |

---

## DISCREPANCIAS / NO CONFORMIDADES

1. **`docs/review/R4_CAPA11_EVIDENCIA.md` faltaba** — referenciado en el contrato
   (L62), en el header de la migración 034 y en el docstring del test, pero no
   existía. **Corrección aplicada en esta ejecución:** creación de este documento
   para completar el expediente (patrón par `*_CERTIFICACION.md` + `*_EVIDENCIA.md`
   de R2/R3).
2. **Contrato §4.2 snippet desactualizado** (nombres `cert_id`/`acta` vs reales
   `certification_id`/`evidence`; y columnas añadidas). Documentación únicamente,
   sin impacto funcional; se recomienda alinear el snippet al contrato.
3. **Redacción "2 corridas = igual" en §4.5** en tensión con anclar `cert_hash`
   a `run_id`. No es un defecto de código; se recomienda reformular en el contrato
   para reflejar la garantía real (reproducibilidad de la misma evidencia).
4. **Observación cosmética:** docstring de `c11_certificar.py` L30 escribe
   "cerH_hash" en lugar de "cert_hash" (comentario de solo-título; sin impacto).
   No se modificó por no constituir discrepancia contractual (no tocar código
   salvo discrepancia contractual concreta).

---

## CORRECCIONES REALIZADAS (solo las estrictamente necesarias para el expediente)

- **Creación de `docs/review/R4_CAPA11_EVIDENCIA.md`** (este documento), que
  estaba referenciado pero no existía.

No se modificó código de `c11_certificar.py` ni de la migración 034 en esta
alineación: la implementación cumple el contrato y los invariantes. (Las
correcciones de código de la sesión anterior — `evaluar_evidencia`, `cert_hash`,
guard sin stage_runs, normalización del acta re-leída — ya quedaron validadas
por los 18 tests.)

---

## ESTADO

**VERIFICADO — PENDIENTE CERTIFICACIÓN.**

Invariantes R4 (INV1–INV7) cumplidos y con evidencia reproducible. Sin
no-conformidad contractual abierta de C11; los 43 fallos globales son ajenos.
La certificación se emite en etapa separada (mismo patrón que R2/R3).

Referencias:
- Contrato: `docs/review/bymastocks_reingenieria/fase_definir/04_R4_CAPA11.md`
- Implementación: `scripts/engine/c11_certificar.py`
- Migración: `migrations/engine/034_c11_certifications.sql`
- Tests: `tests/test_c11_contract.py`
- Manifest: `engine/manifest.yaml`
