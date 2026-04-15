"""Helpers for reading analyst summaries and portfolio context from AgentState."""

from __future__ import annotations

import inspect
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _trace_prompt_context_consumer() -> str:
    stack = inspect.stack()
    for frame in stack[2:20]:
        if frame.function == "get_prompt_context_from_summaries":
            continue
        return frame.function
    return "unknown"


def _append_analyst_context_trace(state: AgentState, ctx: Dict[str, str]) -> None:
    path = os.environ.get("TRADESWARM_ANALYST_CONTEXT_LOG")
    if not path:
        return
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "consumer": _trace_prompt_context_consumer(),
        "company_of_interest": state.get("company_of_interest"),
        "trade_date": state.get("trade_date"),
        "enabled_analysts_text": ctx.get("enabled_analysts_text", ""),
        "active_analyst_blocks": ctx.get("active_analyst_blocks", ""),
    }
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def get_prompt_context_from_summaries(state: AgentState) -> Dict[str, str]:
    """Prompt 侧只暴露启用列表与证据块；内容与 AnalystMemorySummary 一致，无扁平别名重复。"""
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

    ctx = {
        "enabled_analysts_text": ", ".join(enabled),
        "active_analyst_blocks": "\n\n".join(block for block in analyst_blocks if block).strip(),
    }
    _append_analyst_context_trace(state, ctx)
    return ctx


def format_position_info(current_position: Optional[Dict[str, Any]]) -> str:
    """Format current_position dict into a human-readable text block."""
    if not current_position:
        return "\nCurrent position: none\n"
    shares = current_position.get("shares") or 0.0
    entry_price = current_position.get("entry_price") or 0.0
    entry_date = current_position.get("entry_date") or ""
    current_price = current_position.get("current_price") or 0.0
    pnl = current_position.get("pnl") or 0.0
    pnl_pct = current_position.get("pnl_pct") or 0.0
    sl_raw = current_position.get("stop_loss_price")
    sl_str = f"${sl_raw:.2f}" if sl_raw is not None else "Not set"
    tp_raw = current_position.get("take_profit_price")
    tp_str = f"${tp_raw:.2f}" if tp_raw is not None else "Not set"
    return (
        f"\nCurrent position:\n"
        f"- Shares: {shares:.0f}\n"
        f"- Entry price: ${entry_price:.2f}\n"
        f"- Entry date: {entry_date}\n"
        f"- Current price: ${current_price:.2f}\n"
        f"- PnL: ${pnl:.2f}\n"
        f"- PnL %: {pnl_pct:.2f}%\n"
        f"- Stop loss: {sl_str}\n"
        f"- Take profit: {tp_str}\n"
    )


def format_portfolio_info(portfolio_state: Optional[Dict[str, Any]]) -> str:
    """Format portfolio_state dict into a human-readable text block."""
    if not portfolio_state:
        return ""
    total_value = portfolio_state.get("total_value") or 0.0
    cash = portfolio_state.get("cash") or 0.0
    positions_value = portfolio_state.get("positions_value") or 0.0
    total_return = portfolio_state.get("total_return") or 0.0
    return (
        f"\nPortfolio state:\n"
        f"- Total value: ${total_value:,.2f}\n"
        f"- Cash: ${cash:,.2f}\n"
        f"- Positions value: ${positions_value:,.2f}\n"
        f"- Total return: {total_return:.2f}%\n"
    )


def format_position_context(state: AgentState) -> str:
    """Return combined position + portfolio text from AgentState. Empty string if no data."""
    position_info = format_position_info(state.get("current_position"))
    portfolio_info = format_portfolio_info(state.get("portfolio_state"))
    combined = (position_info + portfolio_info).strip()
    return combined if combined and combined != "Current position: none" else ""


def build_curr_situation_from_summaries(
    state: AgentState,
    max_length: Optional[int] = None,
    include_history: bool = False,
) -> str:
    """拼接启用 analyst 的当日（及可选 history）报告，供 Research/Risk/Trader 与 HybridMemory 查询向量使用。"""
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
