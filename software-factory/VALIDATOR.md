# VALIDATOR — evalúa, no genera, no corrige, no decide arquitectura

**Archivo**: `agents/validator.py`. **Estado**: implementado, probado (Fase 5B).

## Responsabilidad

FACTORY-SPEC.md §6 (Validator):

> *"produce evidencia objetiva (tests, chequeos estáticos, ejecución real) de que un
> artefacto cumple sus Contracts e Invariants... No puede corregir el artefacto que
> está validando."*

`ValidatorAgent` implementa esto al pie de la letra: **lee** el `artifact` y ejecuta
Invariants/Evals sobre él, pero nunca escribe en el `dict` del artifact ni en el
archivo que `reference`/`code_reference` apunta. Produce un veredicto — no arregla
nada.

## El flujo completo de esta fase

```
AGENT (Generator)
   |
CONTRACT           (Fase 5A -- ya verificado por el Coordinator antes de llegar aca)
   |
INVARIANTS         (INV-001, INV-002 -- propiedades sobre el contenido)
   |
EVALS              (EVAL-001 -- comportamiento del software generado, ejecutado)
   |
VALIDATOR          (agrega los resultados de arriba en un veredicto)
   |
EVIDENCE           (AgentResult -> RunManager.record_evidence())
   |
KERNEL             (interpreta el veredicto, decide la transicion de estado)
   |
ADVANCE / BLOCK
```

El Validator en sí no re-implementa Contracts/Invariants/Evals — los **orquesta**:
recibe un `InvariantRegistry` y un `EvalRegistry` ya construidos (`invariants_catalog.
build_default_registry()`, `evals_catalog.build_default_registry()`), arma un
`context` compartido, y agrega sus resultados.

## Contrato

`ValidatorAgent` extiende `agent_contract.BaseAgent` — mismo contrato mínimo que
`ClassifierAgent`/`GeneratorAgent`: `metadata` + `execute(input_data) -> AgentResult`.

### Input — `ValidatorInput`

```python
@dataclass(frozen=True)
class ValidatorInput:
    run_id: str
    scope: str                                  # p.ej. "Generator" -- que Invariants/Evals aplican
    artifact: dict | None
    evidence: dict | None
    context: dict = field(default_factory=dict)  # datos extra (code_reference, registros, etc.)
    invariant_registry: InvariantRegistry | None = None
    eval_registry: EvalRegistry | None = None
```

El Validator **nunca adivina** qué verificar — si no se le pasa ni `invariant_
registry` ni `eval_registry`, rechaza la ejecución (`AgentResult(status="ERROR",
output={"error": "sin_invariants_ni_evals"})`) en vez de reportar un `PASS` vacío por
ausencia de checks.

### Output

```python
{
    "result": "PASS" | "FAIL",
    "status": "PASS" | "FAIL",     # alias, ver nota de compatibilidad abajo
    "checks": [{"id": ..., "status": "PASS"|"FAIL", "detail": ...}, ...],
    "failures": [{"id": ..., "type": "INVARIANT"|"EVAL", "reason": ...}, ...],
    "violations": ["INV-002", ...],  # ids de `failures`, para compatibilidad con VALIDATOR_OUTPUT
    "evidence": {"run_id": ..., "scope": ..., "artifact_id": ..., "checks_evaluados": N},
}
```

Compatible, sin cambios, con el Contract `VALIDATOR_OUTPUT` ya declarado en
`contracts_catalog.py` desde la Fase 5A (`result`, `violations`, `evidence` como
campos obligatorios) — verificado en
`tests/test_validator.py::test_validator_output_compatible_con_su_contrato`.

## PASS / FAIL — binario, sin estados ambiguos

La Fase 5B pide explícitamente no usar estados como "más o menos correcto". Este
Validator concreto usa únicamente `{PASS, FAIL}`.

**Nota de reconciliación con el Contract existente**: `VALIDATOR_OUTPUT.
postconditions` (Fase 5A) documenta el vocabulario más amplio que FACTORY-SPEC.md §6
menciona para Validation en general (`PASS`/`WARNING`/`BLOCK`/`NOT_CALCULABLE`). Esto
no es una contradicción: el Contract solo exige `result: str` por Schema — no fija
mecánicamente los valores permitidos — así que `{PASS, FAIL}` es un subconjunto válido,
más estricto, elegido para esta implementación concreta del Validator. Un Validator
futuro con criterios más granulares (p. ej. distinguir `WARNING` de `BLOCK`) podría
usar el vocabulario completo sin romper el Contract ni este documento.

