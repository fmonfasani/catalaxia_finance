# HARDENING — FASE 5D

Corrección de los findings demostrados en `INDEPENDENT-VERIFICATION-5C.md`
(auditoría independiente, veredicto **PASS WITH FINDINGS**). Se corrigen
exclusivamente los tres findings priorizados por el pedido de esta fase:
MEDIUM (FINDING-01, path traversal), y dos LOW (FINDING-02, confianza en
`output["result"]`; FINDING-04, excepción de Eval no contenida). Los tres
`INFO` del reporte (FINDING-03, 05, 06) no requerían corrección de código —
son observaciones de alcance/documentación, no debilidades demostradas.

## 1. Baseline

**VERIFICADO POR EJECUCIÓN**. `python -m pytest tests/ -q` antes de tocar
código: **138 passed**, coincidiendo exactamente con el baseline esperado
por el pedido (`138 passed`) — sin discrepancia que investigar.

## 2. Finding MEDIUM — Path Traversal

**Causa** (VERIFICADO POR CÓDIGO): `GenerationWorkspace.__init__` construía
`self.root = Path(base_dir) / run_id` y `StateManager._path_for()` construía
`self.runs_dir / f"{run_id}.json"`, ambos sin validar la forma de `run_id`.
`RunManager.create_run()` siempre genera un `uuid4()` seguro, pero
`GeneratorInput.run_id` es controlado por quien invoca al Generator, y
`StateManager.save()` toma `run_id` directamente del dict que le pasan — un
`run_id="../escape"` permitía escribir fuera del root pretendido en ambos
sinks, exactamente como el reporte lo demostró contra los tres niveles
(`GenerationWorkspace`, `StateManager`, `Generator.execute()`).

**Corrección** (VERIFICADO POR CÓDIGO): nuevo módulo
[kernel/identifiers.py](kernel/identifiers.py) con dos capas independientes:
`assert_safe_identifier()` (forma: solo `[A-Za-z0-9._-]`, nunca vacío, nunca
`.`/`..`) y `safe_child_path()` (containment: resuelve el path final y
verifica que sigue siendo descendiente del root autorizado, vía
`Path.resolve()` + `relative_to()`). Ambos sinks (`GenerationWorkspace.
__init__`, `StateManager._path_for()`) llaman las dos funciones en su único
punto de construcción de path. `GeneratorAgent.execute()` no se modificó —
su `except Exception` genérico ya existente captura el
`UnsafeIdentifierError` (subclase de `ValueError`) y lo convierte en
`AgentResult(status="ERROR")`, sin necesidad de tocar ese archivo.

**Tests** (VERIFICADO POR TEST): [tests/test_identifiers.py](tests/test_identifiers.py)
— 28 tests: run_id válido funciona (2), traversal directo rechazado (2),
9 variantes equivalentes rechazadas × 2 sinks (18), ningún archivo creado
fuera del root (3, incluyendo el Generator real completo), comportamiento
normal de runs reales sin cambios (1), containment defensivo de
`safe_child_path()` (2).

**Evidencia** (VERIFICADO POR EJECUCIÓN): reproducción manual del escenario
exacto del reporte (`run_id="../pz-escape"` contra `GeneratorAgent.execute()`
real) → `status=ERROR`, `detail` cita el `run_id` rechazado, y se confirmó
por `Path.exists()` que ningún archivo se creó fuera del directorio
autorizado.

## 3. Finding LOW — Validator Verdict Trust

**Causa** (VERIFICADO POR CÓDIGO): `_run_single_agent()` (en
`coordinator/coordinator.py`) reconocía `output["result"] in {"PASS","FAIL"}`
como veredicto de CUALQUIER agente, mirando solo la FORMA del output — sin
verificar que quien lo produjo fuera realmente un Validator. Un agente
registrado bajo cualquier `agent_id`, con cualquier `role` declarado, podía
producir esa forma y el Coordinator lo trataba como un veredicto de
validación real.

**Corrección** (VERIFICADO POR CÓDIGO): la lectura de `output["result"]`
ahora exige adicionalmente `agent.metadata.role is AgentRole.VALIDATOR`
(`agent_contract.AgentRole`, campo que ya existía desde la Fase 3, sin
cambios de forma). Un agente cuyo rol declarado no sea `VALIDATOR` nunca
logra que su `output["result"]` sea interpretado como veredicto — su éxito
depende únicamente de `AgentResult.status`, exactamente como antes de que
existiera este mecanismo (Fase 5B). No se creó ningún framework de
autorización nuevo: es una única condición adicional sobre un campo que ya
existía, en el único punto donde el Coordinator ya interpretaba el output.

