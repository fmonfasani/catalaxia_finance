# OBSERVABILITY — observabilidad transversal de la Software Factory

**Archivo principal**: `observability.py` (raíz de `software-factory/`, no dentro de
`kernel/`, `coordinator/` ni `agents/`). **Estado**: implementado, probado (Fase 4A).

## Objetivo

Poder reconstruir completamente qué ocurrió en cualquier ejecución (`Run`) usando
únicamente lo que la Factory ya registró — sin inferencia, sin re-ejecutar nada.

## Arquitectura

```
                    OBSERVABILITY (observability.py)
                         │  lee, no almacena de nuevo
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
      KERNEL         COORDINATOR        AGENT
   (RunManager,      (coordinator.py)  (agents/classifier.py,
    events.py)                          via agent_contract.py)
```

`observability.py` **no pertenece** al Kernel, al Coordinator ni a ningún Agent —
ninguno de esos tres lo importa. Es al revés: `observability.py` importa `Run` y
`StateManager` del Kernel para poder leerlos. Esto es deliberado: si la observabilidad
viviera dentro del Coordinator (como se probó de forma implícita en la Fase 3, donde
`RunManager` ya emitía algunos eventos por su cuenta), un futuro Generator/Validator/
Reviewer tendría que reimplementar la misma lógica de correlación cada vez. Al ser
transversal, cualquier componente nuevo solo necesita emitir eventos con la forma que
`EventLogger` ya define — la reconstrucción (`observability.py`) los entiende a todos
por igual, sin saber nada de Classifier, Generator, Validator ni Reviewer en particular.

**No se creó un sistema paralelo.** Se extendieron tres piezas que ya existían:

- `kernel/events.py` — `Event` ganó `component`, `component_id`, `parent_event_id`,
  `input_reference`, `output_reference` (todos opcionales, `None` por defecto — un
  evento de la Fase 2 sigue siendo válido). `EventLogger` ganó builders para los tipos
  nuevos, pero los 7 que ya existían (`RUN_CREATED`, `STATE_CHANGED`, `STAGE_STARTED`,
  `STAGE_COMPLETED`, `ERROR`, `BLOCKED`, `EVIDENCE_RECORDED`) se reutilizan tal cual.
- `kernel/run_manager.py` — `RunManager.transition()` ahora también emite
  `RUN_STARTED`/`RUN_COMPLETED`/`RUN_FAILED` cuando la transición cruza el umbral
  correspondiente (PENDING→RUNNING, →APPROVED, →REJECTED), y ganó `emit()`, el único
  punto por el que un componente externo (Coordinator) agrega un evento a `run.events`.
- `coordinator/coordinator.py` — ahora emite `COORDINATOR_STARTED/COMPLETED` y
  `AGENT_SELECTED/STARTED/COMPLETED/FAILED`, construidos con el mismo `EventLogger` y
  registrados con el mismo `RunManager.emit()`/`transition()`/`record_evidence()` de
  siempre — el Coordinator no implementa observabilidad, la usa.

## Eventos

**Ya existían (Fase 2/3), reutilizados sin cambios de significado**: `RUN_CREATED`,
`STATE_CHANGED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `ERROR`, `BLOCKED`,
`EVIDENCE_RECORDED`.

**Nuevos (Fase 4A)**: `RUN_STARTED`, `RUN_COMPLETED`, `RUN_FAILED`,
`COORDINATOR_STARTED`, `COORDINATOR_COMPLETED`, `AGENT_SELECTED`, `AGENT_STARTED`,
`AGENT_COMPLETED`, `AGENT_FAILED`.

**Pedidos pero deliberadamente NO agregados como tipos nuevos** (para no duplicar):

- `STAGE_BLOCKED`/`STAGE_FAILED` — ya representables con `BLOCKED`/`ERROR` + el campo
  `stage` que `Event` ya tenía desde la Fase 2.
- `STATE_TRANSITION` — es lo que `STATE_CHANGED` ya es, con otro nombre.

**Distinción no obvia — `RunStatus.COMPLETED` (estado) vs. `RUN_COMPLETED` (evento)**:
son cosas distintas a propósito. `RunStatus.COMPLETED` significa "un agente terminó de
producir algo para esta etapa, pendiente de aprobación" (no es terminal — puede seguir
a `APPROVED` o `REJECTED`). `RUN_COMPLETED` es un evento de observabilidad que solo se
emite cuando el `Run` llega a `APPROVED`, el único estado verdaderamente terminal de
éxito en la `StateMachine`. Análogamente, `RUN_FAILED` se emite en la transición a
`REJECTED` (el veredicto final de "no aceptado"), no en cada `RunStatus.FAILED`
transitorio de un reintento — para eso ya existe `AGENT_FAILED`/`ERROR` a nivel de
intento. Ver `AGENT-REGISTRY.md`/`COORDINATOR.md` para el resto del vocabulario.

## Trace

Un `Trace` (`observability.build_trace()`) es una **vista de lectura**, no un
almacenamiento nuevo: reconstruye el árbol de eventos de un `Run` ya serializado,
usando `parent_event_id` para anidar. No existe un `Trace` persistido en disco aparte
del propio `Run` — se recalcula cada vez que se pide, a partir de los mismos eventos.

Ejemplo real (`demo.py`, corrida real, no ilustrativa):

```
TRACE run_id=0ff223b2-...
+-- RUN_CREATED (component=KERNEL stage=None)
+-- COORDINATOR_STARTED (component=COORDINATOR stage=Requirement)
    +-- AGENT_SELECTED (component=COORDINATOR stage=Requirement)
    +-- STATE_CHANGED (component=KERNEL stage=Requirement)
    +-- RUN_STARTED (component=KERNEL stage=Requirement)
    +-- AGENT_STARTED (component=AGENT stage=Requirement)
    +-- AGENT_COMPLETED (component=AGENT stage=Requirement)
    +-- EVIDENCE_RECORDED (component=KERNEL stage=Requirement)
    +-- STATE_CHANGED (component=KERNEL stage=Requirement)
    +-- COORDINATOR_COMPLETED (component=COORDINATOR stage=Requirement)