`AgentResult.status` es **independiente** del veredicto: un Validator que evalúa
correctamente y encuentra una violación real devuelve `AgentResult(status="OK",
output={"result": "FAIL", ...})` — `status="OK"` significa "el Agent se ejecutó sin
error de programa", no "el resultado fue favorable". Ver la sección de integración con
el Coordinator para cómo se resuelve esta distinción.

## Integración con el Coordinator — genérica, sin `if agent_id == "validator"`

El Coordinator (`coordinator/coordinator.py`) no tiene ningún caso especial para el
Validator. La convención agregada en esta fase:

```python
veredicto_evaluacion = result.output.get("result") if isinstance(result.output, dict) else None
avanza = result.status == "OK" and veredicto_evaluacion != "FAIL"
```

Si el `output` de **cualquier** agente trae la forma `{"result": "PASS"|"FAIL", ...}`,
ese veredicto decide si el Run avanza — no `AgentResult.status`. Para el Classifier y
el Generator (que nunca producen esa forma), `veredicto_evaluacion` es `None` y
`avanza == (status == "OK")`, exactamente el comportamiento de las fases anteriores
(verificado en
`tests/test_validator.py::test_coordinator_sin_veredicto_preserva_comportamiento_previo`
y por los 109 tests previos, que siguen pasando sin cambios).

Cuando `avanza` es `False` (por `status == "ERROR"` o por un veredicto `FAIL`):

1. Se emite `AGENT_FAILED`, no `AGENT_COMPLETED` — mismo evento que cualquier otra
   falla de agente, sin un tipo de evento nuevo.
2. No se llama a `record_artifact()` — un veredicto FAIL nunca dEja pasar un artifact
   como si hubiera sido aceptado.
3. `record_evidence()` registra igual la evidencia completa (con el detalle de qué
   Invariant/Eval falló) — la falla queda trazable, nunca oculta.
4. `RunManager.transition(run, RunStatus.FAILED)` — el Kernel decide la transición;
   el Validator nunca toca `run.status`.

## El Kernel decide, el Validator informa

Ningún cambio al `StateMachine` (`kernel/state_machine.py`) — `RunStatus.FAILED` ya
existía desde la Fase 2 y ya era alcanzable desde `RUNNING`. No se inventó un estado
nuevo: la Fase 5B pide explícitamente "no inventar un nuevo estado si la State Machine
actual ya tiene uno apropiado", y `FAILED` es exactamente eso — "el Agent intentó y no
pudo producir un artefacto conforme" (§8 de FACTORY-SPEC.md), que describe tanto una
excepción de programa como un veredicto de validación negativo.

## Aislamiento de ejecución: Generator y Validator en Runs distintos (Fase 5B — superado, ver Addendum)

`ValidatorAgent` corre como el agente de la etapa `"Validation"` (FACTORY-SPEC.md §7:
`Validation | Validator | Evidencia PASS sobre Contracts + Invariants + Evals`) — una
etapa distinta de `"Code"` (Generator). Encadenar ambas etapas sobre el **mismo** Run
requeriría que la StateMachine permitiera `COMPLETED -> RUNNING`, transición que no
existe (misma brecha que `GENERATOR.md` ya documentó en la Fase 4B para el propio
Generator). Sin modificar la StateMachine ni FACTORY-SPEC.md, **esta fase (5B)**
resolvió la demostración con **dos Runs separados**: el Generator corría en un Run
avanzado a `"Code"`; el Validator corría en un Run fresco distinto, avanzado
directamente a `"Validation"`, recibiendo como input el `artifact`/`evidence` que
produjo el primer Run.

**Esta limitación quedó resuelta en la Fase 5C** — ver el Addendum al final de este
documento. Se conserva esta sección tal cual porque explica correctamente *por qué*
existía la restricción (la StateMachine, sin cambios) y *qué* se intentó primero antes
de la solución final.

## Observabilidad — reutilización, sin eventos nuevos

