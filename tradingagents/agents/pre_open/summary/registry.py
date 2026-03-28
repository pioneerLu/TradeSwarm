from __future__ import annotations

from typing import Dict, Tuple

from tradingagents.agents.pre_open.summary.providers import (
    load_fundamentals_summary,
    load_market_summary,
    load_news_summary,
    load_sentiment_summary,
)
from tradingagents.agents.pre_open.summary.types import SummaryProviderSpec

DEFAULT_ENABLED_ANALYSTS: Tuple[str, ...] = ("market", "news", "sentiment", "fundamentals")


def get_summary_registry(conn) -> Dict[str, SummaryProviderSpec]:
    return {
        "market": {
            "analyst_type": "market",
            "report_title": "Market Analysis Report",
            "node_name": "market_summary",
            "loader": lambda state: load_market_summary(conn, state),
        },
        "news": {
            "analyst_type": "news",
            "report_title": "News Analysis Report",
            "node_name": "news_summary",
            "loader": lambda state: load_news_summary(conn, state),
        },
        "sentiment": {
            "analyst_type": "sentiment",
            "report_title": "Sentiment Analysis Report",
            "node_name": "sentiment_summary",
            "loader": lambda state: load_sentiment_summary(conn, state),
        },
        "fundamentals": {
            "analyst_type": "fundamentals",
            "report_title": "Fundamentals Analysis Report",
            "node_name": "fundamentals_summary",
            "loader": lambda state: load_fundamentals_summary(conn, state),
        },
    }

