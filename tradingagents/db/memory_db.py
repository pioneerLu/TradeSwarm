"""
Memory DB 交互层。

原始 1300+ 行 ``agents/utils/memory_db_helper.py`` 的精简重构版：
- DDL 集中在 :mod:`tradingagents.db.schema`
- 线程安全连接由内部 ``threading.local`` 管理（与原实现一致）
- 公开 API 不变，下游无需改动
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tradingagents.db.schema import ensure_schema

logger = logging.getLogger(__name__)


class MemoryDBHelper:
    """Thread-safe helper for ``memory.db`` CRUD operations."""

    def __init__(
        self,
        db_path: str = "memory.db",
        trading_dates_resolver: Optional[Callable[[str, int], List[str]]] = None,
    ) -> None:
        self.db_path = Path(db_path)
        self._conn_local = threading.local()
        self.trading_dates_resolver = trading_dates_resolver
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        conn = sqlite3.connect(self.db_path)
        ensure_schema(conn)
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._conn_local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            self._conn_local.conn = conn
        return conn

    def _rollback_current_thread(self) -> None:
        conn = getattr(self._conn_local, "conn", None)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

    def close(self) -> None:
        conn = getattr(self._conn_local, "conn", None)
        if conn is not None:
            conn.close()
            self._conn_local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ==================================================================
    # analyst_reports
    # ==================================================================

    def insert_report(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        report_content: str,
    ) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO analyst_reports (analyst_type, symbol, trade_date, report_content) VALUES (?, ?, ?, ?)",
                (analyst_type, symbol, trade_date, report_content),
            )
            conn.commit()
            cur.close()
            logger.info("[OK] 成功插入报告: %s - %s - %s", analyst_type, symbol, trade_date)
            return True
        except Exception as e:
            logger.error("[ERROR] 插入报告失败: %s", e)
            self._rollback_current_thread()
            return False

    def insert_report_or_update(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        report_content: str,
    ) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM analyst_reports WHERE analyst_type=? AND symbol=? AND trade_date=? ORDER BY id DESC LIMIT 1",
                (analyst_type, symbol, trade_date),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE analyst_reports SET report_content=?, created_at=CURRENT_TIMESTAMP WHERE id=?",
                    (report_content, row[0]),
                )
                conn.commit()
                cur.close()
                logger.info("[OK] 已更新报告: %s - %s - %s", analyst_type, symbol, trade_date)
                return True
            cur.close()
            return self.insert_report(analyst_type, symbol, trade_date, report_content)
        except Exception as e:
            logger.error("[ERROR] 插入/更新报告失败: %s", e)
            self._rollback_current_thread()
            return False

    def query_today_report(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
    ) -> Optional[str]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT report_content FROM analyst_reports WHERE analyst_type=? AND symbol=? AND trade_date=? ORDER BY created_at DESC LIMIT 1",
                (analyst_type, symbol, trade_date),
            )
            result = cur.fetchone()
            cur.close()
            return result[0] if result and result[0] else None
        except Exception as e:
            logger.error("[ERROR] 查询今日报告失败: %s", e)
            return None

    def query_history_reports(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        lookback_days: int = 7,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            if self.trading_dates_resolver:
                dates = self.trading_dates_resolver(trade_date, lookback_days)
                if dates:
                    ph = ",".join("?" * len(dates))
                    cur.execute(
                        f"SELECT id, trade_date, report_content, created_at FROM analyst_reports "
                        f"WHERE analyst_type=? AND symbol=? AND trade_date IN ({ph}) "
                        f"AND report_content IS NOT NULL AND report_content != '' ORDER BY trade_date ASC, created_at ASC",
                        (analyst_type, symbol, *dates),
                    )
                    rows = cur.fetchall()
                    cur.close()
                    return [{"id": r[0], "trade_date": r[1], "report_content": r[2], "created_at": r[3]} for r in rows]

            sql = (
                "SELECT id, trade_date, report_content, created_at FROM analyst_reports "
                "WHERE analyst_type=? AND symbol=? AND trade_date<=? AND trade_date>=date(?, '-{} days') "
                "AND report_content IS NOT NULL AND report_content != '' ORDER BY trade_date ASC, created_at ASC"
            ).format(lookback_days)
            cur.execute(sql, (analyst_type, symbol, trade_date, trade_date))
            rows = cur.fetchall()
            cur.close()
            return [{"id": r[0], "trade_date": r[1], "report_content": r[2], "created_at": r[3]} for r in rows]
        except Exception as e:
            logger.error("[ERROR] 查询历史报告失败: %s", e)
            return []

    def query_all_reports(
        self,
        analyst_type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            conditions: List[str] = []
            params: List[Any] = []
            if analyst_type:
                conditions.append("analyst_type = ?")
                params.append(analyst_type)
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            lim = f" LIMIT {limit}" if limit else ""
            cur.execute(
                f"SELECT id, analyst_type, symbol, trade_date, created_at FROM analyst_reports{where} ORDER BY created_at DESC{lim}",
                params,
            )
            rows = cur.fetchall()
            cur.close()
            return [{"id": r[0], "analyst_type": r[1], "symbol": r[2], "trade_date": r[3], "created_at": r[4]} for r in rows]
        except Exception as e:
            logger.error("[ERROR] 查询所有报告失败: %s", e)
            return []

    def update_report(self, report_id: int, report_content: str) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE analyst_reports SET report_content=?, created_at=CURRENT_TIMESTAMP WHERE id=?", (report_content, report_id))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error("[ERROR] 更新报告失败: %s", e)
            self._rollback_current_thread()
            return False

    def delete_report(self, report_id: int) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM analyst_reports WHERE id=?", (report_id,))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error("[ERROR] 删除报告失败: %s", e)
            self._rollback_current_thread()
            return False

    def get_statistics(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            if symbol:
                cur.execute(
                    "SELECT analyst_type, COUNT(*), MIN(trade_date), MAX(trade_date) FROM analyst_reports WHERE symbol=? GROUP BY analyst_type",
                    (symbol,),
                )
            else:
                cur.execute("SELECT analyst_type, COUNT(*), MIN(trade_date), MAX(trade_date) FROM analyst_reports GROUP BY analyst_type")
            rows = cur.fetchall()
            cur.close()
            stats: Dict[str, Any] = {"total_reports": 0, "by_type": {}}
            for r in rows:
                stats["total_reports"] += r[1]
                stats["by_type"][r[0]] = {"count": r[1], "earliest_date": r[2], "latest_date": r[3]}
            return stats
        except Exception as e:
            logger.error("[ERROR] 获取统计信息失败: %s", e)
            return {"total_reports": 0, "by_type": {}}

    # ==================================================================
    # analyst_summaries
    # ==================================================================

    def upsert_summary(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        summary_content: str,
        window_start_date: str,
        window_end_date: str,
        source_reports_count: int,
        llm_model: Optional[str] = None,
        token_usage: Optional[int] = None,
    ) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO analyst_summaries
                   (analyst_type, symbol, trade_date, summary_content,
                    window_start_date, window_end_date, source_reports_count,
                    llm_model, token_usage, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                   ON CONFLICT(analyst_type, symbol, trade_date) DO UPDATE SET
                     summary_content=excluded.summary_content,
                     window_start_date=excluded.window_start_date,
                     window_end_date=excluded.window_end_date,
                     source_reports_count=excluded.source_reports_count,
                     llm_model=excluded.llm_model,
                     token_usage=excluded.token_usage,
                     updated_at=CURRENT_TIMESTAMP""",
                (analyst_type, symbol, trade_date, summary_content,
                 window_start_date, window_end_date, source_reports_count,
                 llm_model, token_usage),
            )
            conn.commit()
            cur.close()
            logger.info(
                "[OK] 成功更新 summary: %s - %s - %s (窗口 %s ~ %s, 报告数=%d)",
                analyst_type, symbol, trade_date, window_start_date, window_end_date, source_reports_count,
            )
            return True
        except Exception as e:
            logger.error("[ERROR] 更新 summary 失败: %s", e)
            self._rollback_current_thread()
            return False

    def query_summary(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, analyst_type, symbol, trade_date, summary_content,
                          window_start_date, window_end_date, source_reports_count,
                          llm_model, token_usage, created_at, updated_at
                   FROM analyst_summaries
                   WHERE analyst_type=? AND symbol=? AND trade_date=? LIMIT 1""",
                (analyst_type, symbol, trade_date),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            keys = [
                "id", "analyst_type", "symbol", "trade_date", "summary_content",
                "window_start_date", "window_end_date", "source_reports_count",
                "llm_model", "token_usage", "created_at", "updated_at",
            ]
            return dict(zip(keys, row))
        except Exception as e:
            logger.error("[ERROR] 查询 summary 失败: %s", e)
            return None

    # ==================================================================
    # daily_trading_summaries
    # ==================================================================

    def upsert_daily_trading_summary(
        self,
        date: str,
        symbol: str,
        summary_json: str,
        market_regime: Optional[str] = None,
        selected_strategy: Optional[str] = None,
        expected_behavior: Optional[str] = None,
        actual_return: Optional[float] = None,
        actual_max_drawdown: Optional[float] = None,
        positioning: Optional[str] = None,
        anomaly: Optional[str] = None,
    ) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO daily_trading_summaries
                   (date, symbol, market_regime, selected_strategy, expected_behavior,
                    actual_return, actual_max_drawdown, positioning, anomaly, summary_json,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                   ON CONFLICT(date, symbol) DO UPDATE SET
                     market_regime=excluded.market_regime,
                     selected_strategy=excluded.selected_strategy,
                     expected_behavior=excluded.expected_behavior,
                     actual_return=excluded.actual_return,
                     actual_max_drawdown=excluded.actual_max_drawdown,
                     positioning=excluded.positioning,
                     anomaly=excluded.anomaly,
                     summary_json=excluded.summary_json,
                     updated_at=CURRENT_TIMESTAMP""",
                (date, symbol, market_regime, selected_strategy, expected_behavior,
                 actual_return, actual_max_drawdown, positioning, anomaly, summary_json),
            )
            conn.commit()
            cur.close()
            logger.info("[OK] 成功更新 daily trading summary: %s - %s", date, symbol)
            return True
        except Exception as e:
            logger.error("[ERROR] 更新 daily trading summary 失败: %s", e)
            self._rollback_current_thread()
            return False

    def query_daily_trading_summary(self, date: str, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, date, symbol, market_regime, selected_strategy,
                          expected_behavior, actual_return, actual_max_drawdown,
                          positioning, anomaly, summary_json, created_at, updated_at
                   FROM daily_trading_summaries WHERE date=? AND symbol=? LIMIT 1""",
                (date, symbol),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            keys = [
                "id", "date", "symbol", "market_regime", "selected_strategy",
                "expected_behavior", "actual_return", "actual_max_drawdown",
                "positioning", "anomaly", "summary_json", "created_at", "updated_at",
            ]
            return dict(zip(keys, row))
        except Exception as e:
            logger.error("[ERROR] 查询 daily trading summary 失败: %s", e)
            return None

    def query_daily_trading_summaries_by_date_range(
        self, symbol: str, start_date: str, end_date: str,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, date, symbol, market_regime, selected_strategy,
                          expected_behavior, actual_return, actual_max_drawdown,
                          positioning, anomaly, summary_json, created_at, updated_at
                   FROM daily_trading_summaries WHERE symbol=? AND date>=? AND date<=? ORDER BY date ASC""",
                (symbol, start_date, end_date),
            )
            rows = cur.fetchall()
            cur.close()
            keys = [
                "id", "date", "symbol", "market_regime", "selected_strategy",
                "expected_behavior", "actual_return", "actual_max_drawdown",
                "positioning", "anomaly", "summary_json", "created_at", "updated_at",
            ]
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            logger.error("[ERROR] 查询 daily trading summaries 失败: %s", e)
            return []

    # ==================================================================
    # cycle_reflections
    # ==================================================================

    def upsert_cycle_reflection(
        self,
        cycle_type: str,
        cycle_start_date: str,
        cycle_end_date: str,
        reflection_content: str,
        symbol: Optional[str] = None,
        key_insights: Optional[str] = None,
        error_patterns: Optional[str] = None,
        success_patterns: Optional[str] = None,
        strategy_conditions: Optional[str] = None,
        environment_biases: Optional[str] = None,
    ) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """INSERT OR REPLACE INTO cycle_reflections
                   (cycle_type, cycle_start_date, cycle_end_date, symbol,
                    reflection_content, key_insights, error_patterns, success_patterns,
                    strategy_conditions, environment_biases, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (cycle_type, cycle_start_date, cycle_end_date, symbol,
                 reflection_content, key_insights, error_patterns, success_patterns,
                 strategy_conditions, environment_biases),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error("[ERROR] 插入/更新 cycle reflection 失败: %s", e)
            return False

    def query_cycle_reflection(
        self,
        cycle_type: str,
        cycle_start_date: str,
        cycle_end_date: str,
        symbol: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            if symbol:
                cur.execute(
                    """SELECT id, cycle_type, cycle_start_date, cycle_end_date, symbol,
                              reflection_content, key_insights, error_patterns, success_patterns,
                              strategy_conditions, environment_biases, created_at, updated_at
                       FROM cycle_reflections
                       WHERE cycle_type=? AND cycle_start_date=? AND cycle_end_date=? AND symbol=?""",
                    (cycle_type, cycle_start_date, cycle_end_date, symbol),
                )
            else:
                cur.execute(
                    """SELECT id, cycle_type, cycle_start_date, cycle_end_date, symbol,
                              reflection_content, key_insights, error_patterns, success_patterns,
                              strategy_conditions, environment_biases, created_at, updated_at
                       FROM cycle_reflections
                       WHERE cycle_type=? AND cycle_start_date=? AND cycle_end_date=? AND symbol IS NULL""",
                    (cycle_type, cycle_start_date, cycle_end_date),
                )
            result = cur.fetchone()
            cur.close()
            if not result:
                return None
            keys = [
                "id", "cycle_type", "cycle_start_date", "cycle_end_date", "symbol",
                "reflection_content", "key_insights", "error_patterns", "success_patterns",
                "strategy_conditions", "environment_biases", "created_at", "updated_at",
            ]
            return dict(zip(keys, result))
        except Exception as e:
            logger.error("[ERROR] 查询 cycle reflection 失败: %s", e)
            return None

    # ==================================================================
    # portfolio_snapshots
    # ==================================================================

    def upsert_portfolio_snapshot(
        self,
        symbol: str,
        trade_date: str,
        experiment_id: str = "",
        source: str = "qc_real",
        equity: float = 0.0,
        cash: float = 0.0,
        shares: float = 0.0,
        avg_price: float = 0.0,
        market_price: float = 0.0,
        unrealized_pnl: float = 0.0,
        unrealized_pnl_pct: float = 0.0,
        signal_action: Optional[str] = None,
        fill_price: Optional[float] = None,
        fill_qty: Optional[float] = None,
        snapshot_json: Optional[str] = None,
    ) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO portfolio_snapshots
                   (symbol, trade_date, experiment_id, source,
                    equity, cash, shares, avg_price, market_price,
                    unrealized_pnl, unrealized_pnl_pct,
                    signal_action, fill_price, fill_qty, snapshot_json,
                    created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(symbol, trade_date, experiment_id, source) DO UPDATE SET
                     equity=excluded.equity,
                     cash=excluded.cash,
                     shares=excluded.shares,
                     avg_price=excluded.avg_price,
                     market_price=excluded.market_price,
                     unrealized_pnl=excluded.unrealized_pnl,
                     unrealized_pnl_pct=excluded.unrealized_pnl_pct,
                     signal_action=excluded.signal_action,
                     fill_price=excluded.fill_price,
                     fill_qty=excluded.fill_qty,
                     snapshot_json=excluded.snapshot_json,
                     created_at=CURRENT_TIMESTAMP""",
                (symbol, trade_date, experiment_id, source,
                 equity, cash, shares, avg_price, market_price,
                 unrealized_pnl, unrealized_pnl_pct,
                 signal_action, fill_price, fill_qty, snapshot_json),
            )
            conn.commit()
            cur.close()
            logger.info("[OK] upsert portfolio snapshot: %s %s %s", symbol, trade_date, source)
            return True
        except Exception as e:
            logger.error("[ERROR] upsert portfolio snapshot failed: %s", e)
            self._rollback_current_thread()
            return False

    def load_latest_snapshot(
        self,
        symbol: str,
        experiment_id: str = "",
        source: str = "qc_real",
    ) -> Optional[Dict[str, Any]]:
        """Load most recent portfolio snapshot for cross-run resume."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """SELECT symbol, trade_date, experiment_id, source,
                          equity, cash, shares, avg_price, market_price,
                          unrealized_pnl, unrealized_pnl_pct,
                          signal_action, fill_price, fill_qty, snapshot_json
                   FROM portfolio_snapshots
                   WHERE symbol=? AND experiment_id=? AND source=?
                   ORDER BY trade_date DESC LIMIT 1""",
                (symbol, experiment_id, source),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            keys = [
                "symbol", "trade_date", "experiment_id", "source",
                "equity", "cash", "shares", "avg_price", "market_price",
                "unrealized_pnl", "unrealized_pnl_pct",
                "signal_action", "fill_price", "fill_qty", "snapshot_json",
            ]
            return dict(zip(keys, row))
        except Exception as e:
            logger.error("[ERROR] load latest snapshot failed: %s", e)
            return None

    def query_portfolio_snapshots(
        self,
        symbol: str,
        experiment_id: str = "",
        source: str = "qc_real",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            conditions = ["symbol=?", "experiment_id=?", "source=?"]
            params: List[Any] = [symbol, experiment_id, source]
            if start_date:
                conditions.append("trade_date>=?")
                params.append(start_date)
            if end_date:
                conditions.append("trade_date<=?")
                params.append(end_date)
            where = " AND ".join(conditions)
            cur.execute(
                f"""SELECT symbol, trade_date, experiment_id, source,
                           equity, cash, shares, avg_price, market_price,
                           unrealized_pnl, unrealized_pnl_pct,
                           signal_action, fill_price, fill_qty, snapshot_json
                    FROM portfolio_snapshots WHERE {where}
                    ORDER BY trade_date ASC""",
                params,
            )
            rows = cur.fetchall()
            cur.close()
            keys = [
                "symbol", "trade_date", "experiment_id", "source",
                "equity", "cash", "shares", "avg_price", "market_price",
                "unrealized_pnl", "unrealized_pnl_pct",
                "signal_action", "fill_price", "fill_qty", "snapshot_json",
            ]
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            logger.error("[ERROR] query portfolio snapshots failed: %s", e)
            return []

    # ==================================================================
    # cycle_reflections
    # ==================================================================

    def query_cycle_reflections_by_symbol(
        self,
        symbol: str,
        cycle_type: str = "weekly",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, cycle_type, cycle_start_date, cycle_end_date, symbol,
                          reflection_content, key_insights, error_patterns, success_patterns,
                          strategy_conditions, environment_biases, created_at, updated_at
                   FROM cycle_reflections
                   WHERE cycle_type=? AND symbol=?
                   ORDER BY cycle_end_date DESC, created_at DESC LIMIT ?""",
                (cycle_type, symbol, limit),
            )
            rows = cur.fetchall()
            cur.close()
            keys = [
                "id", "cycle_type", "cycle_start_date", "cycle_end_date", "symbol",
                "reflection_content", "key_insights", "error_patterns", "success_patterns",
                "strategy_conditions", "environment_biases", "created_at", "updated_at",
            ]
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            logger.error("[ERROR] 按 symbol 查询 cycle reflections 失败: %s", e)
            return []
