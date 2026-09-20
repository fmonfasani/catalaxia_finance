# GENERATOR — el primer agente que produce software real

**Archivos**: `agents/generator.py`, `agents/specification.py`,
`agents/generation_workspace.py`. **Estado**: implementado, probado (Fase 4B).

## Responsabilidad

Transformar una `Specification` explícita en un artefacto de software ejecutable.
El Generator **no decide arquitectura** — implementa lo que la `Specification` ya
define. Es determinista: la misma `Specification` produce, siempre, el mismo código
(un template de string, sin LLM, sin aleatoriedad).

**Principio citado de FACTORY-SPEC.md §6 (Generator)**: *"produce artefactos... a
partir de los artefactos previos del Pipeline y de los Contracts vigentes... No puede
certificar su propio output como válido."* El Generator de esta fase respeta esto:
valida que la `Specification` esté completa (rechaza si no, nunca "adivina" lo que
falta) y genera el código, pero no decide que ese código está "aprobado" — eso es
Validation/Review, fases futuras explícitamente no implementadas aquí.

## Contrato

`GeneratorAgent` extiende `agent_contract.BaseAgent` — el mismo contrato mínimo que
`ClassifierAgent` (Fase 3): `metadata` (`AgentMetadata`) + `execute(input_data) ->
AgentResult`. El Coordinator no necesita saber que existe un Generator distinto de un
Classifier — solo que implementa `BaseAgent`.

### Input — `GeneratorInput`

```python
@dataclass(frozen=True)
class GeneratorInput:
    run_id: str
    requirement: str
    specification: Specification
    authorized_context: dict[str, Any] = field(default_factory=dict)
```

Deliberadamente **no** recibe solo el `requirement` y deja que el Generator "adivine"
el resto (regla explícita de la Fase 4B) — el `requirement` es la referencia de
origen, pero el comportamiento generado sale enteramente de `specification`.
`authorized_context` es hoy solo un punto de extensión (usado por los tests para
redirigir el `output_dir` fuera de `software-factory/runs/`); el Generator no lee de
ahí nada que decida su lógica de negocio.

### Output

```python
{"artifact": {...}, "code_reference": "<path al .py generado>"}
```

Ver `ARTIFACTS.md` para la forma completa del `artifact`.

## Specification

`agents/specification.py` define el primer modelo concreto de Specification:

```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str        # "str" | "int" — deliberadamente chico, no un sistema de tipos
    required: bool = True
    unique: bool = False

@dataclass(frozen=True)
class Specification:
    spec_id: str
    entity_name: str
    fields: tuple[FieldSpec, ...] = ()
    requirement_ref: str = ""
```

`Specification.validar()` es la **única autoridad** sobre "esta Specification está
completa" — devuelve una lista de problemas (vacía = válida). Revisa: `spec_id` y
`entity_name` no vacíos, al menos un campo, sin nombres de campo duplicados, tipos
soportados (`str`/`int`), y `requirement_ref` no vacío (sin esto, un Artifact no
podría preservar la referencia a su Requirement de origen).

El Generator llama a `spec.validar()` y, ante cualquier problema, **rechaza la
ejecución** (`AgentResult(status="ERROR", output={"error": "specification_invalida",
"problemas": [...]})`) — nunca completa nada en silencio.

## Generación determinista

`_render_modulo_cliente(spec)` arma un módulo Python vía f-strings a partir de los
campos de la `Specification`: una `@dataclass` con esos campos, y una clase
`Alta<Entity>s` con:

- `alta(...)` — valida cada campo `required` (`raise ValueError` si falta) y cada
  campo `unique` (`raise ValueError` si ya existe un registro con ese valor), y
  agrega el registro.
- `listar()` — devuelve los registros en memoria.

No hay ningún LLM invocado. Dos ejecuciones con la misma `Specification` producen
byte-a-byte el mismo archivo (verificado manualmente durante esta fase).

### Decisión de tecnología: Python stdlib, sin framework

