"""Generator -- transforma una Specification en un artefacto de software
ejecutable. NO decide arquitectura: implementa lo que la Specification ya
define. Determinista (sin LLM): misma Specification, mismo codigo generado,
siempre -- via un template de string, no una decision "creativa".

FACTORY-SPEC.md Seccion 6 (Generator): "produce artefactos... a partir de
los artefactos previos del Pipeline y de los Contracts vigentes... No puede
certificar su propio output como valido". Esta implementacion respeta eso:
`execute()` valida que la Specification este completa (rechaza si no, nunca
adivina lo que falta) y genera el codigo -- pero no decide que ese codigo
esta "aprobado"; eso es Validation/Review, fases futuras.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent
from agents.generation_workspace import GenerationWorkspace
from agents.specification import FieldSpec, Specification


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GeneratorInput:
    """Lo minimo que el Generator necesita para no tener que "adivinar"
    nada (Seccion 7 del pedido de Fase 4B): el Requirement de origen, la
    Specification explicita, el run_id (para aislar donde escribe), y un
    contexto autorizado -- hoy solo el directorio de salida permitido, que
    decide el Coordinator/quien invoca, no el Generator."""
    run_id: str
    requirement: str
    specification: Specification
    authorized_context: dict[str, Any] = field(default_factory=dict)


class GenerationError(Exception):
    """Errores de generacion que SI se esperan (specification invalida,
    filesystem no escribible) -- se capturan en `execute()` y se devuelven
    como AgentResult(status=ERROR), nunca como una excepcion sin capturar."""


def _render_modulo_cliente(spec: Specification) -> str:
    """Template deterministico: la MISMA Specification produce el MISMO
    texto, siempre. No hay ningun LLM ni aleatoriedad involucrada."""
    campos_obligatorios = [f.name for f in spec.fields if f.required]
    campos_unicos = [f.name for f in spec.fields if f.unique]
    nombres_campos = [f.name for f in spec.fields]

    firma_parametros = ", ".join(nombres_campos)
    validaciones = []
    for f_ in spec.fields:
        if f_.required:
            validaciones.append(
                f'        if not {f_.name}:\n'
                f'            raise ValueError("{f_.name} es obligatorio")'
            )
    for f_ in campos_unicos:
        validaciones.append(
            f'        if any(getattr(r, "{f_}", None) == {f_} for r in self._registros):\n'
            f'            raise ValueError(f"{f_} duplicado: {{{f_}!r}}")'
        )
    cuerpo_validaciones = "\n".join(validaciones) if validaciones else "        pass"

    campos_dataclass = "\n".join(f"    {f_.name}: {f_.type}" for f_ in spec.fields)

    return f'''"""Modulo generado automaticamente por la Software Factory.

Specification: {spec.spec_id}
Entidad: {spec.entity_name}
Requirement de origen: {spec.requirement_ref}

NO editar a mano -- este archivo es un Artifact generado (ver
software-factory/runs/{{run_id}}/generated/). Volver a generar desde la
misma Specification produce exactamente este mismo contenido.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class {spec.entity_name}:
{campos_dataclass}


class Alta{spec.entity_name}s:
    """Registro en memoria de altas de {spec.entity_name}, con las reglas
    de la Specification {spec.spec_id}."""

    def __init__(self):
        self._registros: list[{spec.entity_name}] = []

    def alta(self, {firma_parametros}) -> {spec.entity_name}:
{cuerpo_validaciones}
        registro = {spec.entity_name}({firma_parametros})
        self._registros.append(registro)
        return registro

    def listar(self) -> list[{spec.entity_name}]:
        return list(self._registros)
'''


class GeneratorAgent(BaseAgent):
    metadata = AgentMetadata(
        id="generator",
        name="Generator",
        role=AgentRole.GENERATOR,
        input_contract="GeneratorInput: {run_id, requirement, specification, authorized_context}",
        output_contract="dict: {artifact, code_reference} -- ver ARTIFACTS.md",
    )

    def execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, GeneratorInput):
            return AgentResult(
                agent_id=self.metadata.id, input=input_data, output=None,
                status="ERROR",
            )

        if not input_data.requirement or not input_data.requirement.strip():
            # "requirement inexistente" (Seccion 11 del pedido): se rechaza
            # antes de mirar la Specification -- sin Requirement no hay nada
            # que el Artifact pueda referenciar como su origen.
            return AgentResult(
                agent_id=self.metadata.id,
                input={"run_id": input_data.run_id, "requirement": input_data.requirement},
                output={"error": "requirement_inexistente"},
                status="ERROR",
            )

        spec = input_data.specification
        problemas = spec.validar() if isinstance(spec, Specification) else ["specification inexistente o de tipo incorrecto"]
        if problemas:
            # Specification incompleta o inexistente: se rechaza, no se
            # completa nada en silencio (regla explicita de la Fase 4B).
            return AgentResult(
                agent_id=self.metadata.id,
                input={"run_id": input_data.run_id, "requirement": input_data.requirement,
                      "specification": spec.to_dict() if isinstance(spec, Specification) else None},
                output={"error": "specification_invalida", "problemas": problemas},
                status="ERROR",
            )

        output_dir = input_data.authorized_context.get("output_dir")
        try:
            workspace = GenerationWorkspace(input_data.run_id) if output_dir is None \
                else GenerationWorkspace(input_data.run_id, base_dir=output_dir.parents[1])
            workspace.write_json("requirements", "requirement.json",
                                 {"text": input_data.requirement, "run_id": input_data.run_id})
            workspace.write_json("specification", f"{spec.spec_id}.json", spec.to_dict())

            codigo = _render_modulo_cliente(spec)
            nombre_archivo = f"{spec.entity_name.lower()}.py"
            ruta_generada = workspace.write_text("generated", nombre_archivo, codigo)
        except OSError as exc:
            # filesystem error: no se deja un artifact a medias marcado
            # como completo -- se devuelve ERROR antes de registrar nada.
            return AgentResult(
                agent_id=self.metadata.id,
                input={"run_id": input_data.run_id, "specification": spec.to_dict()},
                output={"error": "filesystem_error", "detail": str(exc)},
                status="ERROR",
            )
        except Exception as exc:               # noqa: BLE001 -- generation failure generico
            return AgentResult(
                agent_id=self.metadata.id,
                input={"run_id": input_data.run_id, "specification": spec.to_dict()},
                output={"error": "generation_failure", "detail": str(exc)},
                status="ERROR",
            )

        artifact_id = f"ART-{uuid4().hex[:12]}"
        artifact = {
            "artifact_id": artifact_id,
            "run_id": input_data.run_id,
            "stage": "Code",
            "agent_id": self.metadata.id,
            "type": "python_module",
            "reference": str(ruta_generada),
            "created_at": _now_iso(),
            "parent_artifact_id": None,
            "requirement_ref": input_data.requirement,
            "specification_ref": spec.spec_id,
            "evidence_ref": None,  # lo completa el Coordinator al registrar la evidencia
        }

        return AgentResult(
            agent_id=self.metadata.id,
            input={"run_id": input_data.run_id, "requirement": input_data.requirement,
                  "specification": spec.to_dict()},
            output={"artifact": artifact, "code_reference": str(ruta_generada)},
            status="OK",
        )
