"""
memory.db 的统一 DDL 定义。

所有表结构集中在此文件，由 :class:`MemoryDBHelper` 在初始化时调用
:func:`ensure_schema` 创建。
"""

from __future__ import annotations

import sqlite3

# ------------------------------------------------------------------
# Table DDL
# ------------------------------------------------------------------

ANALYST_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS analyst_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyst_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    report_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

ANALYST_SUMMARIES_DDL = """
CREATE TABLE IF NOT EXISTS analyst_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyst_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    summary_content TEXT NOT NULL,
    window_start_date TEXT NOT NULL,
    window_end_date TEXT NOT NULL,
    source_reports_count INTEGER,
    llm_model TEXT,
    token_usage INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analyst_type, symbol, trade_date)
)
"""

DAILY_TRADING_SUMMARIES_DDL = """
CREATE TABLE IF NOT EXISTS daily_trading_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    market_regime TEXT,
    selected_strategy TEXT,
    expected_behavior TEXT,
    actual_return REAL,
    actual_max_drawdown REAL,
    positioning TEXT,
    anomaly TEXT,
    summary_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, symbol)
)
"""

PORTFOLIO_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    experiment_id TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'qc_real',
    equity REAL,
    cash REAL,
    shares REAL DEFAULT 0,
    avg_price REAL DEFAULT 0,
    market_price REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    unrealized_pnl_pct REAL DEFAULT 0,
    signal_action TEXT,
    fill_price REAL,
    fill_qty REAL,
    snapshot_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trade_date, experiment_id, source)
)
"""

CYCLE_REFLECTIONS_DDL = """
CREATE TABLE IF NOT EXISTS cycle_reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_type TEXT NOT NULL,
    cycle_start_date TEXT NOT NULL,
    cycle_end_date TEXT NOT NULL,
    symbol TEXT,
    reflection_content TEXT NOT NULL,
    key_insights TEXT,
    error_patterns TEXT,
    success_patterns TEXT,
    strategy_conditions TEXT,
    environment_biases TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cycle_type, cycle_start_date, cycle_end_date, symbol)
)
"""

# ------------------------------------------------------------------
# Indexes
# ------------------------------------------------------------------

INDEXES = [
    """CREATE INDEX IF NOT EXISTS idx_analyst_reports_lookup
       ON analyst_reports(analyst_type, symbol, trade_date)""",
    """CREATE INDEX IF NOT EXISTS idx_analyst_summaries_lookup
       ON analyst_summaries(analyst_type, symbol, trade_date)""",
    """CREATE INDEX IF NOT EXISTS idx_daily_trading_summaries_lookup
       ON daily_trading_summaries(date, symbol)""",
    """CREATE INDEX IF NOT EXISTS idx_cycle_reflections_lookup
       ON cycle_reflections(cycle_type, cycle_start_date, cycle_end_date, symbol)""",
    """CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_lookup
       ON portfolio_snapshots(symbol, trade_date, experiment_id)""",
]

ALL_DDL = [
    ANALYST_REPORTS_DDL,
    ANALYST_SUMMARIES_DDL,
    DAILY_TRADING_SUMMARIES_DDL,
    PORTFOLIO_SNAPSHOTS_DDL,
    CYCLE_REFLECTIONS_DDL,
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist yet."""
    cursor = conn.cursor()
    for ddl in ALL_DDL:
        cursor.execute(ddl)
    for idx in INDEXES:
        cursor.execute(idx)
    conn.commit()
    cursor.close()
