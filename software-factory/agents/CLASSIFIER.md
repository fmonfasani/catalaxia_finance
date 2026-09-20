# CLASSIFIER

**Archivo**: `agents/classifier.py`. **Estado**: implementado, probado (Fase 3).
**Agent Registry id**: `"classifier"`.

## Responsabilidad

**Clasificar y dirigir.** Recibe un texto libre (un Project Input, típicamente lo que
se convertirá en un Requirement) y produce una clasificación estructurada:
`{category, confidence, reason}`, con `category ∈ {FEATURE, BUG, QUESTION}`.

FACTORY-SPEC.md §6 le atribuye un alcance mayor a futuro (tipo, dominio, complejidad,
descomposición jerárquica — §16.1). Esta implementación cubre únicamente el `category`
mínimo pedido para esta fase; dominio/complejidad/descomposición no están
implementados y no se simulan.

## Inputs

`str` no vacío. Cualquier otra cosa (`None`, string vacío, no-string) produce un
`AgentResult` con `status="ERROR"` — el Classifier nunca lanza una excepción por un
input mal formado, solo por un bug real de su propio código.

## Outputs

Un `agent_contract.AgentResult` con:
- `output = {"category": "FEATURE"|"BUG"|"QUESTION", "confidence": float, "reason": str}`
- `status = "OK"` (clasificación producida) o `"ERROR"` (input inválido)

## Límites (qué NO hace — literal del pedido de Fase 3)

No genera código, no modifica archivos, no ejecuta herramientas, no decide
arquitectura, no modifica el estado global del `Run` (eso lo hace el Coordinator, vía
`RunManager`, con el `AgentResult` que el Classifier le devuelve), no ejecuta otros
agentes.

## Cómo clasifica (determinista, sin LLM)

Reglas por palabras clave, evaluadas en este orden — mismo input, mismo output,
siempre:

1. **QUESTION**: contiene `?`/`¿`, o una palabra interrogativa conocida ("cómo",
   "qué es", "por qué", "es posible", "se puede"...). Se evalúa primero a propósito:
   una pregunta sobre un error ("¿por qué da error el login?") sigue siendo una
   pregunta, no un bug — se está preguntando, no reportando.
2. **BUG**: contiene una palabra asociada a un defecto ya ocurrido ("error", "falla",
   "no funciona", "se cae", "excepción"...).
3. **FEATURE**: contiene una palabra asociada a pedir una capacidad nueva
   ("agregar", "necesitamos", "implementar", "alta de"...).
4. Si ninguna regla coincide: `FEATURE` con `confidence=0.4` (explícitamente baja,
   para que se note que fue un default, no una clasificación segura).

**Por qué determinista y no un LLM en esta fase** (pedido explícito, no una
limitación técnica): permite demostrar el circuito completo
Kernel→Coordinator→Registry→Classifier→Evidence→State sin la variabilidad de un LLM
de por medio, y deja el contrato (`execute(str) -> AgentResult`) idéntico al que
tendría una versión futura respaldada por un modelo — cambiar `classify()` por una
llamada a un LLM no requeriría tocar `ClassifierAgent.execute()` ni al Coordinator.

## Relación con el Kernel

Ninguna directa. El Classifier no importa nada de `kernel/` — solo implementa
`agent_contract.BaseAgent`. Es el Coordinator quien lo conecta con el `Run`.

## Relación con el State

No toca el `Run` ni el archivo de estado. Devuelve un `AgentResult`; es el
Coordinator quien lo convierte en evidencia sobre el `Run`.

## Evidencia

Cada `execute()` produce exactamente un `AgentResult` — la evidencia mínima exigida
(`agent_id`, `input`, `output`, `status`, `timestamp`), con un `result_id` propio
para poder referenciarlo individualmente si en el futuro hay más de una ejecución del
mismo agente sobre el mismo `Run`.

## Qué NO implementa todavía

Clasificación de dominio o complejidad, descomposición jerárquica (§16.1 de la
spec), uso de un LLM, ni ningún estado propio entre ejecuciones (`classify()` es una
función pura, sin memoria de clasificaciones anteriores).
