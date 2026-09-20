from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

SOFTWARE_FACTORY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOFTWARE_FACTORY_DIR))

from agent_contract import AgentMetadata, AgentResult, AgentRole, BaseAgent  # noqa: E402
from agents.classifier import ClassifierAgent  # noqa: E402
from coordinator.agent_registry import AgentRegistry  # noqa: E402
from coordinator.coordinator import Coordinator  # noqa: E402
from kernel.factory_spec_loader import FactorySpecLoader  # noqa: E402
from kernel.pipeline_definition import PipelineDefinition, PipelineStage  # noqa: E402
from kernel.run_manager import RunManager  # noqa: E402
from kernel.state_manager import StateManager  # noqa: E402


@pytest.fixture
def real_spec():
    """La FACTORY-SPEC.md real del repositorio -- no un mock. TEST 6 exige
    que el Kernel cargue la spec real, asi que ningun test de este archivo
    inventa una spec de prueba para ese caso."""
    return FactorySpecLoader().load()


@pytest.fixture
def toy_pipeline() -> PipelineDefinition:
    """Pipeline minimo para tests que no necesitan las 12 etapas reales --
    aislados de si alguien edita la tabla de la Seccion 7 de la spec. Trae
    `typical_agents` poblado a mano (no derivado de la spec real) para poder
    probar casos de borde del Coordinator (etapa sin agente autorizado,
    etc.) sin depender de que FACTORY-SPEC.md tenga esa forma exacta."""
    return PipelineDefinition(stages=(
        PipelineStage(name="Requirement", transition_condition="clasificado",
                     typical_agents=("Classifier",)),
        PipelineStage(name="Specification", transition_condition="aprobada",
                     typical_agents=("Generator",)),
        PipelineStage(name="SinAgente", transition_condition="(etapa de prueba)",
                     typical_agents=()),
        PipelineStage(name="Delivery", transition_condition="validada y revisada",
                     typical_agents=("Coordinator",)),
    ))


@pytest.fixture
def run_manager(toy_pipeline) -> RunManager:
    return RunManager(pipeline=toy_pipeline, factory_version="0.1.0-test")


@pytest.fixture
def real_run_manager(real_spec) -> RunManager:
    """RunManager sobre el Pipeline REAL de FACTORY-SPEC.md -- para probar
    el circuito Requirement->Classifier tal como lo declara la spec de
    verdad, no una copia de prueba."""
    return RunManager(pipeline=real_spec.pipeline, factory_version=real_spec.version)


@pytest.fixture
def state_manager(tmp_path) -> StateManager:
    return StateManager(runs_dir=tmp_path / "runs")


@pytest.fixture
def registry_with_classifier() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(ClassifierAgent())
    return registry


class _DummyAgent(BaseAgent):
    """Agente senuelo para probar que el Coordinator nunca invoca un agente
    que la etapa no autoriza, aunque este registrado y habilitado."""

    def __init__(self, agent_id: str = "dummy"):
        self.metadata = AgentMetadata(
            id=agent_id, name="Dummy", role=AgentRole.GENERATOR,
            input_contract="cualquiera", output_contract="cualquiera",
        )
        self.calls: list[Any] = []

    def execute(self, input_data):
        self.calls.append(input_data)
        return AgentResult(agent_id=self.metadata.id, input=input_data,
                           output={"ok": True}, status="OK")


@pytest.fixture
def dummy_agent_factory():
    return _DummyAgent


@pytest.fixture
def coordinator(run_manager, registry_with_classifier) -> Coordinator:
    return Coordinator(run_manager=run_manager, registry=registry_with_classifier)
