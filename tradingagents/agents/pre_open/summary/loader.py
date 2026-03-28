from __future__ import annotations

from typing import Any, Callable, Dict, List

from tradingagents.agents.pre_open.summary.registry import DEFAULT_ENABLED_ANALYSTS, get_summary_registry
from tradingagents.agents.utils.agentstate.agent_states import AgentState, AnalystMemorySummary

COMPAT_SUMMARY_KEYS = {
    "market": "market_analyst_summary",
    "news": "news_analyst_summary",
    "sentiment": "sentiment_analyst_summary",
    "fundamentals": "fundamentals_analyst_summary",
}

EMPTY_SUMMARY: AnalystMemorySummary = {"today_report": "", "history_report": ""}


def resolve_enabled_analysts(state: AgentState) -> List[str]:
    requested = state.get("enabled_analysts") or []
    if not requested:
        return list(DEFAULT_ENABLED_ANALYSTS)
    return [str(item).strip().lower() for item in requested if str(item).strip()]


def create_summary_loader_node(conn: Any) -> Callable[[AgentState], Dict[str, Any]]:
    registry = get_summary_registry(conn)

    def summary_loader_node(state: AgentState) -> Dict[str, Any]:
        enabled = [name for name in resolve_enabled_analysts(state) if name in registry]
        analyst_summaries: Dict[str, AnalystMemorySummary] = {}
        for analyst_name in enabled:
            analyst_summaries[analyst_name] = registry[analyst_name]["loader"](state)

        updates: Dict[str, Any] = {
            "enabled_analysts": enabled,
            "analyst_summaries": analyst_summaries,
        }
        for analyst_name, compat_key in COMPAT_SUMMARY_KEYS.items():
            updates[compat_key] = analyst_summaries.get(analyst_name, dict(EMPTY_SUMMARY))
        return updates

    return summary_loader_node

