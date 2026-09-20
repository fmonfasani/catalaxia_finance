# FACTORY-KERNEL — Fase 2: primer núcleo ejecutable

**Estado**: implementado, probado, independiente del ETL financiero (verificado, no
solo declarado — ver §7). **No implementa** Coordinator, Agents, generación de código
ni de SDD, MCP real, paralelismo, Reuse/Knowledge/Risk Engine, ni Human Gates
completos — eso es deliberadamente Fase 3+.

## 1 · Responsabilidad del Kernel

El Kernel es el mecanismo que controla la ejecución de la Factory (FACTORY-SPEC.md
§2.1: *"el sistema controla al LLM"*). Concretamente, en esta fase:

1. Carga y valida `FACTORY-SPEC.md` (`FactorySpecLoader`).
2. Crea una ejecución (`Run`) con un `run_id`, versión de Factory, estado inicial y
   primera etapa del Pipeline — todos derivados de la spec real, no hardcodeados.
3. Mantiene el estado de esa ejecución en memoria y lo persiste (`StateManager`).
4. Controla qué transiciones de estado son válidas (`StateMachine`) y qué etapas del
   Pipeline existen (`PipelineDefinition`) — rechazando explícitamente lo que no lo es.
5. Registra cada evento relevante (`EventLogger`) para que la ejecución sea
   reconstruible sin inferencia.

Ningún componente de esta fase invoca un LLM. No hay ningún punto del código donde el
Kernel le "pregunte" a un modelo qué hacer — cada transición y cada avance de etapa
los pide explícitamente quien llama al Kernel, con un destino ya decidido por una
condición externa. Eso es intencional: el principio *"LLM no controla el sistema"* se
cumple hoy por ausencia total de LLM en el camino crítico, no por una promesa a
futuro.

## 2 · Componentes

| Componente | Archivo | Responsabilidad |
|---|---|---|
| `FactorySpecLoader` | `kernel/factory_spec_loader.py` | Lee `FACTORY-SPEC.md`, valida su estructura mínima, extrae versión + Pipeline (§7) + nombres de estado mencionados (§8) |
| `PipelineDefinition` | `kernel/pipeline_definition.py` | Representa las etapas válidas y su orden; no sabe leer Markdown |
| `StateMachine` | `kernel/state_machine.py` | `RunStatus` (enum) + mapa de transiciones válidas + validación |
| `RunManager` | `kernel/run_manager.py` | Crea y avanza un `Run`; delega en `StateMachine`/`PipelineDefinition`/`EventLogger` |
| `EventLogger` | `kernel/events.py` | Construye `Event`s con forma consistente |
| `StateManager` | `kernel/state_manager.py` | Persiste/lee un `Run` (JSON por `run_id`) |
| `errors` | `kernel/errors.py` | Excepciones nombradas por la regla que violan |

Ningún componente adicional se agregó. `PipelineStage`/`Event`/`Run` son dataclasses
de soporte, no componentes nuevos — son la forma de los datos que los seis
componentes de arriba manipulan.

## 3 · Relación con FACTORY-SPEC.md

El Kernel **lee** la spec en vez de duplicar sus reglas en Python:

- La lista y el orden de las 12 etapas del Pipeline (§7) se extraen parseando la
  tabla Markdown real — si alguien edita esa tabla, `PipelineDefinition` cambia sin
  tocar código (verificado: `test_las_12_etapas_de_la_spec_estan_en_orden` lee la
  spec real, no una copia).
- Los nombres de estado que `state_machine.py` declara en código
  (`PENDING/RUNNING/BLOCKED/FAILED/COMPLETED/APPROVED/REJECTED`) se **contrastan**
  contra lo que la Sección 8 de la spec menciona en su prosa
  (`test_estados_de_state_machine_coinciden_con_lo_que_menciona_la_spec`). Esto NO es
  lo mismo que parsear la sección 8 para *derivar* las transiciones — ver la decisión
  documentada en §6.

**Contradicción código↔spec**: si ese test de contraste fallara, el resultado es un
`AssertionError` explícito con ambos conjuntos de nombres impresos — exactamente
"detenerse y reportar", no una resolución automática. En esta entrega, no hay
contradicción: se verificó (ver §7, evidencia de test).

## 4 · State Machine

