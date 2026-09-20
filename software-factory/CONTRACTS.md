# CONTRACTS — formalización de contratos del Pipeline

**Archivos**: `contracts.py` (modelo genérico), `contracts_catalog.py` (contratos
concretos). **Estado**: implementado, probado (Fase 5A).

## Qué es un Contract y por qué existe

FACTORY-SPEC.md §11 (Governance) ya definía el concepto, sin implementación:

> *"Contracts: forma verificable de una Specification. No ambiguos, no
> aspiracionales — si algo no puede verificarse mecánicamente, no es un Contract, es
> una guía."*

Antes de esta fase, lo más cercano que existía era `AgentMetadata.input_contract`/
`output_contract` (`agent_contract.py`) — dos **strings de prosa**, documentación para
un humano, nunca evaluados por código. El Coordinator confiaba en que el `output` de
cualquier agente exitoso tuviera la forma correcta únicamente porque el agente "decía"
tenerla. Un `Contract` (este módulo) es la contraparte **machine-readable**: algo que
se puede llamar y que devuelve una lista de violaciones concretas, no una descripción.

No reemplaza `input_contract`/`output_contract` — esos siguen siendo la documentación
humana de cada `AgentMetadata`. `Contract` es el chequeo mecánico correspondiente.

## Qué estaba formalizado y qué era implícito (diagnóstico previo a implementar)

| Contrato | Antes de esta fase |
|---|---|
| `BaseAgent.execute(input) -> AgentResult` | Explícito (ABC), pero sin schema — `input`/`output` son `Any` |
| Forma del output de Classifier (`category`/`confidence`/`reason`) | Implícito — solo en la docstring de `classifier.py` y en lo que `classify()` construye |
| Forma del output de Generator (`artifact`/`code_reference`) | Implícito — solo en `ARTIFACTS.md` (prosa) y en lo que `generator.py` construye |
| Forma de un `Artifact` | Semi-explícito — dataclass en `observability.py`, pero el Coordinator la trata como `dict` suelto sin validarla nunca |
| Estados y transiciones válidas de un `Run` | **Explícito y mecánicamente verificado** desde la Fase 2 (`kernel/state_machine.py`) — el único contrato real preexistente |
| Contratos de Validator/Reviewer | Inexistentes — ni siquiera en prosa fuera de FACTORY-SPEC.md §6 |

