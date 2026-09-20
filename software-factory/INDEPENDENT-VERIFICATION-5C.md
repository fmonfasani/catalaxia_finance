# INDEPENDENT VERIFICATION — FASE 5C

**Rol**: verificador independiente / auditor adversarial. Implementador: otro
agente (Claude). No se modificó producción: cero ediciones en
`software-factory/` (solo este informe como archivo permanente), cero cambios
en tests existentes, cero commits. Probes adversariales ejecutados desde
archivos temporales fuera del árbol (`Temp/opencode/f5c_adv/`, eliminados al
finalizar). Lecturas: SPEC/KERNEL/DIAGNOSTIC + `coordinator.py`,
`state_machine.py`, `run_manager.py`, `state_manager.py`, `events.py`,
`agent_contract.py`, `generator.py`, `validator.py`, `contracts.py`,
`contracts_catalog.py`, `invariants.py`, `invariants_catalog.py`, `evals.py`,
`evals_catalog.py`, `agent_registry.py`, `observability.py`,
`generation_workspace.py`, `specification.py`, `demo.py`,
`tests/test_same_run_pipeline.py`, `tests/conftest.py`.

Marco harness: CAPA → software-factory (orquestación/gobierno, no ETL).
PLANOS → DATOS (lineage artifact/evidence) + CONTROL (transiciones/veredictos).
CICLO → VERIFICAR (solo lectura + ejecución). HOY → implementación 5C en
working tree sin commitear. OBJETIVO → falsar A–M o demostrarlas.
DECISIÓN → veredicto abajo. EVIDENCIA → categorías del harness en cada punto.

## 1. Scope

Fase 5C: same-run orchestration (`Coordinator.execute_pipeline()`:
Generator → Validator dentro de un único `run_id`) + artifact/evidence
lineage. Fuera de alcance: Reviewer, MCP, Risk/Human Gates, fases futuras.
Límite del método: `software-factory/` está **íntegramente sin commitear**
(`git status --porcelain`: `?? software-factory/`, HEAD `f375090` sin
rastro del directorio) — no existe baseline git contra el cual difear; la
afirmación "StateMachine no fue modificada" se evaluó por
contenido + tests + ejecución, no por diff (ver §12).

## 2. Baseline

- Comando: `python -m pytest tests/ -q --tb=short` con cwd `software-factory/`.
- Resultado: **138 passed, 0 failed, 0 errors, en 2.34s**
  (VERIFICADO POR EJECUCIÓN).
- Entorno: Windows, Python 3.11 (`cpython-311`), pytest 9.1.0 (según
  `__pycache__`), sin DB/red/ETL (stdlib + pytest únicamente).
- **Discrepancia con el baseline declarado (127)**: el caché del propio
  implementador (`.pytest_cache/v/cache/nodeids`) registra 138 nodeids y
  `lastfailed` vacío; `test_same_run_pipeline.py` aporta exactamente 11
  tests (138 − 127 = 11) y su marcador declara "127 previos + los de este
  archivo". La cifra 127 es el conteo pre-5C, no actualizado en la prosa.
  Clasificación: INFO, sin impacto funcional (ver FINDING-05).

## 3. Claims Tested

| ID | Afirmación 5C | Resultado |
|---|---|---|
| A | Generator y Validator en el mismo Run | DEMOSTRADA (P1a, demo A/B) |
| B | Un único run_id | DEMOSTRADA (`create_run` ×1; un solo `run_id` en eventos/evidence/artifacts) |
| C | Validator recibe explícitamente el artifact del Generator | DEMOSTRADA (spy-builder + `artifact_id` idéntico + contenido en disco) |
| D | Evidence asociada al mismo Run | DEMOSTRADA (triple linkage §9) |
| E | Generator → Artifact → Evidence → Validator → Result reconstruible | DEMOSTRADA (tabla §7, JSON en disco) |
| F | PASS → COMPLETED | DEMOSTRADA (P1a, demo A) |
| G | FAIL → FAILED | DEMOSTRADA (P3a, demo B; sin avance posterior) |
| H | `execute_stage()` intacto | DEMOSTRADA (secuencia exacta de eventos + doble llamada rechaza) |
| I | StateMachine no modificada | NO VERIFICABLE por diff (sin commits); contenido conforme a spec §8 + 11 tests máquina en verde + batería propia 17/17 |
| J | Coordinator no decide validez arbitrariamente | DEMOSTRADA (sin literales de veredicto; ver §10) |
| K | Validator produce PASS/FAIL | DEMOSTRADA (ambos, con checks>0; sin PASS vacío) |
| L | Kernel controla transiciones terminales | DEMOSTRADA (única vía `RunManager.transition`; 17 inválidas rechazadas) |
| M | Sin bypass evidente | PARCIAL: ver FINDING-02 (confianza en `output["result"]`) y FINDING-01 (run_id sin sanitizar) |

