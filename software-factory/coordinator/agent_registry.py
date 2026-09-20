"""AgentRegistry -- registra agentes y expone su metadata. No los ejecuta.

Responsabilidades exactas del pedido de Fase 3: registrar agentes
disponibles, obtener un agente por ID, verificar que esta habilitado,
exponer su metadata. Nada mas -- en particular, no decide el pipeline (eso
es `PipelineDefinition`, ya en el Kernel) ni ejecuta nada (eso es
`Coordinator`, que LLAMA a `agent.execute()` el mismo, no le pide al
Registry que lo haga).
"""
from __future__ import annotations

from agent_contract import AgentMetadata, BaseAgent
from kernel.errors import AgentDisabledError, AgentNotFoundError


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.metadata.id] = agent

    def get(self, agent_id: str) -> BaseAgent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id, self.list_ids())
        return agent

    def get_enabled(self, agent_id: str) -> BaseAgent:
        """Como `get()`, pero ademas exige que este habilitado -- es lo que
        el Coordinator deberia llamar siempre, nunca `get()` a secas."""
        agent = self.get(agent_id)
        if not agent.metadata.enabled:
            raise AgentDisabledError(agent_id)
        return agent

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def is_enabled(self, agent_id: str) -> bool:
        return self.is_registered(agent_id) and self._agents[agent_id].metadata.enabled

    def metadata_for(self, agent_id: str) -> AgentMetadata:
        return self.get(agent_id).metadata

    def list_ids(self) -> list[str]:
        return sorted(self._agents)