Igual que con el Generator (Fase 4B): no se agregó ningún `VALIDATION_STARTED`/
`VALIDATION_COMPLETED` como tipo de evento nuevo. Los eventos genéricos ya existentes
(`AGENT_SELECTED`, `AGENT_STARTED`, `AGENT_COMPLETED`/`AGENT_FAILED`,
`EVIDENCE_RECORDED`) cubren la necesidad, con `component_id="validator"`
distinguiéndolo de cualquier otro agente — verificado en
`tests/test_validator.py::test_eventos_de_validacion_quedan_registrados`. `run_id`,
`stage`, `validator_id` (via `component_id`), inicio/fin, checks (en el `evidence`
persistido), resultado y failures quedan todos reconstruibles vía `query_run()`/
`build_trace()` (Fase 4A/4B, sin cambios).

## Evidencia y trazabilidad

Cada ejecución del Validator deja exactamente un elemento en `run.evidence` con
`output` = el dict de arriba (`result`, `checks`, `failures`, `evidence`). La
reconstrucción `Artifact -> Validation -> Evidence` es posible reconociendo
`evidence.output.evidence.artifact_id` — el mismo `artifact_id` que el Run del
Generator ya produjo, correlacionando ambos Runs sin un mecanismo nuevo (el `run_id`
de cada uno queda en su propio Run; la correlación entre Runs es manual en esta fase —
ver Limitaciones).

## Casos PASS / FAIL demostrados (`demo.py`)

- **CASO A (PASS)**: un único registro previo sin conflicto de DNI. Los tres checks
  (`INV-001`, `INV-002`, `EVAL-001`) pasan → `result: PASS` → `RunManager.transition
  (COMPLETED)` → `ADVANCE`.
- **CASO B (FAIL)**: dos registros previos con el mismo DNI en el contexto → `INV-002`
  falla → `result: FAIL` → `RunManager.transition(FAILED)` → `BLOCK/FAIL, NO ADVANCE`.

Ambos casos ejecutados y verificados por ejecución real (no simulados) — ver el
reporte final de la Fase 5B para el trace completo de cada uno.

## Límites actuales (qué NO implementa)

- No genera código, no modifica el artifact ni el archivo generado (verificado por
  test: `test_validator_no_modifica_el_artifact`,
  `test_validator_no_modifica_el_archivo_generado`).
- No decide arquitectura ni corrige nada — solo evalúa.
- Solo `{PASS, FAIL}` — el vocabulario más amplio (`WARNING`/`BLOCK`/
  `NOT_CALCULABLE`) que el Contract deja abierto no está implementado en este
  Validator concreto.
- No hay Reviewer — un `PASS` de Validation no implica `APPROVED`; el Run llega a
  `COMPLETED`, no a un veredicto final de Pipeline (§7 exige también Review para
  `Delivery`).
- Sin MCP, sin Risk Engine, sin Human Gates, sin paralelismo, sin LLM — ninguno
  tocado en esta fase.

## Addendum (Fase 5C) — Generator y Validator, mismo run_id

La limitación "No encadena Generator y Validator sobre el mismo Run" (Fase 5B) quedó
resuelta sin tocar la StateMachine ni FACTORY-SPEC.md: se agregó
`Coordinator.execute_pipeline(run, steps)` (`coordinator/coordinator.py`), que orquesta
varias etapas sobre el **mismo** `run_id`, transicionando a un estado terminal
(`COMPLETED`/`FAILED`) una única vez, al final de la secuencia — nunca entre pasos
intermedios. Esto evita por completo la transición `COMPLETED -> RUNNING` que la
StateMachine sigue sin permitir (y que la Fase 2 prohíbe explícitamente).

El Validator recibe el `artifact` real del Generator de forma explícita: `steps` acepta
un `callable(artifact, evidence) -> input_data` para cualquier etapa después de la
primera, invocado por el Coordinator con lo que produjo el paso anterior — el Validator
nunca "adivina" ni reconstruye qué artifact validar, se lo entrega el Coordinator.

Ver [COORDINATOR.md](COORDINATOR.md) (Addendum Fase 5C) para el detalle de
`execute_pipeline()`, y `demo.py` para la ejecución real de ambos casos (PASS/FAIL)
con Generator y Validator compartiendo un único `run_id`. `execute_stage()` (el método
usado por todas las fases anteriores) no cambió ni un evento — sigue siendo la forma
correcta de correr un único agente para una única etapa.
