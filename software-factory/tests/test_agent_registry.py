"""AgentRegistry: registro, recuperacion, habilitacion.

Cubre TEST 1, TEST 2 y TEST 3 del pedido de Fase 3.
"""
from __future__ import annotations

import pytest

from agent_contract import AgentMetadata, AgentResult, AgentRole
from agents.classifier import ClassifierAgent
from coordinator.agent_registry import AgentRegistry
from kernel.errors import AgentDisabledError, AgentNotFoundError


def test_registry_registra_el_classifier_correctamente():
    """TEST 1."""
    registry = AgentRegistry()
    registry.register(ClassifierAgent())
    assert registry.is_registered("classifier")
    assert "classifier" in registry.list_ids()


def test_registry_recupera_el_classifier():
    """TEST 2."""
    registry = AgentRegistry()
    agent = ClassifierAgent()
    registry.register(agent)
    recuperado = registry.get("classifier")
    assert recuperado is agent
    assert recuperado.metadata.role is AgentRole.CLASSIFIER


def test_agente_no_registrado_no_puede_ejecutarse():
    """TEST 3."""
    registry = AgentRegistry()
    with pytest.raises(AgentNotFoundError):
        registry.get("no-existe")
    with pytest.raises(AgentNotFoundError):
        registry.get_enabled("no-existe")
    assert not registry.is_registered("no-existe")
    assert not registry.is_enabled("no-existe")


def test_agente_deshabilitado_no_puede_ejecutarse_via_get_enabled():
    registry = AgentRegistry()

    class _Deshabilitado:
        metadata = AgentMetadata(
            id="apagado", name="Apagado", role=AgentRole.GENERATOR,
            input_contract="x", output_contract="y", enabled=False,
        )

        def execute(self, input_data):
            return AgentResult(agent_id="apagado", input=input_data, output=None, status="OK")

    registry.register(_Deshabilitado())
    assert registry.is_registered("apagado")
    assert not registry.is_enabled("apagado")
    with pytest.raises(AgentDisabledError):
        registry.get_enabled("apagado")


def test_metadata_for_expone_metadata_del_agente():
    registry = AgentRegistry()
    registry.register(ClassifierAgent())
    meta = registry.metadata_for("classifier")
    assert meta.id == "classifier"
    assert meta.role is AgentRole.CLASSIFIER