**Límite documentado, no corregido** (declarado explícitamente, no
silenciado): un agente que declare `role=AgentRole.VALIDATOR` en su propia
`AgentMetadata` estática (mintiendo sobre su identidad completa, no solo su
`agent_id`) seguiría siendo tratado como autoridad de veredicto — exactamente
el boundary que el propio reporte clasificó como LOW y "no explotable por el
LLM en el modelo actual (los agents son código fijo; no existe vía runtime
para registrar agentes)". Cerrar ese boundary completamente requeriría un
mecanismo de atestación/autorización del Registry — explícitamente fuera de
alcance de esta fase ("No crear un nuevo framework de autorización").

**Tests** (VERIFICADO POR TEST): [tests/test_hardening_5d.py](tests/test_hardening_5d.py)
— Validator real → PASS → COMPLETED; Validator real → FAIL → FAILED; un
Generator (role=GENERATOR) que intenta forjar `"PASS"` no logra que ese
forjado determine el veredicto (avanza solo por `status`); el mismo agente
forjando `"FAIL"` tampoco logra bloquear el Run; un output malformado de
Generator sigue siendo rechazado por `GENERATOR_OUTPUT` (Contract, sin
relación con el rol); verificación estática (AST) de que `coordinator.py`
nunca asigna literales `"PASS"`/`"FAIL"` a mano.

**Evidencia** (VERIFICADO POR EJECUCIÓN): reproducción del escenario P1c del
reporte (agente registrado como `"validator"` pero con `role=GENERATOR`
real) — ya no completa por el veredicto forjado; y del escenario
complementario (Generator real con `role=GENERATOR` que intenta forzar
`"FAIL"`) — el Run llega a `COMPLETED` de todas formas, confirmando que el
Generator no puede producir un resultado terminal de validación.

## 4. Finding LOW — Eval Exception

