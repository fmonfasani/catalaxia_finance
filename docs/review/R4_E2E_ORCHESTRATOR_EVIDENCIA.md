# EVIDENCIA R4 — ORQUESTADOR E2E SEC/EDGAR (OPCIÓN A)

| Campo | Valor |
|---|---|
| Fecha de emision | 2026-09-06 |
| Contrato | Diseño R4 aprobado (Opción A — run_id E2E compartido) |
| Decisión | UN `run_id` E2E agrupa S00→S04; cada etapa registra su `stage_run` bajo ese run; C11 NO se modifica |
| Implementacion | `scripts/engine/e2e_orchestrator.py` + cambios mínimos en `db.run_scope()` y etapas s00..s04 |
| Documento de test | `tests/test_e2e_orchestrator.py`, `tests/test_e2e_orchestrator_integration.py` |
| Estado | **VERIFICADO — MECANISMO LISTO PARA GOLDEN RUN** (certificación = etapa separada) |

---

## 1. DECISION ARQUITECTÓNICA

El pipeline real S00→→S04 ejecuta **cada etapa como script independiente** y cada
una abría su propio `run_id` (`run_scope` por etapa). C11, en cambio, certifica
**un solo run** que agrega N `stage_runs` bajo el mismo `run_id`. La brecha era
estructural. Se resolvió con la **Opción A** (diseño aprobado): un orquestador que
crea UN run E2E y propaga su `run_id` a las 5 etapas vía `ENGINE_E2E_RUN_ID`.

---

## 2. IMPLEMENTACIÓN vs CONTRATO

| Requerimiento | Implementación | Estado |
|---|---|---|
| Orquestador crea UN run E2E | `edb.start_run(engine, settings, "e2e-sec-edgar-v1")` | ✅ |
| `pipeline_version` E2E explícito | `e2e-sec-edgar-v1` | ✅ |
| 5 `stage_runs` (S00..S04) bajo el mismo `run_id` | cada etapa con `run_scope(..., run_id=ENGINE_E2E_RUN_ID)` | ✅ |
| NO crear 5 `engine.runs` durante un E2E | `run_scope` con `run_id` no hace `start_run` | ✅ |
| Ejecución individual intacta | `run_scope` sin `ENGINE_E2E_RUN_ID` → `start_run` normal | ✅ |
| Detener cadena ante fallo | orquestador corta al primer exit≠0 (ver §6) | ✅ |
| Run E2E terminal nunca RUNNING | `finally` en orquestador cierra ABORTED/BLOCKED/OK | ✅ |
| C11 consume el run E2E sin cambios | estructura `runs/stage_runs/checkpoints` compatible | ✅ |

---

## 3. CHECKPOINTS (decisión R4)

En modo E2E las etapas **NO escriben checkpoints individuales**. Motivo: un run
E2E que aborta en una etapa posterior (p.ej. S04) no debe dejar checkpoints
dangling bajo un run no-OK (invariante F-031; el rol app no puede DELETE).
S04 en modo E2E resuelve su insumo S03 desde el propio run (stage_runs), no desde
`engine.checkpoints`. En modo individual el comportamiento previo se conserva
(bloque de checkpoint intacto).

```
INDIVIDUAL:  cada etapa escribe su checkpoint (normal, sin cambios)
E2E        :  sin checkpoint por etapa; S04 lee S03 del mismo run_id
```

---

## 3. EJECUCIÓN INDIVIDUAL vs E2E (verified)

| Escenario | run creado | stage_runs |
|---|---|---|
| `s00_smoke.py` sin env | run propio `383e08a0…` pv=`s0-bootstrap-v1` | S00_bootstrap |
| `s00_smoke.py` con `ENGINE_E2E_RUN_ID=X` | NO crea run; usa X | S00_bootstrap bajo X |
| `e2e_orchestrator.py` éxito (todas PASS) | 1 run E2E (pv `e2e-sec-edgar-v1`) | 5: S00..S04 |
| `e2e_orchestrator.py` falla etapa | 1 run E2E ABORTED/BLOCKED | 1 falló; cadena cortada |

---

## 4. C11 COMPATIBLE

C11 lee el run E2E como cualquier run: `_stages_final` (fila final con report por
`stage_id`), `evaluar_evidencia` (PASS/WARNING/BLOCK/INSUF), `cert_hash`.
Demostrado: el run E2E sintético con 5 stage_runs PASS + report → `CERTIFICADA`
stages_total=5. No se modificó `c11_certificar.py`, ni migración 034.

---

## 5. TESTS

| Suite | Resultado |
|---|---|
| `tests/test_e2e_orchestrator.py` (8) | **8 PASS** |
| `tests/test_e2e_orchestrator_integration.py` (2) | **2 PASS** |
| `tests/test_c11_contract.py` (18) | **18 PASS** |
| `tests/test_f050_lifecycle_s00_s02.py` (19) | **19 PASS** |
| `tests/test_engine_run_lifecycle.py` (8) | **8 PASS** (invariant F-031 restaurado) |
| Suite completa | 792 PASS, 43 fail previos (CNV/ratios/f038 → dependen de identity_v1/envio), 19 skipped |

---

## 6. ARCHIVOS TOCADOS

|mFile | Cambio |
|---|---|
| `engine/db.py` | `run_scope(..., run_id=None)` cuando run_id provisto no abre/cierra run |
| `scripts/engine/s00_smoke.py` | usa env; checkpoint con ON CONFLICT e omitido en E2E |
| `scripts/engine/s01_identity.py` | idem (checkpoint omitido en E2E) |
| `scripts/engine/s02_fetch_ypf.py` | idem |
| `scripts/engine/s03_parse_ypf.py` | idem |
| `scripts/engine/s04_normalize.py` | checkpoint_s03 en modo E2E lee del run E2E |
| `scripts/engine/e2e_orchestrator.py` | NUEVO: orquestador del pipeline |
| `engine/manifest.yaml` | alta del orquestador |
| `tests/test_e2e_orchestrator.py` | NUEVO (8 tests) |
| `tests/test_e2e_orchestrator_integration.py` | NUEVO (2 tests, subproceso real) |

---

## 7. RIESGO RESTANTE

- El Golden Run real requiere precondiciones **de datos** (identity_v1 poblado, SEC
  accesible, catálogo en disco) que son del entorno, no del orquestador.
- Falta una corrida E2E **real** de punta a punta (NO se ejecutó por orden).
- `s00` ahora usa `ON CONFLICT` (arregla idempotencia previa que chocaba en 2da corrida).

---

## 8. CLASIFICACIÓN

VERIFICADO POR CÓDIGO: propagación de run_id, cortocircuito ante fallo.
VERIFICADO POR TEST: 8+2 tests del orquestador + 18 C11 + 19 F-050 + 8 lifecycle.
VERIFICADO POR EJECUCIÓN: run E2E con 5 stage_runs PASS + C11 CERTIFICADA usando
data degenerada (sin SEC). Golden Run real NO ejecutado (orden de no ejecutar).

---

Estado: **READY_FOR_E2E** (no se ejecutó el Golden Run real por instrucción).