# INVARIANTS — propiedades que deben sostenerse siempre

**Archivos**: `invariants.py` (modelo genérico), `invariants_catalog.py` (invariants
concretos). **Estado**: implementado, probado (Fase 5B).

## Responsabilidad

Verificar una **propiedad** que debe sostenerse — no una forma (eso es un `Contract`,
`contracts.py`, Fase 5A). FACTORY-SPEC.md §11 (Governance) lo define:

> *"Invariants: propiedades que deben sostenerse siempre, no solo al final de una
> etapa."*

Un Contract responde "¿tiene `code_reference`? ¿es `str`?" — una pregunta de forma que
no necesita mirar el contenido. Un Invariant responde "¿el DNI es único entre los
registros ya dados de alta?" — una pregunta sobre una propiedad del **contenido**, que
ningún Schema de campos puede expresar.

## Modelo

```python
class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"

@dataclass(frozen=True)
class InvariantCheckResult:
    invariant_id: str
    passed: bool
    detail: str = ""

@dataclass(frozen=True)
class Invariant:
    invariant_id: str
    version: str
    name: str
    description: str
    severity: Severity
    scope: str                                              # a qué se aplica (p.ej. "Generator")
    check: Callable[[dict], InvariantCheckResult]            # funcion pura
```

Un `Invariant` es una función pura (`check(context) -> InvariantCheckResult`), no una
clase por propiedad — mismo espíritu que `agents/classifier.py::classify()`:
determinista, sin estado, fácil de testear en aislamiento. `scope` es lo que
`InvariantRegistry.evaluate_all(scope, context)` usa para saber cuáles Invariants son
aplicables a un contexto dado, sin que el Invariant necesite conocer al Validator ni
al Coordinator.

## InvariantRegistry

Mismo patrón que `AgentRegistry` (Fase 3) y `ContractRegistry` (Fase 5A): registra,
obtiene por id, lista. `evaluate_all(scope, context)` ejecuta todos los aplicables, en
orden determinista (`invariant_id` ascendente), y devuelve la lista completa de
resultados — no decide qué hacer con ellos (eso es el Validator).

**No muta ningún State** — `invariants.py` no importa `kernel/`. **No ejecuta ningún
Agent** — no importa `coordinator/` ni `agent_contract.py`. Verificado por AST en
`tests/test_validator.py::test_no_depende_del_etl_financiero` (que también confirma
la independencia del ETL) y por inspección directa de los imports del módulo.

## Los dos Invariants concretos (`invariants_catalog.py`)

Deliberadamente solo dos — la Fase 5B pide explícitamente no crear invariants
artificiales "solamente para llenar archivos".

### INV-001 — Artifact requiere evidencia

> *"Un Generator no puede producir un resultado aceptado (COMPLETED) sin que el
> Artifact quede correlacionado con una evidencia verificable."*

Espejo, como Invariant, de lo que FACTORY-SPEC.md §6 ya exige en prosa del Generator:
*"No puede... decidir que su output está listo — eso lo determina evidencia, no una
afirmación del Generator."* Verifica que `artifact.evidence_ref` no esté vacío y que
el `context["evidence"]` correspondiente exista — la misma correlación que
`ARTIFACTS.md` (Fase 4B) ya documentaba, ahora verificada mecánicamente en vez de solo
narrada.

- **Severity**: `CRITICAL`.
- **Scope**: `"Generator"`.

### INV-002 — DNI único entre altas

> *"Una etapa no puede avanzar si existen dos altas de cliente con el mismo DNI."*

Propiedad de **dominio** concreta del Requirement de esta demostración ("alta de
clientes con DNI único", Fase 4B) — no una propiedad genérica de la Factory. Necesaria
para poder demostrar un `FAIL` real end-to-end: recibe `context["registros"]` (lista
de dicts con `"dni"`) y reporta cualquier DNI que aparezca más de una vez.

- **Severity**: `CRITICAL`.
- **Scope**: `"Generator"`.

## Relación con Contracts

No hay superposición: `GENERATOR_OUTPUT` (Contract, Fase 5A) ya garantiza que el
`output` del Generator tiene la forma `{artifact: dict, code_reference: str}` —
INV-001 asume esa forma y verifica algo que un Schema no puede expresar (una
referencia cruzada válida, no solo presente). Un Contract inválido nunca llega al
Validator: el Coordinator ya lo rechazó en la Fase 5A, antes de que exista ningún
Invariant que evaluar.

## Relación con el Validator

`invariants.py` no conoce a `ValidatorAgent` — es el Validator quien importa
`InvariantRegistry` y arma el `context` (ver `VALIDATOR.md`). Esta separación permite
agregar Invariants nuevos sin tocar el Validator, y viceversa.

## Límites actuales

- Solo dos Invariants — cualquier propiedad nueva (p. ej. sobre Architecture o
  Contracts como etapas, no como el mecanismo `contracts.py`) queda para cuando esas
  etapas tengan un Agent real que produzca algo que verificar.
- `check()` es una función Python arbitraria — no hay un DSL de invariantes ni
  verificación formal; la corrección de cada `check()` depende de que su implementación
  sea correcta, igual que cualquier otro código de la Factory.
- Sin persistencia propia — los resultados de evaluación viven en el `ValidationResult`
  del Validator (evidence del Run), no en un almacenamiento aparte.