**Causa** (VERIFICADO POR CÓDIGO + EJECUCIÓN): `ValidatorAgent.execute()`
llamaba `input_data.eval_registry.run_all(...)` (y
`invariant_registry.evaluate_all(...)`) sin ningún `try` alrededor —
cualquier excepción real levantada por un `Eval.evaluation_method` (el
reporte demostró un `AttributeError` real: EVAL-001 buscando
`getattr(modulo, "AltaClientes")` contra un módulo generado con
`entity_name` distinto de `"Cliente"`) atravesaba `execute()` sin capturarse,
violando la regla explícita de `agent_contract.py` ("`execute()` no debe
lanzar excepciones por condiciones de negocio esperables") y dejando el Run
en `RUNNING` no-terminal, sin ningún evento `AGENT_FAILED` ni transición
final.

**Corrección** (VERIFICADO POR CÓDIGO): se envolvió la ejecución de
Invariants + Evals en `agents/validator.py::ValidatorAgent.execute()` en un
único `try/except Exception`. Cualquier excepción real se convierte en
`AgentResult(status="ERROR", output={"error": "validation_exception",
"detail": ..., "checks_completados_antes_de_la_excepcion": [...]})` — nunca
se propaga. El Coordinator (sin ningún cambio adicional) trata ese
`status="ERROR"` exactamente igual que cualquier otra falla de agente:
`AGENT_FAILED` + `RunManager.transition(run, RunStatus.FAILED)`. **No se
modificó la StateMachine** — `FAILED` ya era un estado terminal alcanzable
desde `RUNNING` desde la Fase 2; no hizo falta ningún estado nuevo.

**Tests** (VERIFICADO POR TEST): en `tests/test_hardening_5d.py` — Eval PASS
comportamiento normal; Eval FAIL → FAILED; reproducción exacta del escenario
del reporte (`entity_name="TallerX"`) → estado terminal `FAILED`, nunca
`RUNNING`; aislamiento directo del `ValidatorAgent` (sin Coordinator) con un
Eval que levanta `AttributeError` a propósito; estado persistido consistente
(`StateManager.save()`/`load()` sin errores, con la evidencia de la excepción
intacta); confirmación explícita de que nunca termina `COMPLETED` por una
excepción.

**Evidencia** (VERIFICADO POR EJECUCIÓN): reproducción exacta del escenario
del reporte vía `execute_pipeline()` real (Generator con `entity_name=
"TallerX"` → Validator con EVAL-001) → `status=FAILED`,
`evidence[-1].output.error == "validation_exception"`, `AGENT_FAILED`
presente en los eventos, último evento `COORDINATOR_COMPLETED` — nunca
quedó en `RUNNING`.

## 5. Regression

**VERIFICADO POR EJECUCIÓN**. `python -m pytest tests/ -q`:

- Baseline: 138 passed.
- Nuevos (FINDING-01): 28 (`tests/test_identifiers.py`).
- Nuevos (FINDING-02 + FINDING-04): 13 (`tests/test_hardening_5d.py`).
- **Final: 179 passed, 0 failed.**

Ningún test existente se modificó para forzar el número esperado — los 138
originales pasan sin ningún cambio.

## 6. Demo

**VERIFICADO POR EJECUCIÓN**. `demo.py` no se modificó — ninguna de las tres
correcciones cambia el comportamiento del camino legítimo (Generator real →
Validator real, con `run_id` normal). Se re-ejecutó `python demo.py` después
de aplicar las tres correcciones: CASO A → `STATE: COMPLETED (ADVANCE)`,
CASO B → `STATE: FAILED (BLOCK/FAIL — NO ADVANCE)`, idéntico al
comportamiento de la Fase 5C. Evidencia persistida en
`software-factory/runs/` (dos nuevos `run_id` de esta ejecución, junto con
la evidencia previa de la Fase 5C y de la propia auditoría de OpenCode,
conservada sin tocar).

## 7. Files Created

**VERIFICADO POR CÓDIGO**:
- [kernel/identifiers.py](kernel/identifiers.py)
- [tests/test_identifiers.py](tests/test_identifiers.py)
- [tests/test_hardening_5d.py](tests/test_hardening_5d.py)
- [HARDENING-5D.md](HARDENING-5D.md) (este archivo)

## 8. Files Modified

**VERIFICADO POR CÓDIGO**:
- [agents/generation_workspace.py](agents/generation_workspace.py) — `__init__` valida `run_id` y resuelve `self.root` con containment.
- [kernel/state_manager.py](kernel/state_manager.py) — `_path_for()` valida `run_id` y resuelve el path con containment.
- [coordinator/coordinator.py](coordinator/coordinator.py) — la lectura de `output["result"]` como veredicto ahora exige `agent.metadata.role is AgentRole.VALIDATOR`.
- [agents/validator.py](agents/validator.py) — la ejecución de Invariants/Evals queda envuelta en `try/except`, convirtiendo cualquier excepción real en `AgentResult(status="ERROR")`.

Ningún otro archivo de `software-factory/` se modificó. `kernel/state_machine.py`
no se tocó — ninguna de las tres correcciones lo requirió.

## 9. ETL Independence

**VERIFICADO POR TEST + CÓDIGO**. `git status --porcelain -- software-factory`
devuelve únicamente `?? software-factory/` (directorio íntegro sin
commitear) — sin cambios en el resto del repositorio más allá de lo
preexistente antes de esta sesión (confirmado por conteo estable de archivos
modificados fuera de `software-factory/`, ninguno de ellos tocado por este
trabajo). `test_no_depende_del_etl_financiero` (en ambos archivos de test
nuevos) escanea por AST los módulos nuevos/modificados
(`kernel/identifiers.py`, `agents/generation_workspace.py`,
`kernel/state_manager.py`, `coordinator/coordinator.py`,
`agents/validator.py`) contra la lista de imports del ETL — cero hits.

## 10. Remaining Limitations

**NO DETERMINABLE CON LA INFORMACIÓN DISPONIBLE** (fuera de alcance de esta
fase, documentado explícitamente arriba, no corregido):

- Un agente que declare `role=AgentRole.VALIDATOR` en su propia metadata
  estática seguiría siendo tratado como autoridad de veredicto real — cerrar
  esto por completo requeriría un mecanismo de atestación/autorización del
  Registry, explícitamente fuera de alcance ("no crear un nuevo framework de
  autorización").
- `run.status = ...` sigue siendo técnicamente posible por asignación
  directa (dataclass no frozen) — es una convención respetada por todo el
  código existente (verificado por grep en el reporte independiente: cero
  mutaciones directas fuera de `kernel/run_manager.py`), no un enforcement a
  nivel de tipo. No se tocó — no es ninguno de los tres findings priorizados
  y su corrección (congelar `Run` o encapsular `status` detrás de una
  property) tendría un radio de cambio mucho mayor al pedido de esta fase.
- Los findings INFO del reporte (FINDING-03 composición no forzada,
  FINDING-05 baseline desactualizado en prosa, FINDING-06 alcance del test
  anti-ETL) no requerían corrección de código según el propio veredicto del
  reporte y no fueron tocados.

## 11. Evidence Classification

Cada afirmación de este documento fue clasificada inline junto a su
sección correspondiente (§2–§9), siguiendo las cuatro categorías exigidas:
`VERIFICADO POR CÓDIGO`, `VERIFICADO POR TEST`, `VERIFICADO POR EJECUCIÓN`,
`NO DETERMINABLE`.
