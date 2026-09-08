# 22 — Implementation Result F10

Cierre de la máquina de estados de ejecución. Solo DEV
(`catalaxia_engine@127.0.0.1:5433`). Producción (5432) no se tocó en ningún
comando de esta fase.

## 1. Máquina de estados — antes

```
PLANNED → READY → RUNNING → VALIDATING → {PASSED | FAILED}
FAILED → FIXING → RERUNNING → VALIDATING
PASSED → CHECKPOINTED → CERTIFIED
```

`RunState` no existía como enum (`engine.runs.status` = `TEXT` libre). Ante
una excepción, `run_scope` cerraba el *run* (`ABORTED`, y sólo si
`run_id is None`) pero **nunca** la *etapa*: no había ninguna transición de
`StageState` que representara "murió sin decir nada". Una etapa que
alcanzaba a escribir `RUNNING` y luego moría quedaba en `RUNNING` para
siempre — el defecto que F9 encontró 16 veces.

## 2. Máquina de estados — después

```
PLANNED, READY, RUNNING, VALIDATING, FIXING, RERUNNING  →  ABORTED  (nuevo)
FAILED, PASSED, CHECKPOINTED, CERTIFIED                  ↛  ABORTED  (protegidos)
ABORTED  →  (nada; terminal)
```

`run_scope(..., stage_id=STAGE_ID)` — parámetro opt-in, retrocompatible — cierra
ahora la etapa vía `abort_stage_if_open` en el mismo `except` que cierra el
run, **independientemente** de quién sea dueño del cierre del run (modo
standalone o modo E2E compartido con orquestador; test M lo prueba
explícitamente para el modo E2E).

## 3. Defecto corregido

Transversal, confirmado por evidencia (no por intuición): 6 escritores reales
de `stage_runs` (`S00`–`S04` + `C3`), todos con el patrón idéntico, todos
pasando por el mismo `run_scope` en `engine/db.py`. La corrección vive en un
solo punto (`abort_stage_if_open` + la firma extendida de `run_scope`) más
un parámetro de una línea en cada uno de los 6 call sites. Los otros 8
scripts que usan `run_scope` no escriben `stage_runs` (verificado, 0
ocurrencias de `record_stage_transition`) y no necesitaron ningún cambio.

`RUN ABORTED ⇒ STAGE ABORTED` quedó establecido como la única semántica
sostenida por evidencia: código (los 6 escritores comparten el patrón),
datos (16/16 residuos con run ABORTED y etapa RUNNING, 0 casos de lo
contrario) y tests (ninguno de los 3 archivos de lifecycle existentes afirma
nada sobre `stage_runs.state`).

## 4. Históricos — tratados

**Los 16 residuos de F9 NO se tocaron.** Decisión (C) — legacy/test residue,
documentada en `22_F10_STATE_MACHINE.md` §"Históricos". Re-verificados en
Paso 9: **16/16 siguen exactamente en `RUNNING`**, sin ningún `UPDATE`. No se
consideró necesario reconciliarlos porque C10/C11/C12 los tratan
idénticamente con `state='RUNNING'` o `'ABORTED'` — deciden por
`gate_status`, no por `state` — así que no bloquean ni certificación ni
publicación en ninguno de los dos valores.

## 5. Tests

`tests/test_f10_state_machine.py` — nuevo, cubre los 14 puntos pedidos
(A–N, con sub-casos): **35 passed, 1 skipped** (skip intencional:
`ABORTED→ABORTED` no aplica a sí mismo). Corridos contra DEV real, sin mocks
de base de datos.

Destacan:
- **E/E2**: integración real (`run_scope` con excepción real) — run y etapa
  terminan ABORTED juntos, con `prev_state` apuntando al último estado real
  (no se inventa evidencia).
- **F/F2/F3**: la matriz completa de `TRANSITIONS` — 8 estados que NO pueden
  ir a ABORTED, probados uno por uno.
- **G/H**: C11 (`certificar_run`) devuelve `NEGADA`, y la regla pura de C12
  (`gate_decide`) bloquea — **sin modificar ninguno de los dos scripts**.
- **I/J**: idempotencia y no-duplicación del cierre, verificado contando
  filas antes/después.
- **K**: el `main()` REAL de S00/S01/S02 (no una simulación), con el fallo
  inyectado exactamente donde ocurrió en los 16 casos históricos (justo
  después de escribir RUNNING, antes de VALIDATING).
