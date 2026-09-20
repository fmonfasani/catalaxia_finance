# COORDINATOR

**Archivo**: `coordinator/coordinator.py`. **Estado**: implementado, probado (Fase 3).

## Responsabilidad

Orquestar la ejecución de un Agent para la etapa actual de un `Run` — nada más.
Concretamente: leer la etapa actual, preguntarle a `PipelineDefinition` (Kernel, ya
existente) qué agente autoriza FACTORY-SPEC.md §7 para esa etapa, pedirle ese agente
al `AgentRegistry`, ejecutarlo, registrar el resultado como evidencia, y pedirle al
Kernel (`RunManager`) la transición de estado que corresponda según el resultado.

**Principio, citado literalmente del pedido de Fase 3**: *Coordinator ORQUESTA. Agent
EJECUTA. Kernel CONTROLA.* El Coordinator nunca decide *cómo* clasificar, nunca muta
`run.status`/`run.evidence` directamente, y nunca elige un agente que la etapa no
autorizó.

## Inputs

- Un `Run` (del Kernel — `kernel.run_manager.Run`), ya creado por `RunManager`.
- Un `input_data` (hoy: un string de texto libre — el "Project Input").

## Outputs

- El mismo `Run`, mutado únicamente a través de las interfaces del Kernel
  (`RunManager.transition()`, `RunManager.record_evidence()`) — nunca por asignación
  directa a sus atributos.

## Límites (qué NO hace)

- No implementa lógica de clasificación, generación, validación ni revisión — eso
  vive en cada Agent (`agents/`).
- No muta `run.status` ni `run.evidence` directamente — siempre vía `RunManager`.
- No se salta la `StateMachine`: si la transición que intenta pedir es inválida
  (por ejemplo, el `Run` ya está en un estado terminal como `APPROVED`), la excepción
  del Kernel se propaga tal cual — el Coordinator no la atrapa ni la reinterpreta.
- No ejecuta un agente no registrado ni deshabilitado — delega esa verificación
  íntegramente en `AgentRegistry.get_enabled()`.
- No ejecuta un agente que la etapa actual no autorizó — el `agent_id` sale
  exclusivamente de `PipelineDefinition.agents_for(stage)`, que a su vez viene de la
  tabla real de FACTORY-SPEC.md §7 (columna "Agent(s) típico(s)") — nunca de un mapa
  paralelo mantenido a mano en este archivo.
- Si la etapa actual tiene más de un agente típico declarado (p. ej. "Generator +
  Reviewer" para `Architecture`), esta fase solo sabe pedir el primero — orquestar
  múltiples agentes en una misma etapa es explícitamente una capacidad de una fase
  futura, no de este Coordinator mínimo.

## Relación con el Kernel

El Coordinator depende de tres piezas del Kernel, todas ya existentes desde la Fase 2,
ninguna reimplementada:

- `RunManager.pipeline` (`PipelineDefinition.agents_for()`) — para saber qué agente
  corresponde a la etapa actual.
- `RunManager.transition()` — para cambiar `run.status`, siempre validado por
  `StateMachine`.
- `RunManager.record_evidence()` (nuevo método agregado a `RunManager` en esta fase,
  no una clase nueva) — para dejar la evidencia y su evento asociado.

## Relación con el State

El Coordinator no lee ni escribe el archivo de estado directamente — solo opera sobre
el objeto `Run` en memoria que le pasan, y es responsabilidad de quien lo invoca (la
demo, o en el futuro un runner) llamar a `StateManager.save()` después.

## Evidencia

Cada ejecución de `execute_stage()` deja, como mínimo, un elemento en `run.evidence`
con la forma `{agent_id, input, output, status, timestamp}` (ver `agent_contract.py`
→ `AgentResult`), y un evento `EVIDENCE_RECORDED` en `run.events`.

## Qué NO implementa todavía

Selección de múltiples agentes por etapa, reintentos automáticos ante `FAILED`,
Human Gates (aunque `BLOCKED` existe como estado alcanzable, nada lo dispara desde
el Coordinator todavía), Risk Level — Contracts (Fase 5A), Invariants+Evals+Validator
(Fase 5B) y la orquestación multi-etapa dentro de un mismo Run (Fase 5C, ver Addendum)
sí quedaron cubiertos por fases posteriores a esta.

## Addendum (Fase 5C) — `execute_pipeline()`: orquestación multi-etapa, mismo Run

**Problema que resuelve**: `execute_stage()` (arriba, sin cambios desde la Fase 5B) es
"una llamada = un agente = una transición terminal (`COMPLETED`/`FAILED`)". Eso es
correcto para una única etapa, pero no permite demostrar Generator (etapa `"Code"`) y
Validator (etapa `"Validation"`) dentro del **mismo** `run_id`: tras la primera llamada
el `Run` ya está en `COMPLETED`, y la StateMachine prohíbe explícitamente
`COMPLETED -> RUNNING` (regla de la Fase 2) — una segunda llamada fallaría.

**Solución**: `Coordinator.execute_pipeline(run, steps)`, donde `steps` es una lista de
`(stage_name, input_data_o_builder)`. Internamente:

1. Extrae la lógica de "correr un agente para la etapa actual" a un método privado
   `_run_single_agent()` — la misma lógica exacta que antes vivía inline dentro de
   `execute_stage()`, sin cambiar un solo evento ni decisión (`execute_stage()` ahora
   es literalmente un `for` de un solo paso sobre ese mismo helper).
2. Para cada paso: si la etapa actual del `Run` no es la del paso, llama
   `RunManager.advance_stage()` (encadenado al mismo `COORDINATOR_STARTED` vía
   `parent_event_id`, extendido en esta fase); ejecuta el agente autorizado; si
   `input_data_o_builder` es un `callable`, lo invoca con `(artifact, evidence)` del
   paso **anterior** — así el Validator recibe una referencia **explícita** al
   `artifact` real que el Generator acaba de producir, sin que el Coordinator necesite
   conocer de antemano un artifact que todavía no existe, y sin que el Validator tenga
   que "adivinarlo".
3. Se detiene en el primer paso que no avanza (falla de agente, violación de Contract,
   o veredicto `FAIL`) — los pasos restantes de `steps` no se ejecutan.
4. Recién al final, UNA sola vez, decide la transición terminal: `COMPLETED` si **todos**
   los pasos avanzaron, `FAILED` si alguno no.

**Lo que el Coordinator sigue sin hacer**: no ejecuta lógica de Generator ni de
Validator (sigue llamando `agent.execute()` genéricamente), no decide manualmente
PASS/FAIL (sigue leyendo `output["result"]`, mecanismo ya generic de la Fase 5B), no
se convierte en un "super-agente" — `_run_single_agent()` es exactamente el mismo
código que ya existía, solo invocado más de una vez antes de decidir el veredicto.

**Compatibilidad**: `execute_stage()` no cambió su comportamiento observable — los 127
tests de las fases 2 a 5B siguen pasando sin ninguna modificación
(`tests/test_same_run_pipeline.py::test_execute_stage_preserva_comportamiento_exacto_previo`
lo verifica explícitamente, evento por evento). `execute_pipeline()` es aditivo.

Ver [VALIDATOR.md](VALIDATOR.md) (Addendum Fase 5C) y `demo.py` para la ejecución real
de Generator→Validator sobre un único `run_id`, en los casos PASS y FAIL.
