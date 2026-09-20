"""Classifier -- clasifica un Project Input, no genera ni decide nada mas.

FACTORY-SPEC.md Seccion 6: "recibe un Requirement... y determina su tipo,
dominio, complejidad...". Esta implementacion cubre el caso minimo pedido
para esta fase: tipo (FEATURE/BUG/QUESTION). Dominio/complejidad/
descomposicion jerarquica (Seccion 16.1) quedan fuera -- no se inventan
aca.

Deliberadamente determinista, sin LLM (permitido explicitamente por el
pedido de Fase 3: "no es obligatorio utilizar un LLM"). Reglas por
palabras clave, en español (los ejemplos de la tarea son en español),
transparentes y reproducibles: mismo input, mismo output, siempre. El
contrato (`execute(str) -> AgentResult`) es el mismo que tendria una version
futura respaldada por un LLM -- cambiar la implementacion interna de
`classify()` no requeriria tocar `ClassifierAgent.execute()` ni al
Coordinator.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent


class Category(str, Enum):
    FEATURE = "FEATURE"
    BUG = "BUG"
    QUESTION = "QUESTION"


# Reglas evaluadas en este orden -- una pregunta con la palabra "error" adentro
# ("¿por que da error?") es una QUESTION, no un BUG: se pregunta, no se reporta.
_QUESTION_MARKERS = ("?", "¿")
_QUESTION_KEYWORDS = (
    "como ", "cómo ", "que es", "qué es", "por que", "por qué",
    "cual ", "cuál ", "es posible", "se puede", "podemos",
)
_BUG_KEYWORDS = (
    "error", "falla", "fallo", "bug", "no funciona", "roto", "rota",
    "excepcion", "excepción", "crash", "se cae", "dejo de funcionar",
    "dejó de funcionar",
)
_FEATURE_KEYWORDS = (
    "agregar", "implementar", "necesitamos", "necesito", "queremos",
    "quiero", "nueva funcionalidad", "crear", "alta de", "agregar soporte",
)


@dataclass(frozen=True)
class ClassificationResult:
    category: Category
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "reason": self.reason,
        }


def classify(text: str) -> ClassificationResult:
    """Funcion pura, sin estado, sin I/O -- facil de testear y de
    reemplazar. `ClassifierAgent.execute()` es la unica que sabe que esto
    es una funcion determinista y no una llamada a un LLM."""
    t = text.lower()

    if any(m in t for m in _QUESTION_MARKERS) or any(k in t for k in _QUESTION_KEYWORDS):
        return ClassificationResult(
            category=Category.QUESTION, confidence=0.9,
            reason="contiene signo de pregunta o una palabra interrogativa conocida",
        )
    if any(k in t for k in _BUG_KEYWORDS):
        return ClassificationResult(
            category=Category.BUG, confidence=0.85,
            reason="contiene una palabra clave asociada a un defecto reportado",
        )
    if any(k in t for k in _FEATURE_KEYWORDS):
        return ClassificationResult(
            category=Category.FEATURE, confidence=0.8,
            reason="contiene una palabra clave asociada a pedir una capacidad nueva",
        )
    return ClassificationResult(
        category=Category.FEATURE, confidence=0.4,
        reason="sin señales claras de BUG o QUESTION; FEATURE por defecto, confianza baja",
    )


class ClassifierAgent(BaseAgent):
    metadata = AgentMetadata(
        id="classifier",
        name="Classifier",
        role=AgentRole.CLASSIFIER,
        input_contract="str no vacio: texto libre de un Requirement o Change Request",
        output_contract="dict: {category: FEATURE|BUG|QUESTION, confidence: float, reason: str}",
    )

    def execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, str) or not input_data.strip():
            return AgentResult(
                agent_id=self.metadata.id,
                input=input_data,
                output=None,
                status="ERROR",
            )
        resultado = classify(input_data)
        return AgentResult(
            agent_id=self.metadata.id,
            input=input_data,
            output=resultado.to_dict(),
            status="OK",
        )
