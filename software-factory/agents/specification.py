"""Specification -- lo que el Generator recibe, nunca lo que adivina.

FACTORY-SPEC.md Pipeline (Seccion 7): "Requirement -> Specification". Esta
fase agrega la primera forma CONCRETA de Specification -- antes solo existia
como nombre de etapa. Deliberadamente pequena: describe una entidad de
dominio con campos y reglas, suficiente para el caso de demostracion
("alta de clientes"), sin pretender ser un lenguaje de especificacion
general.

`Specification.validar()` es la unica autoridad sobre "esta specification
esta completa" -- el Generator la llama, nunca decide el mismo si algo
"parece suficiente".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str  # "str" | "int" -- deliberadamente un set chico, no un sistema de tipos
    required: bool = True
    unique: bool = False


@dataclass(frozen=True)
class Specification:
    spec_id: str
    entity_name: str
    fields: tuple[FieldSpec, ...] = field(default_factory=tuple)
    requirement_ref: str = ""

    def validar(self) -> list[str]:
        """Devuelve una lista de problemas -- vacia si la Specification esta
        completa. No corrige nada, no completa nada en silencio: solo
        reporta que falta."""
        problemas = []
        if not self.spec_id:
            problemas.append("spec_id vacio")
        if not self.entity_name:
            problemas.append("entity_name vacio")
        if not self.fields:
            problemas.append("no declara ningun campo")
        nombres = [f.name for f in self.fields]
        if len(nombres) != len(set(nombres)):
            problemas.append(f"nombres de campo duplicados: {nombres}")
        for f_ in self.fields:
            if f_.type not in ("str", "int"):
                problemas.append(f"campo {f_.name!r}: tipo no soportado {f_.type!r}")
        if not self.requirement_ref:
            problemas.append("sin referencia al Requirement de origen (requirement_ref)")
        return problemas

    def es_valida(self) -> bool:
        return not self.validar()

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "entity_name": self.entity_name,
            "requirement_ref": self.requirement_ref,
            "fields": [
                {"name": f.name, "type": f.type, "required": f.required, "unique": f.unique}
                for f in self.fields
            ],
        }