```
PENDING   -> RUNNING
RUNNING   -> { BLOCKED, FAILED, COMPLETED }
BLOCKED   -> RUNNING
FAILED    -> RUNNING
COMPLETED -> { APPROVED, REJECTED }
APPROVED  -> (terminal)
REJECTED  -> PENDING
```

Derivado literalmente de FACTORY-SPEC.md §8. `COMPLETED -> RUNNING` (el ejemplo de
transición inválida del pedido de Fase 2) no está en el mapa y por lo tanto se
rechaza — probado explícitamente en `test_completed_a_running_es_invalida`.

## 5 · Run

```json
{
  "run_id": "...",
  "factory_version": "0.1.0",
  "status": "RUNNING",
  "current_stage": "Specification",
  "created_at": "...",
  "updated_at": "...",
  "events": [ { "event_id": "...", "event_type": "RUN_CREATED", "...": "..." } ],
  "artifacts": []
}
```

`artifacts` existe en el esquema desde ahora (lista vacía) para no romper el
contrato de forma cuando un Generator empiece a producir código en una fase futura —
pero el Kernel de esta fase no lo llena.

## 6 · Events

Seis tipos mínimos (`kernel/events.py::EventType`): `RUN_CREATED`, `STATE_CHANGED`,
`STAGE_STARTED`, `STAGE_COMPLETED`, `ERROR`, `BLOCKED`. Cada uno lleva
`event_id`/`run_id`/`timestamp`/`event_type`/`stage`/`status`/`metadata`.

**Decisión no obvia**: un intento de transición inválida SÍ queda registrado (como
`ERROR`) antes de propagar la excepción — no se descarta en silencio. Esto significa
que la trazabilidad de eventos incluye lo que el Kernel *rechazó*, no solo lo que
aceptó (`test_transicion_invalida_es_rechazada_y_no_muta_el_run` verifica ambas cosas
a la vez: que el estado no cambió y que el evento sí quedó).

## 7 · Límites actuales (qué NO hace este Kernel)

- No ejecuta ningún Agent — nada de Classifier/Generator/Validator/Reviewer/
  Coordinator existe como código todavía.
- No genera Specification, Architecture, Contracts, Invariants, Evals, Plan, Tasks
  ni Code — `advance_stage()` solo mueve un puntero de texto (`current_stage`) entre
  nombres de etapa; no produce ningún artefacto real para esas etapas.
- No hay MCP real, ni paralelismo, ni Reuse/Knowledge/Risk Engine, ni Human Gates
  operativos (más allá de que `RunStatus.BLOCKED` existe como estado — nada lo
  dispara automáticamente todavía).
- La persistencia es un archivo JSON por `run_id` bajo `software-factory/runs/`
  (gitignoreado). Es deliberadamente la opción más simple: sin agregar Postgres ni
  ninguna dependencia nueva, y sin tocar `engine/db.py` ni `market_db.py` — mantiene
  al Kernel sin ninguna dependencia de infraestructura del ETL. FACTORY-SPEC.md §9
  deja el mecanismo como NO DETERMINABLE a nivel de diseño; esta es la elección
  concreta de esta fase, no la definitiva.
- `FactorySpecLoader` parsea la tabla de la Sección 7 (formato Markdown estable) pero
  **no** intenta parsear la prosa/diagrama de flechas de la Sección 8 para derivar
  las transiciones automáticamente — ver la decisión siguiente.

## 8 · Decisiones de implementación

1. **Lenguaje y test runner**: Python 3.11 + pytest. Verificado por inspección, no
   asumido — es el lenguaje de `engine/`, `scripts/`, `api/`, `backend/`, y pytest es
   el runner ya usado en `scripts/market/tests/` y en `tests/` de la raíz (más de 20
   archivos `test_*.py` con fixtures y `conftest.py`). No se introdujo ninguna
   dependencia nueva: solo se usa la librería estándar (`ast`, `json`, `enum`,
   `dataclasses`, `pathlib`, `uuid`, `re`) y `pytest`, ya presente en el entorno.
2. **Estilo de código**: siguiendo la convención ya establecida en
   `engine/states.py` (que ya implementa una máquina de estados para el ETL, con
   `class X(str, Enum)` + `TRANSITIONS: dict[Estado, set[Estado]]` +
   `assert_transition()`). El Kernel reproduce ese *patrón* de diseño — no importa
   ni depende de ese archivo (`test_independence.py` lo verifica).
