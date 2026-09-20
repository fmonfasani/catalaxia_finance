# ARTIFACTS — el modelo de artefacto generado

**Archivo del modelo**: `observability.py` (clase `Artifact`). **Estado**: definido en
Fase 4A como preparación (sin ningún Generator que lo produjera todavía); **conectado**
en Fase 4B — mismo modelo, sin cambiar su forma original, solo extendido con los
campos de trazabilidad que la Fase 4A no necesitaba porque no había Requirement/
Specification/Evidence que enlazar.

## Por qué vive en `observability.py` y no en un módulo nuevo

El `Artifact` es, ante todo, algo que debe ser **observable y trazable** — no un
concepto propio del Generator. Ponerlo en `agents/generator.py` habría acoplado el
modelo a un solo Agent; ponerlo en `kernel/` habría hecho que el Kernel conociera
detalles de qué produce un Agent. `observability.py` ya es la capa transversal que
lee tipos de todos los demás sin que ellos la conozcan (ver `OBSERVABILITY.md`) — el
lugar natural para un modelo que sirve exactamente para reconstruir "qué se generó,
cuándo, y a partir de qué".

## Forma del modelo

```python
@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    run_id: str
    stage: str
    agent_id: str
    type: str
    reference: str
    created_at: str
    parent_artifact_id: str | None = None
    # Fase 4B — trazabilidad REQ -> SPEC -> GEN -> ART -> EVIDENCE
    requirement_ref: str | None = None
    specification_ref: str | None = None
    evidence_ref: str | None = None
```

En la práctica (Coordinator/Generator), el `Artifact` se maneja como `dict`, no como
instancia de la dataclass — `Artifact.to_dict()` documenta la forma canónica, pero
`GeneratorAgent.execute()` construye el dict directamente (mismo esquema, sin
instanciar la clase) porque es lo que `run.artifacts` (una lista de `dict`, definida
en Fase 2) ya espera. La dataclass es la referencia normativa de la forma; el dict es
la representación operativa.

| Campo | Origen | Descripción |
|---|---|---|
| `artifact_id` | Generator (`ART-<hex12>`, `uuid4`) | Identificador único del artefacto. |
| `run_id` | Generator (copiado de `GeneratorInput.run_id`) | El `Run` que lo produjo. |
| `stage` | Generator (hardcoded `"Code"` en esta fase) | La etapa del Pipeline en la que se generó. |
| `agent_id` | Generator (`self.metadata.id`, `"generator"`) | Qué agente lo produjo. |
| `type` | Generator (`"python_module"` en esta fase) | Tipo de artefacto — hoy un único valor posible. |
| `reference` | Generator (path absoluto del archivo escrito) | **Referencia**, no el contenido — el archivo vive en el filesystem, no en el evento/evidencia. |
| `created_at` | Generator (ISO-8601 UTC) | Cuándo se generó. |
| `parent_artifact_id` | Generator (`None` en esta fase) | Preparado para artefactos derivados de otro artefacto (p. ej. tests generados a partir del código) — sin uso todavía. |
| `requirement_ref` | Generator (copiado de `GeneratorInput.requirement`) | El Requirement de origen. |
| `specification_ref` | Generator (copiado de `Specification.spec_id`) | La Specification implementada. |
| `evidence_ref` | **Coordinator** (no el Generator) | El `result_id` de la evidencia que este mismo Artifact produjo — ver más abajo por qué lo completa el Coordinator, no el Generator. |

## Por qué `evidence_ref` lo completa el Coordinator, no el Generator

El Generator no conoce el `result_id` de su propia evidencia en el momento en que
genera el Artifact — ese id lo asigna `AgentResult.to_dict()` recién cuando el
Coordinator llama a `result.to_dict()`, **después** de que `execute()` ya devolvió.
En `coordinator/coordinator.py`:

```python
evidence_dict = result.to_dict()
if artifact:
    artifact = {**artifact, "evidence_ref": evidence_dict["result_id"]}
    self.run_manager.record_artifact(run, artifact)
```

El Generator devuelve `evidence_ref=None`; el Coordinator arma un **dict nuevo**
(no muta el original) con la referencia completada, y es esa versión enriquecida la
que termina en `run.artifacts` — no la que trae `AgentResult.output["artifact"]`, que
queda tal cual la generó el Generator (esto es intencional y está cubierto por
`tests/test_generator.py::test_run_reconstruye_requirement_specification_generator_artifact_evidence`,
que verifica `run.artifacts`, no la copia embebida en `evidence[0]["output"]`).

## Generation Directory — dónde vive el artefacto físicamente

```
software-factory/runs/<run_id>/
    requirements/
        requirement.json        # {"text": ..., "run_id": ...}
    specification/
        <spec_id>.json          # Specification.to_dict()
    generated/
        <entity_name_lower>.py  # el artefacto de tipo "python_module"
    evidence/                   # preparado, sin uso desde este Generator
    audit/                      # preparado, sin uso desde este Generator
```

Administrado por `agents/generation_workspace.py` → `GenerationWorkspace`, que expone
`ensure()` (crea los 5 subdirectorios), `write_text()`/`write_json()`. Namespace
deliberadamente distinto del de `StateManager` (`software-factory/runs/<run_id>.json`,
un archivo, no un directorio) — no hay colisión de paths.

**Aislamiento**: el software generado nunca se escribe fuera de este árbol. No toca
`engine/`, `scripts/`, `api/` ni ningún otro directorio de Catalaxia — que además
viven en un working tree de git distinto de `software-factory/`.

## Correlación con Evidence y Events

Un `Artifact` no es una isla: se correlaciona con exactamente un elemento de
`run.evidence` (vía `evidence_ref`) y con el evento `AGENT_COMPLETED` /
`EVIDENCE_RECORDED` que lo registró (ambos ganaron un campo opcional `artifact_id`
en `kernel/events.py`, Fase 4B) — sin crear una tabla de correlación nueva; el
`artifact_id` es simplemente otro campo en un evento que ya existía.

## Reconstrucción de trazabilidad completa

Dado únicamente un `run_id`, es posible reconstruir sin inferencia (verificado en
`tests/test_generator.py`, TEST 15):

```
Requirement (texto)
  -> Specification (spec_id, campos)
    -> Generator (agent_id="generator")
      -> Artifact (artifact_id, reference, requirement_ref, specification_ref)
        -> Evidence (result_id == artifact.evidence_ref)
          -> Events (AGENT_COMPLETED/EVIDENCE_RECORDED con artifact_id)
```

`observability.query_run(run_id)` (Fase 4A, sin cambios en su firma) ya incluye
`artifacts` en su resultado — no hizo falta extenderlo para que la Fase 4B lo
aproveche.

## Límites actuales

- Un único `type` posible (`"python_module"`) — el modelo admite otros tipos (el
  campo es un `str` libre), pero nada más los produce todavía.
- `parent_artifact_id` está en el modelo desde la Fase 4A pero ningún flujo actual lo
  completa — preparado para artefactos derivados (p. ej. un test generado a partir
  del código), no implementado.
- No hay validación de que `reference` siga apuntando a un archivo existente en el
  momento de la consulta (`query_run()` no vuelve a tocar el filesystem) — es una
  referencia, no una garantía persistente.
- El contenido del artefacto no se audita ni se firma — la única garantía de que
  corresponde a su `specification_ref` es que el mismo proceso que lo generó escribió
  ambos atómicamente dentro del mismo `try` (ver `GENERATOR.md`, manejo de errores).
