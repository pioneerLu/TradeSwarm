"""
Memory DB 交互工具模块（兼容层）。

实际实现已迁移至 :mod:`tradingagents.db.memory_db`。
本文件保留全部公开 API 以避免下游 import 断裂。
"""

from tradingagents.db.memory_db import MemoryDBHelper  # noqa: F401

from typing import Any, Dict, List, Optional

# ==================== 便捷函数（保留兼容） ====================

def insert_report(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    report_content: str,
    db_path: str = "memory.db",
) -> bool:
    with MemoryDBHelper(db_path) as helper:
        return helper.insert_report(analyst_type, symbol, trade_date, report_content)


def query_today_report(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    db_path: str = "memory.db",
) -> Optional[str]:
    with MemoryDBHelper(db_path) as helper:
        return helper.query_today_report(analyst_type, symbol, trade_date)


def query_history_reports(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    lookback_days: int = 7,
    db_path: str = "memory.db",
) -> List[Dict[str, Any]]:
    with MemoryDBHelper(db_path) as helper:
        return helper.query_history_reports(analyst_type, symbol, trade_date, lookback_days)


def upsert_summary(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    summary_content: str,
    window_start_date: str,
    window_end_date: str,
    source_reports_count: int,
    llm_model: Optional[str] = None,
    token_usage: Optional[int] = None,
    db_path: str = "memory.db",
) -> bool:
    with MemoryDBHelper(db_path) as helper:
        return helper.upsert_summary(
            analyst_type=analyst_type,
            symbol=symbol,
            trade_date=trade_date,
            summary_content=summary_content,
            window_start_date=window_start_date,
            window_end_date=window_end_date,
            source_reports_count=source_reports_count,
            llm_model=llm_model,
            token_usage=token_usage,
        )


def query_summary(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    db_path: str = "memory.db",
) -> Optional[Dict[str, Any]]:
    with MemoryDBHelper(db_path) as helper:
        return helper.query_summary(analyst_type, symbol, trade_date)