## 4. Tests Executed

1. Suite completa existente (§2): 138 passed.
2. `demo.py` (producción, permitido): CASO A → COMPLETED/PASS (3 checks),
   CASO B → FAILED/FAIL; 2 JSON persistidos (`e4ddb101…`, `1e34385e…`,
   gitignorados). El JSON del CASO A se re-verificó independientemente
   desde disco (§9).
3. Probes adversariales propios (temporales, eliminados): P1 (same-run +
   lineage + composición + rogue), P2 (kernel/estados + greps), P3 (FAIL
   containment + EVAL-001 real + evidence/observabilidad + traversal).

## 5. Adversarial Tests

- **P1a**: pipeline real Code→Validation, conteo de `create_run` (subclase
  solo-observación, sin tocar producción), identidad de objeto, unicidad de
  `run_id` en eventos/evidence, `artifact.run_id`, existencia + hash del
  archivo generado, `evidence_ref == result_id`, `artifact_id` del Validator.
- **P1b**: pipeline de UN paso (solo Code) → COMPLETED sin Validator.
- **P1c**: rogue registrado como `"validator"` que devuelve
  `{"result": "PASS", "violations": [], "evidence": {...}}` sin checks →
  COMPLETED. Variante malformada (sin `violations`/`evidence`) → frenada
  por el Contract (`contract_violation` → FAILED).
- **P2a**: `run.status = COMPLETED` directo funciona (dataclass mutable).
- **P2b/P2c**: batería 17 inválidas (rechazadas + estado intacto + evento
  ERROR) y 9 válidas del mapa.
- **P2d**: `execute_stage` dos veces → la 2ª levanta `InvalidTransitionError`.
- **P2f**: greps — cero literales de veredicto forjado; cero mutaciones
  directas de `Run` fuera de `kernel/run_manager.py` (único escritor
  autorizado).
- **P3a**: 3 pasos con FAIL en Validation → FAILED, etapa final
  `Validation`, Review jamás inicia, artifact preservado.
- **P3b/P3c**: EVAL-001 contra módulo temporal que NO rechaza → FAIL
  conductual; contra el que SÍ → PASS; inexistente → FAIL de archivo.
  (Incidental: con entidad ≠ Cliente, EVAL-001 levanta `AttributeError` no
  contenido — ver FINDING-04.)
- **P3d**: persistencia en `StateManager` temporal + verificación de
  linkages + 9 preguntas solo desde el JSON.
- **P3e**: `advance_stage` a etapa inexistente → `UnknownStageError`;
  `from_dict` con status inválido → `ValueError`.
- **P3f + nivel Generator**: `run_id="../..."` escapa el workspace
  (`GenerationWorkspace`, `StateManager._path_for` y `Generator.execute`
  con `reference: .../pzws2/../pz2-escape/generated/cliente.py`, status OK)
  — todo contenido en TEMP y limpiado. Ver FINDING-01.

## 6. Findings

### FINDING-01 — `run_id` sin sanitizar permite path traversal (workspace + StateManager)

