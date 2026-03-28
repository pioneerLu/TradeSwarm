from __future__ import annotations

from typing import Callable, TypedDict

from tradingagents.agents.utils.agentstate.agent_states import AgentState, AnalystMemorySummary


class SummaryProviderSpec(TypedDict):
    analyst_type: str
    report_title: str
    node_name: str
    loader: Callable[[AgentState], AnalystMemorySummary]

