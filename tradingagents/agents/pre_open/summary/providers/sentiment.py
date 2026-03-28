from __future__ import annotations

from tradingagents.agents.pre_open.summary._db_helpers import query_history_report, query_today_report
from tradingagents.agents.utils.agentstate.agent_states import AgentState, AnalystMemorySummary


def load_sentiment_summary(conn, state: AgentState) -> AnalystMemorySummary:
    symbol = state["company_of_interest"]
    trade_date = state["trade_date"]
    trading_session = state.get("trading_session", "post_close")
    return {
        "today_report": query_today_report(conn, "sentiment", symbol, trade_date, "Sentiment Analysis Report"),
        "history_report": query_history_report(
            conn, "sentiment", symbol, trade_date, trading_session, "Sentiment History Summary"
        ),
    }