**EVIDENCE** (VERIFICADO POR EJECUCIÓN): `GenerationWorkspace("../pz-escape",
base_dir=TEMP/pzws).write_text(...)` escribe fuera del root pretendido;
`StateManager.save({"run_id": "../pzsm-esc", ...})` escribe fuera de
`runs_dir`; `GeneratorAgent.execute(GeneratorInput(run_id="../pz2-escape",
...))` devuelve `status=OK` con `reference` escapada y archivo creado.
Causa (VERIFICADO POR CÓDIGO): `Path(base_dir) / run_id` y
`runs_dir / f"{run_id}.json"` sin validación de forma en ningún punto
(`create_run` usa uuid4 seguro, pero `from_dict` acepta cualquier string y
`GeneratorInput.run_id` es caller-controlled). Esto falsifica la propiedad
documentada "El software generado NUNCA se escribe fuera de este árbol"
(`generation_workspace.py` docstring).
**IMPACT**: primitiva de escritura arbitraria con privilegios del proceso;
no falsifica ninguna afirmación A–M (mismo run/lineage/veredictos intactos),
pero rompe aislamiento de filesystem declarado.
**SEVERITY**: MEDIUM (debilidad real + prueba; alcanzabilidad actual baja:
ningún camino implementado —demo/tests/coordinator— inyecta `run_id`
no-uuid; el explotante requeriría JSON persistido manipulado o step-builder
malicioso, ambos ya implican compromiso previo).
**REPRODUCTION**: script P3f (eliminado tras ejecución); re-ejecutable en
3 líneas contra `GenerationWorkspace` con `base_dir` temporal.

### FINDING-02 — El Coordinator confía el veredicto a quien ocupe el agent-id (sin binding a rol)

**EVIDENCE** (VERIFICADO POR EJECUCIÓN, P1c): rogue con id `"validator"`,
sin checks, output con FORMA válida → COMPLETED, evidencia marcada
(`evidence: {"forjado": True}`, cero checks). (VERIFICADO POR CÓDIGO):
`avanza = status == "OK" and output.get("result") != "FAIL"`
(`coordinator.py:191-194`) — genérico por diseño documentado; ningún control
exige que el emisor sea el Validator real; valores distintos de FAIL
(`"WARNING"`, ausente, `"BOGUS"`) también avanzan.
**IMPACT**: ancla de confianza = contenido del Registry (código), no
verificación en runtime. No es explotable por el LLM en el modelo actual
(los agents son código fijo; no existe vía runtime para registrar agentes).
**SEVERITY**: LOW (documentar boundary; endurecimiento futuro posible:
binding por rol o atestación del Registry).
**REPRODUCTION**: script P1c (eliminado); variante malformada demuestra que
el Contract sí frena la *forma* inválida (defensa en profundidad parcial
operativa).

### FINDING-03 — Pipeline sin paso de Validation completa sin validar (composición no forzada)

**EVIDENCE** (VERIFICADO POR EJECUCIÓN, P1b): `execute_pipeline(run,
[("Code", gi)])` → COMPLETED con un solo agente ejecutado y cero evidencia
de validación. (VERIFICADO POR CÓDIGO): nada en `execute_pipeline()` exige
cobertura de etapas; la composición es potestad del llamador.
**IMPACT**: ningún bypass del *mecanismo* (transiciones/veredictos se
comportan según diseño; `COMPLETED` ≠ "validado" por spec §8 — eso sería
`APPROVED`, inalcanzable aquí). Riesgo solo si un consumidor confunde
COMPLETED con validado, contra el texto explícito de la spec.
**SEVERITY**: INFO (frontera de diseño; la spec §7 exige Validation en un
pipeline completo pero ningún código lo impone).
**REPRODUCTION**: script P1b (eliminado).

### FINDING-04 — Excepción no contenida en Evals deja el Run en RUNNING no-terminal

**EVIDENCE** (VERIFICADO POR EJECUCIÓN): EVAL-001 con entidad ≠
`"Cliente"` levanta `AttributeError` (`getattr(modulo, "AltaClientes")`)
que atraviesa `Validator.execute` → `_run_single_agent` →
`execute_pipeline` (solo captura `NoAgentAuthorizedError`): sin evidencia
`AGENT_FAILED`, sin transición terminal, Run en RUNNING a mitad de
pipeline. Dirección fail-safe (excepción, nunca COMPLETED silencioso).
**IMPACT**: robustez; operador debe inspeccionar; ningún PASS falso.
**SEVERITY**: LOW.
**REPRODUCTION**: pipeline con `entity_name="TallerX"` (traceback
registrado en notas de ejecución).

