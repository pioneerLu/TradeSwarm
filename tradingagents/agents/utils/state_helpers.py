"""Helpers for reading analyst summaries from AgentState."""

from __future__ import annotations

from typing import Dict, List, Optional

from tradingagents.agents.utils.agentstate.agent_states import AgentState, AnalystMemorySummary

DEFAULT_ANALYST_ORDER = ["market", "news", "sentiment", "fundamentals"]
COMPAT_SUMMARY_KEYS = {
    "market": "market_analyst_summary",
    "news": "news_analyst_summary",
    "sentiment": "sentiment_analyst_summary",
    "fundamentals": "fundamentals_analyst_summary",
}


def get_enabled_analysts(state: AgentState) -> List[str]:
    enabled = state.get("enabled_analysts") or []
    if enabled:
        return [str(item).strip().lower() for item in enabled if str(item).strip()]
    summaries = state.get("analyst_summaries") or {}
    if summaries:
        ordered = [name for name in DEFAULT_ANALYST_ORDER if name in summaries]
        extras = [name for name in summaries.keys() if name not in DEFAULT_ANALYST_ORDER]
        return ordered + extras
    return list(DEFAULT_ANALYST_ORDER)


def get_analyst_summary(state: AgentState, analyst_type: str) -> AnalystMemorySummary:
    analyst_type = str(analyst_type).strip().lower()
    summaries: Dict[str, AnalystMemorySummary] = state.get("analyst_summaries") or {}
    if analyst_type in summaries:
        return summaries[analyst_type] or {}
    compat_key = COMPAT_SUMMARY_KEYS.get(analyst_type)
    if compat_key:
        return state.get(compat_key, {}) or {}
    return {}


def get_analyst_summaries_map(state: AgentState) -> Dict[str, AnalystMemorySummary]:
    return {analyst: get_analyst_summary(state, analyst) for analyst in get_enabled_analysts(state)}


def get_prompt_context_from_summaries(state: AgentState) -> Dict[str, str]:
    summaries = {
        "market": get_analyst_summary(state, "market"),
        "news": get_analyst_summary(state, "news"),
        "sentiment": get_analyst_summary(state, "sentiment"),
        "fundamentals": get_analyst_summary(state, "fundamentals"),
    }
    enabled = get_enabled_analysts(state)
    analyst_blocks = []
    for analyst_name in enabled:
        summary = get_analyst_summary(state, analyst_name)
        today_report = summary.get("today_report", "") if summary else ""
        history_report = summary.get("history_report", "") if summary else ""
        block = f"[{analyst_name}]\n{today_report}".strip()
        if history_report:
            block += f"\n\nHistory:\n{history_report}"
        analyst_blocks.append(block)

    return {
        "market_research_report": summaries["market"].get("today_report", ""),
        "market_today_report": summaries["market"].get("today_report", ""),
        "market_history_summary": summaries["market"].get("history_report", ""),
        "news_report": summaries["news"].get("today_report", ""),
        "news_today_report": summaries["news"].get("today_report", ""),
        "news_history_summary": summaries["news"].get("history_report", ""),
        "sentiment_report": summaries["sentiment"].get("today_report", ""),
        "sentiment_today_report": summaries["sentiment"].get("today_report", ""),
        "sentiment_history_summary": summaries["sentiment"].get("history_report", ""),
        "fundamentals_report": summaries["fundamentals"].get("today_report", ""),
        "fundamentals_today_report": summaries["fundamentals"].get("today_report", ""),
        "fundamentals_history_summary": summaries["fundamentals"].get("history_report", ""),
        "enabled_analysts_text": ", ".join(enabled),
        "active_analyst_blocks": "\n\n".join(block for block in analyst_blocks if block).strip(),
    }


def build_curr_situation_from_summaries(
    state: AgentState,
    max_length: Optional[int] = None,
    include_history: bool = False,
) -> str:
    sections = []
    for analyst_name in get_enabled_analysts(state):
        summary = get_analyst_summary(state, analyst_name)
        report = summary.get("today_report", "") if summary else ""
        if include_history:
            history = summary.get("history_report", "") if summary else ""
            if history:
                report = f"{report}\n\n{history}" if report else history
        if report:
            sections.append(report)

    result = "\n\n".join(sections).strip()
    if max_length is not None and len(result) > max_length:
        result = result[:max_length] + "\n\n[内容已截断...]"
    return result