FACTORY-SPEC.md no fija una tecnología para el software generado, y la Fase 4B exige
justificar la elección por inspección, no asumirla. Se inspeccionó el repo: fastapi/
uvicorn/psycopg2-binary aparecen únicamente en `api/` (el backend financiero, fuera de
alcance); no hay ningún requisito HTTP para el caso de demostración ("alta de
clientes"); y el propio `software-factory/` ya es 100% Python sin dependencias
nuevas. Conclusión: **Python 3.11 stdlib puro (`dataclasses`), sin framework web** —
la opción mínima, determinista y sin dependencias nuevas para esta fase. Una fase
futura con un requisito HTTP explícito podría justificar FastAPI; no se anticipa aquí.

## Generation Directory (aislamiento)

`agents/generation_workspace.py` → `GenerationWorkspace`: cada `Run` escribe en
`software-factory/runs/<run_id>/{requirements,specification,generated,evidence,
audit}/` — nunca sobre el código existente de Catalaxia (`engine/`, `scripts/`,
`api/`, que además viven en un working tree distinto de `software-factory/`).

Namespace deliberadamente distinto del de `StateManager`: `StateManager` escribe
`software-factory/runs/<run_id>.json` (archivo); `GenerationWorkspace` escribe
`software-factory/runs/<run_id>/` (directorio). No colisionan.

El Generator escribe tres cosas por ejecución exitosa: `requirements/requirement.json`
(el texto del Requirement), `specification/<spec_id>.json` (la Specification
serializada), y `generated/<entity_name_lower>.py` (el código). `evidence/` y `audit/`
quedan preparados por la estructura pero no se usan todavía desde este Generator —
la evidencia real vive en `run.evidence` (Kernel, Fase 3), no duplicada en disco.

## Relación con el Coordinator

Flujo exacto (sin código nuevo específico de Generator en el Coordinator — ver
`coordinator/coordinator.py`, que ya lo maneja de forma genérica desde la Fase 4A):

```
Coordinator.execute_stage(run, generator_input)
  -> PipelineDefinition.agents_for("Code") == ("Generator",)   (FACTORY-SPEC.md §7)
  -> AgentRegistry.get_enabled("generator")
  -> agent.execute(generator_input)  ->  AgentResult
  -> si status == "OK" y output trae "artifact": RunManager.record_artifact(...)
  -> RunManager.record_evidence(...)
  -> RunManager.transition(run, COMPLETED | FAILED)
```

El Coordinator detecta la clave `"artifact"` en el `output` de **cualquier** agente
exitoso — no tiene ningún `if agent_id == "generator"`. Esto es intencional: el mismo
mecanismo sirve, sin cambios, para un futuro agente que también produzca artefactos.

## Relación con el Kernel — el Generator NO controla el State

`GeneratorAgent.execute()` **nunca** importa `kernel.run_manager`, `kernel.
state_machine` ni `coordinator.coordinator` (verificado por AST en
`tests/test_generator.py::test_generator_no_modifica_el_state_directamente`, no solo
por convención). Devuelve un `AgentResult`; es el Coordinator quien decide, a través
de `RunManager.transition()`, si el `Run` pasa a `COMPLETED` o `FAILED`. El Generator
no tiene forma de forzar una transición de estado por sí mismo.

## Decisión de diseño: una brecha real en la StateMachine, documentada, no resuelta

Durante esta fase se detectó que `RunStatus.COMPLETED` solo transiciona a `{APPROVED,
REJECTED}` (nunca de vuelta a `RUNNING`), y que `RunManager.advance_stage()` no
resetea `run.status`. Esto significa que **no se puede encadenar dos ejecuciones
reales de `execute_stage()` sobre el mismo `Run`** (por ejemplo, Classifier y luego
Generator) tal como está la StateMachine hoy: la segunda llamada fallaría al intentar
`COMPLETED -> RUNNING`.

Siguiendo la norma del proyecto ("ante una contradicción, se documenta, nunca se
resuelve arbitrariamente"), **no se modificó la StateMachine ni FACTORY-SPEC.md**.
En su lugar, tanto los tests (`tests/test_generator.py`) como la demo (`demo.py`)
usan un **Run fresco** (todavía `PENDING`) avanzado directamente a la etapa `"Code"`
vía `RunManager.advance_stage(run, "Code")` **antes** de su primera llamada a
`execute_stage()` — que sigue siendo válida porque `PENDING -> RUNNING` ya lo es. Esto
demuestra el circuito completo sin necesitar una transición que la StateMachine no
define. Encadenar múltiples etapas reales sobre un mismo `Run` (o remodelar el ciclo
de vida a un estado por etapa) queda explícitamente para una fase futura — no forma
parte de esta implementación.

## Observabilidad — reutilización, no eventos nuevos

Se evaluó agregar `GENERATOR_SELECTED/STARTED/COMPLETED/FAILED` como tipos de evento
nuevos y se decidió **no hacerlo**: los eventos genéricos `AGENT_SELECTED/STARTED/
COMPLETED/FAILED` (Fase 4A) ya cubren esta necesidad, con `component="AGENT"` y
`component_id="generator"` distinguiéndolo de cualquier otro agente. Agregar un tipo
de evento por cada Agent nuevo violaría la regla explícita de "no duplicar mecanismos"
repetida en la Fase 4A y en esta fase.

`Event.artifact_id` (nuevo campo, opcional) se completa en `AGENT_COMPLETED` y
`EVIDENCE_RECORDED` cuando el resultado del agente incluyó un artifact — permite
correlacionar un evento con el artefacto que produjo sin inferencia.

## Trazabilidad — REQ → SPEC → GENERATOR → ARTIFACT → EVIDENCE

Cada `Artifact` generado preserva:

- `requirement_ref` — el texto del Requirement de origen.
- `specification_ref` — el `spec_id` de la Specification usada.
- `evidence_ref` — el `result_id` de la evidencia (`AgentResult.to_dict()`) que este
  mismo Artifact produjo, completado por el Coordinator *después* de conocer ese
  `result_id` (el Generator no puede conocerlo de antemano — no controla el Kernel).

Con esto, dado un `run_id`, `query_run()` (Fase 4A, sin cambios) más `run.artifacts`
permiten reconstruir la cadena completa sin inferencia: qué Requirement originó qué
Specification, qué Generator la ejecutó, qué Artifact produjo, y qué evidencia lo
respalda. Verificado en
`tests/test_generator.py::test_run_reconstruye_requirement_specification_generator_artifact_evidence`.

## Manejo de errores

| Caso | Resultado |
|---|---|
| `input_data` no es `GeneratorInput` | `AgentResult(status="ERROR")`, sin output detallado (entrada de forma incorrecta) |
| `requirement` vacío/ausente | `AgentResult(status="ERROR", output={"error": "requirement_inexistente"})` |
| `specification` ausente o de otro tipo | `AgentResult(status="ERROR", output={"error": "specification_invalida", "problemas": [...]})` |
| `specification.validar()` devuelve problemas | ídem — nunca se completa lo que falta |
| Error de filesystem al escribir (`OSError`) | `AgentResult(status="ERROR", output={"error": "filesystem_error", ...})` |
| Cualquier otra excepción durante el render/escritura | `AgentResult(status="ERROR", output={"error": "generation_failure", ...})` |

En **todos** los casos de error: (1) se genera un evento (`AGENT_FAILED` vía el
Coordinator), (2) el `Run` queda en un estado coherente (`FAILED`, nunca a medio
camino), (3) queda asociado a `run_id`, (4) es observable vía `query_run()`/`build_
trace()`, y (5) **nunca** se deja un `artifact` marcado como generado — el Coordinator
solo llama `record_artifact()` cuando `result.status == "OK"` *y* el `output` trae la
clave `"artifact"`. Verificado en
`tests/test_generator.py::test_error_de_generacion_queda_registrado_y_no_marca_artifact_falso`.

## Límites actuales (qué NO implementa)

- Sin LLM — determinista a propósito, primera versión.
- Solo genera un tipo de artefacto (`python_module`, una entidad con alta/unicidad) —
  no un lenguaje de especificación general.
- No valida su propio output como "correcto" más allá de que el archivo se escribió —
  eso es responsabilidad del Validator, fase futura no implementada aquí.
- No hay Reviewer — nada aprueba/rechaza el Artifact generado; el `Run` llega a
  `COMPLETED`, no a `APPROVED`.
- No encadena múltiples etapas reales sobre un mismo `Run` (ver la brecha de
  StateMachine documentada arriba).
- Sin MCP, sin paralelismo, sin Reuse/Knowledge/Risk Engine, sin Human Gates — ninguno
  de estos fue tocado en esta fase.