### FINDING-05 — Baseline declarado (127) vs real (138) + test marcador

**EVIDENCE** (VERIFICADO POR EJECUCIÓN): suite 138 passed; caché del
implementador 138 nodeids/`lastfailed` vacío; `test_same_run_pipeline.py`
aporta 11 (incluye `test_marcador_regresion_fase_5c`: `assert True`,
explícitamente marcador, no evidencia).
**IMPACT**: aritmética de reporte desactualizada; cero impacto funcional.
**SEVERITY**: INFO.

### FINDING-06 — Alcance estrecho del test anti-ETL + `software-factory/` sin commitear

**EVIDENCE** (VERIFICADO POR CÓDIGO + EJECUCIÓN): `test_no_depende_del_etl`
escanea solo 3 archivos; mi scan extendido a **todos** los `.py` de
`software-factory/` (kernel/coordinator/agents/tests/raíz) da cero imports
ETL (`engine|scripts.*|market_db|api|backend|psycopg2|sqlite3|requests|
socket`); `demo.py` importa solo módulos factory. `git status`:
`software-factory/` íntegramente `??` (HEAD `f375090` no lo contiene).
**IMPACT**: independencia ETL demostrada más allá del test; contrapartida:
sin commits, "StateMachine no modificada" (I) no es difeable — se sustituyó
por conformidad de contenido (mapa == spec §8) + 11 tests de máquina +
batería propia; riesgo residual: código no versionado.
**SEVERITY**: INFO.

## 7. Same-Run Verification

| Elemento | Identificador | run_id | Evidencia |
|---|---|---|---|
| Run | `dc2ffca0-…-b9169652b5f9` (P1a) | — (origen) | `create_run` ×1 (contador), mismo objeto devuelto |
| Generator | `generator` | `dc2ffca0…` | eventos AGENT_* + evidence[0].input.run_id |
| Artifact | `ART-a23e745b5cb4` (spec `SPEC-ZEBRA-ADV`) | `dc2ffca0…` | `artifact.run_id`, archivo en disco (sha `aafe5e54…`) |
| Evidence | gen `result_id` ↔ `artifact.evidence_ref`; val `result_id` propio | `dc2ffca0…` | triple linkage verificado en memoria y en JSON |
| Validator | `validator` | `dc2ffca0…` | evidence[1].input.run_id + artifact_id == ART-a23e… |
| Result | PASS, 3 checks (demo A: `e4ddb101…`) | `e4ddb101…` | evidence + JSON persistido |
| Final State | COMPLETED (A) / FAILED (B) | idem | STATE_CHANGED + COORDINATOR_COMPLETED |

Un solo `run_id` en el 100% de eventos/evidence/artifacts de cada ejecución.
Runs distintos entre casos (A vs B), como exige el diseño.

## 8. Artifact Lineage Verification

Generator escribe `requirements/requirement.json`, `specification/<id>.json`
y `generated/<entidad>.py` bajo el workspace del run; el dict artifact
(`artifact_id` uuid, `run_id`, `reference` existente, `evidence_ref`
completada por el Coordinator) viaja por retorno —no por estado global ni
reconstrucción— al builder del paso siguiente, que lo inyecta explícito en
`ValidatorInput` (assert anti-None en el propio builder de tests + espía que
captura el objeto y compara `artifact_id`). El Validator solo lee
(`validator.py` no importa `generator`; EVAL-001 importa el archivo por
`code_reference` y su veredicto cambia con el archivo: §5 P3b/P3c). Ruta
Artifact-B-para-Generator-A: no encontrada (sin copias implícitas, sin
hardcodes de paths/IDs, sin defaults que sustituyan el artifact).

## 9. Evidence Verification

En JSON persistido (demo A `e4ddb101…`, probe P3d): una run → 2 evidencias
(generator, validator), 1 artifact; `artifact.evidence_ref ==
evidence[0].result_id`; `evidence[1].output.evidence.artifact_id ==
evidence[1].input.artifact.artifact_id == artifact_id`; toda evidencia trae
`result_id/agent_id/output/timestamp`; cero `parent_event_id` huérfanos;
cero evidence sin agente/resultado; cero evidence de otro run. Caso B:
artifact preservado + evidence FAIL con `INV-002` causal.

