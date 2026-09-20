# EVALS — comportamiento esperado, verificado por ejecución

**Archivos**: `evals.py` (modelo genérico), `evals_catalog.py` (Evals concretos).
**Estado**: implementado, probado (Fase 5B).

## Responsabilidad

Verificar que un **comportamiento observado** coincide con lo esperado — distinto de
un Contract (forma) y de un Invariant (propiedad sobre el estado/contenido). La
distinción, pedida explícitamente en la Fase 5B:

```
CONTRACT   -> ¿la estructura es válida?
INVARIANT  -> ¿se mantiene una propiedad obligatoria?
EVAL       -> ¿el comportamiento cumple lo esperado?
```

Ejemplo real de esta fase: "el DNI es único" es una propiedad (INV-002, sobre datos ya
existentes). "Dos altas con el mismo DNI deben producir rechazo" es un comportamiento
concreto — hay que **ejecutar** el software generado y observar qué hace, no solo
inspeccionar una lista de registros.

## Modelo

```python
@dataclass(frozen=True)
class EvalCheckResult:
    eval_id: str
    passed: bool
    detail: str = ""

@dataclass(frozen=True)
class Eval:
    eval_id: str
    version: str
    name: str
    description: str
    input: Any
    expected: Any
    evaluation_method: Callable[[Any, Any, dict], EvalCheckResult]
    scope: str = ""
```

`evaluation_method(input, expected, context) -> EvalCheckResult` es la única forma de
saber si el comportamiento coincide. El `context` (armado por el Validator, igual que
para los Invariants) trae los datos de ejecución reales que el método necesita —
típicamente una referencia al código a ejecutar (`code_reference`).

**Un Eval no dispara una ejecución de Agent** — evalúa un comportamiento a partir del
código/artefacto ya generado. No hay ningún `AgentRegistry`/`Coordinator` involucrado
dentro de un `evaluation_method`.

## EvalRegistry

Mismo patrón que `InvariantRegistry`: registra, obtiene, lista, y `run_all(scope,
context)` ejecuta todos los aplicables en orden determinista. **No controla el
pipeline** — no importa `kernel/` ni `coordinator/` (verificado por AST en
`tests/test_validator.py::test_no_depende_del_etl_financiero`).

## El único Eval concreto (`evals_catalog.py`)

Deliberadamente uno solo — mismo criterio que Invariants: "no crear artificiales".

### EVAL-001 — Dos altas con el mismo DNI deben producir rechazo

Importa dinámicamente el módulo generado (`context["code_reference"]`, misma técnica
que la "comprobación mínima" de `demo.py` desde la Fase 4B: registrar en
`sys.modules` **antes** de `exec_module()`, requerido porque el módulo generado usa
`@dataclass`), instancia `AltaClientes`, da de alta un primer registro
(`input["primera_alta"]`), e intenta dar de alta un segundo con el mismo DNI
(`input["segunda_alta"]`). El Eval pasa únicamente si esa segunda llamada levanta
`ValueError` con el mensaje esperado (`expected["excepcion_esperada_contiene"]`) — si
no levanta nada, o levanta la excepción equivocada, el Eval falla.

Esto ejercita el **software generado real**, no una simulación — la misma garantía
que la Fase 4B ya exigía de la "comprobación mínima" del Generator, ahora formalizada
como un caso de verificación reproducible en vez de una comprobación ad-hoc dentro de
`demo.py`.

- **Scope**: `"Generator"`.

## Relación con Contracts e Invariants

Un Eval asume que el Contract del productor ya se cumplió (hay un
`code_reference` real, un archivo que existe) — no repite esa verificación. Tampoco
repite lo que un Invariant ya cubre (INV-002 verifica la propiedad sobre
`context["registros"]`, datos ya existentes; EVAL-001 verifica el comportamiento del
software generado ante un intento nuevo) — son preguntas complementarias, no
redundantes.

## Relación con el Validator

`evals.py` no conoce a `ValidatorAgent` — mismo desacoplamiento que con
`invariants.py`. El Validator arma el `context` compartido (con `code_reference`,
`registros`, etc.) y lo pasa tanto al `InvariantRegistry` como al `EvalRegistry` — un
Eval y un Invariant pueden usar el mismo `context` sin que ninguno conozca al otro.

## Límites actuales

- Un único Eval — cubre el caso de demostración de esta fase (alta de clientes con
  DNI único); un catálogo más amplio de comportamientos queda para cuando existan más
  Requirements generados.
- `evaluation_method` es código Python arbitrario, no un DSL declarativo — la
  ejecución real del módulo generado (`exec_module()`) es lo que hace que el Eval sea
  costoso comparado con un Invariant (que solo inspecciona datos ya en memoria); esa
  diferencia de costo es intencional y refleja la diferencia conceptual entre "mirar
  una propiedad" y "ejecutar un comportamiento".
- Sin timeout ni sandboxing del código ejecutado — el módulo generado es determinista
  y confiable porque lo produjo el Generator de esta misma Factory (Fase 4B), no
  código arbitrario de origen externo.
