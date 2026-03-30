#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
History Maintainer node.

Responsibilities:
- Runs during post_close
- Builds 7-trading-day rolling analyst summaries for the current symbol/date
- Writes summaries into analyst_summaries via MemoryDBHelper
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.utils.memory import (
    FundamentalsMemoryManager,
    MarketMemoryManager,
    NewsMemoryManager,
    SentimentMemoryManager,
)
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper


DEFAULT_ANALYST_TYPES = ("market", "news", "sentiment", "fundamentals")


def create_history_maintainer_node(
    llm: BaseChatModel,
    db_helper: MemoryDBHelper,
    analyst_types: Optional[Iterable[str]] = None,
) -> Callable[[AgentState], Dict[str, Any]]:
    """Create a History Maintainer node."""

    allowed = {
        str(name).strip().lower()
        for name in (analyst_types or DEFAULT_ANALYST_TYPES)
        if str(name).strip()
    }
    manager_factories = {
        "market": lambda: MarketMemoryManager(db_helper=db_helper),
        "news": lambda: NewsMemoryManager(db_helper=db_helper),
        "sentiment": lambda: SentimentMemoryManager(db_helper=db_helper),
        "fundamentals": lambda: FundamentalsMemoryManager(db_helper=db_helper),
    }
    selected_managers = [
        (name, manager_factories[name]())
        for name in DEFAULT_ANALYST_TYPES
        if name in allowed
    ]

    def history_maintainer_node(state: AgentState) -> Dict[str, Any]:
        symbol = state.get("company_of_interest")
        trade_date = state.get("trade_date")

        if not symbol or not trade_date:
            print(
                f"[HistoryMaintainer] Missing required args: symbol={symbol}, trade_date={trade_date}"
            )
            return {}

        results: Dict[str, Any] = {"history_maintainer_log": []}

        for name, manager in selected_managers:
            try:
                print(f"[HistoryMaintainer] Start {name} summary: {symbol} @ {trade_date}")
                status = manager.run_daily_update(
                    llm=llm,
                    symbol=symbol,
                    trade_date=trade_date,
                    window_size=7,
                )
                print(f"[HistoryMaintainer] Done {name} summary: {symbol} @ {trade_date}, status={status}")
                results["history_maintainer_log"].append(
                    {
                        "analyst_type": name,
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "status": status,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[HistoryMaintainer] {name} summary failed: {exc}")
                results["history_maintainer_log"].append(
                    {
                        "analyst_type": name,
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        return results

    return history_maintainer_node