## 10. Validator Enforcement

Validator real ejecuta Invariants + Evals sobre el artifact referenciado:
negativo (duplicado → FAIL con `INV-002` + EVAL-001 conductual) y positivo
(PASS, `checks_evaluados` = 3 > 0) demostrados por ejecución. Sin registries
→ `status=ERROR` → FAILED (TEST 6 + P1-variante): no existe PASS vacío.
Forja bien formada por rogue registrado → COMPLETED (FINDING-02, LOW, nivel
código, no runtime). Forja malformada → `contract_violation` → FAILED
(defensa de forma operativa). Coordinator: cero literales de veredicto
(grep); `avanza` deriva de `AgentResult.status` + `output["result"]`
(lectura, no fabricación) — J demostrada salvo el boundary de FINDING-02.

## 11. Kernel Enforcement

Única mutación de estado vía `RunManager.transition()` (grep: cero
asignaciones directas fuera de `kernel/run_manager.py`; Coordinator/Agents
usan `transition/emit/record_*/advance_stage`). Terminal única al final de
`execute_pipeline()` (intermedios sin tocar `status` salvo PENDING→RUNNING
inicial); 17/17 inválidas rechazadas con estado intacto + evento ERROR;
`execute_stage` repetido rechaza COMPLETED→RUNNING. Bypass directo a nivel
objeto (`run.status = ...`) técnicamente posible (dataclass no frozen) —
convención, no enforcement (LOW, defensa en profundidad sugerida, sin
explotante en los caminos implementados).

## 12. StateMachine Verification

Mapa en código == spec §8 (7 estados, 9 transiciones; `COMPLETED→RUNNING`
ausente). Batería propia: 17 inválidas rechazadas (incluye
`COMPLETED→RUNNING/FAILED/COMPLETED`, `APPROVED→*`, `REJECTED→RUNNING`,
`PENDING→COMPLETED/FAILED/APPROVED`) + 9 válidas aceptadas, siempre con
ERROR registrado y estado intacto. Contraste spec incluido en suite
(`test_estados_…_coinciden…`, verde). I verificada por contenido/ejecución;
diff git imposible (código sin commitear — FINDING-06).

## 13. Observability Verification

Desde el JSON persistido únicamente (`build_trace`/`query_run` sobre disco):
Q1 run ✓, Q2 agentes ✓, Q3 inicio (timestamps `RUN_CREATED`/`RUN_STARTED`)
✓, Q4 producido (input/output completos en `evidence[]`) ✓, Q5 artifact
✓, Q6 validado (vía `evidence[1].input.artifact`, NO vía
`input_reference` del evento — truncado a 160 chars por diseño documentado)
✓ con esa salvedad explícita, Q7 resultado ✓, Q8 motivo de término
(`COORDINATOR_COMPLETED.status` + `STATE_CHANGED from/to`) ✓, Q9 estado
final ✓. Un solo `COORDINATOR_STARTED` raíz con todo anidado (TEST 7 en
verde + traza de demo re-ejecutada). Nada requiere inferencia salvo la
salvedad Q6, declarada.

## 14. execute_stage() Regression

Secuencia exacta de eventos preservada
(`RUN_CREATED,COORDINATOR_STARTED,AGENT_SELECTED,STATE_CHANGED,RUN_STARTED,
AGENT_STARTED,AGENT_COMPLETED,EVIDENCE_RECORDED,STATE_CHANGED,
COORDINATOR_COMPLETED` — test en verde); suite `test_coordinator*.py`
verde en baseline; extracción a `_run_single_agent()` verificada por
lectura (sin cambios de decisión; terminal movido al orquestador);
`execute_stage()` == `execute_pipeline()` de un paso por construcción;
segunda llamada sobre COMPLETED rechaza (P2d). Sin regresión.

## 15. Test Quality Assessment

`tests/test_same_run_pipeline.py` (11 tests), sin mocks ni fixtures que
oculten errores (grep: solo menciones "no un mock" en docstrings; agentes,
registries, spec y filesystem reales —`tmp_path`—; el "espía" del TEST 3
observa sin sustituir producción):