```

`RUN_CREATED` es su propia raíz a propósito: ocurre antes de que exista cualquier
Coordinator (un `Run` puede crearse sin nunca ejecutar una etapa). Todo lo que ocurre
*dentro* de una llamada a `Coordinator.execute_stage()` — incluidas las transiciones de
estado que decide el Kernel — cuelga de ese `COORDINATOR_STARTED`, porque
`RunManager.transition()` ahora acepta un `parent_event_id` opcional y el Coordinator
se lo pasa. Sin esto, las transiciones habrían quedado como raíces sueltas,
desconectadas de qué las originó — es exactamente lo que
`test_parent_event_id_permite_reconstruir_relaciones` verifica que no pase.

No se usa Unicode de caja (`└──`) en `render_trace()`: se probó en este entorno
(consola Windows, codepage cp1252 por defecto) y rompe con `UnicodeEncodeError`. Se usa
`+--`/`|` (ASCII).

## Correlación

Todo evento lleva `run_id` (obligatorio desde la Fase 2). Los nuevos campos
(`component`, `component_id`, `parent_event_id`) permiten responder "quién hizo esto"
y "en el contexto de qué otra cosa" sin tener que inferirlo del orden temporal —
aunque el orden temporal (`timestamp`) también se mantiene consistente con el orden
lógico (verificado: `test_eventos_mantienen_orden_temporal_logico`).

`factory_id`/`factory_version` — `factory_version` ya existía en `Run` desde la Fase 2
(viene de `FactorySpecLoader`). Un `factory_id` explícito (para distinguir instancias
de la misma Factory corriendo en paralelo) **no se agregó**: no hay hoy ningún
escenario de múltiples instancias de la Factory coexistiendo que lo necesite — agregar
el campo ahora sería una capacidad no pedida por ninguna necesidad real todavía. Queda
como decisión pendiente si aparece esa necesidad.

## Agent observability

Ningún agente concreto (`agents/classifier.py`) importa `observability.py` ni
`kernel.events` — verificado por test (`test_observabilidad_funciona_con_el_classifier_
sin_logica_especifica`, que parsea el AST del archivo real). La observabilidad de una
ejecución de agente la produce el **Coordinator**, envolviendo la llamada a
`agent.execute()` con `AGENT_STARTED`/`AGENT_COMPLETED`/`AGENT_FAILED`. Cuando se
agreguen Generator/Validator/Reviewer, ninguno necesitará tocar una línea de
observabilidad propia — el mismo Coordinator los envuelve igual.

## Coordinator observability

Ver `COORDINATOR.md`. El Coordinator emite, en este orden, para cada
`execute_stage()`: `COORDINATOR_STARTED` → `AGENT_SELECTED` → (delega en `RunManager`
para `RUNNING`, que dispara `STATE_CHANGED`/`RUN_STARTED` si corresponde) →
`AGENT_STARTED` → `AGENT_COMPLETED`/`AGENT_FAILED` → `record_evidence` (dispara
`EVIDENCE_RECORDED`) → transición final (`STATE_CHANGED` y, si corresponde,
`RUN_COMPLETED`/`RUN_FAILED`) → `COORDINATOR_COMPLETED`. El Coordinator no decide el
contenido de ningún evento más allá de qué builder de `EventLogger` llamar — no
implementa un mecanismo de observabilidad propio.

## Kernel observability

`RunManager` sigue siendo, como en la Fase 2, el dueño exclusivo de `run.events` para
todo lo que el propio Kernel decide (creación, transiciones, avance de etapa). La
Fase 4A no le quitó esa responsabilidad — se la amplió (ahora también emite
`RUN_STARTED`/`RUN_COMPLETED`/`RUN_FAILED`) y le agregó una puerta (`emit()`) para que
algo externo (Coordinator) pueda sumar eventos sin romper esa exclusividad sobre
*cómo* se agregan (siempre actualiza `updated_at`, siempre por el mismo método).

## Evidence

Sin cambios de contrato respecto de la Fase 3: `run.evidence` sigue siendo la lista
completa, sin redactar, de cada `AgentResult.to_dict()` — es la fuente de verdad
completa, no la de observabilidad. Lo que la Fase 4A agrega es la CORRELACIÓN de esa
evidencia con el resto del trace: `EVIDENCE_RECORDED.parent_event_id` apunta al
`COORDINATOR_STARTED` que la originó (verificado:
`test_evidence_queda_correlacionada`), y `query_run()` la expone junto con eventos,
transiciones y agentes en una sola respuesta.

## Audit vs. Observability vs. Traceability — no se mezclan

- **Observability** (este documento): permite conocer qué está ocurriendo y
  reconstruir la ejecución — es el `Trace`, es `query_run()`.
- **Audit** (ya existía desde FACTORY-SPEC.md §13, implementado como `run.events`
  desde la Fase 2): conserva evidencia verificable de lo ocurrido. Los eventos SON el
  audit — la observabilidad no crea un audit nuevo, lo hace legible/reconstruible.
- **Traceability** (FACTORY-SPEC.md §10, todavía no implementada como mecanismo):
  relaciona Requirement→Specification→...→Delivery — una cadena de *artefactos SDD*,
  no de *eventos de ejecución*. `parent_event_id` correlaciona eventos dentro de UN
  `Run`; no reemplaza (ni todavía puede construir) la cadena `REQ-001→SPEC-001→...`
  porque esta fase no genera Specifications ni ningún otro artefacto SDD — solo
  clasifica.

No se confunden: un `Run` completo, con su Trace entero, puede en el futuro ser **un
solo eslabón** de una cadena de Traceability más larga (el "Action" que produjo un
"Artifact" con su "Evidence").

## Persistencia

Sin cambios respecto de la Fase 2: JSON por `run_id` (`StateManager`). No se incorporó
PostgreSQL, Redis, OpenTelemetry Collector, Grafana ni Jaeger — el repositorio no los
usa hoy para nada equivalente a esto, y la regla de esta fase era no incorporarlos sin
evidencia de que ya se reutilizan. La arquitectura queda preparada para un backend
externo sin cambios de forma: `Event`/`Run` ya son dicts serializables; un backend
futuro solo necesitaría un `StateManager` alternativo con la misma interfaz
(`save`/`load`/`list_run_ids`/`exists`).

## Seguridad — qué se redacta y qué no

`observability.redact_structure()`/`make_reference()` redactan valores de dict cuya
**clave** coincide con una lista de marcadores (`password`, `secret`, `token`,
`api_key`, `credential`, `auth`, `private_key`, ...) — el valor se reemplaza por
`<REDACTED:sha256:xxxx>` (hash truncado, permite correlacionar "es el mismo valor"
sin exponerlo). Se aplica a `input_reference`/`output_reference` de los eventos
`AGENT_STARTED`/`AGENT_COMPLETED`/`AGENT_FAILED` — nunca al string libre de
`input_data` completo, que además se trunca a 160 caracteres.

**Limitación explícita, no oculta**: esto es una heurística por **nombre de clave**,
no un escaneo de contenido. Un secreto embebido dentro de un string libre sin una
clave que lo declare (p. ej. `"la contraseña es hunter2"` como texto plano) **no se
detecta ni se redacta** — coincide exactamente con la limitación que
`test_no_se_registran_secrets_en_las_referencias` documenta al probar la propiedad
sobre una `dict`, no sobre prosa libre. Detectar secretos dentro de texto libre
requeriría un escáner de patrones (regex de formatos conocidos de token, entropía,
etc.) — explícitamente fuera de alcance de esta fase.

`run.evidence` (Fase 3, sin cambios) sigue guardando el input/output completo, sin
redactar — es la evidencia de negocio, no la observabilidad. Si en el futuro un Agent
maneja datos sensibles de verdad, la redacción de `run.evidence` en sí sería una
decisión de esa fase (Generator/Validator reales), no de esta.

## Consulta

`observability.query_run(run_id, state_manager=None)` — función Python (no CLI, no
UI; el resto del Kernel tampoco tiene una, y `demo.py` es el único punto de entrada
ejecutable del repositorio hasta ahora). Devuelve `run_id`, `status`, `current_stage`,
`events`, `agents` (los `component_id` únicos de eventos con `component=AGENT`),
`transitions` (derivadas de los eventos `STATE_CHANGED`), `evidence`, `artifacts` —
todo leído de `StateManager.load()`, sin una fuente de datos nueva.

## Cobertura de "qué debe observarse" (lista mínima del pedido)

| Concepto | Cómo se cubre hoy |
|---|---|
| FACTORY | `run.factory_version`, ya en cada `Run` (Fase 2) |
| RUN | `run_id` en cada evento |
| STAGE | campo `stage` en cada evento |
| STATE TRANSITION | `STATE_CHANGED` (reusado, Fase 2) |
| COORDINATOR | `COORDINATOR_STARTED`/`COORDINATOR_COMPLETED`, `component=COORDINATOR` |
| AGENT | `AGENT_SELECTED/STARTED/COMPLETED/FAILED`, `component=AGENT` |
| AGENT INPUT | `input_reference` (redactado + truncado) |
| AGENT OUTPUT | `output_reference` (redactado + truncado) |
| DECISION | `AGENT_SELECTED.metadata.reason` (por qué ESE agente); toda transición queda en `STATE_CHANGED.metadata` |
| TOOL | **no implementado** — `Event.metadata` ya admite `{"tool": ...}` sin cambio de forma cuando exista un Agent que use una tool real (MCP explícitamente fuera de alcance esta fase) |
| ARTIFACT | modelo `Artifact` definido (`observability.py`), no conectado — ningún Generator existe todavía |
| EVIDENCE | `EVIDENCE_RECORDED` (reusado, Fase 3), correlacionado por `parent_event_id` |
| VALIDATION | **no implementado** — sin Validator no hay nada que observar; el patrón (`AGENT_*`) ya generaliza a un futuro `VALIDATION_*` sin cambios en `observability.py` |
| ERROR | `ERROR` (reusado, Fase 2) |
| BLOCK | `BLOCKED` (reusado, Fase 2) |
| REVIEW | **no implementado** — mismo caso que VALIDATION |
| TIMING | derivable de `timestamp` en cada evento (p. ej. `AGENT_COMPLETED.timestamp - AGENT_STARTED.timestamp`) — no se agregó un campo de duración redundante |

## Cambios a FACTORY-SPEC.md

**Ninguno.** Esta fase no encontró una definición normativa faltante o inconsistente
en FACTORY-SPEC.md — las Secciones 12 (Evidence) y 13 (Audit) ya describían
exactamente las categorías de evidencia y los campos de audit que se implementaron
(`ejecución, agente, decisión, input, output, resultado, timestamp, evidencia`); el
único campo de la Sección 13 sin cobertura dedicada es "herramienta", que queda
resuelto de forma genérica en `metadata` (ver tabla arriba) sin requerir una
definición normativa nueva.

## Limitaciones actuales

- No hay backend externo de observabilidad (OpenTelemetry, Grafana, Jaeger) — a
  propósito, esta fase.
- `parent_event_id` es de un solo padre — no modela un evento con múltiples
  orígenes (no hace falta hoy: ningún componente actual produce ese caso).
- La redacción es por nombre de clave, no por contenido — ver "Seguridad" arriba.
- No hay límite de tamaño ni rotación para `runs/*.json` — el mismo límite que ya
  tenía `StateManager` desde la Fase 2, sin agravarlo ni resolverlo.
- `query_run()` no pagina ni filtra — para el volumen actual (una ejecución de
  Classifier, ~10 eventos) no hace falta; con Generator/Validator produciendo más
  eventos por Run, podría hacer falta en una fase futura.
- No hay Trace entre Runs distintos (p. ej. un Requirement que generó dos Runs
  separados) — cada Trace es, hoy, exactamente un `Run`.

## Evolución futura

Cuando se implementen Generator/Validator/Reviewer, cada uno queda automáticamente
observable con el mismo mecanismo (el Coordinator los envuelve igual). El próximo salto
natural es un backend externo real (ver "Persistencia") cuando el volumen de Runs lo
justifique, y una Traceability real (REQ→SPEC→...→DELIVERY) cuando existan artefactos
SDD que relacionar — ninguna de las dos cosas se simuló ni se adelantó en esta fase.