Esta fase no descubrió ninguna contradicción entre FACTORY-SPEC.md y el código — solo
una ausencia (contratos de agente sin forma verificable), consistente con lo que
`FACTORY-KERNEL.md` y `COORDINATOR.md` ya señalaban explícitamente como pendiente
("Contracts/Invariants/Evals como objetos verificables en tiempo de ejecución... hoy
no exige evidencia de Contracts/Invariants antes de permitir avanzar de etapa").

## El Contract Model (`contracts.py`)

Deliberadamente pequeño — no es un motor de JSON Schema genérico (sin `anyOf`, sin
anidamiento recursivo de sub-schemas). Verifica la forma **plana** de un `dict`:
campos presentes, tipo de cada uno, obligatoriedad. Mismo espíritu que
`agents/specification.py::FieldSpec` (un set chico de tipos, no un sistema de tipos
general), aplicado ahora a I/O de agentes en vez de a entidades de dominio generadas.

```python
@dataclass(frozen=True)
class FieldRule:
    name: str
    type: type | tuple[type, ...]
    required: bool = True

@dataclass(frozen=True)
class Schema:
    fields: tuple[FieldRule, ...] = ()
    def validate(self, value) -> list[str]: ...   # [] == valido

@dataclass(frozen=True)
class Contract:
    contract_id: str
    version: str
    producer: str              # agent_id que produce el output (o "coordinator")
    consumer: str              # agent_id que lo consume (o "coordinator")
    input_schema: Schema
    output_schema: Schema
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    allowed_states: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
```

`preconditions`/`postconditions`/`failure_conditions`/`evidence_requirements` son
**texto descriptivo** (igual que `input_contract`/`output_contract` de
`AgentMetadata`) — no expresiones ejecutables. Formalizarlas como código evaluable
(p. ej. un mini-DSL de invariantes) queda fuera de esta fase: no fue pedido, y
agregarlo ahora sería una abstracción sin un caso de uso real que la justifique
todavía. Lo único verificado **mecánicamente** hoy es la forma (`input_schema`/
`output_schema`) — que es exactamente lo que el Coordinator necesita para decidir si
acepta o rechaza un output.

`ContractRegistry` (mismo patrón que `AgentRegistry`, Fase 3): registra, obtiene por
`contract_id` (+ `version` opcional, default la más alta), lista ids. No ejecuta nada,
no decide el pipeline — solo expone contratos.

## Los contratos concretos (`contracts_catalog.py`)

Separado del modelo genérico a propósito: `contracts.py` no conoce a Generator ni a
Classifier por nombre; `contracts_catalog.py` es el único lugar que instancia
contratos concretos.

| Contract ID | producer → consumer | Estado |
|---|---|---|
| `CLASSIFIER_INPUT` | coordinator → classifier | Implementado (Schema vacío — ver nota abajo) |
| `CLASSIFIER_OUTPUT` | classifier → coordinator | Implementado, verificado contra el Classifier real |
| `GENERATOR_INPUT` | coordinator → generator | Implementado (Schema vacío — ver nota abajo) |
| `GENERATOR_OUTPUT` | generator → coordinator | Implementado, verificado contra el Generator real |
| `ARTIFACT_SHAPE` | generator → coordinator | Implementado — la forma de `observability.Artifact` como Contract |
| `VALIDATOR_INPUT` / `VALIDATOR_OUTPUT` | coordinator ↔ validator | **Definidos, no implementados** — Validator no existe como código |
| `REVIEWER_INPUT` / `REVIEWER_OUTPUT` | coordinator ↔ reviewer | **Definidos, no implementados** — Reviewer no existe como código |

### Nota: por qué `CLASSIFIER_INPUT`/`GENERATOR_INPUT` tienen `input_schema` vacío

El Classifier recibe un `str` suelto (`execute(input_data: str)`); el Generator recibe
una dataclass (`GeneratorInput`), no un `dict`. `Schema` valida la forma de un
**dict** — forzar una forma de dict inexistente sobre estos dos inputs habría exigido
cambiar el comportamiento real del Classifier/Generator, violando la regla explícita
de esta fase ("preservar completamente el comportamiento existente", "no cambies el
comportamiento del Generator salvo que sea estrictamente necesario"). En su lugar,
esos dos `Contract` documentan las precondiciones reales en `preconditions` (texto) y
dejan `input_schema` vacío — un `Schema()` sin campos declarados siempre valida
`True` para cualquier dict, así que no interfiere; la validación real de esos inputs
sigue viviendo donde ya vivía (`ClassifierAgent.execute()`'s `isinstance` check,
`Specification.validar()`). Extender `Schema` para validar dataclasses o tipos no-dict
queda fuera de esta fase — no hay todavía un caso de uso que lo requiera.

### Validator y Reviewer: contratos preparados, agentes no implementados

Siguiendo la Sección 6 de FACTORY-SPEC.md al pie de la letra:

- `VALIDATOR_OUTPUT.output_schema` exige `result` (`PASS`/`WARNING`/`BLOCK`/
  `NOT_CALCULABLE`), `violations` (lista), `evidence` (dict) — nunca una aprobación
  implícita por ausencia de error, tal como exige la spec.
- `REVIEWER_OUTPUT.output_schema` exige `result` (`PASS`/`FAIL`), `findings` (lista),
  `evidence` (dict) — con la postcondición textual de que un `FAIL` sin `findings` no
  es válido ("Aprobación explícita, con motivo — nunca silenciosa", FACTORY-SPEC.md
  §7).

Ningún código instancia `ValidatorAgent` ni `ReviewerAgent` — `AgentRegistry` no tiene
ningún agente con esos ids (verificado en
`tests/test_contracts.py::test_validator_y_reviewer_tienen_contratos_definidos_sin_implementacion`).
Los contratos quedan disponibles para cuando esos agentes se implementen, sin que
nada de esta fase los invoque.

## Integración con el Coordinator — completamente genérica

`coordinator/coordinator.py::Coordinator.__init__` gana un parámetro opcional
`contract_registry: ContractRegistry | None = None`. Con `None` (el default), el
Coordinator se comporta **exactamente** como en la Fase 4B — ningún test previo
necesitó cambiar. Cuando se pasa un `ContractRegistry`:

```python
def _output_contract_for(self, agent_id: str) -> Contract | None:
    if self.contract_registry is None:
        return None
    contract_id = f"{agent_id.upper()}_OUTPUT"
    if not self.contract_registry.is_registered(contract_id):
        return None
    return self.contract_registry.get(contract_id)
```

En `execute_stage()`, después de `agent.execute(input_data)` y antes de decidir si el
resultado fue exitoso:

```python
contract = self._output_contract_for(agent_id)
if result.status == "OK" and contract is not None:
    violaciones = contract.validate_output(result.output)
    if violaciones:
        result = replace(result, status="ERROR", output={
            "error": "contract_violation", "contract_id": contract.contract_id,
            "violations": violaciones, "original_output": result.output,
        })
```

**No hay ningún `if agent_id == "generator"` ni `if agent_id == "classifier"`.** La
convención `f"{agent_id.upper()}_OUTPUT"` es el único acoplamiento entre el
Coordinator y el catálogo de contratos — el mismo camino de código valida al
Classifier, al Generator, y a cualquier agente futuro que el catálogo declare.

### Qué pasa cuando un output viola su Contract

Se trata como una falla del agente, reutilizando el camino que ya existía para
`status == "ERROR"` (ningún mecanismo nuevo):

1. El resultado se reconstruye con `status="ERROR"` (vía `dataclasses.replace()` —
   conserva `result_id`, `agent_id`, `timestamp` originales).
2. El Coordinator emite `AGENT_FAILED` (no `AGENT_COMPLETED`) — mismo evento que
   cualquier otra falla de agente.
3. Como el `output` reconstruido ya no trae la clave `"artifact"` con forma válida
   (fue reemplazado por `{"error": "contract_violation", ...}`), el Coordinator
   **nunca llama a `record_artifact()`** — no queda un artifact a medias marcado como
   generado.
4. `RunManager.record_evidence()` registra igual la evidencia (con `status="ERROR"` y
   el detalle de qué contrato y qué violaciones) — la falla queda trazable, no oculta.
5. `RunManager.transition(run, FAILED)` — el Run nunca llega a `COMPLETED` con un
   output inválido.

Verificado en
`tests/test_contracts.py::test_coordinator_rechaza_output_incompatible_con_contrato`
(un Generator de prueba que devuelve `status="OK"` pero sin `code_reference`).

## Versionado

`contract_id` + `version` (string `"MAYOR.MENOR"`, sin parche) identifican un
Contract. `ContractRegistry.register()` permite múltiples versiones del mismo
`contract_id`; `get(contract_id)` sin `version` explícita devuelve la más alta
(comparación numérica de tupla, no lexicográfica — `"10.0"` no pierde contra
`"9.0"`). Esta fase **no implementa compatibilidad entre versiones** (no hay
migración ni traducción de un output v1.0 a v2.0) — el modelo solo garantiza que
puede *evolucionar* (agregar una v2.0 sin romper quien pide v1.0 explícitamente),
tal como pedía el alcance de esta fase.

## Tests

`tests/test_contracts.py` — 19 tests, cubriendo los 13 puntos pedidos (algunos
puntos comparten test, p. ej. AgentResult válido/inválido) más cobertura adicional
(versión por defecto, independencia del ETL, contratos de Validator/Reviewer
registrados sin agente). Todos aislados con `tmp_path` para el `output_dir` del
Generator — ninguno escribe en `software-factory/runs/` real.

## Relación con Kernel / Observability / Evidence

`Contract` no depende de `kernel/` ni de `observability.py`, y ninguno de esos módulos
depende de `contracts.py` — mismo patrón de capa transversal que ya usa
`observability.py` (Fase 4A): el Coordinator es quien conecta ambos mundos, sin que
uno conozca al otro directamente. Una violación de contrato se registra con el mismo
mecanismo de evidencia/eventos existente (`AgentResult`, `EVIDENCE_RECORDED`,
`AGENT_FAILED`) — no se creó un canal de auditoría paralelo para "violaciones de
contrato".

## Límites actuales (qué NO implementa)

- Sin validación de `input` de agente contra un Schema real (`CLASSIFIER_INPUT`/
  `GENERATOR_INPUT` tienen `input_schema` vacío — ver nota arriba). Solo se valida
  el `output`.
- Sin expresión ejecutable de `preconditions`/`postconditions`/`failure_conditions` —
  son texto descriptivo, igual que `AgentMetadata.input_contract`/`output_contract`.
- Sin compatibilidad entre versiones de un mismo contrato (no hay traducción v1→v2).
- Sin Validator ni Reviewer implementados — solo sus contratos, preparados.
- Sin MCP, sin Risk Engine, sin Human Gates, sin paralelismo, sin LLM — ninguno
  tocado en esta fase.