| Test | Propiedad | Ejecuta | Clasificación |
|---|---|---|---|
| 1 same-run | run_id único + ambos agentes | pipeline real 2 pasos | STRONG (detectaría split-run: faltarían eventos del 2º agente) |
| 2 lineage | artifact↔run + archivo | pipeline real | ADEQUATE (no verifica contenido vs spec; lo cubren INV/EVAL) |
| 3 input explícito | builder recibe el real | pipeline + espía | STRONG (assert anti-None en el builder + igualdad de ids) |
| 4 PASS→COMPLETED | veredicto→estado | pipeline real | ADEQUATE (checks>0 en test compañero) |
| 5 FAIL→FAILED | contención + causa + artifact | pipeline real + 3er paso ausente implícito | STRONG |
| 6 no-bypass | sin registries → ERROR/FAILED | pipeline real | STRONG |
| checks>0 | PASS con checks reales | pipeline real | STRONG |
| 7 trazabilidad | reconstrucción + raíz única | pipeline + save/load disco | STRONG |
| 8 marcador | — | `assert True` | INVALID (declarado marcador; +1 al conteo) |
| execute_stage intacto | secuencia exacta | stage real | STRONG (quebradizo por diseño = su propósito) |
| no_depende_etl | 3 archivos sin imports ETL | AST | ADEQUATE (estrecho; mi scan total lo complementa) |

Debilidad transversal honesta: los tests prueban composición feliz
(Code→Validation con builders correctos); los caminos CALLER-degenerado
(P1b) y rogue-registrado (P1c) no están cubiertos por tests — existen como
probes míos, no como regresión (proponerlos sería fase posterior, no
verificación).

## 16. ETL Independence

Cero imports ETL en **todos** los `.py` de `software-factory/` (scan total:
`engine|scripts.*|market_db|api|backend|psycopg2|sqlite3|requests|socket` —
cero hits); `demo.py` solo importa factory; persistencia en JSON
(gitignoreado, sin Postgres); sin red ni MCP real; `test_independence.py`
(AST kernel + `sys.modules` runtime) en verde. PASS.

## 17. Final Test Count

Suite existente: **138 passed, 0 failed** (comando §2). Composición por
archivo: agent_registry 5, classifier 9, contracts 19, coordinator 10,
coordinator_real_spec 1, events 3, factory_spec_loader 5, generator 16,
independence 3, observability 16, run_manager 7, same_run_pipeline 11,
state_machine 11, state_manager 4, validator 18. Probes propios: 3 scripts
temporales (≈30 aserciones de ataque), todos con veredicto registrado
arriba, eliminados tras la ejecución. Demo: 2 runs reales (PASS+FAIL).

## 18. Verdict

**PASS WITH FINDINGS**

Sin CRITICAL ni HIGH: same-run demostrado por ejecución (un solo `run_id`,
un solo `create_run`, lineage con triple amarre, archivo en disco),
Validator ejecuta de verdad (PASS y FAIL conductuales, sin PASS vacío),
Kernel gobierna todas las transiciones terminales (17/17 inválidas
rechazadas, terminal única), FAIL contenido sin avance, observabilidad
reconstruye las 9 preguntas desde disco, `execute_stage()` intacto,
independencia ETL total, 138/138 en verde, demo A/B conforme.

Findings: 1 MEDIUM (FINDING-01, traversal por `run_id` sin sanitizar —
prueba contenida en TEMP, limpieza verificada), 2 LOW (FINDING-02,
confianza en `output["result"]` a nivel código; FINDING-04, excepción de
Eval no contenida), 3 INFO (FINDING-03 composición no forzada; FINDING-05
baseline 127→138 + marcador; FINDING-06 scan anti-ETL estrecho +
código sin commitear). Corrección explícitamente NO realizada (regla §26);
direcciones de endurecimiento sugeridas sin implementar: validar forma de
`run_id`/nombres en el sink (o en `create_run`/`from_dict`), binding de
veredicto por rol, try alrededor de evaluación de Evals, tests de
regresión para P1b/P1c.
