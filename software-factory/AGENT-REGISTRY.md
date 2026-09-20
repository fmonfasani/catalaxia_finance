# AGENT REGISTRY

**Archivo**: `coordinator/agent_registry.py`. **Estado**: implementado, probado (Fase 3).

## Responsabilidad

Registrar agentes disponibles, permitir recuperarlos por `id`, verificar si están
habilitados, y exponer su metadata (`agent_contract.AgentMetadata`). Nada más.

## Inputs

- `register(agent: BaseAgent)` — cualquier objeto que implemente el `agent_contract`
  (ver `agents/CLASSIFIER.md` para el único agente concreto de esta fase).

## Outputs

- `get(agent_id)` → el agente registrado, o `AgentNotFoundError` si no existe.
- `get_enabled(agent_id)` → como `get()`, pero además exige `metadata.enabled=True`,
  o levanta `AgentDisabledError`.
- `is_registered(agent_id)` / `is_enabled(agent_id)` → booleanos, sin excepciones.
- `metadata_for(agent_id)` → `AgentMetadata`.
- `list_ids()` → los `id` registrados, ordenados.

## Límites (qué NO hace)

- **No ejecuta agentes.** Ningún método del Registry llama a `agent.execute()` — eso
  es exclusivamente responsabilidad del Coordinator.
- **No decide el pipeline.** El Registry no sabe qué etapa está autorizada para qué
  agente — esa relación vive en `PipelineDefinition` (Kernel), derivada de
  FACTORY-SPEC.md §7. El Registry solo responde "¿existe y está habilitado el agente
  X?", nunca "¿corresponde el agente X a esta etapa?".
- No valida el contrato de un agente en el momento de `register()` más allá de que
  tenga un atributo `metadata` con un `id` — no re-verifica que implemente
  `execute()` correctamente (eso lo garantiza `BaseAgent` siendo una clase abstracta:
  no se puede instanciar sin implementar `execute()`).

## Relación con el Kernel

Ninguna directa — el Registry es un componente nuevo de esta fase, sin dependencia
del Kernel ni viceversa. El Coordinator es quien conecta ambos.

## Diseño para extensión futura

Agregar `generator`, `validator`, `reviewer` no requiere modificar el mecanismo
central del Registry — es exactamente el mismo `register()`/`get()`/`get_enabled()`
para cualquier objeto que cumpla `agent_contract.BaseAgent`. El Registry ya es
agnóstico del rol concreto del agente (`AgentMetadata.role` es solo un campo
descriptivo, no algo que el Registry inspeccione para decidir su comportamiento).

## Evidencia / Audit

El Registry en sí no genera evidencia (no ejecuta nada) — la evidencia de que un
agente corrió la genera el propio agente (`AgentResult`) y la registra el
Coordinator vía `RunManager.record_evidence()`.

## Qué NO implementa todavía

Habilitar/deshabilitar un agente en caliente (`enabled` es fijo desde que se
construye el `AgentMetadata`), versionado de agentes, ni un mecanismo de descubrimiento
automático de agentes (hoy el registro es manual: quien arma el Coordinator llama
`registry.register(...)` explícitamente para cada agente).