- **M**: modo E2E — la etapa se cierra aunque el run compartido no (el
  orquestador sigue siendo dueño del run, sin cambios).
- **N2**: retrocompatibilidad explícita — sin `stage_id`, cero filas nuevas.

## 6. Regresión

11 archivos, 211 tests (lifecycle ×3, orquestador ×2, C11 ×1, F5–F10 ×6, F8
E2E ×1): **175 passed, 1 skipped, 4 failed**.

Los 4 `FAIL` son **PREEXISTENTES**, verificado con `git diff` acotado a los
archivos que tocó F10 (mi único cambio en `c3_cnv_fetch.py` es la línea
`stage_id=STAGE_ID`; el resto del diff de ese archivo — incluida la firma de
`load_identity` que causa el fallo — ya estaba ahí antes de F10). Misma
familia que F9 documentó ("identidad/universo CNV stale"): Central Puerto
S.A. perdió su CUIT autoritativo en DEV (3 tests), y un guard de
`scripts/market/m1_symbol_mapping.py` no relacionado con la máquina de
estados (1 test, de la suite de F5). Cero fallos en archivos que F10 tocó.

## 7. E2E

Demostrado en dos niveles:

- **Vía shell, comando real**: `python scripts/engine/s00_smoke.py` contra
  `catalaxia` DEV, sin inyección — `run_id=2c1d18ee9042…`, gate `PASS`,
  etapa terminó en `CHECKPOINTED` con `gate_status=PASS`, run en `OK`. Cero
  filas `ABORTED` — el camino feliz no se activa nunca.
- **Vía pytest, contra el `main()` real**: los 5 escenarios pedidos (run
  exitoso, run FAILED [estructura sin cambios, cubierta por regresión
  preexistente], run ABORTED, etapa abortada, reintento/idempotencia) están
  cubiertos por los tests L, K, E, I/J respectivamente, todos contra DEV
  real.

## 8. Impacto en C10/C11/C12

**Cero modificaciones de código** en los tres (`c10_evaluate.py`,
`c11_certificar.py`, `publisher.py`) — verificado con `git diff`, sin
cambios. Comportamiento verificado igual antes y después: los tres leen
`gate_status` (siempre `NULL` en una fila `RUNNING` o en una `ABORTED` — el
mismo `NULL`), nunca `state` para decidir. Test G prueba que C11 sigue
negando; test H que la regla de C12 sigue bloqueando.

## 9. Auditoría post-implementación (Paso 9), los 8 puntos

| # | verificación | resultado |
|---|---|---:|
| 1 | nuevos RUNNING huérfanos (>1h, sin proceso) | **0** |
| 2 | RUNNING después de ABORTED (misma run+stage) | **0** |
| 3 | checkpoint después de ABORTED | **0** |
| 4 | certificación no-NEGADA de un run con etapa ABORTED | **0** |
| 5 | publicación de un run con etapa ABORTED | **0** |
| 6 | contaminación cross-run (`prev_state` sin predecesor propio) | **0** |
| 7 | pérdida de provenance (16 históricos alterados) | **0** (16/16 intactos) |
| 8 | escritura en producción (5432) | **0** (toda la fase corrió en 5433) |

## 10. Recomendación de F11

**TLS `verify=False` + auth/CORS de la API** (gaps 1 y 2 de
`22_F10_GAP_UPDATE.md`). Los dos son `BLOCKER`, sin dependencias, y no tienen
ningún overlap de archivos ni de tablas con lo que cerró F10. Es exactamente
la prioridad que F9 ya había fijado — F10 no la reordena, sólo tacha el gap
#11 (control) que corría en paralelo.

---

Archivos: `22_PRE_F10_STATE.md`, `22_F10_STATE_MACHINE.md`,
`22_F10_GAP_UPDATE.md`, este resultado, `tests/test_f10_state_machine.py`.
Código productivo modificado: `engine/states.py`, `engine/db.py`,
`scripts/engine/{s00_smoke,s01_identity,s02_fetch_ypf,s03_parse_ypf,s04_normalize,c3_cnv_fetch}.py`
(un parámetro cada uno). C10/C11/C12: intactos. Legacy: intacto. Producción:
intacta. F11 no iniciado.

**STEP_21_STATUS = PASS**
**NEXT_PHASE = F11**

DETENIDO — sin implementación de gaps de producción en F10; F11 no iniciado.