3. **Nombres de estado en mayúscula**: FACTORY-SPEC.md §8 los escribe en minúscula
   (prosa). El pedido de Fase 2 pide explícitamente `PENDING/RUNNING/BLOCKED/FAILED/
   COMPLETED` en mayúscula. Se normalizó a mayúscula en código, siguiendo también la
   convención de `engine/states.py::StageState`. Es una normalización de forma; un
   test (`test_estados_de_state_machine_coinciden_con_lo_que_menciona_la_spec`)
   verifica que el *conjunto* de nombres (case-insensitive) sigue coincidiendo
   exactamente con lo que la spec menciona.
4. **Por qué no se parsea la Sección 8 para derivar transiciones automáticamente**:
   la Sección 7 es una tabla Markdown — formato tabular, estable, de bajo riesgo de
   parseo ambiguo. La Sección 8 es un diagrama de flechas en prosa dentro de un
   bloque de código, sin gramática formal (`pending -> running -> { blocked | failed
   | completed }`) — parsearlo automáticamente para *generar* el `TRANSITIONS` dict
   sería frágil (cualquier reformulación de la prosa rompería el parser en tiempo de
   carga, no en tiempo de test) y no aporta más seguridad que la alternativa elegida:
   declarar `TRANSITIONS` en Python (código legible, testeable con casos concretos) y
   verificar por test que coincide con lo que la spec menciona. Si se quisiera derivar
   automáticamente en una fase futura, requeriría primero formalizar la notación de
   la Sección 8 de la spec misma (decisión de spec, no de Kernel) — se deja
   NO DETERMINABLE CON LA INFORMACIÓN DISPONIBLE.
5. **`RunManager` no persiste automáticamente**: separa la lógica de transición
   (testeable sin filesystem) de la persistencia (`StateManager`, explícita). Quien
   opera el Kernel decide cuándo guardar — visible en `demo.py`, que guarda una sola
   vez al final.

## 9 · Qué queda para la Fase 3

- Coordinator real: hoy `RunManager` expone las operaciones, pero nada decide *por sí
  mismo* qué operación corresponde según el estado — eso es exactamente lo que un
  Coordinator agregaría (orquestación automática basada en evidencia).
- Los 5 Agents (Classifier/Generator/Validator/Reviewer/Coordinator como ejecutores,
  no solo como concepto).
- Contracts/Invariants/Evals como objetos verificables en tiempo de ejecución (hoy
  son solo prosa en FACTORY-SPEC.md).
- Un mecanismo de Evidence (§12 de la spec) que efectivamente bloquee una transición
  de Pipeline si no hay evidencia — hoy el Kernel valida transiciones de *estado*,
  pero no exige evidencia de Contracts/Invariants antes de permitir avanzar de etapa.
- Human Gates operativos (hoy `BLOCKED` existe como estado alcanzable, pero nada lo
  dispara automáticamente ni notifica a una persona).
- Decidir el mecanismo de persistencia definitivo (JSON por archivo no escala a
  concurrencia real ni a queries sobre el historial de Runs).

## 10 · Addendum (Fase 3) — extensiones al Kernel, no reemplazos

La Fase 3 (Coordinator + Agent Registry + Classifier — ver `COORDINATOR.md`,
`AGENT-REGISTRY.md`, `agents/CLASSIFIER.md`) **extendió** estos componentes del
Kernel, sin crear versiones paralelas:

- `kernel/pipeline_definition.py`: `PipelineStage` ganó `typical_agents` (la columna
  "Agent(s) típico(s)" de la tabla real de §7, antes descartada); `PipelineDefinition`
  ganó `agents_for(stage)`.
- `kernel/factory_spec_loader.py`: `_extract_pipeline()` ahora puebla ese campo.
- `kernel/run_manager.py`: `Run` ganó `evidence`/`last_agent`/`last_result`;
  `RunManager` ganó `record_evidence()`.
- `kernel/events.py`: nuevo `EventType.EVIDENCE_RECORDED` + `EventLogger.evidence_recorded()`.
- `kernel/errors.py`: `AgentNotFoundError`, `AgentDisabledError`, `NoAgentAuthorizedError`.

Los 33 tests de la Fase 2 se re-corrieron después de cada extensión y siguen en
verde — son adiciones con default seguro (`field(default_factory=list)`,
`None`), no cambios de forma sobre lo que ya existía.
